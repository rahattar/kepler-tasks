"""Structural pre-flight. Everything the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Run from anywhere. Exits non-zero if anything fails. Needs numpy and pandas (the record regeneration check);
everything else is standard library.
"""
import base64, hashlib, io, os, re, subprocess, sys, tempfile, tomllib

sys.dont_write_bytecode = True   # the junk check must not trip on this script's own imports

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment", "solution", "tests", "authoring"}
# Internal programme names that must not appear anywhere but the mandated [task].name prefix.
# Stored encoded because this file ships inside the bundle.
BLOCKED = tuple(base64.b64decode(s).decode() for s in ("YWZ0ZXJxdWVyeQ==", "a2VwbGVy"))
FAILS, WARNS = [], []
PASSED = 0


def check(ok, msg):
    """msg describes the FAILURE. Passing checks are counted, not printed."""
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILS.append(msg)


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    os.chdir(ROOT)
    extra = {e for e in set(os.listdir(".")) - ALLOWED_ROOT if not e.startswith(".")}
    check(not extra, "root has entries the structure check rejects: %s" % sorted(extra))
    hidden = [e for e in os.listdir(".") if e.startswith(".")]
    check(not hidden, "hidden entries at the root: %s" % hidden)
    JUNK_DIRS = ("__pycache__", ".pytest_cache", ".ipynb_checkpoints", ".mypy_cache", ".ruff_cache", "jobs")
    JUNK_FILES = (".DS_Store", "Thumbs.db", ".coverage")
    JUNK_SUFFIX = (".pyc", ".pyo", ".orig", ".rej", ".bak", ".swp", "~")
    junk = []
    for r, dirs, fns in os.walk("."):
        junk += [os.path.join(r, fn) for fn in fns if fn in JUNK_FILES or fn.endswith(JUNK_SUFFIX)]
        for d in [d for d in dirs if d in JUNK_DIRS or d == ".git"]:
            junk.append(os.path.join(r, d)); dirs.remove(d)
    check(not junk, "junk that must be removed: %s" % junk[:6])
    upper = [os.path.join(r, n) for r, dirs, fns in os.walk(".") for n in dirs + fns
             if n.split(".")[0].isupper() and n != "README.md" and n != "Dockerfile"]
    check(not upper, "all-uppercase file or folder names: %s" % upper[:6])

    SEALED = ("tc.py",)
    for p in ["task.toml", "README.md", "environment/Dockerfile", "environment/start-tcwafer",
              "environment/tcwafer/run-service", "environment/tcwafer/server.py", "solution/solve.sh", "solution/solve.py",
              "tests/test.sh", "tests/Dockerfile", "tests/grade_tc.py", "tests/test_corrections.py",
              "authoring/instruction-fact-sheet.md", "authoring/provenance/gen.py", "authoring/evidence/methods.py",
              "authoring/evidence/route_study.py", "authoring/evidence/route_study.txt",
              "authoring/evidence/method_spread.py", "authoring/evidence/method_spread.txt",
              "authoring/evidence/campaign_study.py", "authoring/evidence/campaign_study.txt"] + \
            ["%s/%s" % (d, f) for d in ("environment/tcwafer", "tests", "authoring/provenance") for f in SEALED]:
        check(os.path.exists(p), "missing required file %s" % p)
    if not os.path.exists("instruction.md"):
        WARNS.append("instruction.md is not written yet -- written by hand by the author")

    with open("task.toml", "rb") as f:
        t = tomllib.load(f)
    raw = open("task.toml").read()
    name = t["task"]["name"]
    check(name.startswith(BLOCKED[0] + "/"), "[task].name must carry the mandated prefix")
    slug = name.split("/", 1)[1]
    check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) is not None, "slug must be lowercase kebab-case")
    check(slug.count("-") <= 2, "slug may be at most 3 hyphenated words: %s" % slug)
    check(t.get("artifacts") == ["/app/output/corrections.csv"], "artifacts must be ['/app/output/corrections.csv']")
    check("artifacts" in raw.split("[")[0], "'artifacts' must sit above the first [section]")
    md = t["metadata"]
    check(md["category"] == "Science", "category must be exactly 'Science'")
    check(md["domain"] == "engineering-sciences" and md["field"] == "mechanical-engineering", "domain/field")
    check(t["task"]["keywords"] == md["tags"], "keywords and tags must match")
    check(9000 <= t["agent"]["timeout_sec"] <= 28800, "[agent].timeout_sec must be 9000-28800")
    check(t["verifier"]["timeout_sec"] <= 13500, "[verifier].timeout_sec must be at most 13500")
    check(t["agent"].get("user") == "agent", "[agent] user must be 'agent' (the agent must not run as root)")
    check(t["verifier"]["environment_mode"] == "separate", "verifier environment_mode")
    check(t["verifier"]["environment"]["network_mode"] == "no-network", "verifier must have no network")
    check(t["environment"]["network_mode"] == "public", "agent environment network_mode")
    check(t["environment"]["cpus"] in (1, 2, 4, 8, 16), "cpus in the enumerated set")
    check(t["environment"]["memory_mb"] in (1024, 2048, 4096, 8192, 16384), "memory_mb")
    check(t["environment"]["storage_mb"] <= 40960, "storage_mb")
    check(t["environment"].get("gpus", 0) == 0, "no GPU")
    check("allow_internet" not in raw, "'allow_internet' is deprecated and fails")
    for fld in ("author_organization", "author_profile", "conflicts_of_interest", "relevant_experience",
                "difficulty_explanation", "solution_explanation", "verification_explanation"):
        check("@@" not in md.get(fld, "") and md.get(fld, "").strip(), "task.toml [%s] is a placeholder" % fld)
    check(raw.isascii(), "task.toml has non-ASCII characters")
    check(re.search(r"synthetic|fictional", md["difficulty_explanation"], re.I) is not None,
          "difficulty_explanation must say the data is synthetic")
    check(re.search(r"local trials|\bof [368]\b|agent harness", md["difficulty_explanation"], re.I) is None,
          "difficulty_explanation argues from agent performance; keep trial evidence out of the bundle text")

    rd = open("README.md").read()
    for sec in ("## Difficulty", "## Reference solution", "## Verification"):
        check(sec in rd, "README is missing the required section %s" % sec)
    check(re.search(r"local trials|\bof [368]\b|agent harness|full effort|\bscreen\b", rd, re.I) is None,
          "README carries agent-trial evidence; the quality review read it against the task (Oct 15)")
    for nm, body in (("README.md", rd), ("task.toml", raw)):
        check("TBD" not in body and "@@" not in body, "%s still carries a placeholder" % nm)
        check(body.isascii(), "%s has non-ASCII characters" % nm)

    for df in ("environment/Dockerfile", "tests/Dockerfile"):
        d = open(df).read()
        check("FROM --platform" not in d, "%s must not pin a platform" % df)
        for m in re.findall(r"pip install[^\n]*(?:\\\n[^\n]*)*", d):
            body = re.sub(r"--[\w-]+", " ", m).replace("pip install", " ")
            for tok in body.replace("\\", " ").split():
                if re.match(r"[a-zA-Z]", tok):
                    check("==" in tok, "%s: pip package '%s' is not pinned with ==" % (df, tok))
        if "apt-get install" in d:
            check("apt-get update" in d, "%s: apt-get install without update" % df)
            check("rm -rf /var/lib/apt/lists/*" in d, "%s: apt lists not cleaned" % df)
            check(not re.search(r"apt-get install[^\n]*=[0-9]", d), "%s: apt packages must not be version-pinned" % df)
    td = open("tests/Dockerfile").read()
    check("pytest==8.4.1" in td and "pytest-json-ctrf==0.3.5" in td, "tests/Dockerfile must pin pytest 8.4.1 and ctrf 0.3.5")
    check("chmod 700 /tests" in td, "tests/Dockerfile must make /tests root-only")
    check(re.search(r"^RUN\s+mkdir\s+-p\s+/app/output\s*$", td, re.M) is not None,
          "tests/Dockerfile needs its own line 'RUN mkdir -p /app/output'")
    check("--ctrf=" in open("tests/test.sh").read(), "test.sh must write the ctrf report")
    ts = open("tests/test.sh").read()
    check(re.search(r'echo -n "0" > /logs/verifier/reward.txt', ts) is not None, "test.sh must write reward 0 first")
    # one container: no compose file, no second Dockerfile, no cheat/ directory
    composes = [os.path.join(r, fn) for r, _, fns in os.walk(".") for fn in fns
                if re.fullmatch(r"(docker-)?compose(\.[\w-]+)?\.ya?ml", fn)]
    check(not composes, "compose files are rejected (one container): %s" % composes)
    dockerfiles = sorted(os.path.join(r, fn) for r, _, fns in os.walk(".") for fn in fns if fn == "Dockerfile")
    check(dockerfiles == ["./environment/Dockerfile", "./tests/Dockerfile"], "unexpected Dockerfiles: %s" % dockerfiles)
    cheat = [os.path.join(r, d) for r, ds, _ in os.walk(".") for d in ds if d == "cheat"]
    check(not cheat, "a cheat/ directory fails the structure check: %s" % cheat)

    for r, dirs, fns in os.walk("environment"):
        for fn in fns:
            if fn.endswith((".py", ".sh", ".yaml", ".yml")) or fn == "Dockerfile":
                body = open(os.path.join(r, fn), errors="ignore").read()
                for bad in ("solve.sh", "solve.py", "test.sh", "test_corrections", "grade_tc"):
                    check(bad not in body, "environment/%s references %s" % (fn, bad))
    d = open("environment/Dockerfile").read()
    check(re.findall(r"^COPY\s+(\S+)", d, re.M) == ["data/", "tcwafer/", "start-tcwafer"],
          "environment/Dockerfile must copy data/, tcwafer/ and start-tcwafer only")
    check(not re.search(r"^USER\s", d, re.M), "environment/Dockerfile must end as root (use [agent] user instead of USER)")
    check("useradd --create-home --shell /bin/bash agent" in d, "the image must create the agent user")
    check("chmod 700 /opt/tcwafer" in d and "chmod 600 /opt/tcwafer/*.py" in d and "chmod 700 /var/lib/tcwafer" in d,
          "the service's files and state must be private to the metrology user")
    check("'agent ALL=(metrology) NOPASSWD: /opt/tcwafer/run-service \"\"'" in d,
          "the single sudo rule (no arguments allowed) is missing or changed")
    check(len(re.findall(r"NOPASSWD", d)) == 1, "exactly one sudo rule")
    check("visudo -cf /etc/sudoers.d/tcwafer" in d, "the sudoers file must be validated at build time")
    check("chown metrology:metrology /app/runs" in d and "chown agent:agent /app/output" in d,
          "/app/runs must belong to metrology and /app/output to agent")
    check("chown root:agent /app && chmod 1775 /app" in d and "chown agent:agent /app " not in d,
          "/app must be root's with the sticky bit, so the agent cannot rename /app/runs")
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        m = re.search(r"^ENV\s+%s=(\d+)" % var, d, re.M)
        check(m is not None and int(m.group(1)) <= t["environment"]["cpus"], "%s must be set at or below cpus" % var)
    check("ENV TCWAFER_URL=http://127.0.0.1:8000" in d, "TCWAFER_URL must point at the local service")
    sv = open("environment/tcwafer/server.py").read()
    check("os.environ" not in sv, "the service must not read its caller's environment")
    check('"127.0.0.1"' in sv, "the service must bind to localhost only")
    check("O_EXCL" in sv and "O_NOFOLLOW" in sv and "dir_fd=OUT_FD" in sv,
          "reports must be created as new files in the directory opened at start, never through a link")
    check("st.st_uid != os.geteuid()" in sv, "the service must refuse a report directory it does not own")
    check("except FileNotFoundError" in sv and "fail closed" in sv and "fcntl.flock" in sv,
          "an unreadable step record must count as exhausted, and state changes must be locked")
    rs = open("environment/tcwafer/run-service").read()
    check("env -i" in rs and "python3 -I" in rs, "run-service must start the server with a clean environment")
    check("/app/runs" in rs and "/var/lib/tcwafer/state.json" in rs, "run-service must write runs and state")
    st = open("environment/start-tcwafer").read()
    check("sudo -n -u metrology /opt/tcwafer/run-service" in st, "start-tcwafer must call the one sudo rule")
    # the documents carry no sealed definition text
    agent_side = [os.path.join(r, fn) for r, _, fns in os.walk("environment/data") for fn in fns]
    check(not [p for p in agent_side if p.endswith((".py", ".json"))], "code or json in environment/data")
    for p in agent_side:
        body = open(p, "rb").read()
        check(not re.search(rb"make_bay|d1000|G_old|D_TUBE|G_FAT|DG_SIC|spike_err|cal2025_err|gradient=", body),
              "%s carries sealed definition text" % p)
    # agent-side columns: no damper position or anything computed from true airflow
    import csv as _csv
    for fn, cols in (("furnace_register.csv", {"furnace", "model", "process", "liner", "profile_tc", "spike_tc"}),
                     ("maintenance_log.csv", {"date", "furnace", "work_done"}),
                     ("tc_wafer_calibration_2025.csv", {"furnace", "zone", "wafer_minus_profile_850_c",
                                                        "wafer_minus_profile_1050_c"}),
                     ("loaded_corrections.csv", {"furnace", "zone", "correction_850_c", "correction_1050_c", "source"}),
                     ("trends/f1.csv", {"timestamp", "state", "setpoint_c", "boat_wafers"} | {"profile_raw_z%d" % i for i in range(1, 6)}
                      | {"spike_z%d" % i for i in range(1, 6)})):
        with open(os.path.join("environment/data", fn)) as f:
            head = set(next(_csv.reader(f)))
        check(head == cols, "environment/data/%s has unexpected columns %s" % (fn, sorted(head ^ cols)))

    hits = []
    for r, dirs, fns in os.walk("."):
        for fn in fns:
            p = os.path.join(r, fn)
            try:
                body = open(p, errors="ignore").read().lower()
            except OSError:
                continue
            for term in BLOCKED:
                if term in body and not (p.endswith("task.toml") and body.count(term) == 1):
                    hits.append((p, term))
    check(not hits, "blocked internal terms outside [task].name: %s" % hits[:6])
    marker = base64.b64decode("Y2FuYXJ5").decode()
    marked = [os.path.join(r, fn) for r, _, fns in os.walk(".") for fn in fns
              if marker in open(os.path.join(r, fn), errors="ignore").read().lower()]
    check(not marked, "eval-set marker word in: %s (the structure check rejects it)" % marked)
    paths = []
    for r, dirs, fns in os.walk("."):
        for fn in fns:
            if (fn.endswith((".py", ".sh", ".md", ".toml", ".txt")) or fn == "Dockerfile") and fn != "preflight.py":
                body = open(os.path.join(r, fn), errors="ignore").read()
                if re.search(r"/home/|/Users/|/Volumes/|/srv/probes", body):
                    paths.append(os.path.join(r, fn))
    check(not paths, "hard-coded author paths in: %s" % paths[:6])
    # docstrings and READMEs must not name files that are not in the bundle
    present = {fn for _, _, fns in os.walk(".") for fn in fns}
    named = set()
    for r, _, fns in os.walk("."):
        for fn in fns:
            if fn.endswith((".py", ".md", ".toml")) and fn not in ("preflight.py", "check_instruction.py"):
                named |= set(re.findall(r"\b([\w-]+\.(?:py|csv|xlsx|docx|pdf|json|sh|md|txt|toml))\b",
                                        open(os.path.join(r, fn), errors="ignore").read()))
    ghosts = sorted(n for n in named - present if n not in ("corrections.csv", "metrics.json", "ctrf.json", "reward.txt",
                                                                "instruction.md", "state.json", "s.csv", "s.json"))
    check(not ghosts, "files named in text but not in the bundle: %s" % ghosts[:8])

    # the three copies of the sealed definition are identical, and the service's budget is three
    for f in SEALED:
        check(md5("environment/tcwafer/%s" % f) == md5("tests/%s" % f) == md5("authoring/provenance/%s" % f),
              "the copies of %s differ" % f)
    check(len(re.findall(r"^BUDGET\s*=\s*3\s*$", sv, re.M)) == 1, "BUDGET must be assigned 3 exactly once in server.py")
    check(len(re.findall(r"^BUDGET\s*=\s*3\s*$", open("solution/solve.py").read(), re.M)) == 1,
          "the reference must plan for three steps")
    gv = open("tests/tc.py").read()
    check(re.search(r"^TOL\s*=\s*2\.0\b", gv, re.M) is not None, "the requirement in tests/tc.py must be 2.0 K")
    check("within 2 K" in open("environment/data/docs/calibration_spec.md").read(),
          "the calibration requirement must state 2 K")
    proc = open("environment/data/docs/tc_wafer_procedure.md").read()
    check("three steps" in proc and "four steps" not in proc, "the TC-wafer procedure must state the three-step budget")
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_tc", "tests/tc.py"); _tc = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_tc)
    check(_tc.CAL_DATE in proc and '"date": "%s"' % _tc.CAL_DATE not in sv and "date=tc.CAL_DATE" in sv,
          "the run reports and the procedure must carry the calibration date")

    # the generator rewrites every record and trend byte for byte
    sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
    import contextlib
    import gen as gen_mod
    tmp = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()):
        gen_mod.main(tmp)
    made = sorted(os.path.relpath(os.path.join(r, fn), tmp) for r, _, fns in os.walk(tmp) for fn in fns)
    shipped = sorted(os.path.relpath(os.path.join(r, fn), "environment/data") for r, _, fns in os.walk("environment/data")
                     for fn in fns if not fn.endswith(".md"))
    check(shipped == made, "environment/data and the generator disagree on the file list: %s" % sorted(set(shipped) ^ set(made)))
    for fn in made:
        if fn in shipped:
            check(md5(os.path.join(tmp, fn)) == md5(os.path.join("environment/data", fn)),
                  "environment/data/%s is not what the generator writes" % fn)

    if os.path.exists("instruction.md"):
        r = subprocess.run([sys.executable, "-I", "authoring/evidence/check_instruction.py", "instruction.md"],
                           capture_output=True, text=True)
        check(r.returncode == 0, "check_instruction.py failed:\n" + r.stdout.strip())

    for w in WARNS:
        print("  WARN  " + w)
    if FAILS:
        print("\n%d FAILED of %d checks:" % (len(FAILS), PASSED + len(FAILS)))
        for f in FAILS:
            print("  FAIL  " + f)
        return 1
    print("\npre-flight clean: %d checks passed, %d warning(s)" % (PASSED, len(WARNS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
