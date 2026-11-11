"""Complete sheets, run through the whole verifier in a clean subprocess: tests/test.sh's own pytest command, a
fresh import of tests/sealed, and the pass or fail taken from pytest's exit status the way test.sh takes it.

The other studies here call the verifier's grading module in process, which is the same code on the same written
sheets but spares them a subprocess each; this one closes the gap, so the calibration does not rest on a proxy.

    python3 verifier_runs.py > verifier_runs.txt
"""
import os
import subprocess
import sys
import tempfile

import common as C

TESTS = os.path.join(C.HERE, "..", "..", "tests")


def run(name, ans, expect, raw=None):
    """Write the sheet, run pytest over it as test.sh does, and report what the reward would be."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "form.csv")
        if raw is None:
            C.sheet_of(ans, path)
        else:
            with open(path, "w") as fh:
                fh.write(raw)
        env = dict(os.environ, FORM_FILE=path, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, "-m", "pytest", "test_form.py", "-p", "no:cacheprovider", "-q"],
                           cwd=TESTS, env=env, capture_output=True, text=True)
    reward = 1 if p.returncode == 0 else 0
    ok = "ok " if reward == expect else "WRONG"
    print("  %s  reward %d (expected %d)  %s" % (ok, reward, expect, name))
    return reward == expect


def main():
    P = C.plan_reference()
    cases = [("the reference solution's sentencing", C.sentence(plan=P), 1)]

    # the second, independently written solution, with its own reporting kept out of the way
    import contextlib
    import io
    import independent
    with contextlib.redirect_stdout(io.StringIO()):
        other = independent.main()
    cases.append(("the independent solution's sentencing", other, 1))

    # every defective route has to be refused
    for name, route in (("the tester's error motion charged to the parts", dict(spindle="keep")),
                        ("one error motion pooled over the whole campaign", dict(spindle="pooled")),
                        ("each campaign's whole average taken off its parts", dict(spindle="mean")),
                        ("the Gaussian band left off", dict(filt="none")),
                        ("nothing removed from the profile at all", dict(filt="order1")),
                        ("the mean diameter in place of the mating cylinder", dict(size="mean")),
                        ("the mating size alone, no two-point local size", dict(local=False)),
                        ("no temperature correction", dict(tcorr=False)),
                        ("roundness where the drawing calls cylindricity", dict(kindover=True)),
                        ("no transfer from the scan to the twin", dict(transfer=False))):
        cases.append((name, C.sentence(plan=P, **route), 0))
    cases.append(("no scans ordered at all", C.sentence(plan=()), 0))

    # the best a sheet made without doing the work can do
    cases.append(("every feature accept, form 20.00", {f: (20.0, "accept") for f in C.ORDER}, 0))
    cases.append(("every feature reject_both, form 26.00", {f: (26.0, "reject_both") for f in C.ORDER}, 0))

    print("sheets run through tests/test_form.py under pytest, one subprocess each:\n")
    good = all(run(n, a, e) for n, a, e in cases)

    print("\nand sheets the verifier has to refuse rather than grade:\n")
    head = "feature,form_um,verdict\n"
    body = "".join("%s,20.00,accept\n" % f for f in C.ORDER)
    for name, raw in (("a sheet with a feature missing", head + body.replace("RJ-46,20.00,accept\n", "")),
                      ("a sheet with a feature twice", head + body + "CB-21,20.00,accept\n"),
                      ("a sheet with an unknown sentence", head + body.replace("accept", "ok", 1)),
                      ("a sheet with a form figure that is not a number", head + body.replace("20.00", "n/a", 1)),
                      ("a sheet with no header", body),
                      ("an empty sheet", "")):
        good = run(name, None, 0, raw=raw) and good

    # The reference's own answers, right on all 14 features, in and out of the format the instruction states.
    print("\nand the reference's answers, where only the format differs:\n")
    ans = C.sentence(plan=P)
    rows = [[f, "%.2f" % ans[f][0], ans[f][1]] for f in C.ORDER]
    text = lambda rs, h="feature,form_um,verdict", nl="\n": nl.join([h] + [",".join(r) for r in rs]) + nl
    for name, raw, expect in (
            ("as asked for, LF line ends", text(rows), 1),
            ("as asked for, CRLF line ends", text(rows, nl="\r\n"), 1),
            ("form_um to one decimal place", text([[f, "%.1f" % float(v), w] for f, v, w in rows]), 0),
            ("form_um as whole numbers", text([[f, "%d" % round(float(v)), w] for f, v, w in rows]), 0),
            ("form_um to three decimal places", text([[f, v + "0", w] for f, v, w in rows]), 0),
            ("the header with spaces after its commas", text(rows, h="feature, form_um, verdict"), 0),
            ("the header in capitals", text(rows, h="FEATURE,FORM_UM,VERDICT"), 0),
            ("a space after every sentence", text([[f, v, w + " "] for f, v, w in rows]), 0)):
        good = run(name, None, expect, raw=raw) and good

    print("\n%s" % ("every sheet was decided as it should be" if good else "A SHEET WAS DECIDED WRONGLY"))
    assert good


if __name__ == "__main__":
    main()
