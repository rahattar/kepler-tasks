"""Mechanical checks on the hand-written instruction.md. Prose is never touched.

    python3 authoring/evidence/check_instruction.py [path]

Checks that every number, path, key and interface the brief states agrees with the bundle (the verifier's
constants, the comfort file, task.toml), that the closing sentence is byte exact, that the file reads as
prose and states requirements rather than describing a grader, that it is ASCII, and that nothing giving the
method away appears. Standard library only; the sealed modules are read with ast, never imported.
"""
import ast
import base64
import json
import os
import re
import sys
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FAILS, WARNS, PASSED = [], [], 0

MARKER = base64.b64decode("aGFyYm9yLWNhbmFyeQ==").decode()
CLOSING = ("You have {t} seconds to complete this task. Do not cheat by using online "
           "solutions or hints specific to this task.")
# the instruction describes the task, not the grader (channel rule, Oct 14)
GRADER_TERMS = ["grader", "graded", "grading", "verifier", "scored", "scoring", "score ", "compared with",
                "compared to", "will be compared", "credit", "reward", "what counts", "is read", "are read",
                "hidden", "test case", "passes when", "pass when", "it does not grade", "to pass"]
# terms that hand over the method or the planted features
FORBIDDEN = [
    "kalman", "observer", "estimator", "state estimat", "model predictive", "mpc", "receding horizon",
    "linear program", "optimi", "system identification", "identify the", "fit a model", "rc model",
    "grey-box", "gray-box", "trust region", "lineari", "precool", "pre-cool", "night", "lag", "time constant",
    "damp", "bias", "underestimat", "overestimat", "valve failed", "stuck", "failed closed", "labor day",
    "holiday", "federal", "blind", "furnish", "as-built zones differ by", "you should", "you may want",
    "make sure", "start by", "first,", "step 1", "step one", "hint", "tip:", "careful", "beware", "note that",
]
WORD_MIN, WORD_MAX = 300, 650


def module_constants(path):
    ns = {}
    for node in ast.parse(open(path).read()).body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            val = eval(compile(ast.Expression(node.value), path, "eval"), {"__builtins__": {}}, ns)
        except Exception:
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name):
                ns[tgt.id] = val
            elif isinstance(tgt, ast.Tuple) and isinstance(val, tuple) and len(val) == len(tgt.elts):
                for e, v in zip(tgt.elts, val):
                    if isinstance(e, ast.Name):
                        ns[e.id] = v
    return SimpleNamespace(**ns)


def toml_value(path, section, key):
    try:
        import tomllib
        with open(path, "rb") as f:
            return tomllib.load(f)[section][key]
    except ImportError:
        text = open(path).read()
        sec = re.search(r"^\[%s\]\n(.*?)(?=^\[|\Z)" % re.escape(section), text, re.M | re.S).group(1)
        return ast.literal_eval(re.search(r"^%s\s*=\s*([^\n]+)" % key, sec, re.M).group(1).strip())


def check(ok, msg):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILS.append(msg)


def num_in(text, x, unit=""):
    s = ("%g" % x).replace(".", r"\.")
    return re.search(r"(?<![\d.])%s(?:\.0+)?(?![\d])%s" % (s, unit), text) is not None


def main(path):
    global PASSED
    if not os.path.exists(path):
        print("no instruction file at %s -- Alex writes it, by hand" % path)
        return 1
    raw = open(path, encoding="utf-8").read()
    body = raw.lower()
    outside = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("    "))
    prose = outside.lower()
    timeout = int(float(toml_value(os.path.join(ROOT, "task.toml"), "agent", "timeout_sec")))
    want = CLOSING.format(t=timeout)
    scan = body.replace(want.lower(), "")
    g = module_constants(os.path.join(ROOT, "tests", "grade.py"))
    inst = module_constants(os.path.join(ROOT, "tests", "instance.py"))
    comfort = json.load(open(os.path.join(ROOT, "environment", "data", "comfort.json")))

    # --- closing sentence, byte exact; no eval-set marker
    check(raw.rstrip("\n").endswith(want), "the file must end with exactly:\n    " + want)
    check(raw.endswith("\n") and not raw.endswith("\n\n"), "exactly one trailing newline after the closing sentence")
    check("\n\n" + want in raw, "a blank line must precede the closing sentence")
    check(MARKER not in body, "an eval-set marker line is present (the structure check rejects it)")

    # --- paths and interface
    for s in ("/app/controller.py", "/app/data", "/app/check_controller.py"):
        check(s in raw, "the path %s must appear" % s)
    for m in set(re.findall(r"/app/[\w./-]*\w/?", raw)):
        check("`%s`" % m in raw or "`%s" % m in raw, "the path %s must be in a code span (backticks lost?)" % m)
    for s in ("Controller", "step(obs)", "numpy", "scipy"):
        check(s in raw, "'%s' must appear" % s)
    check(re.search(r"self[- ]contained|single file|one file|alone", prose) is not None,
          "say the controller is one self-contained file run alone")
    for k in ("time", "outdoor_temp_c", "facade_irradiance_w_m2", "supply_temp_c", "supply_setpoint_c", "zones",
              "air_temp_c", "slab_temp_c", "return_temp_c", "valve_duty", "forecast", "issued", "step_minutes",
              "west", "east"):
        check("`%s`" % k in raw or '"%s"' % k in raw, "the observation key '%s' must appear in a code span" % k)
    check(num_in(raw, 216), "the forecast length, 216 values, must appear")
    check(re.search(r"00:00, 06:00, 12:00 and 18:00|00:00, 06:00, 12:00, 18:00", raw) is not None,
          "the forecast issue times must appear")
    check("2017-07-15T00:00" in raw and "2017-09-08T23:45" in raw, "the run period must appear")
    check("2017-05-20" in raw and "2017-07-14" in raw, "the trend log period must appear")
    check(re.search(r"15[- ]minute|every 15 min|15 min", prose) is not None, "the 15-minute step must appear")
    check(re.search(r"15\s*-\s*22\s*c|15 to 22", prose) is not None, "the 15-22 C setpoint clip must appear")
    check(re.search(r"\[0, 1\]|0 to 1|between 0 and 1", prose) is not None, "the valve duty range [0, 1] must appear")
    check("whole minute" in prose, "duty rounded to whole minutes must appear")
    check(re.search(r"cannot heat|no heat is removed|colder than the supply", prose) is not None,
          "the no-heating and cold-slab rules must appear")
    check(re.search(r"(leaving|supply)[^.]{0,80}(rises|raises|rise)|(rises|raises)[^.]{0,60}above the setpoint", prose) is not None,
          "say the leaving water rises when capacity is exceeded")

    # --- requirements, every number tied to the bundle
    check(comfort["operative_temp_band_c"] == [inst.LO_OCC, inst.HI_OCC], "comfort.json disagrees with the verifier")
    check(num_in(raw, inst.LO_OCC) and num_in(raw, inst.HI_OCC), "the comfort band %.1f-%.1f C must appear" % (inst.LO_OCC, inst.HI_OCC))
    check(num_in(body, g.DEV_MAX, r"\s*k\s*h"), "the %.1f K h limit must appear" % g.DEV_MAX)
    check(re.search(r"\b(one|1)\b[^.]{0,40}\b16\b", prose) is not None and g.FAILS_OK == 1,
          "at most one of the 16 zone-weeks must appear")
    check(("%.2f" % g.ALLOW) in raw, "the cost allowance %.2f must appear" % g.ALLOW)
    check(re.search(r"operative", prose) is not None, "comfort is on operative temperature; say so")
    check(re.search(r"every minute|each minute|minute by minute", prose) is not None, "say it is evaluated every minute")
    check(re.search(r"cop", prose) is not None and "tariff" in prose, "the cost definition (COP, tariff) must appear")
    check(re.search(r"benchmark", prose) is not None, "the benchmark the cost is measured against must be described")
    for s in ("21.3", "25.7", "48"):
        check(s in raw, "the benchmark's '%s' must appear" % s)
    check(re.search(r"saturday[^.]{0,40}friday", prose) is not None, "the weeks run Saturday to Friday")
    check(num_in(raw, g.INIT_TIMEOUT_S, r"\s*(s\b|sec)") and num_in(raw, g.STEP_TIMEOUT_S, r"\s*(s\b|sec)")
          and num_in(raw, g.BUDGET_S, r"\s*(s\b|sec)"), "the 600 s, 10 s and 7200 s limits must appear")

    # --- the task, not the grader
    for term in GRADER_TERMS:
        i = scan.find(term)
        if i >= 0:
            FAILS.append("grader talk '%s': ...%s... (state it as a requirement or as setup)"
                         % (term.strip(), scan[max(0, i - 40):i + 40].replace("\n", " ").strip()))
        else:
            PASSED += 1
    for term in FORBIDDEN:
        i = scan.find(term)
        if i >= 0:
            FAILS.append("forbidden term '%s': ...%s..." % (term, scan[max(0, i - 40):i + 40].replace("\n", " ").strip()))
        else:
            PASSED += 1

    # --- prose, not a procedure; ASCII; no leftovers
    check(not re.search(r"^\s{0,3}#{1,6}\s", raw, re.M), "no markdown headings")
    check(len(re.findall(r"^\s*[-*]\s+\S", outside, re.M)) <= 8, "too many bullets")
    check("[[" not in raw and "FILL" not in raw, "a placeholder was left in the file")
    check(raw.isascii(), "non-ASCII characters present: %s" % sorted({c for c in raw if ord(c) > 127}))
    check(not re.search(r"\b(\w+)\s+\1\b", prose), "a word appears doubled (editing slip?)")
    check(not re.search(r"\b(we|our|us)\b", prose), "first person ('we', 'our', 'us')")
    check(not re.search(r"\b(you are|as the|role of)\b[^.]{0,40}\b(engineer|operator|consultant)", prose),
          "no role-play opening")
    check(not re.search(r"\b(tools|libraries) (are|is) available|available tools", prose), "drop the tools sentence")
    check("```" not in raw, "no fenced blocks; indent any example four spaces")
    check("\n\n\n" not in raw, "more than one blank line between paragraphs")
    for para in re.split(r"\n\s*\n", outside):
        s = " ".join(para.split())
        if not s or s.startswith(("-", "|")) or len(s) < 60:
            continue
        check(s[-1] in ".:;!?\"')`", "this paragraph ends mid-sentence: ...%s" % s[-56:])
    words = len(outside.split())
    check(WORD_MIN <= words <= WORD_MAX, "word count %d is outside %d-%d (prose only)" % (words, WORD_MIN, WORD_MAX))

    print("instruction: %s  (%d words of prose)" % (path, words))
    for w in WARNS:
        print("  WARN  " + w)
    if FAILS:
        print("\n%d FAILED of %d checks:" % (len(FAILS), PASSED + len(FAILS)))
        for f in FAILS:
            print("  FAIL  " + f)
        return 1
    print("\nclean: %d checks passed, %d warning(s)" % (PASSED, len(WARNS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "instruction.md")))
