"""Structural pre-flight: what the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Exits non-zero if anything fails. Needs numpy (the record regeneration check).
"""
import base64, filecmp, os, re, subprocess, sys, tempfile, tomllib

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment", "solution", "tests", "authoring"}
BLOCKED = tuple(base64.b64decode(s).decode() for s in ("YWZ0ZXJxdWVyeQ==", "a2VwbGVy"))
FAILS, PASSED = [], [0]


def check(ok, msg):
    if ok:
        PASSED[0] += 1
    else:
        FAILS.append(msg)


def main():
    os.chdir(ROOT)
    extra = {e for e in os.listdir(".") if e not in ALLOWED_ROOT}
    check(not extra, "root has unexpected entries: %s" % sorted(extra))
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "tests/Dockerfile",
                 "tests/test.sh", "tests/test_supervisor.py", "tests/grade.py", "tests/host.py", "tests/puller.py",
                 "solution/solve.sh", "solution/fit.py", "solution/supervisor_template.py",
                 "environment/check_interface.py", "authoring/provenance/gen.py", "authoring/provenance/puller.py",
                 "authoring/instruction-fact-sheet.md"):
        check(os.path.isfile(need), "missing %s" % need)
    junk = []
    for top, dirs, files in os.walk("."):
        for d in dirs:
            if d in ("__pycache__", ".pytest_cache", ".ipynb_checkpoints", "jobs"):
                junk.append(os.path.join(top, d))
        for f in files:
            p = os.path.join(top, f)
            if f.startswith(".") or f.endswith((".pyc", ".orig", ".bak")):
                junk.append(p)
            base = os.path.splitext(f)[0]
            check(f == "README.md" or not (base.isupper() and len(base) > 1), "all-uppercase file name: %s" % p)
            try:
                txt = open(p, "rb").read()
            except OSError:
                continue
            check(all(b < 128 for b in txt), "non-ASCII bytes in %s" % p)
            low = txt.decode("ascii", "ignore").lower()
            for w in BLOCKED:
                n = low.count(w)
                if p == "./task.toml":
                    n -= low.count('name = "%s/' % w)
                check(n == 0, "blocked programme name in %s" % p)
        for d in dirs:
            check(not (d.isupper() and len(d) > 1), "all-uppercase folder name: %s" % os.path.join(top, d))
    check(not junk, "junk that must be removed: %s" % sorted(junk))
    t = tomllib.load(open("task.toml", "rb"))
    check(t.get("schema_version") == "1.4", "schema_version must be 1.4")
    check(t.get("artifacts") == ["/app/supervisor.py"], "artifacts must be /app/supervisor.py")
    check(t["task"]["name"] == BLOCKED[0] + "/cz-silicon-control", "task name")
    check(t["verifier"]["environment_mode"] == "separate", "verifier must run in a separate environment")
    check(t["verifier"]["environment"]["network_mode"] == "no-network", "verifier must have no network")
    for k in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
        check(len(t["metadata"].get(k, "")) > 200, "metadata.%s too short" % k)
    readme = open("README.md").read()
    for h in ("## Difficulty", "## Reference solution", "## Verification"):
        check(h in readme, "README lacks %s" % h)
    ins = open("instruction.md").read()
    check(ins.rstrip().endswith("You have 14400 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction closing line")
    check(t["agent"]["timeout_sec"] == 14400.0, "agent timeout must match the instruction's 14400 s")
    for w in ("grader", "verifier", "reward", "scoring", "test_"):
        check(w not in ins.lower(), "instruction uses grading word %r" % w)
    check(filecmp.cmp("tests/puller.py", "authoring/provenance/puller.py", shallow=False),
          "tests/puller.py and authoring/provenance/puller.py differ")
    for x in ("solution/solve.sh", "tests/test.sh"):
        check(os.access(x, os.X_OK), "%s not executable" % x)
    df = open("environment/Dockerfile").read()
    check("tests" not in df and "solution" not in df and "puller" not in df, "environment Dockerfile references sealed files")
    check(not os.path.exists("environment/data/puller.py"), "sealed module in the environment")
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([sys.executable, "-B", "authoring/provenance/gen.py", d], capture_output=True, text=True,
                           env=dict(os.environ, OMP_NUM_THREADS="1"))
        check(p.returncode == 0, "gen.py failed: %s" % p.stderr[-500:])
        for sub in ("logs", "recipes"):
            a, b = os.path.join(d, sub), os.path.join("environment/data", sub)
            for f in sorted(os.listdir(b)):
                check(os.path.isfile(os.path.join(a, f)) and filecmp.cmp(os.path.join(a, f), os.path.join(b, f), shallow=False),
                      "environment/data/%s/%s does not regenerate byte for byte" % (sub, f))
    nums = re.findall(r"\d+(?:\.\d+)?", ins)
    for n in ("301.0", "303.0", "1500", "14400"):
        check(n in nums, "instruction does not state %s" % n)
    if FAILS:
        print("%d FAILED of %d checks:" % (len(FAILS), len(FAILS) + PASSED[0]))
        for f in FAILS:
            print("  FAIL ", f)
        return 1
    print("pre-flight clean: %d checks passed" % PASSED[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
