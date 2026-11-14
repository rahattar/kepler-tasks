"""Every rule the bundle has to meet before it is packed, checked against the files themselves.

    python3 preflight.py > preflight.txt        as root, from anywhere

A line that starts "ok" is a rule that holds; "FAILS" is one that does not, and the script then ends with
status 1. The rules come from the repository's playbook and from the intake's asks of 11 November 2026: the
bundle's layout, the instruction's form and its agreement with the verifier, task.toml, the verifier's
literals, the time limit, the data and their manifest, and what each study under authoring/evidence reports.
At the end the reference is run once more through the verifier's bench, under the umask test.sh sets.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
EVIDENCE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(EVIDENCE))
TESTS = os.path.join(BUNDLE, "tests")
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.join(BUNDLE, "authoring", "provenance"))
import rope_bench  # noqa: E402
import works as generator  # noqa: E402
import design_rules  # noqa: E402

TASK = "rope-bending-damage"
PROGRAM = "ropes.py"
CLOSING = "You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task."
GRADING_WORDS = r"\b(grader|graders|grading|graded|verifier|verify|verified|reward|score|scored|scoring|pass|passes|passed|passing|fail|fails|failed|failing|tested|test case|test cases|partial credit)\b"
results = []


def rule(holds, text):
    results.append(bool(holds))
    print(("ok     " if holds else "FAILS  ") + text)


def text_of(*parts):
    with open(os.path.join(BUNDLE, *parts), encoding="utf-8") as handle:
        return handle.read()


def study(name):
    path = os.path.join(EVIDENCE, name + ".txt")
    return text_of("authoring", "evidence", name + ".txt") if os.path.exists(path) else ""


def every_file():
    for base, folders, names in os.walk(BUNDLE):
        for name in names:
            yield os.path.relpath(os.path.join(base, name), BUNDLE)


print("the bundle\n")
rule(sorted(os.listdir(BUNDLE)) == sorted(["README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"]),
     "the bundle holds README.md, instruction.md, task.toml, authoring, environment, solution and tests, and nothing else")
files = sorted(every_file())
stray = [f for f in files if f.endswith((".pyc", ".zip", ".log", ".orig")) or "__pycache__" in f.split(os.sep)
         or any(part.startswith(".") for part in f.split(os.sep))]
rule(not stray, "no caches, dotfiles, logs or zips%s" % ("" if not stray else ": " + ", ".join(stray[:3])))
upper = [f for f in files for part in f.split(os.sep) if part not in ("README.md", "Dockerfile") and re.sub(r"\.[a-z0-9]+$", "", part).isupper()]
rule(not upper, "no all-uppercase names but README.md and Dockerfile%s" % ("" if not upper else ": " + ", ".join(upper[:3])))
rule(all(re.fullmatch(r"[A-Za-z0-9_./-]+", f) for f in files), "every path is plain ASCII letters, digits, dots, hyphens and underscores")
not_ascii = []
for f in files:
    with open(os.path.join(BUNDLE, f), "rb") as handle:
        if any(byte > 127 for byte in handle.read()):
            not_ascii.append(f)
rule(not not_ascii, "every file is ASCII%s" % ("" if not not_ascii else ": " + ", ".join(not_ascii[:3])))
encoders = []
for f in files:
    if f.endswith(".py"):
        tree = ast.parse(text_of(f))
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, (ast.Import, ast.ImportFrom)) else []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            if any(n.split(".")[0] in ("base64", "codecs", "binascii", "zlib", "marshal", "pickle") for n in names):
                encoders.append(f)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("b64decode", "decompress", "fromhex"):
                encoders.append(f)
rule(not encoders, "no Python file imports an encoding or packing module or decodes a string%s" % ("" if not encoders else ": " + ", ".join(sorted(set(encoders)))))
rule(len(TASK.split("-")) <= 3, "the task's name has at most three hyphenated words")

print("\nthe instruction\n")
ins = text_of("instruction.md")
body = ins.rstrip("\n")[: -len(CLOSING)] if ins.rstrip("\n").endswith(CLOSING) else ins
rule(ins.rstrip("\n").endswith("\n\n" + CLOSING), "its last paragraph is the closing sentence, exactly")
rule(not re.search(r"^\s{0,3}#", ins, re.M), "it has no heading")
graded = re.findall(GRADING_WORDS, body, re.I)
rule(not graded, "it has no grading word%s" % ("" if not graded else ": " + ", ".join(sorted(set(g if isinstance(g, str) else g[0] for g in graded)))))
rule(not re.search(r"\b(you|your|yours|we|our|us|I|me|my)\b", body), "it has no first or second person before the closing sentence")
rule(not re.search(r"\byou are\b|\bas an?\b [a-z ]*engineer", body, re.I), "it gives no role")
limit = rope_bench.LIMIT_S
rule("Each run of %s must finish within %d seconds on 1 CPU." % (PROGRAM, limit) in ins,
     "it says \"Each run of %s must finish within %d seconds on 1 CPU.\", with the bench's LIMIT_S" % (PROGRAM, limit))
rule(re.findall(r"within (\d+) seconds", ins) == [str(limit)], "it names one time limit, the bench's")
rule("`%s`" % rope_bench.SHEET_HEADER in ins, "it gives the header the reader holds, `%s`" % rope_bench.SHEET_HEADER)
m = re.search(r"within (\d+) per cent of the greatest damage of that rope", ins)
rule(bool(m) and int(m.group(1)) / 100.0 == rope_bench.SHARE == generator.BAND,
     "its accuracy, %s per cent of the rope's greatest damage, is the bench's SHARE and the generator's BAND" % (m.group(1) if m else "?"))
m = re.search(r"at most (\d+) MiB \(([\d,]+) bytes\)", ins)
rule(bool(m) and int(m.group(1)) * 1024 * 1024 == rope_bench.SHEET_CAP == int(m.group(2).replace(",", "")),
     "the size cap it states is the reader's, %d bytes" % rope_bench.SHEET_CAP)
rule("an ordinary file, not a link" in ins and "O_NOFOLLOW" in text_of("tests", "rope_bench.py"),
     "it says OUT_CSV is an ordinary file, not a link, which the reader requires")
rule("up to %d cranes, %s movements" % (design_rules.STATED_CRANES, format(design_rules.STATED_MOVEMENTS, ",")) in ins
     and "ropes of up to %d m" % design_rules.STATED_ROPE_M in ins,
     "it states the largest package as design_rules.py holds the six works to (%d cranes, %s movements, %d m)"
     % (design_rules.STATED_CRANES, format(design_rules.STATED_MOVEMENTS, ","), design_rules.STATED_ROPE_M))
paths = re.findall(r"`(/app/[^`]+)`", ins)
missing = [p for p in paths if p != "/app/output/" + PROGRAM and not os.path.exists(os.path.join(BUNDLE, "environment", p[len("/app/"):]))]
rule(paths and not missing and "/app/output/" + PROGRAM in paths, "every /app path it names is shipped, and it names /app/output/%s%s" % (PROGRAM, "" if not missing else ": missing " + ", ".join(missing)))
for kind in ("examples", "pending"):
    for name in sorted(os.listdir(os.path.join(BUNDLE, "environment", "data", kind))):
        rule("/app/data/%s/%s" % (kind, name) in ins, "it names /app/data/%s/%s by its absolute path" % (kind, name))
for doc in sorted(os.listdir(os.path.join(BUNDLE, "environment", "data", "docs"))):
    rule("/app/data/docs/%s" % doc in ins, "it names /app/data/docs/%s by its absolute path" % doc)
for phrase in ("python3 %s WORKS_DIR OUT_CSV" % PROGRAM, "exit status has to be 0", "only `%s` has been copied" % PROGRAM, "unprivileged", "no network",
               "cannot be written to", "numpy, scipy and pandas"):
    rule(phrase in ins, "it says \"%s\", as the bench runs the program" % phrase)
seen_text = ins + "".join(text_of("environment", "data", "docs", d) for d in sorted(os.listdir(os.path.join(BUNDLE, "environment", "data", "docs"))))
standard = text_of("environment", "data", "docs", "rs4_rope_bending.md")
stated = ["turned end for end", "taken from the dead end", "the mirror image", "where the\nrope goes on thinning"]
rule(all(phrase in standard for phrase in stated),
     "RS-4 states both conditions that decide hidden works, the turn and the survey from the dead end, and the criterion that tells them apart")

print("\ntask.toml and the README\n")
toml = tomllib.loads(text_of("task.toml"))
meta = toml.get("metadata", {})
name = toml.get("task", {}).get("name", "")
prefix = name.split("/")[0] if name.count("/") == 1 else ""
rule(prefix and name.split("/")[1] == TASK, "the name is <prefix>/%s, with the prefix every task of the repository uses" % TASK)
elsewhere = []
for f in files:
    with open(os.path.join(BUNDLE, f), errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            if prefix and prefix.lower() in line.lower() and not (f == "task.toml" and line.startswith("name = ")):
                elsewhere.append("%s:%d" % (f, number))
rule(not elsewhere, "the name's prefix appears nowhere but task.toml's name line%s" % ("" if not elsewhere else ": " + ", ".join(elsewhere[:3])))
rule(toml.get("artifacts") == ["/app/output/" + PROGRAM], "the artifact is /app/output/%s" % PROGRAM)
rule(toml.get("agent", {}).get("timeout_sec") == 28800.0 and toml.get("agent", {}).get("user") == "agent", "agent: 28800 s, as the user agent")
rule(toml.get("verifier", {}).get("timeout_sec") == 600.0 and toml.get("verifier", {}).get("environment_mode") == "separate"
     and toml.get("verifier", {}).get("environment", {}).get("network_mode") == "no-network", "verifier: 600 s, a separate environment, no network")
rule(meta.get("domain") == "engineering-sciences" and meta.get("field") == "mechanical-engineering", "domain engineering-sciences, field mechanical-engineering")
rule(meta.get("category") == "Science" and str(meta.get("subcategory", "")).strip(), "category Science, and a subcategory")
rule(0 < len(str(meta.get("subfield", ""))) <= 120, "the subfield is 1 to 120 characters (%d)" % len(str(meta.get("subfield", ""))))
block = ["author_name", "author_email", "author_organization", "author_profile", "research_advisor", "referred_by",
         "conflicts_of_interest", "domain", "field", "subfield", "category", "subcategory", "tags", "expert_time_estimate_hours",
         "relevant_experience", "difficulty_explanation", "solution_explanation", "verification_explanation"]
rule(all(k in meta for k in block), "[metadata] carries the whole block%s" % ("" if all(k in meta for k in block) else ": missing " + ", ".join(k for k in block if k not in meta)))
rule(toml.get("task", {}).get("keywords") == meta.get("tags"), "keywords are the tags")
readme = text_of("README.md")


def section(head, after):
    return readme.split(head, 1)[1].split(after, 1)[0].strip() if head in readme and after in readme.split(head, 1)[1] else ""


sections = {"difficulty_explanation": section("## Difficulty", "\n## Reference solution"),
            "solution_explanation": section("## Reference solution", "\n## Verification").split("\n\n`solution/solve.sh` starts")[0].strip(),
            "verification_explanation": section("## Verification", "\nEvidence (`authoring/evidence/`)")}
for key, words in sections.items():
    rule(len(words) > 400 and str(meta.get(key, "")).strip() == words, "%s is the README's section, word for word" % key)
difficulty = sections["difficulty_explanation"]
rule("synthetic" in difficulty and "realistic" in difficulty and not re.search(r"\broutine\b", difficulty, re.I),
     "the difficulty text says the data are synthetic and realistic, and never calls the work routine")
rule(not re.search(r"\b\d+ (of|out of) \d+ (probes?|runs|trials|attempts)|low effort|xhigh|\bsolved\b|\bsolve rate", readme, re.I),
     "the README carries no agent-performance figures")
rule("## Submission notes" in readme and "tests/works" in readme and "authoring/provenance/works.py" in readme,
     "the README's submission notes say what the hidden shift is and where it is built")

print("\nthe verifier\n")
tdock = text_of("tests", "Dockerfile")
tsh = text_of("tests", "test.sh")
bench = text_of("tests", "rope_bench.py")
lines = [line.strip() for line in tdock.splitlines()]
for literal in ("RUN mkdir -p /app/output", "COPY . /tests/", "WORKDIR /tests"):
    rule(literal in lines, "tests/Dockerfile has `%s` on a line of its own" % literal)
rule(re.search(r"^ENV PYTHONUNBUFFERED=1$", tdock, re.M) is not None, "tests/Dockerfile has `ENV PYTHONUNBUFFERED=1`")
for pin in ("numpy==2.1.3", "scipy==1.14.1", "pandas==2.2.3", "pytest==8.4.1", "pytest-json-ctrf==0.3.5"):
    rule(pin in tdock, "tests/Dockerfile pins %s" % pin)
for literal in ('echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt', "mkdir -p /logs/verifier",
                "--ctrf=/logs/verifier/ctrf.json", "-p no:cacheprovider"):
    rule(literal in tsh, "tests/test.sh has `%s`" % literal)
writes = [line for line in tsh.splitlines() if "reward.txt" in line and ">" in line]
rule(writes and all(line in ('echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt') for line in writes),
     "every write of reward.txt in test.sh is one of the two literals, alone on its line")
commands = [line for line in tsh.splitlines() if line.strip() and not line.lstrip().startswith("#")]
first_zero = commands.index('echo -n "0" > /logs/verifier/reward.txt') if 'echo -n "0" > /logs/verifier/reward.txt' in commands else len(commands)
first_run = next((k for k, line in enumerate(commands) if "pytest" in line or "python" in line), len(commands))
rule(first_zero < first_run, "test.sh writes the 0 before it runs anything")
rule("time.monotonic() - started >= limit" in bench and "sum(most.values()) >= limit" in bench and "ru_utime + usage.ru_stime" in bench,
     "the bench holds the limit on the clock and on the CPU time of every process of the run")
rule('if ending == "over":' in bench and "return verdict" in bench.split('if ending == "over":', 1)[1][:400],
     "a run over the limit ends the judging at once, unread, and the program is not accepted")
rule("TimeoutExpired" not in bench, "no TimeoutExpired is caught anywhere in the bench")
rule('"OMP_NUM_THREADS": "1"' in bench and '"OPENBLAS_NUM_THREADS": "1"' in bench, "a run has OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1")
rule("setaffinity" not in bench and "taskset" not in bench + tsh, "no CPU affinity is set")
rule("setpriv" in bench and "chmod -R go-rwx /tests" in tdock and "chmod 0700 /logs/verifier" in tdock, "the program runs as nobody; /tests and /logs/verifier are root's alone")
rule("mode=" not in bench and "os.chmod(" in bench, "every mode the program depends on is set with os.chmod, never through a mode= argument")
rule("umask 077" in tsh, "test.sh works under umask 077")
edock = text_of("environment", "Dockerfile")
rule("numpy==2.1.3 scipy==1.14.1 pandas==2.2.3" in edock and "useradd" in edock and "-o agent -g agent" in edock and "OMP_NUM_THREADS=1" in edock,
     "the agent's image: the same pins, the user agent owning /app/output, one thread to a library")
test_py = text_of("tests", "test_ropes.py")
rule(test_py.count("def test_") == 1, "pytest finds one test")

print("\nthe data\n")
pending = os.path.join(BUNDLE, "environment", "data", "pending")
rule(all(not os.path.exists(os.path.join(pending, n, "expected.csv")) for n in os.listdir(pending)), "no pending works carries results")
leaked = [f for f in files if f.startswith("environment") and ("sealed" in f or "pending_results" in f)]
rule(not leaked, "nothing sealed sits under environment/")
with open(os.path.join(BUNDLE, "authoring", "provenance", "manifest.json")) as handle:
    book = json.load(handle)
listed, wrong = 0, 0
for entry in book["works"]:
    for rel, facts in entry["files"].items():
        listed += 1
        try:
            with open(os.path.join(BUNDLE, rel), "rb") as handle:
                wrong += hashlib.sha256(handle.read()).hexdigest() != facts["sha256"]
        except OSError:
            wrong += 1
rule(listed == 45 and wrong == 0, "all %d files manifest.json lists are there with its SHA-256 (%d not)" % (listed, wrong))
table = {w["works"]: w for w in generator.WORKS}
rule(all(table[e["works"]]["role"] == e["role"] and all(table[e["works"]][k] == e[k] for k in ("turned", "dead_end", "both")) for e in book["works"]),
     "manifest.json's table of works is the generator's")
hidden = sorted(os.listdir(os.path.join(TESTS, "works")))
rule(hidden == sorted(w["works"] for w in generator.WORKS if w["role"] == "hidden")
     and sorted(f[:-4] for f in os.listdir(os.path.join(TESTS, "sealed", "results"))) == hidden,
     "tests/works holds the six works and tests/sealed/results their six results")

print("\nthe studies\n")
names = ["regenerate", "design_rules", "reference_run", "seed_screen", "route_run", "spread_run", "second_run", "null_run", "verifier_checks", "verifier_run"]
texts = {n: study(n) for n in names}
for n in names:
    rule(texts[n] and not re.search(r"UNEXPECTED|PROBLEM|Traceback|FAILS|NOT ACCEPTED\n\s*$", texts[n]) or n in ("second_run", "verifier_run") and texts[n] and not re.search(r"UNEXPECTED|PROBLEM|Traceback", texts[n]),
         "%s.txt is there and reports no failure" % n)
rule(re.search(r"\n45 files compared, 0 differ", texts["regenerate"]) is not None, "regenerate: every shipped data file is what the generator writes")
m = re.search(r"\n(\d+) rules, (\d+) hold", texts["design_rules"])
rule(bool(m) and m.group(1) == m.group(2), "design rules: all hold (%s)" % ("/".join(m.groups()) if m else "?"))
m = re.search(r"slowest run ([\d.]+) s; the limit of (\d+) s is ([\d.]+) times that", texts["reference_run"])
rule(bool(m) and int(m.group(2)) == limit and 2.0 <= float(m.group(3)) <= 3.5,
     "the limit is 2 to 3.5 times the reference's slowest run (%s)" % (m.group(3) if m else "?"))
rule(texts["reference_run"].count("\nACCEPTED") == 2, "the reference is accepted on the six works and on the three visible ones")
m = re.search(r"\n20 seeds, 20 accepted; widest departure on any seed ([\d.]+)", texts["seed_screen"])
rule(bool(m) and float(m.group(1)) <= 0.5, "seed screen: accepted on 20 of 20 seeds, widest %s of the band" % (m.group(1) if m else "?"))
m = re.search(r"widest departure of a sound program: ([\d.]+) of the band", texts["spread_run"])
q = re.search(r"widest departure from the sealed results ([\d.]+) of the band", texts["second_run"])
rule(bool(m) and bool(q) and max(float(m.group(1)), float(q.group(1))) <= 0.5,
     "the band is at least twice the widest departure of any sound program (%s) and of the second solution (%s)" % (m.group(1) if m else "?", q.group(1) if q else "?"))
rule(re.search(r"\n10 programs, 0 not accepted somewhere", texts["spread_run"]) is not None, "every sound variation, and a turn at either edge of its gap, is accepted")
m = re.search(r"\n(\d+) routes, 0 accepted on the six works; works that stop fewer than three routes: none", texts["route_run"])
rule(bool(m) and int(m.group(1)) >= 6, "routes: none accepted, every works stops at least three")
least = [float(x) for x in re.findall(r"misses least: ([\d.]+) bands", texts["route_run"])]
rule(least and min(least) >= 1.5, "the route nearest to right misses by at least 1.5 bands (%.1f)" % (min(least) if least else 0))
m = re.search(r"would take (\d+) to (\d+) s a run, ([\d.]+) to ([\d.]+) times the limit", texts["second_run"])
rule(bool(m) and float(m.group(3)) >= 3.0, "the second solution in plain loops would need at least 3 times the limit (%s)" % (m.group(3) if m else "?"))
m = re.search(r"runs of ([\d.]+) to ([\d.]+) s, ([\d.]+) to ([\d.]+) times the limit", texts["second_run"])
rule(bool(m) and float(m.group(3)) >= 1.5, "brute force needs at least 1.5 times the limit on every works (%s)" % (m.group(3) if m else "?"))
rule(texts["second_run"].count("works tried: 1 of 6") == 2 and texts["second_run"].count("\nACCEPTED") == 3,
     "the fast second solution is accepted; plain loops and brute force are stopped on the first works")
rule(re.search(r"\n5 programs, 0 accepted; most ropes wholly right: 0 of", texts["null_run"]) is not None, "no program without the calculation gets a rope wholly right")
rule(re.search(r"\n(\d+) cases, 0 unexpected", texts["verifier_checks"]) is not None, "verifier checks: none unexpected")
rule(re.search(r"\n5 programs, 0 unexpected", texts["verifier_run"]) is not None
     and re.search(r"the reference, solution/ropes\.py\s+reward 1\b", texts["verifier_run"]) is not None,
     "test.sh itself: reward 1 for the reference and the second solution, 0 for the other three")
studied = os.path.getmtime(os.path.join(EVIDENCE, "verifier_run.txt"))
newer = [f for f in ("tests/rope_bench.py", "tests/test.sh", "tests/test_ropes.py", "tests/tally.py", "solution/ropes.py")
         if os.path.getmtime(os.path.join(BUNDLE, f)) > studied]
rule(not newer, "no verifier file or the reference has changed since verifier_run.txt%s" % ("" if not newer else ": " + ", ".join(newer)))

figures = set(re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", readme))
pool = "".join(texts.values()) + "".join(text_of(f) for f in files if f.endswith((".md", ".py")) and f != "README.md")
absent = sorted(f for f in figures if f not in pool)
rule(not absent, "every decimal figure in README.md occurs in a study, a document or the code%s" % ("" if not absent else ": " + ", ".join(absent[:8])))

print("\na live run\n")
os.umask(0o077)
verdict = rope_bench.judge(os.path.join(BUNDLE, "solution", PROGRAM))
rule(verdict["accepted"], "the reference, through the bench under umask 077: %s" % "; ".join(
    "%s %.1f s" % (n["works"], n["cpu_seconds"]) for n in verdict["trials"]))

print("\n%d rules, %d hold" % (len(results), sum(results)))
sys.exit(0 if all(results) else 1)
