#!/usr/bin/env python3
"""TS-2 heated oil transfer line calculation for one site package.

Usage: python3 lines.py PACKAGE_DIR OUT_CSV
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

NSTEP = 48          # axial steps per pipe (cubic clustering at the inlet)
NFP = 3             # fixed-point passes for the wall temperature
GRID = 121          # split-fraction grid for pairs
COVER_WORDS = ("covering", "lagging", "insulation", "cladding", "jacket", "sheathing")


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- oil
class Oil:
    def __init__(self, row):
        self.rho = float(row["density_kg_m3"])
        self.cp = float(row["cp_J_kgK"])
        self.k = float(row["k_W_mK"])
        T1, T2 = 323.15, 373.15
        y1 = np.log10(np.log10(float(row["nu50_cSt"]) + 0.7))
        y2 = np.log10(np.log10(float(row["nu100_cSt"]) + 0.7))
        self.B = (y1 - y2) / (np.log10(T2) - np.log10(T1))
        self.A = y1 + self.B * np.log10(T1)

    def nu(self, Tc):
        """kinematic viscosity m2/s at Tc (deg C)"""
        T = Tc + 273.15
        return (10.0 ** (10.0 ** (self.A - self.B * np.log10(T))) - 0.7) * 1e-6


# ---------------------------------------------------------------- one pipe
_s = (np.arange(NSTEP + 1) / NSTEP) ** 3
_SM = ((np.arange(NSTEP) + 0.5) / NSTEP) ** 3


def pipe(oil, D, L, Uo, m, Tin, Ta):
    """Vectorised integration of TS-2 section 3.
    All of Uo, m, Tin, Ta broadcast together. Returns (dp Pa, Tout C)."""
    m, Uo, Tin, Ta = np.broadcast_arrays(np.asarray(m, float), np.asarray(Uo, float),
                                         np.asarray(Tin, float), np.asarray(Ta, float))
    rho, cp, k = oil.rho, oil.cp, oil.k
    A = np.pi * D * D / 4
    u = m / (rho * A)
    piD = np.pi * D
    cG = 4 * m * cp / (np.pi * k)       # Gz * x  (Re Pr D = 4 m cp /(pi k))

    def rates(x, Tb, Tw0):
        nub = oil.nu(Tb)
        mub = rho * nub
        Gz = cG / x
        base = (3.66 ** 3 + 0.7 ** 3 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1 / 3)
        hb = base * k / D
        Tw = Tw0
        for _ in range(NFP):
            muw = rho * oil.nu(Tw)
            h = hb * (mub / muw) ** 0.14
            Tw = (h * Tb + Uo * Ta) / (h + Uo)
        muw = rho * oil.nu(Tw)
        h = hb * (mub / muw) ** 0.14
        Ue = h * Uo / (h + Uo)
        kdec = piD * Ue / (m * cp)
        gp = 32 * mub * u / (D * D) * np.sqrt(muw / mub)
        return kdec, gp, Tw

    Tb = Tin.copy()
    Tw = 0.5 * (Tin + Ta)
    dp = np.zeros_like(Tb)
    for i in range(NSTEP):
        xa, xb = L * _s[i], L * _s[i + 1]
        dx = xb - xa
        xm = L * _SM[i]
        # predictor to the step midpoint
        kd, _, Tw = rates(xa if i > 0 else xm, Tb, Tw)
        Tm = Ta + (Tb - Ta) * np.exp(-kd * (xm - xa))
        kd, gp, Tw = rates(xm, Tm, Tw)
        Tb = Ta + (Tb - Ta) * np.exp(-kd * dx)
        dp += gp * dx
    return dp, Tb


# ---------------------------------------------------------------- Uo from survey
def fit_uo(oil, D, L, m, Tin, Tout, Ta):
    m, Tin, Tout, Ta = map(lambda a: np.asarray(a, float), (m, Tin, Tout, Ta))
    lo = np.full(m.shape, -12.0)
    hi = np.full(m.shape, 6.0)   # log Uo bounds
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        _, T = pipe(oil, D, L, np.exp(mid), m, Tin, Ta)
        big = T < Tout          # too much loss -> Uo too big
        hi = np.where(big, mid, hi)
        lo = np.where(big, lo, mid)
    return np.exp(0.5 * (lo + hi))


# ---------------------------------------------------------------- main
def main():
    pkg, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, "site.json")))
    allowance = int(site.get("survey_allowance", 0))
    oils = {r["oil"]: Oil(r) for r in read_csv(os.path.join(pkg, "oils.csv"))}
    lines = read_csv(os.path.join(pkg, "lines.csv"))
    surveys = read_csv(os.path.join(pkg, "surveys.csv"))
    work = read_csv(os.path.join(pkg, "work_log.csv"))
    records = read_csv(os.path.join(pkg, "records.csv"))

    linfo = {}
    pipe_line = {}
    for r in lines:
        n = int(r["pipes"])
        names = [r["line"] + "-A"] + ([r["line"] + "-B"] if n == 2 else [])
        linfo[r["line"]] = dict(n=n, D=float(r["bore_mm"]) / 1000, L=float(r["length_m"]),
                                oil=oils[r["oil"]], pipes=names)
        for p in names:
            pipe_line[p] = r["line"]

    # last covering work per pipe
    lastwork = {}
    for w in work:
        if any(k in w["job"].lower() for k in COVER_WORDS):
            p = w["pipe"]
            lastwork[p] = max(lastwork.get(p, ""), w["date"])
    # valid surveys: after the last covering work
    valid = {}
    latest_any = {}
    for s in surveys:
        p = s["pipe"]
        if p not in pipe_line:
            continue
        if latest_any.get(p) is None or s["date"] > latest_any[p]["date"]:
            latest_any[p] = s
        if s["date"] > lastwork.get(p, ""):
            if valid.get(p) is None or s["date"] > valid[p]["date"]:
                valid[p] = s

    # records grouped by line
    recs_by_line = {}
    for i, r in enumerate(records):
        recs_by_line.setdefault(r["line"], []).append(i)
    need = [p for p in pipe_line if p not in valid]
    # priority: pipes carrying the most records first
    need.sort(key=lambda p: -len(recs_by_line.get(pipe_line[p], [])))
    order = need[:allowance]
    if order:
        try:
            res = subprocess.run(["heatsurvey", pkg] + order, capture_output=True,
                                 text=True, timeout=30)
            rows = list(csv.DictReader(res.stdout.strip().splitlines()))
            for row in rows:
                if row.get("pipe") in pipe_line:
                    row["date"] = "9999-99-99"
                    valid[row["pipe"]] = row
        except Exception as e:  # noqa
            sys.stderr.write("heatsurvey failed: %r\n" % (e,))
    for p in pipe_line:
        if p not in valid:
            sys.stderr.write("no valid survey for %s, using latest on file\n" % p)
            if p in latest_any:
                valid[p] = latest_any[p]

    # fit Uo for every pipe, grouped per line
    Uo = {}
    for ln, li in linfo.items():
        ps = [p for p in li["pipes"] if p in valid]
        if not ps:
            continue
        sv = [valid[p] for p in ps]
        u = fit_uo(li["oil"], li["D"], li["L"],
                   [float(s["flow_t_h"]) / 3.6 for s in sv],
                   [float(s["t_in_C"]) for s in sv],
                   [float(s["t_out_C"]) for s in sv],
                   [float(s["t_amb_C"]) for s in sv])
        for p, x in zip(ps, u):
            Uo[p] = float(x)
    for ln, li in linfo.items():   # fallback: twin's value
        for p in li["pipes"]:
            if p not in Uo:
                other = [q for q in li["pipes"] if q in Uo]
                Uo[p] = Uo[other[0]] if other else 1.0

    dp_out = np.zeros(len(records))
    t_out = np.zeros(len(records))
    sgrid = 0.5 - 0.5 * np.cos(np.pi * np.linspace(0, 1, GRID + 2)[1:-1])  # symmetric

    for ln, idx in recs_by_line.items():
        li = linfo[ln]
        idx = sorted(idx, key=lambda i: float(records[i]["hour"]))
        M = np.array([float(records[i]["flow_t_h"]) / 3.6 for i in idx])
        Ti = np.array([float(records[i]["t_in_C"]) for i in idx])
        Ta = np.array([float(records[i]["t_amb_C"]) for i in idx])
        oil, D, L = li["oil"], li["D"], li["L"]
        if li["n"] == 1:
            dp, T = pipe(oil, D, L, Uo[li["pipes"][0]], M, Ti, Ta)
            dp_out[idx] = dp / 1000
            t_out[idx] = T
            continue
        ua, ub = Uo[li["pipes"][0]], Uo[li["pipes"][1]]
        mm = M[:, None] * sgrid[None, :]
        dA, _ = pipe(oil, D, L, ua, mm, Ti[:, None], Ta[:, None])
        dB, _ = pipe(oil, D, L, ub, mm, Ti[:, None], Ta[:, None])
        G = dA - dB[:, ::-1]          # g(s) = dpA(sM) - dpB((1-s)M)
        brackets = []
        sprev = None
        for j in range(len(idx)):
            g = G[j]
            sc = np.nonzero(np.sign(g[:-1]) != np.sign(g[1:]))[0]
            if len(sc) == 0:
                b = 0 if abs(g[0]) < abs(g[-1]) else GRID - 2
            elif sprev is None:
                # unique division at the opening record (4.3); if several, take the
                # one with the steepest crossing
                b = sc[0] if len(sc) == 1 else sc[np.argmax(np.abs(g[sc + 1] - g[sc]))]
            else:
                gp = np.interp(sprev, sgrid, g)
                if gp > 0:   # A higher: oil moves from A to B, s decreases
                    cand = [c for c in sc if sgrid[c] <= sprev]
                    b = max(cand) if cand else min(sc)
                else:
                    cand = [c for c in sc if sgrid[c + 1] >= sprev]
                    b = min(cand) if cand else max(sc)
            s0, s1 = sgrid[b], sgrid[b + 1]
            g0, g1 = g[b], g[b + 1]
            sprev = s0 - g0 * (s1 - s0) / (g1 - g0) if g1 != g0 else 0.5 * (s0 + s1)
            brackets.append((s0, s1, g0, g1))
        # refine all roots of this line with Illinois regula falsi
        a = np.array([b[0] for b in brackets]); c = np.array([b[1] for b in brackets])
        fa = np.array([b[2] for b in brackets]); fc = np.array([b[3] for b in brackets])
        for _ in range(8):
            with np.errstate(all="ignore"):
                s = np.where(fc != fa, a - fa * (c - a) / (fc - fa), 0.5 * (a + c))
            s = np.clip(s, np.minimum(a, c), np.maximum(a, c))
            pa, _ = pipe(oil, D, L, ua, s * M, Ti, Ta)
            pb, _ = pipe(oil, D, L, ub, (1 - s) * M, Ti, Ta)
            f = pa - pb
            sw = np.sign(f) != np.sign(fc)
            a, fa = np.where(sw, c, a), np.where(sw, fc, 0.5 * fa)
            c, fc = s, f
        s = np.where(np.abs(fa) < np.abs(fc), a, c)
        pa, TA = pipe(oil, D, L, ua, s * M, Ti, Ta)
        pb, TB = pipe(oil, D, L, ub, (1 - s) * M, Ti, Ta)
        dp_out[idx] = 0.5 * (pa + pb) / 1000
        t_out[idx] = s * TA + (1 - s) * TB

    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record", "dp_kPa", "t_out_C"])
        for i, r in enumerate(records):
            w.writerow([r["record"], "%.3f" % dp_out[i], "%.3f" % t_out[i]])


if __name__ == "__main__":
    main()
