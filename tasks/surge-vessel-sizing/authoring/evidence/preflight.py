"""Structural pre-flight. Everything the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Run from anywhere. Exits non-zero if anything fails. Needs numpy for the regeneration check (the generator writes
every data file again into a temporary directory and the bytes must match); everything else is standard library.
"""
import base64, hashlib, io, os, re, subprocess, sys, tempfile, tomllib, contextlib

sys.dont_write_bytecode = True   # the junk check must not trip on this script's own imports

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment", "solution", "tests", "authoring"}
# Internal programme names that must not appear anywhere but the mandated [task].name prefix.
# Stored encoded because this file ships inside the bundle.
BLOCKED = tuple(base64.b64decode(s).decode() for s in ("YWZ0ZXJxdWVyeQ==", "a2VwbGVy"))
FAILS, WARNS = [], []
# (number as the README quotes it, evidence file it comes from)
NUMBERS = [('1.052', 'reference'),
           ('1.092', 'reference'),
           ('-2.60', 'reference'),
           ('-2.88', 'reference'),
           ('0.822', 'reference'),
           ('0.825', 'reference'),
           ('40.04', 'reference'),
           ('19.85', 'reference'),
           ('1.016', 'reference'),
           ('1.023', 'reference'),
           ('0.830', 'route_study'),
           ('0.889', 'route_study'),
           ('2.204', 'route_study'),
           ('1.968', 'route_study'),
           ('0.979', 'route_study'),
           ('0.973', 'route_study'),
           ('1.586', 'route_study'),
           ('1.629', 'route_study'),
           ('0.838', 'route_study'),
           ('0.831', 'route_study'),
           ('0.947', 'route_study'),
           ('1.191', 'route_study'),
           ('1.201', 'route_study'),
           ('0.926', 'route_study'),
           ('0.496', 'route_study'),
           ('0.385', 'route_study'),
           ('0.837', 'route_study'),
           ('0.901', 'route_study'),
           ('0.674', 'route_study'),
           ('1.805', 'route_study'),
           ('0.291', 'constant_null'),
           ('1.439', 'constant_null'),
           ('0.369', 'constant_null'),
           ('1.827', 'constant_null'),
           ('0.739', 'constant_null'),
           ('3.653', 'constant_null'),
           ('0.596', 'constant_null'),
           ('1.090', 'constant_null'),
           ('1.013', 'constant_null'),
           ('1.011', 'constant_null'),
           ('39.26', 'route_example'),
           ('40.04', 'route_example'),
           ('33.48', 'route_example'),
           ('1.038', 'method_spread'), ('1.109', 'method_spread'), ('1.072', 'method_spread'), ('1.093', 'method_spread'), ('0.993', 'method_spread'), ('1.058', 'method_spread')]
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



def files(top):
    return sorted(os.path.relpath(os.path.join(r, fn), top) for r, _, fns in os.walk(top) for fn in fns)


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
    links = [os.path.join(r, n) for r, dirs, fns in os.walk(".") for n in dirs + fns if os.path.islink(os.path.join(r, n))]
    check(not links, "symlinks in the bundle: %s" % links[:6])
    upper = [os.path.join(r, n) for r, dirs, fns in os.walk(".") for n in dirs + fns
             if n.split(".")[0].isupper() and n not in ("README.md", "Dockerfile")]
    check(not upper, "all-uppercase file or folder names: %s" % upper[:6])

    REQ = ["task.toml", "README.md", "environment/Dockerfile", "solution/solve.sh", "solution/surge.py", "tests/test.sh",
           "tests/Dockerfile", "tests/grade.py", "tests/test_surge.py", "tests/surge_check.py", "tests/moc.py",
           "tests/hidden/truth.json", "authoring/provenance/moc.py", "authoring/provenance/mains.py",
           "authoring/provenance/docs_main.py", "authoring/provenance/build.py"]
    for ev in ("reference", "method_spread", "route_study", "constant_null", "verifier_checks"):
        REQ += ["authoring/evidence/%s.py" % ev, "authoring/evidence/%s.txt" % ev]
    REQ += ["authoring/evidence/independent.py", "authoring/evidence/common.py", "authoring/evidence/check_instruction.py",
            "authoring/evidence/route_example.py", "authoring/evidence/route_example.txt"]
    for p in REQ:
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
    check(t.get("artifacts") == ["/app/output/surge.py"], "artifacts must be ['/app/output/surge.py']")
    check("artifacts" in raw.split("[")[0], "'artifacts' must sit above the first [section]")
    md = t["metadata"]
    check(md["category"] == "Science", "category must be exactly 'Science'")
    check(md["domain"] == "engineering-sciences" and md["field"] == "mechanical-engineering", "domain/field")
    check(t["task"]["keywords"] == md["tags"], "keywords and tags must match")
    check(t["agent"]["timeout_sec"] == 28800, "[agent].timeout_sec must be 28800 (announcement)")
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

    rd = open("README.md").read()
    for sec in ("## Difficulty", "## Reference solution", "## Verification"):
        check(sec in rd, "README is missing the required section %s" % sec)
    for nm, body in (("README.md", rd), ("task.toml", raw)):
        check(re.search(r"local trials|agent harness|full effort|low effort|xhigh|pass rate|probe|\bof [38] (?:runs|trials|attempts|agents)", body, re.I) is None,
              "%s argues from agent trials; keep trial evidence out of the bundle text" % nm)
        check("TBD" not in body and "@@" not in body, "%s still carries a placeholder" % nm)
        check(body.isascii(), "%s has non-ASCII characters" % nm)
    # the three explanations in task.toml are the README's three sections
    for sec, fld in (("Difficulty", "difficulty_explanation"), ("Reference solution", "solution_explanation"),
                     ("Verification", "verification_explanation")):
        m = re.search(r"^## %s\n\n(.*?)(?=^## |\Z)" % re.escape(sec), rd, re.S | re.M)
        check(m is not None and m.group(1).strip() == md[fld].strip(), "task.toml %s differs from README ## %s" % (fld, sec))

    # numbers the README quotes are the evidence files' numbers
    ev = {n: open("authoring/evidence/%s.txt" % n).read() for n in ("reference", "method_spread", "route_study", "constant_null", "verifier_checks", "route_example")}
    for num, src in NUMBERS:
        check(num in rd and num in ev[src], "README number %s not found in %s.txt" % (num, src))
    check("wrong 0 (accepted)" in ev["reference"], "reference not clean in the evidence")
    spread = re.findall(r"as designed\s+wrong (\d+)", ev["method_spread"])
    check(len(spread) == 6 and set(spread) == {"0"}, "a correct method, as designed, gets a main wrong")
    check(all("as nobody" in ev[n] for n in ("reference", "method_spread", "route_study", "constant_null", "verifier_checks")),
          "evidence not measured through the verifier as nobody")
    body = ev["route_study"].split("\n\n", 1)[1]
    check("rejected" in body and "accepted" not in body, "a defective route is accepted")
    body = ev["constant_null"].split("\n\n", 2)[2]
    check(body.count("rejected") == 4 and "accepted" not in body, "a method-free answer is accepted")
    check(ev["verifier_checks"].count("processes left: 0") == ev["verifier_checks"].count(" wrong ") and
          ev["verifier_checks"].count(" accepted") == 3, "verifier_checks.txt: a process survived or a bad case was accepted")

    for df in ("environment/Dockerfile", "tests/Dockerfile"):
        d = open(df).read()
        check("FROM --platform" not in d, "%s must not pin a platform" % df)
        for m in re.findall(r"pip install[^\n]*(?:\\\n[^\n]*)*", d):
            body = re.sub(r"--[\w-]+", " ", m).replace("pip install", " ")
            for tok in body.replace("\\", " ").split():
                if re.match(r"[a-zA-Z]", tok):
                    check("==" in tok, "%s: pip package '%s' is not pinned with ==" % (df, tok))
        check("apt-get install" not in d, "%s installs apt packages" % df)
    td = open("tests/Dockerfile").read()
    check("pytest==8.4.1" in td and "pytest-json-ctrf==0.3.5" in td, "tests/Dockerfile must pin pytest 8.4.1 and ctrf 0.3.5")
    check("chmod 700 /tests" in td, "tests/Dockerfile must make /tests root-only")
    check(re.search(r"^RUN\s+mkdir\s+-p\s+/app/output\s*$", td, re.M) is not None,
          "tests/Dockerfile needs its own line 'RUN mkdir -p /app/output'")
    check("chmod 700 /logs/verifier" in td, "tests/Dockerfile must make /logs/verifier root-only")
    ed = open("environment/Dockerfile").read()
    check(all(x in ed for x in ("numpy==2.1.3", "scipy==1.14.1", "pandas==2.2.3")), "agent image libraries changed")
    check("numpy==2.1.3" in td and "scipy==1.14.1" in td and "pandas==2.2.3" in td, "verifier image must have the agent's libraries")
    check(re.findall(r"^COPY\s+(\S+)", ed, re.M) == ["data/"], "environment/Dockerfile must copy data/ only")
    check(not re.search(r"^USER\s", ed, re.M), "environment/Dockerfile must end as root (use [agent] user instead of USER)")
    check("useradd --create-home --shell /bin/bash agent" in ed, "the image must create the agent user")
    check("chown agent:agent /app/output" in ed and "go-w /app/data" in ed, "agent writes /app/output only")
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        m = re.search(r"^ENV\s+%s=(\d+)" % var, ed, re.M)
        check(m is not None and int(m.group(1)) <= t["environment"]["cpus"], "%s must be set at or below cpus" % var)
    ts = open("tests/test.sh").read()
    check("--ctrf=" in ts, "test.sh must write the ctrf report")
    check(re.search(r'echo -n "0" > /logs/verifier/reward.txt', ts) is not None, "test.sh must write reward 0 first")
    check(ts.count("chmod 700 /logs/verifier") >= 2, "test.sh must lock /logs/verifier before grading and before the reward")
    check('s.get("tests") == 1 and s.get("passed") == 1' in ts and '"$COUNTS_OK" = "yes"' in ts,
          "test.sh must gate the reward on the ctrf counts (1 test, 1 passed)")
    check(set(re.findall(r'echo -n "([^"]*)" > /logs/verifier/reward.txt', ts)) == {"0", "1"}, "reward values must be 0 or 1")
    # verifier limits: the per-run limit times the packages fits the verifier timeout
    g = open("tests/grade.py").read()
    lim = int(re.search(r"^TIME_LIMIT_S = (\d+)", g, re.M).group(1))
    npk = len([d for d in os.listdir("tests/hidden") if os.path.isdir(os.path.join("tests/hidden", d))])
    check(lim * npk + 300 <= t["verifier"]["timeout_sec"], "time limit x packages does not fit the verifier timeout")
    check("os.O_NOFOLLOW" in g and "S_ISREG" in g and "isfinite" in g, "grade.py must read the output strictly")
    loose = sorted(fn for fn in os.listdir("authoring") if os.path.isfile(os.path.join("authoring", fn)) and fn != "hint.md")
    check(not loose, "files at the authoring/ root other than hint.md: %s" % loose)
    composes = [os.path.join(r, fn) for r, _, fns in os.walk(".") for fn in fns
                if re.fullmatch(r"(docker-)?compose(\.[\w-]+)?\.ya?ml", fn)]
    check(not composes, "compose files are rejected (one container): %s" % composes)
    dockerfiles = sorted(os.path.join(r, fn) for r, _, fns in os.walk(".") for fn in fns if fn == "Dockerfile")
    check(dockerfiles == ["./environment/Dockerfile", "./tests/Dockerfile"], "unexpected Dockerfiles: %s" % dockerfiles)
    cheat = [os.path.join(r, d) for r, ds, _ in os.walk(".") for d in ds if d == "cheat"]
    check(not cheat, "a cheat/ directory fails the structure check: %s" % cheat)

    # the agent's data: no code, no truth, no hidden package; the verifier's copy is identical
    agent_side = files("environment/data")
    check([p for p in agent_side if p.endswith((".py", ".json"))] == ["examples/kestrel-lane/reported_design.json"],
          "code or json in environment/data other than the example's reported design")
    check(files("tests/app_data") == agent_side and all(md5(os.path.join("tests/app_data", p)) == md5(os.path.join("environment/data", p)) for p in agent_side),
          "tests/app_data differs from environment/data")
    hid = sorted(d for d in os.listdir("tests/hidden") if os.path.isdir(os.path.join("tests/hidden", d)))
    check(not any(h in p for h in hid for p in agent_side), "a hidden package name appears in the agent's data")
    check(not any(p.endswith("reported_design.json") for p in files("tests/hidden")), "a hidden package carries a design")
    for p in agent_side:
        body = open(os.path.join("environment/data", p), errors="ignore").read()
        check("k_true" not in body and "z_drawing" not in body and "vmin" not in body, "%s carries sealed definition text" % p)

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
                if re.search(r"/home/|/Users/|/Volumes/|/srv/probes|scratchpad", body):
                    paths.append(os.path.join(r, fn))
    check(not paths, "hard-coded author paths in: %s" % paths[:6])
    present = {fn for _, _, fns in os.walk(".") for fn in fns}
    named = set()
    for r, _, fns in os.walk("."):
        for fn in fns:
            if fn.endswith((".py", ".md", ".toml")) and fn not in ("preflight.py", "check_instruction.py"):
                named |= set(re.findall(r"\b([\w-]+\.(?:py|csv|xlsx|docx|pdf|json|sh|md|txt|toml))\b",
                                        open(os.path.join(r, fn), errors="ignore").read()))
    ghosts = sorted(n for n in named - present if n not in ("metrics.json", "ctrf.json", "reward.txt", "instruction.md", "design.json"))
    check(not ghosts, "files named in text but not in the bundle: %s" % ghosts[:8])

    # the generator rewrites every data file byte for byte
    sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
    import build
    tmp = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()):
        build.main(tmp)
    for top in ("environment/data", "tests/app_data", "tests/hidden"):
        a, b = files(top), files(os.path.join(tmp, top))
        check(a == b, "%s and the generator disagree on the file list: %s" % (top, sorted(set(a) ^ set(b))[:4]))
        bad = [p for p in a if p in b and md5(os.path.join(top, p)) != md5(os.path.join(tmp, top, p))]
        check(not bad, "%s differs from what the generator writes: %s" % (top, bad[:4]))

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
