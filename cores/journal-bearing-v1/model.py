"""Journal bearing operating point: equilibrium position, film temperature, power, peak pressure.

Method LS-3 (see docs in gen.py). All SI inside. One class, grid given at construction.
"""
import numpy as np
from scipy.optimize import brentq
from film import Film

CP = 2000.0            # J/(kg K)
RHO_SLOPE = 0.65       # kg/m3 per K
TAYLOR = 41.3


def walther(nu40, nu100):
    f = lambda nu: np.log10(np.log10(nu + 0.7))
    B = (f(nu40) - f(nu100)) / (np.log10(373.15) - np.log10(313.15))
    A = f(nu40) + B * np.log10(313.15)
    return A, B


def oil_at(oil, T):
    A, B = walther(oil["nu40_cSt"], oil["nu100_cSt"])
    nu = 10 ** (10 ** (A - B * np.log10(T + 273.15))) - 0.7       # cSt
    rho = oil["rho15_kg_m3"] - RHO_SLOPE * (T - 15.0)
    return nu * 1e-6 * rho, rho                                      # Pa s, kg/m3


class Bearing:
    def __init__(self, brg, nth=240, nz=32):
        self.b = brg
        self.R = brg["diameter_mm"] / 2000.0
        self.L = brg["length_mm"] / 1000.0
        self.c = brg["radial_clearance_um"] * 1e-6
        self.Q = brg["oil_flow_L_min"] / 60000.0
        g = [a / 360.0 for a in brg["groove_angles_deg"]]
        self.film = Film(nth, nz, self.L / (2 * self.R), grooves=g)
        self.guess = None

    def forces(self, eps, psi, Rec, turb):
        P, Hn, Hf = self.film.solve(eps, psi, Rec, turb)
        return self.film.integrals(P, Hn, Hf, Rec, turb)

    def position(self, wbar, thL, Rec, turb):
        """(eps, psi) with the pressure resultant equal to wbar toward thL. Newton with finite differences."""
        tx, ty = wbar * np.cos(thL), wbar * np.sin(thL)
        if self.guess is None:
            x = np.array([0.5, 0.9])                 # (atanh-like variable for eps, attitude)
        else:
            x = self.guess.copy()
        # variables: u = log(eps/(1-eps)), phi = psi - thL
        def resid(x):
            eps = 1.0 / (1.0 + np.exp(-x[0])); psi = thL + x[1]
            fx, fy, fr, pm = self.forces(eps, psi, Rec, turb)
            s = max(wbar, 1e-12)
            return np.array([(fx - tx) / s, (fy - ty) / s]), (eps, psi, fr, pm)
        r, aux = resid(x)
        for it in range(40):
            if np.abs(r).max() < 1e-9:
                break
            J = np.zeros((2, 2))
            for k in (0, 1):
                d = np.zeros(2); d[k] = 1e-5
                J[:, k] = (resid(x + d)[0] - r) / 1e-5
            step = np.linalg.solve(J, -r)
            t = 1.0
            while True:
                xn = x + t * step
                xn[1] = np.clip(xn[1], -0.2, np.pi)
                rn, auxn = resid(xn)
                if np.abs(rn).max() < np.abs(r).max() or t < 1e-3:
                    break
                t *= 0.5
            x, r, aux = xn, rn, auxn
        self.guess = x.copy()
        return aux, it

    def point(self, rpm, load, beta_deg, t_in, regime=None):
        w = rpm * 2 * np.pi / 60.0
        thL = np.pi + np.radians(beta_deg)
        R, L, c = self.R, self.L, self.c
        Ret = TAYLOR * np.sqrt(R / c)
        def state(T):
            mu, rho = oil_at(self.b["oil"], T)
            Rec = rho * w * R * c / mu
            turb = (Rec > Ret) if regime is None else regime
            wbar = load * c ** 2 / (mu * w * R ** 3 * (L / 2))
            (eps, psi, fr, pm), _ = self.position(wbar, thL, Rec, turb)
            power = (mu * w * R / c) * R * (L / 2) * fr * w * R
            mu_in, rho_in = oil_at(self.b["oil"], t_in)
            t_out = t_in + power / (rho_in * CP * self.Q)
            return dict(eps=eps, psi=psi, power=power, t_eff=0.5 * (t_in + t_out), mu=mu, Rec=Rec, turb=bool(turb),
                        pmax=pm * mu * w * R ** 2 / c ** 2, margin=Rec / Ret)
        g = lambda T: state(T)["t_eff"] - T
        lo, hi = t_in, t_in + 5.0
        while g(hi) > 0:
            hi += 10.0
            if hi > t_in + 400: raise RuntimeError("no thermal balance")
        T = brentq(g, lo, hi, xtol=1e-6)
        s = state(T)
        s["t_eff"] = T
        s["attitude"] = np.degrees(s["psi"] - thL)
        s["hmin_um"] = c * (1 - s["eps"]) * 1e6
        return s
