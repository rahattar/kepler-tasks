"""shell.py: sealed definition for v1. The fixed-edge thin plate of v0 with an initial bow
W0 = H g(xi) g(eta), g = (1 - xi^2)^2 (H in thicknesses, stress-free), under uniform pressure Q, positive in
the direction of the bow. Ritz in displacements by symmetry class; the tangent stiffness is assembled for each
of the four classes (even or odd in x, even or odd in y) so that the stability of an equilibrium is known."""
import numpy as np
from numpy.polynomial import legendre as L, polynomial as P


def fam(m, parity, n, xi, scale=None):
    """(1-xi^2)^m P_k(xi), k of the given parity: values, first and second derivatives on xi."""
    xi = np.atleast_1d(np.asarray(xi, float))
    poly = np.array([1.0])
    for _ in range(m):
        poly = P.polymul(poly, np.array([1.0, 0.0, -1.0]))
    v = np.empty((len(xi), n)); d = np.empty_like(v); dd = np.empty_like(v)
    for k in range(n):
        c = np.zeros(2 * k + parity + 1); c[-1] = 1.0
        full = P.polymul(poly, L.leg2poly(c)); d1 = P.polyder(full); d2 = P.polyder(d1)
        v[:, k] = P.polyval(xi, full); d[:, k] = P.polyval(xi, d1); dd[:, k] = P.polyval(xi, d2)
    if scale is None:
        scale = np.abs(v).max(axis=0)
    return v / scale, d / scale, dd / scale, scale


class Shell:
    def __init__(self, r, nu, H=0.0, n=10):
        self.r, self.nu, self.H, self.n = float(r), float(nu), float(H), n
        nq = 3 * n + 14; nq += nq % 2
        xf, wf = L.leggauss(nq)
        self.xi = xf[nq // 2:]; wq = 2.0 * wf[nq // 2:]
        self.W2 = np.outer(wq, wq).ravel() * (self.r / 4.0)
        self.sx, self.sy = 2.0 / self.r, 2.0
        self.Cm = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
        self.Cb = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, 2 * (1 - nu)]]) / 12.0
        self.ops = {c: self._class(*c) for c in ((0, 0), (1, 0), (0, 1), (1, 1))}
        xi = self.xi
        g = (1 - xi ** 2) ** 2; g1 = -4 * xi * (1 - xi ** 2)
        self.w0x = self.H * self.sx * np.outer(g1, g).ravel(); self.w0y = self.H * self.sy * np.outer(g, g1).ravel()
        o = self.ops[(0, 0)]
        self.fl = (o["Bw"].T * self.W2).sum(axis=1) * (1 - nu * nu)
        self.N = 3 * n * n
        self.z = np.zeros(self.N); self.Q = 0.0

    def _class(self, px, py):
        n, xi, sx, sy, W2 = self.n, self.xi, self.sx, self.sy, self.W2
        tp = lambda ax, ay: np.einsum("qi,pj->qpij", ax, ay).reshape(len(xi) ** 2, -1)
        fx = fam(2, px, n, xi); fy = fam(2, py, n, xi)
        ux = fam(1, 1 - px, n, xi); uy = fam(1, py, n, xi)          # u: x parity flipped
        vx = fam(1, px, n, xi); vy = fam(1, 1 - py, n, xi)          # v: y parity flipped
        o = dict(Bw=tp(fx[0], fy[0]), Bwx=sx * tp(fx[1], fy[0]), Bwy=sy * tp(fx[0], fy[1]))
        Bk = [sx * sx * tp(fx[2], fy[0]), sy * sy * tp(fx[0], fy[2]), sx * sy * tp(fx[1], fy[1])]
        z = np.zeros((len(W2), n * n))
        o["Bm"] = [np.hstack([sx * tp(ux[1], uy[0]), z]), np.hstack([z, sy * tp(vx[0], vy[1])]),
                   np.hstack([sy * tp(ux[0], uy[1]), sx * tp(vx[1], vy[0])])]
        o["Kb"] = sum(self.Cb[i, j] * (Bk[i].T * W2) @ Bk[j] for i in range(3) for j in range(3) if self.Cb[i, j])
        o["Km"] = sum(self.Cm[i, j] * (o["Bm"][i].T * W2) @ o["Bm"][j] for i in range(3) for j in range(3) if self.Cm[i, j])
        o["sc"] = (fx[3], fy[3], ux[3], uy[3], vx[3], vy[3])
        return o

    def fields(self, z):
        o = self.ops[(0, 0)]; nw = self.n ** 2
        c, d = z[:nw], z[nw:]
        wx = o["Bwx"] @ c + self.w0x; wy = o["Bwy"] @ c + self.w0y
        e = np.array([o["Bm"][0] @ d + 0.5 * (wx * wx - self.w0x ** 2), o["Bm"][1] @ d + 0.5 * (wy * wy - self.w0y ** 2),
                      o["Bm"][2] @ d + wx * wy - self.w0x * self.w0y])
        return c, d, wx, wy, self.Cm @ e

    def tangent(self, z, cls=(0, 0)):
        o = self.ops[cls]; W2, Cm = self.W2, self.Cm
        c, d, wx, wy, s = self.fields(z)
        Ew = [wx[:, None] * o["Bwx"], wy[:, None] * o["Bwy"], wx[:, None] * o["Bwy"] + wy[:, None] * o["Bwx"]]
        CE = [Cm[0, 0] * Ew[0] + Cm[0, 1] * Ew[1], Cm[1, 0] * Ew[0] + Cm[1, 1] * Ew[1], Cm[2, 2] * Ew[2]]
        Hww = o["Kb"] + sum((Ew[i].T * W2) @ CE[i] for i in range(3))
        Hww += (o["Bwx"].T * (W2 * s[0])) @ o["Bwx"] + (o["Bwy"].T * (W2 * s[1])) @ o["Bwy"]
        t = (o["Bwx"].T * (W2 * s[2])) @ o["Bwy"]; Hww += t + t.T
        Hwd = sum((CE[i].T * W2) @ o["Bm"][i] for i in range(3))
        return np.block([[Hww, Hwd], [Hwd.T, o["Km"]]])

    def grad(self, z, Q):
        o = self.ops[(0, 0)]; W2 = self.W2
        c, d, wx, wy, s = self.fields(z)
        gw = o["Kb"] @ c + o["Bwx"].T @ (W2 * (s[0] * wx + s[2] * wy)) + o["Bwy"].T @ (W2 * (s[1] * wy + s[2] * wx)) - Q * self.fl
        gd = o["Bm"][0].T @ (W2 * s[0]) + o["Bm"][1].T @ (W2 * s[1]) + o["Bm"][2].T @ (W2 * s[2])
        return np.concatenate([gw, gd])

    def newton(self, Q, z, tol=1e-10, maxit=40):
        for it in range(maxit):
            dz = np.linalg.solve(self.tangent(z), -self.grad(z, Q))
            z = z + dz
            if not np.all(np.isfinite(z)): return None
            if np.abs(dz).max() < tol * max(1.0, np.abs(z).max()): return z
        return None

    def lowest(self, z, cls):
        """smallest eigenvalue of the tangent stiffness in a class, scaled by the bending stiffness's own."""
        H = self.tangent(z, cls)
        return float(np.linalg.eigvalsh(H)[0])

    def centre(self, z):
        o = self.ops[(0, 0)]; n = self.n
        f0 = fam(2, 0, n, 0.0, o["sc"][0])[0][0]; g0 = fam(2, 0, n, 0.0, o["sc"][1])[0][0]
        return float(f0 @ z[:n * n].reshape(n, n) @ g0)

    def edge(self, z):
        """stress across the middle of a long edge: membrane, and bending magnitude."""
        o = self.ops[(0, 0)]; n = self.n; nu = self.nu; sy = self.sy
        f0 = fam(2, 0, n, 0.0, o["sc"][0])[0][0]; ge2 = fam(2, 0, n, 1.0, o["sc"][1])[2][0]
        v0 = fam(1, 0, n, 0.0, o["sc"][4])[0][0]; ve1 = fam(1, 1, n, 1.0, o["sc"][5])[1][0]
        c = z[:n * n].reshape(n, n); b = z[2 * n * n:].reshape(n, n)
        k = 1.0 / (1 - nu * nu)
        return float(k * sy * (v0 @ b @ ve1)), float(0.5 * k * abs(sy * sy * (f0 @ c @ ge2)))
