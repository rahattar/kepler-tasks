"""Checks /app/output/cell_capability.csv (or the path given) against the sealed tower (ct2.py).

The file is a CSV with a header row containing the columns cell and capability_pct, and one row for each of C1..C8 (no
other cells, none twice); capability_pct is a finite number. The true value of each cell is ct2.CAPABILITY[cell], its
capability at the end of the record in percent of design. A cell is accepted when the reported value is within LIMIT
percentage points of the true one; the file is accepted when all eight are.
"""
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ct2

LIMIT = 3.0          # percentage points, from the requirement


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or "cell" not in rows[0] or "capability_pct" not in rows[0]:
        raise ValueError("expected a CSV with columns cell and capability_pct")
    out = {}
    for r in rows:
        c = str(r["cell"]).strip().upper()
        if c not in ct2.CELLS:
            raise ValueError("not a cell of CT-2: %r" % r["cell"])
        if c in out:
            raise ValueError("%s given twice" % c)
        x = float(r["capability_pct"])
        if not math.isfinite(x):
            raise ValueError("%s: not a finite number" % c)
        out[c] = x
    return out


def score(path):
    got = load(path)
    rows = {}
    for c in ct2.CELLS:
        if c not in got:
            rows[c] = {"accepted": False, "reason": "missing"}
            continue
        miss = got[c] - ct2.CAPABILITY[c]
        rows[c] = {"reported": got[c], "miss_pp": round(float(miss), 3), "accepted": bool(abs(miss) <= LIMIT)}
    return {"accepted": all(r["accepted"] for r in rows.values()), "cells": rows,
            "missing": [c for c in ct2.CELLS if c not in got]}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/cell_capability.csv")
    bad = [c for c, v in r["cells"].items() if not v["accepted"]]
    worst = max((abs(v.get("miss_pp", 99)), c) for c, v in r["cells"].items())
    print("accepted" if r["accepted"] else "rejected", "| largest miss %.2f pp (%s)" % worst, "| outside:", bad)
