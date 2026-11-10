"""Structural pre-flight: what the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Exits non-zero if anything fails. Needs numpy, scipy and pandas (the record regeneration check, a few minutes).
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
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/fieldwork-cmd",
                 "environment/fieldwork/run", "environment/fieldwork/fieldwork.py", "environment/fieldwork/screens.py",
                 "environment/fieldwork/bank.json", "tests/Dockerfile", "tests/test.sh", "tests/test_damage.py",
                 "tests/grade_screens.py", "tests/screens.py", "solution/solve.sh", "solution/solve.py",
                 "authoring/provenance/gen.py", "authoring/provenance/screens.py", "authoring/provenance/fieldwork.py",
                 "authoring/evidence/route_study.txt", "authoring/evidence/plan_sweep.txt",
                 "authoring/evidence/method_spread.txt", "authoring/evidence/constant_null.txt",
                 "authoring/evidence/calibration.txt"):
        check(os.path.isfile(need), "missing %s" % need)
    check(not os.path.exists("authoring/instruction-fact-sheet.md"), "authoring notes that do not belong in the zip")
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
    check(t.get("artifacts") == ["/app/output/damage.json"], "artifacts must be /app/output/damage.json")
    check(t["task"]["name"] == BLOCKED[0] + "/screen-fatigue-assessment", "task name")
    check(t["verifier"]["environment_mode"] == "separate", "verifier must run in a separate environment")
    check(t["verifier"]["environment"]["network_mode"] == "no-network", "verifier must have no network")
    check(t["agent"].get("user") == "agent", "agent must run as the user agent")
    for k in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
        check(len(t["metadata"].get(k, "")) > 200, "metadata.%s too short" % k)
    readme = open("README.md").read()
    for h in ("## Difficulty", "## Reference solution", "## Verification"):
        check(h in readme, "README lacks %s" % h)
    ins = open("instruction.md").read()
    check(ins.rstrip().endswith("You have 10800 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction closing line")
    check(t["agent"]["timeout_sec"] == 10800.0, "agent timeout must match the instruction's 10800 s")
    for w in ("grader", "verifier", "reward", "scoring", "test_"):
        check(w not in ins.lower(), "instruction uses grading word %r" % w)
    for w in ("coast", "brake", "resonan", "mode", "spring", "survey", "gauge factor", "swap", "debond", "wet",
              "historian", "drive", "37 kw", "s5", "s6", "s8", "proxy", "rainflow"):
        check(w not in ins.lower(), "instruction names a mechanism or a screen to test: %r" % w)
    check(filecmp.cmp("tests/screens.py", "authoring/provenance/screens.py", shallow=False), "tests/screens.py differs")
    for f in ("screens.py", "fieldwork.py", "bank.json"):
        check(filecmp.cmp("environment/fieldwork/" + f, "authoring/provenance/" + f, shallow=False),
              "environment/fieldwork/%s differs from the provenance copy" % f)
    check("chmod 700 /opt/fieldwork" in open("environment/Dockerfile").read() and
          "chmod 600 /opt/fieldwork/*.py /opt/fieldwork/bank.json" in open("environment/Dockerfile").read(),
          "the field-work service and its sealed files must be private to the contractor user")
    check("/opt/fieldwork/run status, /opt/fieldwork/run submit" in open("environment/Dockerfile").read(),
          "the sudo rule must allow only status and submit")
    for x in ("solution/solve.sh", "tests/test.sh", "environment/fieldwork-cmd", "environment/fieldwork/run"):
        check(os.access(x, os.X_OK), "%s not executable" % x)
    df = open("environment/Dockerfile").read()
    check("chown -R root:root /app/data" in df, "environment Dockerfile must keep /app/data read-only")
    check("chmod 700 /logs/verifier" in open("tests/Dockerfile").read() and "chmod 700 /logs/verifier" in open("tests/test.sh").read(),
          "reward directory must be root-only")
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([sys.executable, "-B", "authoring/provenance/gen.py", d], capture_output=True, text=True)
        check(p.returncode == 0, "gen.py failed: %s" % p.stderr[-500:])
        check(filecmp.cmp(os.path.join("authoring", "provenance", "bank.json"), "environment/fieldwork/bank.json", shallow=False),
              "bank.json does not regenerate byte for byte")
        for top, _, files in os.walk("environment/data"):
            for f in files:
                rel = os.path.relpath(os.path.join(top, f), "environment/data")
                check(os.path.isfile(os.path.join(d, rel)) and filecmp.cmp(os.path.join(d, rel), os.path.join(top, f), shallow=False),
                      "environment/data/%s does not regenerate byte for byte" % rel)
    nums = re.findall(r"\d+(?:\.\d+)?", ins)
    for n in ("20", "10800", "2026"):
        check(any(x.startswith(n) for x in nums), "instruction does not state %s" % n)
    if FAILS:
        print("%d FAILED of %d checks:" % (len(FAILS), len(FAILS) + PASSED[0]))
        for f in FAILS:
            print("  FAIL ", f)
        return 1
    print("pre-flight clean: %d checks passed" % PASSED[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
