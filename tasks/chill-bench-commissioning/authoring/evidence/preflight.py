"""Structural pre-flight. Everything the platform checks that can be checked offline.

Run from the bundle root. Exits non-zero if anything fails.
"""
import base64
import json
import os
import re
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment",
                "solution", "tests", "authoring"}

# The programme's internal names, which must not appear anywhere in a submitted
# bundle. They are stored encoded rather than as literals because THIS FILE SHIPS
# INSIDE THE BUNDLE: a literal here is itself a hit on the very check it performs.
# An earlier version held them literally and exempted itself from the scan, which is
# how a submission got rejected for terms that existed only in the checker.
BLOCKED = tuple(base64.b64decode(s).decode()
                for s in ("YWZ0ZXJxdWVyeQ==", "a2VwbGVy"))
FAILS = []
WARNS = []
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

    # --- root layout
    extra = set(os.listdir(".")) - ALLOWED_ROOT
    extra = {e for e in extra if not e.startswith(".")}
    check(not extra, f"root has entries the structure check rejects: {sorted(extra)}")

    # --- junk. Tool droppings, not authored files: anything a local test run or an
    # editor leaves behind. .pytest_cache in particular appears the moment the verifier
    # is run by hand from tests/, which is exactly what happens before packaging.
    JUNK_DIRS = ("__pycache__", ".pytest_cache", ".ipynb_checkpoints", ".mypy_cache",
                 ".ruff_cache", ".pytest_tmp")
    JUNK_FILES = (".DS_Store", "Thumbs.db", ".coverage")
    JUNK_SUFFIX = (".pyc", ".pyo", ".orig", ".rej", ".bak", ".swp", "~")
    junk = []
    for r, dirs, fns in os.walk("."):
        dirs[:] = [d for d in dirs if d != ".git"]
        for fn in fns:
            if fn in JUNK_FILES or fn.endswith(JUNK_SUFFIX):
                junk.append(os.path.join(r, fn))
        for d in [d for d in dirs if d in JUNK_DIRS]:
            junk.append(os.path.join(r, d))
            dirs.remove(d)
    check(not junk, f"junk files that must be removed: {junk[:6]}")

    # --- required files
    for p in ("task.toml", "README.md", "environment/Dockerfile",
              "solution/solve.sh", "tests/test.sh", "tests/Dockerfile"):
        check(os.path.exists(p), f"missing required file {p}")
    if not os.path.exists("instruction.md"):
        WARNS.append("instruction.md is not written yet -- Alex writes it, by hand")

    # --- task.toml
    with open("task.toml", "rb") as f:
        t = tomllib.load(f)
    name = t["task"]["name"]
    check(name.startswith(BLOCKED[0] + "/"),
          f"[task].name must carry the mandated prefix: {name}")
    slug = name.split("/", 1)[1]
    check(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug),
          f"slug must be lowercase kebab-case: {slug}")
    check(slug.count("-") <= 2, f"slug may be at most 3 hyphenated words: {slug}")
    check(t["metadata"]["category"] == "Science", "category must be exactly 'Science'")
    check(t["metadata"]["domain"] == "engineering-sciences", "domain")
    check(t["metadata"]["field"] == "mechanical-engineering", "field")
    check(3600 <= t["agent"]["timeout_sec"] <= 28800, "[agent].timeout_sec in range")
    check(t["verifier"]["timeout_sec"] <= 28800, "[verifier].timeout_sec in range")
    check(t["verifier"]["environment_mode"] == "separate", "verifier environment_mode")
    check(t["verifier"]["environment"]["network_mode"] == "no-network",
          "verifier must have no network")
    check(t["environment"]["network_mode"] == "public", "agent keeps the open internet")
    check(t["environment"]["cpus"] in (1, 2, 4, 8, 16), "cpus in the enumerated set")
    check(t["environment"]["memory_mb"] in (1024, 2048, 4096, 8192, 16384), "memory_mb")
    check(t["environment"]["storage_mb"] <= 40960, "storage_mb")
    raw = open("task.toml").read()
    check("allow_internet" not in raw, "'allow_internet' is deprecated and fails")
    check("artifacts" in raw.split("[")[0], "'artifacts' must sit above the first [section]")
    for fld in ("relevant_experience", "difficulty_explanation", "solution_explanation",
                "verification_explanation"):
        if "FILL:" in t["metadata"].get(fld, ""):
            WARNS.append(f"task.toml [{fld}] still carries a FILL: placeholder")

    # --- README sections
    rd = open("README.md").read()
    for sec in ("## Difficulty", "## Reference solution", "## Verification"):
        check(sec in rd, f"README is missing the required section {sec}")

    # --- Dockerfiles
    for df in ("environment/Dockerfile", "environment/bench/Dockerfile",
               "tests/Dockerfile"):
        d = open(df).read()
        check("FROM --platform" not in d, f"{df} must not pin a platform")
        for m in re.findall(r"pip install[^\n]*(?:\\\n[^\n]*)*", d):
            body = re.sub(r"--[\w-]+", " ", m).replace("pip install", " ")
            for tok in body.replace("\\", " ").split():
                if not re.match(r"[a-zA-Z]", tok):
                    continue
                check("==" in tok,
                      f"{df}: pip package '{tok}' is not pinned with ==")
        if "apt-get install" in d:
            check("apt-get update" in d, f"{df}: apt-get install without update")
            check("rm -rf /var/lib/apt/lists/*" in d, f"{df}: apt lists not cleaned")
            check(not re.search(r"apt-get install[^\n]*=\d", d),
                  f"{df}: apt packages must not be version pinned")
    check("volumes" not in open("environment/docker-compose.yaml").read(),
          "compose must declare no volumes of any kind")

    # --- environment must not reference solution or test files
    for r, dirs, fns in os.walk("environment"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in fns:
            if not fn.endswith((".py", ".sh", ".yaml", ".yml", "Dockerfile")):
                continue
            body = open(os.path.join(r, fn), errors="ignore").read()
            for bad in ("solve.py", "solve.sh", "test.sh", "test_recipe", "truth.json",
                        "grade.py"):
                check(bad not in body,
                      f"environment/{fn} references {bad}, which it may not")

    # --- blocked internal terms anywhere but [task].name
    hits = []
    for r, dirs, fns in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for fn in fns:
            p = os.path.join(r, fn)
            try:
                body = open(p, errors="ignore").read().lower()
            except (OSError, UnicodeDecodeError):
                continue
            for term in BLOCKED:
                if term in body:
                    # The ONLY permitted occurrence is the mandated prefix in
                    # [task].name. Nothing else is exempt -- least of all this file.
                    if p.endswith("task.toml") and body.count(term) == 1:
                        continue
                    hits.append((p, term))
    check(not hits, f"blocked internal terms outside [task].name: {hits[:6]}")

    # --- the sealed fleet must not be visible to the agent
    for r, _, fns in os.walk("environment/data"):
        for fn in fns:
            body = open(os.path.join(r, fn)).read()
            check("_alpha" not in body and "lot_offset" not in body,
                  f"environment/data/{fn} leaks a sealed parameter")
    agent_side = ["environment/Dockerfile", "environment/bench.py"]
    for p in agent_side:
        body = open(p).read()
        check("make_fleet" not in body and "bench_core" not in body,
              f"{p} would put the sealed generator in the agent's container")

    # --- spec agreement between what is shipped and what is graded
    spec_agent = json.load(open("environment/data/spec.json"))
    spec_truth = json.load(open("tests/truth.json"))["spec"]
    check(spec_agent == spec_truth,
          f"agent spec and sealed spec disagree:\n    {spec_agent}\n    {spec_truth}")

    for w in WARNS:
        print("  WARN  " + w)
    if FAILS:
        print(f"\n{len(FAILS)} FAILED of {PASSED + len(FAILS)} checks:")
        for f in FAILS:
            print("  FAIL  " + f)
        return 1
    print(f"\npre-flight clean: {PASSED} checks passed, {len(WARNS)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
