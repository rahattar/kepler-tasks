"""Mechanical checks of the bundle as it stands, run from anywhere:

    python3 authoring/evidence/preflight.py > authoring/evidence/preflight.txt

It reads the bundle's files and runs the checker on a few small programs. It does not rerun the studies; it
checks that what the README, the task statement, task.toml, the verifier and the committed study outputs say
agree with each other and with the shipped data. The last line is the count of checks and of failures.
"""
import atexit
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import tomllib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import common  # noqa: E402
from common import judge_airflow  # noqa: E402

TASK = "ventilation-district-airflow"
STUDIES = ("design_rules", "reference_run", "naive_run", "records_run", "verifier_checks", "verifier_run", "regenerate")
CLOSE = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
         "specific to this task.")
LIMIT_SENTENCE = "Each run of airflow.py must finish within %d seconds on 1 CPU."
VISIBLE_WORDS = ("trap", "hidden", "truth", "overfit", "probe", "verifier", "grader", "pytest", "breach", "breached",
                 "stall", "stalled", "hysteresis", "damaged", "imbalance", "as it is")
EXAMPLES = ("north_field", "east_decline")
PENDING = "west_reef"
MOST = {"branches.csv": 1000, "log.csv": 1500, "points.csv": 4500}
failures = 0
count = 0


def check(what, ok, note=""):
    global failures, count
    count += 1
    failures += not ok
    print("%s  %s%s" % ("ok  " if ok else "FAIL", what, "" if ok or not note else "  [%s]" % note))


def text(*parts):
    with open(os.path.join(ROOT, *parts)) as handle:
        return handle.read()


def rows(*parts):
    with open(os.path.join(ROOT, *parts), newline="") as handle:
        return list(csv.DictReader(handle))


def files_under(*parts):
    top = os.path.join(ROOT, *parts)
    for base, dirs, names in os.walk(top):
        dirs.sort()
        for name in sorted(names):
            yield os.path.relpath(os.path.join(base, name), ROOT)


def digest(path):
    with open(os.path.join(ROOT, path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def table_program(payload, then=""):
    handle, path = tempfile.mkstemp(prefix="pre_", suffix=".py")
    with os.fdopen(handle, "w") as out:
        out.write("import sys, time\nopen(sys.argv[2], 'wb').write(%r)\n%s" % (payload, then))
    os.chmod(path, 0o644)
    atexit.register(lambda: os.path.exists(path) and os.unlink(path))
    return path


def main():
    # ---- the tree
    check("the bundle's root holds README.md, instruction.md, task.toml, authoring, environment, solution, tests "
          "and nothing else", set(os.listdir(ROOT)) - {".source_zip"} == {
              "README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"})
    # .source_zip is the repository's note of which zip a task folder was last packed as; it is never zipped
    everything = [name for name in files_under(".") if name != ".source_zip"]
    check("no cache, bytecode or dotfile anywhere",
          not [n for n in everything if "__pycache__" in n or n.endswith(".pyc") or "/." in "/" + n])
    shouting = [n for n in everything for part in n.split("/")
                if part not in ("README.md", "Dockerfile") and part.split(".")[0].isupper()]
    check("no all-uppercase file or folder name but README.md and Dockerfile", not shouting, ", ".join(shouting[:3]))
    not_ascii = []
    for name in everything:
        with open(os.path.join(ROOT, name), "rb") as handle:
            raw = handle.read()
        try:
            raw.decode("ascii")
        except UnicodeDecodeError:
            not_ascii.append(name)
    check("every file is ASCII", not not_ascii, ", ".join(not_ascii[:3]))
    coded = [n for n in everything if n.endswith(".py") and n != "authoring/evidence/preflight.py"
             and re.search(r"\b(b64decode|b64encode|rot13|unhexlify|fromhex|decompress|zlib|binascii|codecs)\b", text(n))]
    check("no encoded strings, decoders or checksum modules in any program", not coded, ", ".join(coded))

    # ---- task.toml
    with open(os.path.join(ROOT, "task.toml"), "rb") as handle:
        toml = tomllib.load(handle)
    meta = toml.get("metadata", {})
    folder = os.path.basename(ROOT)
    check("the task's name ends with the bundle folder's name, of at most three hyphenated words",
          toml["task"]["name"].split("/")[-1] == TASK and len(TASK.split("-")) <= 3
          and (folder == TASK or not folder.startswith("ventilation")))
    check("the one artifact is /app/output/airflow.py", toml.get("artifacts") == ["/app/output/airflow.py"])
    wanted = ("author_name", "author_email", "author_organization", "author_profile", "research_advisor",
              "referred_by", "conflicts_of_interest", "domain", "field", "subfield", "category", "subcategory", "tags",
              "expert_time_estimate_hours", "relevant_experience", "difficulty_explanation", "solution_explanation",
              "verification_explanation")
    check("[metadata] carries the whole block", all(key in meta for key in wanted),
          ", ".join(k for k in wanted if k not in meta))
    check('category "Science", a subcategory, domain engineering-sciences, field mechanical-engineering',
          meta.get("category") == "Science" and bool(meta.get("subcategory")) and meta.get("domain") == "engineering-sciences"
          and meta.get("field") == "mechanical-engineering")
    check("keywords and tags are the same list", toml["task"].get("keywords") == meta.get("tags"))
    check("agent: 28800 s as the user agent; verifier: 600 s, separate, no network",
          toml["agent"] == {"timeout_sec": 28800.0, "user": "agent"} and toml["verifier"]["timeout_sec"] == 600.0
          and toml["verifier"]["environment_mode"] == "separate"
          and toml["verifier"]["environment"]["network_mode"] == "no-network")
    readme = text("README.md")
    for head, key in (("## Difficulty", "difficulty_explanation"), ("## Reference solution", "solution_explanation"),
                      ("## Verification", "verification_explanation")):
        value = str(meta.get(key, "")).strip()
        check("%s is in task.toml and word for word in the README under %s" % (key, head),
              len(value) > 400 and head in readme and value in readme)
    hard = meta.get("difficulty_explanation", "")
    check("the difficulty text says the data is synthetic and realistic and names a research analogue",
          "synthetic" in hard and "realistic" in hard and "research analogue" in hard)
    check("the difficulty text does not call the work routine and gives no solve counts",
          not re.search(r"\broutine\b", hard) and not re.search(r"\b\d+ of \d+ (runs|trials|attempts|probes)\b|\beffort\b", hard))
    notes = readme.split("## Submission notes")[-1]
    check("the README's notes say what the shift in the data is and where it is built",
          "## Submission notes" in readme and "authoring/provenance/districts.py" in notes and PENDING in notes)

    # ---- the task statement
    ins = text("instruction.md")
    body = ins.replace(CLOSE, "")
    check("the statement ends with a blank line and the closing sentence", ins.rstrip("\n").endswith("\n\n" + CLOSE))
    check("the statement has no heading", not re.search(r"(?m)^\s{0,3}#", ins))
    check("the statement assigns no role and speaks to no one",
          not re.search(r"\b(you|your|we|our|I|imagine|pretend)\b", body) and not re.search(r"(?i)\bas an? [a-z ]*engineer\b", body))
    words = re.findall(r"(?i)\b(grader|graded|grading|verifier|reward|score[sd]?|scoring|partial credit|tested|"
                       r"pass(?:ed)?|fail(?:s|ed)?)\b", body)
    check("the statement has no grading words", not words, ", ".join(sorted(set(words))))
    limit = judge_airflow.LIMIT_S
    check("the statement gives the limit in the required sentence, and it is the checker's: %d s" % limit,
          LIMIT_SENTENCE % limit in ins and len(re.findall(r"within \d+ seconds", ins)) == 1)
    judge = text("tests", "judge_airflow.py")
    check("the checker enforces that limit with a timeout on the run and treats TimeoutExpired as the end of the "
          "judging", "child.wait(timeout=limit)" in judge and "except subprocess.TimeoutExpired" in judge
          and "limit=LIMIT_S" in judge)
    check("the checker sets no CPU affinity", "taskset" not in judge and "sched_setaffinity" not in judge
          and "taskset" not in text("tests", "test.sh"))
    check("the statement gives the checker's cap on the size of OUT_CSV: %d bytes" % judge_airflow.MOST_BYTES,
          "no larger than %d bytes" % judge_airflow.MOST_BYTES in ins)
    check("the statement's header is the checker's", "`" + ",".join(judge_airflow.HEADER) + "`" in ins)
    check("the statement's band is the checker's: 1.5 per cent, or 0.03 m3/s where that is more",
          judge_airflow.BAND_SHARE == 0.015 and judge_airflow.BAND_FLOOR == 0.03
          and "within 1.5 per cent of the result to VS-4" in ins and "0.03 m3/s" in ins)
    check("the statement names the command and how the program is run",
          "`python3 airflow.py PACKAGE_DIR OUT_CSV`" in ins and "`pqsurvey`" in ins and "`/app/output/airflow.py`" in ins)
    named = re.findall(r"`(/app/data/[^`]*)`", ins)
    absent = [p for p in named if not os.path.exists(os.path.join(ROOT, "environment", "data", p[len("/app/data/"):]))]
    check("every path the statement names is in the image's data", bool(named) and not absent, ", ".join(absent))
    docs = sorted(os.listdir(os.path.join(ROOT, "environment", "data", "docs")))
    check("the statement names both documents and all three packages by absolute path",
          len(docs) == 2 and all("/app/data/docs/" + d in ins for d in docs)
          and all("/app/data/examples/" + n in ins for n in EXAMPLES) and "/app/data/pending/" + PENDING in ins)
    six = sorted(os.listdir(os.path.join(ROOT, "tests", "districts")))
    package_doc = text("environment", "data", "docs", "district_package.md")
    sizes = {name: max(len(rows("tests", "districts", d, name)) for d in six) for name in MOST}
    check("no package the program is run on is larger than district_package.md says a package can be "
          "(most: %d branches, %d log rows, %d survey points)" % (sizes["branches.csv"], sizes["log.csv"], sizes["points.csv"]),
          "A package holds up to 1,000 branches, 1,500 log rows and 4,500 survey points." in " ".join(package_doc.split())
          and all(sizes[name] <= MOST[name] for name in MOST))

    # ---- what the program's author can read
    seen = [n for n in everything if n.startswith(("environment/data/docs/", "environment/rig/lab", "environment/rig/pqsurvey",
                                                   "instruction.md"))]
    loud = []
    for name in seen:
        low = text(name).lower()
        loud += ["%s: %s" % (name, w) for w in VISIBLE_WORDS if re.search(r"\b%s\b" % re.escape(w), low)]
    check("nothing the program's author can read uses the authoring vocabulary", not loud, "; ".join(loud[:4]))
    check("the example packages carry results and the pending package none",
          all(os.path.exists(os.path.join(common.DATA, "examples", n, "expected.csv")) for n in EXAMPLES)
          and sorted(os.listdir(os.path.join(common.DATA, "pending", PENDING))) == sorted(judge_airflow.PACKAGE))
    check("the verifier's copy of /app/data is the image's, file for file",
          sorted((n[len("environment/data/"):], digest(n)) for n in everything if n.startswith("environment/data/"))
          == sorted((n[len("tests/app_data/"):], digest(n)) for n in everything if n.startswith("tests/app_data/")))
    check("the survey crew is one program: tests/crew/lab.py is environment/rig/lab.py",
          digest("tests/crew/lab.py") == digest("environment/rig/lab.py"))
    check("the verifier's pqsurvey looks for the crew where the checker opens its window",
          'WINDOW = "%s"' % judge_airflow.WINDOW in text("tests", "crew", "pqsurvey"))
    both = (text("tests", "crew", "pqsurvey"), text("environment", "rig", "pqsurvey"))
    check("both pqsurvey wrappers print the same usage and the same words for a package without district.json",
          all('print("usage: pqsurvey PACKAGE_DIR BRANCH [BRANCH ...]")' in t
              and '"%s is not a district package: no district.json naming the district" % sys.argv[1]' in t for t in both))
    check("where the program is written the crew holds a book for the two example districts and none for the pending one, "
          "and district_package.md says so",
          sorted(os.listdir(os.path.join(ROOT, "environment", "rig", "sealed"))) == sorted(n + ".json" for n in EXAMPLES)
          and "it has not been to the district in `pending`" in " ".join(package_doc.split()))

    # ---- the districts
    visible_names = set(EXAMPLES) | {PENDING}
    check("six districts to run on, three beside the program, no name in both",
          len(six) == 6 and not set(six) & visible_names
          and set(os.listdir(os.path.join(common.DATA, "examples"))) == set(EXAMPLES)
          and os.listdir(os.path.join(common.DATA, "pending")) == [PENDING])
    check("each of the six is the ten files of a package and nothing else",
          all(sorted(os.listdir(os.path.join(ROOT, "tests", "districts", n))) == sorted(judge_airflow.PACKAGE) for n in six))
    covered = True
    for name in six:
        points = {p["point"] for p in rows("tests", "districts", name, "points.csv")}
        result = rows("tests", "results", name + ".csv")
        covered &= points == {r["point"] for r in result} and len(result) == len(points) and list(result[0]) == judge_airflow.HEADER
    check("the sealed results have one row for every point of each of the six, in the statement's columns", covered)
    check("no name of the six, and no result of theirs, anywhere in the agent's image",
          not [n for n in everything if n.startswith("environment/") and any(h in n or h in text(n) for h in six)])
    books_ok = sorted(os.listdir(os.path.join(ROOT, "tests", "crew", "books"))) == sorted(n + ".json" for n in six)
    for where, names in ((("tests", "crew", "books"), six), (("environment", "rig", "sealed"), EXAMPLES)):
        for name in names:
            book = judge_airflow.lab.book(os.path.join(ROOT, *where), name)
            package = (("tests", "districts", name) if where[0] == "tests" else ("environment", "data", "examples", name))
            head = json.loads(text(*package, "district.json"))
            branches = {b["branch"] for b in rows(*package, "branches.csv")}
            books_ok &= book["allowance"] == head["survey_allowance"] and set(book["readings"]) == branches and head["district"] == name
    check("the crew holds a book for each district it answers for, with the package's allowance and a reading for "
          "every branch", books_ok)
    manifest = json.loads(text("authoring", "provenance", "manifest.json"))
    shipped = sorted(n for n in everything if n.startswith(("environment/data/examples/", "environment/data/pending/",
                                                           "environment/rig/sealed/", "tests/districts/", "tests/results/",
                                                           "tests/crew/books/", "authoring/provenance/as_it_is/",
                                                           "authoring/evidence/small/")))
    check("the manifest lists every data file with its SHA-256, and every one matches (%d files)" % len(shipped),
          sorted(manifest["files"]) == shipped and all(manifest["files"][n] == digest(n) for n in shipped))
    regen = text("authoring", "evidence", "regenerate.txt") if os.path.exists(os.path.join(HERE, "regenerate.txt")) else ""
    check("regenerate.txt records the generator making every one of those files again, byte for byte",
          "%d files, 0 different, 0 not listed" % len(shipped) in regen)

    # ---- the two images and the reward script
    vdock = text("tests", "Dockerfile")
    vlines = [l.strip() for l in vdock.splitlines()]
    check("tests/Dockerfile has the lines intake reads as text",
          all(l in vlines for l in ("RUN mkdir -p /app/output", "COPY . /tests/", "WORKDIR /tests", "ENV PYTHONUNBUFFERED=1")))
    check("tests/Dockerfile pins pytest 8.4.1, pytest-json-ctrf 0.3.5, numpy 2.1.3, scipy 1.14.1, pandas 2.2.3",
          all(p in vdock for p in ("pytest==8.4.1", "pytest-json-ctrf==0.3.5", "numpy==2.1.3", "scipy==1.14.1", "pandas==2.2.3")))
    edock = text("environment", "Dockerfile")
    check("the agent's image pins the same numpy, scipy and pandas",
          all(p in edock for p in ("numpy==2.1.3", "scipy==1.14.1", "pandas==2.2.3")))
    check("threads are held to one in both images and in the run's own environment",
          all("ENV OMP_NUM_THREADS=1" in d and "ENV OPENBLAS_NUM_THREADS=1" in d for d in (vdock, edock))
          and '"OMP_NUM_THREADS": "1"' in judge and '"OPENBLAS_NUM_THREADS": "1"' in judge)
    check("the verifier's image closes /tests and /logs/verifier to every account but root",
          "chmod -R u=rwX,go= /tests" in vdock and "install -d -m 700 -o 0 -g 0 /logs/verifier" in vdock)
    elines = [l.strip() for l in edock.splitlines() if l.strip() and not l.strip().startswith("#")]
    check("the agent's image: users agent and crew, one sudo rule checked by visudo, books only crew can read, "
          "and it ends as root",
          "--shell /bin/bash agent" in edock and "--shell /usr/sbin/nologin crew" in edock
          and "agent ALL=(crew) NOPASSWD: /opt/crew/lab.py" in text("environment", "rig", "sudoers")
          and "env_reset" in text("environment", "rig", "sudoers") and "visudo -cf /etc/sudoers.d/crew" in edock
          and "chmod 700 /opt/crew/sealed" in edock and "-o crew -g crew -m 700 /opt/crew/state" in edock
          and not elines[-1].upper().startswith("USER "))
    sh = text("tests", "test.sh")
    writes = [l.strip() for l in sh.splitlines() if "reward.txt" in l and not l.strip().startswith(("#", "rm "))]
    check("test.sh writes the reward only as the two literal lines, the 0 first",
          writes == ['echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt',
                     'echo -n "0" > /logs/verifier/reward.txt'])
    check("test.sh runs the one pytest file with the report and cache flags intake looks for, then one_passed.py",
          "python -m pytest test_airflow.py -q -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json" in sh
          and "mkdir -p /logs/verifier" in sh and "python one_passed.py /logs/verifier/ctrf.json" in sh)
    check("the verifier's test is one test", len(re.findall(r"(?m)^def test_", text("tests", "test_airflow.py"))) == 1)

    # ---- the reference and the studies
    check("solution/solve.sh puts solution/airflow.py at /app/output/airflow.py",
          'cp "$from/airflow.py" /app/output/airflow.py' in text("solution", "solve.sh"))
    missing = [s for s in STUDIES if not os.path.exists(os.path.join(HERE, s + ".txt"))]
    check("every study's output is committed", not missing, ", ".join(missing))
    out = {s: (text("authoring", "evidence", s + ".txt") if s not in missing else "") for s in STUDIES}
    bad = [s for s in STUDIES if re.search(r"UNEXPECTED|Traceback|DOES NOT HOLD|DIFFERENT  ", out[s])]
    check("no study reports anything unexpected", not bad, ", ".join(bad))
    ref = out["reference_run"]
    check("reference_run.txt: accepted on the six districts, on the three packages beside the program and on the small districts",
          ref.count("\n  accepted") == 3 and "not accepted" not in ref and "reference accepted on all three sets" in ref)
    slowest = re.search(r"the limit of (\d+) s is (\d+\.\d) times the slowest", ref)
    check("the limit is between 2 and 3.5 times the reference's slowest run",
          bool(slowest) and int(slowest.group(1)) == limit and 2.0 <= float(slowest.group(2)) <= 3.5)
    naive = out["naive_run"]
    check("naive_run.txt: the second solution is right on the small districts and stopped at the limit on the six",
          "\n  accepted\n" in naive and "over the limit" in naive
          and "the second solution is right where it is given the time and is stopped at the limit" in naive)
    widest = re.search(r"widest departure from the sealed results: (\d\.\d+) of the band", naive)
    check("the band is at least twice the widest departure of the separately written solution",
          bool(widest) and float(widest.group(1)) <= 0.5)
    rec = out["records_run"]
    check("records_run.txt: each program written to the examples is accepted on them; three of the four are not "
          "accepted on the six districts and the sound variation is; with no order placed the examples are out of band",
          rec.count("the two examples: accepted") == 4 and rec.count("the two examples: not accepted") == 1
          and rec.count("\n  not accepted") == 4 and rec.count("\n  accepted") == 1 and "nothing unexpected" in rec)
    check("design_rules.txt: every rule holds", bool(re.search(r"\n\d+ rules, 0 not holding", out["design_rules"])))
    check("verifier_checks.txt and verifier_run.txt end with nothing unexpected",
          bool(re.search(r"\n\d+ cases, 0 unexpected", out["verifier_checks"]))
          and out["verifier_run"].rstrip().endswith("nothing unexpected"))
    check("verifier_run.txt is tests/test.sh itself: reward 1 for the reference, 0 for the other two",
          out["verifier_run"].startswith("bash tests/test.sh") and len(re.findall(r"\n  reward 1 ", out["verifier_run"])) == 1
          and len(re.findall(r"\n  reward 0 ", out["verifier_run"])) == 2)

    # every figure the README quotes is in a study, the statement, the data's generator, the standard or the checker
    corpus = ins + text("task.toml").split("[metadata]")[0] + "".join(out.values())
    for part in (("authoring", "provenance", "districts.py"), ("authoring", "provenance", "district.py"),
                 ("authoring", "provenance", "network.py"), ("tests", "judge_airflow.py"), ("tests", "Dockerfile"),
                 ("solution", "airflow.py"), ("authoring", "evidence", "naive_airflow.py"),
                 ("environment", "data", "docs", "vs4_ventilation_networks.md"),
                 ("environment", "data", "docs", "district_package.md")):
        corpus += text(*part)
    known = set(re.findall(r"\d+(?:\.\d+)?", corpus.replace(",", "")))
    known |= set(re.findall(r"\d+(?:\.\d+)?", corpus))
    quoted = set(re.findall(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-]|\.\d)", readme.split("## Difficulty", 1)[-1].replace(",000", "000").replace(",500", "500")))
    loose = sorted(q for q in quoted if q not in known and not (q.isdigit() and int(q) <= 12))
    check("every figure in the README is in a study, the statement, the standard, the generator or the checker",
          not loose, ", ".join(loose[:12]))

    # ---- the checker, live, on small programs, under the umask tests/test.sh sets: nothing the checker makes
    # for the program may depend on it
    os.umask(0o077)
    check("test.sh sets umask 077, and these live runs are made under it", "\numask 077\n" in sh)
    name = "new_incline"
    result = rows("authoring", "evidence", "small", "results", name + ".csv")
    head = ",".join(judge_airflow.HEADER)
    good = (head + "\n" + "\n".join("%s,%s" % (r["point"], r["flow_m3_s"]) for r in result) + "\n").encode()
    moved = lambda share: (head + "\n" + "\n".join(
        "%s,%.6f" % (r["point"], (1.0 + share) * float(r["flow_m3_s"])) for r in result) + "\n").encode()
    live = [
        ("the sealed table of a small district is accepted", good, True),
        ("the same with CRLF line ends and the rows reversed is accepted",
         (head + "\r\n" + "\r\n".join("%s,%s" % (r["point"], r["flow_m3_s"]) for r in result[::-1]) + "\r\n").encode(), True),
        ("the same with a capitalised header is not", good.replace(head.encode(), head.upper().encode()), False),
        ("the same with one point left out is not", good.replace(("%s,%s\n" % (result[1]["point"], result[1]["flow_m3_s"])).encode(), b""), False),
        ("the same with one value nan is not", good.replace(("," + result[0]["flow_m3_s"] + "\n").encode(), b",nan\n", 1), False),
        ("every airflow 1.4 per cent high is accepted", moved(0.014), True),
        ("every airflow 1.6 per cent high is not", moved(0.016), False),
    ]
    for what, payload, want in live:
        verdict = common.run(table_program(payload), "small", only=[name])
        check("live: " + what, verdict["accepted"] == want)
    late = common.run(table_program(good, "time.sleep(20)\n"), "small", limit=2, only=[name])
    note = late["districts"][name]
    check("live: a program that writes the sealed table and is still running at the limit is not accepted, and its "
          "table is not opened", not late["accepted"] and note["run"] == "over the limit"
          and "points_out_of_band" not in note and "not_the_table" not in note and bool(late["stopped"]))
    brief = common.run(common.REFERENCE, "small", only=[name])
    check("live: the reference on the small district is accepted and places one order of the district's allowance",
          brief["accepted"] and len(brief["districts"][name]["survey_order"]) == 4)

    print("%d checks, %d failed%s" % (count, failures, ": the bundle is clean" if not failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
