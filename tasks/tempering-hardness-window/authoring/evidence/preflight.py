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
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/rig/lab.py",
                 "environment/rig/sealed/tsim.py", "environment/rig/sealed/seed.json",
                 "environment/data/docs/procedure.md", "environment/data/docs/laboratory.md",
                 "environment/data/batches.csv", "environment/data/mill_certificates.csv",
                 "environment/data/production_log.csv", "environment/data/supplier_tempering_curves.csv",
                 "tests/Dockerfile", "tests/test.sh", "tests/test_tempering.py", "tests/grade_tempering.py",
                 "tests/sealed/tsim.py", "tests/sealed/seed.json", "solution/solve.sh", "solution/solve.py",
                 "authoring/provenance/gen.py", "authoring/provenance/build.py", "authoring/provenance/tsim.py",
                 "authoring/provenance/seed.json", "authoring/provenance/seed_screen.py",
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
            low = txt.decode("ascii", "ignore").lower()
            for w in BLOCKED:
                n = low.count(w)
                if p == "./task.toml":
                    n -= low.count('name = "%s/' % w)
                check(n == 0, "blocked programme name in %s" % p)
    check(not junk, "junk that must be removed: %s" % sorted(junk))
    t = tomllib.load(open("task.toml", "rb"))
    check(t.get("schema_version") == "1.4", "schema_version must be 1.4")
    check(t.get("artifacts") == ["/app/output/tempering.json"], "artifacts must be /app/output/tempering.json")
    check(t["task"]["name"] == BLOCKED[0] + "/tempering-hardness-window", "task name")
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
    for w in ("retained", "austenite", "fresh martensite", "secondary", "hump", "vanadium", "molybdenum", "hollomon",
              "jaffe", "equivalent", "41-7864", "43-2288", "52-1", "pinion", "hint", "hidden", "trap", "typical heat"):
        check(w not in body, "instruction names a mechanism or an element to find: %r" % w)
    for frag in ("tempering.json", "temper <heat> <T> [<diameter_mm> <surface|half-radius>] [double]", "11 tempers",
                 "A test tempered once uses one temper; a test tempered twice uses two", "a whole degree C",
                 "Every batch must meet its required hardness range", "28800", "HT-4", "B01 to B13",
                 "/app/data/batches.csv", "/app/data/mill_certificates.csv", "/app/data/production_log.csv",
                 "/app/data/supplier_tempering_curves.csv", "/app/data/docs/procedure.md",
                 "/app/data/docs/laboratory.md", "/app/lab_reports", "/app/output/tempering.json"):
        check(frag in ins, "instruction does not state '%s'" % frag)
    for top, _, files in os.walk("environment/data"):
        for f in files:
            ap = "/app/data/" + os.path.relpath(os.path.join(top, f), "environment/data")
            check(ap in ins, "instruction does not name the input file %s" % ap)
    # the documents must not name the effects or the traps
    docs = " ".join(open(os.path.join("environment/data", f)).read().lower() for f in
                    ("docs/procedure.md", "docs/laboratory.md", "batches.csv", "mill_certificates.csv",
                     "production_log.csv", "supplier_tempering_curves.csv"))
    for w in ("retained", "austenite", "fresh martensite", "secondary", "hump", "carbide", "hollomon", "jaffe",
              "tempering parameter", "not the same", "differs", "deviat", "hint", "trap", "out of date",
              "not been updated", "the batch list is"):
        check(w not in docs, "documents name a mechanism: %r" % w)
    sys.path.insert(0, "tests")
    import grade_tempering  # noqa: F401
    sys.path.insert(0, "tests/sealed")
    import tsim
    check(grade_tempering.GATE == 13 and len(tsim.BATCHES) == 13, "thirteen batches, all required")
    check(json.load(open("tests/sealed/seed.json")) == json.load(open("environment/rig/sealed/seed.json"))
          == json.load(open("authoring/provenance/seed.json")), "verifier, laboratory and provenance share the seed")
    check(filecmp.cmp("tests/sealed/tsim.py", "environment/rig/sealed/tsim.py", shallow=False)
          and filecmp.cmp("tests/sealed/tsim.py", "authoring/provenance/tsim.py", shallow=False),
          "the three copies of the sealed definition must be identical")
    check("BUDGET = 11" in open("authoring/provenance/tsim.py").read(), "laboratory booking 11 tempers")
    rig = open("environment/rig/lab.py").read()
    check("O_EXCL" in rig and "O_NOFOLLOW" in rig and "S.BUDGET" in rig and "check_dir" in rig and "tempers" in rig,
          "laboratory: booking from the sealed definition, exclusive record files, directory checks")
    lab = open("environment/data/docs/laboratory.md").read()
    check("11 tempers" in lab and "tempered twice uses two" in lab and "mean of five indentations" in lab,
          "laboratory.md states the booking")
    df = open("environment/Dockerfile").read()
    for frag in ("useradd --create-home --shell /usr/sbin/nologin lab", "chmod 700 /opt/lab/sealed /opt/lab/state",
                 "chown -R root:root /app/data", "agent ALL=(lab) NOPASSWD: /opt/lab/lab.py", "env_reset",
                 "/usr/local/bin/temper",
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
        for n in set(re.findall(r"[-+]?\d+\.\d{2,}", t["metadata"][k])) - {"273.15"}:   # 273.15: kelvin offset
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
