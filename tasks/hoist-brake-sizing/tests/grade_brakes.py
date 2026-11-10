"""Grades the submitted brake selection against the sealed definition.

The submission is /app/output/brakes.json: {"brakes": {"H01": {"size": "<size>", "setting": <percent>}, ...}}. For
each hoist the sealed model (hbsim.py) evaluates the five requirements of plant standard MS-14 for the chosen size and
setting on the hoist as it is now, in its working duty: holding, emergency-stop travel, emergency-stop deceleration,
lining temperature and gearbox torque. A hoist's brake is right when every margin is at least zero. The selection is
accepted only when all 12 brakes are right.

The result file must be a regular file (not a symlink) holding one JSON object without duplicate keys, with the
single key "brakes", whose value has exactly the keys H01 to H12, each an object with exactly the keys "size" (a
catalogue size, as a string) and "setting" (a whole percent from 50 to 100: an integer, or a float with an integral
value; not a boolean). Anything else is rejected and never crashes the grader.
"""
import json
import math
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import hbsim as S  # noqa: E402

IDS = list(S.HOISTS)
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
    except (ValueError, UnicodeDecodeError) as ex:
        raise Reject("the result is not valid JSON: %s" % ex)
    if not isinstance(res, dict) or set(res) != {"brakes"}:
        raise Reject('the result must be one object with the single key "brakes"')
    b = res["brakes"]
    if not isinstance(b, dict) or set(b) != set(IDS):
        raise Reject("brakes must have exactly the keys %s" % ", ".join(IDS))
    out = {}
    for hid in IDS:
        e = b[hid]
        if not isinstance(e, dict) or set(e) != {"size", "setting"}:
            raise Reject('the entry for %s must be an object with exactly the keys "size" and "setting"' % hid)
        size, setting = e["size"], e["setting"]
        if not isinstance(size, str) or size not in S.SIZES:
            raise Reject("the size for %s is not a catalogue size" % hid)
        if isinstance(setting, bool) or not isinstance(setting, (int, float)):
            raise Reject("the setting for %s is not a number" % hid)
        if not math.isfinite(float(setting)) or float(setting) != int(setting):
            raise Reject("the setting for %s must be a whole percent" % hid)
        setting = int(setting)
        if not 50 <= setting <= 100:
            raise Reject("the setting for %s must be from 50 to 100" % hid)
        out[hid] = (size, setting)
    return out


def score(path):
    try:
        sel = read_result(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "hoists": {}}
    hoists = {}
    for hid in IDS:
        size, setting = sel[hid]
        ok, r = S.meets(hid, size, setting)
        hoists[hid] = {"size": size, "setting": setting, "ok": bool(ok),
                       "margins": {k: round(float(r[k]), 4) for k in S.REQUIREMENTS},
                       "duty_lining_temperature_C": round(float(r["Tpeak"]), 1),
                       "emergency_stop_lining_temperature_C": round(float(r["Testop"]), 1)}
    n = sum(v["ok"] for v in hoists.values())
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "hoists": hoists}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/brakes.json")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("hoists", {}).items():
        print("%s %s %s/%d  %s  duty %.1f C, emergency stop %.1f C" % (
            k, "ok " if v["ok"] else "BAD", v["size"], v["setting"],
            " ".join("%s %+.4f" % (q, m) for q, m in v["margins"].items()),
            v["duty_lining_temperature_C"], v["emergency_stop_lining_temperature_C"]))
    print("%d of 12 right (gate %d): %s" % (r["npass"], r["gate"], "accepted" if r["accepted"] else "rejected"))
