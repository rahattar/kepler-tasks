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
FORBIDDEN = ["auto-zero", "autozero", "auto zero", "drift", "zero error", "never close", "never shut", "24/7",
             "day and night", "around the clock", "laborator", "lab box", "elbow", "orientation", "vertical",
             "bend", "bent", "kink", "crush", "sag", "punch", "stale", "out of date", "predate", "failed",
             "class", "representative", "one per", "one box per", "firmware", "you should", "make sure",
             "start by", "step 1", "hint", "tip:", "trap", "careful", "beware", "note that", "remember",
             "you are a", "python", "numpy", "scipy", "tools"]
REQUIRED = [r"\b40\b", r"VAV-3-01", r"VAV-3-40", r"2025", r"K x sqrt\(VP - offset\)|K\s*\*\s*sqrt\(VP - offset\)",
            r"10 percent|10%", r"design minimum", r"design maximum", r"/app/data", r"five", r"start-hood",
            r"127\.0\.0\.1:8000", r"GET /status", r"POST /visit\?box=VAV-3-\d\d", r"/app/visits",
            r"/app/output/calibration\.csv", r"tag,k_factor,vp_offset_inwc", r"one row (?:per box|for each of the 40 boxes)",
            r"in\. w\.c\.", r"cfm"]


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
        check(w not in low, "gives the mechanism or method away: %r" % w)
    for pat in REQUIRED:
        check(re.search(pat, body) is not None, "fact not stated: %s" % pat)
    check(re.search(r"\b(?:three|six|seven|eight|4|6)\s+visits?\b", low) is None, "the visit budget is five")
    allowed = {"1", "01", "3", "07", "10", "40", "2024", "2025", "8000", "127.0.0.1", str(t), "0"}
    for num in re.findall(r"(?<![\w.-])\d+(?:\.\d+)*(?![\w.])", body):
        check(num in allowed, "number %s is not one of the bundle's facts" % num)
    for msg in FAILS:
        print("  FAIL  " + msg)
    print(("%d FAILED of %d checks" % (len(FAILS), PASSED + len(FAILS))) if FAILS else
          "instruction clean: %d checks passed" % PASSED)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "instruction.md")))
