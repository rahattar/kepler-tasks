"""Verifier checks: malformed results must be rejected as a whole without crashing the grader, and the reference
result must be accepted.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import json
import os
import sys
import tempfile

import common as C

sys.path.insert(0, os.path.join(C.ROOT, "tests"))
import grade_intervals as G  # noqa: E402


def reference_intervals():
    law = C.examples_for_heats(C.fit(C.lab([("paris", 0.20, "H1"), ("paris", 0.35, "H1"), ("paris", 0.45, "H1"),
                                            ("paris", 0.90, "H1"), ("paris", 0.70, "H4")])))
    iv, _ = C.assess(law)
    return {c: round(float(v), 4) for c, v in iv.items()}


def cases(ref):
    good = {"intervals_months": dict(ref)}
    out = []
    out.append(("reference result", json.dumps(good), True))
    out.append(("not JSON", "intervals: 1", False))
    out.append(("a JSON array", json.dumps([1, 2]), False))
    out.append(("missing key", json.dumps({"intervals_months": {k: v for k, v in ref.items() if k != "C16"}}), False))
    out.append(("extra crack key", json.dumps({"intervals_months": dict(ref, C17=1.0)}), False))
    out.append(("extra top-level key", json.dumps(dict(good, note="x")), False))
    out.append(("duplicate key", '{"intervals_months": {"C01": 1.0, "C01": 2.0, %s}}' % ", ".join(
        '"%s": %s' % (k, json.dumps(v)) for k, v in ref.items() if k != "C01"), False))
    for label, val in (("NaN", "NaN"), ("Infinity", "Infinity"), ("-Infinity", "-Infinity"), ("zero", "0"),
                       ("negative", "-1.5"), ("boolean", "true"), ("string", '"7.5"'), ("array", "[7.5]"),
                       ("null", "null")):
        body = ", ".join('"%s": %s' % (k, val if k == "C05" else json.dumps(v)) for k, v in ref.items())
        out.append(("interval %s" % label, '{"intervals_months": {%s}}' % body, False))
    out.append(("intervals as a list", json.dumps({"intervals_months": list(ref.values())}), False))
    return out


if __name__ == "__main__":
    ref = reference_intervals()
    n_ok = 0
    print("Malformed and reference results through tests/grade_intervals.score (one temporary file each).\n")
    with tempfile.TemporaryDirectory() as d:
        for i, (label, text, expect) in enumerate(cases(ref)):
            p = os.path.join(d, "r%02d.json" % i)
            with open(p, "w") as f:
                f.write(text)
            try:
                r = G.score(p)
                crashed = False
            except Exception as ex:  # noqa: BLE001
                r, crashed = {"accepted": False, "error": "CRASH %r" % ex}, True
            good = (not crashed) and (bool(r["accepted"]) == expect) and (expect or "error" in r or not r["accepted"])
            n_ok += good
            print("%-28s accepted=%-5s %s %s" % (label, r["accepted"], "ok" if good else "WRONG",
                                                  r.get("error", "%d of 16 right" % r.get("npass", 0))))
        link = os.path.join(d, "link.json")
        os.symlink(os.path.join(d, "r00.json"), link)
        r = G.score(link)
        n_ok += (not r["accepted"])
        print("%-28s accepted=%-5s %s %s" % ("result is a symlink", r["accepted"], "ok" if not r["accepted"] else "WRONG",
                                              r.get("error", "")))
    total = len(cases(ref)) + 1
    print("\n%d of %d cases handled as expected; none crashed the grader." % (n_ok, total))
