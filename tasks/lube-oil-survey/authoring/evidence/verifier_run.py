"""The whole verifier, tests/test.sh itself, on three programs.

    python3 verifier_run.py > verifier_run.txt        (as root, on a machine set up as tests/Dockerfile sets one up)

Each program in turn is put at /app/output/bearing.py and `bash tests/test.sh` is run as it stands: its umask,
pytest, the checker running the program as nobody, read_report.py, the reward. What is printed is the reward
file's content and the checker's findings for each site.

Two things tests/Dockerfile does have to have been done by hand where this is run: tests/lab/labsample copied
to /usr/local/bin/labsample, and pytest installed. Where the pytest-json-ctrf plugin is missing, ctrf_standin.py
writes the report in its place; this script says which was used.
"""
import filecmp
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

import common
import variants

NAIVE = os.path.join(common.HERE, "naive_bearing.py")
DELIVERED = "/app/output/bearing.py"
REWARD = "/logs/verifier/reward.txt"
FINDINGS = "/logs/verifier/sites.json"


def main():
    installed = "/usr/local/bin/labsample"
    if os.geteuid() != 0:
        print("not root; nothing run")
        return 1
    if not (os.path.exists(installed) and filecmp.cmp(installed, os.path.join(common.TESTS, "lab", "labsample"), False)):
        print("tests/lab/labsample is not installed at %s; nothing run" % installed)
        return 1
    surroundings = dict(os.environ)
    real = importlib.util.find_spec("pytest_jsonctrf") is not None
    if not real:
        surroundings["PYTHONPATH"] = common.HERE + os.pathsep + surroundings.get("PYTHONPATH", "")
        surroundings["PYTEST_PLUGINS"] = "ctrf_standin"
    register = variants.build("register")
    kept = None
    if os.path.exists(DELIVERED):
        kept = DELIVERED + ".kept"
        os.rename(DELIVERED, kept)
    os.makedirs(os.path.dirname(DELIVERED), exist_ok=True)
    wrong = 0
    print("bash tests/test.sh, the program under test at %s; the ctrf report written by %s" % (
        DELIVERED, "pytest-json-ctrf" if real else "ctrf_standin.py, the plugin not being installed here"))
    print()
    try:
        for what, program, want in (("the reference, solution/bearing.py", common.REFERENCE, "1"),
                                    ("one sample for each listed system (variants.py, register)", register, "0"),
                                    ("the unoptimised second solution, naive_bearing.py", NAIVE, "0")):
            shutil.copy(program, DELIVERED)
            for left in (REWARD, FINDINGS):
                if os.path.exists(left):
                    os.unlink(left)
            begun = time.time()
            subprocess.run(["bash", os.path.join(common.TESTS, "test.sh")], env=surroundings, capture_output=True)
            took = time.time() - begun
            try:
                with open(REWARD) as handle:
                    reward = handle.read()
            except OSError:
                reward = "no file"
            wrong += reward != want
            print("%-62s reward %s in %3.0f s%s" % (what, reward, took, "" if reward == want else "   UNEXPECTED"))
            try:
                with open(FINDINGS) as handle:
                    found = json.load(handle)
                for name, entry in found["sites"].items():
                    print("      " + common.line(name, entry))
                if found["stopped"]:
                    print("      stopped: " + found["stopped"])
            except (OSError, ValueError):
                print("      no findings were left")
    finally:
        os.unlink(register)
        os.unlink(DELIVERED)
        if kept:
            os.rename(kept, DELIVERED)
        for left in (REWARD, FINDINGS, "/logs/verifier/ctrf.json"):
            if os.path.exists(left):
                os.unlink(left)
    print()
    print("3 programs, %d unexpected" % wrong)
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
