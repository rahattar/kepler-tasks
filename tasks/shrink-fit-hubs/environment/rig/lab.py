#!/usr/bin/env python3
"""The joint laboratory (runs as the lab user; the agent reaches it only through the `slip` and `cte` wrappers).

    lab.py slip <material> <dry|oiled|paste> <pressure_MPa> [shrink]
    lab.py cte <material> <T>

`slip` makes a 40 mm specimen joint of a hub of the material on a steel shaft at the contact pressure given, pressed
together or (with `shrink`) shrink-fitted, and reports the friction coefficient at slip; `cte` reports the mean
expansion coefficient of the material from 20 C to T. Each test leaves one record file in STATE, created exclusively
(O_EXCL, O_NOFOLLOW); the allowance is sfsim.BUDGET tests and does not refill. A reading comes from numpy's generator
seeded with (seed, test number, the test's arguments), so the same test in the same place of a plan always gives the
same report. The laboratory refuses to run if its directories are not as installed.
"""
import json
import os
import re
import stat
import sys

import numpy as np

sys.dont_write_bytecode = True
LAB = os.environ.get("LAB_DIR", "/opt/lab")          # the overrides are for local testing; sudo resets the environment
SEALED = os.path.join(LAB, "sealed")
STATE = os.path.join(LAB, "state")
REPORTS = os.environ.get("REPORT_DIR", "/app/lab_reports")
USAGE = "usage: slip <material> <dry|oiled|paste> <pressure_MPa> [shrink]   |   cte <material> <T>"
CONDS = ("dry", "oiled", "paste")


def refuse(msg, code=1):
    print(msg)
    sys.exit(code)


def check_dir(path, mode=0o700):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and (st.st_mode & 0o777) == mode


def main(argv):
    sys.path.insert(0, SEALED)
    import sfsim as S  # noqa: E402
    if not argv or argv[0] not in ("slip", "cte"):
        refuse(USAGE, 2)
    kind, a = argv[0], list(argv[1:])
    mats = ", ".join(S.LABMAT)
    if kind == "slip":
        shrink = bool(a) and a[-1] == "shrink"
        if shrink:
            a = a[:-1]
        if len(a) != 3 or a[0] not in S.LABMAT or a[1] not in CONDS or not re.match(r"^\d{2,3}$", a[2]):
            refuse(USAGE + "   (materials: %s; pressure a whole MPa)" % mats, 2)
        p = int(a[2])
        if not S.LAB_P[0] <= p <= S.LAB_P[1]:
            refuse("pressure must be %d to %d MPa" % S.LAB_P, 2)
        key = [1, list(S.LABMAT).index(a[0]), CONDS.index(a[1]), p, int(shrink)]
    else:
        if len(a) != 2 or a[0] not in S.LABMAT or not re.match(r"^\d{3}$", a[1]):
            refuse(USAGE + "   (materials: %s; T a whole degree C)" % mats, 2)
        T = int(a[1])
        if not S.LAB_T[0] <= T <= S.LAB_T[1]:
            refuse("temperature must be %d to %d C" % S.LAB_T, 2)
        key = [2, list(S.LABMAT).index(a[0]), T]
    if not (check_dir(SEALED) and check_dir(STATE) and check_dir(REPORTS, 0o755)):
        refuse("laboratory not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["seed"]
    done = 0
    for name in os.listdir(STATE):
        if re.match(r"^test_\d{2}\.json$", name):
            if not stat.S_ISREG(os.lstat(os.path.join(STATE, name)).st_mode):
                refuse("laboratory records damaged; refusing")
            done += 1
    if done >= S.BUDGET:
        refuse("test allowance used: %d of %d tests" % (done, S.BUDGET))
    idx = done + 1
    try:
        fd = os.open(os.path.join(STATE, "test_%02d.json" % idx), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("laboratory busy; try again")
    rng = np.random.default_rng([seed, idx] + key)
    if kind == "slip":
        v = S.lab_slip(S.LABMAT[a[0]], a[1], p, shrink, rng)
        text = ("# test %d: slip test, %s hub on steel shaft, %s, contact pressure %d MPa, %s\n"
                "friction_coefficient,%.3f\n" % (idx, a[0], a[1], p,
                                                  "assembled by heating the hub (shrink)" if shrink else "pressed together", v))
        name = "test_%02d_slip_%s_%s_%d%s.csv" % (idx, a[0], a[1], p, "_shrink" if shrink else "")
    else:
        v = S.lab_cte(S.LABMAT[a[0]], T, rng)
        text = ("# test %d: dilatometer, %s, mean coefficient of expansion from 20 C to %d C\n"
                "expansion_um_per_m_K,%.2f\n" % (idx, a[0], T, v))
        name = "test_%02d_cte_%s_%d.csv" % (idx, a[0], T)
    with os.fdopen(fd, "w") as f:
        json.dump({"test": idx, "argv": argv, "value": v}, f)
    rfd = os.open(os.path.join(REPORTS, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(rfd, "w") as f:
        f.write(text)
    sys.stdout.write(text)
    print("# tests used %d of %d; report saved as %s" % (idx, S.BUDGET, os.path.join(REPORTS, name)))


if __name__ == "__main__":
    main(sys.argv[1:])
