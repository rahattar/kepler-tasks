"""Answers made without the laboratory, and the batches each of them gets right for free.

    python3 authoring/evidence/null_baselines.py      (writes null_baselines.txt)
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402
import solve  # noqa: E402

S = C.S


def right(temps):
    return [b for b in S.BATCHES if C.margin(b, temps[b]) >= 0]


def main():
    out = []
    rows = []
    best_one = max(range(400, 701), key=lambda T: len(right({b: T for b in S.BATCHES})))
    counts = {T: len(right({b: T for b in S.BATCHES})) for T in range(400, 701)}
    out.append("one setpoint for every batch: best %d of 13 (at %s C)" % (
        counts[best_one], ", ".join(str(T) for T, k in counts.items() if k == counts[best_one])))
    rows.append(("one setpoint for all (best, %d C)" % best_one, right({b: best_one for b in S.BATCHES})))
    per_grade = {}
    for g in S.GRADES:
        bs = [b for b in S.BATCHES if S.HEATS[S.BATCHES[b][1]][0] == g]
        T = max(range(400, 701), key=lambda T: sum(C.margin(b, T) >= 0 for b in bs))
        per_grade.update({b: T for b in bs})
    rows.append(("one setpoint per grade, chosen with the truth in hand", right(per_grade)))
    # supplier curve read as a 2 h temper of the batch itself: no soak, no double temper, no section, no tests
    rec = solve.Records(C.DATA)
    coupon = {}
    for b, r in rec.batches.items():
        g = rec.grade(r["heat"])
        mid = 0.5 * (float(r["hardness_min_HRC"]) + float(r["hardness_max_HRC"]))
        Ts = [T for T in range(int(rec.tmin[g]), 701)]
        coupon[b] = min(Ts, key=lambda T: abs(float(np.interp(T, *zip(*sorted(rec.sup[g])))) - mid))
    rows.append(("supplier curve as a 2 h temper of the part (no conversions)", right(coupon)))
    temps, lab = C.run([])
    rows.append(("supplier curves with every conversion, no tests", right(temps)))

    def undo(rec):
        rec.batches["B09"]["heat"] = "41-7731"
    temps, lab = C.run([], rec_fn=undo)
    rows.append(("the same with the batch list as it stands (B09 on 41-7731)", right(temps)))
    for name, r in rows:
        out.append("%-62s %2d of 13: %s" % (name, len(r), " ".join(r)))
    free = {b: sum(b in r for name, r in rows) for b in S.BATCHES}
    out.append("")
    out.append("free passes per batch (of the %d answers above): %s" % (len(rows), " ".join("%s %d" % kv for kv in free.items())))
    out.append("batches no answer above gets right: %s" % " ".join(b for b, k in free.items() if k == 0))
    return "\n".join(out)


if __name__ == "__main__":
    txt = main()
    print(txt)
    open(os.path.join(HERE, "null_baselines.txt"), "w").write(txt + "\n")
