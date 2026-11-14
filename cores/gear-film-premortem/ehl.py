"""Isothermal Newtonian EHL line contact, dimensionless (Venner): X = x/a, P = p/ph, H = h R / a^2.
Reynolds  d/dX(eps dP/dX) - d(rho H)/dX = 0,  eps = rho H^3 / (eta lam)
Film      H = H0 + X^2/2 - (1/pi) int ln|X - X'| P dX'
Load      int P dX = pi/2
Roelands viscosity, Dowson-Higginson density; cavitation P >= 0 (projection)."""
import numpy as np

P0_ROE = 1.96e8


class Case:
    def __init__(self, w, R, Ep, eta0, alpha, um):
        self.w, self.R, self.Ep, self.eta0, self.alpha, self.um = w, R, Ep, eta0, alpha, um
        W = w / (Ep * R); U = eta0 * um / (Ep * R); G = alpha * Ep
        self.W, self.U, self.G = W, U, G
        self.M = W * U ** -0.5; self.L = G * U ** 0.25
        self.a = R * np.sqrt(8 * W / np.pi)
        self.ph = Ep * np.sqrt(W / (2 * np.pi))
        self.lam = 6 * eta0 * (2 * um) * R ** 2 / (self.a ** 3 * self.ph)
        self.z = alpha * P0_ROE / (np.log(eta0) + 9.67)

    def eta(self, P):
        p = self.ph * np.maximum(P, 0)
        e = np.exp((np.log(self.eta0) + 9.67) * (-1 + (1 + p / P0_ROE) ** self.z))
        de = e * (np.log(self.eta0) + 9.67) * self.z * (1 + p / P0_ROE) ** (self.z - 1) / P0_ROE * self.ph
        return e, de

    def rho(self, P):
        p = self.ph * np.maximum(P, 0)
        r = 1 + 0.6e-9 * p / (1 + 1.7e-9 * p)
        dr = 0.6e-9 / (1 + 1.7e-9 * p) ** 2 * self.ph
        return r, dr

    def h_dim(self, H):
        return H * self.a ** 2 / self.R


def kernel(X, h):
    F = lambda t: np.where(t == 0, 0.0, t * np.log(np.abs(t) + 1e-300) - t)
    D = X[None, :] - X[:, None]
    return F(D + h / 2) - F(D - h / 2)


def solve(case, N=500, Xa=-4.0, Xb=1.5, P_init=None, H0_init=None, order=2, iters=60, tol=1e-9, damp=1.0, verbose=False):
    """Newton-Raphson on all nodes and H0. Returns dict with X, P, H, H0, converged, iterations."""
    X = np.linspace(Xa, Xb, N + 2)[1:-1]
    h = X[1] - X[0]
    K = kernel(X, h) / np.pi
    if P_init is None:
        P = np.where(np.abs(X) < 1, np.sqrt(np.clip(1 - X ** 2, 0, None)), 0.0)
    else:
        P = np.interp(X, *P_init)
    H0 = -0.5 if H0_init is None else H0_init
    lam = case.lam
    conv = False
    for it in range(iters):
        H = H0 + X ** 2 / 2 - K @ P
        if np.any(H <= 0):
            # raise H0 so the film is positive
            H0 += -H.min() + 1e-6
            H = H0 + X ** 2 / 2 - K @ P
        e, de = case.eta(P); r, dr = case.rho(P)
        eps = r * H ** 3 / (e * lam)
        Pf = np.concatenate([[0.0], P, [0.0]])
        epsf = np.concatenate([[eps[0]], eps, [eps[-1]]])
        em = 0.5 * (epsf[1:-1] + epsf[:-2]); ep = 0.5 * (epsf[1:-1] + epsf[2:])
        rH = r * H
        rHf = np.concatenate([[rH[0], rH[0]], rH])           # values before the inlet: as the first node
        if order == 2:
            wedge = (3 * rHf[2:] - 4 * rHf[1:-1] + rHf[:-2]) / (2 * h)
            wedge[0] = (rH[0] - rH[0]) / h
        else:
            wedge = (rHf[2:] - rHf[1:-1]) / h
        Rres = (ep * (Pf[2:] - Pf[1:-1]) - em * (Pf[1:-1] - Pf[:-2])) / h ** 2 - wedge
        Fres = h * P.sum() - np.pi / 2
        # Jacobian
        dHdP = -K                                             # (N, N)
        deps = eps[:, None] * (3 * dHdP / H[:, None]) + np.diag(eps * (dr / r - de / e))
        drH = r[:, None] * dHdP + np.diag(dr * H)
        J = np.zeros((N + 1, N + 1))
        dPp = np.concatenate([P[1:] - P[:-1], [0 - P[-1]]])   # P_{i+1} - P_i
        dPm = np.concatenate([[P[0] - 0], P[1:] - P[:-1]])   # P_i - P_{i-1}
        # d(ep)/dP = 0.5 (deps_i + deps_{i+1}); d(em) = 0.5 (deps_i + deps_{i-1})
        depsp = 0.5 * (deps + np.vstack([deps[1:], deps[-1:]]))
        depsm = 0.5 * (deps + np.vstack([deps[:1], deps[:-1]]))
        J[:N, :N] = (depsp * dPp[:, None] - depsm * dPm[:, None]) / h ** 2
        idx = np.arange(N)
        J[idx, idx] += -(ep + em) / h ** 2
        J[idx[:-1], idx[:-1] + 1] += ep[:-1] / h ** 2
        J[idx[1:], idx[1:] - 1] += em[1:] / h ** 2
        drHf = np.vstack([drH[:1], drH[:1], drH])
        if order == 2:
            dw = (3 * drHf[2:] - 4 * drHf[1:-1] + drHf[:-2]) / (2 * h)
            dw[0] = 0.0
        else:
            dw = (drHf[2:] - drHf[1:-1]) / h
        J[:N, :N] -= dw
        # d/dH0: dH/dH0 = 1
        depsH0 = eps * 3 / H
        drHH0 = r
        epsH0f = np.concatenate([[depsH0[0]], depsH0, [depsH0[-1]]])
        dep = 0.5 * (epsH0f[1:-1] + epsH0f[2:]); dem = 0.5 * (epsH0f[1:-1] + epsH0f[:-2])
        rHH0f = np.concatenate([[drHH0[0], drHH0[0]], drHH0])
        dwH0 = (3 * rHH0f[2:] - 4 * rHH0f[1:-1] + rHH0f[:-2]) / (2 * h) if order == 2 else (rHH0f[2:] - rHH0f[1:-1]) / h
        if order == 2:
            dwH0[0] = 0.0
        J[:N, N] = (dep * dPp - dem * dPm) / h ** 2 - dwH0
        J[N, :N] = h
        # cavitated nodes: P = 0 replaces Reynolds
        cav = (P <= 0) & (Rres < 0)
        Rres = np.where(cav, P, Rres)
        J[np.flatnonzero(cav), :] = 0.0
        J[np.flatnonzero(cav), np.flatnonzero(cav)] = 1.0
        res = np.concatenate([Rres, [Fres]])
        scale = np.max(np.abs(Rres)) * h ** 2
        if verbose:
            print(it, "res %.3e  load %.2e  H0 %.5f" % (scale, Fres, H0))
        try:
            d = np.linalg.solve(J, -res)
        except np.linalg.LinAlgError:
            return dict(converged=False, iterations=it, X=X, P=P, H0=H0)
        P = np.maximum(P + damp * d[:N], 0.0)
        H0 = H0 + damp * d[N]
        if np.max(np.abs(d[:N])) < tol and abs(Fres) < 1e-9:
            conv = True
            break
        if not np.all(np.isfinite(P)):
            return dict(converged=False, iterations=it, X=X, P=P, H0=H0)
    H = H0 + X ** 2 / 2 - K @ P
    return dict(converged=conv, iterations=it + 1, X=X, P=P, H=H, H0=H0, Hc=float(np.interp(0.0, X, H)), Hmin=float(H.min()))


def continuation(case_fn, targets, N=500, **kw):
    """Solve a sequence of cases (increasing difficulty), each from the last solution."""
    out, prev = [], None
    for c in targets:
        case = case_fn(c)
        sol = solve(case, N=N, P_init=None if prev is None else (prev["X"], prev["P"]),
                    H0_init=None if prev is None else prev["H0"], **kw)
        out.append((case, sol))
        if sol["converged"]:
            prev = sol
    return out
