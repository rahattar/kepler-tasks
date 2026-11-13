#!/usr/bin/env python3
"""Airflow at every survey point of a district package, calculated to VS-4.

Usage: python3 airflow.py PACKAGE_DIR OUT_CSV

Method
------
Every branch outside the fans follows the square law (VS-4 sections 2 and 3)
and natural ventilation is left out, so the network seen by the fan house is
homogeneous: with the fans' total flow Q every other branch carries Q times its
flow at Q = 1, and the fan house pressure is -R_eq Q|Q|.  At every state of the
log the network is therefore solved once for Q = 1 (Newton, warm started),
giving R_eq and the unit flows.

The fans then satisfy  P_i(q_i) - R_i q_i|q_i| = R_eq Q|Q|  with Q the sum of
the fan flows.  Because the catalogue characteristics have a stall dip this has
several solutions.  VS-4 section 5 (changes are made gradually by hand, the air
follows within seconds, the flow is steady at every moment) picks the physical
one: the stable steady state reached by following the district through the
record.  So each change is followed in small steps of R_eq; while the current
stable state persists it is tracked by Newton, and where it ceases to exist
(a fold, e.g. a fan driven into stall or recovering from it) the flow is carried
to the next stable state by integrating the fans' equations of motion.
"""
import sys, os
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spl


def rd(pkg, f):
    df = pd.read_csv(os.path.join(pkg, f), dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


class Fans:
    """The fans at the fan house: q_i positive in each fan branch's direction."""

    def __init__(self, curves, Rd, sgn):
        self.c = curves          # list of (qs, ps)
        self.Rd = np.array(Rd)   # ducting resistances
        self.s = np.array(sgn, float)
        self.F = len(curves)

    def G(self, q):
        g = np.empty(self.F); dg = np.empty(self.F)
        for i, (qs, ps) in enumerate(self.c):
            j = int(np.clip(np.searchsorted(qs, q[i], side='right') - 1, 0, len(qs) - 2))
            sl = (ps[j + 1] - ps[j]) / (qs[j + 1] - qs[j])
            g[i] = ps[j] + sl * (q[i] - qs[j]) - self.Rd[i] * q[i] * abs(q[i])
            dg[i] = sl - 2 * self.Rd[i] * abs(q[i])
        return g, dg

    def f(self, q, Req):
        """Equations of motion: dq/dt = f(q); returns f and its Jacobian."""
        g, dg = self.G(q)
        Q = self.s @ q
        f = g - self.s * Req * Q * abs(Q)
        J = np.diag(dg) - 2 * Req * abs(Q) * np.outer(self.s, self.s)
        return f, J

    def newton(self, q, Req, maxit=30):
        q = q.copy()
        for _ in range(maxit):
            f, J = self.f(q, Req)
            if np.abs(f).max() < 1e-9:
                return q, True
            try:
                dq = np.linalg.solve(J, -f)
            except np.linalg.LinAlgError:
                return q, False
            m = np.abs(dq).max()
            if m > 2.0:
                dq *= 2.0 / m
            q = q + dq
        f, J = self.f(q, Req)
        return q, np.abs(f).max() < 1e-9

    def stable(self, q, Req):
        f, J = self.f(q, Req)
        return np.linalg.eigvalsh(0.5 * (J + J.T)).max() < 0

    def settle(self, q, Req):
        """Integrate the motion (implicit Euler, growing step) to a stable state."""
        q = q.copy()
        h = 1e-3
        for _ in range(20000):
            f, J = self.f(q, Req)
            if np.abs(f).max() < 1e-9 and self.stable(q, Req):
                return q
            A = np.eye(self.F) / h - J
            dq = np.linalg.solve(A, f)
            m = np.abs(dq).max()
            if m > 1.0:            # keep the integration honest
                dq *= 1.0 / m
                h = max(h * 0.5, 1e-5)
            else:
                h = min(h * 1.3, 0.05 if not self.stable(q, Req) else 1e6)
            q = q + dq
        print('warning: fans did not settle', file=sys.stderr)
        return q

    def follow(self, q, R0, R1):
        """Follow the stable state while R_eq moves gradually from R0 to R1."""
        if R0 == R1:
            return q
        n = max(1, int(np.ceil(abs(np.log(R1 / R0)) / np.log(1.01))))
        for k in range(1, n + 1):
            R = R0 * (R1 / R0) ** (k / n)
            q2, ok = self.newton(q, R)
            if ok and np.abs(q2 - q).max() < 3.0 and self.stable(q2, R):
                q = q2
            else:
                q = self.settle(q, R)
        return q


class Network:
    def __init__(self, pkg):
        br = rd(pkg, 'branches.csv')
        regs = rd(pkg, 'regulators.csv'); doors = rd(pkg, 'doors.csv')
        fans = rd(pkg, 'fans.csv'); curves = rd(pkg, 'fan_curves.csv')
        self.log = rd(pkg, 'log.csv'); self.pts = rd(pkg, 'points.csv')
        kind = br.kind.str.lower().values
        self.bid = {b: i for i, b in enumerate(br.branch)}
        B = self.B = len(br)
        isfan = kind == 'fan'
        fanb = {b for b in fans.branch}
        isfan |= br.branch.isin(fanb).values
        self.fidx = np.where(isfan)[0]
        self.nidx = np.where(~isfan)[0]
        nodes = sorted((set(br.from_node) | set(br.to_node)) - {'ATM'})
        nid = {n: i for i, n in enumerate(nodes)}
        self.N = len(nodes)
        rows, cols, vals = [], [], []
        for i, (f, t) in enumerate(zip(br.from_node, br.to_node)):
            if f != 'ATM': rows.append(i); cols.append(nid[f]); vals.append(1.0)
            if t != 'ATM': rows.append(i); cols.append(nid[t]); vals.append(-1.0)
        M = sp.csr_matrix((vals, (rows, cols)), shape=(B, self.N))
        self.Mn = M[self.nidx].tocsr(); self.MnT = self.Mn.T.tocsr()
        # the fan house port
        ends = {}
        sgn = []
        f0 = br.from_node.values[self.fidx[0]]; t0 = br.to_node.values[self.fidx[0]]
        for i in self.fidx:
            f, t = br.from_node.values[i], br.to_node.values[i]
            if (f, t) == (f0, t0): sgn.append(1.0)
            elif (f, t) == (t0, f0): sgn.append(-1.0)
            else:
                raise SystemExit('fans are not in parallel at one fan house (VS-4 section 1)')
        self.e = M[self.fidx[0]].toarray().ravel()   # port: p_from - p_to = e.p
        self.R = np.zeros(B)
        for i in range(B):
            if kind[i] in ('airway', 'fan') and br.resistance_Ns2_m8.values[i] != '':
                self.R[i] = float(br.resistance_Ns2_m8.values[i])
        self.regtab = {}
        for r, s, v in zip(regs.regulator, regs.setting, regs.resistance_Ns2_m8):
            self.regtab.setdefault(r, {})[int(round(float(s)))] = float(v)
        self.doortab = {d: (float(c), float(o)) for d, c, o in
                        zip(doors.door, doors.resistance_closed_Ns2_m8, doors.resistance_open_Ns2_m8)}
        self.item_br = {}
        for i in range(B):
            if kind[i] in ('regulator', 'door'):
                self.item_br.setdefault(br.item.values[i], []).append(i)
        fan_of_branch = {b: (m, s) for b, m, s in zip(fans.branch, fans.model, fans.blade_setting)}
        cl = []
        for i in self.fidx:
            m, s = fan_of_branch[br.branch.values[i]]
            c = curves[(curves.model == m) & (curves.blade_setting.astype(float) == float(s))]
            qs = c.flow_m3_s.astype(float).values; ps = c.pressure_Pa.astype(float).values
            o = np.argsort(qs, kind='stable')
            cl.append((qs[o], ps[o]))
        self.fans = Fans(cl, self.R[self.fidx], sgn)
        self.Rn = self.R[self.nidx]
        # unit injection: the network delivers Q = 1 through the port
        self.b = -self.e
        self.qn = None; self.p = np.zeros(self.N)

    def item_R(self, item, s):
        s = s.lower()
        if item in self.doortab:
            c, o = self.doortab[item]
            if s in ('open', 'o'): return o
            if s in ('closed', 'close', 'shut', 'c'): return c
            raise ValueError(f'door {item}: setting {s}')
        tab = self.regtab[item]
        x = float(s)
        if x in tab: return tab[int(x)]
        ks = sorted(tab); x = min(max(x, ks[0]), ks[-1])
        lo = max(k for k in ks if k <= x); hi = min(k for k in ks if k >= x)
        a = (x - lo) / (hi - lo)
        return float(np.exp((1 - a) * np.log(tab[lo]) + a * np.log(tab[hi])))

    def unit_solve(self, Rn):
        """Square-law network with unit flow through the fan house port."""
        Mn, MnT = self.Mn, self.MnT
        if self.qn is None:
            # start: linear (laminar-like) solution
            K = (MnT @ sp.diags(1.0 / Rn) @ Mn).tocsc()
            p = spl.spsolve(K, self.b)
            q = (Mn @ p) / Rn
            self.qn = q; self.p = p
        q, p = self.qn.copy(), self.p.copy()
        scale = None
        for it in range(100):
            r1 = Rn * q * np.abs(q) - Mn @ p
            r2 = MnT @ q - self.b
            if scale is None:
                scale = max(np.abs(Mn @ p).max(), 1e-300)
            if np.abs(r1).max() < 1e-11 * scale and np.abs(r2).max() < 1e-12:
                break
            d = 2 * Rn * np.abs(q)
            d = np.maximum(d, 1e-8 * Rn + 1e-300)
            Di = 1.0 / d
            K = (MnT @ sp.diags(Di) @ Mn).tocsc()
            dp = spl.spsolve(K, MnT @ (Di * r1) - r2)
            dq = Di * (Mn @ dp - r1)
            # safeguard: don't let flows overshoot sign wildly
            q += dq; p += dp
        else:
            print('warning: network solve did not converge', file=sys.stderr)
        self.qn, self.p = q, p
        Req = -(self.e @ p)
        return Req, q


def main(pkg, out):
    net = Network(pkg)
    log, pts = net.log, net.pts
    events = {}
    for t, it, s in zip(log.time, log.item, log.setting):
        events.setdefault(t, []).append((it, s))
    ptimes = set(pts.time)
    Rall = net.R.copy()
    results = {}
    qf = None; Req = None; unit = None
    for t in sorted(set(events) | ptimes):
        if t in events:
            for it, s in events[t]:
                v = net.item_R(it, s)
                for i in net.item_br.get(it, []):
                    Rall[i] = v
            Rnew, unit = net.unit_solve(Rall[net.nidx])
            if qf is None:
                # as the record opens the fans are in normal running: the stable
                # state reached from free delivery (the unstalled state)
                qf = net.fans.settle(np.array([c[0][-1] for c in net.fans.c]), Rnew)
            else:
                qf = net.fans.follow(qf, Req, Rnew)
            Req = Rnew
        if t in ptimes:
            if qf is None:
                raise SystemExit('survey point before the log opens')
            Q = net.fans.s @ qf
            full = np.empty(net.B)
            full[net.nidx] = unit * Q
            full[net.fidx] = qf
            results[t] = full
    outq = [results[t][net.bid[b]] for t, b in zip(pts.time, pts.branch)]
    pd.DataFrame({'point': pts.point, 'flow_m3_s': [f'{v:.5f}' for v in outq]}).to_csv(out, index=False)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
