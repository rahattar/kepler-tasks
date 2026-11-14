"""Physics of the gas-network core, as GD-3 states it (core/data/docs/gd3_design_day.md).

Mains: p_a^2 - p_b^2 = K Q |Q|^0.82 (bar abs, m3(st)/h). Linepack held at the nodes, half of every main's
geometric volume at each end, gas ideal at 15 C. PRS: holds its node at its set point, delivering 0 to its
capacity. A passing boundary valve is a main to a node held at the neighbour's pressure, with no volume.
Implicit steps of 0.1 h; the design day is periodic.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

P_ATM = 1.01325
EXP = 1.82
STEPS = 240
DT = 0.1


def q_of(dp2, K):
    return np.sign(dp2) * (np.abs(dp2) / K) ** (1 / EXP)


def dq_of(dp2, K):
    return (1 / EXP) * (np.abs(dp2) / K + 1e-12) ** (1 / EXP - 1) / K


class Net:
    def __init__(self, nodes, mains, prs, valves=()):
        """nodes: ids; mains: (a, b, K, V_m3); prs: (node, set_abs, cap_m3h); valves: (node, p_neigh_abs, Kv)"""
        self.nodes = list(nodes)
        self.ix = {n: i for i, n in enumerate(self.nodes)}
        n = self.n = len(self.nodes)
        self.a = np.array([self.ix[m[0]] for m in mains], dtype=int)
        self.b = np.array([self.ix[m[1]] for m in mains], dtype=int)
        self.K = np.array([m[2] for m in mains], dtype=float)
        V = np.array([m[3] for m in mains], dtype=float)
        C = np.zeros(n)
        np.add.at(C, self.a, V / 2)
        np.add.at(C, self.b, V / 2)
        self.C = C / P_ATM
        self.pi = np.array([self.ix[p[0]] for p in prs], dtype=int)
        self.pset = np.array([p[1] for p in prs], dtype=float)
        self.pcap = np.array([p[2] for p in prs], dtype=float)
        self.vi = np.array([self.ix[v[0]] for v in valves], dtype=int)
        self.vp = np.array([v[1] for v in valves], dtype=float)
        self.vK = np.array([v[2] for v in valves], dtype=float)
        a, b = self.a, self.b
        self.rows = np.concatenate([b, b, a, a, np.arange(n)])
        self.cols = np.concatenate([a, b, a, b, np.arange(n)])

    def balance(self, p):
        """Flow into every node from mains and valves (m3/h), the Jacobian entries, the mains' flows."""
        a, b = self.a, self.b
        dp2 = p[a] ** 2 - p[b] ** 2
        Q = q_of(dp2, self.K)
        g = dq_of(dp2, self.K)
        inflow = np.zeros(self.n)
        np.add.at(inflow, b, Q)
        np.add.at(inflow, a, -Q)
        ga, gb = 2 * g * p[a], 2 * g * p[b]
        diag = np.zeros(self.n)
        if len(self.vi):
            dv = self.vp ** 2 - p[self.vi] ** 2
            np.add.at(inflow, self.vi, q_of(dv, self.vK))
            np.add.at(diag, self.vi, -dq_of(dv, self.vK) * 2 * p[self.vi])
        data = np.concatenate([ga, -gb, -ga, gb, diag])
        return inflow, data, Q

    def step(self, p_start, demand, dt, mode):
        """One implicit step (dt in h; None for a steady state). mode per PRS: 0 at set point, 1 at capacity,
        2 delivering nothing. Returns the pressures, the PRS deliveries and the modes."""
        n = self.n
        p = p_start.copy()
        mode = mode.copy()
        for _sweep in range(20):
            fixed = self.pi[mode == 0]
            p[fixed] = self.pset[mode == 0]
            src = np.zeros(n)
            np.add.at(src, self.pi[mode == 1], self.pcap[mode == 1])
            free = np.ones(n, bool)
            free[fixed] = False
            fidx = np.flatnonzero(free)
            for _it in range(60):
                inflow, data, _ = self.balance(p)
                r = inflow + src - demand
                if dt:
                    r = r - self.C * (p - p_start) / dt
                    data[-n:] -= self.C / dt
                J = sp.csc_matrix((data, (self.rows, self.cols)), shape=(n, n))
                Jf = J[fidx][:, fidx]
                d = spl.spsolve(Jf.tocsc(), -r[fidx])
                big = np.max(np.abs(d)) if len(d) else 0.0
                if big > 0.5:
                    d *= 0.5 / big
                p[fidx] += d
                if big < 1e-9:
                    break
            inflow, _, _ = self.balance(p)
            r = inflow + src - demand
            if dt:
                r = r - self.C * (p - p_start) / dt
            need = -r[self.pi]                         # what each PRS must deliver to hold its node at set point
            new = mode.copy()
            for k in range(len(self.pi)):
                if mode[k] == 0:
                    if need[k] > self.pcap[k]:
                        new[k] = 1
                    elif need[k] < 0:
                        new[k] = 2
                elif mode[k] == 1 and p[self.pi[k]] > self.pset[k]:
                    new[k] = 0
                elif mode[k] == 2 and p[self.pi[k]] < self.pset[k]:
                    new[k] = 0
            if np.array_equal(new, mode):
                deliv = np.where(mode == 0, need, np.where(mode == 1, self.pcap, 0.0))
                return p, deliv, mode
            mode = new
        raise RuntimeError("PRS modes did not settle")

    def steady(self, demand, p0=None):
        p = np.full(self.n, self.pset.max() - 0.3) if p0 is None else p0.copy()
        mode = np.zeros(len(self.pi), int)
        p, deliv, mode = self.step(p, demand, None, mode)
        return p, deliv

    def flows(self, p):
        return self.balance(p)[2]

    def valve_flows(self, p):
        if not len(self.vi):
            return np.zeros(0)
        return q_of(self.vp ** 2 - p[self.vi] ** 2, self.vK)

    def design_day(self, demand_h, tol=1e-7, max_days=60):
        """demand_h: (24, n) hourly demand from 06:00. Returns P (STEPS, n) of the periodic day, the PRS
        deliveries (STEPS, n_prs) and the number of days run."""
        p, _ = self.steady(demand_h.mean(axis=0))
        mode = np.zeros(len(self.pi), int)
        for day in range(1, max_days + 1):
            p0 = p.copy()
            P = np.zeros((STEPS, self.n))
            D = np.zeros((STEPS, len(self.pi)))
            for k in range(STEPS):
                p, D[k], mode = self.step(p, demand_h[k // 10], DT, mode)
                P[k] = p
            if np.max(np.abs(p - p0)) < tol:
                return P, D, day
        raise RuntimeError("design day not periodic after %d days" % max_days)
