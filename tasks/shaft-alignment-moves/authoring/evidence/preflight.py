#!/usr/bin/env python3
"""Every rule this bundle has to meet, checked mechanically.

    python3 preflight.py

The last line says how many checks failed. Run it after any change, after the evidence scripts.
"""
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common  # noqa: E402

ROOT = common.ROOT
TASK = "shaft-alignment-moves"
ENTRIES = {"README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"}
CLOSING = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
           "specific to this task.")
HEADER = "tag,v_front_mm,v_rear_mm,h_front_mm,h_rear_mm"
PINS = ("numpy==2.1.3", "scipy==1.14.1", "pandas==2.2.3", "pytest==8.4.1", "pytest-json-ctrf==0.3.5")
METADATA = ("author_name", "author_email", "author_organization", "author_profile", "research_advisor",
            "referred_by", "conflicts_of_interest", "domain", "field", "subfield", "category", "subcategory",
            "tags", "expert_time_estimate_hours", "relevant_experience", "difficulty_explanation",
            "solution_explanation", "verification_explanation")
STUDIES = ("route_study", "method_spread", "independent", "null_baselines", "hedge_study", "visit_study",
           "verifier_checks", "verifier_run", "reference_run", "seed_screen", "tune")
# words the engineer's records must not carry, and words the task statement must not carry
NOT_IN_RECORDS = ("sealed", "grader", "verifier", "synthetic", "authoring", "provenance", "unit3")
NOT_IN_STATEMENT = ("grader", "graded", "grading", "verifier", "reward", "score", "scored", "scoring", "pass",
                    "passes", "passed", "fail", "fails", "failed", "tested", "partial credit", "tolerance")
out = []


def check(what, ok, note=""):
    out.append((what, bool(ok), note))


def text(*parts):
    with open(os.path.join(ROOT, *parts), "rb") as handle:
        return handle.read().decode("utf-8", "replace")


def every_file():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if not name.startswith("."):
                yield os.path.join(base, name)


def tree_differs(a, b):
    cmp = filecmp.dircmp(a, b)
    found = list(cmp.left_only) + list(cmp.right_only) + list(cmp.diff_files)
    for name, sub in cmp.subdirs.items():
        found += tree_differs(os.path.join(a, name), os.path.join(b, name))
    return found


def main():
    me = os.path.abspath(__file__)

    # ---- the bundle
    top = {n for n in os.listdir(ROOT) if not n.startswith(".")}
    check("the bundle holds the seven entries and nothing else", top == ENTRIES, ", ".join(sorted(top ^ ENTRIES)))
    caches = [os.path.relpath(os.path.join(b, n), ROOT) for b, ds, fs in os.walk(ROOT) for n in ds + fs
              if n == "__pycache__" or n.endswith((".pyc", ".pyo"))]
    check("no bytecode caches", not caches, ", ".join(caches[:3]))
    upper, plain, links, outside, encoded, zips = [], [], [], [], [], []
    for path in every_file():
        rel = os.path.relpath(path, ROOT)
        name = os.path.basename(path)
        stem = name.split(".")[0]
        if name not in ("README.md", "Dockerfile") and stem.isupper():
            upper.append(rel)
        if os.path.islink(path):
            links.append(rel)
        if name.endswith(".zip"):
            zips.append(rel)
        body = text(rel)
        if not body.isascii():
            plain.append(rel)
        if path != me:
            # this file has to spell the things it looks for, so it does not look in itself
            for mark in ("/home/", "/Users/", "/mnt/", "/tmp/"):
                if mark in body:
                    outside.append("%s (%s)" % (rel, mark))
            for mark in ("b64decode", "base64", "rot13", "codecs.decode", "unhexlify"):
                if mark in body:
                    encoded.append("%s (%s)" % (rel, mark))
    for base, dirs, _ in os.walk(ROOT):
        upper += [os.path.relpath(os.path.join(base, d), ROOT) for d in dirs if d.isupper()]
    check("no all-uppercase names", not upper, ", ".join(upper))
    check("every file is ASCII", not plain, ", ".join(plain))
    check("no symbolic links and no zip", not links and not zips, ", ".join(links + zips))
    check("no path from outside the bundle", not outside, ", ".join(outside[:4]))
    check("nothing encoded", not encoded, ", ".join(encoded[:4]))

    # ---- the engineer's records
    data = os.path.join(ROOT, "environment", "data")
    said = []
    for base, _, files in os.walk(data):
        for name in files:
            body = text(os.path.relpath(os.path.join(base, name), ROOT)).lower()
            said += ["%s: %s" % (name, w) for w in NOT_IN_RECORDS if w in body]
    check("the records carry no authoring vocabulary", not said, ", ".join(said))
    check("tests/app_data is the records exactly", not tree_differs(data, os.path.join(ROOT, "tests", "app_data")))
    box = tempfile.mkdtemp(prefix="sam_pf_")
    try:
        common.gen.main(os.path.join(box, "data"))
        check("the generator reproduces the shipped records from the seed", not tree_differs(data, os.path.join(box, "data")))
    finally:
        shutil.rmtree(box, ignore_errors=True)

    # ---- the task statement
    ins = text("instruction.md")
    body = ins.replace(CLOSING, "")
    check("the statement has no heading", not re.search(r"(?m)^\s{0,3}#", ins))
    used = [w for w in NOT_IN_STATEMENT if re.search(r"\b%s\b" % re.escape(w), body, re.I)]
    check("the statement uses no grading words", not used, ", ".join(used))
    check("the statement ends with the required paragraph after a blank line",
          re.search(r"\n\n" + re.escape(CLOSING) + r"\n?$", ins) is not None)
    inputs = ["/app/data/" + os.path.relpath(os.path.join(b, n), data) for b, _, fs in os.walk(data) for n in fs]
    absent = sorted(p for p in inputs if p not in ins)
    check("the statement names every input by its absolute path", not absent, ", ".join(absent))
    ghosts = sorted(p for p in set(re.findall(r"/app/data/[\w/.-]+\.\w+", ins)) if p not in inputs)
    check("every input the statement names exists", not ghosts, ", ".join(ghosts))
    check("the statement gives the output path and the header", "/app/output/moves.csv" in ins and HEADER in ins)
    check("the statement asks for exactly three decimal places and one figure a move",
          "exactly three decimal places" in ins and "one figure for every move" in ins)
    check("the statement says where the contractor reports and that the programme is one order",
          "/app/laser_reports" in ins and "in one order" in ins)
    check("the statement does not print the acceptance", ("%.2f" % common.unit3.TOL) not in ins)
    check("the statement names no train, model or group",
          not re.search(r"\b(P|K|TP|FN)-\d|HSC|HS-|CLC|CL-|lagg|blank|jacket|compressor|turbine", ins))

    # ---- task.toml and README.md
    raw = text("task.toml")
    toml = tomllib.loads(raw)
    meta = toml.get("metadata", {})
    check("task.toml: agent 28800 s as user agent", toml["agent"]["timeout_sec"] == 28800.0 and toml["agent"]["user"] == "agent")
    check("task.toml: verifier 600 s, separate, no network",
          toml["verifier"]["timeout_sec"] == 600.0 and toml["verifier"]["environment_mode"] == "separate"
          and toml["verifier"]["environment"]["network_mode"] == "no-network")
    check("task.toml: the artifact is the sheet", toml["artifacts"] == ["/app/output/moves.csv"])
    missing = [k for k in METADATA if k not in meta]
    check("task.toml: the full metadata block", not missing, ", ".join(missing))
    check("task.toml: domain, field, category and a subcategory",
          meta.get("domain") == "engineering-sciences" and meta.get("field") == "mechanical-engineering"
          and meta.get("category") == "Science" and str(meta.get("subcategory", "")).strip())
    check("task.toml: keywords are the tags", toml["task"].get("keywords") == meta.get("tags"))
    parts = toml["task"]["name"].split("/")
    check("task.toml: the name is one prefix and this task's name", len(parts) == 2 and parts[0] and parts[1] == TASK)
    if len(parts) == 2 and parts[0]:
        stray = []
        for path in every_file():
            for number, line in enumerate(text(os.path.relpath(path, ROOT)).splitlines(), 1):
                if parts[0].lower() in line.lower() and not (os.path.basename(path) == "task.toml" and line.startswith("name =")):
                    stray.append("%s:%d" % (os.path.relpath(path, ROOT), number))
        check("the name's prefix is on that one line and nowhere else", not stray, ", ".join(stray[:4]))
    readme = text("README.md")
    diff = str(meta.get("difficulty_explanation", ""))
    check("the difficulty explanation says the data is synthetic and realistic", "synthetic" in diff and "realistic" in diff)
    check("the difficulty explanation names who does the work and the research analogue",
          "engineer" in diff and "research analogue" in diff)
    check("the difficulty explanation carries no agent-performance numbers",
          not re.search(r"\b\d+ of \d+ (runs|trials|attempts|probes)\b|\beffort\b", diff))
    for head, key in (("## Difficulty", "difficulty_explanation"), ("## Reference solution", "solution_explanation"),
                      ("## Verification", "verification_explanation")):
        value = str(meta.get(key, "")).strip()
        check("%s is in task.toml and word for word in the README under %s" % (key, head),
              len(value) > 400 and head in readme and value in readme)

    # every figure the README quotes is in the evidence, the records, the sealed definition or the statement
    corpus = ins + raw.split("[metadata]")[0] + text("authoring", "provenance", "unit3.py") + text("authoring", "provenance", "seed.json")
    for name in STUDIES + ("preflight",):
        path = os.path.join(HERE, name + ".txt")
        corpus += open(path).read() if os.path.exists(path) and name != "preflight" else ""
    for base, _, files in os.walk(data):
        for name in files:
            corpus += text(os.path.relpath(os.path.join(base, name), ROOT))
    for name in ("Dockerfile", "test.sh", "grade_moves.py"):
        corpus += text("tests", name)
    known = set(re.findall(r"\d+(?:\.\d+)?", corpus))
    quoted = set(re.findall(r"(?<![\w.-])\d+(?:\.\d+)?(?![\w-]|\.\d)", readme.split("## Difficulty", 1)[-1]))
    loose = sorted(q for q in quoted if q not in known and not (q.isdigit() and int(q) <= 12))
    check("every figure in the README is in the evidence, the records or the sealed definition", not loose, ", ".join(loose[:12]))

    # ---- the verifier
    vdock = text("tests", "Dockerfile")
    lines = [line.strip() for line in vdock.splitlines()]
    check("tests/Dockerfile: the five pins", all(pin in vdock for pin in PINS))
    check("tests/Dockerfile: the literal lines", "RUN mkdir -p /app/output" in lines and "COPY . /tests/" in lines
          and "WORKDIR /tests" in lines and "ENV PYTHONUNBUFFERED=1" in lines)
    sh = text("tests", "test.sh")
    zero, one, run = 'echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt', "python -m pytest"
    check("test.sh: the literal contract", zero in sh and one in sh and "mkdir -p /logs/verifier" in sh
          and "--ctrf=/logs/verifier/ctrf.json" in sh and "-p no:cacheprovider" in sh)
    check("test.sh: zero first, then grading, then the reward", sh.index(zero) < sh.index(run) < sh.index(one) < sh.rindex(zero))
    check("test.sh: an old report is removed before grading",
          sh.index("rm -f /logs/verifier/ctrf.json") < sh.index(run))
    check("test.sh: the reward is one only on a clean exit and a counted report",
          'case "$graded:$counted" in' in sh and '0:0) ' + one in sh and "*)   " + zero in sh
          and "graded=$?" in sh and "python count_report.py /logs/verifier/ctrf.json\ncounted=$?" in sh)
    check("test.sh: the log directory is closed before grading and again before the reward",
          sh.count("\nclose_logs\n") == 2 and sh.index(run) < sh.rindex("\nclose_logs\n") < sh.index(one))
    check("the verifier's test is one test", len(re.findall(r"(?m)^def test_", text("tests", "test_moves.py"))) == 1)

    # ---- the sealed definition and the contractor
    prov = text("authoring", "provenance", "unit3.py")
    check("the sealed definition is identical in provenance, tests and the contractor's directory",
          prov == text("tests", "sealed", "unit3.py") == text("environment", "rig", "sealed", "unit3.py"))
    seed = text("authoring", "provenance", "seed.json")
    check("the seed is identical in the three places",
          seed == text("tests", "sealed", "seed.json") == text("environment", "rig", "sealed", "seed.json"))
    sealed_dir = os.path.join(ROOT, "environment", "rig", "sealed")
    leaked = [os.path.relpath(os.path.join(b, n), ROOT) for b, _, fs in os.walk(os.path.join(ROOT, "environment"))
              for n in fs if b != sealed_dir and ("K_NOW" in text(os.path.relpath(os.path.join(b, n), ROOT)) or n == "unit3.py")]
    check("the sealed definition is nowhere else in the agent's environment", not leaked, ", ".join(leaked))
    edock = text("environment", "Dockerfile")
    lab = text("environment", "rig", "lab.py")
    check("the image gives the contractor its own account with no shell", "useradd" in edock and "nologin contractor" in edock)
    check("the image closes the contractor's directories",
          "chmod 700 /opt/contractor/sealed /opt/contractor/state" in edock and "chmod 600 /opt/contractor/sealed/*" in edock)
    check("the agent runs one program as the contractor with a clean environment",
          "agent ALL=(contractor) NOPASSWD: /opt/contractor/lab.py" in edock and "env_reset" in edock and "visudo -cf" in edock)
    check("the way in is the laservisit wrapper", "/usr/local/bin/laservisit" in edock and 'lab.py laservisit "$@"' in edock)
    check("the contractor's reports are its own to write",
          "install -d -o contractor -g contractor -m 755 /app/laser_reports" in edock)
    last = [line for line in edock.splitlines() if line.strip() and not line.strip().startswith("#")][-1]
    check("the agent's image ends as root", not last.upper().startswith("USER "))
    check("the contractor writes the order down before measuring, exclusively and never through a link",
          lab.index("O_EXCL") < lab.index("unit3.laser_report") and "O_NOFOLLOW" in lab)
    check("the contractor takes exactly the budget, once", "len(wanted) != unit3.BUDGET" in lab and "takes no second order" in lab)
    check("the contractor refuses to work in directories that are not as installed", lab.count("own_directory(") >= 4)
    service = text("environment", "data", "docs", "laser_service.md")
    check("the service note and the sealed budget agree", ("time for %d trains" % common.unit3.BUDGET) in service)
    check("AP-12 states the acceptance the sealed definition uses",
          ("within %.2f mm" % common.unit3.TOL) in text("environment", "data", "docs", "alignment_procedure.md"))

    # ---- the reference and the reader
    sheet, programme = common.run()
    outcome = common.grade(sheet)
    worst = max(abs(row["worst_mm"]) for row in outcome.detail.values())
    check("the grader accepts the reference", outcome.accepted, "%d of %d" % (outcome.aligned, outcome.trains))
    check("the reference is within half the acceptance on every train", worst <= common.unit3.TOL / 2, "%.4f" % worst)
    good = "".join("%s,%s\n" % (tag, ",".join("%.3f" % m for m in sheet[tag])) for tag in sorted(sheet))
    first = good.splitlines()[0]
    for what, body_, want in (
            ("CRLF line ends", (HEADER + "\n" + good).replace("\n", "\r\n"), True),
            ("the rows reversed", HEADER + "\n" + "\n".join(reversed(good.splitlines())) + "\n", True),
            ("a blank in the header", HEADER.replace(",v_front", ", v_front") + "\n" + good, False),
            ("a move to two decimals", HEADER + "\n" + good.replace(first, first[:-1], 1), False),
            ("a move to four decimals", HEADER + "\n" + good.replace(first, first + "0", 1), False),
            ("a train left out", HEADER + "\n" + good.replace(first + "\n", "", 1), False)):
        check("the reader on %s: %s" % (what, "taken" if want else "refused"),
              common.grade(None, text=body_).accepted == want)

    # ---- the design rules and the evidence
    done = subprocess.run([sys.executable, "-B", os.path.join(common.PROV, "tune.py")], capture_output=True, text=True)
    check("the design rules hold (tune.py)", done.returncode == 0, (done.stdout.strip().splitlines() or [""])[-1])
    ev = {}
    for name in STUDIES:
        path = os.path.join(HERE, name + ".txt")
        check("authoring/evidence/%s.txt is there" % name, os.path.exists(path))
        ev[name] = open(path).read() if os.path.exists(path) else ""
    newest = max(os.path.getmtime(p) for p in every_file()
                 if p.endswith(".py") and ("/provenance/" in p or "/solution/" in p or "/tests/" in p))
    stale = [n for n in STUDIES if os.path.exists(os.path.join(HERE, n + ".txt"))
             and os.path.getmtime(os.path.join(HERE, n + ".txt")) < newest - 120]
    check("no study is older than the code it describes", not stale, ", ".join(stale))
    broken = [n for n in ev if "Traceback" in ev[n] or re.search(r"(?m)^UNEXPECTED", ev[n])]
    check("no study reports a crash or an unexpected case", not broken, ", ".join(broken))
    total = outcome.trains
    check("every defective route misses a train", "routes that pass on the shipped records: none" in ev["route_study"])
    check("every train is missed by at least three routes", "trains missed by fewer than 3 routes: none" in ev["route_study"])
    check("every sound variation gets every train, on every seed", "variations that miss a train: none" in ev["method_spread"])
    check("the second solution gets every train, shipped and on every laboratory seed",
          ("on the shipped records: %d of %d trains aligned" % (total, total)) in ev["independent"]
          and ("laboratory seeds: %d of %d trains aligned" % (total, total)) in ev["independent"])
    check("no sheet of constants aligns two trains", re.search(r"most trains a sheet of constants aligns: [01]\b", ev["null_baselines"]) is not None)
    check("only the programmes that measure all six get every train",
          "leaves every train aligned: 150 of 1947792" in ev["visit_study"] and "accepted: 150" in ev["visit_study"])
    check("the verifier checks report nothing unexpected", re.search(r"(?m)^\d+ cases, 0 UNEXPECTED", ev["verifier_checks"]) is not None)
    check("pytest agrees on every complete sheet", "; 0 UNEXPECTED" in ev["verifier_run"])
    check("the reference run ends with every train aligned and pytest passing",
          ("%d of %d trains aligned" % (total, total)) in ev["reference_run"] and "1 passed" in ev["reference_run"])
    check("every screened seed is acceptable", re.search(r"acceptable seeds: (\d+) of \1,", ev["seed_screen"]) is not None)

    width = max(len(what) for what, _, _ in out)
    failed = 0
    for what, ok, note in out:
        failed += 0 if ok else 1
        print("%s %-*s %s" % ("pass" if ok else "FAIL", width, what, note if not ok else ""))
    # tools/shipcheck.py reads this line
    print("\n%d checks, %d failed: the bundle is %s" % (len(out), failed, "clean" if not failed else "NOT ready"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
