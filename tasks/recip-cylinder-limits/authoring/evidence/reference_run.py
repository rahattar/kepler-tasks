"""Runs solution/solve.py against the real laboratory program (environment/rig/lab.py, with the shipped seed, in a
temporary copy of the agent's directories) and grades the result with tests/grade_limits.py.

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
        for cmd in ("gc", "weigh"):
            p = os.path.join(bin_, cmd)
            with open(p, "w") as f:
                f.write('#!/bin/bash\nLAB_DIR=%s REPORT_DIR=%s exec %s -B %s %s "$@"\n' % (
                    rig, os.path.join(app, "lab_reports"), sys.executable, os.path.join(rig, "lab.py"), cmd))
            os.chmod(p, 0o755)
        env = dict(os.environ, PATH=bin_ + os.pathsep + os.environ["PATH"])
        out = os.path.join(app, "output", "cylinder_limits.csv")
        r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "solution", "solve.py"), C.DATA, out],
                           env=env, capture_output=True, text=True, check=True)
        print("solution/solve.py output:")
        print(r.stdout)
        print("the reports the services wrote:")
        for name in sorted(os.listdir(os.path.join(app, "lab_reports"))):
            print("  " + open(os.path.join(app, "lab_reports", name)).read().replace("\n", " | ").strip(" |"))
        print()
        print("a third reading, over the allowance:")
        q = subprocess.run([os.path.join(bin_, "gc"), "1"], env=env, capture_output=True, text=True)
        print("  exit %d: %s" % (q.returncode, q.stdout.strip()))
        print()
        print("a reading of something that does not exist:")
        q = subprocess.run([os.path.join(bin_, "weigh"), "4C"], env=env, capture_output=True, text=True)
        print("  exit %d: %s" % (q.returncode, q.stdout.strip().replace("\n", " | ")))
        print()
        print("tests/grade_limits.py:")
        g = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "tests", "grade_limits.py"), out],
                           capture_output=True, text=True, check=True)
        print(g.stdout)
        print("cylinder_limits.csv:")
        print(open(out).read())
        print("the sealed definition, for the record:")
        for cid in C.IDS:
            p, q2 = C.S.ps_min(cid)
            print("  %-3s %8.2f bar  %s" % (cid, p, q2))
        print()
        print("its constants: tolerance %.3f relative, resolution %.2f bar, allowance %d readings, valve losses "
              "%.2f and %.2f bar," % (C.S.TOL, C.S.PS_STEP, C.S.BUDGET, C.S.DPS, C.S.DPD))
        print("least reversal %d degrees, bottle correction %.1f K, allowable discharge temperature %.1f C" % (
            C.S.REV_MIN, C.S.BOTTLE_OFFSET, C.S.TD_LIMIT))
        print()
        print("the gas of each stage, as the records and the laboratory report it:")
        for st in (1, 2, 3):
            a = C.S.analysis(st)
            print("  stage %d  %s" % (st, " ".join("%s %.2f" % (c[:4], a[c]) for c in C.S.COMPONENTS)))
        print()
        print("the exponent and the discharge temperature of each cylinder at its lowest allowable pressure, which"
              " the standard's iteration settles together:")
        for cid in C.IDS:
            p0 = C.S.ps_min(cid)[0]
            k, td = C.S.kappa_td(p0, C.S.CYL[cid])
            print("  %-3s k %.4f  suction %5.1f C  discharge %6.1f C" % (
                cid, k, C.S.suction_t(C.S.CYL[cid]), td))
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
