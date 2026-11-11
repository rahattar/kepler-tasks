#!/usr/bin/env python3
"""The unit's test crew (runs as the crew user; the agent reaches it only through the `fieldtest` wrapper).

    lab.py fieldtest <test>

runs one of isim.TESTS on the unit and writes what it measured to REPORTS as one CSV. Each order leaves one
record in STATE, created exclusively (O_EXCL, O_NOFOLLOW). The booking is isim.BUDGET tests and does not refill,
an order is charged before the test is run, and a test already run is refused. The crew will not start if its
directories are not as installed.
"""
import datetime
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True
LAB = os.environ.get("LAB_DIR", "/opt/crew")       # the overrides are for local testing; sudo resets the environment
SEALED = os.path.join(LAB, "sealed")
STATE = os.path.join(LAB, "state")
REPORTS = os.environ.get("REPORT_DIR", "/app/field_reports")
DAY = "2026-11-11"


def refuse(message, code=1):
    print(message)
    sys.exit(code)


def as_installed(path, mode=0o700):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and (st.st_mode & 0o777) == mode


def main(argv):
    sys.path.insert(0, SEALED)
    import isim as S  # noqa: E402
    usage = "usage: fieldtest <test>   (one of: %s)" % ", ".join(S.TESTS)
    if len(argv) != 2 or argv[0] != "fieldtest" or argv[1] not in S.TESTS:
        refuse(usage, 2)
    test = argv[1]
    if not (as_installed(SEALED) and as_installed(STATE) and as_installed(REPORTS, 0o755)):
        refuse("the test crew is not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["test_seed"]

    done = []
    for name in sorted(os.listdir(STATE)):
        if re.match(r"^order_\d{2}\.json$", name):
            path = os.path.join(STATE, name)
            if not stat.S_ISREG(os.lstat(path).st_mode):
                refuse("the crew's own records are damaged; refusing to run")
            done.append(json.load(open(path))["test"])
    if len(done) >= S.BUDGET:
        refuse("booking used: %d of %d tests" % (len(done), S.BUDGET))
    if test in done:
        refuse("%s has been run already; the crew will not take a second order for it" % test)

    index = len(done) + 1
    try:
        fd = os.open(os.path.join(STATE, "order_%02d.json" % index),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("the crew is out on another order; try again")
    with os.fdopen(fd, "w") as handle:
        json.dump({"order": index, "test": test}, handle)

    header, rows, note = S.run_test(test, seed)
    lines = ["# order %d: %s, %s, run %s" % (index, test, note, DAY), ",".join(header)]
    lines += [",".join(row) for row in rows]
    name = "order_%02d_%s.csv" % (index, test.replace("-", "_"))
    rfd = os.open(os.path.join(REPORTS, name),
                  os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(rfd, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    print("# order %d: %s" % (index, note))
    print("# %d rows written to %s" % (len(rows), os.path.join(REPORTS, name)))
    print("# booking used %d of %d tests" % (index, S.BUDGET))


if __name__ == "__main__":
    main(sys.argv[1:])
