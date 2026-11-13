"""The whole pytest verifier, tests/test_program.py, on three programs, each in a process of its own.

    python3 verifier_run.py > verifier_run.txt

It is run where the install step of tests/Dockerfile has been done by hand: tests/lab/labsample copied to
/usr/local/bin/labsample. This script stops if the copy there is not that file.
"""
import filecmp
import os
import subprocess
import sys
import time

import common
import variants

NAIVE = os.path.join(common.HERE, "naive_bearing.py")


def main():
    installed = "/usr/local/bin/labsample"
    if not (os.path.exists(installed) and filecmp.cmp(installed, os.path.join(common.TESTS, "lab", "labsample"), False)):
        print("tests/lab/labsample is not installed at %s; nothing run" % installed)
        return 1
    register = variants.build("register")
    wrong = 0
    print("python -m pytest test_program.py -q -p no:cacheprovider, in tests/, BEARING_PROGRAM naming the program")
    print()
    for what, program, want in (("the reference, solution/bearing.py", common.REFERENCE, 0),
                                ("one sample for each listed system (variants.py, register)", register, 1),
                                ("the unoptimised second solution, naive_bearing.py", NAIVE, 1)):
        begun = time.time()
        done = subprocess.run([sys.executable, "-m", "pytest", "test_program.py", "-q", "-p", "no:cacheprovider"],
                              cwd=common.TESTS, env=dict(os.environ, BEARING_PROGRAM=program),
                              capture_output=True, text=True)
        last = [l for l in done.stdout.strip().splitlines() if l.strip()][-1]
        why = [l for l in done.stdout.splitlines() if l.startswith("E ") and " where " not in l
               and ("stopped: " in l or "points out of band" in l)]
        as_wanted = (done.returncode == 0) == (want == 0)
        wrong += not as_wanted
        print("%-62s pytest exit status %d in %3.0f s%s" % (what, done.returncode, time.time() - begun,
                                                            "" if as_wanted else "   UNEXPECTED"))
        for l in why[:8]:
            print("      " + l[1:].strip())
        print("      " + last.strip())
    os.unlink(register)
    print()
    print("3 programs, %d unexpected" % wrong)
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
