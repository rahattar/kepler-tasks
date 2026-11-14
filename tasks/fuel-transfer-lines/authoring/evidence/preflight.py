"""preflight.py: the rules of the playbook and of this bundle's design, checked on the files. Writes preflight.txt.

    python3 authoring/evidence/preflight.py

Static checks first (layout, names, task.toml, the README, the statement against the checker, the two
images, the data and its manifest, the committed studies), then a few live runs of the checker, made under
the umask 077 that tests/test.sh sets. Ends with "N checks, 0 failed: the bundle is clean" or says what failed.
"""
import ast
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib

sys.dont_write_bytecode = True
EVIDENCE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(os.path.dirname(EVIDENCE))
sys.path.insert(0, EVIDENCE)
sys.path.insert(0, os.path.join(B, "tests"))
sys.path.insert(0, os.path.join(B, "authoring", "provenance"))

results = []


def check(ok, text):
    results.append((bool(ok), text))
    print("%-5s %s" % ("ok" if ok else "FAIL", text), flush=True)


def read(*parts):
    with open(os.path.join(B, *parts), encoding="utf-8", errors="replace") as handle:
        return handle.read()


def every_file(top=B):
    for folder, inner, names in os.walk(top):
        inner.sort()
        for name in sorted(names):
            yield os.path.join(folder, name)


ROOT = {"README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"}
CLOSE = "You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task."
TASK = os.path.basename(B)

# 1. layout and names
check(set(os.listdir(B)) == ROOT, "the bundle's root holds %s and nothing else" % ", ".join(sorted(ROOT)))
junk = [p for p in every_file() if "__pycache__" in p or p.endswith(".pyc") or any(x.startswith(".") for x in os.path.relpath(p, B).split(os.sep))]
check(not junk, "no cache, bytecode or dotfile anywhere%s" % ("" if not junk else ": %s" % [os.path.relpath(p, B) for p in junk[:3]]))
upper = [os.path.relpath(os.path.join(f, n), B) for f, d, ns in os.walk(B) for n in d + ns
         if n not in ("README.md", "Dockerfile") and n.split(".")[0].isupper() and any(c.isalpha() for c in n)]
check(not upper, "no all-uppercase file or folder name but README.md and Dockerfile%s" % ("" if not upper else ": %s" % upper[:3]))
odd = []
for p in every_file():
    raw = open(p, "rb").read()
    try:
        raw.decode("ascii")
    except UnicodeDecodeError:
        odd.append(os.path.relpath(p, B))
check(not odd, "every file is ASCII%s" % ("" if not odd else ": %s" % odd[:3]))
coded = []
for p in every_file():
    if not p.endswith(".py"):
        continue
    tree = ast.parse(open(p).read())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(m.split(".")[0] in ("base64", "binascii", "codecs", "zlib", "marshal", "bz2", "lzma") for m in mods):
                coded.append("%s:%d" % (os.path.relpath(p, B), node.lineno))
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name in ("b64decode", "b32decode", "unhexlify", "fromhex", "decompress", "exec", "eval"):
                coded.append("%s:%d %s" % (os.path.relpath(p, B), node.lineno, name))
check(not coded, "no encoded strings, decoders, checksum modules or exec in any program%s" % ("" if not coded else ": %s" % coded[:3]))

# 2. task.toml
toml = tomllib.loads(read("task.toml"))
meta = toml.get("metadata", {})
check(toml["task"]["name"].split("/")[-1] == TASK and len(toml["task"]["name"].split("/")) == 2 and len(TASK.split("-")) <= 3,
      "the task's name is <prefix>/%s, at most three hyphenated words" % TASK)
check(toml.get("artifacts") == ["/app/output/lines.py"], "the one artifact is /app/output/lines.py")
KEYS = ("author_name", "author_email", "author_organization", "author_profile", "research_advisor", "referred_by", "conflicts_of_interest",
        "domain", "field", "subfield", "category", "subcategory", "tags", "expert_time_estimate_hours", "relevant_experience",
        "difficulty_explanation", "solution_explanation", "verification_explanation")
check(all(k in meta for k in KEYS), "[metadata] carries the whole block")
check(meta.get("category") == "Science" and str(meta.get("subcategory", "")).strip() and meta.get("domain") == "engineering-sciences"
      and meta.get("field") == "mechanical-engineering", 'category "Science", a subcategory, domain engineering-sciences, field mechanical-engineering')
check(toml["task"].get("keywords") == meta.get("tags"), "keywords and tags are the same list")
check(0 < len(meta.get("subfield", "")) <= 120, "subfield is at most 120 characters (it is %d)" % len(meta.get("subfield", "")))
check(toml["agent"]["timeout_sec"] == 28800.0 and toml["agent"].get("user") == "agent" and toml["verifier"]["timeout_sec"] == 600.0
      and toml["verifier"].get("environment_mode") == "separate" and toml["verifier"]["environment"]["network_mode"] == "no-network",
      "agent: 28800 s as the user agent; verifier: 600 s, separate, no network")
readme = read("README.md")
for key, head in (("difficulty_explanation", "## Difficulty"), ("solution_explanation", "## Reference solution"),
                  ("verification_explanation", "## Verification")):
    text = meta.get(key, "").strip()
    part = readme.split(head + "\n", 1)[1].split("\n## ", 1)[0].strip() if head + "\n" in readme else ""
    check(len(text) > 400 and part == text, "%s is in task.toml and word for word in the README under %s" % (key, head))
diff = meta.get("difficulty_explanation", "")
check("synthetic" in diff and "realistic" in diff and "research analogue" in diff, "the difficulty text says the data is synthetic and realistic and names a research analogue")
check(not re.search(r"\broutine\b|\bprobe|\b\d of [38]\b|solve rate", diff, re.I), "the difficulty text does not call the work routine and gives no solve counts")
check("deliberately" in readme and "sites.py" in readme and "SITES" in readme, "the README's notes say what the shift in the data is and where it is built")

# 3. the statement against the checker
import rerun  # noqa: E402
ins = read("instruction.md")
body = ins.replace(CLOSE, "")
check(ins.endswith("\n\n" + CLOSE + "\n") or ins.endswith("\n\n" + CLOSE), "the statement ends with a blank line and the closing sentence")
check(not re.search(r"^\s{0,3}#", ins, re.M), "the statement has no heading")
check(not re.search(r"\b(you|your|we|our|I)\b|\bas an? [a-z ]*engineer", body), "the statement assigns no role and speaks to no one")
check(not re.search(r"\b(grader|graded|grading|verifier|reward|score[sd]?|scoring|partial credit|tested|pass(?:es|ed)?|fail(?:s|ed)?)\b", body, re.I),
      "the statement has no grading words")
m = re.search(r"Each run of lines\.py must finish within (\d+) seconds on 1 CPU\.", ins)
check(m and int(m.group(1)) == rerun.LIMIT_S, "the statement gives the limit in the required sentence, and it is the checker's: %s s" % (m.group(1) if m else "none"))
src = read("tests", "rerun.py")
check("class Meter" in src and "meter.total() >= self.limit" in src and "self.cpu_seconds >= self.limit" in src,
      "the checker holds a run to 1 CPU by the CPU time of the program and every process it starts, against the same limit as the clock")
check("time.monotonic() - began >= self.limit" in src and 'verdict["stopped"]' in src and "return verdict" in src,
      "the checker holds the run to the limit on the clock too, and a run over it ends the comparison")
tests_code = "".join(read("tests", f) for f in os.listdir(os.path.join(B, "tests")) if f.endswith((".py", ".sh")))
check(not re.search(r"sched_setaffinity|taskset|cpu_affinity", tests_code), "nothing in tests/ sets CPU affinity")
check(str(rerun.MOST_BYTES) in ins.replace(",", ""), "the statement gives the checker's cap on the size of OUT_CSV: %d bytes" % rerun.MOST_BYTES)
check(",".join(rerun.COLUMNS) in ins, "the statement's header is the checker's: %s" % ",".join(rerun.COLUMNS))
check(rerun.DP_SHARE == 0.025 and rerun.T_BAND_K == 0.5 and "2.5 per cent" in ins and "0.5 K" in ins,
      "the statement's band is the checker's: 2.5 per cent of the pressure drop, 0.5 K of the outlet temperature")
check("python3 lines.py PACKAGE_DIR OUT_CSV" in ins and "heatsurvey" in ins, "the statement names the command and how the program is run")
paths = re.findall(r"/app/data/[\w/.-]+", ins)
check(paths and all(os.path.exists(os.path.join(B, "environment", "data", p[len("/app/data/"):].rstrip("."))) for p in paths),
      "every path the statement names is in the image's data")
named = ["/app/data/docs/ts2_oil_lines.md", "/app/data/docs/site_package.md"] + \
        ["/app/data/%s/%s" % (k, n) for k in ("examples", "pending") for n in os.listdir(os.path.join(B, "environment", "data", k))]
check(all(p in ins for p in named), "the statement names both documents and all three packages by absolute path")
ts2 = read("environment", "data", "docs", "ts2_oil_lines.md")
check("4.2" in ts2 and "starts at the division of the earlier record" in ts2 and "4.3" in ts2 and "one division only" in ts2,
      "TS-2 states how a pair's division is carried from record to record (4.2) and how a run opens (4.3)")

# 4. the data
import manifest  # noqa: E402
sites_dir = os.path.join(B, "tests", "sites")
six = sorted(os.listdir(sites_dir))
beside = sorted(os.listdir(os.path.join(B, "environment", "data", "examples")) + os.listdir(os.path.join(B, "environment", "data", "pending")))
check(len(six) == 6 and len(beside) == 3 and not set(six) & set(beside), "six sites to run on, three beside the program, no name in both")
SIX_FILES = sorted(rerun.SIX_FILES)
check(all(sorted(os.listdir(os.path.join(sites_dir, n))) == SIX_FILES for n in six), "each of the six is the six files of a package and nothing else")
rows_ok, sizes = True, []
for n in six:
    recs = [r["record"] for r in csv.DictReader(open(os.path.join(sites_dir, n, "records.csv")))]
    res = list(csv.DictReader(open(os.path.join(B, "tests", "results", n + ".csv"))))
    rows_ok &= [r["record"] for r in res] == recs and list(res[0]) == rerun.COLUMNS
    pipes = sum(int(r["pipes"]) for r in csv.DictReader(open(os.path.join(sites_dir, n, "lines.csv"))))
    sizes.append((pipes, len(recs)))
check(rows_ok, "the sealed results have one row for every record of each of the six, in the statement's columns")
check(all(p <= 60 and r <= 1500 for p, r in sizes), "no package the program is run on is larger than site_package.md allows (most: %d pipes, %d records)"
      % (max(p for p, _ in sizes), max(r for _, r in sizes)))
agent_side = "".join(open(p, errors="replace").read() for p in every_file(os.path.join(B, "environment")))
check(not any(n in agent_side for n in six), "no name of the six, and so no result of theirs, anywhere in the agent's image")
visible = "".join(read("environment", "data", "docs", f) for f in os.listdir(os.path.join(B, "environment", "data", "docs"))) + ins
words = re.findall(r"\b(narrow\w*|deposit\w*|declin\w*|deteriorat\w*|trap\w*|hidden|stall\w*|foul\w*|drift\w*|shift\w* in the data)\b", visible, re.I)
check(not words, "the documents and the statement use none of the authoring vocabulary%s" % ("" if not words else ": %s" % sorted(set(words))))
check(all(os.path.exists(os.path.join(B, "environment", "data", "examples", n, "expected.csv")) for n in os.listdir(os.path.join(B, "environment", "data", "examples")))
      and not any(os.path.exists(os.path.join(B, "environment", "data", "pending", n, "expected.csv")) for n in os.listdir(os.path.join(B, "environment", "data", "pending"))),
      "the example packages carry results and the pending package none")
same = sorted(os.path.relpath(p, os.path.join(B, "environment", "data")) for p in every_file(os.path.join(B, "environment", "data")))
copy = sorted(os.path.relpath(p, os.path.join(B, "tests", "app_data")) for p in every_file(os.path.join(B, "tests", "app_data")))
check(same == copy and all(open(os.path.join(B, "environment", "data", f), "rb").read() == open(os.path.join(B, "tests", "app_data", f), "rb").read() for f in same),
      "the verifier's copy of /app/data is the image's, file for file")
check(read("tests", "crew", "lab.py") == read("environment", "rig", "lab.py"), "the survey crew is one program: tests/crew/lab.py is environment/rig/lab.py")
client = read("tests", "crew", "heatsurvey")
check(rerun.DESK in client, "the verifier's heatsurvey leaves an order where the checker looks: %s" % rerun.DESK)
import lab  # noqa: E402
both = [read("tests", "crew", "heatsurvey"), read("environment", "rig", "heatsurvey")]
check(all(lab.USAGE in t and "is not a site package: it has no site.json that names the site" in t for t in both)
      and "is not a site package: it has no site.json that names the site" in lab.NOT_A_PACKAGE,
      "both heatsurvey commands print the crew's usage and the same words for a package without site.json")
sealed = sorted(f[:-5] for f in os.listdir(os.path.join(B, "environment", "rig", "sealed")))
check(sealed == sorted(os.listdir(os.path.join(B, "environment", "data", "examples")))
      and "takes no order for it" in read("environment", "data", "docs", "site_package.md"),
      "where the program is written the crew holds books for the two example sites and none for the pending one, and site_package.md says so")
books_ok = True
for n in six:
    book = json.load(open(os.path.join(B, "tests", "crew", "books", n + ".json")))
    pipes = {r["pipe"] for r in csv.DictReader(open(os.path.join(sites_dir, n, "surveys.csv")))}
    books_ok &= book["allowance"] == json.load(open(os.path.join(sites_dir, n, "site.json")))["survey_allowance"] and set(book["readings"]) == pipes
check(books_ok, "the crew holds a book for each of the six, with the package's allowance and a reading for every pipe")
listed = json.load(open(os.path.join(B, "authoring", "provenance", "manifest.json")))["files"]
now = manifest.listing(B)
check(listed == now, "the manifest lists every data file with its SHA-256, and every one matches (%d files)" % len(listed))
regen = read("authoring", "evidence", "regenerate.txt") if os.path.exists(os.path.join(EVIDENCE, "regenerate.txt")) else ""
check(re.search(r"%d files listed, 0 made differently, 0 made and not listed" % len(listed), regen) is not None,
      "regenerate.txt records sites.py making every one of those files again, byte for byte")

# 5. the images and the reward script
td = read("tests", "Dockerfile")
lines_td = [l.strip() for l in td.splitlines()]
check("RUN mkdir -p /app/output" in lines_td and "COPY . /tests/" in lines_td and "WORKDIR /tests" in lines_td and "ENV PYTHONUNBUFFERED=1" in lines_td,
      "tests/Dockerfile has the lines intake reads as text")
pins = ("pytest==8.4.1", "pytest-json-ctrf==0.3.5", "numpy==2.1.3", "scipy==1.14.1", "pandas==2.2.3")
check(all(p in td for p in pins), "tests/Dockerfile pins %s" % ", ".join(pins))
ed = read("environment", "Dockerfile")
check(all(p in ed for p in pins[2:]), "the agent's image pins the same numpy, scipy and pandas")
check(all("OMP_NUM_THREADS=1" in t and "OPENBLAS_NUM_THREADS=1" in t for t in (td, ed)) and '"OMP_NUM_THREADS": "1"' in src and '"OPENBLAS_NUM_THREADS": "1"' in src,
      "threads are held to one in both images and in the run's own environment")
check("chmod -R u=rwX,go= /tests" in td and "install -d -o 0 -g 0 -m 700 /logs/verifier" in td, "the verifier's image closes /tests and /logs/verifier to every account but root")
last = [l for l in ed.splitlines() if l.strip() and not l.strip().startswith("#")][-1]
check("useradd --create-home --user-group --shell /bin/bash agent" in ed and "surveyor" in ed and "visudo -cf /etc/sudoers.d/surveyor" in ed
      and "chmod 700 /opt/surveyors/sealed" in ed and "chmod 600 /opt/surveyors/sealed/*.json" in ed and not last.strip().upper().startswith("USER"),
      "the agent's image: users agent and surveyor, one sudo rule checked by visudo, books only surveyor can read, and it ends as root")
sudo = read("environment", "rig", "sudoers").strip().splitlines()
check([l for l in sudo if l and not l.startswith("#")] == ["agent ALL=(surveyor) NOPASSWD: /opt/surveyors/lab.py heatsurvey *"], "the sudo rule allows lab.py heatsurvey and nothing else")
ts = read("tests", "test.sh")
writes = [l.strip() for l in ts.splitlines() if "reward.txt" in l and not l.strip().startswith(("#", "rm "))]
check(writes == ['echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt']
      and all(l.startswith("echo") for l in ts.splitlines() if "reward.txt" in l and l.startswith("echo")),
      "test.sh writes the reward only as the two literal lines, each on a line of its own, the 0 first")
check("umask 077" in ts and "mkdir -p /logs/verifier" in ts and "--ctrf=/logs/verifier/ctrf.json" in ts and "-p no:cacheprovider" in ts and "tally.py" in ts,
      "test.sh sets umask 077, runs the one pytest file with the report and cache flags intake looks for, then tally.py")
check(len(re.findall(r"^def test_", read("tests", "test_lines.py"), re.M)) == 1, "the verifier's test is one test")
check("cp \"$here/lines.py\" /app/output/lines.py" in read("solution", "solve.sh"), "solution/solve.sh puts solution/lines.py at /app/output/lines.py")

# 6. the committed studies
studies = ("reference_run", "second_run", "records_run", "verifier_checks", "verifier_run")
check(all(os.path.exists(os.path.join(EVIDENCE, s + ".txt")) for s in studies) and os.path.exists(os.path.join(EVIDENCE, "design_rules.txt")),
      "every study's output is committed")
txt = {s: read("authoring", "evidence", s + ".txt") if os.path.exists(os.path.join(EVIDENCE, s + ".txt")) else "" for s in studies + ("design_rules", "regenerate")}
bad = [s for s, t in txt.items() if re.search(r"(?<!0 )UNEXPECTED|PROBLEM|BROKEN|Traceback", t)]
check(not bad, "no study reports anything unexpected%s" % ("" if not bad else ": %s" % bad))
check("reference: accepted on all three sets" in txt["reference_run"], "reference_run.txt: accepted on the six sites, on the three packages beside the program and on the small sites")
cpu = [float(x) for x in re.findall(r"CPU time of a run: [\d.]+ to ([\d.]+) s; the limit", txt["reference_run"])]
check(cpu and 2.0 <= rerun.LIMIT_S / cpu[0] <= 3.5, "the limit is between 2 and 3.5 times the reference's longest run (%s s of CPU)" % (cpu[0] if cpu else "?"))
check("second solution: as expected" in txt["second_run"],
      "second_run.txt: the second solution as first written is right on small sites and stopped at the limit on the six; made fast, it is accepted on every set inside the limit")
w = re.search(r"widest departure of the second solution from the sealed results, either form, any set: ([\d.]+) of the band", txt["second_run"])
check(w and float(w.group(1)) <= 0.5, "the band is at least twice the widest departure of the separately written solution (%s of the band)" % (w.group(1) if w else "?"))
check("records: every program ends as it should" in txt["records_run"],
      "records_run.txt: each program written to the examples is accepted on them and not on the six; with no order the examples are out of band; the sound variations are accepted")
check(re.search(r"\n(\d+) of \1 rules hold", txt["design_rules"]) is not None, "design_rules.txt: every rule holds")
check(re.search(r"\b\d+ cases, 0 UNEXPECTED", txt["verifier_checks"]) and "; 0 UNEXPECTED" in txt["verifier_run"], "verifier_checks.txt and verifier_run.txt end with nothing unexpected")
check("bash tests/test.sh" in txt["verifier_run"] and "reward 1 (expected 1)" in txt["verifier_run"], "verifier_run.txt is tests/test.sh itself: reward 1 for the reference, 0 for the other two")
corpus = " ".join(txt.values()) + ins + ts2 + read("environment", "data", "docs", "site_package.md") + read("authoring", "provenance", "sites.py") + src + read("solution", "lines.py") \
    + read("authoring", "evidence", "second_lines.py") + read("authoring", "evidence", "plain_lines.py")
expl = " ".join(meta.get(k, "") for k in ("difficulty_explanation", "solution_explanation", "verification_explanation"))
figures = sorted(set(re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", expl)))
missing = [f for f in figures if f not in corpus]
check(not missing, "every decimal figure in the README's three sections is in a study, the statement, the documents, the generator, the checker or a solution%s"
      % ("" if not missing else ": %s" % missing[:8]))

# 7. live, under test.sh's umask
os.umask(0o077)
import common  # noqa: E402
import variants  # noqa: E402
small = common.site_set("small")[0]
one = sorted(os.listdir(small))[0]
sealed_text = open(os.path.join(common.SMALL, "results", one + ".csv")).read()


def table_program(text):
    return common.written("import sys\nopen(sys.argv[2], 'w').write(%r)\n" % text, "lines.py")


rows = [r.split(",") for r in sealed_text.strip().split("\n")]
alter = lambda f: "\n".join([",".join(rows[0])] + [",".join(f(r)) for r in rows[1:]]) + "\n"
live = [
    ("the sealed table of a small site is accepted", table_program(sealed_text), True),
    ("the same with CRLF line ends and the rows reversed is accepted", table_program("\r\n".join([",".join(rows[0])] + [",".join(r) for r in rows[:0:-1]]) + "\r\n"), True),
    ("the same with a capitalised header is not", table_program(sealed_text.replace("record,dp_kPa,t_out_C", "Record,dp_kPa,t_out_C", 1)), False),
    ("the same with one record left out is not", table_program("\n".join(sealed_text.strip().split("\n")[:-1]) + "\n"), False),
    ("the same with one value nan is not", table_program(sealed_text.replace(rows[3][2], "nan", 1)), False),
    ("every pressure drop 2.4 per cent high is accepted", table_program(alter(lambda r: [r[0], repr(float(r[1]) * 1.024), r[2]])), True),
    ("every pressure drop 2.6 per cent high is not", table_program(alter(lambda r: [r[0], repr(float(r[1]) * 1.026), r[2]])), False),
    ("every outlet temperature 0.45 K low is accepted", table_program(alter(lambda r: [r[0], r[1], repr(float(r[2]) - 0.45)])), True),
    ("every outlet temperature 0.55 K low is not", table_program(alter(lambda r: [r[0], r[1], repr(float(r[2]) - 0.55)])), False),
]
for text, program, want in live:
    v = common.run(program, "small", only=[one])
    check(v["accepted"] == want, "live: " + text)
v = common.run(common.written("import sys, time\nopen(sys.argv[2], 'w').write(%r)\ntime.sleep(60)\n" % sealed_text, "lines.py"), "small", limit=3, only=[one])
check(not v["accepted"] and "used up" in v["stopped"], "live: a program that writes the sealed table and is still running at the limit is not accepted, and its table is not opened")
v = common.run(common.REFERENCE, "small", only=[one])
allowance = json.load(open(os.path.join(small, one, "site.json")))["survey_allowance"]
check(v["accepted"] and v["sites"][one]["survey_order"] and len(v["sites"][one]["survey_order"]) == allowance,
      "live: the reference on a small site is accepted and places one order of the site's allowance")

failed = sum(1 for ok, _ in results if not ok)
summary = "%d checks, %d failed: %s" % (len(results), failed, "the bundle is clean" if not failed else "the bundle is NOT clean")
print(summary)
with open(os.path.join(EVIDENCE, "preflight.txt"), "w") as handle:
    handle.write("\n".join("%-5s %s" % ("ok" if ok else "FAIL", t) for ok, t in results) + "\n" + summary + "\n")
sys.exit(1 if failed else 0)
