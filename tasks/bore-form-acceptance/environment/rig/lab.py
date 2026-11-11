#!/usr/bin/env python3
"""The metrology room (runs as the room user; the agent reaches it only through the `formscan` wrapper).

    lab.py formscan <feature>

scans the feature on the room's RT-1 form tester: three sections, isim.TESTER_PTS points a revolution, absolute
radius in mm, at the room's own temperature. The points are written to REPORTS as one file; each scan leaves one
record in STATE, created exclusively (O_EXCL, O_NOFOLLOW). The booking is isim.BUDGET scans and does not refill,
a scan is charged before it is made, and a feature already scanned is refused. The room refuses to run if its
directories are not as installed.
"""
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True
LAB = os.environ.get("LAB_DIR", "/opt/room")       # the overrides are for local testing; sudo resets the environment
SEALED = os.path.join(LAB, "sealed")
STATE = os.path.join(LAB, "state")
REPORTS = os.environ.get("REPORT_DIR", "/app/scan_reports")


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
    usage = "usage: formscan <feature>   (one of: %s)" % ", ".join(S.ORDER)
    if len(argv) != 2 or argv[0] != "formscan" or argv[1] not in S.ORDER:
        refuse(usage, 2)
    feature = argv[1]
    if not (check_dir(SEALED) and check_dir(STATE) and check_dir(REPORTS, 0o755)):
        refuse("metrology room not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["scan_seed"]
    done = []
    for name in sorted(os.listdir(STATE)):
        if re.match(r"^scan_\d{2}\.json$", name):
            path = os.path.join(STATE, name)
            if not stat.S_ISREG(os.lstat(path).st_mode):
                refuse("metrology room records damaged; refusing")
            done.append(json.load(open(path))["feature"])
    if len(done) >= S.BUDGET:
        refuse("booking used: %d of %d scans" % (len(done), S.BUDGET))
    if feature in done:
        refuse("%s has been scanned already; the room will not take a second order for it" % feature)
    idx = len(done) + 1
    try:
        fd = os.open(os.path.join(STATE, "scan_%02d.json" % idx),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("metrology room busy; try again")
    with os.fdopen(fd, "w") as f:
        json.dump({"scan": idx, "feature": feature}, f)
    secs = S.scan(feature, idx, seed)
    length = S.LENGTH[feature]
    rows = ["section_mm,angle_deg,radius_mm"]
    for frac, (th, r) in zip(S.SECTIONS, secs):
        z = round(frac * length, 1)
        for a, rr in zip(th, r):
            rows.append("%.1f,%.3f,%.5f" % (z, np.degrees(a), rr))
    name = "scan_%02d_%s.csv" % (idx, feature.lower().replace("-", ""))
    rfd = os.open(os.path.join(REPORTS, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(rfd, "w") as f:
        f.write("\n".join(rows) + "\n")
    print("# scan %d: %s, RT-1 form tester, 1 mm ball, %d points a revolution, %d sections, room %.1f C"
          % (idx, feature, S.TESTER_PTS, len(S.SECTIONS), S.T_ROOM))
    print("# %d points written to %s" % (len(rows) - 1, os.path.join(REPORTS, name)))
    print("# booking used %d of %d scans" % (idx, S.BUDGET))


if __name__ == "__main__":
    main(sys.argv[1:])
