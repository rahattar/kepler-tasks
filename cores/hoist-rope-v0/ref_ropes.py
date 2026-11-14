#!/usr/bin/env python3
"""Reference for the hoist-rope core: python3 ropes.py WORKS_DIR OUT_CSV
Damage is summed for the rope element now at each station. Each survey is laid against the one before it, as
listed and end for end; where the rope has been turned between two surveys the element is followed to the
place it had before. TRUST_LOG=1 takes every survey as listed."""
import csv, os, sys
import numpy as np

G = 9.80665
ROPE = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}
TRUST = os.environ.get("TRUST_LOG") == "1"


def rd(d, n):
    return list(csv.DictReader(open(os.path.join(d, n))))


def main(wd, out_csv):
    cranes = rd(wd, "cranes.csv")
    sheaves = {}
    for r in rd(wd, "sheaves.csv"):
        sheaves.setdefault(r["crane"], []).append((int(r["parts"]), float(r["offset_m"]), float(r["diameter_mm"]), float(r["bend_weight"])))
    mv = {}
    for r in rd(wd, "movements.csv"):
        mv.setdefault(r["crane"], []).append((float(r["day"]), float(r["from_height_m"]), float(r["to_height_m"]), float(r["hook_load_t"])))
    sv = {}
    for r in rd(wd, "surveys.csv"):
        sv.setdefault(r["crane"], {}).setdefault(float(r["day"]), []).append((float(r["station_m"]), float(r["diameter_mm"])))
    rows = []
    for c in cranes:
        name = c["crane"]; L = float(c["rope_length_m"]); n = int(c["falls"]); H = float(c["upper_block_height_m"])
        b0, b1, b2, b3 = ROPE[c["rope_construction"]]
        days = sorted(sv[name]); K = len(days)
        prof = [np.array([d for _, d in sorted(sv[name][t])]) for t in days]
        x = np.array([s for s, _ in sorted(sv[name][days[-1]])]); ns = x.size
        flip = [False] * (K - 1)
        if not TRUST:
            for k in range(K - 1):
                same = np.sum((prof[k + 1] - prof[k]) ** 2); mir = np.sum((prof[k + 1] - prof[k][::-1]) ** 2)
                flip[k] = mir < 0.5 * same
        o = [0] * K
        for k in range(K - 2, -1, -1):
            o[k] = o[k + 1] ^ int(flip[k])
        m = np.array(mv[name]); t, h1, h2, ld = m.T
        S = (ld + float(c["block_mass_t"])) * 1e3 * G / (n * float(c["reeving_efficiency"]))
        lo = np.minimum(h1, h2); hi = np.maximum(h1, h2)
        D = np.zeros(ns)
        for k in range(K):
            t0 = days[k]; t1 = days[k + 1] if k + 1 < K else np.inf
            parts = [(t0, t1, o[k])]
            if k + 1 < K and flip[k]:
                mid = 0.5 * (t0 + t1)
                parts = [(t0, mid, o[k]), (mid, t1, o[k + 1])]
            dia = prof[k] if o[k] == 0 else prof[k][::-1]          # diameter of each element at this survey
            for ta, tb, oo in parts:
                sel = (t >= ta) & (t < tb)
                if not sel.any():
                    continue
                xp = x if oo == 0 else L - x
                for j, off, Ds, w in sheaves[name]:
                    hc = H - (L - off - xp) / j
                    cross = (lo[sel][:, None] < hc[None, :]) & (hc[None, :] <= hi[sel][:, None])
                    r = np.log10(Ds / dia)[None, :]
                    N = 10.0 ** (b0 + (b1 + b3 * r) * np.log10(S[sel][:, None] / dia[None, :] ** 2) + b2 * r)
                    D += w * (cross / N).sum(0)
        if os.environ.get("VERBOSE"):
            print(name, "turned between surveys:", [(days[k], days[k + 1]) for k in range(K - 1) if flip[k]], file=sys.stderr)
        rows += [["%s-%03d" % (name, i + 1), "%.6f" % D[i]] for i in range(ns)]
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["row", "damage"]); w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
