#!/usr/bin/env python3
"""The unit's test crew (runs as the crew user; the agent reaches it only through the `fieldtest` wrapper).

    lab.py fieldtest <test> <test>

runs isim.BUDGET of isim.TESTS on the unit and writes what each measured to REPORTS as one CSV apiece. The whole
booking is placed in a single order: the crew takes the names of every test it is to run before it runs any of
them, so no choice can rest on a result, and it refuses a second order outright. The order leaves one record in
STATE, created exclusively (O_EXCL, O_NOFOLLOW). The crew will not start if its directories are not as installed.
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
    usage = ("usage: fieldtest <test> <test>   (%d tests, named together in one order, from: %s)"
             % (S.BUDGET, ", ".join(S.TESTS)))
    wanted = argv[1:]
    if argv[:1] != ["fieldtest"] or len(wanted) != S.BUDGET:
        refuse(usage, 2)
    if any(test not in S.TESTS for test in wanted):
        refuse(usage, 2)
    if len(set(wanted)) != len(wanted):
        refuse("the crew will not run the same test twice; name %d different tests" % S.BUDGET, 2)
    if not (as_installed(SEALED) and as_installed(STATE) and as_installed(REPORTS, 0o755)):
        refuse("the test crew is not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["test_seed"]

    for name in sorted(os.listdir(STATE)):
        if re.match(r"^order_\d{2}\.json$", name):
            path = os.path.join(STATE, name)
            if not stat.S_ISREG(os.lstat(path).st_mode):
                refuse("the crew's own records are damaged; refusing to run")
            placed = json.load(open(path))["tests"]
            refuse("the booking was placed already, for %s; the crew is off the unit"
                   % ", ".join(placed))

    # the whole booking is written down before any test is run, so no order can rest on a result
    try:
        fd = os.open(os.path.join(STATE, "order_01.json"),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("the crew is out on another order; try again")
    with os.fdopen(fd, "w") as handle:
        json.dump({"order": 1, "tests": wanted}, handle)

    for index, test in enumerate(wanted, start=1):
        header, rows, note = S.run_test(test, seed)
        lines = ["# test %d of the booking: %s, %s, run %s" % (index, test, note, DAY), ",".join(header)]
        lines += [",".join(row) for row in rows]
        name = "order_%02d_%s.csv" % (index, test.replace("-", "_"))
        rfd = os.open(os.path.join(REPORTS, name),
                      os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(rfd, "w") as handle:
            handle.write("\n".join(lines) + "\n")
        print("# test %d of the booking: %s" % (index, note))
        print("# %d rows written to %s" % (len(rows), os.path.join(REPORTS, name)))
    print("# the booking is used up: %d of %d tests" % (len(wanted), S.BUDGET))


if __name__ == "__main__":
    main(sys.argv[1:])
