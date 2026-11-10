"""Verifier checks: malformed results must be rejected as a whole without crashing the grader, a well-formed wrong
result must be graded, and the reference result must be accepted.

    python3 authoring/evidence/verifier_checks.py      (writes verifier_checks.txt)
"""
import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

sys.path.insert(0, os.path.join(C.ROOT, "tests"))
import grade_tempering as G  # noqa: E402


def entry(ref, label, raw):
    body = ", ".join('"%s": %s' % (b, raw if b == "B07" else json.dumps(v)) for b, v in ref.items())
    return (label, '{"tempering_C": {%s}}' % body, False)


def cases(ref):
    good = {"tempering_C": ref}
    out = [("reference result", json.dumps(good), True),
           ("reference, temperatures as floats", json.dumps({"tempering_C": {b: float(v) for b, v in ref.items()}}), True),
           ("empty file", "", False),
           ("not JSON", "tempering_C: 1", False),
           ("a JSON array", json.dumps([1, 2]), False),
           ("missing batch", json.dumps({"tempering_C": {k: v for k, v in ref.items() if k != "B13"}}), False),
           ("extra batch", json.dumps({"tempering_C": dict(ref, B14=550)}), False),
           ("extra top-level key", json.dumps(dict(good, note="x")), False),
           ("wrong top-level key", json.dumps({"temperatures": ref}), False),
           ("duplicate batch", '{"tempering_C": {"B01": 533, %s}}' % ", ".join(
               '"%s": %s' % (k, json.dumps(v)) for k, v in ref.items()), False),
           ("duplicate top-level key", '{"tempering_C": %s, "tempering_C": %s}' % (json.dumps(ref), json.dumps(ref)), False),
           ("tempering_C as a list", json.dumps({"tempering_C": list(ref.values())}), False),
           ("batch keys lower case", json.dumps({"tempering_C": {k.lower(): v for k, v in ref.items()}}), False)]
    for label, val in (("temperature NaN", "NaN"), ("temperature Infinity", "Infinity"), ("temperature -Infinity", "-Infinity"),
                       ("temperature 580.5", "580.5"), ("temperature boolean", "true"), ("temperature string", '"580"'),
                       ("temperature null", "null"), ("temperature array", "[580]"), ("temperature object", '{"C": 580}'),
                       ("temperature -5", "-5"), ("temperature 1001", "1001"), ("temperature 1e400", "1e400")):
        out.append(entry(ref, label, val))
    return out


def main():
    temps, tests, lab = C.run_reference()
    ref = {b: int(T) for b, T in temps.items()}
    lines = ["Malformed and reference results through tests/grade_tempering.score (one temporary file each).", ""]
    n_ok = 0
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
            lines.append("%-34s accepted=%-5s %s %s" % (label, r["accepted"], "ok" if good else "WRONG",
                                                       r.get("error", "%d of 13 right" % r.get("npass", 0))))
        link = os.path.join(d, "link.json")
        os.symlink(os.path.join(d, "r00.json"), link)
        r = G.score(link)
        n_ok += not r["accepted"]
        lines.append("%-34s accepted=%-5s %s %s" % ("result is a symlink", r["accepted"], "ok" if not r["accepted"] else "WRONG",
                                                   r.get("error", "")))
        r = G.score(os.path.join(d, "absent.json"))
        n_ok += not r["accepted"]
        lines.append("%-34s accepted=%-5s %s %s" % ("no result file", r["accepted"], "ok" if not r["accepted"] else "WRONG",
                                                   r.get("error", "").replace(d, "<tmp>")))
        for label, wrong, nexp in (("B07 at 600 C (well formed, too soft)", dict(ref, B07=600), 12),
                                   ("B13 at 535 C (below G52's 540 C minimum)", dict(ref, B13=535), 12),
                                   ("every batch at 546 C", {b: 546 for b in ref}, None)):
            p = os.path.join(d, "wrong.json")
            with open(p, "w") as f:
                json.dump({"tempering_C": wrong}, f)
            r = G.score(p)
            ok = (not r["accepted"]) and "error" not in r and (nexp is None or r["npass"] == nexp)
            n_ok += ok
            lines.append("%-34s accepted=%-5s %s %d of 13 right" % (label, r["accepted"], "ok" if ok else "WRONG", r["npass"]))
    total = len(allc) + 5
    lines.append("")
    lines.append("%d of %d cases handled as expected; none crashed the grader." % (n_ok, total))
    return "\n".join(lines), n_ok == total


if __name__ == "__main__":
    txt, ok = main()
    print(txt)
    open(os.path.join(HERE, "verifier_checks.txt"), "w").write(txt + "\n")
    sys.exit(0 if ok else 1)
