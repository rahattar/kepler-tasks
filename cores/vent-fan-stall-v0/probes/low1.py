#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4.

Usage: python3 airflow.py PACKAGE_DIR OUT_CSV

The network is solved (Newton / gradient method on branch flows and node
pressures) for every state of the regulators and doors in log order. Because
the fan characteristics have a stall dip, the steady flow can have more than
one solution; the flow followed is the one reached continuously from the
previous state (VS-4 section 5: changes are slow, the air follows), so every
change is tracked by continuation from the previous solution.
"""
import os
import sys

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu


def load(pkg):
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype=str, keep_default_na=False)
    br = rd("branches.csv")
    regs = rd("regulators.csv")
    doors = rd("doors.csv")
    fans = rd("fans.csv")
    curves = rd("fan_curves.csv")
    log = rd("log.csv")
    pts = rd("points.csv")
    return br, regs, doors, fans, curves, log, pts


class Net:
    def __init__(self, br, regs, doors, fans, curves):
        for c in br.columns:
            br[c] = br[c].str.strip()
        self.names = list(br["branch"])
        self.bidx = {n: i for i, n in enumerate(self.names)}
        nodes = sorted(set(br["from_node"]) | set(br["to_node"]))
        nodes.remove("ATM")
        nid = {n: i for i, n in enumerate(nodes)}
        nid["ATM"] = -1
        m = len(br)
        n = len(nodes)
        self.m, self.n = m, n
        fr = np.array([nid[x] for x in br["from_node"]])
        to = np.array([nid[x] for x in br["to_node"]])
        rows, cols, vals = [], [], []
        for b in range(m):
            if fr[b] >= 0:
                rows.append(fr[b]); cols.append(b); vals.append(1.0)
            if to[b] >= 0:
                rows.append(to[b]); cols.append(b); vals.append(-1.0)
        self.A = sp.csr_matrix((vals, (rows, cols)), shape=(n, m))
        self.AT = self.A.T.tocsr()
        # fixed pattern of M = A diag(w) A^T: M.data = self.P @ w
        Mpat = (self.A @ self.AT).tocsc()
        Mpat.sort_indices()
        self.Mpat = Mpat
        key = {}
        indptr, indices = Mpat.indptr, Mpat.indices
        for c in range(n):
            for k in range(indptr[c], indptr[c + 1]):
                key[(indices[k], c)] = k
        pr, pc, pv = [], [], []
        for b in range(m):
            ends = [(x, sgn) for x, sgn in ((fr[b], 1.0), (to[b], -1.0)) if x >= 0]
            for i, si in ends:
                for j, sj in ends:
                    pr.append(key[(i, j)]); pc.append(b); pv.append(si * sj)
        self.P = sp.csr_matrix((pv, (pr, pc)), shape=(Mpat.nnz, m))

        self.R = np.zeros(m)
        kind = list(br["kind"])
        item = list(br["item"])
        res = list(br["resistance_Ns2_m8"])
        # regulators / doors
        self.regtab = {}
        for r in regs.itertuples(index=False):
            self.regtab.setdefault(r.regulator.strip(), {})[float(r.setting)] = float(r.resistance_Ns2_m8)
        self.doortab = {d.door.strip(): (float(d.resistance_closed_Ns2_m8), float(d.resistance_open_Ns2_m8))
                        for d in doors.itertuples(index=False)}
        self.item_branches = {}
        for b in range(m):
            if kind[b] in ("airway", "fan"):
                self.R[b] = float(res[b])
            if kind[b] in ("regulator", "door"):
                self.item_branches.setdefault(item[b], []).append(b)
        # fans
        self.fan_b = []
        self.fan_q = []
        self.fan_p = []
        for f in fans.itertuples(index=False):
            fname = f.fan.strip()
            b = None
            if f.branch.strip() in self.bidx:
                b = self.bidx[f.branch.strip()]
            else:
                for i in range(m):
                    if kind[i] == "fan" and item[i] == fname:
                        b = i
            c = curves[(curves["model"].str.strip() == f.model.strip()) &
                       (curves["blade_setting"].astype(float) == float(f.blade_setting))]
            q = c["flow_m3_s"].astype(float).values
            p = c["pressure_Pa"].astype(float).values
            o = np.argsort(q, kind="stable")
            self.fan_b.append(b)
            self.fan_q.append(q[o])
            self.fan_p.append(p[o])
        self.fan_b = np.array(self.fan_b, dtype=int)

    def item_R(self, it, setting):
        if it in self.doortab:
            c, o = self.doortab[it]
            return o if str(setting).strip().lower() == "open" else c
        tab = self.regtab[it]
        s = float(setting)
        if s in tab:
            return tab[s]
        ks = sorted(tab)
        # log-linear interpolation (not expected to be needed)
        return float(np.exp(np.interp(s, ks, np.log([tab[k] for k in ks]))))

    def fan(self, k, q):
        xs, ps = self.fan_q[k], self.fan_p[k]
        j = min(max(int(np.searchsorted(xs, q)) - 1, 0), len(xs) - 2)
        s = (ps[j + 1] - ps[j]) / (xs[j + 1] - xs[j])
        return ps[j] + s * (q - xs[j]), s

    def residual(self, q, R, p):
        h = R * q * np.abs(q)
        for k, b in enumerate(self.fan_b):
            h[b] -= self.fan(k, q[b])[0]
        dp = self.AT @ p
        return dp - h

    def fan_int(self, k, q):
        """Integral of the fan pressure from 0 to q (linear extrapolation outside)."""
        xs, ps = self.fan_q[k], self.fan_p[k]
        if not hasattr(self, "_cum"):
            self._cum = {}
        if k not in self._cum:
            self._cum[k] = np.concatenate([[0.0], np.cumsum(0.5 * (ps[1:] + ps[:-1]) * np.diff(xs))])
        cum = self._cum[k]
        j = min(max(int(np.searchsorted(xs, q)) - 1, 0), len(xs) - 2)
        pq, _ = self.fan(k, q)
        return cum[j] - cum[0] * 0 + 0.5 * (ps[j] + pq) * (q - xs[j]) - (0.0 if xs[0] == 0 else 0.0)

    def content(self, R, q):
        F = np.sum(R * np.abs(q) ** 3) / 3.0
        for k, b in enumerate(self.fan_b):
            F -= self.fan_int(k, q[b])
        return F

    def hfun(self, R, q):
        aq = np.abs(q)
        h = R * q * aq
        s = np.zeros(len(self.fan_b))
        for k, b in enumerate(self.fan_b):
            pf, s[k] = self.fan(k, q[b])
            h[b] -= pf
        return h, s

    def mmat(self, w):
        M = self.Mpat.copy()
        M.data = self.P @ w
        return M

    def msolve(self, w, rhs):
        return splu(self.mmat(w), permc_spec="MMD_AT_PLUS_A",
                    options=dict(SymmetricMode=True, Equil=False)).solve(rhs)

    def solve(self, R, q, tol=1e-6, maxit=300):
        """Newton (gradient method) towards a local minimum of the network's
        content F(q) = sum R|q|^3/3 - sum int P_fan, subject to node balance.
        Stationary points of F are the steady flows of VS-4 section 2; the
        stable ones are its local minima, which is what the search follows."""
        A, AT = self.A, self.AT
        qscale = max(1.0, np.max(np.abs(q)))
        p = None
        balanced = False
        F = None
        for it in range(maxit):
            aq = np.abs(q)
            h, s = self.hfun(R, q)
            D = 2.0 * R * np.maximum(aq, 1e-4 * qscale)
            D[self.fan_b] -= s
            for attempt in range(2):
                Dm = D.copy()
                if attempt == 1:
                    fb = self.fan_b
                    Dm[fb] = np.maximum(Dm[fb], 2.0 * R[fb] * np.maximum(aq[fb], 1e-4 * qscale) + 1e-3)
                Dm[np.abs(Dm) < 1e-9] = 1e-9
                Di = 1.0 / Dm
                p = self.msolve(Di, A @ (h * Di - q))
                dq = (AT @ p - h) * Di
                if not balanced:
                    break
                slope = h @ dq
                if slope < 0:
                    break
            if not balanced:
                q = q + dq
                balanced = True
                F = self.content(R, q)
                continue
            lam = 1.0
            ok = False
            for _ in range(30):
                qn = q + lam * dq
                Fn = self.content(R, qn)
                if Fn <= F + 1e-4 * lam * slope:
                    ok = True
                    break
                lam *= 0.5
            q = qn if ok else q + lam * dq
            F = self.content(R, q)
            if np.max(np.abs(lam * dq)) < tol * qscale:
                break
        self.last_p = p
        return q, p, it


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    br, regs, doors, fans, curves, log, pts = load(pkg)
    net = Net(br, regs, doors, fans, curves)

    log = log.copy()
    log["t"] = pd.to_datetime(log["time"].str.strip())
    log["item"] = log["item"].str.strip()
    log = log.reset_index().sort_values(["t", "index"], kind="stable")
    pts = pts.copy()
    pts["t"] = pd.to_datetime(pts["time"].str.strip())

    R = net.R.copy()
    times = sorted(log["t"].unique())
    groups = {t: g for t, g in log.groupby("t", sort=True)}

    # first time: initial settings
    for r in groups[times[0]].itertuples():
        for b in net.item_branches.get(r.item, []):
            R[b] = net.item_R(r.item, r.setting)
    q0 = np.zeros(net.m)
    q0[net.fan_b] = [np.mean(x) for x in net.fan_q]
    q = stable_solve(net, R, q0 + 1.0)

    ptimes = np.array(sorted(pts["t"].unique()))
    states = []  # (time, q)
    states.append((times[0], q.copy()))
    for t in times[1:]:
        Rn = R.copy()
        for r in groups[t].itertuples():
            for b in net.item_branches.get(r.item, []):
                Rn[b] = net.item_R(r.item, r.setting)
        q = track(net, R, Rn, q)
        R = Rn
        states.append((t, q.copy()))

    st_t = np.array([s[0] for s in states])
    rows = []
    for r in pts.itertuples():
        i = np.searchsorted(st_t, np.datetime64(r.t), side="right") - 1
        i = max(i, 0)
        rows.append((r.point, states[i][1][net.bidx[r.branch.strip()]]))
    with open(out, "w") as f:
        f.write("point,flow_m3_s\n")
        for p, v in rows:
            f.write("%s,%.6f\n" % (p, v))
    if os.environ.get("AF_DEBUG"):
        print(STATS, file=sys.stderr)


def fan_seg(net, q):
    return tuple(int(np.searchsorted(net.fan_q[k], q[b])) for k, b in enumerate(net.fan_b))


def fan_region(net, q):
    """For each fan, which monotonic part of its characteristic it works on."""
    out = []
    for k, b in enumerate(net.fan_b):
        xs, ps = net.fan_q[k], net.fan_p[k]
        j = int(np.clip(np.searchsorted(xs, q[b]) - 1, 0, len(xs) - 2))
        sl = np.sign(np.diff(ps))
        # region index = number of slope sign changes before segment j
        out.append(int(np.sum(sl[1:j + 1] != sl[:j])))
    return tuple(out)


STATS = {"solves": 0, "its": 0, "cont": 0}


def unstable_dir(net, R, q):
    """None when the steady flow q is stable (a local minimum of the content),
    else a node-balanced flow perturbation along which it is unstable."""
    aq = np.abs(q)
    qscale = max(1.0, np.max(aq))
    D = 2.0 * R * np.maximum(aq, 1e-4 * qscale)
    _, s = net.hfun(R, q)
    D[net.fan_b] -= s
    neg = [b for b in net.fan_b if D[b] < 0]
    if not neg:
        return None
    neg = np.array(neg)
    Dp = D.copy()
    Dp[neg] = np.inf
    lu = splu(net.mmat(1.0 / Dp))
    U = net.A[:, neg].toarray()
    X = lu.solve(U)
    S = np.diag(np.abs(D[neg])) - U.T @ X
    w, V = np.linalg.eigh(S)
    if w[-1] < 0:
        return None
    y = V[:, -1]
    pi = -(X @ y)
    dq = (net.AT @ pi) / Dp
    dq[neg] = y
    return dq / np.max(np.abs(dq))


def stable_solve(net, R, q):
    q, p, it = net.solve(R, q)
    STATS["solves"] += 1; STATS["its"] += it
    for _ in range(5):
        d = unstable_dir(net, R, q)
        if d is None:
            return q
        STATS["unstable"] = STATS.get("unstable", 0) + 1
        eps = 0.02 * max(1.0, np.max(np.abs(q)))
        cands = []
        for sg in (1.0, -1.0):
            qq, _, it = net.solve(R, q + sg * eps * d)
            STATS["its"] += it
            cands.append((net.content(R, qq), qq))
        q = min(cands, key=lambda c: c[0])[1]
    return q


def track(net, R0, R1, q):
    """Follow the steady flow continuously as resistances go from R0 to R1."""
    reg0 = fan_region(net, q)
    qa = stable_solve(net, R1, q)
    if fan_region(net, qa) == reg0:
        return qa
    # A fan changed region: follow the change step by step, and where a step
    # makes a fan change region shorten it, so that a jump (a fan falling
    # into or out of stall) starts where the flow it leaves ceases to exist.
    STATS["cont"] += 1
    lr0, lr1 = np.log(R0), np.log(R1)
    Rs = lambda s: np.exp(lr0 + s * (lr1 - lr0))
    s0, qc, reg = 0.0, q, reg0
    h = 1.0 / 16
    hmin = 1.0 / 4096
    while s0 < 1.0:
        s1 = min(1.0, s0 + h)
        qn = stable_solve(net, Rs(s1), qc)
        rn = fan_region(net, qn)
        if rn != reg and h > hmin:
            h *= 0.5
            continue
        s0, qc, reg = s1, qn, rn
        h = min(1.0 / 16, h * 2)
    if os.environ.get("AF_DEBUG"):
        print("cont", q[net.fan_b], "direct", qa[net.fan_b], "path", qc[net.fan_b], file=sys.stderr)
    return qc


if __name__ == "__main__":
    main()
