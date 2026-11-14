"""Sheets made without the calculation, each written by a complete program and judged by the verifier's bench.

    python3 null_run.py > null_run.txt

  nothing      every damage 0
  flat         every station of a rope gets the mean damage of the examples' stations
  shape        every station gets the examples' mean damage at the same share of the rope's length
  thinning     the damage is read off the last survey alone: the loss of diameter since the first survey, turned
               into damage by the power law that fits the two examples best (one law for all ropes)
  thinning_fit the same, with the law's scale set rope by rope so that the rope's summed damage is what RS-4
               gives when every survey is taken as written (a turn moves damage along a rope, it does not make any)

None may be accepted, and the count of rows each gets right is the floor against which a row is worth something.
"""
import csv
import os
import sys

import numpy as np

import common
import variants

HEAD = '''import csv, os, sys
import numpy as np
works_dir, out_csv = sys.argv[1], sys.argv[2]
surveys = {}
for row in csv.DictReader(open(os.path.join(works_dir, "surveys.csv"))):
    surveys.setdefault(row["crane"], {}).setdefault(float(row["day"]), []).append((float(row["station_m"]), float(row["diameter_mm"])))
lines = ["row,damage"]
for crane, by_day in surveys.items():
    days = sorted(by_day)
    first = np.array([d for _, d in sorted(by_day[days[0]])]); last = np.array([d for _, d in sorted(by_day[days[-1]])])
    n = last.size; share = (np.arange(n) + 0.5) / n
'''
TAIL = '''
    lines += ["%s-%03d,%.6f" % (crane, i + 1, v) for i, v in enumerate(damage)]
open(out_csv, "w").write("\\n".join(lines) + "\\n")
'''


def examples():
    """(share of length, damage, relative loss of diameter) over every station of the two examples."""
    share, damage, loss = [], [], []
    for name in sorted(os.listdir(os.path.join(common.DATA, "examples"))):
        folder = os.path.join(common.DATA, "examples", name)
        want = {r["row"]: float(r["damage"]) for r in csv.DictReader(open(os.path.join(folder, "expected.csv")))}
        by = {}
        for r in csv.DictReader(open(os.path.join(folder, "surveys.csv"))):
            by.setdefault(r["crane"], {}).setdefault(float(r["day"]), []).append((float(r["station_m"]), float(r["diameter_mm"])))
        for crane, by_day in by.items():
            days = sorted(by_day)
            first = np.array([d for _, d in sorted(by_day[days[0]])])
            last = np.array([d for _, d in sorted(by_day[days[-1]])])
            n = last.size
            share += list((np.arange(n) + 0.5) / n)
            damage += [want["%s-%03d" % (crane, i + 1)] for i in range(n)]
            loss += list((first - last) / first)
    return np.array(share), np.array(damage), np.array(loss)


def main():
    share, damage, loss = examples()
    mean = float(damage.mean())
    grid = np.linspace(0, 1, 41)
    shape = [float(damage[(share >= a) & (share < b)].mean()) for a, b in zip(grid[:-1], grid[1:])]
    # damage = scale * (loss - floor)^power on the examples, by least squares in logarithms over worn stations
    floor = float(np.percentile(loss, 5))
    worn = (loss - floor > 0.004) & (damage > 0)
    power, log_scale = np.polyfit(np.log(loss[worn] - floor), np.log(damage[worn]), 1)
    law = "np.where(lost > 0.0, %r * np.maximum(lost, 1e-12) ** %r, 0.0)" % (float(np.exp(log_scale)), float(power))
    with open(common.REFERENCE) as handle:
        reference = handle.read()
    as_written = variants.make([(variants.MIRROR_TEST, "        changed.append(False)\n")])
    with open(as_written) as handle:
        listed = handle.read().replace('if __name__ == "__main__":\n    main(sys.argv[1], sys.argv[2])\n', "")
    programs = {
        "nothing": HEAD + "    damage = np.zeros(n)" + TAIL,
        "flat": HEAD + "    damage = np.full(n, %r)" % mean + TAIL,
        "shape": HEAD + "    damage = np.array(%r)[np.minimum((share * 40).astype(int), 39)]" % shape + TAIL,
        "thinning": HEAD + "    lost = (first - last) / first - %r\n    damage = %s" % (floor, law) + TAIL,
    }
    # thinning_fit: the as-written calculation gives each rope's summed damage; the last survey gives its shape
    programs["thinning_fit"] = listed + '''

def _fit(works_dir, out_csv):
    main(works_dir, out_csv + ".listed")
    total = {}
    for row in csv.DictReader(open(out_csv + ".listed")):
        crane = row["row"].rsplit("-", 1)[0]
        total[crane] = total.get(crane, 0.0) + float(row["damage"])
    os.remove(out_csv + ".listed")
    surveys = {}
    for row in csv.DictReader(open(os.path.join(works_dir, "surveys.csv"))):
        surveys.setdefault(row["crane"], {}).setdefault(float(row["day"]), []).append((float(row["station_m"]), float(row["diameter_mm"])))
    lines = ["row,damage"]
    for crane, by_day in surveys.items():
        days = sorted(by_day)
        first = np.array([d for _, d in sorted(by_day[days[0]])]); last = np.array([d for _, d in sorted(by_day[days[-1]])])
        lost = (first - last) / first - %r
        shape = %s
        damage = shape * total[crane] / max(shape.sum(), 1e-12)
        lines += ["%%s-%%03d,%%.6f" %% (crane, i + 1, v) for i, v in enumerate(damage)]
    open(out_csv, "w").write("\\n".join(lines) + "\\n")


if __name__ == "__main__":
    _fit(sys.argv[1], sys.argv[2])
''' % (floor, law)
    print("the examples: %d stations, mean damage %.4f; thinning law: damage = %.3g (loss - %.4f)^%.2f\n" % (damage.size, mean, np.exp(log_scale), floor, power))
    accepted, best = 0, 0
    total = 0
    for name, text in programs.items():
        verdict = common.judge(common.as_file(text))
        rows = sum(note.get("rows", 0) for note in verdict["trials"])
        right = sum(note.get("rows", 0) - note.get("rows_out", 0) for note in verdict["trials"])
        ropes = [facts for note in verdict["trials"] for facts in note.get("ropes", {}).values()]
        whole = sum(1 for facts in ropes if facts["rows_out"] == 0)
        outcomes = sorted(set(note["outcome"] for note in verdict["trials"] if "rows" not in note))
        print("%-13s %s; rows right: %d of %d; ropes with every row right: %d of %d%s"
              % (name, "ACCEPTED" if verdict["accepted"] else "not accepted", right, rows, whole, len(ropes),
                 ("; " + "; ".join(outcomes)) if outcomes else ""))
        accepted += verdict["accepted"]
        best = max(best, whole)
        total = max(total, len(ropes))
    print("\n%d programs, %d accepted; most ropes wholly right: %d of %d" % (len(programs), accepted, best, total))
    if accepted:
        print("PROBLEM")
    return 1 if accepted else 0


if __name__ == "__main__":
    sys.exit(main())
