#!/usr/bin/env python3
"""The booked instrument M-7 (runs as the lab user; the agent reaches it only through the `slm` and `rt` wrappers).

    lab.py slm <position> <state>     the eight band levels at a position, with that state of the machines
    lab.py rt <position>              the reverberation time of the eight bands at a position

Both commands draw on one booking of isim.BUDGET readings, which does not refill. Each reading leaves one record file
in STATE, created exclusively (O_EXCL, O_NOFOLLOW). A reading comes from numpy's generator seeded with (seed, the
reading number, the command and its arguments), so the same reading in the same place of a plan always gives the same
report. The instrument refuses to run if its directories are not as installed.
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
    usage = ("usage: slm <position> <state>   (positions: %s; states: %s)\n"
             "       rt <position>" % (" ".join(S.POS), " ".join(S.STATES)))
    if not argv or argv[0] not in ("slm", "rt"):
        refuse(usage, 2)
    cmd = argv[0]
    want = 3 if cmd == "slm" else 2
    if len(argv) != want:
        refuse(usage, 2)
    pid = argv[1]
    if pid not in S.POS:
        refuse(usage, 2)
    state = argv[2] if cmd == "slm" else "off"
    if state not in S.STATES:
        refuse(usage, 2)
    if not (check_dir(SEALED) and check_dir(STATE) and check_dir(REPORTS, 0o755)):
        refuse("the instrument is not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["seed"]
    done = 0
    for name in os.listdir(STATE):
        if re.match(r"^reading_\d{2}\.json$", name):
            if not stat.S_ISREG(os.lstat(os.path.join(STATE, name)).st_mode):
                refuse("the instrument's records are damaged; refusing")
            done += 1
    if done >= S.BUDGET:
        refuse("booking used: %d of %d readings" % (done, S.BUDGET))
    idx = done + 1
    try:
        fd = os.open(os.path.join(STATE, "reading_%02d.json" % idx),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("the instrument is busy; try again")
    rng = np.random.default_rng([seed, idx, 3, ("slm", "rt").index(cmd), list(S.POS).index(pid),
                                 list(S.STATES).index(state)])
    if cmd == "slm":
        v = S.lab_slm(pid, state, rng)
        head = "# reading %d: M-7, band sound pressure level at %s, machines running: %s" % (
            idx, pid, state if state != "off" else "none")
        body = "band_Hz,%s\nlevel_dB,%s" % (",".join(S.LABEL[b] for b in S.BANDS), ",".join("%.1f" % x for x in v))
        name = "reading_%02d_slm_%s_%s.csv" % (idx, pid, state)
    else:
        v = S.lab_rt(pid, rng)
        head = "# reading %d: M-7 decay analyser, reverberation time at %s" % (idx, pid)
        body = "band_Hz,%s\nT_s,%s" % (",".join(S.LABEL[b] for b in S.BANDS), ",".join("%.2f" % x for x in v))
        name = "reading_%02d_rt_%s.csv" % (idx, pid)
    text = "%s\n%s\n" % (head, body)
    with os.fdopen(fd, "w") as f:
        json.dump({"reading": idx, "argv": argv, "value": v}, f)
    rfd = os.open(os.path.join(REPORTS, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(rfd, "w") as f:
        f.write(text)
    sys.stdout.write(text)
    print("# readings used %d of %d; report saved as %s" % (idx, S.BUDGET, os.path.join(REPORTS, name)))


if __name__ == "__main__":
    main(sys.argv[1:])
