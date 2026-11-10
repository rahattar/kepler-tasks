"""Verifier robustness: malformed results must be rejected (never crash the grader), and the valid reference result
must be accepted. Each case writes a file and runs tests/grade_torques.score on it.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import json
import os
import tempfile

import common as C
import grade_torques as G

GOOD = {"torques": {j: C.K_HB * C.d_m(j) * C.target_N(j) for j in C.IDS}}      # well formed, wrong values
good = json.dumps(GOOD)
CASES = {
    "well-formed, handbook values (judged on values)": good,
    "NaN torque": good.replace(json.dumps(GOOD["torques"]["J05"]), "NaN", 1),
    "infinite torque": good.replace(json.dumps(GOOD["torques"]["J05"]), "Infinity", 1),
    "negative torque": good.replace(json.dumps(GOOD["torques"]["J05"]), "-120.0", 1),
    "zero torque": good.replace(json.dumps(GOOD["torques"]["J05"]), "0", 1),
    "boolean torque": good.replace(json.dumps(GOOD["torques"]["J05"]), "true", 1),
    "string torque": good.replace(json.dumps(GOOD["torques"]["J05"]), '"300"', 1),
    "array torque": good.replace(json.dumps(GOOD["torques"]["J05"]), "[300]", 1),
    "duplicate joint key": good.replace('"J06"', '"J05"', 1),
    "missing joint": json.dumps({"torques": {k: v for k, v in GOOD["torques"].items() if k != "J09"}}),
    "extra joint": json.dumps({"torques": dict(GOOD["torques"], J17=300.0)}),
    "extra top-level key": json.dumps(dict(GOOD, note="x")),
    "torques not an object": json.dumps({"torques": [300.0] * 16}),
    "top level an array": "[]",
    "empty file": "",
    "not JSON": "torques: J01 300",
    "symlink as the result": None,
    "no file": "ABSENT",
}

if __name__ == "__main__":
    print("Verifier robustness (tests/grade_torques.py): each malformed result must be rejected without a crash.\n")
    with tempfile.TemporaryDirectory() as d:
        for name, body in CASES.items():
            p = os.path.join(d, "torques.json")
            if os.path.lexists(p):
                os.unlink(p)
            if body is None:
                os.symlink("/etc/hostname", p)
            elif body != "ABSENT":
                open(p, "w").write(body)
            try:
                r = G.score(p)
                err = r.get("error", "").replace(d, "<dir>")
                verdict = ("accepted" if r["accepted"] else "rejected") + (": " + err if "error" in r else
                          " on values (%d of 16 right)" % r["npass"])
            except Exception as ex:                      # a crash would be a defect
                verdict = "CRASH %r" % ex
            print("%-48s %s" % (name, verdict))
    # the reference's own result, as produced by solve.py on the rig emulation
    t = C.reference()[0]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "torques.json")
        json.dump({"torques": t}, open(p, "w"))
        r = G.score(p)
        print("%-48s %s" % ("reference result", "accepted, %d of 16" % r["npass"] if r["accepted"] else "REJECTED"))
