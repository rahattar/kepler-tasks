"""A correct but unoptimised program: general sparse solves, one loop inside another."""

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl


def coeffs(Reh, turbulent):
    if not turbulent:
        return 12.0 + 0 * Reh, 12.0 + 0 * Reh, 1.0 + 0 * Reh
    return 12.0 + 0.0136 * Reh ** 0.90, 12.0 + 0.0043 * Reh ** 0.96, 1.0 + 0.0012 * Reh ** 0.94


class Film:
    def __init__(self, nth, nz, lod, grooves=(0.25, 0.75)):
        assert nth % 4 == 0
        self.nth, self.nz, self.lod = nth, nz, lod
        self.th = np.arange(nth) * 2 * np.pi / nth
        self.dth = 2 * np.pi / nth
        self.dz = 1.0 / nz
        self.lam = (1.0 / lod) ** 2          # (2R/L)^2 = (D/L)^2
        self.groove = np.zeros(nth, bool)
        for g in grooves:
            self.groove[int(round(g * nth))] = True
        self.free = np.where(~np.repeat(self.groove[:, None], nz, 1).ravel())[0]   # unknown nodes (i, j), j = 0..nz-1
        self.wz = np.ones(nz); self.wz[0] = 0.5                                      # trapezoid on [0,1], end value 0
        self.last = None

    def assemble(self, eps, psi, Rec=0.0, turbulent=False):
        nth, nz, dth, dz = self.nth, self.nz, self.dth, self.dz
        thf = self.th + dth / 2                                   # face i+1/2
        Hf = 1 - eps * np.cos(thf - psi)
        Hn = 1 - eps * np.cos(self.th - psi)
        kt, _, _ = coeffs(Rec * Hf, turbulent)
        _, kzn, _ = coeffs(Rec * Hn, turbulent)
        Gf = Hf ** 3 / kt                                          # theta faces
        Gz = Hn ** 3 / kzn                                         # axial, at nodes
        idx = np.arange(nth * nz).reshape(nth, nz)
        ip, im = np.roll(idx, -1, 0), np.roll(idx, 1, 0)
        ae = np.repeat((Gf / dth ** 2)[:, None], nz, 1)            # to i+1
        aw = np.repeat((np.roll(Gf, 1) / dth ** 2)[:, None], nz, 1)
        an = np.repeat((self.lam * Gz / dz ** 2)[:, None], nz, 1)  # to j+1 (j = nz-1 -> end, p = 0)
        as_ = an.copy()
        rows, cols, vals = [], [], []
        diag = ae + aw + an + as_
        # symmetry at j = 0: p[-1] = p[1], so the j+1 coefficient doubles and there is no j-1 neighbour
        rows.append(idx.ravel()); cols.append(idx.ravel()); vals.append(diag.ravel())
        rows.append(idx.ravel()); cols.append(ip.ravel()); vals.append(-ae.ravel())
        rows.append(idx.ravel()); cols.append(im.ravel()); vals.append(-aw.ravel())
        up = an.copy(); up[:, 0] *= 2
        rows.append(idx[:, :-1].ravel()); cols.append(idx[:, 1:].ravel()); vals.append(-up[:, :-1].ravel())
        rows.append(idx[:, 1:].ravel()); cols.append(idx[:, :-1].ravel()); vals.append(-as_[:, 1:].ravel())
        A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(nth * nz,) * 2)
        b = -0.5 * (Hf - np.roll(Hf, 1)) / dth                      # -(S dH/dtheta), S = 1/2 ; A p = b
        b = np.repeat(b[:, None], nz, 1).ravel()
        return A, b, Hn, Hf

    def solve(self, eps, psi, Rec=0.0, turbulent=False, warm=True):
        A, b, Hn, Hf = self.assemble(eps, psi, Rec, turbulent)
        n = self.nth * self.nz
        free = np.zeros(n, bool); free[self.free] = True
        act = free.copy()
        if warm and self.last is not None and self.last.shape[0] == n:
            act = free & self.last
        p = np.zeros(n)
        for it in range(60):
            ids = np.where(act)[0]
            p[:] = 0.0
            if len(ids):
                p[ids] = spl.spsolve(A[ids][:, ids].tocsc(), b[ids])
            neg = act & (p < 0)
            res = b - A @ p                                        # at inactive free nodes: want res <= 0
            pos = free & ~act & (res > 1e-13)
            if not neg.any() and not pos.any():
                break
            act = (act & ~neg) | pos
            p[neg] = 0.0
        self.last = act
        self.its = it + 1
        P = p.reshape(self.nth, self.nz)
        return P, Hn, Hf

    def integrals(self, P, Hn, Hf, Rec=0.0, turbulent=False):
        """Dimensionless: force components (toward theta=0 and theta=90 deg, of the pressure resultant), friction, peak."""
        w = self.wz[None, :] * self.dz * self.dth * 2.0              # both halves
        fx = np.sum(P * np.cos(self.th)[:, None] * w)
        fy = np.sum(P * np.sin(self.th)[:, None] * w)
        _, _, cf = coeffs(Rec * Hn, turbulent)
        couette = np.sum(cf / Hn) * self.dth * 2.0                   # full length, Z in [-1,1]
        dP = (np.roll(P, -1, 0) - np.roll(P, 1, 0)) / (2 * self.dth)
        poise = np.sum(0.5 * Hn[:, None] * dP * w)
        return fx, fy, couette + poise, P.max()


import numpy as np
from scipy.optimize import brentq

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


def main(case, out):
    import csv, json
    b = Bearing(json.load(open(case + "/bearing.json")), 96, 12)
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"])
        for r in csv.DictReader(open(case + "/points.csv")):
            b.guess = None
            s = b.point(float(r["speed_rpm"]), float(r["load_N"]), float(r["load_angle_deg"]), float(r["inlet_C"]))
            w.writerow([r["point"], "%.3f" % s["hmin_um"], "%.2f" % s["attitude"], "%.4f" % (s["power"] / 1e3),
                        "%.2f" % s["t_eff"], "%.4f" % (s["pmax"] / 1e6)])


if __name__ == "__main__":
    import sys
    main(sys.argv[1], sys.argv[2])
