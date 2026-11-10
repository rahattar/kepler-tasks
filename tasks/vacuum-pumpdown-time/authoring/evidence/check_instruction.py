"""Mechanical checks on the hand-written instruction.md. Prose is never touched.

    python3 authoring/evidence/check_instruction.py [path]

Checks that every path, name and number the instruction states agrees with the bundle (the agent's data, the
artifact, the verifier's constants, task.toml), that the run conditions and output rules the verifier applies are all
stated, that the closing sentence is byte exact, that it is ASCII, and that nothing naming the grading thresholds or a
record fault appears. Standard library only; tests/grade.py is read with ast, never imported.
"""
import ast, os, re, sys, tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FAILS = []
CLOSING = ("You have {t} seconds to complete this task. Do not cheat by using online solutions or hints specific to "
           "this task.")
NUM = {6: "six", 7: "seven", 8: "eight", 10: "ten"}
# the instruction describes the task and its run conditions, not the grader (the tolerance is a requirement; its
# wording is checked above, so "within" and "percent" are allowed there only)
GRADER = ["verifier", "graded", "grading", "scored", "score", "threshold", "at most", "accepted", "reward",
          "hidden", "test case", "compared", "allowed"]
# substrings that would name a record fault, a model shortcut or the checks that find them
FAULTS = ["turbo", "exchange", "gauge", "crossover", "spool", "internals", "load lock", "merge", "seal", "leak",
          "nitrogen", "water", "conductance", "volume", "outgassing", "header", "log", "record", "synthetic", "seed",
          "trap", "careful", "note that", "hint", "beware", "make sure", "check", "trust", "fault", "error", "verify",
          "margin"]
# each rule may be worded in any of these ways
REQUIRED = [("regular file",), ("exactly once",), ("exit with status 0",), ("`python3 -I pumpdown.py JOB_DIR OUT_JSON`",),
            ("copy of `pumpdown.py` alone",), ("unprivileged user",), ("without network access",), ("read-only",),
            ("one after another",), ("`pumpdown_min`",), ("only that key",), ("finite positive number",),
            ("remains readable at the same path", "remains available at the same path")]


def check(ok, msg):
    if not ok:
        FAILS.append(msg)


def grade_constants():
    out = {}
    for node in ast.parse(open(os.path.join(ROOT, "tests", "grade.py")).read()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def main(path):
    txt = open(path).read()
    t = tomllib.load(open(os.path.join(ROOT, "task.toml"), "rb"))
    closing = CLOSING.format(t=int(t["agent"]["timeout_sec"]))
    low = txt.replace(closing, "").lower()   # the mandated sentence aside
    g = grade_constants()
    check(txt.isascii(), "instruction.md has non-ASCII characters")
    check(txt.rstrip("\n").endswith(closing), "closing sentence not byte exact")
    check(txt.count(closing) == 1, "closing sentence must appear once")
    check(t["artifacts"] == ["/app/output/pumpdown.py"] and "`/app/output/pumpdown.py`" in txt, "artifact path")
    for rel in re.findall(r"`/app/data/([^`]+)`", txt):
        check(os.path.exists(os.path.join(ROOT, "environment", "data", rel)), "named path missing: /app/data/%s" % rel)
    check(tuple(g["KEYS"]) == ("pumpdown_min",), "keys differ from the verifier's %s" % (g["KEYS"],))
    check("within %d percent of the job's true pump-down time" % round(100 * g["TOL"]) in txt, "tolerance (%g) not stated" % g["TOL"])
    n = len([d for d in os.listdir(os.path.join(ROOT, "tests", "hidden")) if os.path.isdir(os.path.join(ROOT, "tests", "hidden", d))])
    check(re.search(r"\b%s other chambers\b" % NUM[n], txt) and re.search(r"\b(The|Those) %s packages\b" % NUM[n], txt),
          "number of chambers (%d) not stated as '%s'" % (n, NUM[n]))
    mins = g["TIME_LIMIT_S"] // 60
    check(g["TIME_LIMIT_S"] % 60 == 0 and "%d minutes" % mins in txt, "time limit (%d s) not stated" % g["TIME_LIMIT_S"])
    check("no larger than %d bytes" % g["MAX_BYTES"] in txt, "output size limit (%d bytes) not stated" % g["MAX_BYTES"])
    for alts in REQUIRED:
        check(any(r in txt for r in alts), "run condition or format rule not stated: %r" % (alts,))
    for w in GRADER:
        check(re.search(r"\b%s" % re.escape(w), low) is None if w[0].isalpha() else w not in low, "grader term %r" % w)
    tol = "within %d percent of the job's true pump-down time" % round(100 * g["TOL"])
    rest = low.replace(tol.lower(), "")
    check("within" not in rest and "percent" not in rest and "%" not in rest, "a tolerance word outside the stated tolerance")
    for w in FAULTS:
        check(w not in low, "names a fault or a check: %r" % w)
    words = len(re.findall(r"\S+", txt))
    check(150 <= words <= 400, "length %d words outside 150 to 400" % words)
    for f in FAILS:
        print("FAIL  " + f)
    print("check_instruction: %s" % ("clean" if not FAILS else "%d failure(s)" % len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "instruction.md")))
