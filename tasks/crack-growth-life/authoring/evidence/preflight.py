"""Structural pre-flight: what the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Exits non-zero if anything fails.
"""
import base64
import filecmp
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib

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
    check(set(os.listdir("authoring")) == {"provenance", "evidence"}, "authoring/ must hold only provenance/ and evidence/")
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/rig/fcgr.py",
                 "environment/rig/sealed/fcgsim.py", "environment/rig/sealed/seed.json",
                 "environment/data/docs/procedure.md", "environment/data/docs/laboratory.md",
                 "environment/data/component_register.csv", "environment/data/material_certificates.csv",
                 "environment/data/inspection_2026.csv", "environment/data/strain_survey_rainflow.csv",
                 "environment/data/fcg_handbook.csv", "environment/data/maintenance_log.csv",
                 "environment/data/examples/E01_record.csv", "environment/data/examples/E02_record.csv",
                 "tests/Dockerfile", "tests/test.sh", "tests/test_intervals.py", "tests/grade_intervals.py",
                 "tests/sealed/fcgsim.py", "tests/sealed/seed.json", "solution/solve.sh", "solution/solve.py",
                 "authoring/provenance/gen.py", "authoring/provenance/build.py", "authoring/provenance/fcgsim.py",
                 "authoring/provenance/seed_screen.py", "authoring/evidence/seed_screen.txt",
                 "authoring/evidence/hedge_study.py", "authoring/evidence/hedge_study.txt", "authoring/evidence/reference_run.txt",
                 "authoring/evidence/common.py", "authoring/evidence/route_study.py", "authoring/evidence/route_study.txt",
                 "authoring/evidence/method_spread.py", "authoring/evidence/method_spread.txt",
                 "authoring/evidence/independent.py", "authoring/evidence/independent.txt",
                 "authoring/evidence/null_baselines.py", "authoring/evidence/null_baselines.txt",
                 "authoring/evidence/verifier_checks.py", "authoring/evidence/verifier_checks.txt"):
        check(os.path.isfile(need), "missing %s" % need)
    junk = []
    for top, dirs, files in os.walk("."):
        for d in dirs:
            if d in ("__pycache__", ".pytest_cache", ".ipynb_checkpoints", "jobs"):
                junk.append(os.path.join(top, d))
            check(not (d.isupper() and len(d) > 1), "all-uppercase folder name: %s" % os.path.join(top, d))
        for f in files:
            p = os.path.join(top, f)
            if f.startswith(".") or f.endswith((".pyc", ".orig", ".bak")):
                junk.append(p)
            base = os.path.splitext(f)[0]
            check(f == "README.md" or not (base.isupper() and len(base) > 1), "all-uppercase file name: %s" % p)
            txt = open(p, "rb").read()
            check(all(b < 128 for b in txt), "non-ASCII bytes in %s" % p)
            low = txt.decode("ascii", "ignore").lower()
            for w in BLOCKED:
                n = low.count(w)
                if p == "./task.toml":
                    n -= low.count('name = "%s/' % w)
                check(n == 0, "blocked programme name in %s" % p)
    check(not junk, "junk that must be removed: %s" % sorted(junk))
    t = tomllib.load(open("task.toml", "rb"))
    check(t.get("schema_version") == "1.4", "schema_version must be 1.4")
    check(t.get("artifacts") == ["/app/output/intervals.json"], "artifacts must be /app/output/intervals.json")
    check(t["task"]["name"] == BLOCKED[0] + "/crack-growth-life", "task name")
    slug = t["task"]["name"].split("/", 1)[1]
    check(len(slug.split("-")) <= 3, "task name must be at most 3 hyphen-separated words")
    check(os.path.basename(ROOT) == slug, "bundle folder must be named after the task")
    check(t["verifier"]["environment_mode"] == "separate", "verifier must run in a separate environment")
    check(t["verifier"]["environment"]["network_mode"] == "no-network", "verifier must have no network")
    check(t["agent"].get("user") == "agent", "agent must run as the user agent")
    check(600.0 <= float(t["verifier"]["timeout_sec"]) <= 28800.0, "verifier timeout must be 600-28800 s")
    check(t["agent"]["timeout_sec"] == 28800.0, "agent timeout must match the instruction's 28800 s")
    for k in ("difficulty_explanation", "solution_explanation", "verification_explanation", "relevant_experience",
              "conflicts_of_interest"):
        check(len(t["metadata"].get(k, "")) > 100, "metadata.%s too short" % k)
    for k in ("domain", "field", "subfield", "category", "subcategory", "author_name", "author_email",
              "author_organization", "expert_time_estimate_hours", "tags"):
        check(k in t["metadata"], "metadata lacks %s" % k)
    check(t["metadata"]["domain"] == "engineering-sciences" and t["metadata"]["field"] == "mechanical-engineering",
          "domain/field")
    de = t["metadata"]["difficulty_explanation"].lower()
    check("synthetic" in de and "realistic" in de, "difficulty_explanation must say synthetic and argue realism")
    for w in ("low effort", "xhigh", "probe", "trial run", "of 3", "of 8 solved", "agents solved"):
        check(w not in de, "difficulty_explanation must not carry agent-performance numbers (%r)" % w)
    readme = open("README.md").read()
    for h in ("## Difficulty", "## Reference solution", "## Verification"):
        check(h in readme, "README lacks %s" % h)
        body = t["metadata"][{"## Difficulty": "difficulty_explanation", "## Reference solution": "solution_explanation",
                              "## Verification": "verification_explanation"}[h]].strip()
        check(body in readme, "README %s does not carry the full explanation" % h)
    ins = open("instruction.md").read()
    check(not ins.lstrip().startswith("#"), "instruction must have no heading")
    check(ins.rstrip().endswith("You have 28800 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction closing line")
    for w in ("grader", "verifier", "reward", "scoring", "test_", "tested", "testing", "will be run", "graded",
              "pass", "fail", "score", "partial credit"):
        check(not re.search(r"\b%s\b" % re.escape(w), ins.lower()), "instruction uses grading word %r" % w)
    body = ins.lower().replace("do not cheat by using online solutions or hints specific to this task.", "")
    for w in ("closure", "residual", "mk", "magnification", "vibratory", "stress relie", "payload", "throughput",
              "out of service", "hint", "hidden", "trap", "0.5 "):
        check(w not in body, "instruction names a mechanism or an element to find: %r" % w)
    for frag in ("intervals.json", "fcgr paris <R>", "fcgr threshold <R>", "5 slots", "40 percent", "half of its",
                 "All 16 intervals must meet", "28800", "uses one test slot", "uses three"):
        check(frag in ins, "instruction does not state '%s'" % frag)
    # the documents must not name the effects or the traps
    docs = " ".join(open(os.path.join("environment/data", f)).read().lower() for f in
                    ("docs/procedure.md", "docs/laboratory.md", "component_register.csv", "fcg_handbook.csv",
                     "maintenance_log.csv", "material_certificates.csv", "inspection_2026.csv",
                     "examples/E01_record.csv", "examples/E02_record.csv"))
    # FA-3 names the weld-toe residual stress once (R counts it, at BS 7910's level); nothing gives its values
    check(docs.count("residual") == 1 and "residual stress at the weld toe, at the level bs 7910 gives" in docs,
          "the documents name residual stress only in FA-3's one sentence")
    for w in ("closure", "magnification", "mk", "annex m", "pd 6493", "iiw", "0.2 yield", "20 percent", "credited",
              "s460nl grows", "grade factor", "faster",
              "saturat", "walker", "cycles fall", "fewer cycles", "operating days of the survey", "hint", "trap"):
        check(w not in docs, "documents name a mechanism: %r" % w)
    sys.path.insert(0, "tests")
    import grade_intervals  # noqa: F401
    sys.path.insert(0, "tests/sealed")
    import fcgsim
    check(fcgsim.GATE == 16 and abs(fcgsim.LO - 0.40) < 1e-12 and abs(fcgsim.HI - 0.50) < 1e-12,
          "gate 16 and window 0.40-0.50, as stated")
    check(len(fcgsim.COMPS) == 16, "sixteen cracks")
    check(json.load(open("tests/sealed/seed.json")) == json.load(open("environment/rig/sealed/seed.json")),
          "verifier and laboratory must share the seed")
    check(filecmp.cmp("tests/sealed/fcgsim.py", "environment/rig/sealed/fcgsim.py", shallow=False)
          and filecmp.cmp("tests/sealed/fcgsim.py", "authoring/provenance/fcgsim.py", shallow=False),
          "the three copies of the sealed definition must be identical")
    rig = open("environment/rig/fcgr.py").read()
    check("BUDGET = 5" in rig and "O_EXCL" in rig and "O_NOFOLLOW" in rig and '"threshold": 3' in rig and '"paris": 1' in rig,
          "laboratory budget 5 (Paris 1, threshold 3) with exclusive record files")
    lab = open("environment/data/docs/laboratory.md").read()
    check("5 test slots" in lab and "Uses 1 test slot" in lab and "Uses 3 test slots" in lab, "laboratory.md states the costs")
    df = open("environment/Dockerfile").read()
    for frag in ("useradd --create-home --shell /usr/sbin/nologin lab", "chmod 700 /opt/lab/sealed /opt/lab/state",
                 "chown -R root:root /app/data", "agent ALL=(lab) NOPASSWD: /opt/lab/fcgr.py", "env_reset",
                 "visudo -cf", "chown lab:lab /app/lab_reports"):
        check(frag in df, "environment Dockerfile lacks '%s'" % frag)
    check("tests/" not in df and "sealed/seed" not in df.replace("rig/sealed/", ""), "verifier material in the agent image")
    tdf = open("tests/Dockerfile").read()
    check("chmod 700 /logs/verifier" in tdf and "chmod 700 /logs/verifier" in open("tests/test.sh").read(),
          "reward directory must be root-only")
    check("chmod 700 /tests" in tdf, "/tests must be root-only")
    for x in ("solution/solve.sh", "tests/test.sh"):
        check(os.access(x, os.X_OK), "%s not executable" % x)
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([sys.executable, "-B", "authoring/provenance/build.py", d], capture_output=True, text=True)
        check(p.returncode == 0, "build.py failed: %s" % p.stderr[-500:])
        for sub in ("environment/data", "environment/rig/sealed", "tests/sealed", "tests/app_data"):
            for top, _, files in os.walk(sub):
                for f in files:
                    rel = os.path.relpath(os.path.join(top, f), ".")
                    check(os.path.isfile(os.path.join(d, rel)) and filecmp.cmp(os.path.join(d, rel), rel, shallow=False),
                          "%s does not regenerate byte for byte" % rel)
    # numbers quoted in the explanations must appear in the evidence files
    ev = " ".join(open(os.path.join("authoring/evidence", f)).read() for f in os.listdir("authoring/evidence") if f.endswith(".txt"))
    evnums = set(x.lstrip("+-") for x in re.findall(r"-?\d+\.\d+", ev))
    for k in ("solution_explanation", "verification_explanation"):
        for n in set(re.findall(r"[-+]?\d+\.\d{2,}", t["metadata"][k])):
            check(n.lstrip("+-") in evnums, "%s quotes %s, which is in no evidence file" % (k, n))
    if FAILS:
        print("%d FAILED of %d checks:" % (len(FAILS), len(FAILS) + PASSED[0]))
        for f in FAILS:
            print("  FAIL ", f)
        return 1
    print("pre-flight clean: %d checks passed" % PASSED[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
