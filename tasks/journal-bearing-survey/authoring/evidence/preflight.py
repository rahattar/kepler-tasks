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
import shutil
import sys
import tempfile
import tomllib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import common  # noqa: E402
from common import grade_program  # noqa: E402

STUDIES = ("design_rules", "reference_run", "naive_run", "register_run", "verifier_checks", "verifier_run",
           "regenerate")
CLOSE = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
         "specific to this task.")
LIMIT_SENTENCE = "Each run of bearing.py must finish within %d seconds on 1 CPU."
VISIBLE_WORDS = ("trap", "hidden", "truth", "overfit", "probe", "two charges", "second charge", "split", "divided",
                 "screen", "verifier", "grader", "pytest")
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
             and re.search(r"\b(b64decode|b64encode|rot13|unhexlify|fromhex|decompress)\b", text(n))]
    check("no encoded strings or decoders in any program", not coded, ", ".join(coded))

    # ---- task.toml
    with open(os.path.join(ROOT, "task.toml"), "rb") as handle:
        toml = tomllib.load(handle)
    meta = toml.get("metadata", {})
    task = os.path.basename(ROOT)
    check("the task's name ends with the bundle folder's name, of at most three hyphenated words",
          toml["task"]["name"].split("/")[-1] == "journal-bearing-survey"
          and (task == "journal-bearing-survey" or not task.startswith("journal")))
    check("the one artifact is /app/output/bearing.py", toml.get("artifacts") == ["/app/output/bearing.py"])
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
    check("the README's notes say what the shift in the data is and where it is built",
          "## Submission notes" in readme and "authoring/provenance/sites.py" in readme.split("## Submission notes")[-1]
          and "west_quarry" in readme.split("## Submission notes")[-1])

    # ---- the task statement
    ins = text("instruction.md")
    body = ins.replace(CLOSE, "")
    check("the statement ends with a blank line and the closing sentence", ins.rstrip("\n").endswith("\n\n" + CLOSE))
    check("the statement has no heading", not re.search(r"(?m)^\s{0,3}#", ins))
    check("the statement assigns no role and speaks to no one",
          not re.search(r"\b(you|your|we|our|I|imagine|pretend)\b", body) and not re.search(r"(?i)\bas an? [a-z ]*engineer\b", body))
    words = re.findall(r"(?i)\b(grader|graded|grading|verifier|reward|score[sd]?|scoring|partial credit|tested|"
                       r"pass(?:es|ed)?|fail(?:s|ed)?)\b", body)
    check("the statement has no grading words", not words, ", ".join(sorted(set(words))))
    limit = grade_program.RUN_LIMIT_S
    check("the statement gives the limit in the required sentence, and it is the checker's: %d s" % limit,
          LIMIT_SENTENCE % limit in ins and len(re.findall(r"within \d+ seconds", ins)) == 1)
    check("the checker enforces that limit with a timeout on the run and treats TimeoutExpired as the end of the "
          "assessment", "started.wait(timeout=limit)" in text("tests", "grade_program.py")
          and "except subprocess.TimeoutExpired" in text("tests", "grade_program.py")
          and "def assess(program, sites=None, truths=None, books=None, limit=RUN_LIMIT_S" in text("tests", "grade_program.py"))
    check("the statement's header is the checker's", "`" + ",".join(grade_program.COLUMNS) + "`" in ins)
    bands = {name: band for name, _, band in grade_program.BANDS}
    check("the statement's bands are the checker's: 1.5 per cent, 1 degree, 0.5 K",
          bands == {"h_min_um": 0.015, "power_kW": 0.015, "p_max_MPa": 0.015, "attitude_deg": 1.0, "t_eff_C": 0.5}
          and "within 1.5 per cent of the result to LS-3" in ins and "within 1 degree" in ins and "within 0.5 K" in ins)
    check("the statement names the command and how the program is run",
          "`python3 bearing.py PACKAGE_DIR OUT_CSV`" in ins and "`labsample`" in ins and "`/app/output/bearing.py`" in ins)
    named = re.findall(r"`(/app/data/[^`]*)`", ins)
    check("every path the statement names is in the image's data", bool(named)
          and all(os.path.exists(os.path.join(ROOT, "environment", "data", p[len("/app/data/"):])) for p in named),
          ", ".join(p for p in named if not os.path.exists(os.path.join(ROOT, "environment", "data", p[len("/app/data/"):]))))
    docs = sorted(os.listdir(os.path.join(ROOT, "environment", "data", "docs")))
    check("the statement names both documents and all three packages by absolute path",
          all("/app/data/docs/" + d in ins for d in docs) and "/app/data/examples/north_works" in ins
          and "/app/data/examples/east_works" in ins and "/app/data/pending/west_quarry" in ins)
    sizes = [len(common.rows_of(os.path.join(common.SITES, name, "points.csv"))) for name in common.HIDDEN]
    check("no package the program is run on has more than the 3,000 points the statement gives (most: %d)" % max(sizes),
          "up to 3,000 operating points" in ins and max(sizes) <= 3000)

    # ---- what the program's author can read
    seen = [n for n in everything if n.startswith(("environment/data/", "environment/rig/lab", "instruction.md"))
            and not n.startswith("environment/rig/sealed")]
    loud = []
    for name in seen:
        low = text(name).lower().replace(".split(", "(").replace(".rsplit(", "(")     # the string method is not a word
        loud += ["%s: %s" % (name, w) for w in VISIBLE_WORDS if re.search(r"\b%s\b" % re.escape(w), low)]
    check("nothing the program's author can read uses the authoring vocabulary", not loud, "; ".join(loud[:4]))
    check("the example packages carry results and the pending package none",
          all(os.path.exists(os.path.join(common.VISIBLE, "examples", n, "expected.csv")) for n in common.EXAMPLES)
          and sorted(os.listdir(os.path.join(common.VISIBLE, "pending", common.PENDING))) == sorted(grade_program.PACKAGE))
    check("the verifier's copy of /app/data is the image's, file for file",
          sorted((n[len("environment/data/"):], digest(n)) for n in everything if n.startswith("environment/data/"))
          == sorted((n[len("tests/app_data/"):], digest(n)) for n in everything if n.startswith("tests/app_data/")))
    check("the laboratory is one program: tests/lab/lab.py is environment/rig/lab.py",
          digest("tests/lab/lab.py") == digest("environment/rig/lab.py"))
    check("the verifier's labsample looks for the laboratory where the checker opens it",
          'DESK = "%s"' % grade_program.DESK in text("tests", "lab", "labsample"))
    both = (text("tests", "lab", "labsample"), text("environment", "rig", "labsample"))
    check("both labsample wrappers print the same usage and the same words for a package without site.json",
          all('USAGE = "usage: labsample PACKAGE_DIR TAG [TAG ...]"' in t
              and '"%s is not a site package: no site.json naming the site" % argv[0]' in t for t in both))

    # ---- the sites
    hidden_names = set(common.HIDDEN)
    visible_names = set(common.EXAMPLES) | {common.PENDING}
    check("six sites to run on, three beside the program, no name in both",
          len(hidden_names) == 6 and not hidden_names & visible_names
          and set(os.listdir(os.path.join(common.VISIBLE, "examples"))) == set(common.EXAMPLES)
          and os.listdir(os.path.join(common.VISIBLE, "pending")) == [common.PENDING])
    check("each of the six is the six files of a package and nothing else",
          all(sorted(os.listdir(os.path.join(common.SITES, n))) == sorted(grade_program.PACKAGE) for n in common.HIDDEN))
    covered = True
    for name in common.HIDDEN:
        points = {p["point"] for p in common.rows_of(os.path.join(common.SITES, name, "points.csv"))}
        truth = common.rows_of(os.path.join(common.TRUTHS, name + ".csv"))
        covered &= points == {r["point"] for r in truth} and len(truth) == len(points) and list(truth[0]) == grade_program.COLUMNS
    check("the sealed results have one row for every point of each of the six, in the statement's columns", covered)
    check("no site's name, and no results, anywhere in the agent's image but its own three",
          not [n for n in everything if n.startswith("environment/") and any(h in n or h in text(n) for h in hidden_names)
               and n.endswith((".csv", ".json", ".md", ".py", "Dockerfile", "labsample"))])
    books_ok = True
    for where, names in ((common.BOOKS, common.HIDDEN), (common.VISIBLE_BOOKS, sorted(visible_names))):
        books_ok &= sorted(os.listdir(where)) == sorted(n + ".json" for n in names)
        for name in names:
            book = grade_program.lab.book_of(where, name)
            package = os.path.join(common.SITES, name) if where == common.BOOKS else os.path.join(
                common.VISIBLE, "pending" if name == common.PENDING else "examples", name)
            with open(os.path.join(package, "site.json")) as handle:
                site = json.load(handle)
            tags = {b["tag"] for b in common.rows_of(os.path.join(package, "bearings.csv"))}
            books_ok &= book["budget"] == site["lab_samples"] and set(book["analyses"]) == tags and site["site"] == name
    check("the laboratory holds a book for each site, with the package's allowance and an analysis for every bearing",
          books_ok)
    manifest = json.loads(text("authoring", "provenance", "manifest.json"))
    shipped = sorted(n for n in everything if n.startswith(("environment/data/examples/", "environment/data/pending/",
                                                           "environment/rig/sealed/", "tests/sites/", "tests/sealed/",
                                                           "tests/lab/sealed/")))
    check("the manifest lists every data file with its SHA-256, and every one matches (%d files)" % len(shipped),
          sorted(manifest["files"]) == shipped and all(manifest["files"][n] == digest(n) for n in shipped))
    regen = text("authoring", "evidence", "regenerate.txt") if os.path.exists(os.path.join(HERE, "regenerate.txt")) else ""
    check("regenerate.txt records the generator making every one of those files again, byte for byte",
          "%d files, 0 different" % len(shipped) in regen)

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
          and '"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"' in text("tests", "grade_program.py"))
    check("the verifier's image closes /tests and /logs/verifier to every account but root",
          "chmod -R u=rwX,go= /tests" in vdock and "install -d -m 700 -o 0 -g 0 /logs/verifier" in vdock)
    elines = [l.strip() for l in edock.splitlines() if l.strip() and not l.strip().startswith("#")]
    check("the agent's image: users agent and lab, one sudo rule checked by visudo, books only lab can read, "
          "and it ends as root",
          "--shell /bin/bash agent" in edock and "--shell /usr/sbin/nologin lab" in edock
          and "agent ALL=(lab) NOPASSWD: /opt/lab/lab.py" in text("environment", "rig", "sudoers")
          and "env_reset" in text("environment", "rig", "sudoers") and "visudo -cf /etc/sudoers.d/lab" in edock
          and "chmod 700 /opt/lab/sealed" in edock and "-o lab -g lab -m 700 /opt/lab/state" in edock
          and not elines[-1].upper().startswith("USER "))
    sh = text("tests", "test.sh")
    writes = [l.strip() for l in sh.splitlines() if "reward.txt" in l and not l.strip().startswith(("#", "rm "))]
    check("test.sh writes the reward only as the two literal lines, the 0 first",
          writes == ['echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt',
                     'echo -n "0" > /logs/verifier/reward.txt'])
    check("test.sh runs the one pytest file with the report and cache flags intake looks for, then read_report.py",
          "python -m pytest test_program.py -q -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json" in sh
          and "mkdir -p /logs/verifier" in sh and "python read_report.py /logs/verifier/ctrf.json" in sh)
    check("the verifier's test is one test", len(re.findall(r"(?m)^def test_", text("tests", "test_program.py"))) == 1)

    # ---- the reference and the studies
    check("solution/solve.sh puts solution/bearing.py at /app/output/bearing.py",
          'cp "$here/bearing.py" /app/output/bearing.py' in text("solution", "solve.sh"))
    missing = [s for s in STUDIES if not os.path.exists(os.path.join(HERE, s + ".txt"))]
    check("every study's output is committed", not missing, ", ".join(missing))
    out = {s: (text("authoring", "evidence", s + ".txt") if s not in missing else "") for s in STUDIES}
    bad = [s for s in STUDIES if re.search(r"UNEXPECTED|Traceback|FAILS  ", out[s])]
    check("no study reports anything unexpected", not bad, ", ".join(bad))
    ref = out["reference_run"]
    check("reference_run.txt: accepted on the six sites and on both example sites",
          ref.count("\naccepted") == 2 and "NOT ACCEPTED" not in ref)
    slowest = re.search(r"the limit of (\d+) s is (\d+\.\d) times the slowest run", ref)
    check("the limit is between 2 and 3.5 times the reference's slowest run, and that run takes more than a second",
          bool(slowest) and int(slowest.group(1)) == limit and 2.0 <= float(slowest.group(2)) <= 3.5)
    naive = out["naive_run"]
    check("naive_run.txt: the unoptimised solution is right on the cut-down sites and over the limit on the sites as "
          "they are", "\naccepted\n" in naive and "over the limit" in naive and naive.rstrip().endswith("not accepted"))
    widest = re.search(r"is (\d\.\d+) of a band", naive)
    check("every band is at least twice the widest departure of the separately written solution",
          bool(widest) and float(widest.group(1)) <= 0.5)
    reg = out["register_run"]
    check("register_run.txt: each program written to the examples is accepted on them and not on the six sites",
          reg.count("the two example sites: accepted") >= 2 and reg.count("the six sites: not accepted") == 3
          and "the six sites: accepted" not in reg)
    check("design_rules.txt: every rule holds", bool(re.search(r"\n\d+ rules, 0 not holding", out["design_rules"])))
    check("verifier_checks.txt and verifier_run.txt end with nothing unexpected",
          bool(re.search(r"\n\d+ cases, 0 unexpected", out["verifier_checks"]))
          and "3 programs, 0 unexpected" in out["verifier_run"])
    check("verifier_run.txt is tests/test.sh itself: reward 1 for the reference, 0 for the other two",
          out["verifier_run"].startswith("bash tests/test.sh") and len(re.findall(r"reward 1 in", out["verifier_run"])) == 1
          and len(re.findall(r"reward 0 in", out["verifier_run"])) == 2)

    # every figure the README quotes is in a study, the statement, the data's generator or the checker
    corpus = ins + text("task.toml").split("[metadata]")[0] + "".join(out.values())
    for part in (("authoring", "provenance", "sites.py"), ("authoring", "provenance", "film.py"),
                 ("tests", "grade_program.py"), ("tests", "Dockerfile"), ("solution", "bearing.py"),
                 ("authoring", "evidence", "naive_bearing.py"), ("environment", "data", "docs", "ls3_journal_bearings.md"),
                 ("environment", "data", "docs", "site_package.md")):
        corpus += text(*part)
    for name in sorted(os.listdir(os.path.join(common.VISIBLE, "pending", common.PENDING))):
        if name != "points.csv":
            corpus += text("environment", "data", "pending", common.PENDING, name)
    known = set(re.findall(r"\d+(?:\.\d+)?", corpus.replace(",", "")))
    known |= set(re.findall(r"\d+(?:\.\d+)?", corpus))
    quoted = set(re.findall(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-]|\.\d)", readme.split("## Difficulty", 1)[-1].replace(",000", "000")))
    loose = sorted(q for q in quoted if q not in known and not (q.isdigit() and int(q) <= 12))
    check("every figure in the README is in a study, the statement, the standard, the generator or the checker",
          not loose, ", ".join(loose[:12]))

    # ---- the checker, live, on small programs, under the umask tests/test.sh sets: nothing the checker makes
    # for the program may depend on it
    os.umask(0o077)
    check("test.sh sets umask 077, and these live runs are made under it", "\numask 077\n" in sh)
    root, sites, truths = common.staged(["south_yard"], every=60)
    atexit.register(shutil.rmtree, root, True)
    truth = common.rows_of(os.path.join(truths, "south_yard.csv"))
    head = ",".join(grade_program.COLUMNS)
    good = (head + "\n" + "\n".join(",".join(r[c] for c in grade_program.COLUMNS) for r in truth) + "\n").encode()
    live = [
        ("the true table of a cut-down site is accepted", good, "", True),
        ("the same with CRLF line ends and the rows reversed is accepted",
         (head + "\r\n" + "\r\n".join(",".join(r[c] for c in grade_program.COLUMNS) for r in truth[::-1]) + "\r\n").encode(), "", True),
        ("the same with a capitalised header is not", good.replace(head.encode(), head.upper().encode()), "", False),
        ("the same with one point left out is not", good.replace((",".join(truth[1][c] for c in grade_program.COLUMNS) + "\n").encode(), b""), "", False),
        ("the same with one value nan is not", good.replace(("," + truth[0]["power_kW"] + ",").encode(), b",nan,", 1), "", False),
        ("the same with every power loss 1.6 per cent high is not",
         (head + "\n" + "\n".join(",".join(("%.6f" % (1.016 * float(r[c]))) if c == "power_kW" else r[c]
                                           for c in grade_program.COLUMNS) for r in truth) + "\n").encode(), "", False),
    ]
    for what, payload, then, want in live:
        outcome = common.assess(table_program(payload, then), sites=sites, truths=truths)
        check("live: " + what, outcome.accepted == want)
    late = common.assess(table_program(good, "time.sleep(20)\n"), sites=sites, truths=truths, limit=2)
    entry = late.sites["south_yard"]
    check("live: a program that writes the true table and is still running at the limit is not accepted, and its "
          "table is not opened", not late.accepted and entry["run"] == "over the limit"
          and "points_out_of_band" not in entry and "refused" not in entry and bool(late.stopped))
    brief = common.assess(common.REFERENCE, sites=sites, truths=truths)
    check("live: the reference on the cut-down site is accepted and places one order of the site's allowance",
          brief.accepted and len(brief.sites["south_yard"]["laboratory_order"]) == 5)

    print("%d checks, %d failed%s" % (count, failures, ": the bundle is clean" if not failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
