"""The verifier end to end: tests/test.sh itself, with nothing changed, on five programs.

    python3 verifier_run.py > verifier_run.txt        as root

Each program in turn is put at /app/output/ropes.py; `bash tests/test.sh` is run as it stands (its umask, pytest
on test_ropes.py, the bench starting the program as nobody, tally.py); then /logs/verifier/reward.txt is read,
and the bench's notes from /logs/verifier/trials.json. This is the way the reward comes about in the verifier's
image, which a study that calls the bench directly does not go through.

pytest must be installed. Without the pytest-json-ctrf plugin, ctrf_standin.py writes the report, and the
output says so. /app/output and /logs/verifier are made if missing, and removed again if this script made them.
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

DELIVERED = "/app/output/ropes.py"
LOGS = "/logs/verifier"


def reward_for(program):
    shutil.copyfile(program, DELIVERED)
    os.chmod(DELIVERED, 0o644)
    env = dict(os.environ)
    if importlib.util.find_spec("pytest_jsonctrf") is None:
        env["PYTEST_PLUGINS"] = "ctrf_standin"
        env["PYTHONPATH"] = common.EVIDENCE + os.pathsep + env.get("PYTHONPATH", "")
    start = time.time()
    subprocess.run(["bash", os.path.join(common.TESTS, "test.sh")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    seconds = time.time() - start
    try:
        with open(os.path.join(LOGS, "reward.txt")) as handle:
            reward = handle.read()
    except OSError:
        reward = "no reward file"
    try:
        with open(os.path.join(LOGS, "trials.json")) as handle:
            notes = json.load(handle)
    except (OSError, ValueError):
        notes = None
    return reward, seconds, notes


def main():
    if os.geteuid() != 0:
        print("this study is run as root, as test.sh is; nothing was run")
        return 1
    made = [d for d in ("/app", "/logs") if not os.path.exists(d)]
    os.makedirs(os.path.dirname(DELIVERED), exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)
    route = {name: changes for name, _, changes in variants.ROUTES}
    programs = [
        ("the reference, solution/ropes.py", common.REFERENCE, "1"),
        ("the second solution made fast, quick_ropes.py", os.path.join(common.EVIDENCE, "quick_ropes.py"), "1"),
        ("RS-4 on the surveys as written", variants.make(route["as_written"]), "0"),
        ("every mirrored survey taken for a turned rope", variants.make(route["all_turns"]), "0"),
        ("the second solution in plain loops, plain_ropes.py", os.path.join(common.EVIDENCE, "plain_ropes.py"), "0"),
    ]
    print("bash tests/test.sh, unchanged, with each program in turn at %s; the reward read from %s/reward.txt" % (DELIVERED, LOGS))
    print("the ctrf report is written by %s\n" % ("pytest-json-ctrf" if importlib.util.find_spec("pytest_jsonctrf")
                                                 else "authoring/evidence/ctrf_standin.py: pytest-json-ctrf is not installed on this machine"))
    unexpected = 0
    try:
        for label, program, expect in programs:
            reward, seconds, notes = reward_for(program)
            good = reward == expect
            unexpected += not good
            print("%-52s reward %s in %.0f s   %s" % (label, reward, seconds, "as expected" if good else "UNEXPECTED"))
            print(common.indent(common.rope_bench.account(notes)) if notes else "    no notes were left")
            print()
            sys.stdout.flush()
    finally:
        if os.path.exists(DELIVERED):
            os.remove(DELIVERED)
        for folder in made:
            shutil.rmtree(folder, ignore_errors=True)
    print("%d programs, %d unexpected" % (len(programs), unexpected))
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
