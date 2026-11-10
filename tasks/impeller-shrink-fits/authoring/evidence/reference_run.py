"""Runs solution/solve.py against the real laboratory program (environment/rig/lab.py, with the shipped seed, in a
temporary copy of the agent's directories) and grades the result with tests/grade_bores.py.

    python3 authoring/evidence/reference_run.py > authoring/evidence/reference_run.txt
"""
import os
import shutil
import subprocess
import sys
import tempfile

import common as C

ROOT = C.ROOT


def main():
    tmp = tempfile.mkdtemp()
    try:
        rig, app, bin_ = os.path.join(tmp, "rig"), os.path.join(tmp, "app"), os.path.join(tmp, "bin")
        os.makedirs(os.path.join(rig, "state"))
        shutil.copytree(os.path.join(ROOT, "environment", "rig", "sealed"), os.path.join(rig, "sealed"))
        shutil.copy(os.path.join(ROOT, "environment", "rig", "lab.py"), rig)
        os.makedirs(os.path.join(app, "lab_reports"))
        os.makedirs(os.path.join(app, "output"))
        os.makedirs(bin_)
        os.chmod(os.path.join(rig, "sealed"), 0o700)
        os.chmod(os.path.join(rig, "state"), 0o700)
        os.chmod(os.path.join(app, "lab_reports"), 0o755)
        p = os.path.join(bin_, "cte")
        with open(p, "w") as f:
            f.write('#!/bin/bash\nLAB_DIR=%s REPORT_DIR=%s exec %s -B %s cte "$@"\n' % (
                rig, os.path.join(app, "lab_reports"), sys.executable, os.path.join(rig, "lab.py")))
        os.chmod(p, 0o755)
        env = dict(os.environ, PATH=bin_ + os.pathsep + os.environ["PATH"])
        out = os.path.join(app, "output", "bore_sheet.csv")
        r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "solution", "solve.py"), C.DATA, out],
                           env=env, capture_output=True, text=True, check=True)
        print("solution/solve.py output:")
        print(r.stdout)
        print("laboratory reports:")
        for name in sorted(os.listdir(os.path.join(app, "lab_reports"))):
            print("  " + open(os.path.join(app, "lab_reports", name)).read().replace("\n", " | ").strip(" |"))
        print()
        print("tests/grade_bores.py:")
        g = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "tests", "grade_bores.py"), out], capture_output=True,
                           text=True, check=True)
        print(g.stdout)
        print("bore_sheet.csv:")
        print(open(out).read())
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
