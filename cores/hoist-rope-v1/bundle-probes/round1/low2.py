#!/usr/bin/env python3
"""Bending fatigue damage along crane hoist ropes to RS-4.

Usage: python3 ropes.py WORKS_DIR OUT_CSV
"""
import os
import sys
import math

import numpy as np
import pandas as pd

G = 9.80665
COEF = {
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}
NTERMS = 6  # Taylor terms for the station-dependent exponent of S


def read(path):
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()
    return df


def construction_coef(name):
    key = str(name).strip().lower().replace(" ", "").replace("×", "x")
    if key in COEF:
        return COEF[key]
    raise KeyError(name)


def crane_damage(cr, sh, mv, sv):
    n = int(cr["falls"])
    H = float(cr["upper_block_height_m"])
    mb = float(cr["block_mass_t"]) * 1000.0
    e = float(cr["reeving_efficiency"])
    L = float(cr["rope_length_m"])
    b0, b1, b2, b3 = construction_coef(cr["rope_construction"])

    # surveys: epochs in day order; per epoch diameters on the station grid
    sv = sv.dropna(subset=["day", "station_m", "diameter_mm"])
    sv = sv.sort_values(["day", "station_m"], kind="stable")
    days = np.unique(sv["day"].to_numpy(float))
    last = sv[sv["day"] == days[-1]]
    last = last.drop_duplicates("station_m", keep="last")
    stations = np.sort(last["station_m"].to_numpy(float))
    ns = len(stations)
    # diameter of each final station element at each epoch (nearest station read)
    diam = np.empty((len(days), ns))
    Lep = np.full(len(days), L)
    for i, dday in enumerate(days):
        g = sv[sv["day"] == dday].drop_duplicates("station_m", keep="last")
        st = g["station_m"].to_numpy(float)
        dd = g["diameter_mm"].to_numpy(float)
        o = np.argsort(st)
        st, dd = st[o], dd[o]
        idx = np.searchsorted(st, stations)
        idx = np.clip(idx, 1, len(st) - 1) if len(st) > 1 else np.zeros(ns, int)
        if len(st) > 1:
            left = st[idx - 1]
            right = st[idx]
            pick = np.where(np.abs(stations - left) <= np.abs(right - stations), idx - 1, idx)
        else:
            pick = idx
        diam[i] = dd[pick]
        # rope length at this survey (a shortened rope has fewer stations)
        if len(st) > 1:
            span = st[-1] + 0.5
            if abs(span - L) >= 1.0 and st[0] < 1.0:
                Lep[i] = span

    mday = mv["day"].to_numpy(float)
    h1 = mv["from_height_m"].to_numpy(float)
    h2 = mv["to_height_m"].to_numpy(float)
    mh = mv["hook_load_t"].to_numpy(float) * 1000.0
    S = (mh + mb) * G / (n * e)
    lgS = np.log10(S)
    # epoch of each movement: last survey not later than the movement
    ep = np.searchsorted(days, mday, side="right") - 1
    ep = np.clip(ep, 0, len(days) - 1)

    damage = np.zeros(ns)
    lgd_all = np.log10(diam)
    for _, s in sh.iterrows():
        p = float(s["parts"])
        a = float(s["offset_m"])
        D = float(s["diameter_mm"])
        w = float(s["bend_weight"])
        if w == 0:
            continue
        Lm = Lep[ep]
        x1 = Lm - a - p * (H - h1)
        x2 = Lm - a - p * (H - h2)
        lo = np.minimum(x1, x2)
        hi = np.maximum(x1, x2)
        # station j counted if lo <= x_j < hi  (half-open; measure-zero edge)
        i0 = np.searchsorted(stations, lo, side="left")
        i1 = np.searchsorted(stations, hi, side="left")
        ok = i1 > i0
        for k in range(len(days)):
            sel = ok & (ep == k)
            if not sel.any():
                continue
            lgd = lgd_all[k]
            r = math.log10(D) - lgd
            kj = b1 + b3 * r
            k0 = float(kj.mean())
            t_all = lgS[sel]
            s0 = float(t_all.mean())
            t = t_all - s0
            base = w * np.power(10.0, -k0 * t)
            a_lo = i0[sel]
            a_hi = i1[sel]
            dk = -(kj - k0) * math.log(10.0)
            acc = np.zeros(ns)
            tm = np.ones_like(t)
            fact = 1.0
            for m in range(NTERMS):
                v = base * tm
                diff = np.bincount(a_lo, v, ns + 1) - np.bincount(a_hi, v, ns + 1)
                Am = np.cumsum(diff)[:ns]
                acc += Am * dk ** m / fact
                tm = tm * t
                fact *= (m + 1)
            lgC = -(b0 + b2 * r) + kj * (2.0 * lgd - s0)
            damage += np.power(10.0, lgC) * acc
    return stations, damage


def main():
    wd, out = sys.argv[1], sys.argv[2]
    cranes = read(os.path.join(wd, "cranes.csv"))
    sheaves = read(os.path.join(wd, "sheaves.csv"))
    moves = read(os.path.join(wd, "movements.csv"))
    surveys = read(os.path.join(wd, "surveys.csv"))
    rows = []
    for _, cr in cranes.iterrows():
        c = cr["crane"]
        mv = moves[moves["crane"] == c]
        mv = mv.dropna(subset=["day", "from_height_m", "to_height_m", "hook_load_t"])
        st, dmg = crane_damage(cr, sheaves[sheaves["crane"] == c], mv,
                               surveys[surveys["crane"] == c])
        for j, v in enumerate(dmg):
            rows.append("%s-%03d,%.6g" % (c, j + 1, max(v, 0.0)))
    if os.path.islink(out):
        os.unlink(out)
    with open(out, "w") as f:
        f.write("row,damage\n")
        f.write("\n".join(rows))
        f.write("\n")


if __name__ == "__main__":
    main()
