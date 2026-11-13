"""plate.py: sealed definition. A thin elastic rectangular plate, fixed at its four edges (no deflection, no
rotation, no in-plane movement), under uniform pressure, with the stretching of its middle surface kept
(Foppl-von Karman). Ritz solution in displacements on a polynomial basis; Newton with load stepping.

Dimensionless: X = x/b, Y = y/b, W = w/t, in-plane displacements scaled by t^2/b, Q = q b^4 / (E t^4),
stress S = sigma b^2 / (E t^2). r = a/b >= 1 is the side ratio (a long side, b short side).
"""
import numpy as np
from numpy.polynomial import legendre as L


def _basis(kind, idx, xi, scale=None):
    """values, first and second derivative at xi of (1-xi^2)^m P_i(xi); m = 2 for 'w', 1 for 'u'.
    Each function is divided by scale[i]; when scale is None it is the function's largest value on xi."""
    from numpy.polynomial import polynomial as P
    m = 2 if kind == "w" else 1
    xi = np.atleast_1d(np.asarray(xi, float))
    poly = np.array([1.0])
    for _ in range(m):
        poly = P.polymul(poly, np.array([1.0, 0.0, -1.0]))
    v = np.empty((len(xi), len(idx))); d = np.empty_like(v); dd = np.empty_like(v)
    for k, i in enumerate(idx):
        c = np.zeros(i + 1); c[i] = 1.0
        full = P.polymul(poly, L.leg2poly(c))
        d1 = P.polyder(full); d2 = P.polyder(d1)
        v[:, k] = P.polyval(xi, full); d[:, k] = P.polyval(xi, d1); dd[:, k] = P.polyval(xi, d2)
    if scale is None:
        scale = np.abs(v).max(axis=0); scale[scale == 0] = 1.0
    return v / scale, d / scale, dd / scale, scale


class Plate:
    def __init__(self, r, nu, n=10, nq=None):
        self.r, self.nu, self.n = float(r), float(nu), n
        nq = nq or (3 * n + 12)
        nq += nq % 2
        xi, wq = L.leggauss(nq)
        xi, wq = xi[nq // 2:], 2.0 * wq[nq // 2:]      # every integrand is even in x and in y: one quadrant
        nq = nq // 2
        self.xi, self.wq = xi, wq
        ev = [2 * k for k in range(n)]; od = [2 * k + 1 for k in range(n)]
        self.ev, self.od = ev, od
        sx, sy = 2.0 / self.r, 2.0                     # d/dX = sx d/dxi ; d/dY = sy d/deta
        # w: even-even
        f, f1, f2, self.sw = _basis("w", ev, xi)
        # u: odd in x, even in y ; v: even in x, odd in y
        ge, ge1, _, self.sge = _basis("u", ev, xi)
        go, go1, _, self.sgo = _basis("u", od, xi)
        self.f = f
        nq2 = nq * nq
        W2 = np.outer(wq, wq).ravel() * (self.r / 4.0)
        self.W2 = W2

        def tp(ax, ay):                                # tensor product operator: rows quad points, cols coeffs
            return np.einsum("qi,pj->qpij", ax, ay).reshape(nq2, ax.shape[1] * ay.shape[1])
        self.Bw = tp(f, f)
        self.Bwx = sx * tp(f1, f); self.Bwy = sy * tp(f, f1)
        self.Bwxx = sx * sx * tp(f2, f); self.Bwyy = sy * sy * tp(f, f2); self.Bwxy = sx * sy * tp(f1, f1)
        self.Bux = sx * tp(go1, ge); self.Buy = sy * tp(go, ge1)
        self.Bvx = sx * tp(ge1, go); self.Bvy = sy * tp(ge, go1)
        self.nw = n * n; self.nu_ = n * n
        self.N = self.nw + 2 * self.nu_
        nu = self.nu
        self.Cm = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
        self.Cb = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, 2 * (1 - nu)]]) / 12.0
        # constant parts of the Hessian
        Bk = [self.Bwxx, self.Bwyy, self.Bwxy]
        Kb = np.zeros((self.nw, self.nw))
        for i in range(3):
            for j in range(3):
                if self.Cb[i, j] != 0:
                    Kb += self.Cb[i, j] * (Bk[i].T * W2) @ Bk[j]
        self.Kb = Kb
        z = np.zeros((nq2, self.nu_))
        self.Bm_lin = [np.hstack([self.Bux, z]), np.hstack([z, self.Bvy]), np.hstack([self.Buy, self.Bvx])]
        Km = np.zeros((2 * self.nu_, 2 * self.nu_))
        for i in range(3):
            for j in range(3):
                if self.Cm[i, j] != 0:
                    Km += self.Cm[i, j] * (self.Bm_lin[i].T * W2) @ self.Bm_lin[j]
        self.Km = Km
        self.Kmf = np.linalg.cholesky(Km)
        self.fload = (self.Bw.T * W2).sum(axis=1)
        self.z = np.zeros(self.N); self.Q = 0.0

    def _state(self, z):
        c = z[:self.nw]; d = z[self.nw:]
        wx = self.Bwx @ c; wy = self.Bwy @ c
        e = np.array([self.Bm_lin[0] @ d + 0.5 * wx * wx, self.Bm_lin[1] @ d + 0.5 * wy * wy,
                      self.Bm_lin[2] @ d + wx * wy])
        n = self.Cm @ e
        return c, d, wx, wy, e, n

    def _grad_hess(self, z, Q):
        c, d, wx, wy, e, n = self._state(z)
        W2 = self.W2; nw = self.nw
        ql = Q * (1 - self.nu ** 2)
        gw = self.Kb @ c + self.Bwx.T @ (W2 * (n[0] * wx + n[2] * wy)) + self.Bwy.T @ (W2 * (n[1] * wy + n[2] * wx)) \
            - ql * self.fload
        gd = sum(self.Bm_lin[i].T @ (W2 * n[i]) for i in range(3))
        g = np.concatenate([gw, gd])
        # strain variation wrt c: de_x = wx Bwx, de_y = wy Bwy, dg = wx Bwy + wy Bwx
        Ew = [wx[:, None] * self.Bwx, wy[:, None] * self.Bwy, wx[:, None] * self.Bwy + wy[:, None] * self.Bwx]
        H = np.zeros((self.N, self.N))
        Hww = self.Kb.copy()
        for i in range(3):
            for j in range(3):
                if self.Cm[i, j] != 0:
                    Hww += self.Cm[i, j] * (Ew[i].T * W2) @ Ew[j]
        Hww += (self.Bwx.T * (W2 * n[0])) @ self.Bwx + (self.Bwy.T * (W2 * n[1])) @ self.Bwy
        t = (self.Bwx.T * (W2 * n[2])) @ self.Bwy
        Hww += t + t.T
        Hwd = np.zeros((nw, 2 * self.nu_))
        for i in range(3):
            for j in range(3):
                if self.Cm[i, j] != 0:
                    Hwd += self.Cm[i, j] * (Ew[i].T * W2) @ self.Bm_lin[j]
        H[:nw, :nw] = Hww; H[:nw, nw:] = Hwd; H[nw:, :nw] = Hwd.T; H[nw:, nw:] = self.Km
        return g, H

    def solve(self, Q, tol=1e-10, maxit=40):
        """advance from the current state to load Q (load stepping when Newton fails)."""
        if Q == 0:
            self.z[:] = 0; self.Q = 0; return self
        z0, Q0 = self.z.copy(), self.Q
        steps = [Q]
        while steps:
            Qt = steps[-1]
            z = self.z.copy()
            if self.Q > 0:
                z[:self.nw] *= (Qt / self.Q) ** (1 / 3.0) if Qt / self.Q < 8 else 1.0
            ok = False
            for it in range(maxit):
                g, H = self._grad_hess(z, Qt)
                try:
                    dz = np.linalg.solve(H, -g)
                except np.linalg.LinAlgError:
                    break
                z = z + dz
                if not np.all(np.isfinite(z)):
                    break
                if np.abs(dz).max() < tol * max(1.0, np.abs(z).max()):
                    ok = True; break
            if ok:
                self.z, self.Q = z, Qt; steps.pop()
            else:
                steps.append(0.5 * (self.Q + Qt) if self.Q > 0 else Qt / 4.0)
                if len(steps) > 60:
                    raise RuntimeError("no convergence")
        return self

    def results(self):
        """W at centre; S at centre in the short direction on the tension surface; S at the middle of the long
        edge, normal to it, on the tension surface."""
        from numpy.polynomial import polynomial as P
        n, nu = self.n, self.nu
        sx, sy = 2.0 / self.r, 2.0
        c = self.z[:self.nw].reshape(n, n); d = self.z[self.nw:]
        a_ = d[:self.nu_].reshape(n, n); b_ = d[self.nu_:].reshape(n, n)

        def ev1(kind, idx, x, scale):
            v, d1, d2, s = _basis(kind, idx, np.array([x]), scale)
            return v[0], d1[0], d2[0]
        f0, f0_1, f0_2 = ev1("w", self.ev, 0.0, self.sw)
        fe, fe_1, fe_2 = ev1("w", self.ev, 1.0, self.sw)
        ge0, ge0_1, _ = ev1("u", self.ev, 0.0, self.sge); go0, go0_1, _ = ev1("u", self.od, 0.0, self.sgo)
        gee, gee_1, _ = ev1("u", self.ev, 1.0, self.sge); goe, goe_1, _ = ev1("u", self.od, 1.0, self.sgo)
        Wc = f0 @ c @ f0
        Wxx = sx * sx * (f0_2 @ c @ f0); Wyy = sy * sy * (f0 @ c @ f0_2)
        Ux = sx * (go0_1 @ a_ @ ge0); Vy = sy * (ge0 @ b_ @ go0_1)
        ex, ey = Ux, Vy                                  # slopes vanish at the centre
        k = 1.0 / (1 - nu * nu)
        S_c = k * (ey + nu * ex) + 0.5 * k * abs(Wyy + nu * Wxx)
        # middle of the long edge: X = 0, eta = 1
        Wyy_e = sy * sy * (f0 @ c @ fe_2)
        Vy_e = sy * (ge0 @ b_ @ goe_1)
        S_e = k * Vy_e + 0.5 * k * abs(Wyy_e)
        return float(Wc), float(S_c), float(S_e)


def curve(r, nu, Qs, n=10):
    p = Plate(r, nu, n=n); out = []
    for Q in Qs:
        p.solve(Q); out.append(p.results())
    return np.array(out)


if __name__ == "__main__":
    import sys, time
    np.set_printoptions(precision=6, suppress=True, linewidth=150)
    Qs = [1, 10, 50, 200, 1000, 3000]
    for r in (1.0, 2.0):
        for n in (6, 8, 10, 12):
            t = time.time(); c = curve(r, 0.3, Qs, n=n)
            print("r", r, "n", n, "%.1fs" % (time.time() - t)); print(c.T)
