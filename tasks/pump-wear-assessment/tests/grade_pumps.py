"""Scores /app/output/overhaul.json (or the path given) against the sealed pump bank (pumps.py, seed 7).

The file is one JSON object: keys P1..P10, nothing else, each a finite number of metres. For every pump the
reported deficit is set against (1 - k) x the as-new head at 900 m3/h and 1480 rpm on 2026-11-02; within LIMIT m
the pump is accepted. The file is accepted when all ten are.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pumps

LIMIT = 0.3          # m, from the reliability requirement


def load(path):
    with open(path) as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("expected one JSON object keyed by pump")
    out = {}
    for key, val in obj.items():
        pump = str(key).strip().upper()
        if pump in out:
            raise ValueError("%s given twice" % pump)
        if isinstance(val, bool):
            raise ValueError("%s: not a number" % pump)
        x = float(val)
        if not math.isfinite(x):
            raise ValueError("%s: not finite" % pump)
        out[pump] = x
    stray = sorted(set(out) - set(pumps.UNITS))
    if stray:
        raise ValueError("not pumps of this bank: %s" % stray)
    return out


def score(path):
    bank = pumps.make_bank(7)
    got = load(path)
    rows = {}
    for p in pumps.UNITS:
        if p not in got:
            rows[p] = {"accepted": False, "reason": "missing"}
            continue
        miss = got[p] - pumps.deficit(bank[p])
        rows[p] = {"reported_m": got[p], "miss_m": round(float(miss), 4), "accepted": bool(abs(miss) <= LIMIT)}
    return {"accepted": all(r["accepted"] for r in rows.values()), "pumps": rows,
            "missing": [p for p in pumps.UNITS if p not in got]}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/overhaul.json")
    bad = [p for p, v in r["pumps"].items() if not v["accepted"]]
    worst = max((abs(v.get("miss_m", 99)), p) for p, v in r["pumps"].items())
    print("accepted" if r["accepted"] else "rejected", "| largest miss %.3f m (%s)" % worst, "| outside:", bad)
