"""Transient isothermal gas distribution network (medium pressure), for the pre-mortem.
Pipes: Renouard quadratic  p1^2 - p2^2 = 48600 d L Q^1.82 / D^4.82   (bar abs^2, km, m3(n)/h, mm), d = 0.6.
Nodes: linepack C_i dp_i/dt = sum(inflow) - sum(outflow) - demand_i,  C_i = sum(V/2 over pipes) / p_n  (m3(n)/bar).
Feeds: fixed outlet pressure (regulator set point). Implicit Euler, Newton each step."""
import numpy as np

KR = 48600 * 0.6


class Net:
    def __init__(self, nodes, pipes, feeds):
        """nodes: list of ids; pipes: list of (a, b, L_km, D_mm); feeds: {node: set_bar_abs}"""
        self.ix = {n: i for i, n in enumerate(nodes)}
        self.n = len(nodes)
        self.a = np.array([self.ix[p[0]] for p in pipes]); self.b = np.array([self.ix[p[1]] for p in pipes])
        self.L = np.array([p[2] for p in pipes]); self.D = np.array([p[3] for p in pipes])
        self.k = KR * self.L / self.D ** 4.82                       # p1^2 - p2^2 = k Q|Q|^0.82
        vol = np.pi / 4 * (self.D / 1000) ** 2 * self.L * 1000       # m3 geometric
        C = np.zeros(self.n)
        np.add.at(C, self.a, vol / 2); np.add.at(C, self.b, vol / 2)
        self.C = C / 1.01325                                          # m3(n) per bar (ideal, isothermal)
        self.feeds = feeds
        self.fi = np.array([self.ix[f] for f in feeds]); self.free = np.setdiff1d(np.arange(self.n), self.fi)

    def flows(self, p):
        dp2 = p[self.a] ** 2 - p[self.b] ** 2
        Q = np.sign(dp2) * (np.abs(dp2) / self.k) ** (1 / 1.82)
        dQ = (1 / 1.82) * (np.abs(dp2) / self.k + 1e-12) ** (1 / 1.82 - 1) / self.k   # dQ / d(dp2)
        return Q, dQ

    def step(self, p_old, demand, dt_h, set_p, p_guess=None):
        p = (p_old if p_guess is None else p_guess).copy()
        p[self.fi] = [set_p[f] for f in self.feeds]
        fr = self.free
        for _ in range(30):
            Q, dQ = self.flows(p)
            bal = np.zeros(self.n)
            np.add.at(bal, self.b, Q); np.add.at(bal, self.a, -Q)
            res = bal - demand - self.C * (p - p_old) / dt_h if dt_h else bal - demand
            J = np.zeros((self.n, self.n))
            g_a = dQ * 2 * p[self.a]; g_b = dQ * 2 * p[self.b]
            # dQ/dp_a = g_a, dQ/dp_b = -g_b
            np.add.at(J, (self.b, self.a), g_a); np.add.at(J, (self.b, self.b), -g_b)
            np.add.at(J, (self.a, self.a), -g_a); np.add.at(J, (self.a, self.b), g_b)
            if dt_h:
                J[np.arange(self.n), np.arange(self.n)] -= self.C / dt_h
            d = np.linalg.solve(J[np.ix_(fr, fr)], -res[fr])
            p[fr] += d
            if np.max(np.abs(d)) < 1e-9:
                break
        Q, _ = self.flows(p)
        return p, Q

    def run(self, demand_t, set_t, dt_h, p0=None, steady=False):
        """demand_t: (T, n) m3(n)/h; set_t: list of {feed: bar}. Returns pressures (T, n) and feed inflows (T, feeds)."""
        T = len(demand_t)
        P = np.zeros((T, self.n)); F = np.zeros((T, len(self.fi)))
        p, _ = self.step(np.full(self.n, 4.0), demand_t[0], 0, set_t[0]) if p0 is None else (p0, None)
        for t in range(T):
            p, Q = self.step(p, demand_t[t], 0 if steady else dt_h, set_t[t], p)
            P[t] = p
            bal = np.zeros(self.n); np.add.at(bal, self.b, Q); np.add.at(bal, self.a, -Q)
            F[t] = -(bal[self.fi])                                   # what each feed puts in
        return P, F
