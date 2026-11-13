"""network.py: the physics of a ventilation district, as the sealed results are made with it.

Steady incompressible airflow in a network of branches. A branch's pressure drop in its own direction is
R q |q|, less the pressure of a fan standing in it. The district is a gradient system: with air inertia in
every branch the flows descend a potential whose local minima are the stable steady states. A state is
followed through the log by letting the flow settle after every change (implicit Euler on the inertial
equations in mesh coordinates), so where a change removes the state the district was in, it goes where the
air's own dynamics take it.
"""
import numpy as np
import scipy.sparse as sp
from scipy.linalg import cho_factor, cho_solve, LinAlgError

def curve_eval(qs, ps, q):
    """Fan pressure and its slope at flow q: straight lines between tabulated points, end segments produced."""
    i = int(np.clip(np.searchsorted(qs, q, side="right") - 1, 0, len(qs) - 2))
    s = (ps[i + 1] - ps[i]) / (qs[i + 1] - qs[i])
    return ps[i] + s * (q - qs[i]), s

def curve_marks(qs, ps):
    """Flow at the stall trough (the first local minimum from shutoff) and at the peak that follows it."""
    k = 1
    while k < len(qs) - 1 and not (ps[k] < ps[k - 1] and ps[k] <= ps[k + 1]): k += 1
    k_tr = k
    while k < len(qs) - 1 and ps[k + 1] > ps[k]: k += 1
    return qs[k_tr], qs[k]

class Net:
    def __init__(self, nnodes, frm, to, fans, inert=None):
        """nodes 0..nnodes-1, node 0 the atmosphere; fans: {branch index: (qs, ps)}."""
        self.n = nnodes; self.frm = np.asarray(frm); self.to = np.asarray(to); self.B = len(frm)
        self.fans = {int(b): (np.asarray(c[0], float), np.asarray(c[1], float)) for b, c in fans.items()}
        self.fanb = sorted(self.fans)
        self.marks = {b: curve_marks(*self.fans[b]) for b in self.fanb}
        self.inert = np.ones(self.B) if inert is None else np.asarray(inert, float)
        self._basis()

    def _basis(self):
        adj = [[] for _ in range(self.n)]
        for b in range(self.B):
            adj[self.frm[b]].append((self.to[b], b, +1)); adj[self.to[b]].append((self.frm[b], b, -1))
        path = [None] * self.n; path[0] = {}
        tree = set(); order = [0]
        for u in order:
            for v, b, s in adj[u]:
                if path[v] is None:
                    # flow from root to v along the tree: copy u's path, then branch b in sense s
                    p = dict(path[u]); p[b] = s; path[v] = p; tree.add(b); order.append(v)
        if any(p is None for p in path): raise ValueError("network not connected")
        chords = [b for b in range(self.B) if b not in tree]
        Z = np.zeros((self.B, len(chords)))
        for j, c in enumerate(chords):
            Z[c, j] = 1.0                       # unit flow round: chord frm->to, back to frm through the tree
            for b, s in path[self.to[c]].items(): Z[b, j] -= s
            for b, s in path[self.frm[c]].items(): Z[b, j] += s
        self.Z = sp.csr_matrix(Z); self.Zt = sp.csr_matrix(Z.T); self.chords = chords; self.M = len(chords)
        self.Min = Z.T @ (self.inert[:, None] * Z)

    def law(self, q, R):
        h = R * q * np.abs(q); d = 2.0 * R * np.abs(q)
        for b in self.fanb:
            P, s = curve_eval(*self.fans[b], q[b]); h[b] -= P; d[b] -= s
        return h, d

    def limbs(self, q):
        out = []
        for b in self.fanb:
            qt, qp = self.marks[b]
            out.append("L" if q[b] <= qt else ("R" if q[b] >= qp else "M"))
        return "".join(out)

    def settle(self, y, R, dt0=0.5, metric=None, tol=1e-7, maxit=3000, cap=4.0):
        """Let the flow settle from mesh flows y under resistances R: implicit Euler on the inertial equations,
        no step moving any mesh flow by more than cap m3/s. Returns y, iterations, stable flag."""
        Min = self.Min if metric is None else metric
        dt = dt0; y = y.copy()
        for it in range(maxit):
            q = self.Z @ y; h, d = self.law(q, R); F = self.Zt @ h; nF = np.abs(F).max()
            J = (self.Zt @ sp.diags(d) @ self.Z).toarray()
            if nF < tol:
                try:
                    cho_factor(J, lower=True, check_finite=False); return y, it, True
                except LinAlgError:
                    return y, it, False       # an unstable steady state: the caller decides
            while True:
                try:
                    c = cho_factor(Min / dt + J, lower=True, check_finite=False)
                except LinAlgError:
                    dt *= 0.5; continue
                dy = -cho_solve(c, F, check_finite=False)
                if np.abs(dy).max() > cap and dt > 1e-9:
                    dt *= 0.5; continue
                break
            y = y + dy; dt = min(dt * (10.0 if np.abs(dy).max() < 0.1 * cap else 2.0), 1e9)
        raise RuntimeError("did not settle")

    def start(self, R, guess=150.0):
        """A first state: every fan given a healthy flow, then settled."""
        y = np.zeros(self.M)
        q0 = np.zeros(self.B)
        for b in self.fanb: q0[b] = guess
        y = np.linalg.lstsq(self.Z.toarray(), q0, rcond=None)[0]
        return self.settle(y, R, dt0=1.0, cap=25.0)
