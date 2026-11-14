import sys, os
import numpy as np
import pandas as pd

G = 9.80665
COEF = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}


def main(wd, out):
    rd = lambda f: pd.read_csv(os.path.join(wd, f), skipinitialspace=True)
    cr, sh, mv, sv = rd("cranes.csv"), rd("sheaves.csv"), rd("movements.csv"), rd("surveys.csv")
    for df in (cr, sh, mv, sv):
        df["crane"] = df["crane"].astype(str).str.strip()
    rows = []
    for _, c in cr.iterrows():
        name = c["crane"]
        n, H, L, e = float(c["falls"]), float(c["upper_block_height_m"]), float(c["rope_length_m"]), float(c["reeving_efficiency"])
        b0, b1, b2, b3 = COEF[str(c["rope_construction"]).strip()]
        m = mv[mv.crane == name].sort_values("day", kind="stable")
        s = sv[sv.crane == name]
        sdays = np.sort(s["day"].unique())
        last = s[s.day == sdays[-1]].sort_values("station_m")
        st = last["station_m"].to_numpy(float)
        # diameter table: survey x station (by nearest matching station)
        dtab = np.empty((len(sdays), len(st)))
        for i, dd in enumerate(sdays):
            ss = s[s.day == dd].sort_values("station_m")
            dtab[i] = np.interp(st, ss["station_m"].to_numpy(float), ss["diameter_mm"].to_numpy(float))
        dmg = np.zeros(len(st))
        if len(m):
            day = m["day"].to_numpy(float)
            h0 = m["from_height_m"].to_numpy(float); h1 = m["to_height_m"].to_numpy(float)
            S = (m["hook_load_t"].to_numpy(float) * 1000 + float(c["block_mass_t"]) * 1000) * G / (n * e)
            idx = np.searchsorted(sdays, day, side="right") - 1
            idx = np.clip(idx, 0, len(sdays) - 1)
            d = dtab[idx]                       # movements x stations
            lgS = np.log10(S)[:, None] - 2 * np.log10(d)
            for _, k in sh[sh.crane == name].iterrows():
                p, a, D, w = float(k["parts"]), float(k["offset_m"]), float(k["diameter_mm"]), float(k["bend_weight"])
                x0 = L - a - p * (H - h0); x1 = L - a - p * (H - h1)
                lo = np.minimum(x0, x1)[:, None]; hi = np.maximum(x0, x1)[:, None]
                hit = (st[None, :] >= lo) & (st[None, :] <= hi) & (hi > lo)
                lr = np.log10(D) - np.log10(d)
                lgN = b0 + (b1 + b3 * lr) * lgS + b2 * lr
                dmg += w * np.where(hit, 10.0 ** (-lgN), 0.0).sum(axis=0)
        for i, v in enumerate(dmg):
            rows.append((f"{name}-{i+1:03d}", v))
    pd.DataFrame(rows, columns=["row", "damage"]).to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
