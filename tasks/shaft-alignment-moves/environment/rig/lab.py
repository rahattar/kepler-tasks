#!/usr/bin/env python3
"""The laser alignment contractor. It runs as the contractor's own user; the engineer reaches it only through
the `laservisit` wrapper.

    lab.py laservisit <tag> <tag> <tag> <tag> <tag> <tag>

The whole programme of visits is one order. The contractor writes the order down in its own records before it
measures anything, and from then on takes no other, so no train can be chosen on what another train's report
showed. Each visit leaves one report in the reports directory. The sealed definition of the unit and the
contractor's records sit in directories only the contractor can open, and the program refuses to work if they
are not as the image installed them.
"""
import json
import os
import stat
import sys

sys.dont_write_bytecode = True

# sudo clears the environment, so in the image these are always the installed paths; the two variables exist
# for a local copy of the rig
HOME = os.environ.get("LAB_DIR", "/opt/contractor")
REPORTS = os.environ.get("REPORT_DIR", "/app/laser_reports")
SEALED = os.path.join(HOME, "sealed")
BOOK = os.path.join(HOME, "state")
ORDER = os.path.join(BOOK, "programme.json")


def leave(words, status=1):
    print(words)
    raise SystemExit(status)


def own_directory(path, mode):
    try:
        found = os.lstat(path)
    except OSError:
        return False
    return (stat.S_ISDIR(found.st_mode) and found.st_uid == os.geteuid()
            and stat.S_IMODE(found.st_mode) == mode)


def placed_already():
    """The tags of the programme on the contractor's books, or None when there is none."""
    try:
        found = os.lstat(ORDER)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(found.st_mode):
        leave("the contractor's records are damaged; no visit is made")
    with open(ORDER) as handle:
        return json.load(handle)["trains"]


def main(argv):
    sys.path.insert(0, SEALED)
    import unit3

    usage = ("usage: laservisit <tag> ... <tag>   (the %d trains to visit, named together in one order)"
             % unit3.BUDGET)
    if argv[:1] != ["laservisit"]:
        leave(usage, 2)
    if not (own_directory(SEALED, 0o700) and own_directory(BOOK, 0o700) and own_directory(REPORTS, 0o755)):
        leave("the laser contractor is not available (its directories are not as installed)")
    with open(os.path.join(SEALED, "seed.json")) as handle:
        trains = unit3.build(json.load(handle)["seed"])

    before = placed_already()
    if before is not None:
        leave("the programme was placed already, for %s; the contractor takes no second order"
              % ", ".join(before))
    wanted = argv[1:]
    if len(wanted) != unit3.BUDGET or any(tag not in trains for tag in wanted):
        leave(usage, 2)
    if len(set(wanted)) != unit3.BUDGET:
        leave("the contractor does not return to a train; name %d different trains" % unit3.BUDGET, 2)

    # the order goes on the books before the first train is measured: created, never overwritten, never a link
    try:
        slot = os.open(ORDER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        leave("the programme was placed already; the contractor takes no second order")
    with os.fdopen(slot, "w") as handle:
        json.dump({"trains": wanted}, handle)

    for tag in wanted:
        path = os.path.join(REPORTS, "%s.csv" % tag)
        sheet = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(sheet, "w") as handle:
            handle.write("quantity,mm\n")
            for quantity, value in unit3.laser_report(trains[tag]):
                handle.write("%s,%.3f\n" % (quantity, value))
        print("# %s written to %s" % (tag, path))


if __name__ == "__main__":
    main(sys.argv[1:])
