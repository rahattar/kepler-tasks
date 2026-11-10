#!/usr/bin/env python3
"""The metallurgical laboratory (runs as the lab user; the agent reaches it only through the `temper` wrapper).

    lab.py temper <heat> <T> [<diameter_mm> <surface|half-radius>] [double]

hardens a test piece of the heat as production does, tempers it once (or, with `double`, twice) for 2 h at T, and
reports the hardness at the location. Each test leaves one record file in STATE, created exclusively (O_EXCL,
O_NOFOLLOW) and holding the number of tempers it used; the allowance is tsim.BUDGET tempers and does not refill. A
test's reading comes from numpy's generator seeded with (seed, test number, heat, T, diameter, location, tempers), so
the same test in the same place of a plan always gives the same report. The laboratory refuses to run if its
directories are not as installed.
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
USAGE = "usage: temper <heat> <T> [<diameter_mm> <surface|half-radius>] [double]"


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
    import tsim as S  # noqa: E402
    if not argv or argv[0] != "temper":
        refuse(USAGE, 2)
    args = argv[1:]
    n = 1
    if args and args[-1] == "double":
        n, args = 2, args[:-1]
    if len(args) not in (2, 4) or args[0] not in S.HEATS or not re.match(r"^\d{3}$", args[1]):
        refuse(USAGE + "   (heat as on the mill certificates, T a whole degree C)", 2)
    heat, T = args[0], int(args[1])
    if not S.LAB_T[0] <= T <= S.LAB_T[1]:
        refuse("temperature must be %d to %d C" % S.LAB_T, 2)
    D, loc = 25.0, "half-radius"
    if len(args) == 4:
        if not re.match(r"^\d{2,3}$", args[2]) or args[3] not in ("surface", "half-radius"):
            refuse(USAGE, 2)
        D, loc = float(args[2]), args[3]
        if not S.LAB_D[0] <= D <= S.LAB_D[1]:
            refuse("diameter must be %d to %d mm" % S.LAB_D, 2)
    if not (check_dir(SEALED) and check_dir(STATE) and check_dir(REPORTS, 0o755)):
        refuse("laboratory not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["seed"]
    done, used = 0, 0
    for name in os.listdir(STATE):
        if re.match(r"^test_\d{2}\.json$", name):
            p = os.path.join(STATE, name)
            if not stat.S_ISREG(os.lstat(p).st_mode):
                refuse("laboratory records damaged; refusing")
            try:
                used += int(json.load(open(p)).get("tempers", 1))
            except (ValueError, OSError):
                refuse("laboratory records damaged; refusing")
            done += 1
    if used + n > S.BUDGET:
        refuse("temper allowance: %d of %d tempers used; this test needs %d" % (used, S.BUDGET, n))
    idx = done + 1
    try:
        fd = os.open(os.path.join(STATE, "test_%02d.json" % idx), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("laboratory busy; try again")
    rng = np.random.default_rng([seed, idx, list(S.HEATS).index(heat), T, int(D), 0 if loc == "surface" else 1, n])
    h = S.lab_temper(heat, T, rng, D, loc, n)
    with os.fdopen(fd, "w") as f:
        json.dump({"test": idx, "heat": heat, "T": T, "D": D, "loc": loc, "tempers": n, "HRC": h}, f)
    how = "tempered once 2 h" if n == 1 else "tempered twice 2 h (cooled to room temperature between)"
    text = ("# test %d: heat %s, %.0f mm round hardened as production, %s at %d C, hardness at %s\n"
            "hardness_HRC,%.1f\n" % (idx, heat, D, how, T, loc, h))
    name = "test_%02d_%s_%d_%d_%s%s.csv" % (idx, heat, T, int(D), loc, "_double" if n == 2 else "")
    rfd = os.open(os.path.join(REPORTS, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(rfd, "w") as f:
        f.write(text)
    sys.stdout.write(text)
    print("# tempers used %d of %d; report saved as %s" % (used + n, S.BUDGET, os.path.join(REPORTS, name)))


if __name__ == "__main__":
    main(sys.argv[1:])
