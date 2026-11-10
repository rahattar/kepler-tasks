#!/usr/bin/env python3
"""The tightening rig. Runs as the user `rig` (the agent reaches it only through `trial`, a sudo wrapper).

    trial.py <joint_id> [torque_Nm] [pattern]

Single-bolt trial: tightens one bolt of the joint to the torque (default: the handbook torque for the joint's target
preload) and prints the torque applied and the preload developed in that bolt. Pattern trial (the word `pattern`
after the torque): tightens every bolt of the pattern to the torque and prints the preload then measured in one
monitored bolt. A single-bolt trial uses one slot of the budget and a pattern trial two. The budget is BUDGET slots
in all and does not refill: every slot used leaves one record file in STATE, created exclusively, and the count of
records is the count of slots used.
The rig refuses to run if its state directory is not exactly as installed (fail closed).
"""
import json
import os
import re
import stat
import sys

import numpy as np

RIG = os.environ.get("RIG_DIR", "/opt/rig")      # the override is for local testing; sudo resets the environment
SEALED = os.path.join(RIG, "sealed")
STATE = os.path.join(RIG, "state")
BUDGET = 8
T_MAX = 20000.0            # N.m; above this the rig's reaction arm is not rated
JOINT_RE = re.compile(r"^J(0[1-9]|1[0-6])$")


def refuse(msg, code=1):
    print(msg)
    sys.exit(code)


def check_dir(path):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and (st.st_mode & 0o777) == 0o700


def trials_used():
    n = 0
    for name in os.listdir(STATE):
        if re.match(r"^trial_\d{2}\.json$", name):
            p = os.path.join(STATE, name)
            st = os.lstat(p)
            if not stat.S_ISREG(st.st_mode):
                refuse("rig state damaged; refusing")
            n += 1
    return n


def main(argv):
    pattern = False
    if len(argv) == 2 and argv[1] == "pattern":
        pattern = True
        argv = argv[:1]
    elif len(argv) == 3:
        if argv[2] != "pattern":
            refuse("usage: trial <joint_id> [torque_Nm] [pattern]", 2)
        pattern = True
        argv = argv[:2]
    if not (1 <= len(argv) <= 2):
        refuse("usage: trial <joint_id> [torque_Nm] [pattern]", 2)
    jid = argv[0]
    if not JOINT_RE.match(jid):
        refuse("unknown joint %r (J01 to J16)" % jid, 2)
    torque = None
    if len(argv) == 2:
        try:
            torque = float(argv[1])
        except ValueError:
            refuse("torque must be a number in N.m", 2)
        if not (np.isfinite(torque) and 0.0 < torque <= T_MAX):
            refuse("torque must be between 0 and %.0f N.m" % T_MAX, 2)
    if not (check_dir(SEALED) and check_dir(STATE)):
        refuse("rig not available (state check failed)")
    sys.path.insert(0, SEALED)
    import jointsim as J  # noqa: E402
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["seed"]
    truth = J.seal(seed)
    used = trials_used()
    cost = J.PATTERN_COST if pattern else 1
    if used + cost > BUDGET:
        refuse("trial budget exhausted: %d of %d used, a %s trial needs %d" % (
            used, BUDGET, "pattern" if pattern else "single-bolt", cost))
    # reserve the trial's slots first (exclusive create); a pattern trial takes two slots. The count of slot files is
    # the count of trials used.
    idx = used + 1
    fds = []
    for k in range(cost):
        rec = os.path.join(STATE, "trial_%02d.json" % (idx + k))
        try:
            fds.append((rec, os.open(rec, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)))
        except FileExistsError:
            for path, fd in fds:
                os.close(fd)
                os.unlink(path)
            refuse("rig busy; try again")
    t = truth[jid]
    if torque is None:
        torque = J.K_HB * t["d"] * t["Ftarget"]
    # measurement noise, fixed by the trial index and joint so that a rerun of the same campaign repeats
    rng = np.random.default_rng([seed, idx, int(jid[1:])])
    T, F = J.trial(truth, jid, rng, torque, pattern)
    with os.fdopen(fds[0][1], "w") as f:
        json.dump({"index": idx, "joint": jid, "pattern": pattern, "torque_Nm": round(T, 3),
                   "preload_kN": round(F / 1e3, 3)}, f)
    for k, (path, fd) in enumerate(fds[1:], start=1):
        with os.fdopen(fd, "w") as f:
            json.dump({"index": idx + k, "slot_of": idx}, f)
    used_now = idx + cost - 1
    if pattern:
        print("joint %s, pattern trial: torque applied %.1f N.m to every bolt, preload in the monitored bolt %.2f kN "
              "(trials used %d of %d)" % (jid, T, F / 1e3, used_now, BUDGET))
    else:
        print("joint %s: torque applied %.1f N.m, preload developed in the bolt %.2f kN (trials used %d of %d)"
              % (jid, T, F / 1e3, used_now, BUDGET))


if __name__ == "__main__":
    main(sys.argv[1:])
