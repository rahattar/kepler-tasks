"""What the verifier does with a sheet that is not as asked for. Every case must be rejected as a whole, and none
may crash the grader. The last block checks that a correct sheet still passes when it is written untidily.

    python3 verifier_checks.py > verifier_checks.txt
"""
import os
import shutil
import subprocess
import sys
import tempfile

import common as C

HERE = os.path.dirname(os.path.abspath(__file__))
GRADER = os.path.join(HERE, "..", "..", "tests", "grade_form.py")
HEADER = "feature,form_um,verdict"


def good_rows():
    ans = C.sentence(plan=C.plan_reference())
    return ["%s,%.2f,%s" % (f, ans[f][0], ans[f][1]) for f in C.ORDER]


def run(text, mangle=None):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "form.csv")
    if mangle == "symlink":
        os.symlink(os.path.join(d, "real.csv"), p)
        open(os.path.join(d, "real.csv"), "w").write(text)
    elif mangle == "absent":
        pass
    else:
        with open(p, "wb") as f:
            f.write(text.encode("utf-8", "surrogateescape") if isinstance(text, str) else text)
    r = subprocess.run([sys.executable, "-I", GRADER, p], capture_output=True, text=True)
    shutil.rmtree(d, ignore_errors=True)
    tail = [ln for ln in r.stdout.strip().splitlines() if ln][-1] if r.stdout.strip() else ""
    return r.returncode, tail


def main():
    rows = good_rows()
    ok = "\n".join([HEADER] + rows) + "\n"
    cases = [
        ("absent", ok, "absent"),
        ("a symlink to a correct sheet", ok, "symlink"),
        ("empty", "", None),
        ("header only", HEADER + "\n", None),
        ("header misspelt", ok.replace("form_um", "form_mm"), None),
        ("a fourth column added", ok.replace(HEADER, HEADER + ",note"), None),
        ("a feature missing", "\n".join([HEADER] + rows[1:]) + "\n", None),
        ("a feature repeated", "\n".join([HEADER] + rows + [rows[0]]) + "\n", None),
        ("an unknown feature", ok.replace("CB-21", "CB-99"), None),
        ("a feature in lower case", ok.replace("CB-21", "cb-21"), None),
        ("a row of two fields", ok.replace(rows[0], rows[0].rsplit(",", 1)[0]), None),
        ("a form error of three decimals", ok.replace(rows[0], rows[0].split(",")[0] + ",12.345,accept"), None),
        ("a form error that is text", ok.replace(rows[0], rows[0].split(",")[0] + ",wide,accept"), None),
        ("a form error that is NaN", ok.replace(rows[0], rows[0].split(",")[0] + ",nan,accept"), None),
        ("a form error that is infinite", ok.replace(rows[0], rows[0].split(",")[0] + ",inf,accept"), None),
        ("a form error that is negative", ok.replace(rows[0], rows[0].split(",")[0] + ",-3.00,accept"), None),
        ("a form error out of range", ok.replace(rows[0], rows[0].split(",")[0] + ",900.00,accept"), None),
        ("a form error left empty", ok.replace(rows[0], rows[0].split(",")[0] + ",,accept"), None),
        ("a sentence not in the four words", ok.replace("accept", "pass", 1), None),
        ("a sentence in upper case", ok.replace("accept", "ACCEPT", 1), None),
        ("a sentence left empty", ok.replace(rows[0], rows[0].rsplit(",", 1)[0] + ","), None),
        ("non-ASCII text", ok.replace("accept", "accept\u00b5", 1), None),
        ("a very large file", "\n".join([HEADER] + rows + ["#" + "x" * 200000]) + "\n", None),
    ]
    print("malformed sheets: every one must be rejected as a whole, and none may crash the grader\n")
    bad = 0
    for name, text, mangle in cases:
        rc, tail = run(text, mangle)
        rejected = "rejected" in tail
        crashed = rc not in (0, 1) or "Traceback" in tail
        bad += (not rejected) or crashed
        print("  %-38s %s%s" % (name, "rejected" if rejected else "NOT REJECTED",
                                "  CRASHED" if crashed else ""))
    print("\ncases that were not rejected or that crashed: %d of %d" % (bad, len(cases)))

    print("\na correct sheet, written untidily (these must pass)")
    for name, text in (("CRLF line ends", ok.replace("\n", "\r\n")),
                       ("blank lines between rows", "\n".join([HEADER] + sum([[r, ""] for r in rows], []))),
                       ("spaces around the fields", "\n".join([HEADER] + [" " + r.replace(",", " , ") for r in rows])),
                       ("the rows in another order", "\n".join([HEADER] + rows[::-1]) + "\n"),
                       ("a trailing comment line removed, final newline absent", "\n".join([HEADER] + rows))):
        rc, tail = run(text)
        print("  %-48s %s" % (name, "accepted" if "accepted" in tail else "REJECTED: " + tail[:60]))


if __name__ == "__main__":
    main()
