"""tests/test.sh as it stands, on three programs.

    python3 verifier_run.py > verifier_run.txt       (as root)

Each program in turn is left at /app/output/airflow.py and `bash tests/test.sh` is run: its umask, pytest, the
checker starting the program as nobody on the six districts, one_passed.py, the reward. Printed for each: what
/logs/verifier/reward.txt holds afterwards and what the checker found at each district.

tests/Dockerfile puts the verifier's `pqsurvey` at /usr/local/bin; this script does the same for the length
of its run where it is missing. Where the pytest-json-ctrf plugin is not installed, ctrf_stand_in.py writes
the report and the output says so.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import time

import common
import variants

DELIVERED = "/app/output/airflow.py"
REWARD = "/logs/verifier/reward.txt"
NOTES = "/logs/verifier/districts.json"
COMMAND = "/usr/local/bin/pqsurvey"


def main():
    if os.geteuid() != 0:
        print("not root: nothing run")
        return
    ours = os.path.join(common.TESTS, "crew", "pqsurvey")
    placed = not os.path.exists(COMMAND)
    if placed:
        shutil.copy(ours, COMMAND); os.chmod(COMMAND, 0o755)
    elif open(COMMAND).read() != open(ours).read():
        print("%s is another program: nothing run" % COMMAND)
        return
    env = dict(os.environ)
    plugin = importlib.util.find_spec("pytest_jsonctrf") is not None
    if not plugin:
        env["PYTHONPATH"] = common.HERE + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTEST_PLUGINS"] = "ctrf_stand_in"
    kept = None
    if os.path.exists(DELIVERED):
        kept = DELIVERED + ".kept"; os.rename(DELIVERED, kept)
    os.makedirs(os.path.dirname(DELIVERED), exist_ok=True)
    print("bash tests/test.sh with each program at %s; ctrf report by %s" % (
        DELIVERED, "pytest-json-ctrf" if plugin else "ctrf_stand_in.py (the plugin is not installed here)"))
    print()
    surprises = 0
    try:
        for what, program, want in (("the reference, solution/airflow.py", common.REFERENCE, "1"),
                                    ("variants.py worked_on: " + variants.SAYS["worked_on"], variants.build("worked_on"), "0"),
                                    ("the second solution, naive_airflow.py", common.SECOND, "0")):
            shutil.copy(program, DELIVERED)
            for left in (REWARD, NOTES):
                if os.path.exists(left):
                    os.unlink(left)
            clock = time.time()
            done = subprocess.run(["bash", os.path.join(common.TESTS, "test.sh")], env=env, capture_output=True, text=True)
            seconds = time.time() - clock
            try:
                reward = open(REWARD).read()
            except OSError:
                reward = "no reward file"
            print("%s" % what)
            print("  reward %s   (test.sh exit status %d, %.0f s)" % (reward, done.returncode, seconds))
            try:
                print(common.lines(json.load(open(NOTES)), "  "))
            except (OSError, ValueError):
                print("  no notes left by the checker")
            if reward != want or done.returncode != 0:
                surprises += 1
                print("  UNEXPECTED: wanted reward %s" % want)
            print()
    finally:
        if os.path.exists(DELIVERED):
            os.unlink(DELIVERED)
        if kept:
            os.rename(kept, DELIVERED)
        if placed:
            os.unlink(COMMAND)
    print("nothing unexpected" if not surprises else "UNEXPECTED: %d" % surprises)


if __name__ == "__main__":
    main()
