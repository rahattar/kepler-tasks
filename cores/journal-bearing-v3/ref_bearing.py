#!/usr/bin/env python3
"""Reference: operating points of a grooved journal bearing to LS-3.   python3 bearing.py CASE_DIR OUT_CSV

A long record is not solved point by point. With the viscosity taken out, the laminar film's force and peak
pressure depend only on where the journal sits, so for each state of the bearing they are worked out once on a
grid of positions and every point of that state is then solved from the table, all points at once (Chart).

The package's records are first reduced to the bearing as it stood at each operating point (state_at), and the
inlet temperature to what the sound RTDs read (inlets). Then the film is solved.

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


NOMINAL = {22: (22.0, 4.3, 860.0), 32: (32.0, 5.4, 865.0), 46: (46.0, 6.8, 870.0), 68: (68.0, 8.7, 875.0),
           100: (100.0, 11.4, 880.0), 150: (150.0, 15.0, 885.0)}


def grade_number(text):
    return int(float(str(text).upper().replace("ISO", "").replace("VG", "").strip()))


def state_at(sheet, history, samples, date):
    """(D mm, L mm, c mm, groove angles, (nu40, nu100, rho15), Q L/min) as the bearing stood on `date`."""
    pos = sheet["position"]
    D = float(sheet["journal_diameter_mm"]); c = float(sheet["radial_clearance_um"]) / 1000.0
    turn = 0.0; flow = float(sheet["oil_flow_L_min"]); grade = grade_number(sheet["oil_grade"]); charged = ""
    for job in sorted(history, key=lambda r: r["date"]):
        if job["date"] >= date:
            break
        mine = job["position"] == pos
        if job["work"] == "SHELL_FITTED" and mine:
            c = float(job["value"]) / 2.0                       # the clearance measured at fitting is diametral
        elif job["work"] == "JOURNAL_GROUND" and mine:
            c += (D - float(job["value"])) / 2.0                # the shell is as it was; the journal is smaller
            D = float(job["value"])
        elif job["work"] == "SPLIT_SET" and mine:
            turn = float(job["value"])
        elif job["work"] == "ORIFICE_CHANGED" and mine:
            flow = float(job["value"])
        elif job["work"] == "OIL_CHANGED":
            grade = grade_number(job["value"]); charged = job["date"]
    oil = NOMINAL[grade]
    for sample in sorted(samples, key=lambda r: r["date"]):
        if charged < sample["date"] < date:                     # an analysis of the charge now in the system
            oil = (float(sample["nu40_cSt"]), float(sample["nu100_cSt"]), float(sample["rho15_kg_m3"]))
    grooves = tuple((float(a) + turn) % 360.0 for a in sheet["groove_angles_deg"])
    return (D, float(sheet["length_mm"]), c, grooves, oil, flow)


AGREE = 0.5      # K: two sound supply RTDs read within this of each other
CLEAR = 0.3      # K: how much better one inlet must fit the drain reading to be preferred


def reading(text):
    value = float(text)
    return value if -50.0 < value < 200.0 else None


class Bearing:
    def __init__(self, state):
        D, L, c, grooves, oil, flow = state
        self.R = D / 2000.0; self.L = L / 1000.0
        self.c = c / 1000.0; self.Q = flow / 60000.0
        self.oil = oil_constants(dict(nu40_cSt=oil[0], nu100_cSt=oil[1], rho15_kg_m3=oil[2]))
        g = sorted(math.radians(a % 360.0) for a in grooves)
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


from scipy.interpolate import RectBivariateSpline

CHARTS = {}               # one chart for each film geometry (L/R and groove positions) met in the run
CHART_FROM = 200          # points in one bearing state above which the chart pays for itself
U_NODES = np.linspace(-4.3, 3.8, 38)          # u = ln(eps / (1 - eps)): eps from 0.013 to 0.978
PSI_STEP = math.radians(3.0)


class Chart:
    """Laminar film of one bearing state, tabulated over journal position (u, psi)."""

    def __init__(self, brg, th_lo, th_hi):
        self.psi = np.arange(th_lo - 0.30, th_hi + 2.15 + PSI_STEP, PSI_STEP)
        logf = np.empty((len(U_NODES), len(self.psi))); ang = np.empty_like(logf); logp = np.empty_like(logf)
        brg.lands = brg.grids[0]
        for i, u in enumerate(U_NODES):
            eps = 1.0 / (1.0 + math.exp(-u))
            prev = 0.0
            for j, psi in enumerate(self.psi):
                fx, fy, fr, pm = brg.film(eps, psi, 0.0, False)
                logf[i, j] = math.log(math.hypot(fx, fy))
                a = math.atan2(fy, fx) - psi                          # direction of the resultant, from the line of centres
                a += 2 * math.pi * round((prev - a) / (2 * math.pi))  # unwrapped along psi
                ang[i, j] = prev = a
                logp[i, j] = math.log(pm)
        self.s_f = RectBivariateSpline(U_NODES, self.psi, logf)
        self.s_a = RectBivariateSpline(U_NODES, self.psi, ang)
        self.s_p = RectBivariateSpline(U_NODES, self.psi, logp)
        self.a0 = ang

    def solve(self, b, w, load, thL, t_in):
        """All points of bearing state b at once. Returns arrays (h_min um, attitude deg, power kW, T_eff,
        p_max MPa, ok)."""
        R, L, c = b.R, b.L, b.c
        n = len(w)
        A, B, rho15 = b.oil
        def visc(T):
            rho = rho15 - RHO_SLOPE * (T - 15.0)
            return (10 ** (10 ** (A - B * np.log10(T + 273.15))) - 0.7) * 1e-6 * rho, rho
        rho_in = rho15 - RHO_SLOPE * (t_in - 15.0)
        u = np.zeros(n); phi = np.full(n, 0.9); T = t_in + 8.0
        ok = np.zeros(n, bool)
        ulo, uhi = U_NODES[0], U_NODES[-1]; plo, phi_hi = self.psi[0], self.psi[-1]

        def resid(u, phi, T):
            psi = thL + phi
            lf = self.s_f.ev(u, psi); an = self.s_a.ev(u, psi)
            mu, rho = visc(T)
            eps = 1.0 / (1.0 + np.exp(-u))
            f = np.exp(lf); dirn = an + psi
            fx, fy = f * np.cos(dirn), f * np.sin(dirn)
            fr = 4.0 * math.pi / np.sqrt(1.0 - eps * eps) - 0.5 * eps * (fy * np.cos(psi) - fx * np.sin(psi))
            wbar = load * c * c / (mu * w * R ** 3 * (L / 2))
            power = (mu * w * R / c) * R * (L / 2) * fr * w * R
            t_eff = t_in + 0.5 * power / (rho_in * CP * b.Q)
            d = dirn - thL
            d -= 2 * math.pi * np.round(d / (2 * math.pi))
            return np.stack([lf - np.log(wbar), d, (t_eff - T) / 10.0]), (eps, psi, power, mu, rho)

        r, aux = resid(u, phi, T)
        for _ in range(60):
            done = np.abs(r).max(axis=0) < 1e-9
            if done.all():
                break
            J = np.empty((3, 3, n))
            for k, d in enumerate((1e-5, 1e-5, 1e-3)):
                up = u + (d if k == 0 else 0.0); pp = phi + (d if k == 1 else 0.0); Tp = T + (d if k == 2 else 0.0)
                J[:, k, :] = (resid(up, pp, Tp)[0] - r) / d
            step = np.linalg.solve(np.moveaxis(J, 2, 0), -np.moveaxis(r, 1, 0)[:, :, None])[:, :, 0].T
            scale = np.minimum(1.0, 1.5 / np.maximum(np.abs(step[0]), 1e-12))
            scale = np.minimum(scale, 0.6 / np.maximum(np.abs(step[1]), 1e-12))
            scale = np.minimum(scale, 15.0 / np.maximum(np.abs(step[2]), 1e-12))
            scale = np.where(done, 0.0, scale)
            u = np.clip(u + scale * step[0], ulo, uhi)
            phi = np.clip(phi + scale * step[1], plo - thL, phi_hi - thL)
            T = np.maximum(T + scale * step[2], t_in)
            r, aux = resid(u, phi, T)
        eps, psi, power, mu, rho = aux
        ok = (np.abs(r).max(axis=0) < 1e-7) & (u > ulo + 1e-6) & (u < uhi - 1e-6) & (rho * w * R * c / mu <= b.Ret)
        pmax = np.exp(self.s_p.ev(u, psi)) * mu * w * R * R / (c * c)
        return c * (1 - eps) * 1e6, np.degrees(phi), power / 1e3, T, pmax / 1e6, ok


def geometry(brg):
    """What the dimensionless film depends on: L/R and where the grooves are."""
    return (round(brg.L / brg.R / 0.004), tuple(round(land.th[0] - land.dth, 9) for land in brg.grids[0]))


def solve_group(brg, rows, t_ins):
    """Results for the points of one bearing state at the given inlet temperatures."""
    w = np.array([float(r["speed_rpm"]) for r in rows]) * 2 * math.pi / 60.0
    load = np.array([float(r["load_N"]) for r in rows])
    thL = math.pi + np.radians([float(r["load_angle_deg"]) for r in rows])
    t = np.asarray(t_ins, float)
    out = [None] * len(rows)
    todo = np.ones(len(rows), bool)
    key = geometry(brg)
    if key in CHARTS and len(rows):
        h, att, P, T, pm, ok = CHARTS[key].solve(brg, w, load, thL, t)
        for i in np.where(ok)[0]:
            out[i] = (h[i], att[i], P[i], T[i], pm[i])
        todo = ~ok
    for i in np.where(todo)[0]:
        r = rows[i]
        out[i] = brg.point(float(r["speed_rpm"]), float(r["load_N"]), float(r["load_angle_deg"]), float(t[i]))
    return out


def main(case, out):
    sheet = json.load(open(case + "/datasheet.json"))
    history = list(csv.DictReader(open(case + "/history.csv")))
    samples = list(csv.DictReader(open(case + "/oil_samples.csv")))
    points = list(csv.DictReader(open(case + "/points.csv")))
    groups = {}
    on_date = {}
    for i, row in enumerate(points):
        if row["date"] not in on_date:
            on_date[row["date"]] = state_at(sheet, history, samples, row["date"])
        groups.setdefault(on_date[row["date"]], []).append(i)
    result = [None] * len(points)
    # a chart for every film geometry that enough points share, over the load directions those points have
    made = {state: Bearing(state) for state in groups}
    share = {}
    for state, idx in groups.items():
        share.setdefault(geometry(made[state]), []).extend(idx)
    for state, brg in made.items():
        key = geometry(brg); idx = share[key]
        if len(idx) >= CHART_FROM and key not in CHARTS:
            th = [math.pi + math.radians(float(points[i]["load_angle_deg"])) for i in idx]
            CHARTS[key] = Chart(brg, min(th), max(th))
    for state, idx in groups.items():
        brg = made[state]
        rows = [points[i] for i in idx]
        a = [reading(r["inlet_a_C"]) for r in rows]; b = [reading(r["inlet_b_C"]) for r in rows]
        drain = [reading(r["drain_C"]) for r in rows]
        # first pass: the mean where the two supply RTDs agree, else sensor a (or the only one that reads)
        first = [0.5 * (x + y) if x is not None and y is not None and abs(x - y) <= AGREE else (x if x is not None else y)
                 for x, y in zip(a, b)]
        res = solve_group(brg, rows, first)
        # second pass for the points where the RTDs disagree: sensor b, and the drain as the witness
        again = [k for k, (x, y) in enumerate(zip(a, b)) if x is not None and y is not None and abs(x - y) > AGREE]
        if again:
            res_b = solve_group(brg, [rows[k] for k in again], [b[k] for k in again])
            unsure = []
            for k, alt in zip(again, res_b):
                if drain[k] is None:
                    unsure.append(k); continue
                miss_a = abs(2.0 * res[k][3] - a[k] - drain[k]); miss_b = abs(2.0 * alt[3] - b[k] - drain[k])
                if abs(miss_a - miss_b) < CLEAR:
                    unsure.append(k)                   # the drain cannot tell them apart: they are close
                elif miss_b < miss_a:
                    res[k] = alt
            if unsure:
                mid = solve_group(brg, [rows[k] for k in unsure], [0.5 * (a[k] + b[k]) for k in unsure])
                for k, r in zip(unsure, mid):
                    res[k] = r
        for i, r in zip(idx, res):
            result[i] = r
    with open(out, "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"])
        for row, (h, att, P, T, pm) in zip(points, result):
            wr.writerow([row["point"], "%.3f" % h, "%.2f" % att, "%.4f" % P, "%.2f" % T, "%.4f" % pm])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
