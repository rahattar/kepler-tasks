"""Grades the submitted tempering temperatures against the sealed definition.

The submission is /app/output/tempering.json: {"tempering_C": {"B01": <C>, ..., "B13": <C>}}. For each batch the
sealed model (tsim.py) gives the hardness at the drawing's location after tempering at the setpoint as procedure HT-4
requires (soak 1 h per 25 mm of ruling section, at least 2 h; G52 double tempered). A batch is right when the setpoint
is at or above its grade's lowest permitted temperature and the hardness is within the drawing's range. The submission
is accepted only when all 13 batches are right.

The result file must be a regular file (not a symlink) holding one JSON object without duplicate keys, with the single
key "tempering_C", whose value has exactly the keys B01 to B13, each a whole degree C from 0 to 1000 (an integer, or a
float with an integral value; not a boolean). Anything else is rejected and never crashes the grader.
"""
import json
import math
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import tsim as S  # noqa: E402

IDS = list(S.BATCHES)
GATE = len(IDS)


class Reject(Exception):
    pass


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise Reject("duplicate key in the result")
    return dict(pairs)


def read_result(path):
    try:
        st = os.lstat(path)
    except OSError:
        raise Reject("no result file at %s" % path)
    if not stat.S_ISREG(st.st_mode):
        raise Reject("the result is not a regular file")
    if st.st_size > 1_000_000:
        raise Reject("the result file is too large")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with os.fdopen(fd) as f:
            res = json.load(f, object_pairs_hook=_no_duplicates, parse_constant=lambda c: float(c))
    except (ValueError, UnicodeDecodeError, RecursionError) as ex:
        raise Reject("the result is not valid JSON: %s" % ex)
    if not isinstance(res, dict) or set(res) != {"tempering_C"}:
        raise Reject('the result must be one object with the single key "tempering_C"')
    t = res["tempering_C"]
    if not isinstance(t, dict) or set(t) != set(IDS):
        raise Reject("tempering_C must have exactly the keys %s" % ", ".join(IDS))
    out = {}
    for b in IDS:
        v = t[b]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise Reject("the temperature for %s is not a number" % b)
        if not math.isfinite(float(v)) or float(v) != int(v):
            raise Reject("the temperature for %s must be a whole degree C" % b)
        v = int(v)
        if not 0 <= v <= 1000:
            raise Reject("the temperature for %s must be from 0 to 1000 C" % b)
        out[b] = v
    return out


def score(path):
    try:
        sel = read_result(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "batches": {}}
    batches = {}
    for b in IDS:
        part, heat, D, loc, (lo, hi) = S.BATCHES[b]
        T = sel[b]
        ok, h = S.batch_ok(b, T)
        batches[b] = {"heat": heat, "T": T, "ok": bool(ok), "hardness_HRC": round(float(h), 2), "range": [lo, hi],
                      "minimum_C": S.TMIN[S.HEATS[heat][0]]}
    n = sum(v["ok"] for v in batches.values())
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "batches": batches}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/tempering.json")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("batches", {}).items():
        print("%s %s %s %d C -> %.2f HRC (range %g-%g, minimum %d C)" % (
            k, "ok " if v["ok"] else "BAD", v["heat"], v["T"], v["hardness_HRC"], v["range"][0], v["range"][1],
            v["minimum_C"]))
    print("%d of %d right (gate %d): %s" % (r["npass"], GATE, r["gate"], "accepted" if r["accepted"] else "rejected"))
