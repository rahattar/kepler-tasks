"""Malformed and edge-case results against tests/grade_fits.py: each must be rejected (or graded) without a crash.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import copy
import json
import os
import sys
import tempfile

import common as C

sys.path.insert(0, os.path.join(C.ROOT, "tests"))
import grade_fits as G  # noqa: E402

REF = {"J01": (60, 234), "J02": (190, 190), "J03": (141, 176), "J04": (289, 270), "J05": (131, 300), "J06": (118, 270),
       "J07": (140, 248), "J08": (216, 248), "J09": (461, 280), "J10": (155, 260), "J11": (261, 293), "J12": (43, 224)}


def ref_obj(floats=False):
    f = float if floats else int
    return {"fits": {k: {"interference_um": f(a), "heating_C": f(b)} for k, (a, b) in REF.items()}}


def with_entry(field, value, joint="J05"):
    o = ref_obj()
    o["fits"][joint][field] = value
    return o


def cases():
    o = ref_obj()
    yield "reference result, integers", json.dumps(o), True
    yield "reference result, integral floats", json.dumps(ref_obj(True)), True
    yield "empty file", "", False
    yield "not JSON", "fits: J01 60", False
    yield "a JSON array", "[]", False
    yield "top-level extra key", json.dumps(dict(o, note=1)), False
    yield "top-level key misspelt", json.dumps({"fit": o["fits"]}), False
    yield "duplicate top-level key", '{"fits": %s, "fits": %s}' % (json.dumps(o["fits"]), json.dumps(o["fits"])), False
    d = copy.deepcopy(o); del d["fits"]["J12"]
    yield "a joint missing", json.dumps(d), False
    d = copy.deepcopy(o); d["fits"]["J13"] = d["fits"]["J12"]
    yield "an extra joint", json.dumps(d), False
    d = copy.deepcopy(o); d["fits"]["j01"] = d["fits"].pop("J01")
    yield "a joint key misspelt", json.dumps(d), False
    s = json.dumps(o).replace('"J02": {', '"J02": {"interference_um": 190, ', 1)
    yield "duplicate key inside a joint", s, False
    d = copy.deepcopy(o); d["fits"]["J03"] = [141, 176]
    yield "a joint entry not an object", json.dumps(d), False
    d = copy.deepcopy(o); d["fits"]["J03"]["note"] = "x"
    yield "a joint entry with an extra key", json.dumps(d), False
    d = copy.deepcopy(o); del d["fits"]["J03"]["heating_C"]
    yield "a joint entry missing heating_C", json.dumps(d), False
    for name, v in (("NaN", "NaN"), ("Infinity", "Infinity"), ("-Infinity", "-Infinity")):
        yield "interference %s" % name, json.dumps(o).replace('"interference_um": 131', '"interference_um": %s' % v), False
    for name, v in (("130.5", 130.5), ("true", True), ("a string", "131"), ("an array", [131]), ("an object", {"v": 131}),
                    ("null", None), ("0", 0), ("2001", 2001), ("-5", -5)):
        yield "interference %s" % name, json.dumps(with_entry("interference_um", v)), False
    for name, v in (("19", 19), ("1001", 1001), ("299.9", 299.9), ("false", False)):
        yield "heating %s" % name, json.dumps(with_entry("heating_C", v)), False
    yield "oven above J05's heating limit (301 C): graded, J05 wrong", json.dumps(with_entry("heating_C", 301)), "graded"
    yield "J01 at its at-rest stress limit (84 um): graded, J01 wrong", json.dumps(with_entry("interference_um", 84, "J01")), "graded"


def main():
    tmp = tempfile.mkdtemp()
    n = 0
    for name, text, expect in cases():
        p = os.path.join(tmp, "fits.json")
        with open(p, "w") as f:
            f.write(text)
        r = G.score(p)
        n += 1
        if expect is True:
            ok = r["accepted"] and r["npass"] == 12
            print("%-62s accepted %d of 12  %s" % (name, r["npass"], "as expected" if ok else "UNEXPECTED"))
        elif expect == "graded":
            ok = "error" not in r and not r["accepted"] and r["npass"] == 11
            print("%-62s graded, %d of 12 right  %s" % (name, r["npass"], "as expected" if ok else "UNEXPECTED"))
        else:
            ok = "error" in r and not r["accepted"]
            print("%-62s rejected: %s  %s" % (name, r.get("error"), "" if ok else "UNEXPECTED"))
        os.remove(p)
    # a symlink and an absent file
    target = os.path.join(tmp, "real.json")
    with open(target, "w") as f:
        f.write(json.dumps(ref_obj()))
    link = os.path.join(tmp, "fits.json")
    os.symlink(target, link)
    r = G.score(link)
    n += 1
    print("%-62s rejected: %s" % ("the result a symlink to a correct result", r.get("error")))
    r = G.score(os.path.join(tmp, "absent.json"))
    n += 1
    print("%-62s rejected: %s" % ("no result file", r.get("error")))
    print()
    print("%d cases run, none crashed the grader" % n)


if __name__ == "__main__":
    main()
