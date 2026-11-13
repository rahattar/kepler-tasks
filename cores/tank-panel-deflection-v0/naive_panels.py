#!/usr/bin/env python3
"""ref_panels.py PACKAGE_DIR OUT_CSV: reference for the core.

A fixed-edge thin plate under uniform pressure with the stretching of its middle surface kept. In the
variables W = w/t, Q = p b^4/(E t^4), S = sigma b^2/(E t^2) the answer depends on the side ratio r, on
Poisson's ratio and on Q alone, so the plate is solved once for each Poisson's ratio in the package on a
grid of side ratios and loads (Ritz in displacements, Newton, continuation in load) and every row is read
from that table.
"""
import csv, os, sys
import numpy as np
from numpy.polynomial import legendre as L, polynomial as P

N_TERMS = int(os.environ.get("REF_N", "9"))
N_R = int(os.environ.get("REF_NR", "9"))
N_Q = int(os.environ.get("REF_NQ", "22"))


def basis(m, idx, xi, scale=None):
    poly = np.array([1.0])
    for _ in range(m):
        poly = P.polymul(poly, np.array([1.0, 0.0, -1.0]))
    xi = np.atleast_1d(np.asarray(xi, float))
    v = np.empty((len(xi), len(idx))); d = np.empty_like(v); dd = np.empty_like(v)
    for k, i in enumerate(idx):
        c = np.zeros(i + 1); c[i] = 1.0
        full = P.polymul(poly, L.leg2poly(c)); d1 = P.polyder(full); d2 = P.polyder(d1)
        v[:, k] = P.polyval(xi, full); d[:, k] = P.polyval(xi, d1); dd[:, k] = P.polyval(xi, d2)
    if scale is None:
        scale = np.abs(v).max(axis=0)
    return v / scale, d / scale, dd / scale, scale


class Film:
    """one side ratio and Poisson's ratio; quarter-symmetric Ritz basis on Gauss points of one quadrant."""

    def __init__(self, r, nu, n):
        self.r, self.nu, self.n = r, nu, n
        nq = (3 * n + 12) // 2
        xf, wf = L.leggauss(2 * nq)
        xi, wq = xf[nq:], wf[nq:]                               # positive half; integrands are even
        ev = [2 * k for k in range(n)]; od = [2 * k + 1 for k in range(n)]
        sx, sy = 2.0 / r, 2.0
        f, f1, f2, sw = basis(2, ev, xi)
        ge, ge1, _, sge = basis(1, ev, xi); go, go1, _, sgo = basis(1, od, xi)
        W2 = np.outer(wq, wq).ravel() * r
        tp = lambda ax, ay: np.einsum("qi,pj->qpij", ax, ay).reshape(len(xi) ** 2, -1)
        self.Bw = tp(f, f); self.Bwx = sx * tp(f1, f); self.Bwy = sy * tp(f, f1)
        Bk = [sx * sx * tp(f2, f), sy * sy * tp(f, f2), sx * sy * tp(f1, f1)]
        nn = n * n; z = np.zeros((len(W2), nn))
        self.Bm = [np.hstack([sx * tp(go1, ge), z]), np.hstack([z, sy * tp(ge, go1)]),
                   np.hstack([sy * tp(go, ge1), sx * tp(ge1, go)])]
        self.Cm = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
        Cb = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, 2 * (1 - nu)]]) / 12.0
        self.Kb = sum(Cb[i, j] * (Bk[i].T * W2) @ Bk[j] for i in range(3) for j in range(3) if Cb[i, j])
        self.Km = sum(self.Cm[i, j] * (self.Bm[i].T * W2) @ self.Bm[j] for i in range(3) for j in range(3) if self.Cm[i, j])
        self.W2 = W2; self.nw = nn
        self.fl = (self.Bw.T * W2).sum(axis=1) * (1 - nu * nu)
        # read-out rows: centre deflection, edge curvature and edge membrane strain
        f0 = basis(2, ev, 0.0, sw)[0][0]; fe2 = basis(2, ev, 1.0, sw)[2][0]
        ge0 = basis(1, ev, 0.0, sge)[0][0]; goe1 = basis(1, od, 1.0, sgo)[1][0]
        self.rW = np.outer(f0, f0).ravel(); self.rK = sy * sy * np.outer(f0, fe2).ravel()
        self.rV = sy * np.outer(ge0, goe1).ravel()
        self.z = np.zeros(3 * nn); self.hist = []

    def newton(self, Q, z):
        nw, W2, Cm = self.nw, self.W2, self.Cm
        for it in range(30):
            c, d = z[:nw], z[nw:]
            wx = self.Bwx @ c; wy = self.Bwy @ c
            e = np.array([self.Bm[0] @ d + 0.5 * wx * wx, self.Bm[1] @ d + 0.5 * wy * wy, self.Bm[2] @ d + wx * wy])
            s = Cm @ e
            gw = self.Kb @ c + self.Bwx.T @ (W2 * (s[0] * wx + s[2] * wy)) + self.Bwy.T @ (W2 * (s[1] * wy + s[2] * wx)) - Q * self.fl
            gd = self.Bm[0].T @ (W2 * s[0]) + self.Bm[1].T @ (W2 * s[1]) + self.Bm[2].T @ (W2 * s[2])
            Ew = [wx[:, None] * self.Bwx, wy[:, None] * self.Bwy, wx[:, None] * self.Bwy + wy[:, None] * self.Bwx]
            CE = [Cm[0, 0] * Ew[0] + Cm[0, 1] * Ew[1], Cm[1, 0] * Ew[0] + Cm[1, 1] * Ew[1], Cm[2, 2] * Ew[2]]
            Hww = self.Kb + sum((Ew[i].T * W2) @ CE[i] for i in range(3))
            Hww += (self.Bwx.T * (W2 * s[0])) @ self.Bwx + (self.Bwy.T * (W2 * s[1])) @ self.Bwy
            t = (self.Bwx.T * (W2 * s[2])) @ self.Bwy; Hww += t + t.T
            Hwd = sum((CE[i].T * W2) @ self.Bm[i] for i in range(3))
            H = np.block([[Hww, Hwd], [Hwd.T, self.Km]])
            dz = np.linalg.solve(H, -np.concatenate([gw, gd]))
            z = z + dz
            if np.abs(dz).max() < 1e-9 * max(1.0, np.abs(z).max()):
                return z
        raise RuntimeError("no convergence")

    def advance(self, Q):
        h = self.hist
        if len(h) >= 2:                                      # secant predictor in log Q
            (q1, z1), (q2, z2) = h[-2], h[-1]
            z0 = z2 + (z2 - z1) * (np.log(Q) - np.log(q2)) / (np.log(q2) - np.log(q1))
        elif h:
            z0 = h[-1][1] * (Q / h[-1][0])
        else:
            z0 = np.zeros_like(self.z)
        try:
            z = self.newton(Q, z0)
        except Exception:
            z = self.newton(Q, h[-1][1] if h else np.zeros_like(self.z))
        h.append((Q, z)); self.z = z
        c = z[:self.nw]; b = z[2 * self.nw:]
        k = 1.0 / (1 - self.nu ** 2)
        return self.rW @ c, k * (self.rV @ b) + 0.5 * k * abs(self.rK @ c)



def main(pkg, out):
    """every row from scratch: a new basis, load raised from nothing in steps, no table."""
    mats = {r["material"]: (float(r["E_GPa"]) * 1e3, float(r["poisson"])) for r in csv.DictReader(open(os.path.join(pkg, "materials.csv")))}
    pan = {r["panel"]: r for r in csv.DictReader(open(os.path.join(pkg, "panels.csv")))}
    every = int(os.environ.get("NAIVE_EVERY", "1"))
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["row", "deflection_mm", "edge_stress_MPa"])
        for i, r in enumerate(csv.DictReader(open(os.path.join(pkg, "conditions.csv")))):
            if i % every: continue
            p = pan[r["panel"]]; a, b, t = float(p["a_mm"]), float(p["b_mm"]), float(p["t_mm"]); E, nu = mats[p["material"]]
            a, b = max(a, b), min(a, b)
            Q = float(r["pressure_kPa"]) * 1e-3 * (b / t) ** 4 / E
            film = Film(a / b, nu, 10)
            steps = max(1, int(np.ceil(np.log2(max(Q, 1.0)))))
            for k in range(1, steps + 1):
                film.hist = film.hist[-1:]
                W, S = film.advance(Q * k / steps)
            w.writerow([r["row"], "%.6g" % (W * t), "%.6g" % (S * E * (t / b) ** 2)])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
