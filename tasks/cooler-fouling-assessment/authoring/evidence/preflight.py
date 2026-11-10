"""Structural pre-flight: what the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Exits non-zero if anything fails. Needs numpy (the record regeneration check).
"""
import filecmp, os, re, subprocess, sys, tempfile, tomllib

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment", "solution", "tests", "authoring"}
# Files the agent can read: the instruction and everything copied to /app/data. The requirement the verifier
# applies must appear in none of them (a visible band lets a solver split an answer between two readings of a
# choice instead of settling it), and the relations that settle those choices must appear in them.
TOL_NUMBER = re.compile(r"(?<![\d.])0\.04(?![\d])")
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
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/start-hxtest",
                 "environment/hxtest/server.py", "environment/hxtest/hx.py", "environment/hxtest/run-service",
                 "tests/Dockerfile", "tests/test.sh", "tests/test_fouling.py", "tests/grade_hx.py", "tests/hx.py",
                 "solution/solve.sh", "solution/solve.py", "authoring/provenance/gen.py", "authoring/provenance/hx.py",
                 "authoring/evidence/route_study.txt", "authoring/evidence/method_spread.txt",
                 "authoring/evidence/campaign_study.txt", "authoring/evidence/constant_null.txt",
                 "authoring/evidence/wilson_noise.txt", "authoring/evidence/hedge_study.py",
                 "authoring/evidence/hedge_study.txt"):
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
        for d in dirs:
            check(not (d.isupper() and len(d) > 1), "all-uppercase folder name: %s" % os.path.join(top, d))
    check(not junk, "junk that must be removed: %s" % sorted(junk))
    t = tomllib.load(open("task.toml", "rb"))
    check(t.get("schema_version") == "1.4", "schema_version must be 1.4")
    check(t.get("artifacts") == ["/app/output/fouling.csv"], "artifacts must be /app/output/fouling.csv")
    check(t["task"]["name"].endswith("/cooler-fouling-assessment"), "task name")
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
    check(t["agent"]["timeout_sec"] == 28800.0, "agent timeout must match the instruction's 28800 s")
    for w in ("grader", "verifier", "reward", "scoring", "test_"):
        check(w not in ins.lower().replace("/app/test_reports", ""), "instruction uses grading word %r" % w)
    for w in ("standby", "bias", "plugged", "ribbed", "vendor", "baffle"):
        check(w not in ins.lower(), "instruction names a mechanism: %r" % w)
    check(filecmp.cmp("tests/hx.py", "authoring/provenance/hx.py", shallow=False) and
          filecmp.cmp("environment/hxtest/hx.py", "authoring/provenance/hx.py", shallow=False),
          "the three copies of hx.py differ")
    for x in ("solution/solve.sh", "tests/test.sh", "environment/start-hxtest", "environment/hxtest/run-service"):
        check(os.access(x, os.X_OK), "%s not executable" % x)
    df = open("environment/Dockerfile").read()
    check("chmod 700 /opt/hxtest" in df and "chmod 1775 /app" in df, "environment Dockerfile lost the isolation modes")
    check("chmod 700 /logs/verifier" in open("tests/Dockerfile").read() and "chmod 700 /logs/verifier" in open("tests/test.sh").read(),
          "reward directory must be root-only")
    check("O_EXCL" in open("environment/hxtest/server.py").read(), "service report writes must be O_EXCL")
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([sys.executable, "-B", "authoring/provenance/gen.py", d], capture_output=True, text=True)
        check(p.returncode == 0, "gen.py failed: %s" % p.stderr[-500:])
        for top, _, files in os.walk("environment/data"):
            if "docs" in top:
                continue
            for f in files:
                rel = os.path.relpath(os.path.join(top, f), "environment/data")
                check(os.path.isfile(os.path.join(d, rel)) and filecmp.cmp(os.path.join(d, rel), os.path.join(top, f), shallow=False),
                      "environment/data/%s does not regenerate byte for byte" % rel)
    nums = re.findall(r"\d+(?:\.\d+)?", ins)
    for n in ("28800", "2026"):
        check(any(x.startswith(n) for x in nums), "instruction does not state %s" % n)
    # the verifier's requirement must be readable nowhere the agent can reach
    visible = ["instruction.md"] + sorted(os.path.join(dp, f) for dp, _, fs in os.walk("environment/data") for f in fs)
    for p in visible:
        txt = open(p, encoding="ascii", errors="ignore").read()
        check(not TOL_NUMBER.search(txt), "agent-visible file states the requirement band: %s" % p)
        check("tolerance" not in txt.lower(), "agent-visible file mentions a tolerance: %s" % p)
    check(TOL_NUMBER.search(open("tests/grade_hx.py").read()) is not None, "the verifier lost its band")
    # the relations that settle the two readings a solver would otherwise have to guess
    rib = open("environment/data/docs/retube_2026.md").read()
    check("h_ribbed / h_plain - 1 = K * (f_ribbed / f_plain - 1)" in rib,
          "the retube note lost the film-gain / friction-gain relation")
    check("single coefficient K" in rib and "all three lots" in rib,
          "the retube note must say the coefficient is one for the rib form, the same for every lot")
    check("no value of K" in rib, "the retube note must not give the value of K")
    sheet = open("environment/data/docs/thermal_design_sheet.md").read()
    check("inversely with the baffle spacing" in sheet,
          "the design sheet lost the crossflow velocity / baffle spacing relation")
    ds = open("environment/data/docs/c310_vendor_datasheet.md").read()
    check("E1 and E10" in ds and "one batch" in ds and "ran its program\nonce for the pair" in ds
          and "only\nrating either cooler has" in ds,
          "the C-310 datasheet must record that one rating from one program covers both new coolers")
    check("whatever the program is worth" not in ds, "the C-310 datasheet must not draw the inference for the solver")
    log = open("environment/data/maintenance_log.csv").read()
    for phrase in ("dosing pump failed", "repaired 2026-09-12", "Shock chlorination"):
        check(phrase in log, "the maintenance log lost %r, which dates a cooling-water event" % phrase)
    reg = open("environment/data/unit_register.csv").read()
    check(reg.count("C-310") == 2, "the register must carry the two new C-310 coolers")
    acc = open("environment/data/acceptance_tests_2025.csv").read()
    for u in ("E1,", "E10,"):
        check(u not in acc, "the 2025 acceptance sheet must not carry a new cooler (%s)" % u.rstrip(","))
    if FAILS:
        print("%d FAILED of %d checks:" % (len(FAILS), len(FAILS) + PASSED[0]))
        for f in FAILS:
            print("  FAIL ", f)
        return 1
    print("pre-flight clean: %d checks passed" % PASSED[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
