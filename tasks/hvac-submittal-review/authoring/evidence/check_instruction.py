"""Mechanical checks on the hand-written instruction.md. Prose is never touched.

    python3 authoring/evidence/check_instruction.py [path]

Checks that every path, name, code and number the brief states agrees with the bundle (data files,
the verifier's constants, the verification service's budget, task.toml), that the closing sentence
is byte exact, that the file reads as prose rather than a procedure, that it is ASCII, and that
nothing giving the mechanism away appears. Standard library only; the sealed modules are read with
ast, never imported.
"""
import ast
import base64
import os
import re
import sys
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FAILS, WARNS, PASSED = [], [], 0

# eval-set marker the structure check rejects; stored encoded so this file does not carry it
MARKER = base64.b64decode("aGFyYm9yLWNhbmFyeQ==").decode()
# the instruction describes the task, not the grader (channel rule, Oct 14)
GRADER_TERMS = ["grader", "graded", "grading", "verifier", "scored", "scoring", "score ", "compared with",
                "compared to", "will be compared", "credit", "reward", "what counts", "is read", "are read",
                "evaluat", "hidden test", "test case"]
CLOSING = ("You have {t} seconds to complete this task. Do not cheat by using online "
           "solutions or hints specific to this task.")
DATA_FILES = ["owner/design_standard_23_05_10.docx", "architect/room_schedule.xlsx", "architect/addenda.pdf",
              "contractor/hvac_load_calcs.xlsx", "contractor/transmittal.docx",
              "manufacturer/rtx_catalog_performance.pdf"]
WORD_MIN, WORD_MAX = 250, 650
WORDS = {3: "three", 7: "seven", 8: "eight"}

# substrings that would hand over the mechanism, the rooms that matter or the method
FORBIDDEN = [
    "refurnish", "reorganis", "reorganiz", "headcount", "head count", "workstation", "room-size",
    "room size", "size band", "size class", "sibling", "identical room", "extrapolat", "drift", "seed",
    "stale", "out of date", "outdated", "superseded", "no longer describe", "server room", "split system",
    "ductless", "ac-1", "ro-2019", "2019", "2022", "instrument", "autoclave", "freezer", "copier",
    "workroom", "which rooms", "which items matter", "which eight", "largest", "smallest", "one of each",
    "one per", "campaign", "allocat", "trust the", "arithmetic", "to the watt", "reproduce", "correct on",
    "right on the", "already served", "served by an existing", "served by existing", "remains in service",
    "you should", "you may want", "make sure", "start by", "first,", "step 1", "step one", "hint", "tip",
    "trap", "careful", "beware", "note that", "remember", "class of room", "room class", "by use and size",
    "appendix", "ventilation efficiency", "zone outdoor", "62.1", "mixed air", "mixed-air", "mixture", "mixing",
    "bypass", "fan heat", "fan motor", "draw-through", "ahri", "rating point", "rated capacity", "gross",
    "entering dry", "dry coil", "interpolat", "psychrometr", "station pressure", "hyland", "ev ", "zpz",
]
# whole words only
FORBIDDEN_WORDS = ["lab", "labs", "infer", "inferred", "ratio", "ratios", "sample", "sampled", "2.1", "3.2",
                   "110", "112", "114", "116", "118", "142", "143", "144", "145", "160", "161",
                   "210", "220", "221", "222", "223", "230", "231", "232", "233"]


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
        m = re.search(r"^%s\s*=\s*([^\n]+)" % key, sec, re.M)
        return ast.literal_eval(m.group(1).strip())


def check(ok, msg):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILS.append(msg)


def has_number(body, n, unit_re=""):
    word = WORDS.get(int(n)) if float(n).is_integer() else None
    num = ("%g" % n).replace(".", r"\.")
    alts = [r"(?<![\d.])%s(?:\.0)?(?![\d])" % num]
    if word:
        alts.append(r"\b%s\b" % word)
    return re.search("(?:%s)%s" % ("|".join(alts), unit_re), body) is not None


def main(path):
    global PASSED
    if not os.path.exists(path):
        print("no instruction file at %s -- Alex writes it, by hand" % path)
        return 1
    raw = open(path, encoding="utf-8").read()
    body = raw.lower()
    # the deliverable example is an indented block; prose is everything else
    outside = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("    "))
    prose = outside.lower()

    timeout = int(float(toml_value(os.path.join(ROOT, "task.toml"), "agent", "timeout_sec")))
    grade = module_constants(os.path.join(ROOT, "tests", "grade.py"))
    service = module_constants(os.path.join(ROOT, "environment", "verify", "project.py"))
    sealed = module_constants(os.path.join(ROOT, "tests", "project.py"))

    # --- the bundle agrees with itself
    check(service.BUDGET == sealed.BUDGET, "BUDGET differs between the service and tests/project.py")
    for f in DATA_FILES:
        check(os.path.exists(os.path.join(ROOT, "environment", "data", f)), "environment/data/%s is missing" % f)
    for f in ("work_orders_2017_2025.csv", "asset_inventory.xlsx", "user_group_minutes.docx"):
        check(os.path.exists(os.path.join(ROOT, "environment", "data", "facilities", f)),
              "environment/data/facilities/%s is missing" % f)
    check("/app/review.json" in open(os.path.join(ROOT, "task.toml")).read(), "task.toml artifacts must list /app/review.json")

    # --- the closing sentence, byte exact
    want = CLOSING.format(t=timeout)
    check(raw.rstrip("\n").endswith(want), "the file must end with exactly:\n    " + want)
    check(raw.endswith("\n") and not raw.endswith("\n\n"), "exactly one trailing newline after the closing sentence")
    check("\n\n" + want in raw, "a blank line must precede the closing sentence")
    check(MARKER not in body, "an eval-set marker line is present (the structure check rejects it)")

    # --- paths, names, interface
    # inputs: where they are and which document sets the method; the rest the agent can discover (the Oct 15
    # quality review called a file-by-file tour removable). Any path that is named must be exact.
    check("/app/data" in raw, "say where the documents are: /app/data")
    check("/app/data/owner/design_standard_23_05_10.docx" in raw, "name the standard that sets the method by its absolute path")
    for m in re.findall(r"/app/data/[\w./-]+", raw):
        m = m.rstrip(".")
        check(os.path.exists(os.path.join(ROOT, "environment", "data", m[len("/app/data/"):])), "a named path does not exist: %s" % m)
    check("/app/review.json" in raw, "the deliverable /app/review.json must be named by absolute path")
    check("$VERIFY_URL" in raw, "the service address $VERIFY_URL must appear")
    check("start-verification" in raw, "say how the service is started: `start-verification`")
    check("$VERIFY_URL/status" in raw, "GET $VERIFY_URL/status must be given")
    check("$VERIFY_URL/verify?item=" in raw, "GET $VERIFY_URL/verify?item=<id> must be given")
    for s in ("room", "roof level", "existing unit"):
        check(s in body, "the item kinds must be listed: %s" % s)
    for s in ("area", "glazing", "roof assembly", "occupan", "nameplate", "serve"):
        check(s in body, "the field report's contents must be listed: %s" % s)
    b = service.BUDGET
    near = [m for m in re.finditer(r"\b(%d|%s)\b(?!\s*(%%|percent|per cent))" % (b, WORDS.get(b, "")), prose)
            if re.search(r"item|verif|request", prose[max(0, m.start() - 60):m.end() + 60])]
    check(bool(near), "the budget, at most %d items, must be stated next to the items or verifications" % b)
    check(re.search(r"repeat|again|same item|charged once", prose) is not None,
          "say that a repeated item is not charged again")
    for s in ("RTU-1", "RTU-7"):
        check(s in raw, "'%s' must appear" % s)
    check(re.search(r"\bseven\b|\b7\b", prose) is not None, "say there are seven units")

    # --- schema: what the grader parses
    for k in ["units", "submittal", "verdict", "missing", "approve", "return_for_revision"] + sorted(grade.TOL):
        check(k in raw, "the key or value '%s' must appear" % k)
    for v in sorted(grade.VERDICTS):
        check(v in raw, "the verdict '%s' must be listed" % v)
    for v in sorted(grade.MISSING):
        check(v in raw, "the missing-information code '%s' must be listed" % v)
    check(re.search(r"\bno (loads|quantities|values|numbers)\b|omit the (loads|quantities)|without (the )?(loads|quantities)|"
                    r"(loads|quantities) (are )?omitted", prose) is not None,
          "say that an undetermined unit reports no quantities")
    for s in ("block", "sensible", "latent", "net capacit", "kw", "outdoor air", "wet bulb", "wet-bulb"):
        if s in ("wet bulb", "wet-bulb"):
            continue
        check(s in prose, "'%s' must appear in the field meanings" % s.replace("capacit", "capacity"))
    check(re.search(r"as the standard defines|standard defines them|defined (in|by) the standard", prose) is not None,
          "say the verdicts and quantities are as the standard defines them")

    # --- grading, every fact
    check(re.search(r"wet[- ]bulb", prose) is not None, "the coil entering wet bulb must be named")
    # pass thresholds stay hidden (announcement, Nov 5; the Oct review of this task rejected stated tolerances):
    # no tolerance, percentage or allowed number of wrong units may appear
    check(re.search(r"\d\s*(%|percent|per cent)", prose) is None, "a percentage appears; the tolerances must stay hidden")
    for k, (kind, tol) in sorted(grade.TOL.items()):
        if kind == "abs":
            check(re.search(r"\b%s\s*k\b" % re.escape("%g" % tol), prose) is None,
                  "the tolerance %g K (%s) appears; it must stay hidden" % (tol, k))
    check(re.search(r"\btoleran|\bwithin\b|allowed to be wrong|at most \w+ units?|at least \w+ (of|units)", prose) is None,
          "a pass threshold is described; it must stay hidden")
    check(re.search(r"as it exists|as it stands|as[- ]built|existing condition|building as it is", prose) is not None,
          "say the review is made on the building as it exists")
    check("method" in prose and "standard" in prose, "say the review uses the standard's method")
    check(re.search(r"verdict[^.]{0,120}(standard|as defined)|(standard|as defined)[^.]{0,120}verdict", prose) is not None,
          "say each verdict is the one the standard gives")
    check(re.search(r"(each|every) verdict and (each |every )?quantity must be", prose) is not None,
          "say each verdict and quantity must be the one the standard's method gives")
    # every limit the verifier enforces on the file is stated (announcement, Nov 5)
    check("regular file" in prose, "say the review must be a regular file (a symlink fails)")
    check(re.search(r"only the keys|no other keys|exactly the keys", prose) is not None, "say no other keys are allowed")
    check(re.search(r"\bonce\b", prose) is not None, "say each key appears once (duplicates fail)")
    check("finite number" in prose, "say every quantity is a finite number")
    check(re.search(r"submittal[^.]{0,120}(must|follow|consistent|decision)|decision[^.]{0,80}submittal", prose) is not None,
          "say what the submittal decision must be")
    check(re.search(r"missing[^.]{0,120}(must|code|names)", prose) is not None,
          "say what the missing-information code must name for an undetermined unit")
    check(grade.ALLOW_WRONG == 0, "grade.ALLOW_WRONG is not 0; the brief's 'each verdict and quantity' would be wrong")

    # --- no tools sentence: the quality review called it removable (Oct 15)
    check(not re.search(r"\b(tools|libraries) (are|is) available|available tools", prose), "drop the tools sentence")

    # --- prose, not a procedure; ASCII; no leftovers
    check(not re.search(r"^\s{0,3}#{1,6}\s", raw, re.M), "no markdown headings")
    check(not re.search(r"^\s*\d+[.)]\s+\S", outside, re.M), "no numbered steps")
    check(len(re.findall(r"^\s*[-*]\s+\S", outside, re.M)) <= 8, "too many bullets; this should read as prose")
    check("[[" not in raw and "]]" not in raw, "a [[template slot]] was left in the file")
    check("FILL" not in raw and ">>>" not in raw, "a placeholder was left in the file")
    check(raw.isascii(), "non-ASCII characters present: %s" % sorted({c for c in raw if ord(c) > 127}))
    check(not re.search(r"\b(\w+)\s+\1\b", prose), "a word appears doubled (editing slip?)")
    check(not re.search(r"\b(we|our|us)\b", prose), "first person ('we', 'our', 'us')")
    check("```" not in raw, "no fenced blocks; indent the example four spaces")
    # formatting an editor can strip: code spans on paths and identifiers, a contiguous example block
    for m in set(re.findall(r"/app/data/[\w./-]*\w/?", raw)):
        check("`%s`" % m in raw or "`%s" % m in raw, "the path %s must be in a code span (backticks lost?)" % m)
    check("`$VERIFY_URL/verify?item=<id>`" in raw or "`GET $VERIFY_URL/verify?item=<id>`" in raw,
          "<id> outside a code span disappears when the markdown is rendered")
    blk = re.search(r"(?m)^    \{\n(.*?)^    \}$", raw, re.S)
    check(blk is not None and "\n\n" not in blk.group(1), "blank lines inside the indented example (editor artefact?)")
    check("\n\n\n" not in raw, "more than one blank line between paragraphs")
    for para in re.split(r"\n\s*\n", outside):
        s = " ".join(para.split())
        if not s or s.startswith(("-", "|")) or len(s) < 60:
            continue
        check(s[-1] in ".:;!?\"')`", "this paragraph ends mid-sentence: ...%s" % s[-56:])
    words = len(outside.split())
    check(WORD_MIN <= words <= WORD_MAX, "word count %d is outside %d-%d (prose only)" % (words, WORD_MIN, WORD_MAX))
    if "section" in prose:
        WARNS.append("'section' appears; pointing at a section of the standard is a hint")

    # --- describe the task, not the grader
    for term in GRADER_TERMS:
        i = body.replace(want.lower(), "").find(term)
        if i >= 0:
            sc = body.replace(want.lower(), "")
            FAILS.append("grader talk '%s': ...%s... (state it as a requirement of the task)"
                         % (term.strip(), sc[max(0, i - 40):i + 40].replace("\n", " ").strip()))
        else:
            PASSED += 1

    # --- nothing that gives the mechanism away (the closing sentence is exempt: it says "hints")
    scan = body.replace(want.lower(), "")
    for term in FORBIDDEN:
        if term in scan:
            i = scan.index(term)
            FAILS.append("forbidden term '%s': ...%s..." % (term, scan[max(0, i - 40):i + 40].replace("\n", " ").strip()))
        else:
            PASSED += 1
    for term in FORBIDDEN_WORDS:
        m = re.search(r"(?<![\w.-])%s(?![\w.-])" % re.escape(term), scan)
        if m:
            i = m.start()
            FAILS.append("forbidden word '%s': ...%s..." % (term, scan[max(0, i - 40):i + 40].replace("\n", " ").strip()))
        else:
            PASSED += 1

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
