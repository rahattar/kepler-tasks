#!/usr/bin/env python3
"""The brake laboratory (runs as the lab user; the agent reaches it only through the `friction` and `engage` wrappers).

    lab.py friction <T> [<lining>]           disc temperature T in C, 20 to 320; lining O1 (default) or O2
    lab.py engage <size> <setting> <AC|DC>   bench engagement time

Each test leaves one record file in STATE, created exclusively (O_EXCL, O_NOFOLLOW); the allowance is hbsim.BUDGET
tests of either kind and does not refill. A test's readings come from numpy's generator seeded with (seed, test
number, key), the key being the temperature and lining or the size, setting and switching, so the same test in the same
place of a plan always gives the same report. The laboratory refuses to run if its directories are not as installed.
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
USAGE = "usage: friction <T> [<lining>]   |   engage <size> <setting> <AC|DC>"


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
    import hbsim as S  # noqa: E402
    if not argv or argv[0] not in ("friction", "engage"):
        refuse(USAGE, 2)
    kind = argv[0]
    if kind == "friction":
        if len(argv) not in (2, 3) or not re.match(r"^[0-9]*\.?[0-9]+$", argv[1]):
            refuse("usage: friction <T> [<lining>]   (disc temperature in C, 20 to 320; lining O1 or O2, default O1)", 2)
        T = round(float(argv[1]), 1)
        lining = argv[2] if len(argv) == 3 else "O1"
        if lining not in ("O1", "O2"):
            refuse("lining must be O1 or O2", 2)
        if not (S.LAB_T[0] <= T <= S.LAB_T[1]):
            refuse("disc temperature must be between %g and %g C" % S.LAB_T, 2)
        key = [int(round(T * 10)), int(lining[1])]
    else:
        if len(argv) != 4 or argv[1] not in S.SIZES or not re.match(r"^\d{2,3}$", argv[2]) or argv[3] not in ("AC", "DC"):
            refuse("usage: engage <size> <setting> <AC|DC>   (size as in the catalogue, setting a whole percent 50 to 100)", 2)
        size, setting, sw = argv[1], int(argv[2]), argv[3]
        if not 50 <= setting <= 100:
            refuse("setting must be a whole percent from 50 to 100", 2)
        key = [1000 + list(S.SIZES).index(size), setting, 1 if sw == "AC" else 0]
    if not (check_dir(SEALED) and check_dir(STATE) and check_dir(REPORTS, 0o755)):
        refuse("laboratory not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["seed"]
    used = 0
    for name in os.listdir(STATE):
        if re.match(r"^test_\d{2}\.json$", name):
            if not stat.S_ISREG(os.lstat(os.path.join(STATE, name)).st_mode):
                refuse("laboratory records damaged; refusing")
            used += 1
    if used >= S.BUDGET:
        refuse("test allowance exhausted: %d of %d tests used" % (used, S.BUDGET))
    idx = used + 1
    rec = os.path.join(STATE, "test_%02d.json" % idx)
    try:
        fd = os.open(rec, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("laboratory busy; try again")
    rng = np.random.default_rng([seed, idx] + key)
    if kind == "friction":
        vals = S.lab_friction(T, rng, lining)
        head = "# test %d: friction, series SB organic lining %s, bedded-in specimen, disc at %.1f C" % (idx, lining, T)
        lines = [head, "reading,friction_coefficient"] + ["%d,%.4f" % (i + 1, v) for i, v in enumerate(vals)]
        name = "test_%02d_friction_%s_T%03d.csv" % (idx, lining, int(round(T)))
        info = {"test": idx, "kind": kind, "T": T, "lining": lining}
    else:
        vals = S.lab_engage(size, setting, sw, rng)
        head = "# test %d: engagement time, series SB size %s at %d %% setting, %s-side switching" % (idx, size, setting, sw)
        lines = [head, "engagement,time_ms"] + ["%d,%.1f" % (i + 1, v) for i, v in enumerate(vals)]
        name = "test_%02d_engage_%s_%d_%s.csv" % (idx, size, setting, sw)
        info = {"test": idx, "kind": kind, "size": size, "setting": setting, "sw": sw}
    with os.fdopen(fd, "w") as f:
        json.dump(info, f)
    text = "\n".join(lines) + "\n"
    path = os.path.join(REPORTS, name)
    with open(path, "w") as f:
        f.write(text)
    sys.stdout.write(text)
    print("# tests used %d of %d; report saved as %s" % (idx, S.BUDGET, path))


if __name__ == "__main__":
    main(sys.argv[1:])
