"""Checks /app/output/gt1_corrected_results.csv (or the path given) against the sealed test results (gt1_truth.py).

The file is a CSV with a header row containing the columns condition, corrected_output_mw and
corrected_heat_rate_kj_kwh, and one row for each of as_found and as_left (no other conditions, none twice); the values
are finite positive numbers. A value is accepted when it is within LIMIT of the true value, relative; the file is
accepted when all four are.
"""
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gt1_truth as T

LIMIT = 0.005        # relative (0.5 %), from the requirement
COLS = ("corrected_output_mw", "corrected_heat_rate_kj_kwh")


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or any(c not in rows[0] for c in ("condition",) + COLS):
        raise ValueError("expected a CSV with columns condition, %s" % ", ".join(COLS))
    out = {}
    for r in rows:
        c = str(r["condition"]).strip().lower()
        if c not in T.CONDITIONS:
            raise ValueError("not a test condition: %r" % r["condition"])
        if c in out:
            raise ValueError("%s given twice" % c)
        v = [float(r[k]) for k in COLS]
        if not all(math.isfinite(x) and x > 0 for x in v):
            raise ValueError("%s: values must be finite positive numbers" % c)
        out[c] = v
    return out


def score(path):
    got = load(path)
    rows = {}
    for c in T.CONDITIONS:
        if c not in got:
            rows[c] = {"accepted": False, "reason": "missing"}
            continue
        mo = got[c][0] / T.OUTPUT_MW[c] - 1.0
        mh = got[c][1] / T.HEAT_RATE[c] - 1.0
        rows[c] = {"output_mw": got[c][0], "heat_rate": got[c][1], "output_miss": round(mo, 5),
                   "heat_rate_miss": round(mh, 5), "accepted": bool(abs(mo) <= LIMIT and abs(mh) <= LIMIT)}
    return {"accepted": all(r["accepted"] for r in rows.values()), "conditions": rows,
            "missing": [c for c in T.CONDITIONS if c not in got]}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/gt1_corrected_results.csv")
    print("accepted" if r["accepted"] else "rejected", r["conditions"])
