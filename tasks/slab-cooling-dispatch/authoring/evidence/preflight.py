"""Structural pre-flight. Everything the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Run from anywhere. Exits non-zero if anything fails.
"""
import base64, hashlib, json, os, re, subprocess, sys, tempfile, tomllib

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

    for p in ("task.toml", "README.md", "environment/Dockerfile", "environment/check_controller.py",
              "solution/solve.sh", "solution/fit.py", "solution/controller_template.py",
              "tests/test.sh", "tests/Dockerfile", "tests/grade.py", "tests/host.py", "tests/test_controller.py",
              "tests/bench.json", "tests/world.py", "tests/chicago_tmy3.epw",
              "authoring/provenance/make_public.py", "authoring/provenance/run_bench.py",
              "authoring/provenance/regenerate.py"):
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
    check(t.get("artifacts") == ["/app/controller.py"], "artifacts must be ['/app/controller.py']")
    check("artifacts" in raw.split("[")[0], "'artifacts' must sit above the first [section]")
    md = t["metadata"]
    check(md["category"] == "Science", "category must be exactly 'Science'")
    check(md["domain"] == "engineering-sciences" and md["field"] == "mechanical-engineering", "domain/field")
    check(t["task"]["keywords"] == md["tags"], "keywords and tags must match")
    check(9000 <= t["agent"]["timeout_sec"] <= 28800, "[agent].timeout_sec must be 9000-28800")
    check(t["verifier"]["timeout_sec"] <= 13500, "[verifier].timeout_sec must be at most 13500 (Oct 15 page)")
    check(t["verifier"]["environment_mode"] == "separate", "verifier environment_mode")
    check(t["verifier"]["environment"]["network_mode"] == "no-network", "verifier must have no network")
    check(t["environment"]["network_mode"] == "public", "agent environment network_mode")
    check(t["environment"]["cpus"] in (1, 2, 4, 8, 16), "cpus in the enumerated set")
    check(t["environment"]["memory_mb"] in (1024, 2048, 4096, 8192, 16384), "memory_mb")
    check(t["environment"]["storage_mb"] <= 40960, "storage_mb")
    check("allow_internet" not in raw, "'allow_internet' is deprecated and fails")
    for fld in ("conflicts_of_interest", "relevant_experience", "difficulty_explanation",
                "solution_explanation", "verification_explanation"):
        check("@@" not in md.get(fld, "") and md.get(fld, "").strip(), "task.toml [%s] is a placeholder" % fld)
    check(raw.isascii(), "task.toml has non-ASCII characters")
    check(t["verifier"]["timeout_sec"] > 7200 + 600 + 900, "verifier timeout must cover the controller budget")

    rd = open("README.md").read()
    for sec in ("## Difficulty", "## Reference solution", "## Verification"):
        check(sec in rd, "README is missing the required section %s" % sec)
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
    env_pins = set(re.findall(r"(numpy|scipy)==([\d.]+)", open("environment/Dockerfile").read()))
    ver_pins = set(re.findall(r"(numpy|scipy)==([\d.]+)", open("tests/Dockerfile").read()))
    check(env_pins == ver_pins and len(env_pins) == 2, "numpy/scipy pins differ between the images")
    td = open("tests/Dockerfile").read()
    check("chmod 700 /tests" in td, "tests/Dockerfile must make /tests root-only")
    check(re.search(r"^RUN\s+mkdir\s+-p\s+/app\s*$", td, re.M) is not None,
          "tests/Dockerfile needs its own line 'RUN mkdir -p /app'")
    check(not os.path.exists("environment/docker-compose.yaml"), "no compose file expected")

    for r, dirs, fns in os.walk("environment"):
        for fn in fns:
            if fn.endswith((".py", ".sh", ".yaml", ".yml")) or fn == "Dockerfile":
                body = open(os.path.join(r, fn), errors="ignore").read()
                for bad in ("solve.sh", "fit.py", "controller_template", "test.sh", "test_controller",
                            "bench.json", "grade.py", "world.py", "make_public", "run_bench"):
                    check(bad not in body, "environment/%s references %s" % (fn, bad))
    d = open("environment/Dockerfile").read()
    check(re.findall(r"^COPY\s+(\S+)", d, re.M) == ["data/", "check_controller.py"],
          "environment/Dockerfile must copy only data/ and check_controller.py")

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
    paths = []
    for r, dirs, fns in os.walk("."):
        for fn in fns:
            if (fn.endswith((".py", ".sh", ".md", ".toml", ".txt")) or fn == "Dockerfile") and fn != "preflight.py":
                body = open(os.path.join(r, fn), errors="ignore").read()
                if re.search(r"/home/|/Users/|/Volumes/", body):
                    paths.append(os.path.join(r, fn))
    check(not paths, "hard-coded author paths in: %s" % paths[:6])

    # nothing sealed reaches the agent: the graded weeks' weather, occupancy and benchmark live in tests/
    for r, _, fns in os.walk("environment"):
        for fn in fns:
            check(not fn.endswith((".epw", "bench.json")), "environment/%s is sealed material" % fn)
    log = open("environment/data/trend_log.csv").read()
    check("2017-07-15" not in log, "the trend log reaches into the graded period")

    sys.path.insert(0, os.path.join(ROOT, "tests"))
    sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
    import contextlib, io
    import make_public
    tmp = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()):
        make_public.main(out=tmp)
    shipped = sorted(os.listdir("environment/data"))
    check(shipped == sorted(os.listdir(tmp)), "environment/data and the generator disagree on the file list")
    for fn in shipped:
        check(md5(os.path.join(tmp, fn)) == md5(os.path.join("environment/data", fn)),
              "environment/data/%s is not what the generator writes" % fn)
    check(md5("tests/chicago_tmy3.epw") == "4c7bb1655aa251a7420514c9e7512310", "weather file changed")

    import grade
    chk = open("environment/check_controller.py").read()
    for nm, val in (("INIT_LIMIT_S", grade.INIT_TIMEOUT_S), ("STEP_LIMIT_S", grade.STEP_TIMEOUT_S),
                    ("BUDGET_S", grade.BUDGET_S)):
        m = re.search(r"^%s\s*=\s*([\d.]+)" % nm, chk, re.M)
        check(m is not None and float(m.group(1)) == val, "check_controller.py %s disagrees with the verifier" % nm)
    comfort = json.load(open("environment/data/comfort.json"))
    import instance
    check(comfort["operative_temp_band_c"] == [instance.LO_OCC, instance.HI_OCC], "comfort band disagrees")
    if os.path.exists("instruction.md"):
        ins = open("instruction.md").read()
        for s in ("/app/controller.py", "/app/data", "%.2f" % grade.ALLOW, "0.5 K h"):
            check(s in ins, "instruction.md does not state %r" % s)
        n = int(t["agent"]["timeout_sec"])
        tail = ("You have %d seconds to complete this task. Do not cheat by using online solutions or hints "
                "specific to this task." % n)
        check(ins.rstrip("\n").endswith("\n\n" + tail) and not ins.endswith("\n\n"),
              "instruction.md must end with a blank line then the exact closing sentence")

    # rules found on the live page and in the structure check, Oct 15
    composes = [os.path.join(r, fn) for r, _, fns in os.walk(".") for fn in fns
                if re.fullmatch(r"(docker-)?compose(\.[\w-]+)?\.ya?ml", fn)]
    check(not composes, "compose files are rejected (one container): %s" % composes)
    cheat = [os.path.join(r, d) for r, ds, _ in os.walk(".") for d in ds if d == "cheat"]
    check(not cheat, "a cheat/ directory fails the structure check: %s" % cheat)
    marker = base64.b64decode("Y2FuYXJ5").decode()
    marked = [os.path.join(r, fn) for r, _, fns in os.walk(".") for fn in fns
              if marker in open(os.path.join(r, fn), errors="ignore").read().lower()]
    check(not marked, "eval-set marker word in: %s (the structure check rejects it)" % marked)
    for df in ("environment/Dockerfile", "tests/Dockerfile"):
        d = open(df).read()
        check(not re.search(r"^USER\s", d, re.M), "%s must end as root" % df)
        for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
            m = re.search(r"^ENV\s+%s=(\d+)" % var, d, re.M)
            check(m is not None and int(m.group(1)) <= t["environment"]["cpus"], "%s: %s must be set at or below cpus" % (df, var))
    check(re.search(r"local trials|of 3 |of 6 |agent harness|full effort|screen-level|easiness", rd, re.I) is None,
          "README carries agent-trial evidence; the Oct 15 quality review read it against the task")
    check(re.search(r"local trials|agent harness|full effort|screen-level", md["difficulty_explanation"], re.I) is None,
          "difficulty_explanation argues from agent performance")
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
