"""verifier_run.py: tests/test.sh itself, as the verifier's image runs it, on three programs. Writes verifier_run.txt.

    python3 authoring/evidence/verifier_run.py          (as root)

Each program in turn is put at /app/output/lines.py and `bash tests/test.sh` is run as it stands: its umask
077, pytest on test_lines.py, rerun.py starting the program as nobody on the six sites, tally.py, the reward.
Written down for each: what /logs/verifier/reward.txt holds afterwards, and what rerun.py found at each site.

tests/Dockerfile installs the verifier's heatsurvey at /usr/local/bin; this study does the same for the length
of its run where nothing is there. Where the pytest-json-ctrf plugin is not installed, ctrf_standin.py writes
the report, and the output says so.
"""
import importlib.util
import json
import os
import shutil
import subprocess

import common
import variants

DELIVERED = "/app/output/lines.py"
REWARD = "/logs/verifier/reward.txt"
NOTES = "/logs/verifier/sites.json"
COMMAND = "/usr/local/bin/heatsurvey"

out = common.Sheet(__file__)
if os.geteuid() != 0:
    out.say("not root: nothing run")
    out.close()
    raise SystemExit(0)
ours = os.path.join(common.TESTS, "crew", "heatsurvey")
installed_here = not os.path.exists(COMMAND)
if installed_here:
    shutil.copy(ours, COMMAND)
    os.chmod(COMMAND, 0o755)
elif open(COMMAND).read() != open(ours).read():
    out.say("%s is some other program: nothing run" % COMMAND)
    out.close()
    raise SystemExit(1)
env = dict(os.environ)
plugin = importlib.util.find_spec("pytest_jsonctrf") is not None
if not plugin:
    env["PYTHONPATH"] = common.EVIDENCE + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTEST_PLUGINS"] = "ctrf_standin"
kept = None
if os.path.lexists(DELIVERED):
    kept = DELIVERED + ".kept"
    os.rename(DELIVERED, kept)
os.makedirs(os.path.dirname(DELIVERED), exist_ok=True)
out.say("bash tests/test.sh with each program at %s; the ctrf report written by %s" % (
    DELIVERED, "pytest-json-ctrf" if plugin else "ctrf_standin.py, the plugin not being installed here"))
problems = 0
try:
    for what, program, want in (("the reference, solution/lines.py", common.REFERENCE, "1"),
                                ("variants.py covering_jobs_only: " + variants.EVERY["covering_jobs_only"][0],
                                 common.written(variants.make("covering_jobs_only"), "lines.py"), "0"),
                                ("the second solution as first written, plain_lines.py", common.PLAIN, "0")):
        shutil.copy(program, DELIVERED)
        os.chmod(DELIVERED, 0o644)
        for left in (REWARD, NOTES):
            if os.path.exists(left):
                os.unlink(left)
        done = subprocess.run(["bash", os.path.join(common.TESTS, "test.sh")], env=env, capture_output=True, text=True)
        got = open(REWARD).read() if os.path.exists(REWARD) else "(no reward file)"
        out.say()
        out.say("%s: reward %s (expected %s)%s" % (what, got, want, "" if got == want else "  UNEXPECTED"))
        problems += got != want
        if os.path.exists(NOTES):
            with open(NOTES) as handle:
                verdict = json.load(handle)
            for line in common.rerun.account(verdict).splitlines():
                out.say("  " + line)
        for line in done.stderr.strip().splitlines():
            if line.startswith("test.sh:"):
                out.say("  " + line)
finally:
    if os.path.lexists(DELIVERED):
        os.unlink(DELIVERED)
    if kept:
        os.rename(kept, DELIVERED)
    if installed_here:
        os.unlink(COMMAND)
out.say()
out.say("bash tests/test.sh: reward 1 for the reference and 0 for the other two; %d UNEXPECTED" % problems)
out.close()
