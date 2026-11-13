"""The whole verifier, as pytest, in a process of its own, on three programs.

    python3 verifier_run.py > verifier_run.txt

tests/test_indicate.py is run by `python -m pytest` from the tests folder, with the program given through
INDICATE_PROGRAM: the reference, the program that takes the records as the indicating system has them, and
the second solution at the limit. Exit status 0 means the one test passed.
"""
import os
import subprocess
import sys
import tempfile

import common
import variants


def plugin_installed():
    try:
        import pytest_jsonctrf  # noqa: F401
        return True
    except ImportError:
        return False


def pytest_on(path):
    """(pytest's exit status, whether the report it left counts one test, passed)."""
    with tempfile.TemporaryDirectory() as box:
        env = dict(os.environ, INDICATE_PROGRAM=path, INDICATE_NOTES=os.path.join(box, "cells.json"),
                   PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-m", "pytest", "test_indicate.py", "-q", "-p", "no:cacheprovider",
                   "--ctrf=%s" % os.path.join(box, "ctrf.json")]
        if not plugin_installed():
            env["PYTHONPATH"] = common.HERE + os.pathsep + env.get("PYTHONPATH", "")
            command[3:3] = ["-p", "ctrf_standin"]
        ran = subprocess.run(command, cwd=common.TESTS, env=env, capture_output=True, text=True)
        counted = subprocess.run([sys.executable, os.path.join(common.TESTS, "one_passed.py"),
                                  os.path.join(box, "ctrf.json")]).returncode == 0
    return ran.returncode, counted


def main():
    slow = common.SOLUTION.replace("solution/indicate.py", "authoring/evidence/slow_indicate.py")
    cases = [("the reference, solution/indicate.py", common.SOLUTION, 0),
             ("the records taken as the indicating system has them", common.program(variants.made(variants.ROUTES[0][2])), 1),
             ("the misfit put down to the index alone", common.program(variants.made(variants.ROUTES[1][2])), 1),
             ("the second solution, slow_indicate.py, at the limit", slow, 1)]
    ok = True
    print("tests/test_indicate.py run by `python -m pytest` from tests/, the program given through INDICATE_PROGRAM.")
    print("pytest-json-ctrf %s\n" % ("is installed: the report is the plugin's" if plugin_installed() else
          "is not installed on this machine: the report is written by authoring/evidence/ctrf_standin.py,\n"
          "which writes the same summary block"))
    for what, path, want in cases:
        status, counted = pytest_on(path)
        good = status == want and counted == (want == 0)
        ok = ok and good
        print("%-56s pytest exit status %d, report of one test passed: %s   %s" % (
            what, status, "yes" if counted else "no", "as expected" if good else "UNEXPECTED"))
    print("\n%d programs, %s" % (len(cases), "0 unexpected" if ok else "PROBLEM"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
