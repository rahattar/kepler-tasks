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
NUM = {6: "six", 8: "eight", 10: "ten"}
# the instruction describes the task and its run conditions, not the grader's thresholds
GRADER = ["verifier", "graded", "grading", "scored", "score", "tolerance", "within", "threshold", "at most", "percent",
          "%", "accepted", "reward", "hidden", "test case", "compared", "smallest"]
# substrings that would name a record fault or the checks that find it
FAULTS = ["divert", "diversion", "drawing", "as laid", "as-laid", "profile", "level", "datum", "tapping", "crown",
          "chamber", "transmitter", "static", "roughness", "friction", "aged", "relin", "throttl", "valve", "scada",
          "high point", "calibrat", "synthetic", "seed", "trap", "careful", "note that", "hint", "beware", "make sure",
          "record", "check", "trust", "fault", "error", "verify", "margin"]
# each rule may be worded in any of these ways
REQUIRED = [("regular file",), ("exactly once",), ("exit with status 0",), ("`python3 -I surge.py MAIN_DIR OUT_JSON`",),
            ("copy of `surge.py` alone",), ("unprivileged user",), ("without network access",), ("read-only",),
            ("one after another",), ("`vessel_volume_m3`",), ("`gas_volume_m3`",),
            ("only those two keys", "only the two required keys"),
            ("finite positive number",),
            ("below the vessel volume", "`gas_volume_m3` must be smaller than `vessel_volume_m3`"),
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
    check(t["artifacts"] == ["/app/output/surge.py"] and "`/app/output/surge.py`" in txt, "artifact path")
    for rel in re.findall(r"`/app/data/([^`]+)`", txt):
        check(os.path.exists(os.path.join(ROOT, "environment", "data", rel)), "named path missing: /app/data/%s" % rel)
    check(tuple(g["KEYS"]) == ("vessel_volume_m3", "gas_volume_m3"), "keys differ from the verifier's %s" % (g["KEYS"],))
    n = len([d for d in os.listdir(os.path.join(ROOT, "tests", "hidden")) if os.path.isdir(os.path.join(ROOT, "tests", "hidden", d))])
    check(re.search(r"\b%s other main(s| packages)\b" % NUM[n], txt) and re.search(r"\b(The|Those) %s packages\b" % NUM[n], txt),
          "number of mains (%d) not stated as '%s'" % (n, NUM[n]))
    mins = g["TIME_LIMIT_S"] // 60
    check(g["TIME_LIMIT_S"] % 60 == 0 and "%d minutes" % mins in txt, "time limit (%d s) not stated" % g["TIME_LIMIT_S"])
    check("no larger than %d bytes" % g["MAX_BYTES"] in txt, "output size limit (%d bytes) not stated" % g["MAX_BYTES"])
    for alts in REQUIRED:
        check(any(r in txt for r in alts), "run condition or format rule not stated: %r" % (alts,))
    for w in GRADER:
        check(re.search(r"\b%s" % re.escape(w), low) is None if w[0].isalpha() else w not in low, "grader term %r" % w)
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
