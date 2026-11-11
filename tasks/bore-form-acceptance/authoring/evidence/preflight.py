"""Structural checks on the bundle. Run from the task directory:

    python3 authoring/evidence/preflight.py
"""
import filecmp
import os
import re
import subprocess
import sys
import tempfile
import tomllib

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment", "solution", "tests", "authoring"}
BAND = re.compile(r"(?<![\d.])1\.2(?![\d])")        # the band the verifier allows on a reported form error
FAILS, PASSED = [], [0]


def check(ok, msg):
    PASSED[0] += 1
    if not ok:
        FAILS.append(msg)


def main():
    os.chdir(ROOT)
    # ---- structure
    roots = set(os.listdir("."))
    check(roots <= ALLOWED_ROOT | {".source_zip"}, "root has unexpected entries: %s" % sorted(roots - ALLOWED_ROOT))
    for p in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/rig/lab.py",
              "environment/rig/sealed/isim.py", "environment/rig/sealed/seed.json", "solution/solve.py",
              "solution/solve.sh", "tests/Dockerfile", "tests/test.sh", "tests/test_form.py", "tests/grade_form.py",
              "tests/sealed/isim.py", "tests/sealed/seed.json", "authoring/provenance/isim.py",
              "authoring/provenance/gen.py", "authoring/provenance/tune.py", "authoring/evidence/common.py",
              "authoring/evidence/route_study.py", "authoring/evidence/route_study.txt",
              "authoring/evidence/method_spread.py", "authoring/evidence/method_spread.txt",
              "authoring/evidence/campaign_study.py", "authoring/evidence/campaign_study.txt",
              "authoring/evidence/hedge_study.py", "authoring/evidence/hedge_study.txt",
              "authoring/evidence/null_baselines.py", "authoring/evidence/null_baselines.txt",
              "authoring/evidence/verifier_checks.py", "authoring/evidence/verifier_checks.txt",
              "authoring/evidence/independent.py", "authoring/evidence/independent.txt",
              "authoring/evidence/reference_run.py", "authoring/evidence/reference_run.txt",
              "authoring/evidence/preflight.py"):
        check(os.path.isfile(p), "missing %s" % p)
    junk = []
    for dp, dirs, files in os.walk("."):
        for name in files:
            p = os.path.join(dp, name)
            if name.startswith(".") or name.endswith((".pyc", ".orig", ".rej")) or "__pycache__" in p:
                junk.append(p)
                continue
            with open(p, "rb") as f:
                raw = f.read()
            try:
                raw.decode("ascii")
            except UnicodeDecodeError:
                check(False, "not ASCII: %s" % p)
        for d in list(dirs):
            if d in ("__pycache__", ".pytest_cache"):
                junk.append(os.path.join(dp, d))
                dirs.remove(d)
    check(not junk, "junk that must be removed: %s" % sorted(junk))

    # ---- the sealed definition, in its three places
    for other in ("environment/rig/sealed/isim.py", "tests/sealed/isim.py"):
        check(filecmp.cmp("authoring/provenance/isim.py", other, shallow=False),
              "%s differs from authoring/provenance/isim.py" % other)
    check(filecmp.cmp("environment/rig/sealed/seed.json", "tests/sealed/seed.json", shallow=False),
          "the two seed.json differ")

    # ---- the records regenerate byte for byte, and the verifier's copy matches the agent's
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "data")
    r = subprocess.run([sys.executable, "-I", "authoring/provenance/gen.py", out], capture_output=True, text=True)
    check(r.returncode == 0, "gen.py failed: %s" % r.stderr[-300:])
    if r.returncode == 0:
        cmp = filecmp.dircmp("environment/data", out)
        bad = []

        def walk(c, base=""):
            bad.extend(os.path.join(base, n) for n in c.left_only + c.right_only + c.diff_files)
            for name, sub in c.subdirs.items():
                walk(sub, os.path.join(base, name))
        walk(cmp)
        check(not bad, "gen.py does not reproduce environment/data: %s" % sorted(bad)[:6])
    cmp2 = filecmp.dircmp("environment/data", "tests/app_data")
    bad2 = []

    def walk2(c, base=""):
        bad2.extend(os.path.join(base, n) for n in c.left_only + c.right_only + c.diff_files)
        for name, sub in c.subdirs.items():
            walk2(sub, os.path.join(base, name))
    walk2(cmp2)
    check(not bad2, "tests/app_data differs from environment/data: %s" % sorted(bad2)[:6])

    # ---- the instruction
    ins = open("instruction.md").read()
    check(ins.rstrip().endswith("You have 28800 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction's closing line")
    for w in ("grader", "verifier", "reward", "scoring", "test_", "tolerance"):
        check(w not in ins.lower(), "instruction mentions %r" % w)
    for w in ("minimum zone", "least squares", "least-squares", "spindle", "error motion", "nyquist", "alias",
              "undulation", "taylor", "mating", "envelope", "re-hone", "rehone", "same setup", "transfer",
              "temperature", "filter", "harmonic"):
        check(w not in ins.lower(), "instruction gives away the mechanism: %r" % w)
    check("28800" in ins and "4 scans" in ins, "instruction must state the time and the booking")

    # ---- the band must be readable nowhere the agent can reach
    visible = ["instruction.md"] + sorted(os.path.join(dp, f) for dp, _, fs in os.walk("environment/data")
                                          for f in fs if not f.endswith(".csv") or "measurements" not in dp)
    for p in visible:
        txt = open(p, encoding="ascii", errors="ignore").read()
        check(not BAND.search(txt), "an agent-visible file states the band: %s" % p)
    check(BAND.search(open("tests/grade_form.py").read()) is not None, "the verifier lost its band")

    # ---- what the documents must say, and must not
    fm7 = open("environment/data/docs/standard_fm7.md").read()
    for phrase in ("exp(-pi (0.4697 n / 50)^2)", "minimum-zone", "largest cylinder", "smallest such cylinder",
                   "diametrically opposite", "11.7e-6", "reject_both"):
        check(phrase in fm7, "FM-7 lost %r" % phrase)
    notes = open("environment/data/docs/instrument_notes.md").read()
    for phrase in ("12 touch points", "least-squares", "spindle encoder's zero", "has not been renewed"):
        check(phrase in notes, "the instrument notes lost %r" % phrase)
    room = open("environment/data/docs/metrology_room.md").read()
    check("4 scans" in room and "does not refill" in room, "the metrology room note lost its booking")
    for p in visible:
        txt = open(p, encoding="ascii", errors="ignore").read().lower()
        check("error motion rides" not in txt and " 23 upr" not in txt and "29 upr" not in txt,
              "a document gives away the machine's error motion: %s" % p)

    # ---- task.toml, and the three explanations shared with the README
    t = tomllib.load(open("task.toml", "rb"))
    check(t["task"]["name"].endswith("/bore-form-acceptance"), "task name")
    check(t["artifacts"] == ["/app/output/form.csv"], "artifacts")
    check(t["agent"]["timeout_sec"] == 28800.0, "agent timeout must be 28800 s")
    check(t["agent"]["user"] == "agent", "the agent must not run as root")
    check(t["verifier"]["environment_mode"] == "separate", "the verifier must run in its own container")
    check(t["verifier.environment"]["network_mode"] if "verifier.environment" in t
          else t["verifier"]["environment"]["network_mode"] == "no-network", "the verifier must have no network")
    readme = open("README.md").read()
    for k in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
        check(t["metadata"][k].strip() in readme, "README is missing task.toml's %s" % k)

    print("%d checks" % PASSED[0])
    if FAILS:
        print("%d FAILED:" % len(FAILS))
        for m in FAILS:
            print("  FAIL  %s" % m)
        sys.exit(1)
    print("pre-flight clean: %d checks passed" % PASSED[0])


if __name__ == "__main__":
    main()
