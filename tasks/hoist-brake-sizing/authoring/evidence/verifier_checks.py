"""Verifier checks: malformed results must be rejected as a whole without crashing the grader, and the reference
result must be accepted.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import json
import os
import sys
import tempfile

import common as C

sys.path.insert(0, os.path.join(C.BUNDLE, "tests"))
import grade_brakes as G  # noqa: E402


def reference_selection():
    picks, n, fails = C.run()
    return {hid: {"size": p[1], "setting": p[2]} for hid, p in picks.items()}


def entry_cases(ref, label, size=None, setting=None, raw=None):
    body = []
    for hid, e in ref.items():
        if hid == "H05":
            if raw is not None:
                body.append('"%s": %s' % (hid, raw))
            else:
                s = json.dumps(e["size"]) if size is None else size
                v = json.dumps(e["setting"]) if setting is None else setting
                body.append('"%s": {"size": %s, "setting": %s}' % (hid, s, v))
        else:
            body.append('"%s": %s' % (hid, json.dumps(e)))
    return (label, '{"brakes": {%s}}' % ", ".join(body), False)


def cases(ref):
    good = {"brakes": ref}
    out = [("reference result", json.dumps(good), True),
           ("reference, settings as floats", json.dumps({"brakes": {h: {"size": e["size"], "setting": float(e["setting"])}
                                                                     for h, e in ref.items()}}), True),
           ("not JSON", "brakes: 1", False),
           ("a JSON array", json.dumps([1, 2]), False),
           ("missing hoist", json.dumps({"brakes": {k: v for k, v in ref.items() if k != "H12"}}), False),
           ("extra hoist", json.dumps({"brakes": dict(ref, H13={"size": "S10", "setting": 80})}), False),
           ("extra top-level key", json.dumps(dict(good, note="x")), False),
           ("duplicate hoist", '{"brakes": {"H01": {"size": "S14", "setting": 58}, %s}}' % ", ".join(
               '"%s": %s' % (k, json.dumps(v)) for k, v in ref.items()), False),
           ("brakes as a list", json.dumps({"brakes": list(ref.values())}), False)]
    for label, size in (("size not in the catalogue", '"S15"'), ("size lower case", '"s16"'), ("size a number", "16"),
                        ("size null", "null")):
        out.append(entry_cases(ref, label, size=size))
    for label, val in (("setting NaN", "NaN"), ("setting Infinity", "Infinity"), ("setting 49", "49"),
                       ("setting 101", "101"), ("setting 64.5", "64.5"), ("setting boolean", "true"),
                       ("setting string", '"64"'), ("setting null", "null"), ("setting array", "[64]")):
        out.append(entry_cases(ref, label, setting=val))
    out.append(entry_cases(ref, "entry with an extra key", raw='{"size": "S16", "setting": 64, "lining": "O2"}'))
    out.append(entry_cases(ref, "entry missing the setting", raw='{"size": "S16"}'))
    out.append(entry_cases(ref, "entry a string", raw='"S16/64"'))
    return out


if __name__ == "__main__":
    ref = reference_selection()
    n_ok = 0
    print("Malformed and reference results through tests/grade_brakes.score (one temporary file each).\n")
    allc = cases(ref)
    with tempfile.TemporaryDirectory() as d:
        for i, (label, text, expect) in enumerate(allc):
            p = os.path.join(d, "r%02d.json" % i)
            with open(p, "w") as f:
                f.write(text)
            try:
                r = G.score(p)
                crashed = False
            except Exception as ex:  # noqa: BLE001
                r, crashed = {"accepted": False, "error": "CRASH %r" % ex}, True
            good = (not crashed) and (bool(r["accepted"]) == expect) and (expect or "error" in r)
            n_ok += good
            print("%-32s accepted=%-5s %s %s" % (label, r["accepted"], "ok" if good else "WRONG",
                                                  r.get("error", "%d of 12 right" % r.get("npass", 0))))
        link = os.path.join(d, "link.json")
        os.symlink(os.path.join(d, "r00.json"), link)
        r = G.score(link)
        n_ok += (not r["accepted"])
        print("%-32s accepted=%-5s %s %s" % ("result is a symlink", r["accepted"], "ok" if not r["accepted"] else "WRONG",
                                              r.get("error", "")))
        # a wrong but well-formed selection: graded, not rejected
        wrong = {"brakes": dict(ref, H05={"size": "S16", "setting": 80})}
        p = os.path.join(d, "wrong.json")
        with open(p, "w") as f:
            json.dump(wrong, f)
        r = G.score(p)
        ok = (not r["accepted"]) and "error" not in r and r["npass"] == 11
        n_ok += ok
        print("%-32s accepted=%-5s %s %d of 12 right" % ("H05 at S16/80 (well formed)", r["accepted"], "ok" if ok else "WRONG",
                                                         r["npass"]))
    total = len(allc) + 2
    print("\n%d of %d cases handled as expected; none crashed the grader." % (n_ok, total))
