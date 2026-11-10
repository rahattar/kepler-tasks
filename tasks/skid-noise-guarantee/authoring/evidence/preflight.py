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
    check(set(os.listdir("authoring")) == {"provenance", "evidence"},
          "authoring/ must hold only provenance/ and evidence/")
    for need in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/rig/lab.py",
                 "environment/rig/sealed/isim.py", "environment/rig/sealed/seed.json",
                 "environment/data/docs/standard.md", "environment/data/docs/laboratory.md",
                 "environment/data/docs/room_report.md", "environment/data/docs/meter_certificates.md",
                 "environment/data/docs/survey_report.md", "environment/data/machines.csv",
                 "environment/data/positions.csv", "environment/data/survey_levels.csv",
                 "environment/data/background_levels.csv", "environment/data/maintenance_log.csv",
                 "environment/data/rss_levels.csv", "environment/data/docs/room_check.md",
                 "tests/Dockerfile", "tests/test.sh", "tests/test_power.py", "tests/grade_power.py",
                 "tests/sealed/isim.py", "tests/sealed/seed.json", "solution/solve.sh", "solution/solve.py",
                 "authoring/provenance/gen.py", "authoring/provenance/build.py", "authoring/provenance/isim.py",
                 "authoring/provenance/tune.py", "authoring/provenance/seed.json",
                 "authoring/provenance/seed_screen.py", "authoring/evidence/seed_screen.txt",
                 "authoring/evidence/common.py", "authoring/evidence/budget.py", "authoring/evidence/budget.txt",
                 "authoring/evidence/route_study.py", "authoring/evidence/route_study.txt",
                 "authoring/evidence/method_spread.py", "authoring/evidence/method_spread.txt",
                 "authoring/evidence/independent.py", "authoring/evidence/independent.txt",
                 "authoring/evidence/null_baselines.py", "authoring/evidence/null_baselines.txt",
                 "authoring/evidence/hedge_study.py", "authoring/evidence/hedge_study.txt",
                 "authoring/evidence/verifier_checks.py", "authoring/evidence/verifier_checks.txt",
                 "authoring/evidence/reference_run.py", "authoring/evidence/reference_run.txt"):
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
            check(all(b < 128 for b in open(p, "rb").read()), "non-ASCII bytes in %s" % p)
    check(not junk, "junk that must be removed: %s" % sorted(junk))
    t = tomllib.load(open("task.toml", "rb"))
    check(t.get("schema_version") == "1.4", "schema_version must be 1.4")
    check(t.get("artifacts") == ["/app/output/sound_power.csv"], "artifacts must be /app/output/sound_power.csv")
    check(t["task"]["name"].endswith("/skid-noise-guarantee"), "task name")
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
        body = t["metadata"][{"## Difficulty": "difficulty_explanation",
                              "## Reference solution": "solution_explanation",
                              "## Verification": "verification_explanation"}[h]].strip()
        check(body in readme, "README %s does not carry the full explanation" % h)
    vc = open("authoring/evidence/verifier_checks.txt").read()
    check("UNEXPECTED" not in vc, "verifier_checks.txt reports an unexpected case")
    rs = open("authoring/evidence/route_study.txt").read()
    check("every value is failed by at least three routes" in rs, "route_study.txt: a value no three routes fail")
    check("UNDER THE BAR" not in rs, "route_study.txt: a route fails by less than twice the tolerance")
    ms = open("authoring/evidence/method_spread.txt").read()
    check(" 20 of 20" in ms and re.search(r"\| (?!72)\d+ \|", ms) is None,
          "method_spread.txt: a sound method does not get every value right on every seed")
    hs = open("authoring/evidence/hedge_study.txt").read()
    check("No choice that decides the result can be hedged" in hs, "hedge_study.txt: a choice can be hedged")
    ss = open("authoring/evidence/seed_screen.txt").read()
    check("<- chosen" in ss and json.load(open("authoring/provenance/seed.json"))["seed"] == int(
        re.search(r"^seed (\d+):", ss).group(1)), "seed_screen.txt does not choose the shipped seed")
    ins = open("instruction.md").read()
    check(not ins.lstrip().startswith("#"), "instruction must have no heading")
    check(ins.rstrip().endswith("You have 28800 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction closing line")
    for w in ("grader", "verifier", "reward", "scoring", "test_", "tested", "testing", "will be run", "graded",
              "pass", "fail", "score", "partial credit"):
        check(not re.search(r"\b%s\b" % re.escape(w), ins.lower()), "instruction uses grading word %r" % w)
    # the prose of the instruction, with the paths, commands and header it has to name taken out
    body = re.sub(r"`[^`]*`", " ", ins.lower()).replace(
        "do not cheat by using online solutions or hints specific to this task.", "")
    for w in ("reverberation", "reverberant", "absorption", "absorptive", "windscreen", "silencer", "enclosure",
              "panel", "blower", "louvre", "louvred", "quarter space", "half space", "solid angle", "diffuse",
              "rated speed", "speed rule", "valid", "invalid", "drop", "configuration", "certificate",
              "calibration", "correction", "energy average", "measurement surface", "modified", "no longer",
              "out of date", "hint", "hidden", "trap", "0.65", "2508", "p15", "p16", "sabine", "0.161",
              "instrument", "meter", "windscreen", "column", "mislabel", "label", "work order", "m-2", "m-5"):
        check(w not in body, "instruction names a mechanism or an element to find: %r" % w)
    for frag in ("sound_power.csv", "slm <position> <state>", "rt <position>", "the booking is 2 readings",
                 "C1 to C8", "as it stands now", "NS-7", "to one decimal place",
                 "machine,lw_63,lw_125,lw_250,lw_500,lw_1k,lw_2k,lw_4k,lw_8k,lwa", "28800",
                 "/app/data/docs/standard.md", "/app/data/docs/laboratory.md", "/app/lab_reports",
                 "/app/output/sound_power.csv"):
        check(frag in ins, "instruction does not state '%s'" % frag)
    for top, _, files in os.walk("environment/data"):
        for f in files:
            ap = "/app/data/" + os.path.relpath(os.path.join(top, f), "environment/data")
            check(ap in ins, "instruction does not name the input file %s" % ap)
    # the documents must not name the effects or the traps
    docs = " ".join(open(os.path.join(top, f)).read().lower()
                    for top, _, fs in os.walk("environment/data") for f in fs)
    for w in ("out of date", "not been updated", "stale", "hint", "trap", "superseded", "no longer", "invalid",
              "mistaken", "in error", "incorrect", "overstates", "understates", "beware", "note that the"):
        check(not re.search(r"\b%s\b" % re.escape(w), docs), "documents name a mechanism: %r" % w)
    sys.path.insert(0, "tests")
    import grade_power  # noqa: F401
    sys.path.insert(0, "tests/sealed")
    import isim
    check(grade_power.GATE == 72 and len(isim.MACHINES) == 8 and isim.TOL == 1.0,
          "eight machines, nine values each, all required, tolerance 1.0 dB")
    check(json.load(open("tests/sealed/seed.json")) == json.load(open("environment/rig/sealed/seed.json"))
          == json.load(open("authoring/provenance/seed.json")),
          "verifier, instrument and provenance share the seed")
    check(filecmp.cmp("tests/sealed/isim.py", "environment/rig/sealed/isim.py", shallow=False)
          and filecmp.cmp("tests/sealed/isim.py", "authoring/provenance/isim.py", shallow=False),
          "the three copies of the sealed definition must be identical")
    check("BUDGET = 2" in open("authoring/provenance/isim.py").read(), "the booking is 2 readings")
    rig = open("environment/rig/lab.py").read()
    check("O_EXCL" in rig and "O_NOFOLLOW" in rig and "S.BUDGET" in rig and "check_dir" in rig,
          "the instrument: booking from the sealed definition, exclusive record files, directory checks")
    lab = open("environment/data/docs/laboratory.md").read()
    check("2 readings" in lab and "slm <position> <state>" in lab and "rt <position>" in lab,
          "laboratory.md states the booking and both commands")
    p = subprocess.run([sys.executable, "-B", "authoring/provenance/tune.py"], capture_output=True, text=True)
    check(p.returncode == 0, "tune.py: the tuned values do not follow from the design rules")
    df = open("environment/Dockerfile").read()
    for frag in ("useradd --create-home --shell /usr/sbin/nologin lab", "chmod 700 /opt/lab/sealed /opt/lab/state",
                 "chown -R root:root /app/data", "agent ALL=(lab) NOPASSWD: /opt/lab/lab.py", "env_reset",
                 "/usr/local/bin/$c", "for c in slm rt", "visudo -cf", "chown lab:lab /app/lab_reports"):
        check(frag in df, "environment Dockerfile lacks '%s'" % frag)
    check("tests/" not in df and "sealed/seed" not in df.replace("rig/sealed/", ""),
          "verifier material in the agent image")
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
                    check(os.path.isfile(os.path.join(d, rel))
                          and filecmp.cmp(os.path.join(d, rel), rel, shallow=False),
                          "%s does not regenerate byte for byte" % rel)
    # numbers quoted in the explanations must appear in the evidence files
    ev = " ".join(open(os.path.join("authoring/evidence", f)).read()
                  for f in os.listdir("authoring/evidence") if f.endswith(".txt"))
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
