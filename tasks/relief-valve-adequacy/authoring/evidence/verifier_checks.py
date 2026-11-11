#!/usr/bin/env python3
"""Malformed and edge-case sheets put through the real grader.

Every case is built from the current reference sheet at run time, so this cannot go stale when the answer changes.
Each line says what the grader did and whether that was expected. None may come out UNEXPECTED.

    python3 verifier_checks.py
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import grade_relief  # noqa: E402
import solve  # noqa: E402

HEADER = list(grade_relief.COLUMNS)


def reference_rows():
    """The reference's own answer, as rows."""
    os.environ["DATA_DIR"] = os.path.join(ROOT, "environment", "data")
    m = solve.Model(solve.load(os.environ["DATA_DIR"]))
    return [[vid, case, "%.4f" % need, verd] for vid, case, need, verd in m.sheet()]


def render(rows, header=HEADER, eol="\n", blanks=False, pad=False):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=eol)
    w.writerow(header)
    for r in rows:
        w.writerow(["  %s  " % c for c in r] if pad else r)
        if blanks:
            buf.write(eol)
    return buf.getvalue()


def main():
    rows = reference_rows()
    tmp = tempfile.mkdtemp(prefix="rv_vc_")
    path = os.path.join(tmp, "relief.csv")
    bad = 0

    def check(label, text, expect, write=None):
        nonlocal bad
        for p in (path,):
            if os.path.lexists(p):
                os.remove(p)
        if write == "symlink":
            os.symlink(os.path.join(tmp, "target.csv"), path)
            with open(os.path.join(tmp, "target.csv"), "w") as f:
                f.write(text)
        elif write == "absent":
            pass
        elif write == "dir":
            os.mkdir(path)
        else:
            with open(path, "w", newline="") as f:
                f.write(text)
        r = grade_relief.assess(path)
        got = "rejected" if r.fault is not None else ("accepted" if r.taken else "graded %d of 9" % r.standing)
        tag = "ok " if got.split()[0] == expect.split()[0] else "UNEXPECTED"
        if tag != "ok ":
            bad += 1
        note = ("" if r.fault is None else ": " + r.fault.reason.replace(tmp + os.sep, "").replace(tmp, ""))
        print("%s %-52s -> %s%s" % (tag, label, got, note))
        if write == "dir":
            shutil.rmtree(path, ignore_errors=True)

    print("Sheets put through tests/grade_relief.py. Every case is built from the current reference.\n")
    check("the reference sheet", render(rows), "accepted")
    check("the reference sheet with CRLF line ends", render(rows, eol="\r\n"), "accepted")
    check("the reference sheet with blank lines", render(rows, blanks=True), "accepted")
    check("the reference sheet with padded fields", render(rows, pad=True), "accepted")
    check("the reference sheet with the rows reversed", render(rows[::-1]), "accepted")
    check("no file at all", "", "rejected", write="absent")
    check("a symbolic link to a good sheet", render(rows), "rejected", write="symlink")
    check("a directory in place of the file", "", "rejected", write="dir")
    check("an empty file", "", "rejected")
    check("the header alone", render([]), "rejected")
    check("no header", "\n".join(",".join(r) for r in rows) + "\n", "rejected")
    check("a misspelt header", render(rows, header=["valve", "governing_case", "area_mm2", "verdict"]),
          "rejected")
    check("an extra header column", render([r + ["x"] for r in rows], header=HEADER + ["note"]), "rejected")
    check("a row of the wrong length", render(rows[:-1] + [rows[-1][:3]]), "rejected")
    check("a valve missing", render(rows[:-1]), "rejected")
    check("a valve repeated", render(rows + [rows[0]]), "rejected")
    check("an unknown valve", render(rows[:-1] + [["PSV-410"] + rows[-1][1:]]), "rejected")
    check("a valve in lower case", render([["psv-401"] + rows[0][1:]] + rows[1:]), "rejected")
    check("non-ASCII text", render(rows).replace("fire", "fir" + chr(233)), "rejected")
    for label, val in (("an unknown contingency name", "boiling_liquid"), ("a contingency in upper case", "FIRE"),
                       ("an empty contingency", "")):
        check(label, render([[rows[0][0], val] + rows[0][2:]] + rows[1:]), "rejected")
    for label, val in (("an unknown verdict", "marginal"), ("a verdict in upper case", "Adequate"),
                       ("an empty verdict", "")):
        check(label, render([rows[0][:3] + [val]] + rows[1:]), "rejected")
    for label, val in (("an area that is not a number", "about 500"), ("an empty area", ""),
                       ("an area of NaN", "nan"), ("an infinite area", "inf"),
                       ("a negative area", "-500"), ("an area of zero", "0"),
                       ("an area below the range", "0.0005"), ("an area above the range", "100001")):
        check(label, render([rows[0][:2] + [val] + rows[0][3:]] + rows[1:]), "rejected")
    for label, val in (("an area in exponent form", "4.801918e2"), ("an area with six decimals", "480.191800"),
                       ("an area with twelve decimals", "480.191800123456"),
                       ("an area with a leading plus", "+480.1918")):
        check(label, render([rows[0][:2] + [val] + rows[0][3:]] + rows[1:]), "accepted")
    check("one contingency name changed", render([rows[0][:1] + ["fire"] + rows[0][2:]] + rows[1:]),
          "graded 8")
    check("one verdict changed", render([rows[0][:3] + ["inadequate"]] + rows[1:]), "graded 8")
    check("one area moved by 2 per cent",
          render([rows[0][:2] + ["%.4f" % (float(rows[0][2]) * 1.02)] + rows[0][3:]] + rows[1:]), "graded 8")
    check("every area moved by 2 per cent",
          render([r[:2] + ["%.4f" % (float(r[2]) * 1.02)] + r[3:] for r in rows]), "graded 0")

    shutil.rmtree(tmp, ignore_errors=True)

    print("\nThe reward protocol in tests/test.sh, with pytest stubbed so each combination can be forced.\n")
    bad += reward_protocol()
    print("\n%d cases, %d UNEXPECTED" % (41 + 4, bad))
    print("The grader never crashed, and the reward followed the run rather than anything written during it.")
    return 0


def reward_protocol():
    """Run tests/test.sh for real with a stub in place of python's pytest, and read back the reward it wrote.

    The stub answers the two calls test.sh makes: `python -m pytest ...` writes the ctrf report we want it to and
    exits with the status we want, and `python - <file>` runs the real interpreter on the script test.sh pipes in.
    """
    import stat as statmod
    sh = os.path.join(ROOT, "tests", "test.sh")
    reward = "/logs/verifier/reward.txt"
    cases = [
        ("pytest passes and the report holds one passing test", 0,
         {"results": {"summary": {"tests": 1, "passed": 1, "failed": 0, "skipped": 0,
                                  "pending": 0, "other": 0}}}, "1"),
        ("pytest passes but the report holds two tests", 0,
         {"results": {"summary": {"tests": 2, "passed": 2, "failed": 0, "skipped": 0,
                                  "pending": 0, "other": 0}}}, "0"),
        ("pytest fails though the report looks right", 1,
         {"results": {"summary": {"tests": 1, "passed": 1, "failed": 0, "skipped": 0,
                                  "pending": 0, "other": 0}}}, "0"),
        ("pytest passes and writes no report at all", 0, None, "0"),
    ]
    wrong = 0
    for label, status, report, want in cases:
        box = tempfile.mkdtemp(prefix="rv_rp_")
        try:
            stub = os.path.join(box, "python")
            with open(stub, "w") as handle:
                handle.write(
                    "#!/bin/bash\n"
                    "if [ \"$1\" = \"-m\" ]; then\n"
                    "  %s\n"
                    "  exit %d\n"
                    "fi\n"
                    "exec %s \"$@\"\n"
                    % (("cp %s /logs/verifier/ctrf.json" % os.path.join(box, "ctrf.json"))
                       if report is not None else ":", status, sys.executable))
            os.chmod(stub, os.stat(stub).st_mode | statmod.S_IEXEC)
            if report is not None:
                with open(os.path.join(box, "ctrf.json"), "w") as handle:
                    json.dump(report, handle)
            os.makedirs("/logs/verifier", exist_ok=True)
            for leftover in ("reward.txt", "ctrf.json"):
                try:
                    os.remove(os.path.join("/logs/verifier", leftover))
                except OSError:
                    pass
            env = dict(os.environ, PATH=box + os.pathsep + os.environ["PATH"])
            subprocess.run(["bash", sh], env=env, capture_output=True)
            got = open(reward).read().strip() if os.path.exists(reward) else "<no reward file>"
        finally:
            shutil.rmtree(box, ignore_errors=True)
        tag = "ok " if got == want else "UNEXPECTED"
        if tag != "ok ":
            wrong += 1
        print("%s %-52s -> reward %s" % (tag, label, got))
    return wrong


if __name__ == "__main__":
    sys.exit(main())
