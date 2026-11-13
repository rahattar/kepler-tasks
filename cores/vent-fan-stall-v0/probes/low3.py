#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os
import numpy as np, pandas as pd
import scipy.sparse as sp
from scipy.optimize import brentq
from scipy.sparse.linalg import splu


def load(d):
    rd = lambda f: pd.read_csv(os.path.join(d, f), dtype=str, keep_default_na=False)
    return (rd('branches.csv'), rd('regulators.csv'), rd('doors.csv'), rd('fans.csv'),
            rd('fan_curves.csv'), rd('log.csv'), rd('points.csv'))


class Inner:
    """Square-law network between ATM (p=0) and fan house (p=-1)."""
    def __init__(self, fr, to, fh):
        nodes = sorted(set(fr) | set(to))
        idx = {n: i for i, n in enumerate(nodes)}
        self.fi = np.array([idx[n] for n in fr]); self.ti = np.array([idx[n] for n in to])
        nb = len(fr)
        self.fixed = {idx['ATM']: 0.0, idx[fh]: -1.0}
        free = [i for i in range(len(nodes)) if i not in self.fixed]
        fmap = -np.ones(len(nodes), int); fmap[free] = np.arange(len(free))
        self.nf = len(free)
        p0 = np.zeros(len(nodes))
        for k, v in self.fixed.items(): p0[k] = v
        self.p0 = p0
        rows = np.r_[np.arange(nb), np.arange(nb)]
        cols = np.r_[self.fi, self.ti]; vals = np.r_[np.ones(nb), -np.ones(nb)]
        A = sp.csr_matrix((vals, (rows, cols)), shape=(nb, len(nodes)))
        self.A = A
        self.Af = A[:, free].tocsc()
        self.Afix_p = A @ p0          # contribution of fixed pressures to dp
        self.free = np.array(free)
        self.q = None

    def _pattern(self):
        # M = Af^T diag(w) Af, assembled straight into a fixed CSC pattern
        Af = self.Af.tocoo()
        nb = self.Af.shape[0]
        rows_b = [[] for _ in range(nb)]
        for r, c, v in zip(Af.row, Af.col, Af.data):
            rows_b[r].append((c, v))
        I, J, V, B = [], [], [], []
        for b_, ent in enumerate(rows_b):
            for c1, v1 in ent:
                for c2, v2 in ent:
                    I.append(c1); J.append(c2); V.append(v1 * v2); B.append(b_)
        I, J, V, B = map(np.array, (I, J, V, B))
        key = J * self.nf + I
        order = np.argsort(key, kind='stable')
        uk, inv = np.unique(key[order], return_inverse=True)
        self.slot = np.empty(len(key), int); self.slot[order] = inv
        self.V, self.B = V, B
        ui, uj = uk % self.nf, uk // self.nf
        self.indices = ui.astype(np.int32)
        self.indptr = np.searchsorted(uj, np.arange(self.nf + 1)).astype(np.int32)
        self.nnz = len(uk)
        self.AfT = self.Af.T.tocsr()

    def solve(self, R):
        if not hasattr(self, 'slot'):
            self._pattern()
        Af, AfT = self.Af, self.AfT
        q = self.q if self.q is not None else np.full(len(R), 1e-3)
        pf = self.pf if self.q is not None else np.zeros(self.nf)
        for it in range(200):
            dpb = Af @ pf + self.Afix_p
            r = R * q * np.abs(q) - dpb
            Di = 1.0 / (2 * R * np.maximum(np.abs(q), 1e-6))
            data = np.bincount(self.slot, weights=self.V * Di[self.B], minlength=self.nnz)
            M = sp.csc_matrix((data, self.indices, self.indptr), shape=(self.nf, self.nf))
            rhs = AfT @ (Di * r - q)
            dpf = splu(M, permc_spec=PERMC).solve(rhs)
            dq = Di * (Af @ dpf - r)
            pf = pf + dpf; q = q + dq
            if it > 0 and np.max(np.abs(dq)) < 1e-6 * np.max(np.abs(q)):
                break
        self.q, self.pf = q, pf
        return q

PERMC = os.environ.get('PERMC', 'MMD_AT_PLUS_A')


def main(pkg, out):
    br, regs, doors, fans, curves, log, pts = load(pkg)
    nb = len(br)
    fanmask = (br.kind == 'fan').values
    fanbr = br[fanmask]
    fh = fanbr.from_node.iloc[0]
    assert (fanbr.to_node == 'ATM').all() and (fanbr.from_node == fh).all()
    ib = br[~fanmask].reset_index(drop=True)
    inner = Inner(list(ib.from_node), list(ib.to_node), fh)
    bidx = {b: i for i, b in enumerate(ib.branch)}
    Rbase = np.array([float(x) if x else 0.0 for x in ib.resistance_Ns2_m8])
    usidx = None
    regtab = {(r.regulator, int(float(r.setting))): float(r.resistance_Ns2_m8) for r in regs.itertuples()}
    doortab = {d.door: (float(d.resistance_closed_Ns2_m8), float(d.resistance_open_Ns2_m8)) for d in doors.itertuples()}
    item_br = {}
    for i, r in ib.iterrows():
        if r.kind in ('regulator', 'door'):
            item_br.setdefault(r['item'], []).append(i)
    # fans
    F = []
    for r in fanbr.itertuples():
        f = fans[fans.fan == r.item].iloc[0]
        c = curves[(curves.model == f.model) & (curves.blade_setting == f.blade_setting)]
        F.append((r.branch, float(r.resistance_Ns2_m8), c.flow_m3_s.astype(float).values,
                  c.pressure_Pa.astype(float).values))
    FS = FanSet(F)
    # node flow out of fan house through inner: branches touching fh
    into_fh = np.array([1.0 if t == fh else (-1.0 if f_ == fh else 0.0)
                        for f_, t in zip(ib.from_node, ib.to_node)])

    # states
    log = log.sort_values('time', kind='stable')
    t0 = log.time.iloc[0]
    state = {}
    def apply(row):
        it, s = row['item'], row['setting']
        if it in doortab:
            state[it] = doortab[it][0] if s == 'closed' else doortab[it][1]
        else:
            state[it] = regtab[(it, int(float(s)))]
    pts = pts.copy()
    res = np.zeros(len(pts))
    ltimes = sorted(set(log.time))
    # each point belongs to the latest log time before it
    pk = np.searchsorted(np.array(ltimes), pts.time.values, side='right') - 1
    pk = np.maximum(pk, 0)
    groups = log.groupby('time', sort=True)
    fq_prev = None
    for k, (tm, g) in enumerate(groups):
        for _, row in g.iterrows():
            apply(row)
        R = Rbase.copy()
        for it, v in state.items():
            for i in item_br.get(it, []): R[i] = v
        q1 = inner.solve(R)              # flows at suction 1 Pa
        Q1 = float(into_fh @ q1)
        Req = 1.0 / Q1 ** 2
        fq_prev = fan_point(FS, F, Req, fq_prev)
        s, fq = fq_prev[0], fq_prev[1]
        sel = np.nonzero(pk == k)[0]
        if len(sel):
            flows = q1 * np.sqrt(s)
            fanflow = {F[j][0]: fq[j] for j in range(len(F))}
            for i in sel:
                b_ = pts.branch.values[i]
                res[i] = fanflow[b_] if b_ in fanflow else flows[bidx[b_]]
    pd.DataFrame({'point': pts.point, 'flow_m3_s': np.round(res, 6)}).to_csv(out, index=False)


class FanSet:
    """Each fan branch's suction curve G(q) = P(q) - Rd q^2, split into monotone pieces."""
    def __init__(self, F):
        self.pieces = []
        for _, Rd, x, y in F:
            qq = np.unique(np.concatenate([np.linspace(x[j], x[j+1], 200) for j in range(len(x)-1)]))
            G = np.interp(qq, x, y) - Rd * qq * qq
            dG = np.sign(np.diff(G))
            cuts = [0] + [i+1 for i in range(len(dG)-1) if dG[i] != dG[i+1]] + [len(qq)-1]
            P = []
            for a, b in zip(cuts[:-1], cuts[1:]):
                gq, gs = qq[a:b+1], G[a:b+1]
                if gs[0] > gs[-1]: gq, gs = gq[::-1], gs[::-1]
                P.append((gs, gq))
            self.pieces.append(P)

    def solutions(self, Req):
        import itertools
        out = []
        for combo in itertools.product(*[range(len(p)) for p in self.pieces]):
            ps = [self.pieces[k][c] for k, c in enumerate(combo)]
            lo = max(p[0][0] for p in ps); hi = min(p[0][-1] for p in ps)
            lo = max(lo, 1e-9)
            if hi <= lo: continue
            sg = np.linspace(lo, hi, 2000)
            f = lambda s: sum(np.interp(s, p[0], p[1]) for p in ps) - np.sqrt(s / Req)
            v = f(sg)
            idx = np.nonzero(np.sign(v[:-1]) * np.sign(v[1:]) <= 0)[0]
            for i in idx:
                if v[i] == 0: s = sg[i]
                elif v[i+1] == 0: continue
                else: s = brentq(f, sg[i], sg[i+1], xtol=1e-10, rtol=1e-13)
                out.append((s, [float(np.interp(s, p[0], p[1])) for p in ps], combo))
        # dedupe
        res = []
        for c in out:
            if all(abs(c[0]-d[0]) > 1e-6 * c[0] or max(abs(u-w) for u, w in zip(c[1], d[1])) > 1e-6 for d in res):
                res.append(c)
        return res


def slope(Fk, q):
    _, Rd, x, y = Fk
    j = min(max(np.searchsorted(x, q) - 1, 0), len(x) - 2)
    return (y[j+1] - y[j]) / (x[j+1] - x[j]) - 2 * Rd * q


def stable(F, Req, qs):
    """Linear stability of the fan-house operating point: L dq_i/dt = G_i(q_i) - Req (sum q)^2."""
    Q = sum(qs)
    J = np.diag([slope(F[k], qs[k]) for k in range(len(F))]) - 2 * Req * Q
    return np.max(np.linalg.eigvals(J).real) < 0


def G(Fk, q):
    _, Rd, x, y = Fk
    j = np.clip(np.searchsorted(x, q) - 1, 0, len(x) - 2)
    return y[j] + (y[j+1] - y[j]) / (x[j+1] - x[j]) * (q - x[j]) - Rd * q * abs(q)


def transient(F, Req, q0):
    """Follow the fans from their previous operating point after a change of the district
    (L dq_i/dt = G_i(q_i) - Req Q|Q|, equal inertia), to the point they settle at."""
    from scipy.integrate import solve_ivp
    def rhs(t, q):
        Q = q.sum()
        return np.array([G(F[k], q[k]) for k in range(len(F))]) - Req * Q * abs(Q)
    r = solve_ivp(rhs, (0, 20.0), np.array(q0, float), method='LSODA', rtol=1e-6, atol=1e-6)
    return r.y[:, -1]


def fan_point(FS, F, Req, prev):
    cands = FS.solutions(Req)
    st = [c for c in cands if stable(F, Req, c[1])] or cands
    if prev is None:
        ch = max(st, key=lambda c: sum(c[1]))
    else:
        same = [c for c in st if c[2] == prev[2]]
        if same:      # changes are slow: the fans stay on the branch they were on
            ch = same[0]
        else:         # that branch has ended: the fans move to the point they settle at
            end = transient(F, Req, prev[1])
            ch = min(st, key=lambda c: sum((a - b) ** 2 for a, b in zip(c[1], end)))
    if DEBUG:
        print(len(cands), len(st), round(ch[0], 1), [round(v, 2) for v in ch[1]],
              [[round(v, 1) for v in c[1]] for c in st], file=sys.stderr)
    return ch

DEBUG = os.environ.get('AFDEBUG')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
