"""Mechanical checks of the bundle against the rules it is built to. Run from anywhere:

    python3 authoring/evidence/preflight.py

Each line is `ok` or `FAIL`. The last line is `preflight clean` or the number of failures. Nothing here runs
the program or regenerates data: it reads the bundle's files and the committed evidence.
"""
import sys

sys.dont_write_bytecode = True
import ast
import hashlib
import json
import os
import re
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(BUNDLE, "tests"))
sys.path.insert(0, os.path.join(BUNDLE, "authoring", "provenance"))
import check_program  # noqa: E402
import cells  # noqa: E402

failures = []


def check(holds, what):
    print("%s %s" % ("ok  " if holds else "FAIL", what))
    if not holds:
        failures.append(what)


def read(*parts):
    with open(os.path.join(BUNDLE, *parts), errors="replace") as handle:
        return handle.read()


def evidence(name):
    path = os.path.join(HERE, name + ".txt")
    return read("authoring", "evidence", name + ".txt") if os.path.exists(path) else ""


CLOSE = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
         "specific to this task.")
ROOT = {"README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"}

# 1. what the bundle holds
check(set(os.listdir(BUNDLE)) == ROOT, "the bundle holds README.md, instruction.md, task.toml, authoring, environment, solution, tests and nothing else")
stray, upper, nonascii = [], [], []
for base, dirs, files in os.walk(BUNDLE):
    for name in dirs + files:
        rel = os.path.relpath(os.path.join(base, name), BUNDLE)
        stem = name.split(".")[0]
        if name == "__pycache__" or name.endswith((".pyc", ".zip")) or name.startswith("."):
            stray.append(rel)
        if name not in ("README.md", "Dockerfile") and stem.isupper() and any(ch.isalpha() for ch in stem):
            upper.append(rel)
    for name in files:
        if name.endswith(".npy"):
            continue
        with open(os.path.join(base, name), "rb") as handle:
            raw = handle.read()
        try:
            raw.decode("ascii")
        except UnicodeDecodeError:
            nonascii.append(os.path.relpath(os.path.join(base, name), BUNDLE))
check(not stray, "no caches, dotfiles or zips%s" % ("" if not stray else ": %s" % stray[:3]))
check(not upper, "no all-uppercase names but README.md and Dockerfile%s" % ("" if not upper else ": %s" % upper[:3]))
check(not nonascii, "every text file is ASCII%s" % ("" if not nonascii else ": %s" % nonascii[:3]))

# 2. no encoded strings: the names below are listed in order to forbid them
decoders = {"base64", "binascii", "codecs", "zlib", "marshal", "bz2", "lzma"}
calls = {"b64decode", "b32decode", "b16decode", "a85decode", "b85decode", "unhexlify", "a2b_base64", "fromhex", "decompress"}
encoded = []
for base, _, files in os.walk(BUNDLE):
    for name in files:
        if not name.endswith(".py"):
            continue
        tree = ast.parse(read(os.path.relpath(os.path.join(base, name), BUNDLE)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name.split(".")[0] in decoders for alias in node.names):
                encoded.append(name)
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in decoders:
                encoded.append(name)
            if isinstance(node, ast.Call):
                fn = node.func
                called = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
                if called in calls:
                    encoded.append(name)
check(not encoded, "no decoding module or call in any Python file%s" % ("" if not encoded else ": %s" % sorted(set(encoded))))

# 3. instruction.md
ins = read("instruction.md")
body = ins.replace(CLOSE, "")
check(ins.rstrip("\n").endswith("\n\n" + CLOSE), "the instruction's last paragraph is the closing sentence")
check(not re.search(r"^\s{0,3}#", ins, re.M), "the instruction has no heading")
grading = re.findall(r"\b(grader|graded|grading|verifier|reward|score[sd]?|scoring|partial credit|tested|pass(?:es|ed)?|fail(?:s|ed)?)\b", body, re.I)
check(not grading, "the instruction has no grading words%s" % ("" if not grading else ": %s" % sorted(set(grading))))
check(not re.search(r"\b(you|your|we|our|I)\b", body), "the instruction has no first or second person outside the closing sentence")
limit = check_program.RUN_LIMIT_S
check("Each run of indicate.py must finish within %d seconds on 1 CPU." % limit in ins,
      "the instruction gives the limit in the announcement's words, with the checker's %d s" % limit)
found = re.findall(r"must finish within (\d+) seconds", ins)
check(found == [str(limit)], "the instruction names one limit and it is the checker's")
check("`%s`" % ",".join(check_program.HEADER) in ins, "the instruction gives the header the checker reads")
for path in ("/app/data/docs/is2_indicating.md", "/app/data/docs/cell_package.md", "/app/data/examples/cell_03",
             "/app/data/examples/cell_08", "/app/data/pending/cell_11", "/app/data/pending/cell_13", "/app/output/indicate.py"):
    check(path in ins and os.path.exists(os.path.join(BUNDLE, "environment", path[len("/app/"):])) or path == "/app/output/indicate.py" and path in ins,
          "the instruction names %s and it exists" % path)
bands = check_program.BANDS
stated = {"imep_bar": r"mean effective pressure must be within (\d+(?:\.\d+)?) per cent", "pmax_bar": r"peak pressure within (\d+(?:\.\d+)?) per cent",
          "q_gross_J": r"heat released within (\d+(?:\.\d+)?) per cent", "apmax_deg": r"each within (\d+(?:\.\d+)?) degrees"}
for name, pattern in stated.items():
    m = re.search(pattern, ins)
    want = bands[name][1] * (100 if bands[name][0] == "share" else 1)
    check(bool(m) and abs(float(m.group(1)) - want) < 1e-9, "the instruction's figure for %s is the checker's band" % name)
check(bands["apmax_deg"] == bands["ca10_deg"] == bands["ca50_deg"], "the three angles share one band")
is2 = read("environment", "data", "docs", "is2_indicating.md")
m = re.search(r"issued to\s+(\S+) degrees on angles, (\S+) per cent on peak pressure, (\S+) per cent on mean effective pressure and (\S+) per cent on\s+heat released", is2)
check(bool(m) and [float(x) for x in m.groups()] == [bands["apmax_deg"][1], 100 * bands["pmax_bar"][1], 100 * bands["imep_bar"][1], 100 * bands["q_gross_J"][1]],
      "IS-2 section 9 gives the same four figures")
check("up to 6 cylinders and 20,000 cycles" in ins, "the instruction states the largest package")

# 4. the agent's documents say what was done and never what is off
visible = ins + is2 + read("environment", "data", "docs", "cell_package.md")
told = [w for w in ("index", "gain", "sensitiv", "calibrat", "misalign", "fault", "phasing", "offset", "drift", "wrong",
                    "error", "suspect", "verify", "check", "correct") if re.search(w, visible, re.I)]
check(not told, "no agent-visible text names an index, a gain, an error or a check%s" % ("" if not told else ": %s" % told))
for c in cells.CELLS:
    if c["role"] == "hidden":
        continue
    with open(os.path.join(BUNDLE, cells.PLACE[c["role"]], c["cell"], "engine.json")) as handle:
        keys = set(json.load(handle))
    check(keys == {"cell", "cylinders", "bore_mm", "stroke_mm", "conrod_mm", "compression_ratio", "ivc_deg", "evo_deg", "bar_per_count"},
          "%s: engine.json holds the documented fields only" % c["cell"])

# 5. task.toml and README.md
with open(os.path.join(BUNDLE, "task.toml"), "rb") as handle:
    toml = tomllib.load(handle)
meta = toml.get("metadata", {})
name = toml.get("task", {}).get("name", "")
task = os.path.basename(BUNDLE)
check(name.count("/") == 1 and name.split("/")[1] == "engine-indicating-analysis" and len(name.split("/")[1].split("-")) <= 3,
      "task name is <prefix>/engine-indicating-analysis, three words")
prefix = name.split("/")[0]
elsewhere = []
for base, _, files in os.walk(BUNDLE):
    for fname in files:
        if fname.endswith(".npy"):
            continue
        for k, line in enumerate(read(os.path.relpath(os.path.join(base, fname), BUNDLE)).splitlines(), 1):
            if prefix and prefix.lower() in line.lower() and not (fname == "task.toml" and line.strip().startswith("name =")):
                elsewhere.append("%s:%d" % (fname, k))
check(not elsewhere, "the name's prefix appears nowhere but task.toml's name line%s" % ("" if not elsewhere else ": %s" % elsewhere[:3]))
check(toml.get("artifacts") == ["/app/output/indicate.py"], "the artifact is /app/output/indicate.py")
check(toml.get("agent", {}).get("timeout_sec") == 28800.0 and toml.get("agent", {}).get("user") == "agent", "agent: 28800 s, user agent")
check(toml.get("verifier", {}).get("timeout_sec") == 600.0 and toml.get("verifier", {}).get("environment_mode") == "separate"
      and toml.get("verifier", {}).get("environment", {}).get("network_mode") == "no-network", "verifier: 600 s, separate, no network")
check(meta.get("domain") == "engineering-sciences" and meta.get("field") == "mechanical-engineering", "domain and field")
check(meta.get("category") == "Science" and bool(str(meta.get("subcategory", "")).strip()), 'category "Science" and a subcategory')
check(0 < len(str(meta.get("subfield", ""))) <= 120, "subfield is at most 120 characters (%d)" % len(str(meta.get("subfield", ""))))
needed = ["author_name", "author_email", "author_organization", "author_profile", "research_advisor", "referred_by",
          "conflicts_of_interest", "domain", "field", "subfield", "category", "subcategory", "tags", "expert_time_estimate_hours",
          "relevant_experience", "difficulty_explanation", "solution_explanation", "verification_explanation"]
check(all(k in meta for k in needed), "[metadata] carries the full block")
check(toml.get("task", {}).get("keywords") == meta.get("tags"), "keywords equal tags")
readme = read("README.md")


def section(head, nxt):
    return readme.split(head, 1)[1].split(nxt, 1)[0].strip() if head in readme else ""


parts = {"difficulty_explanation": section("## Difficulty", "\n## Reference solution"),
         "solution_explanation": section("## Reference solution", "\n## Verification").split("\n\n`solution/solve.sh` starts")[0].strip(),
         "verification_explanation": section("## Verification", "\nEvidence (`authoring/evidence/`)")}
for key, text in parts.items():
    check(len(text) > 400 and str(meta.get(key, "")).strip() == text, "%s is the README's section word for word" % key)
diff = parts["difficulty_explanation"]
check("synthetic" in diff and "realistic" in diff and not re.search(r"\broutine\b", diff, re.I), "the difficulty text says synthetic and realistic and never routine")
check(not re.search(r"\b\d+ of \d+ (probes?|runs|trials)|low effort|xhigh|solved", diff, re.I), "the difficulty text carries no agent-performance figures")
worst_limit = max(c["cyl"] * c["points"] * cells.CYCLES[c["role"]] for c in cells.CELLS)
check(worst_limit <= 20000, "no package is larger than the 20,000 cycles the instruction states (largest %d)" % worst_limit)

# 6. the verifier's literals and the limit
tdock, tsh = read("tests", "Dockerfile"), read("tests", "test.sh")
lines = [line.strip() for line in tdock.splitlines()]
for literal in ("RUN mkdir -p /app/output", "COPY . /tests/", "WORKDIR /tests", "ENV PYTHONUNBUFFERED=1"):
    check(literal in lines, "tests/Dockerfile has `%s` on a line of its own" % literal)
pins = tdock + read("tests", "requirements.txt")
for pin in ("numpy==2.1.3", "scipy==1.14.1", "pandas==2.2.3", "pytest==8.4.1", "pytest-json-ctrf==0.3.5"):
    check(pin in pins and pin in tdock, "verifier pin %s, also spelt in tests/Dockerfile" % pin)
for literal in ("mkdir -p /logs/verifier", "--ctrf=/logs/verifier/ctrf.json", "-p no:cacheprovider"):
    check(literal in tsh, "tests/test.sh has `%s`" % literal)
writes = [line for line in tsh.splitlines() if "reward.txt" in line and not line.strip().startswith(("#", "rm "))]
check(writes and all(line in ('echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt') for line in writes)
      and writes[0].endswith('"0" > /logs/verifier/reward.txt') and sum('"1"' in line for line in writes) == 1,
      "every reward write is the literal write at the start of a line; 0 is written first, 1 in one place")
checker = read("tests", "check_program.py")
check("started.wait(timeout=limit)" in checker and "except subprocess.TimeoutExpired:" in checker, "the limit is a timeout on the wait for the run, in tests/")
after = checker.split("except subprocess.TimeoutExpired:", 1)[1].split("\n", 2)[1]
check("over the limit" in after and 'if ending == "over the limit":' in checker and "return report" in checker.split('if ending == "over the limit":', 1)[1][:400],
      "a run over the limit ends the assessment: no table is read and no later cell is run")
check(all(('"%s": "1"' % v) in checker for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")),
      "runs have OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1")
check("setaffinity" not in checker and "taskset" not in checker + tsh, "the verifier sets no CPU affinity (several verifiers may share a host)")
m = re.search(r"at most (\d+) MiB \(([\d,]+) bytes\)", ins)
check(bool(m) and int(m.group(1)) * 1024 * 1024 == check_program.TABLE_BYTES == int(m.group(2).replace(",", "")),
      "the instruction states the reader's cap on OUT_CSV, and it is the checker's (%d bytes)" % check_program.TABLE_BYTES)
check("O_NOFOLLOW" in checker and "ordinary file, not a link" in ins, "the instruction says OUT_CSV is an ordinary file, not a link, as the reader requires")
check("setpriv" in checker and "chmod -R u=rwX,go= /tests" in tdock, "the program runs as nobody and /tests is root's alone")
edock = read("environment", "Dockerfile")
check("numpy==2.1.3 scipy==1.14.1 pandas==2.2.3" in edock and "useradd" in edock and "agent" in edock
      and not [line for line in edock.splitlines() if line.strip()][-1].upper().startswith("USER "), "the agent image: the pins, the user agent, ends as root")
check(not os.path.exists(os.path.join(BUNDLE, "environment", "data", "pending", "cell_11", "expected.csv"))
      and not os.path.exists(os.path.join(BUNDLE, "environment", "data", "pending", "cell_13", "expected.csv")), "the pending packages carry no results")
leaked = [name for base, _, files in os.walk(os.path.join(BUNDLE, "environment")) for name in files
          if name in ("manifest.json", "cells.py", "cylinder.py") or "results" in base]
check(not leaked, "nothing sealed sits under environment/")

# 7. the data are the generator's, and the manifest lists them
with open(os.path.join(BUNDLE, "authoring", "provenance", "manifest.json")) as handle:
    book = json.load(handle)
wrong = 0
listed = 0
for entry in book["cells"]:
    for rel, facts in entry["files"].items():
        listed += 1
        path = os.path.join(BUNDLE, rel)
        if not os.path.exists(path):
            wrong += 1
            continue
        with open(path, "rb") as handle:
            wrong += hashlib.sha256(handle.read()).hexdigest() != facts["sha256"]
check(wrong == 0 and listed > 100, "all %d data files listed in manifest.json are present with the listed SHA-256" % listed)
table = {c["cell"]: c for c in cells.CELLS}
check(all(table[e["cell"]]["index_deg"] == e["index_deg"] and table[e["cell"]]["gain"] == e["gain"] and table[e["cell"]]["role"] == e["role"]
          for e in book["cells"]) and len(book["cells"]) == len(cells.CELLS), "manifest.json gives each cell's role, index and gain as the generator has them")

# 8. the committed evidence
texts = {name: evidence(name) for name in ("regenerate", "design_rules", "reference_run", "route_run", "slow_run", "null_run",
                                            "seed_screen", "verifier_checks", "verifier_run")}
for name, text in texts.items():
    check(bool(text) and not re.search(r"UNEXPECTED|PROBLEM|Traceback|FAILS", text), "%s.txt is there and reports no failure" % name)
check(re.search(r"\n(\d+) files, 0 different", texts["regenerate"]) is not None, "regenerate: every shipped data file is what the generator writes")
check(re.search(r"\n(\d+) rules, 0 not holding", texts["design_rules"]) is not None, "design rules: all hold")
ref = texts["reference_run"]
m = re.search(r"runs take (\S+) to (\S+) s; the limit of (\d+) s is (\S+) times the slowest", ref)
check(bool(m) and int(m.group(3)) == limit and 2.0 <= float(m.group(4)) <= 3.5 and float(m.group(2)) >= 1.0,
      "reference: accepted; its slowest run is over 1 s and the limit is 2 to 3.5 times it%s" % ("" if not m else " (%s s, %s times)" % (m.group(2), m.group(4))))
check(ref.count("\naccepted") >= 2 and "not accepted" not in ref, "reference: accepted on the six cells and on both examples")
m = re.search(r"widest departure at any row of any cell: (\S+) of its band", ref)
ref_wide = float(m.group(1)) if m else 9.0
slow = texts["slow_run"]
m = re.search(r"widest departure from the sealed results: (\S+) of a band", slow)
slow_wide = float(m.group(1)) if m else 9.0
m = re.search(r"widest departure of any sound variation: (\S+) of a band", texts["route_run"])
sound_wide = float(m.group(1)) if m else 9.0
m = re.search(r"widest departure on any seed (\S+) of a band", texts["seed_screen"])
seed_wide = float(m.group(1)) if m else 9.0
check(max(ref_wide, slow_wide, sound_wide) <= 0.5, "every band is at least twice the widest departure of a sound method "
      "(reference %.2f, second solution %.2f, sound variations %.2f of a band)" % (ref_wide, slow_wide, sound_wide))
check(re.search(r"20 seeds, 20 accepted", texts["seed_screen"]) is not None and seed_wide < 1.0, "seed screen: the reference is accepted on 20 of 20 seeds (widest %.2f of a band)" % seed_wide)
check("still running after %d s" % limit in slow and re.search(r"cells run: 1 of 6", slow) is not None and slow.rstrip().endswith("cells run: 1 of 6"),
      "the second solution, correct and slow, is stopped at the limit on the first cell and not accepted")
m = re.search(r"(\S+) to (\S+) times the limit", slow)
check(bool(m) and float(m.group(1)) >= 3.0, "the second solution would need at least 3 times the limit on every cell%s" % ("" if not m else " (%s to %s times)" % m.groups()))
route = texts["route_run"]
check(re.search(r"\n(\d+) routes, 0 accepted; (\d+) sound variations, 0 not accepted", route) is not None, "routes: none accepted; sound variations: all accepted")
stops = dict(re.findall(r"  (cell_\d+) \(([^)]*)\): (\d+) of \d+", route) and [(a, int(c)) for a, b, c in re.findall(r"  (cell_\d+) \(([^)]*)\): (\d+) of \d+", route)])
conditioned = [c["cell"] for c in cells.CELLS if c["role"] == "hidden" and (c["index_deg"] or c["gain"] != 1)]
check(all(stops.get(cell, 0) >= 3 for cell in conditioned), "every cell with a condition stops at least 3 routes (%s)" % ", ".join("%s %d" % (c, stops.get(c, 0)) for c in conditioned))
least = [float(x) for x in re.findall(r"its widest departure is (\S+) bands", route)]
check(bool(least) and min(least) >= 1.5, "the nearest route misses by at least 1.5 bands (%.1f)" % (min(least) if least else 0))
check(re.search(r"2 programs, 0 accepted; most rows right: 0 of 250", texts["null_run"]) is not None, "programs without physics get no row right")
check(re.search(r"\n(\d+) cases, 0 unexpected", texts["verifier_checks"]) is not None, "verifier checks: none unexpected")
check(re.search(r"\n4 programs, 0 unexpected", texts["verifier_run"]) is not None, "the whole verifier: the reference passes, three others do not")
check("bash tests/test.sh" in texts["verifier_run"] and re.search(r"the reference, solution/indicate\.py\s+reward 1\b", texts["verifier_run"]) is not None,
      "the whole-verifier study runs bash tests/test.sh itself, and the reference reaches reward 1 through it")

# 9. every figure the README quotes is in the evidence, the documents, the generator or the checker
corpus = " ".join(texts.values()) + visible + read("authoring", "provenance", "cells.py") + checker + read("tests", "requirements.txt") + tsh
corpus += " ".join(read("authoring", "evidence", f) for f in ("slow_indicate.py", "variants.py")) + read("solution", "indicate.py")
quoted = set(re.findall(r"(?<![\w.])\d+\.\d+|(?<![\w.,])\d{3,}(?:,\d{3})?(?![\w.])", readme.replace("SHA-256", "")))
missing = sorted(q for q in quoted if q not in corpus and q.replace(",", "") not in corpus)
check(not missing, "every decimal or three-digit figure in README.md occurs in the evidence, the documents or the code%s" % (
    "" if not missing else ": %s" % missing[:12]))

print("\n%s" % ("preflight clean" if not failures else "%d failed" % len(failures)))
sys.exit(1 if failures else 0)
