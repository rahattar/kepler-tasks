"""Grades the submitted re-inspection intervals against the sealed definition.

The submission is /app/output/intervals.json: {"intervals_months": {"C01": <months>, ..., "C16": <months>}}. For each
crack the sealed model gives the remaining life, the months of operation for the crack to grow from its inspected
depth to its critical depth under the loading it will see from now on. A crack's interval is right when it lies
between LO and HI times that life (inclusive). The assessment is accepted when at least GATE of the 16 are right.

The result file must be a regular file (not a symlink) holding one JSON object without duplicate keys, with an
"intervals_months" object whose keys are exactly the 16 crack ids and whose values are finite positive numbers (not
booleans). Anything else is rejected, never crashes the grader.
"""
import json
import math
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import fcgsim as F  # noqa: E402

CRACK_IDS = [t[0] for t in F.COMPS]


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
            res = json.load(f, object_pairs_hook=_no_duplicates)
    except (ValueError, UnicodeDecodeError) as ex:
        raise Reject("the result is not valid JSON: %s" % ex)
    if not isinstance(res, dict) or set(res) != {"intervals_months"}:
        raise Reject('the result must be one object with the single key "intervals_months"')
    iv = res["intervals_months"]
    if not isinstance(iv, dict) or set(iv) != set(CRACK_IDS):
        raise Reject("intervals_months must have exactly the keys %s" % ", ".join(CRACK_IDS))
    out = {}
    for k, v in iv.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise Reject("interval for %s is not a number" % k)
        v = float(v)
        if not math.isfinite(v) or v <= 0:
            raise Reject("interval for %s must be a finite positive number" % k)
        out[k] = v
    return out


def truth():
    return {t[0]: F.life_months(F.comp(t))[0] for t in F.COMPS}


def score(path):
    try:
        iv = read_result(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": F.GATE, "error": str(ex), "cracks": {}}
    life = truth()
    cracks = {}
    for k in CRACK_IDS:
        q = float(iv[k] / life[k])
        cracks[k] = {"interval_months": iv[k], "life_months": round(float(life[k]), 3), "fraction_of_life": round(q, 4),
                     "ok": bool(F.LO <= q <= F.HI)}
    n = sum(v["ok"] for v in cracks.values())
    return {"accepted": n >= F.GATE, "npass": n, "gate": F.GATE, "cracks": cracks}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/intervals.json")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("cracks", {}).items():
        print(k, "ok " if v["ok"] else "BAD", v)
    print("%d of 16 right (gate %d): %s" % (r["npass"], r["gate"], "accepted" if r["accepted"] else "rejected"))
