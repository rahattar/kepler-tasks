#!/usr/bin/env python3
"""The survey crew.

    lab.py pqsurvey DISTRICT BRANCH [BRANCH ...]

For each district the crew holds a book: the number of branches it will survey for the district's package
and what a pressure-quantity survey of every branch reads with the district as it stands now. `answer` is
the whole of its rule. An order for more branches than the allowance, one naming a branch twice and one
naming a branch the district does not have are refused whole, and a refused order is not the district's
order.

Where a program is written this file runs as the account `crew`, which alone can open the books, and is
reached through the `pqsurvey` wrapper and one sudo rule. The wrapper has read the district's name from the
package, so nothing of the caller's is opened here. The crew takes one order for a district in a run. A run
is the process that placed the order, so a program may be run on one package as often as its author needs,
and an order typed at a shell is a run by itself. The order is written down before a figure is given.

Where a program is checked, the checker holds the books and gives `answer`'s reply itself.
"""
import json
import os
import stat
import sys
import time

sys.dont_write_bytecode = True
ROOM = os.environ.get("LAB_DIR") or "/opt/crew"
BOOKS = os.path.join(ROOM, "sealed")
ORDERS = os.path.join(ROOM, "state")
USAGE = "usage: pqsurvey PACKAGE_DIR BRANCH [BRANCH ...]"
UNKNOWN = "the crew holds nothing for a district of that name"
ALREADY = "an order was already placed for this package in this run; the crew takes one"
COLUMNS = "branch,dp_Pa,q_m3_s"


def book(books, district):
    """The crew's book for a district, or None."""
    if not district or not district.replace("_", "").isalnum():
        return None
    try:
        with open(os.path.join(books, district + ".json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def answer(held, branches):
    """(True, the readings as lines) for an order the crew takes; (False, the reason) for one it refuses."""
    if not branches:
        return False, USAGE
    if len(branches) > held["allowance"]:
        return False, "the crew surveys at most %d branches for this package" % held["allowance"]
    if len(set(branches)) != len(branches):
        return False, "a branch is named twice"
    for branch in branches:
        if branch not in held["readings"]:
            return False, "no branch %s in this district" % branch
    lines = [COLUMNS]
    for branch in branches:
        dp, q = held["readings"][branch]
        lines.append("%s,%.5g,%.5g" % (branch, dp, q))
    return True, "\n".join(lines)


def kept_private(path):
    try:
        found = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(found.st_mode) and found.st_uid == os.geteuid() and stat.S_IMODE(found.st_mode) == 0o700


def process(pid):
    """(name, parent, start time) of a process."""
    with open("/proc/%d/stat" % pid) as handle:
        line = handle.read()
    rest = line[line.rindex(")") + 2:].split()
    return line[line.index("(") + 1:line.rindex(")")], int(rest[1]), rest[19]


def run_of_caller():
    """What an order is counted against: the nearest ancestor that is neither sudo nor a shell."""
    pid = os.getppid()
    try:
        for _ in range(6):
            name, parent, since = process(pid)
            if name == "sudo":
                pid = parent
                continue
            if name in ("sh", "bash", "dash", "ash", "zsh", "ksh"):
                break
            return "%d.%s" % (pid, since)
        return "%d.%s" % (os.getpid(), process(os.getpid())[2])
    except (OSError, ValueError):
        return "%d.0" % os.getpid()


def main(argv):
    if len(argv) < 3 or argv[0] != "pqsurvey":
        print(USAGE)
        return 2
    district = argv[1]
    if os.path.isdir(district):                       # called with the package itself, by the caller's own account
        try:
            with open(os.path.join(district, "district.json")) as handle:
                district = str(json.load(handle)["district"])
        except (OSError, ValueError, KeyError, TypeError):
            print("%s is not a district package: no district.json naming the district" % argv[1])
            return 2
    if not (kept_private(BOOKS) and kept_private(ORDERS)):
        print("the crew is not available (its rooms are not as they were set up)")
        return 1
    held = book(BOOKS, district)
    if held is None:
        print(UNKNOWN)
        return 1
    taken, words = answer(held, argv[2:])
    if not taken:
        print(words)
        return 1
    for name in os.listdir(ORDERS):                   # orders of runs more than a day old
        old = os.path.join(ORDERS, name)
        if time.time() - os.lstat(old).st_mtime > 86400:
            os.unlink(old)
    try:
        slot = os.open(os.path.join(ORDERS, "%s.%s" % (district, run_of_caller())),
                       os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        print(ALREADY)
        return 1
    with os.fdopen(slot, "w") as entry:
        entry.write(" ".join(argv[2:]))
    print(words)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
