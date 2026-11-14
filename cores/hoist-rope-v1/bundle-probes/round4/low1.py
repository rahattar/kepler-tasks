#!/usr/bin/env python3
"""RS-4 bending damage along hoist ropes, for one works package.

Usage: python3 ropes.py WORKS_DIR OUT_CSV
"""
import os
import sys
import math
import numpy as np
import pandas as pd

G = 9.80665
COEF = {"8x36": (-1.214, 0.887, 7.432, -2.103),
        "6x36": (-1.371, 0.934, 7.518, -2.146)}
NTERMS = 6  # Taylor terms for the station-wise variation of the exponent


def crane_damage(cr, shv, mv, sv):
    n = int(cr.falls)
    H = float(cr.upper_block_height_m)
    L = float(cr.rope_length_m)
    b0, b1, b2, b3 = COEF[str(cr.rope_construction).strip()]

    # surveys: days and diameter matrix (survey x station)
    sv = sv.sort_values(["day", "station_m"])
    sdays = np.unique(sv.day.values)
    last = sv[sv.day == sdays[-1]]
    st_x = np.sort(last.station_m.values.astype(float))
    K = len(st_x)
    dmat = np.empty((len(sdays), K))
    for i, dday in enumerate(sdays):
        g = sv[sv.day == dday]
        dmat[i] = np.interp(st_x, g.station_m.values, g.diameter_mm.values)

    dmg = np.zeros(K)
    if len(mv) == 0:
        return st_x, dmg
    day = mv.day.values.astype(float)
    h1 = mv.from_height_m.values.astype(float)
    h2 = mv.to_height_m.values.astype(float)
    m = mv.hook_load_t.values.astype(float)
    S = (m + float(cr.block_mass_t)) * 1000.0 * G / (n * float(cr.reeving_efficiency))
    lnS = np.log(S)
    # survey in force: last survey with day <= movement day (first survey if none)
    per = np.searchsorted(sdays, day, side="right") - 1
    per = np.clip(per, 0, len(sdays) - 1)
    lo_h = np.minimum(h1, h2)
    hi_h = np.maximum(h1, h2)
    moving = hi_h > lo_h

    # station positions sorted ascending; grid assumed sorted (uses searchsorted)
    for s in shv.itertuples(index=False):
        p = float(s.parts)
        a = float(s.offset_m)
        D = float(s.diameter_mm)
        w = float(s.bend_weight)
        # x = L - a - p (H - h); larger h -> larger x
        xlo = L - a - p * (H - lo_h)
        xhi = L - a - p * (H - hi_h)
        i0 = np.searchsorted(st_x, xlo, side="left")
        i1 = np.searchsorted(st_x, xhi, side="right")  # exclusive
        ok = moving & (i1 > i0)
        for k in range(len(sdays)):
            sel = ok & (per == k)
            if not sel.any():
                continue
            d = dmat[k]
            lgd = np.log10(d)
            gk = math.log10(D) - lgd
            Bk = b1 + b3 * gk                       # per station exponent
            Ak = b0 + b2 * gk                       # per station constant
            B0 = float(np.mean(Bk))
            delta = Bk - B0
            ls = lnS[sel]
            c = float(np.mean(ls))
            u = ls - c
            base = np.exp(-B0 * ls)
            a0 = i0[sel]
            a1 = i1[sel]
            # per-station factor: w * 10^-A * d^(2B) * S^-B0 * exp(-delta*u) * exp(-delta*c)
            fac = w * np.power(10.0, -Ak + 2.0 * Bk * lgd) * np.exp(-delta * c)
            acc = np.zeros(K)
            term = base.copy()
            coef = np.ones(K)
            for j in range(NTERMS):
                diff = np.bincount(a0, weights=term, minlength=K + 1) \
                    - np.bincount(a1, weights=term, minlength=K + 1)
                cov = np.cumsum(diff)[:K]
                acc += coef * cov
                term = term * u
                coef = coef * (-delta) / (j + 1)
            dmg += fac * acc
    return st_x, dmg


def main():
    wd, out = sys.argv[1], sys.argv[2]
    cr = pd.read_csv(os.path.join(wd, "cranes.csv"), skipinitialspace=True)
    sh = pd.read_csv(os.path.join(wd, "sheaves.csv"), skipinitialspace=True)
    mv = pd.read_csv(os.path.join(wd, "movements.csv"), skipinitialspace=True,
                     dtype={"crane": str})
    sv = pd.read_csv(os.path.join(wd, "surveys.csv"), skipinitialspace=True,
                     dtype={"crane": str})
    for df in (cr, sh, mv, sv):
        df["crane"] = df["crane"].astype(str).str.strip()
    mvg = dict(tuple(mv.groupby("crane", sort=False)))
    svg = dict(tuple(sv.groupby("crane", sort=False)))
    lines = ["row,damage"]
    for c in cr.itertuples(index=False):
        name = c.crane
        if name not in svg:
            continue
        m = mvg.get(name, mv.iloc[0:0])
        m = m.sort_values("day", kind="stable")
        st_x, dmg = crane_damage(c, sh[sh.crane == name], m, svg[name])
        width = max(3, len(str(len(st_x))))
        for i, v in enumerate(dmg):
            lines.append("%s-%0*d,%.6g" % (name, width, i + 1, v))
    if os.path.islink(out):
        os.unlink(out)
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
