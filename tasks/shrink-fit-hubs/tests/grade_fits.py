"""Grades the submitted fits against the sealed definition.

The submission is /app/output/fits.json: {"fits": {"J01": {"interference_um": <um>, "heating_C": <C>}, ...}}. For each
joint the sealed model (sfsim.py) checks plant standard ST-9 as the joint is now: torque at the least interference and
hub stress at the greatest, both at rest and in steady running, and the assembly clearance at the oven temperature,
which must not exceed the hub's heating limit. The submission is accepted only when all 12 joints are right.

The result file must be a regular file (not a symlink) holding one JSON object without duplicate keys, with the single
key "fits", whose value has exactly the keys J01 to J12, each an object with exactly the keys "interference_um" (a
whole number from 1 to 2000) and "heating_C" (a whole number from 20 to 1000); a whole number may be written as an
integer or as a float with an integral value, but not as a boolean. Anything else is rejected and never crashes the
grader.
"""
import json
import math
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import sfsim as S  # noqa: E402

IDS = list(S.JOINTS)
GATE = len(IDS)
FIELDS = {"interference_um": (1, 2000), "heating_C": (20, 1000)}


class Reject(Exception):
    pass


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise Reject("duplicate key in the result")
    return dict(pairs)


def _whole(v, what, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise Reject("%s is not a number" % what)
    if not math.isfinite(float(v)) or float(v) != int(v):
        raise Reject("%s must be a whole number" % what)
    v = int(v)
    if not lo <= v <= hi:
        raise Reject("%s must be from %d to %d" % (what, lo, hi))
    return v


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
    if not isinstance(res, dict) or set(res) != {"fits"}:
        raise Reject('the result must be one object with the single key "fits"')
    fits = res["fits"]
    if not isinstance(fits, dict) or set(fits) != set(IDS):
        raise Reject("fits must have exactly the keys %s" % ", ".join(IDS))
    out = {}
    for k in IDS:
        e = fits[k]
        if not isinstance(e, dict) or set(e) != set(FIELDS):
            raise Reject('%s must be an object with exactly the keys "interference_um" and "heating_C"' % k)
        out[k] = tuple(_whole(e[f], "%s %s" % (k, f), *FIELDS[f]) for f in FIELDS)
    return out


def score(path):
    try:
        sel = read_result(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "joints": {}}
    joints = {}
    for k in IDS:
        um, T = sel[k]
        ok, m = S.joint_ok(k, um, T)
        joints[k] = {"interference_um": um, "heating_C": T, "ok": bool(ok),
                     "margins": {q: round(float(m[q]), 4) for q in ("slip", "stress", "clear", "limit")}}
    n = sum(v["ok"] for v in joints.values())
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "joints": joints}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/fits.json")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("joints", {}).items():
        m = v["margins"]
        print("%s %s %4d um %3d C | torque %+.3f stress %+.3f clearance %+.3f limit %+.2f" % (
            k, "ok " if v["ok"] else "BAD", v["interference_um"], v["heating_C"], m["slip"], m["stress"], m["clear"],
            m["limit"]))
    print("%d of %d right (gate %d): %s" % (r["npass"], GATE, r["gate"], "accepted" if r["accepted"] else "rejected"))
