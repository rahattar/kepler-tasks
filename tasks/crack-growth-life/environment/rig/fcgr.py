#!/usr/bin/env python3
"""The materials laboratory. Runs as the user `lab` (the agent reaches it only through `fcgr`, a sudo wrapper).

    fcgr paris <R> [<heat>]        constant-amplitude test at load ratio R                           (1 slot)
    fcgr threshold <R> [<heat>]    K-decreasing test at load ratio R, down to the threshold            (3 slots)

R is Kmin/Kmax, 0.05 to 0.90; heat is one of the flange plate heats H1 to H4 (default H1). The dK range of each test
is fcgsim.lab's: a Paris test ends at min(45, 75 (1 - R)) MPa sqrt(m), a threshold test starts at min(14, 75 (1 - R)). The report (dK in MPa sqrt(m), da/dN in m/cycle) is printed and saved under REPORTS.
The allowance is BUDGET slots in all and does not refill: every slot used leaves one record file in STATE, created
exclusively, and the count of records is the count of slots used. The laboratory refuses to run if its directories
are not exactly as installed (fail closed).
"""
import json
import os
import re
import stat
import sys

import numpy as np

sys.dont_write_bytecode = True     # never leave a __pycache__ in the sealed directory

LAB = os.environ.get("LAB_DIR", "/opt/lab")          # the overrides are for local testing; sudo resets the environment
SEALED = os.path.join(LAB, "sealed")
STATE = os.path.join(LAB, "state")
REPORTS = os.environ.get("REPORT_DIR", "/app/lab_reports")
BUDGET = 5
COST = {"paris": 1, "threshold": 3}
USAGE = "usage: fcgr paris <R> [<heat>] | fcgr threshold <R> [<heat>]   (R = Kmin/Kmax, 0.05 to 0.90; heat H1 to H4, default H1)"


def refuse(msg, code=1):
    print(msg)
    sys.exit(code)


def check_dir(path, mode=0o700):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and (st.st_mode & 0o777) == mode


def slots_used():
    n = 0
    for name in os.listdir(STATE):
        if re.match(r"^slot_\d{2}\.json$", name):
            if not stat.S_ISREG(os.lstat(os.path.join(STATE, name)).st_mode):
                refuse("laboratory records damaged; refusing")
            n += 1
    return n


def main(argv):
    if len(argv) not in (2, 3) or argv[0] not in COST:
        refuse(USAGE, 2)
    kind = argv[0]
    heat = argv[2] if len(argv) == 3 else "H1"
    if not re.match(r"^H[1-4]$", heat):
        refuse("heat must be one of H1, H2, H3, H4", 2)
    if not re.match(r"^[0-9]*\.?[0-9]+$", argv[1]):
        refuse("R must be a number between 0.05 and 0.90", 2)
    R = round(float(argv[1]), 3)
    if not (0.05 <= R <= 0.90):
        refuse("R must be between 0.05 and 0.90", 2)
    if not (check_dir(SEALED) and check_dir(STATE) and check_dir(REPORTS, 0o755)):
        refuse("laboratory not available (state check failed)")
    sys.path.insert(0, SEALED)
    import fcgsim as F  # noqa: E402
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["seed"]
    used = slots_used()
    cost = COST[kind]
    if used + cost > BUDGET:
        refuse("test allowance exhausted: %d of %d slots used, a %s test needs %d" % (used, BUDGET, kind, cost))
    idx = used + 1
    fds = []
    for k in range(cost):
        rec = os.path.join(STATE, "slot_%02d.json" % (idx + k))
        try:
            fds.append((rec, os.open(rec, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)))
        except FileExistsError:
            for path, fd in fds:
                os.close(fd)
                os.unlink(path)
            refuse("laboratory busy; try again")
    # scatter fixed by the slot index and R, so that a rerun of the same campaign repeats
    rng = np.random.default_rng([seed, idx, int(round(R * 1000)), int(heat[1])])
    dK, r = F.lab(kind, R, rng, heat)
    order = np.argsort(-dK) if kind == "threshold" else np.argsort(dK)
    dK, r = dK[order], r[order]
    lines = ["# ASTM E647 %s test, CT specimen from flange plate heat %s (stress relieved), laboratory air, R = %.3f"
             % ("constant-amplitude" if kind == "paris" else "K-decreasing threshold", heat, R),
             "dK_MPa_sqrt_m,da_dN_m_per_cycle"]
    lines += ["%.3f,%.4e" % (k, v) for k, v in zip(dK, r)]
    if kind == "threshold":
        lr, lk = np.log10(r[::-1]), np.log10(dK[::-1])
        th = 10 ** float(np.interp(-10.0, lr, lk)) if lr.min() <= -10.0 <= lr.max() else float(dK.min())
        lines.append("# threshold dK_th at 1e-10 m/cycle: %.2f MPa sqrt(m)" % th)
    text = "\n".join(lines) + "\n"
    with os.fdopen(fds[0][1], "w") as f:
        json.dump({"slot": idx, "kind": kind, "R": R, "heat": heat}, f)
    for k, (path, fd) in enumerate(fds[1:], start=1):
        with os.fdopen(fd, "w") as f:
            json.dump({"slot": idx + k, "slot_of": idx}, f)
    name = os.path.join(REPORTS, "test_%02d_%s_R%.2f_%s.csv" % (idx, kind, R, heat))
    with open(name, "w") as f:
        f.write(text)
    sys.stdout.write(text)
    print("# slots used %d of %d; report saved as %s" % (idx + cost - 1, BUDGET, name))


if __name__ == "__main__":
    main(sys.argv[1:])
