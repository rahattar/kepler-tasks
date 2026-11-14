#!/usr/bin/env python3
"""Reference for the hoist-rope core v1: python3 ropes.py WORKS_DIR OUT_CSV
Damage is summed for the rope element that lies at each station at the end of the log.

Each survey is laid against the one before it, as listed and end for end. Where a survey is the mirror of the
one before, either the rope was turned end for end between the two, or the stations were counted from the
other end. The two are told apart by where the rope goes on thinning: bendings fall where the reeving puts
them, so in every run of surveys between two mirrorings the loss of diameter is laid against the bendings of
the same days, as listed and mirrored. A run that fits mirrored was counted from the dead end.

MODE=listed takes every survey as listed; MODE=allturn takes every mirroring for a turn; MODE=allwrong takes
every mirroring for a change of the end the stations are counted from."""
import csv, os, sys
import numpy as np

G = 9.80665
ROPE = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}
MODE = os.environ.get("MODE", "ref")


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
        m = np.array(mv[name]); t, h1, h2, ld = m.T
        S = (ld + float(c["block_mass_t"])) * 1e3 * G / (n * float(c["reeving_efficiency"]))
        lo = np.minimum(h1, h2); hi = np.maximum(h1, h2)

        def bend(sel, xp, dia):
            """Damage laid in the movements sel on the elements at the places xp, of diameters dia."""
            out = np.zeros(ns)
            if not sel.any():
                return out
            for j, off, Ds, w in sheaves[name]:
                hc = H - (L - off - xp) / j
                cross = (lo[sel][:, None] < hc[None, :]) & (hc[None, :] <= hi[sel][:, None])
                r = np.log10(Ds / dia)[None, :]
                N = 10.0 ** (b0 + (b1 + b3 * r) * np.log10(S[sel][:, None] / dia[None, :] ** 2) + b2 * r)
                out += w * (cross / N).sum(0)
            return out

        flip = [False] * (K - 1)
        if MODE != "listed":
            for k in range(K - 1):
                same = np.sum((prof[k + 1] - prof[k]) ** 2); mir = np.sum((prof[k + 1] - prof[k][::-1]) ** 2)
                flip[k] = mir < 0.5 * same
        # runs of surveys between mirrorings, and for each the end its stations were counted from
        runs = []; a = 0
        for k in range(K - 1):
            if flip[k]:
                runs.append((a, k)); a = k + 1
        runs.append((a, K - 1))
        cnt = [0] * K                      # 1: stations counted from the dead end
        prev = 0; note = []
        for i, (ka, kb) in enumerate(runs):
            ce = prev
            if MODE == "allwrong":
                ce = i % 2
            elif MODE == "ref" and len(runs) > 1 and kb > ka:
                loss = prof[ka] - prof[kb]
                A = bend((t >= days[ka]) & (t < days[kb]), x, np.full(ns, float(np.median(prof[0]))))
                if A.std() > 0 and loss.std() > 0:
                    ra = np.corrcoef(loss, A)[0, 1]; rm = np.corrcoef(loss, A[::-1])[0, 1]
                    ce = int(rm > ra); note.append((days[ka], days[kb], round(float(ra), 2), round(float(rm), 2)))
            for k in range(ka, kb + 1):
                cnt[k] = ce
            prev = ce
        turn = [flip[k] and cnt[k] == cnt[k + 1] for k in range(K - 1)]
        o = [0] * K                        # 1: the rope lay the other way round than at the end
        for k in range(K - 2, -1, -1):
            o[k] = o[k + 1] ^ int(turn[k])
        D = np.zeros(ns)
        for k in range(K):
            t0 = days[k]; t1 = days[k + 1] if k + 1 < K else np.inf
            parts = [(t0, t1, o[k])]
            if k + 1 < K and turn[k]:
                mid = 0.5 * (t0 + t1)
                parts = [(t0, mid, o[k]), (mid, t1, o[k + 1])]
            dia = prof[k][::-1] if (o[k] ^ cnt[k]) else prof[k]     # diameter of each element at this survey
            for ta, tb, oo in parts:
                D += bend((t >= ta) & (t < tb), x if oo == 0 else L - x, dia)
        if os.environ.get("VERBOSE"):
            print(name, "turned:", [(days[k], days[k + 1]) for k in range(K - 1) if turn[k]],
                  "counted from the dead end:", [days[k] for k in range(K) if cnt[k]][:1], note, file=sys.stderr)
        rows += [["%s-%03d" % (name, i + 1), "%.6f" % D[i]] for i in range(ns)]
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["row", "damage"]); w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
