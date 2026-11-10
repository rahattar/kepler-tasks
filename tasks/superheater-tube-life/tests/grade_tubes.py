"""Checks /app/output/creep_life.csv (or the path given) against the sealed superheater (superheater.py).

The file is a CSV with a header row containing the columns element and life_fraction, and one row for each of E1..E10
(no other elements, none twice); life_fraction is a finite non-negative number. The true value of each element is
superheater.DAMAGE[element], its consumed creep life at the outlet-leg crown to 2026-10-31 (authoring/evidence/
calibration.txt recomputes it). An element is accepted when the reported value is within LIMIT of the true one,
relative; the file is accepted when all ten are.
"""
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import superheater

LIMIT = 0.25         # relative, from the requirement


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or "element" not in rows[0] or "life_fraction" not in rows[0]:
        raise ValueError("expected a CSV with columns element and life_fraction")
    out = {}
    for r in rows:
        e = str(r["element"]).strip().upper()
        if e not in superheater.ELEMENTS:
            raise ValueError("not an element of this superheater: %r" % r["element"])
        if e in out:
            raise ValueError("%s given twice" % e)
        x = float(r["life_fraction"])
        if not math.isfinite(x) or x < 0:
            raise ValueError("%s: not a finite non-negative number" % e)
        out[e] = x
    return out


def score(path):
    got = load(path)
    rows = {}
    for e in superheater.ELEMENTS:
        if e not in got:
            rows[e] = {"accepted": False, "reason": "missing"}
            continue
        rel = got[e] / superheater.DAMAGE[e] - 1.0
        rows[e] = {"reported": got[e], "relative_miss": round(float(rel), 4), "accepted": bool(abs(rel) <= LIMIT)}
    return {"accepted": all(r["accepted"] for r in rows.values()), "elements": rows,
            "missing": [e for e in superheater.ELEMENTS if e not in got]}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/creep_life.csv")
    bad = [e for e, v in r["elements"].items() if not v["accepted"]]
    worst = max((abs(v.get("relative_miss", 99)), e) for e, v in r["elements"].items())
    print("accepted" if r["accepted"] else "rejected", "| largest miss %.3f (%s)" % worst, "| outside:", bad)
