"""Mechanical checks on the hand-written instruction.md. Prose is never touched.

    python3 authoring/evidence/check_instruction.py [path]

Checks the closing sentence byte for byte, ASCII, prose form, that the facts in
authoring/instruction-fact-sheet.md are stated, that every number agrees with the bundle, and that nothing
describes grading or gives the mechanism away. Standard library only.
"""
import base64
import os
import re
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FAILS, PASSED = [], 0
MARKER = base64.b64decode("aGFyYm9yLWNhbmFyeQ==").decode()
GRADER_TERMS = ["grader", "graded", "grading", "verifier", "scored", "scoring", "score ", "credit", "reward",
                "what counts", "is read", "are read", "evaluat", "hidden test", "test case", "tolerance"]
# regular expressions, matched on the lower-cased body; word boundaries keep "calibration" and "holds" legal
FORBIDDEN = [r"\bdrift", r"reads? low", r"\bratio", r"radiat", r"t\^4", r"fourth power", r"isotherm", r"\bsoak",
             r"\bstandby", r"\bhold\b", r"\bliners?\b", r"\bsic\b", r"\btubes?\b", r"thermocouple well", r"\bwells\b",
             r"pocl3", r"phosph", r"\bdoping", r"\bfactory", r"\bvendor", r"\bacceptance", r"sheath", r"\bcrack",
             r"\boffset", r"\bclass", r"\bone per\b", r"two purposes", r"double duty", r"you should", r"make sure",
             r"start by", r"step 1\b", r"\bhint", r"tip:", r"\btrap", r"careful", r"beware", r"note that", r"remember",
             r"you are a", r"python", r"numpy", r"scipy", r"\btools\b"]
REQUIRED = [r"\beight\b", r"\bF1\b", r"\bF8\b", r"\bfive\b", r"\bZ1\b", r"\bZ5\b",
            r"corrected = raw \+ correction|adds a correction to the raw", r"850 C", r"1050 C", r"2 K", r"/app/data", r"2025", r"four weeks",
            r"\bthree\b.{0,40}steps?", r"start-tcwafer", r"127\.0\.0\.1:8000", r"GET /status",
            r"POST /run\?furnace=F\d&steps=[0-9,]+", r"600, 850 and 1050|600, 850, and 1050", r"/app/runs",
            r"/app/output/corrections\.csv", r"furnace,zone,correction_850_c,correction_1050_c", r"\b40\b",
            r"corrections disabled"]


def check(ok, msg):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILS.append(msg)


def main(path):
    raw = open(path, "rb").read()
    check(raw.isascii(), "instruction is not ASCII")
    text = raw.decode("ascii", errors="replace")
    with open(os.path.join(ROOT, "task.toml"), "rb") as f:
        t = int(tomllib.load(f)["agent"]["timeout_sec"])
    closing = ("You have %d seconds to complete this task. Do not cheat by using online solutions or hints specific "
               "to this task." % t)
    check(text.rstrip("\n").endswith("\n\n" + closing), "closing sentence missing or not exact, after a blank line")
    check(not text.endswith("\n\n"), "at most one trailing newline")
    check(MARKER not in text.lower(), "eval-set marker in the instruction")
    body = text[: text.rfind(closing)]
    low = body.lower()
    check(not re.search(r"^\s*#", body, re.M), "markdown headings: the instruction is plain prose")
    check(len(re.findall(r"^\s*(?:[-*]|\d+[.)])\s", body, re.M)) <= 6, "reads as a checklist: more than six list lines")
    n = len(re.findall(r"[A-Za-z0-9]+", body))
    check(150 <= n <= 650, "length %d words, expected 150-650" % n)
    for w in GRADER_TERMS:
        check(w not in low, "describes grading: %r" % w)
    for w in FORBIDDEN:
        check(re.search(w, low) is None, "gives the mechanism or method away: %r" % w)
    for pat in REQUIRED:
        check(re.search(pat, body) is not None, "fact not stated: %s" % pat)
    check(re.search(r"\b(?:two|four|five|six)\s+(?:temperature\s+)?steps\b", low) is None, "the step budget is three")
    allowed = {"1", "2", "3", "5", "8", "40", "600", "850", "1050", "2025", "8000", "127.0.0.1", str(t), "0"}
    for num in re.findall(r"(?<![\w.-])\d+(?:\.\d+)*(?![\w.])", body):
        check(num in allowed, "number %s is not one of the bundle's facts" % num)
    for msg in FAILS:
        print("  FAIL  " + msg)
    print(("%d FAILED of %d checks" % (len(FAILS), PASSED + len(FAILS))) if FAILS else
          "instruction clean: %d checks passed" % PASSED)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "instruction.md")))
