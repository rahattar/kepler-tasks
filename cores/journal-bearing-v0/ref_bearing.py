#!/usr/bin/env python3
"""Reference: operating points of a grooved journal bearing to LS-3.   python3 bearing.py CASE_DIR OUT_CSV

Speed comes from three things. The grooves are lines of zero pressure, so the film falls into separate lands,
each a plain rectangle whose equations are banded (half-width = axial nodes). Rupture is found by an active
set on that banded system, started from the previous film. And position, attitude and film temperature are
found together by one Newton iteration, three unknowns, rather than one loop inside another.
"""
import csv
import json
import math
import sys

import numpy as np
from scipy.linalg import solve_banded

CP, RHO_SLOPE, TAYLOR = 2000.0, 0.65, 41.3
GRIDS = ((144, 16), (192, 20))     # circumferential nodes round the bearing, axial nodes on the half length
REFINE_ABOVE = 0.75                # eccentricity above which the finer grid is used


def oil_constants(oil):
    f = lambda nu: math.log10(math.log10(nu + 0.7))
    B = (f(oil["nu40_cSt"]) - f(oil["nu100_cSt"])) / (math.log10(373.15) - math.log10(313.15))
    return f(oil["nu40_cSt"]) + B * math.log10(313.15), B, oil["rho15_kg_m3"]


def oil_at(k, T):
    A, B, rho15 = k
    rho = rho15 - RHO_SLOPE * (T - 15.0)
    return (10 ** (10 ** (A - B * math.log10(T + 273.15))) - 0.7) * 1e-6 * rho, rho


def turb(Reh):
    return 12.0 + 0.0136 * Reh ** 0.90, 12.0 + 0.0043 * Reh ** 0.96, 1.0 + 0.0012 * Reh ** 0.94


class Land:
    """The film between two grooves: theta in (a, b), m interior columns, NZ axial nodes on the half length."""

    def __init__(self, a, b, m, lam, nz):
        self.nz = NZ = nz
        self.m, self.dth = m, (b - a) / (m + 1)
        self.th = a + self.dth * np.arange(1, m + 1)
        self.thf = a + self.dth * (np.arange(m + 1) + 0.5)          # faces, m + 1 of them
        self.cos, self.sin = np.cos(self.th), np.sin(self.th)
        self.lam, self.dz = lam, 1.0 / NZ
        self.active = np.ones((m, NZ), bool)
        self.wz = np.full(NZ, 2.0 * self.dz * self.dth); self.wz[0] *= 0.5

    def solve(self, eps, psi, Rec, turbulent):
        m, dth, dz, NZ = self.m, self.dth, self.dz, self.nz
        Hf = 1.0 - eps * np.cos(self.thf - psi)
        Hn = 1.0 - eps * np.cos(self.th - psi)
        if turbulent:
            Gf = Hf ** 3 / turb(Rec * Hf)[0]; Gz = Hn ** 3 / turb(Rec * Hn)[1]
        else:
            Gf = Hf ** 3 / 12.0; Gz = Hn ** 3 / 12.0
        ae = (Gf[1:] / dth ** 2)[:, None] * np.ones(NZ)             # to column i + 1
        aw = (Gf[:-1] / dth ** 2)[:, None] * np.ones(NZ)
        an = (self.lam * Gz / dz ** 2)[:, None] * np.ones(NZ)       # to node j + 1
        as_ = an.copy(); as_[:, 0] = 0.0
        up = an.copy(); up[:, 0] *= 2.0                              # symmetry at mid-length
        diag = ae + aw + up + as_ if False else ae + aw + 2.0 * an
        rhs = (-0.5 * (Hf[1:] - Hf[:-1]) / dth)[:, None] * np.ones(NZ)
        upz = up.copy(); upz[:, -1] = 0.0                            # j = NZ-1 couples to the end, p = 0
        aez = ae.copy(); aez[-1, :] = 0.0
        awz = aw.copy(); awz[0, :] = 0.0
        n = m * NZ
        act = self.active
        for _ in range(40):
            ab = np.zeros((2 * NZ + 1, n))
            a = act.ravel()
            ab[NZ, :] = np.where(a, diag.ravel(), 1.0)
            ab[NZ - 1, 1:] = np.where(a, -upz.ravel(), 0.0)[:-1]
            ab[NZ + 1, :-1] = np.where(a, -as_.ravel(), 0.0)[1:]
            ab[0, NZ:] = np.where(a, -aez.ravel(), 0.0)[:-NZ]
            ab[2 * NZ, :-NZ] = np.where(a, -awz.ravel(), 0.0)[NZ:]
            p = solve_banded((NZ, NZ), ab, np.where(a, rhs.ravel(), 0.0), overwrite_ab=True, overwrite_b=True,
                             check_finite=False).reshape(m, NZ)
            neg = act & (p < 0.0)
            p[neg] = 0.0
            pe = np.zeros_like(p); pe[:-1] = p[1:]
            pw = np.zeros_like(p); pw[1:] = p[:-1]
            pn = np.zeros_like(p); pn[:, :-1] = p[:, 1:]
            ps = np.zeros_like(p); ps[:, 1:] = p[:, :-1]
            res = rhs - (diag * p - ae * pe - aw * pw - up * pn - as_ * ps)
            pos = ~act & (res > 1e-12)
            if not neg.any() and not pos.any():
                break
            act = (act & ~neg) | pos
        self.active = act
        w = p * self.wz
        fx = float(np.sum(w * self.cos[:, None])); fy = float(np.sum(w * self.sin[:, None]))
        return fx, fy, float(p.max())


class Bearing:
    def __init__(self, b):
        self.R = b["diameter_mm"] / 2000.0; self.L = b["length_mm"] / 1000.0
        self.c = b["radial_clearance_um"] * 1e-6; self.Q = b["oil_flow_L_min"] / 60000.0
        self.oil = oil_constants(b["oil"])
        g = sorted(math.radians(a % 360.0) for a in b["groove_angles_deg"])
        lam = (2.0 * self.R / self.L) ** 2
        self.grids = []
        for nth, nz in GRIDS:
            lands = []
            for k, a in enumerate(g):
                bnd = g[(k + 1) % len(g)] + (2 * math.pi if k == len(g) - 1 else 0.0)
                m = max(8, int(round(nth * (bnd - a) / (2 * math.pi))) - 1)
                lands.append(Land(a, bnd, m, lam, nz))
            self.grids.append(lands)
        self.lands = self.grids[0]
        self.thq = (np.arange(720) + 0.5) * 2 * math.pi / 720
        self.Ret = TAYLOR * math.sqrt(self.R / self.c)

    def film(self, eps, psi, Rec, turbulent):
        fx = fy = pm = 0.0
        for land in self.lands:
            a, b, c = land.solve(eps, psi, Rec, turbulent)
            fx += a; fy += b; pm = max(pm, c)
        if turbulent:
            H = 1.0 - eps * np.cos(self.thq - psi)
            couette = float(np.sum(turb(Rec * H)[2] / H)) * (2 * math.pi / 720) * 2.0
        else:
            couette = 4.0 * math.pi / math.sqrt(1.0 - eps * eps)
        fr = couette - 0.5 * eps * (fy * math.cos(psi) - fx * math.sin(psi))
        return fx, fy, fr, pm

    def residual(self, x, w, load, thL, t_in, turbulent):
        eps = 1.0 / (1.0 + math.exp(-x[0])); psi = thL + x[1]; T = x[2]
        mu, rho = oil_at(self.oil, T)
        R, L, c = self.R, self.L, self.c
        Rec = rho * w * R * c / mu
        fx, fy, fr, pm = self.film(eps, psi, Rec, turbulent)
        wbar = load * c * c / (mu * w * R ** 3 * (L / 2))
        power = (mu * w * R / c) * R * (L / 2) * fr * w * R
        rho_in = oil_at(self.oil, t_in)[1]
        t_eff = t_in + 0.5 * power / (rho_in * CP * self.Q)
        r = np.array([fx / wbar - math.cos(thL), fy / wbar - math.sin(thL), (t_eff - T) / 10.0])
        return r, (eps, psi, T, power, pm * mu * w * R * R / (c * c), Rec)

    def solve_regime(self, w, load, thL, t_in, turbulent, x0):
        x = np.array(x0, float)
        r, aux = self.residual(x, w, load, thL, t_in, turbulent)
        for _ in range(60):
            if np.abs(r).max() < 1e-8:
                return x, aux
            J = np.empty((3, 3))
            for k, d in enumerate((1e-5, 1e-5, 1e-3)):
                xp = x.copy(); xp[k] += d
                J[:, k] = (self.residual(xp, w, load, thL, t_in, turbulent)[0] - r) / d
            try:
                step = np.linalg.solve(J, -r)
            except np.linalg.LinAlgError:
                step = -r
            t = 1.0
            while True:
                xn = x + t * step
                xn[0] = min(max(xn[0], -9.0), 9.0); xn[1] = min(max(xn[1], -0.5), math.pi); xn[2] = max(xn[2], t_in)
                rn, auxn = self.residual(xn, w, load, thL, t_in, turbulent)
                if np.abs(rn).max() < np.abs(r).max() or t < 1e-3:
                    break
                t *= 0.5
            x, r, aux = xn, rn, auxn
        return x, aux

    def point(self, rpm, load, beta, t_in):
        w = rpm * 2 * math.pi / 60.0; thL = math.pi + math.radians(beta)
        x0 = (0.0, 0.9, t_in + 8.0)
        self.lands = self.grids[0]
        for turbulent in (False, True):
            x, aux = self.solve_regime(w, load, thL, t_in, turbulent, x0)
            if (aux[5] > self.Ret) == turbulent:
                break
            x0 = x
        if aux[0] > REFINE_ABOVE:
            self.lands = self.grids[1]
            x, aux = self.solve_regime(w, load, thL, t_in, turbulent, x)
        eps, psi, T, power, pmax, Rec = aux
        return self.c * (1 - eps) * 1e6, math.degrees(psi - thL), power / 1e3, T, pmax / 1e6


def main(case, out):
    brg = Bearing(json.load(open(case + "/bearing.json")))
    with open(out, "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"])
        for row in csv.DictReader(open(case + "/points.csv")):
            h, att, P, T, pm = brg.point(float(row["speed_rpm"]), float(row["load_N"]), float(row["load_angle_deg"]),
                                         float(row["inlet_C"]))
            wr.writerow([row["point"], "%.3f" % h, "%.2f" % att, "%.4f" % P, "%.2f" % T, "%.4f" % pm])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
