"""The sealed definition of the layered pipe wall, and a one-step-per-ramp integrator built on it.

State per line (vectorised over lines in lockstep): hoop strain eps, and per layer plastic strain ep,
backstresses X[3], isotropic increment R. Uniaxial hoop stress. Layers at z_i = ((i + 1/2)/N - 1/2) t,
inner surface first. Thermal strain alpha * dT * (-z/t): dT = T_inner - T_outer.
Equilibrium: mean layer stress = p R / t. Chaboche (Armstrong-Frederick) backstresses, Voce isotropic.
`advance(state, mat, sm, dT, substeps)` takes the lines from their present load to (sm, dT) along a straight
line in (sm, dT), in `substeps` equal parts, each solved at its end with the exact laws of the material under
plastic flow of one sign (the exponential forms)."""
import numpy as np

NL = 24
Z = (np.arange(NL) + 0.5) / NL - 0.5


class Mat:
    """Constants per line, arrays of shape (n,) or (n,3)."""
    def __init__(self, rows):
        self.E = np.array([r["E"] for r in rows])[:, None]
        self.A = np.array([r["alpha"] for r in rows])[:, None]
        self.k0 = np.array([r["k0"] for r in rows])[:, None]
        self.C = np.array([r["C"] for r in rows])[:, None, :]
        self.G = np.array([r["g"] for r in rows])[:, None, :]
        self.Q = np.array([r["Q"] for r in rows])[:, None]
        self.b = np.array([r["b"] for r in rows])[:, None]


class State:
    def __init__(self, n):
        self.ep = np.zeros((n, NL)); self.X = np.zeros((n, NL, 3)); self.R = np.zeros((n, NL))
        self.eps = np.zeros(n); self.sm = np.zeros(n); self.dT = np.zeros(n)


def _solve(st, m, sm, dT, exact=True):
    """End state of one straight step to (sm, dT); returns (eps, dp, n)."""
    epth = m.A * dT[:, None] * (-Z)
    eps = st.eps.copy()
    Xs = st.X.sum(-1); k = m.k0 + st.R
    sat = m.C / m.G
    for _ in range(60):
        tr = m.E * (eps[:, None] - epth - st.ep)
        f = np.abs(tr - Xs) - k
        n = np.where(tr >= Xs, 1.0, -1.0)
        pl = f > 0
        dp = np.zeros_like(tr); dg = -m.E * np.ones_like(tr)
        if pl.any():
            for _ in range(40):
                if exact:
                    e = np.exp(-m.G * dp[..., None]); a = st.X - n[..., None] * sat
                    Xn = (n[..., None] * sat + a * e).sum(-1); dX = (-m.G * a * e).sum(-1)
                    eb = np.exp(-m.b * dp); kn = m.Q + m.k0 + (st.R - m.Q) * eb; dk = -m.b * (st.R - m.Q) * eb
                else:
                    den = 1 + m.G * dp[..., None]; num = st.X + n[..., None] * m.C * dp[..., None]
                    Xn = (num / den).sum(-1); dX = ((n[..., None] * m.C * den - num * m.G) / den ** 2).sum(-1)
                    bd = 1 + m.b * dp; kn = m.k0 + (st.R + m.b * m.Q * dp) / bd; dk = (m.b * m.Q * bd - (st.R + m.b * m.Q * dp) * m.b) / bd ** 2
                g = n * (tr - m.E * n * dp - Xn) - kn
                dg = -m.E - n * dX - dk
                new = np.where(pl, np.maximum(dp - g / dg, 0.0), 0.0)
                if np.max(np.abs(new - dp)) < 1e-14:
                    dp = new; break
                dp = new
        sig = tr - m.E * n * dp
        H = -dg - m.E
        tan = np.where(pl, m.E * H / (m.E + H), m.E)
        r = sig.mean(1) - sm
        if np.max(np.abs(r)) < 1e-9:
            break
        eps = eps - r / tan.mean(1)
    return eps, dp, n


def _commit(st, m, eps, dp, n, sm, dT, exact=True):
    if exact:
        sat = m.C / m.G
        st.X = n[..., None] * sat + (st.X - n[..., None] * sat) * np.exp(-m.G * dp[..., None])
        st.R = m.Q + (st.R - m.Q) * np.exp(-m.b * dp)
    else:
        st.X = (st.X + n[..., None] * m.C * dp[..., None]) / (1 + m.G * dp[..., None])
        st.R = (st.R + m.b * m.Q * dp) / (1 + m.b * dp)
    st.ep = st.ep + n * dp
    st.eps = eps; st.sm = sm.copy(); st.dT = dT.copy()


def advance(st, m, sm, dT, substeps=1, exact=True):
    s0, d0 = st.sm.copy(), st.dT.copy()
    for j in range(1, substeps + 1):
        f = j / substeps
        a, b = s0 + f * (sm - s0), d0 + f * (dT - d0)
        eps, dp, n = _solve(st, m, a, b, exact)
        _commit(st, m, eps, dp, n, a, b, exact)
    return st
