"""Scores /app/output/damage.json (or the path given) against the sealed superheater (superheater.py).

The file is one JSON object: keys E1..E10, nothing else, each a finite non-negative life fraction. The true value of
each element is superheater.DAMAGE[element], its consumed creep life at the outlet-leg crown to 2026-10-31
(authoring/evidence/calibration.txt recomputes it). An element is accepted when the reported value is within LIMIT
of the true one, relative; the file is accepted when all ten are.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import superheater

LIMIT = 0.25         # relative, from the requirement


def load(path):
    with open(path) as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError("expected one JSON object keyed by element")
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
    stray = sorted(set(out) - set(superheater.ELEMENTS))
    if stray:
        raise ValueError("not elements of this superheater: %s" % stray)
    return out


def score(path):
    got = load(path)
    rows = {}
    for u in superheater.ELEMENTS:
        if u not in got:
            rows[u] = {"accepted": False, "reason": "missing"}
            continue
        rel = got[u] / superheater.DAMAGE[u] - 1.0
        rows[u] = {"reported": got[u], "relative_miss": round(float(rel), 4), "accepted": bool(abs(rel) <= LIMIT)}
    return {"accepted": all(r["accepted"] for r in rows.values()), "elements": rows,
            "missing": [u for u in superheater.ELEMENTS if u not in got]}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/damage.json")
    bad = [u for u, v in r["elements"].items() if not v["accepted"]]
    worst = max((abs(v.get("relative_miss", 99)), u) for u, v in r["elements"].items())
    print("accepted" if r["accepted"] else "rejected", "| largest miss %.3f (%s)" % worst, "| outside:", bad)
