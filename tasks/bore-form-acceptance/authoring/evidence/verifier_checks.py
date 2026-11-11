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

    # The instruction's formatting contract, clause by clause. Each of these sheets carries the right form error
    # and the right sentence for all 14 features, so the only thing wrong with it is the thing named: if the
    # verifier took any of them, a sheet outside the format the instruction states would pass.
    def recast(i, fn):
        """the correct sheet with field i of every row rewritten"""
        out = []
        for r in rows:
            c = r.split(",")
            c[i] = fn(c[i])
            out.append(",".join(c))
        return "\n".join([HEADER] + out) + "\n"

    first = rows[0].split(",")
    one = lambda c: ok.replace(rows[0], ",".join(c), 1)
    contract = [
        ('"exact header": spaces after the commas', ok.replace(HEADER, HEADER.replace(",", ", "), 1)),
        ('"exact header": a space before it', " " + ok),
        ('"exact header": a space after it', ok.replace(HEADER, HEADER + " ", 1)),
        ('"exact header": in capitals', ok.replace(HEADER, HEADER.upper(), 1)),
        ('"exact header": quoted', ok.replace(HEADER, ",".join('"%s"' % h for h in HEADER.split(",")), 1)),
        ('"exact header": a blank line above it', "\n" + ok),
        ('"two decimal places": every figure to one', recast(1, lambda v: "%.1f" % float(v))),
        ('"two decimal places": every figure a whole number', recast(1, lambda v: "%d" % round(float(v)))),
        ('"two decimal places": every figure to three', recast(1, lambda v: v + "0")),
        ('"two decimal places": one figure to one', one([first[0], first[1][:-1], first[2]])),
        ('"two decimal places": one figure in exponent form', one([first[0], "%.2E" % float(first[1]), first[2]])),
        ('"two decimal places": one figure with a plus sign', one([first[0], "+" + first[1], first[2]])),
        ('"two decimal places": one figure with a unit', one([first[0], first[1] + " um", first[2]])),
        ('"two decimal places": a space before one figure', one([first[0], " " + first[1], first[2]])),
        ('"one of" the four words: a space after one', one([first[0], first[1], first[2] + " "])),
        ('"one row for each": a space before one feature', one([" " + first[0], first[1], first[2]])),
    ]
    print("\ncorrect answers in a format the instruction does not allow: every one must be rejected\n")
    slipped = 0
    for name, text in contract:
        rc, tail = run(text)
        rejected = "rejected" in tail
        slipped += not rejected
        print("  %-52s %s" % (name, "rejected" if rejected else "NOT REJECTED"))
    print("\nsheets outside the stated format that the verifier took: %d of %d" % (slipped, len(contract)))
    assert not slipped and not bad

    print("\na correct sheet, varied only in ways the instruction does not constrain (these must pass)")
    refused = 0
    for name, text in (("the sheet exactly as the reference writes it", ok),
                       ("CRLF line ends, which Python's csv module writes", ok.replace("\n", "\r\n")),
                       ("no terminator on the last line", "\n".join([HEADER] + rows)),
                       ("the rows in another order", "\n".join([HEADER] + rows[::-1]) + "\n"),
                       ("empty lines between the rows", "\n".join([HEADER] + sum([[r, ""] for r in rows], []))),
                       ("the fields of each row quoted, as CSV allows",
                        "\n".join([HEADER] + [",".join('"%s"' % c for c in r.split(",")) for r in rows]) + "\n")):
        rc, tail = run(text)
        took = "accepted" in tail
        refused += not took
        print("  %-52s %s" % (name, "accepted" if took else "REJECTED: " + tail[:60]))
    assert not refused


if __name__ == "__main__":
    main()
