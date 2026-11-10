"""Grades the submitted assembly torques against the sealed definition.

The submission is /app/output/torques.json: {"torques": {"J01": <N.m>, ..., "J16": <N.m>}}. For each joint the
sealed model gives the single-bolt preload at that torque (clipped if the bolt yields) and the assembled per-bolt
preload after the pattern is tightened. A joint is right when the assembled preload is within WINDOW of its target and
the bolt did not yield. The bolt-up is accepted when at least GATE of the 16 joints are right.

The result file must be a regular file (not a symlink) holding one JSON object without duplicate keys, with a
"torques" object whose keys are exactly the 16 joint ids and whose values are finite positive numbers (not booleans).
Anything else is rejected, never crashes the grader.
"""
import json
import math
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import jointsim as J  # noqa: E402

SEED = json.load(open(os.path.join(HERE, "sealed", "seed.json")))["seed"]
JOINT_IDS = [j[0] for j in J.JOINTS]


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
    if not isinstance(res, dict) or set(res) != {"torques"}:
        raise Reject('the result must be one object with the single key "torques"')
    t = res["torques"]
    if not isinstance(t, dict) or set(t) != set(JOINT_IDS):
        raise Reject("torques must have exactly the keys %s" % ", ".join(JOINT_IDS))
    out = {}
    for k, v in t.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise Reject("torque for %s is not a number" % k)
        v = float(v)
        if not math.isfinite(v) or v <= 0:
            raise Reject("torque for %s must be a finite positive number" % k)
        out[k] = v
    return out


def score(path):
    truth = J.seal(SEED)
    try:
        torques = read_result(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": J.GATE, "error": str(ex), "joints": {}}
    g = J.grade(truth, torques)
    return {"accepted": bool(g["accepted"]), "npass": int(g["npass"]), "gate": J.GATE, "joints": g["joints"]}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/torques.json")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("joints", {}).items():
        print(k, "ok " if v["ok"] else "BAD", v)
    print("%d of 16 right (gate %d): %s" % (r["npass"], r["gate"], "accepted" if r["accepted"] else "rejected"))
