"""Structural pre-flight: what the platform checks that can be checked offline.

    python3 authoring/evidence/preflight.py

Exits non-zero if anything fails.
"""
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
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/rig/lab.py",
                 "environment/rig/sealed/isim.py", "environment/rig/sealed/seed.json",
                 "environment/data/docs/standard.md", "environment/data/docs/laboratory.md",
                 "environment/data/docs/inspection_report.md", "environment/data/docs/oem_rotor_data.md",
                 "environment/data/parts_register.csv", "environment/data/material_certificates.csv",
                 "environment/data/rotor_inspection.csv", "environment/data/thermal_survey.csv",
                 "environment/data/materials.csv", "environment/data/maintenance_log.csv",
                 "tests/Dockerfile", "tests/test.sh", "tests/test_bores.py", "tests/grade_bores.py",
                 "tests/sealed/isim.py", "tests/sealed/seed.json", "solution/solve.sh", "solution/solve.py",
                 "authoring/provenance/gen.py", "authoring/provenance/build.py", "authoring/provenance/isim.py",
                 "authoring/provenance/tune.py", "authoring/provenance/seed.json", "authoring/provenance/seed_screen.py",
                 "authoring/evidence/seed_screen.txt", "authoring/evidence/hedge_study.py",
                 "authoring/evidence/hedge_study.txt", "authoring/evidence/reference_run.py",
                 "authoring/evidence/reference_run.txt", "authoring/evidence/common.py",
                 "authoring/evidence/route_study.py", "authoring/evidence/route_study.txt",
                 "authoring/evidence/method_spread.py", "authoring/evidence/method_spread.txt",
                 "authoring/evidence/independent.py", "authoring/evidence/independent.txt",
                 "authoring/evidence/null_baselines.py", "authoring/evidence/null_baselines.txt",
                 "authoring/evidence/verifier_checks.py", "authoring/evidence/verifier_checks.txt",
                 "authoring/evidence/windows.py", "authoring/evidence/windows.txt"):
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
    check(not junk, "junk that must be removed: %s" % sorted(junk))
    t = tomllib.load(open("task.toml", "rb"))
    check(t.get("schema_version") == "1.4", "schema_version must be 1.4")
    check(t.get("artifacts") == ["/app/output/bore_sheet.csv"], "artifacts must be /app/output/bore_sheet.csv")
    check(t["task"]["name"].endswith("/impeller-shrink-fits"), "task name")
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
    vc = open("authoring/evidence/verifier_checks.txt").read()
    check("UNEXPECTED" not in vc, "verifier_checks.txt reports an unexpected case")
    ins = open("instruction.md").read()
    check(not ins.lstrip().startswith("#"), "instruction must have no heading")
    check(ins.rstrip().endswith("You have 28800 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction closing line")
    for w in ("grader", "verifier", "reward", "scoring", "test_", "tested", "testing", "will be run", "graded",
              "pass", "fail", "score", "partial credit"):
        check(not re.search(r"\b%s\b" % re.escape(w), ins.lower()), "instruction uses grading word %r" % w)
    body = ins.lower().replace("do not cheat by using online solutions or hints specific to this task.", "")
    for w in ("titanium", "ti-6al", "110 %", "28.5", "interpolat", "extrapolat", "expansion", "coefficient",
              "hotter", "centrifugal", "growth", "hoop", "smoothing", "hint", "hidden", "trap",
              "out of date", "lame", "spin", "micrometer", "calibrat", "mill test", "mill value", "recoat", "coating", "rotor steel",
              "forging", "26nicrmov", "10500", "test speed"):
        check(w not in body, "instruction names a mechanism or an element to find: %r" % w)
    for frag in ("bore_sheet.csv", "cte <material> <T>", "the booking is 3 tests", "mm to three decimals",
                 "whole degrees C", "RS-3", "S1 to S6", "(BD)", "(TC)", "on the rotor as it is now",
                 "Every part must meet all the requirements of RS-3", "part,bore_mm,oven_C", "28800",
                 "/app/data/docs/standard.md", "/app/data/docs/laboratory.md", "/app/lab_reports",
                 "/app/output/bore_sheet.csv"):
        check(frag in ins, "instruction does not state '%s'" % frag)
    for top, _, files in os.walk("environment/data"):
        for f in files:
            ap = "/app/data/" + os.path.relpath(os.path.join(top, f), "environment/data")
            check(ap in ins, "instruction does not name the input file %s" % ap)
    # the documents must not name the effects or the traps
    docs = " ".join(open(os.path.join(top, f)).read().lower() for top, _, fs in os.walk("environment/data") for f in fs)
    for w in ("levels off", "flattens", "non-linear", "nonlinear", "interpolat", "extrapolat", "rises with",
              "correct to 20", "corrected to 20", "out of date", "not been updated", "stale", "hint", "trap",
              "superseded", "no longer", "concave"):
        check(not re.search(r"\b%s\b" % re.escape(w), docs), "documents name a mechanism: %r" % w)
    sys.path.insert(0, "tests")
    import grade_bores  # noqa: F401
    sys.path.insert(0, "tests/sealed")
    import isim
    check(grade_bores.GATE == 8 and len(isim.PARTS) == 8, "eight parts, all required")
    check(json.load(open("tests/sealed/seed.json")) == json.load(open("environment/rig/sealed/seed.json"))
          == json.load(open("authoring/provenance/seed.json")), "verifier, laboratory and provenance share the seed")
    check(filecmp.cmp("tests/sealed/isim.py", "environment/rig/sealed/isim.py", shallow=False)
          and filecmp.cmp("tests/sealed/isim.py", "authoring/provenance/isim.py", shallow=False),
          "the three copies of the sealed definition must be identical")
    check("BUDGET = 3" in open("authoring/provenance/isim.py").read(), "laboratory booking 3 tests")
    rig = open("environment/rig/lab.py").read()
    check("O_EXCL" in rig and "O_NOFOLLOW" in rig and "S.BUDGET" in rig and "check_dir" in rig,
          "laboratory: booking from the sealed definition, exclusive record files, directory checks")
    lab = open("environment/data/docs/laboratory.md").read()
    check("3 tests" in lab and "from 20 C to T" in lab, "laboratory.md states the booking and the test")
    p = subprocess.run([sys.executable, "-B", "authoring/provenance/tune.py"], capture_output=True, text=True)
    check(p.returncode == 0, "tune.py: the sealed limits and hoop stresses do not follow from the rules")
    df = open("environment/Dockerfile").read()
    for frag in ("useradd --create-home --shell /usr/sbin/nologin lab", "chmod 700 /opt/lab/sealed /opt/lab/state",
                 "chown -R root:root /app/data", "agent ALL=(lab) NOPASSWD: /opt/lab/lab.py", "env_reset",
                 "/usr/local/bin/$c", "for c in cte",
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
        for n in set(re.findall(r"[-+]?\d+\.\d{2,}", t["metadata"][k])) - {"0.001", "1.25"}:   # 0.001: RS-3's clearance rule; 1.25: the reference's stated allowance (%)
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
