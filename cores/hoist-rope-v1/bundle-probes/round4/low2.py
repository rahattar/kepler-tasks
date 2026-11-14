#!/usr/bin/env python3
"""RS-4 bending damage along hoist ropes for one works package.

Usage: python3 ropes.py WORKS_DIR OUT_CSV
"""
import os
import sys

import numpy as np
import pandas as pd

G = 9.80665
COEF = {
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}


def crane_damage(cr, sh, mv, sv):
    n = int(cr["falls"])
    H = float(cr["upper_block_height_m"])
    L = float(cr["rope_length_m"])
    mb = float(cr["block_mass_t"])
    e = float(cr["reeving_efficiency"])
    b0, b1, b2, b3 = COEF[str(cr["rope_construction"]).strip()]

    sv = sv.sort_values(["day", "station_m"], kind="stable")
    sdays = np.unique(sv["day"].to_numpy(float))
    last = sv[sv["day"] == sdays[-1]]
    xs = last["station_m"].to_numpy(float)          # result stations
    order = np.argsort(xs, kind="stable")
    xs = xs[order]
    # diameter at the result stations for every survey
    dia = np.empty((len(sdays), len(xs)))
    for i, dday in enumerate(sdays):
        g = sv[sv["day"] == dday]
        gx = g["station_m"].to_numpy(float)
        gd = g["diameter_mm"].to_numpy(float)
        o = np.argsort(gx)
        dia[i] = np.interp(xs, gx[o], gd[o])

    mv = mv.sort_values("day", kind="stable")
    day = mv["day"].to_numpy(float)
    h0 = mv["from_height_m"].to_numpy(float)
    h1 = mv["to_height_m"].to_numpy(float)
    S = (mv["hook_load_t"].to_numpy(float) * 1000.0 + mb * 1000.0) * G / (n * e)
    S = np.maximum(S, 1e-9)
    lnS = np.log(S)
    # survey in force: last survey not later than the movement
    seg = np.searchsorted(sdays, day, side="right") - 1
    seg = np.clip(seg, 0, len(sdays) - 1)
    nseg = len(sdays)
    nx = len(xs)

    dmg = np.zeros(nx)
    hlo = np.minimum(h0, h1)
    hhi = np.maximum(h0, h1)
    for _, s in sh.iterrows():
        p = float(s["parts"])
        a = float(s["offset_m"])
        D = float(s["diameter_mm"])
        w = float(s["bend_weight"])
        if w == 0:
            continue
        # x of touch point; x increases with h
        xlo = L - a - p * (H - hlo)
        xhi = L - a - p * (H - hhi)
        lr = np.log10(D)
        # per survey, per station: 1/N = 10^-(b0+b2 lg(D/d)) * (S/d^2)^-(b1+b3 lg(D/d))
        lgd = np.log10(dia)                       # (nseg, nx)
        lgr = lr - lgd
        k = b1 + b3 * lgr                         # (nseg, nx)
        i_lo = np.searchsorted(xs, xlo, side="left")    # first station >= xlo
        i_hi = np.searchsorted(xs, xhi, side="right")   # past last station <= xhi
        valid = i_hi > i_lo
        for sg in range(nseg):
            msk = valid & (seg == sg)
            if not msk.any():
                continue
            il = i_lo[msk]
            ih = i_hi[msk]
            ls = lnS[msk]
            # For each station j, the sum of S^-k[j] over the movements that
            # cover it: exact per distinct k when there are few, else a Taylor
            # series in k, each term summed with difference arrays.
            kk = k[sg]
            pref = 10.0 ** (-(b0 + b2 * lgr[sg])) * (dia[sg] ** 2) ** kk * w
            kv, inv = np.unique(kk, return_inverse=True)

            def cover(vals):
                c = np.bincount(il, vals, nx + 1) - np.bincount(ih, vals, nx + 1)
                return np.cumsum(c)[:nx]

            u0 = 0.5 * (ls.max() + ls.min())
            u = ls - u0
            k0 = 0.5 * (kv.max() + kv.min())
            dk = kv - k0
            x = float(np.abs(dk).max() * np.abs(u).max())
            # terms needed for Taylor series of exp(-dk*u) to 1e-10 relative
            nt, t, f = 1, 1.0, 1.0
            while t * np.exp(x) > 1e-10 and nt < 60:
                t *= x / nt
                nt += 1
            if len(kv) <= nt:
                tot = np.empty(nx)
                for i, kq in enumerate(kv):
                    sel = inv == i
                    tot[sel] = cover(np.exp(-kq * ls))[sel]
            else:
                base = np.exp(-k0 * ls)
                kdk = (kk - k0)
                tot = np.zeros(nx)
                coef = np.ones(nx)
                term = base
                for ti in range(nt):
                    tot += coef * cover(term)
                    term = term * u
                    coef = coef * (-kdk) / (ti + 1)
                tot *= np.exp(-kdk * u0)
            dmg += pref * tot
    return xs, dmg


def main():
    wd, out = sys.argv[1], sys.argv[2]
    cr = pd.read_csv(os.path.join(wd, "cranes.csv"), skipinitialspace=True)
    sh = pd.read_csv(os.path.join(wd, "sheaves.csv"), skipinitialspace=True)
    mv = pd.read_csv(os.path.join(wd, "movements.csv"), skipinitialspace=True)
    sv = pd.read_csv(os.path.join(wd, "surveys.csv"), skipinitialspace=True)
    for df in (cr, sh, mv, sv):
        df.columns = [c.strip() for c in df.columns]
        cs = df["crane"].astype(str)
        uq = pd.unique(cs)
        df["crane"] = cs.map({q: q.strip() for q in uq}) if any(q != q.strip() for q in uq) else cs
    lines = ["row,damage"]
    for _, c in cr.iterrows():
        name = c["crane"]
        xs, dmg = crane_damage(c, sh[sh.crane == name], mv[mv.crane == name], sv[sv.crane == name])
        for j, v in enumerate(dmg):
            lines.append("%s-%03d,%.8g" % (name, j + 1, v))
    if os.path.islink(out):
        os.unlink(out)
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
