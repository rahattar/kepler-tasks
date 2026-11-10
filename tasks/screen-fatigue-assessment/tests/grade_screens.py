"""Scores /app/output/damage.json (or the path given) against the sealed screen house (screens.py).

The file is one JSON object: keys S1..S10, nothing else, each a finite non-negative Miner sum. The true value of
each screen is screens.DAMAGE[screen], the sealed model's damage at the monitored weld toe to 2026-10-31 (the model
is calibrated to it exactly; authoring/evidence/calibration.txt recomputes it). A screen is accepted when the
reported value is within LIMIT of the true one, relative; the file is accepted when all ten are.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screens

LIMIT = 0.20         # relative, from the requirement


def load(path):
    with open(path) as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("expected one JSON object keyed by screen")
    out = {}
    for key, val in obj.items():
        u = str(key).strip().upper()
        if u in out:
            raise ValueError("%s given twice" % u)
        if isinstance(val, bool):
            raise ValueError("%s: not a number" % u)
        x = float(val)
        if not math.isfinite(x) or x < 0:
            raise ValueError("%s: not a finite non-negative number" % u)
        out[u] = x
    stray = sorted(set(out) - set(screens.UNITS))
    if stray:
        raise ValueError("not screens of this house: %s" % stray)
    return out


def score(path):
    got = load(path)
    rows = {}
    for u in screens.UNITS:
        if u not in got:
            rows[u] = {"accepted": False, "reason": "missing"}
            continue
        rel = got[u] / screens.DAMAGE[u] - 1.0
        rows[u] = {"reported": got[u], "relative_miss": round(float(rel), 4), "accepted": bool(abs(rel) <= LIMIT)}
    return {"accepted": all(r["accepted"] for r in rows.values()), "screens": rows,
            "missing": [u for u in screens.UNITS if u not in got]}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/damage.json")
    bad = [u for u, v in r["screens"].items() if not v["accepted"]]
    worst = max((abs(v.get("relative_miss", 99)), u) for u, v in r["screens"].items())
    print("accepted" if r["accepted"] else "rejected", "| largest miss %.3f (%s)" % worst, "| outside:", bad)
