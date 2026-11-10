"""Structural pre-flight. Everything the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Run from anywhere. Exits non-zero if anything fails.
"""
import base64
import json
import os
import re
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment", "solution",
                "tests", "authoring"}

# The programme's internal names, which must not appear anywhere in a submitted bundle
# except the mandated [task].name prefix. Stored encoded because this file ships inside
# the bundle and a literal here would itself be a hit.
BLOCKED = tuple(base64.b64decode(s).decode() for s in ("YWZ0ZXJxdWVyeQ==", "a2VwbGVy"))
SEALED_KEYS = ("_alpha", "_sag_um", "_T0_C", "_noise_seed")
FAILS, WARNS = [], []
PASSED = 0


def check(ok, msg):
    """msg describes the FAILURE. Passing checks are counted, not printed."""
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILS.append(msg)


def main():
    os.chdir(ROOT)

    # --- root layout and junk
    extra = {e for e in set(os.listdir(".")) - ALLOWED_ROOT if not e.startswith(".")}
    check(not extra, "root has entries the structure check rejects: %s" % sorted(extra))
    hidden = [e for e in os.listdir(".") if e.startswith(".")]
    check(not hidden, "hidden entries at the root: %s" % hidden)
    JUNK_DIRS = ("__pycache__", ".pytest_cache", ".ipynb_checkpoints", ".mypy_cache",
                 ".ruff_cache", "jobs")
    JUNK_FILES = (".DS_Store", "Thumbs.db", ".coverage")
    JUNK_SUFFIX = (".pyc", ".pyo", ".orig", ".rej", ".bak", ".swp", "~")
    junk = []
    for r, dirs, fns in os.walk("."):
        for fn in fns:
            if fn in JUNK_FILES or fn.endswith(JUNK_SUFFIX):
                junk.append(os.path.join(r, fn))
        for d in [d for d in dirs if d in JUNK_DIRS or d == ".git"]:
            junk.append(os.path.join(r, d))
            dirs.remove(d)
    check(not junk, "junk that must be removed: %s" % junk[:6])
    upper = [os.path.join(r, n) for r, dirs, fns in os.walk(".") for n in dirs + fns
             if n.isupper() and n not in ("README.md",)]
    check(not upper, "all-uppercase file or folder names: %s" % upper[:6])

    # --- required files
    for p in ("task.toml", "README.md", "environment/Dockerfile", "solution/solve.sh",
              "tests/test.sh", "tests/Dockerfile", "tests/truth.json", "tests/plant.py",
              "tests/grade.py", "tests/host.py", "tests/test_controller.py",
              "authoring/provenance/make_data.py"):
        check(os.path.exists(p), "missing required file %s" % p)
    if not os.path.exists("instruction.md"):
        WARNS.append("instruction.md is not written yet -- Alex writes it, by hand")

    # --- task.toml
    with open("task.toml", "rb") as f:
        t = tomllib.load(f)
    raw = open("task.toml").read()
    name = t["task"]["name"]
    check(name.startswith(BLOCKED[0] + "/"), "[task].name must carry the mandated prefix")
    slug = name.split("/", 1)[1]
    check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug) is not None,
          "slug must be lowercase kebab-case: %s" % slug)
    check(slug.count("-") <= 2, "slug may be at most 3 hyphenated words: %s" % slug)
    check(t.get("artifacts") == ["/app/controller.py"], "artifacts must be ['/app/controller.py']")
    check("artifacts" in raw.split("[")[0], "'artifacts' must sit above the first [section]")
    check(t["metadata"]["category"] == "Science", "category must be exactly 'Science'")
    check(t["metadata"]["domain"] == "engineering-sciences", "domain")
    check(t["metadata"]["field"] == "mechanical-engineering", "field")
    check(t["task"]["keywords"] == t["metadata"]["tags"], "keywords and tags must match")
    check(9000 <= t["agent"]["timeout_sec"] <= 28800, "[agent].timeout_sec must be 9000-28800")
    check(t["verifier"]["timeout_sec"] <= 28800, "[verifier].timeout_sec in range")
    check(t["verifier"]["environment_mode"] == "separate", "verifier environment_mode")
    check(t["verifier"]["environment"]["network_mode"] == "no-network",
          "verifier must have no network")
    check(t["environment"]["network_mode"] == "public", "agent environment network_mode")
    check(t["environment"]["cpus"] in (1, 2, 4, 8, 16), "cpus in the enumerated set")
    check(t["environment"]["memory_mb"] in (1024, 2048, 4096, 8192, 16384), "memory_mb")
    check(t["environment"]["storage_mb"] <= 40960, "storage_mb")
    check("allow_internet" not in raw, "'allow_internet' is deprecated and fails")
    for fld in ("relevant_experience", "difficulty_explanation", "solution_explanation",
                "verification_explanation"):
        if "FILL" in t["metadata"].get(fld, ""):
            WARNS.append("task.toml [%s] still carries a FILL placeholder" % fld)
    check(raw.isascii(), "task.toml has non-ASCII characters")

    # --- README
    rd = open("README.md").read() if os.path.exists("README.md") else ""
    for sec in ("## Difficulty", "## Reference solution", "## Verification"):
        check(sec in rd, "README is missing the required section %s" % sec)
    for name, body in (("README.md", rd), ("task.toml", raw)):
        check("TBD" not in body, "%s still carries a TBD marker" % name)
        check(body.isascii(), "%s has non-ASCII characters" % name)

    # --- Dockerfiles
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
    env_pins = set(re.findall(r"(numpy|scipy)==([\d.]+)", open("environment/Dockerfile").read()))
    ver_pins = set(re.findall(r"(numpy|scipy)==([\d.]+)", open("tests/Dockerfile").read()))
    check(env_pins == ver_pins and len(env_pins) == 2,
          "numpy/scipy pins differ between the agent and verifier images: %s vs %s"
          % (sorted(env_pins), sorted(ver_pins)))
    check("chmod 700 /tests" in open("tests/Dockerfile").read(),
          "tests/Dockerfile must make /tests root-only (the controller runs as nobody)")
    # The platform's structure check (artifact-parent-not-created) wants the parent of every
    # declared artifact created by its own `RUN mkdir -p <parent>` line in tests/Dockerfile;
    # a parent buried later in a chained mkdir with other paths is not recognised.
    for art in t.get("artifacts", []):
        parent = os.path.dirname(art.rstrip("/")) or "/"
        check(re.search(r"^RUN\s+mkdir\s+-p\s+%s\s*$" % re.escape(parent),
                        open("tests/Dockerfile").read(), re.M) is not None,
              "tests/Dockerfile needs its own line 'RUN mkdir -p %s' (parent of the artifact %s)"
              % (parent, art))
    check(not os.path.exists("environment/docker-compose.yaml")
          or "volumes" not in open("environment/docker-compose.yaml").read(),
          "compose must declare no volumes")

    # --- the agent's side must not reference the solution, the verifier or the generator
    for r, dirs, fns in os.walk("environment"):
        for fn in fns:
            if not fn.endswith((".py", ".sh", ".yaml", ".yml", "Dockerfile")):
                continue
            body = open(os.path.join(r, fn), errors="ignore").read()
            for bad in ("solve.py", "solve.sh", "test.sh", "test_controller", "truth.json",
                        "grade.py", "plant.py", "make_data", "refmodel"):
                check(bad not in body, "environment/%s references %s" % (fn, bad))
    d = open("environment/Dockerfile").read()
    check(re.findall(r"^COPY\s+(\S+)", d, re.M) == ["data/", "check_controller.py"],
          "environment/Dockerfile must copy only data/ and check_controller.py")

    # --- blocked internal terms anywhere but [task].name
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

    # --- nothing sealed reaches the agent
    for r, _, fns in os.walk("environment"):
        for fn in fns:
            body = open(os.path.join(r, fn), errors="ignore").read()
            for k in SEALED_KEYS:
                check('"' + k not in body, "environment/%s carries the sealed key %s" % (fn, k))

    # --- provenance: the generator reproduces every shipped data file and the truth
    sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
    import make_data
    files, truth = make_data.build()
    shipped = set()
    for r, _, fns in os.walk("environment/data"):
        for fn in fns:
            shipped.add(os.path.relpath(os.path.join(r, fn), "environment/data"))
    check(shipped == set(files), "environment/data and the generator disagree on the file "
          "list: %s" % sorted(shipped ^ set(files))[:6])
    for rel, text in files.items():
        p = os.path.join("environment/data", rel)
        check(os.path.exists(p) and open(p).read() == text,
              "environment/data/%s is not what the generator writes" % rel)
    with open("tests/truth.json") as f:
        check(json.load(f) == json.loads(json.dumps(truth)),
              "tests/truth.json is not what the generator writes")

    # --- the public spec agrees with the sealed plant and the verifier
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import plant
    import grade
    prod = json.load(open("environment/data/production.json"))
    for key, sealed in (("release_mass_mean_max_C", plant.T_TARGET),
                        ("zone_difference_max_K", plant.ZONE_CAP),
                        ("cycle_max_s", plant.T_CYCLE_MAX),
                        ("control_period_s", plant.CTRL_DT),
                        ("pressure_command_min_torr", plant.P_MIN),
                        ("pressure_command_max_torr", plant.P_MAX),
                        ("chamber_pressure_at_landing_torr", plant.P_IDLE),
                        ("cycle_allowance_fraction", truth["allowance"])):
        check(abs(prod[key] - sealed) < 1e-12,
              "production.json %s=%r, verifier uses %r" % (key, prod[key], sealed))
    chk = open("environment/check_controller.py").read()
    for name, val in (("INIT_LIMIT_S", grade.INIT_TIMEOUT_S), ("STEP_LIMIT_S", grade.STEP_TIMEOUT_S),
                      ("WAFER_LIMIT_S", grade.WAFER_BUDGET_S)):
        m = re.search(r"^%s\s*=\s*([\d.]+)" % name, chk, re.M)
        check(m is not None and float(m.group(1)) == val,
              "check_controller.py %s disagrees with the verifier (%s)" % (name, val))

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
