"""Structural pre-flight: what the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Exits non-zero if anything fails. Needs numpy (the audit regeneration check, about a minute).
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
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "tests/Dockerfile", "tests/test.sh",
                 "tests/test_audit.py", "tests/grade_audits.py", "tests/hidden/truth.json",
                 "solution/solve.sh", "solution/audit.py", "authoring/provenance/gen.py",
                 "authoring/provenance/build.py", "authoring/evidence/independent_audit.py",
                 "authoring/evidence/route_study.txt", "authoring/evidence/method_spread.txt",
                 "authoring/evidence/constant_null.txt", "authoring/evidence/independent.py",
                 "authoring/evidence/independent.txt"):
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
            if f.endswith(".npz"):
                continue
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
    check(t.get("artifacts") == ["/app/output/audit.py"], "artifacts must be /app/output/audit.py")
    check(t["task"]["name"] == BLOCKED[0] + "/air-system-audit", "task name")
    slug = t["task"]["name"].split("/", 1)[1]
    check(len(slug.split("-")) <= 3, "task name must be at most 3 hyphen-separated words")
    check(os.path.basename(ROOT) == slug, "bundle folder must be named after the task")
    check(t["verifier"]["environment_mode"] == "separate", "verifier must run in a separate environment")
    check(t["verifier"]["environment"]["network_mode"] == "no-network", "verifier must have no network")
    check(t["agent"].get("user") == "agent", "agent must run as the user agent")
    for k in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
        check(len(t["metadata"].get(k, "")) > 200, "metadata.%s too short" % k)
    readme = open("README.md").read()
    for h in ("## Difficulty", "## Reference solution", "## Verification"):
        check(h in readme, "README lacks %s" % h)
    ins = open("instruction.md").read()
    check(ins.rstrip().endswith("You have 28800 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction closing line")
    check(600.0 <= float(t["verifier"]["timeout_sec"]) <= 28800.0, "verifier timeout must be 600-28800 s")
    check(t["agent"]["timeout_sec"] == 28800.0, "agent timeout must match the instruction's 28800 s")
    for w in ("grader", "verifier", "reward", "scoring", "test_", "tested", "testing", "will be run", "graded",
              "pass", "fail", "score", "partial credit"):
        check(not re.search(r"\b%s\b" % re.escape(w), ins.lower()), "instruction uses grading word %r" % w)
    for w in ("clock", "phase", "current transformer", " ct ", "offset", "storage", "blow", "unload", "lag",
              "align", "synchron", "bug", "defect", "hidden", "fault", "receiver"):
        check(w not in ins.lower(), "instruction names a mechanism or an element to test: %r" % w)
    sys.path.insert(0, "authoring/provenance")
    import json as _json, filecmp as _fc
    tr = _json.load(open("tests/hidden/truth.json"))
    check(len(tr) == 8, "hidden sites must number 8")
    sys.path.insert(0, "tests")
    import grade_audits
    check(grade_audits.MAX_WRONG == 1, "grader allowance 1 of 8, as the instruction states")
    check(grade_audits.TOL == {"avg_demand_m3_min": 0.03, "specific_power_kw_per_m3_min": 0.03,
                               "peak_demand_m3_min": 0.05, "leak_m3_min": 0.05}, "tolerances 3 and 5 percent")
    sys.path.insert(0, "authoring/provenance")
    import gen
    ex = _json.load(open("environment/data/examples/s-201/audit_result.json"))
    check(set(ex) == set(grade_audits.TOL), "example result keys must be the procedure's keys")
    proc = open("environment/data/docs/audit_procedure.md").read()
    for k in grade_audits.TOL:
        check("`%s`" % k in proc, "procedure does not define %s" % k)
    for name, c in gen.SITES.items():
        if c.get("example"):
            check(not c.get("one_phase") and not c.get("clock_s"), "the example must carry no logger fault")
    for x in ("solution/solve.sh", "tests/test.sh"):
        check(os.access(x, os.X_OK), "%s not executable" % x)
    df = open("environment/Dockerfile").read()
    check("chown -R root:root /app/data" in df, "environment Dockerfile must keep /app/data read-only")
    check("hidden" not in df, "hidden case packages must not reach the agent's image")
    check(not os.path.exists("environment/hidden") and not os.path.exists("environment/data/hidden"),
          "hidden case packages under environment/")
    check("chmod 700 /logs/verifier" in open("tests/Dockerfile").read() and "chmod 700 /logs/verifier" in open("tests/test.sh").read(),
          "reward directory must be root-only")
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([sys.executable, "-B", "authoring/provenance/build.py", d], capture_output=True, text=True)
        check(p.returncode == 0, "build.py failed: %s" % p.stderr[-500:])
        for sub in ("environment/data", "tests/hidden", "tests/app_data"):
            if os.path.isfile(sub):
                check(filecmp.cmp(os.path.join(d, sub), sub, shallow=False), "%s does not regenerate" % sub)
                continue
            for top, _, files in os.walk(sub):
                for f in files:
                    rel = os.path.relpath(os.path.join(top, f), ".")
                    check(os.path.isfile(os.path.join(d, rel)) and filecmp.cmp(os.path.join(d, rel), rel, shallow=False),
                          "%s does not regenerate byte for byte" % rel)
    for frag in ("python3 -I", "120 seconds", "unprivileged", "alone", "one after another", "network"):
        check(frag in ins, "instruction does not state the run condition '%s'" % frag)
    check(grade_audits.TIME_LIMIT_S == 120, "grader time limit is not 120 s")
    check(8 * grade_audits.TIME_LIMIT_S + 120 <= float(t["verifier"]["timeout_sec"]),
          "eight runs at the time limit must fit the verifier timeout")
    nums = re.findall(r"\d+(?:\.\d+)?", ins)
    check(("eight" in ins.lower() or " 8 " in ins) and ("seven" in ins.lower() or " 7 " in ins),
          "instruction does not state the eight cases and the seven needed")
    for n in ("3", "5", "28800"):
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
