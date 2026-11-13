"""The verifier from end to end: `bash tests/test.sh` as it stands, on four programs, and the reward it leaves.

    python3 verifier_run.py > verifier_run.txt        as root

For each program the file is put at /app/output/indicate.py, tests/test.sh is run with nothing changed (its
umask, pytest, the checker starting the program as the user nobody, one_passed.py) and /logs/verifier/reward.txt
is read afterwards, with the checker's notes on each cell. This is the path the reward takes in the verifier's
image; a study that calls pytest or the checker directly does not go through test.sh's umask.

pytest has to be installed. Where the pytest-json-ctrf plugin is not, pytest is given ctrf_standin.py through
PYTEST_PLUGINS, and the first line printed says so. /app/output and /logs/verifier are made if they are not
there, and whatever this script made is removed at the end.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

import common
import variants

PLACE = "/app/output/indicate.py"
LOGS = "/logs/verifier"


def one(program):
    """(what reward.txt holds after test.sh, seconds, the checker's notes or None)."""
    shutil.copyfile(program, PLACE)
    os.chmod(PLACE, 0o644)
    env = dict(os.environ)
    if importlib.util.find_spec("pytest_jsonctrf") is None:
        env["PYTEST_PLUGINS"] = "ctrf_standin"
        env["PYTHONPATH"] = common.HERE + os.pathsep + env.get("PYTHONPATH", "")
    began = time.time()
    subprocess.run(["bash", os.path.join(common.TESTS, "test.sh")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    took = time.time() - began
    try:
        with open(os.path.join(LOGS, "reward.txt")) as handle:
            reward = handle.read()
    except OSError:
        reward = "none written"
    try:
        with open(os.path.join(LOGS, "cells.json")) as handle:
            notes = json.load(handle)
    except (OSError, ValueError):
        notes = None
    return reward, took, notes


def main():
    if os.geteuid() != 0:
        print("this study has to be run as root, as test.sh is; nothing was run")
        return 1
    made = [d for d in ("/app", "/logs") if not os.path.exists(d)]
    os.makedirs(os.path.dirname(PLACE), exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    slow = os.path.join(common.HERE, "slow_indicate.py")
    programs = [("the reference, solution/indicate.py", common.SOLUTION, "1"),
                ("the records taken as the indicating system has them", common.program(variants.made(variants.ROUTES[0][2])), "0"),
                ("the misfit put down to the index alone", common.program(variants.made(variants.ROUTES[1][2])), "0"),
                ("the second solution, slow_indicate.py", slow, "0")]
    plugin = importlib.util.find_spec("pytest_jsonctrf") is not None
    print("bash tests/test.sh, unchanged, with each program in turn at %s; reward read from %s/reward.txt" % (PLACE, LOGS))
    print("the ctrf report is written by %s" % ("pytest-json-ctrf" if plugin else
          "authoring/evidence/ctrf_standin.py: pytest-json-ctrf is not installed on this machine"))
    unexpected = 0
    try:
        for what, path, want in programs:
            reward, took, notes = one(path)
            unexpected += reward != want
            print("\n%-52s reward %s in %.0f s   %s" % (what, reward, took, "as expected" if reward == want else "UNEXPECTED"))
            if notes is None:
                print("    the checker left no notes")
            else:
                for line in common.check_program.account(notes).splitlines():
                    print("    " + line)
    finally:
        for left in (PLACE, os.path.join(LOGS, "reward.txt"), os.path.join(LOGS, "ctrf.json"), os.path.join(LOGS, "cells.json")):
            if os.path.exists(left):
                os.unlink(left)
        for d in made:
            shutil.rmtree(d, ignore_errors=True)
    print("\n%d programs, %s" % (len(programs), "0 unexpected" if not unexpected else "PROBLEM"))
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
