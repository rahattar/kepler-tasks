#!/usr/bin/env python3
"""The materials laboratory (runs as the lab user; the agent reaches it only through the `cte` wrapper).

    lab.py cte <material> <T>

reports the mean expansion coefficient of the material from 20 C to T, from a dilatometer. Each test leaves one
record file in STATE, created exclusively (O_EXCL, O_NOFOLLOW); the allowance is isim.BUDGET tests and does not
refill. A reading comes from numpy's generator seeded with (seed, test number, the test's arguments), so the same test
in the same place of a plan always gives the same report. The laboratory refuses to run if its directories are not as
installed.
"""
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True
LAB = os.environ.get("LAB_DIR", "/opt/lab")          # the overrides are for local testing; sudo resets the environment
SEALED = os.path.join(LAB, "sealed")
STATE = os.path.join(LAB, "state")
REPORTS = os.environ.get("REPORT_DIR", "/app/lab_reports")


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
    import isim as S  # noqa: E402
    import numpy as np  # noqa: E402
    usage = "usage: cte <material> <T>   (materials: %s; T a whole degree C, %d to %d)" % (
        ", ".join(S.LABMAT), S.LAB_T[0], S.LAB_T[1])
    if len(argv) != 3 or argv[0] != "cte" or argv[1] not in S.LABMAT or not re.match(r"^\d{3}$", argv[2]):
        refuse(usage, 2)
    mat, T = argv[1], int(argv[2])
    if not S.LAB_T[0] <= T <= S.LAB_T[1]:
        refuse(usage, 2)
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
    rng = np.random.default_rng([seed, idx, 2, list(S.LABMAT).index(mat), T])
    v = S.lab_cte(S.LABMAT[mat], T, rng)
    text = "# test %d: dilatometer, %s, mean coefficient of expansion from 20 C to %d C\nexpansion_um_per_m_K,%.2f\n" % (
        idx, mat, T, v)
    name = "test_%02d_cte_%s_%d.csv" % (idx, mat, T)
    with os.fdopen(fd, "w") as f:
        json.dump({"test": idx, "argv": argv, "value": v}, f)
    rfd = os.open(os.path.join(REPORTS, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(rfd, "w") as f:
        f.write(text)
    sys.stdout.write(text)
    print("# tests used %d of %d; report saved as %s" % (idx, S.BUDGET, os.path.join(REPORTS, name)))


if __name__ == "__main__":
    main(sys.argv[1:])
