#!/usr/bin/env python3
"""The oil laboratory.

    lab.py SITE TANK [TANK ...]

For a site the laboratory holds a book: how many samples it will analyse for the site's package, and what the
oil now in each tank analyses as. `answer` is its whole rule for an order. An order of more
tanks than the allowance, or naming a tank the site does not have, is refused whole and does not count
as the site's order.

Where a program is written, this file runs as the user `lab`, which alone can read the books, and is reached
through the `labsample` wrapper and one sudo rule. The wrapper has already read the site's name from the
package, so nothing here opens a file of the caller's. One order is taken for a site in a run, and a run is
the process that placed the order, so a program can be run on the same package as often as it is needed, and
an order typed at a shell is a run of its own. The order is written down before any figure is given.

Where a program is checked, the checker holds the books, takes the orders itself and gives `answer`'s reply.
"""
import json
import os
import stat
import sys
import time

sys.dont_write_bytecode = True
HOME = "/opt/lab"
BOOKS = os.path.join(HOME, "sealed")
ORDERS = os.path.join(HOME, "state")
HEADER = "sampled_at,cr_max_K_s,t_crmax_C,cr_300_K_s"
TAKEN = "an order was already placed for this package in this run; the laboratory takes one"
NO_BOOK = "the laboratory holds nothing for a site of that name"
SHELLS = ("sh", "bash", "dash", "ash", "zsh", "ksh")


def book_of(books, site):
    """The laboratory's book for a site, or None when it holds none."""
    if not site or not site.replace("_", "").isalnum():
        return None
    try:
        with open(os.path.join(books, site + ".json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def answer(book, tags):
    """(True, the analyses as lines of text) for an order the laboratory takes, (False, why not) otherwise."""
    if len(tags) > book["budget"]:
        return False, "the laboratory analyses at most %d samples for this package" % book["budget"]
    for tag in tags:
        if tag not in book["analyses"]:
            return False, "no tank %s on this site" % tag
    lines = [HEADER]
    for tag in tags:
        cr_max, t_crmax, cr_300 = book["analyses"][tag]
        lines.append("%s,%.1f,%d,%.2f" % (tag, cr_max, t_crmax, cr_300))
    return True, "\n".join(lines)


def as_installed(path):
    try:
        found = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(found.st_mode) and found.st_uid == os.geteuid() and stat.S_IMODE(found.st_mode) == 0o700


def started(pid):
    """(name, parent pid, start time) of a process, from /proc."""
    with open("/proc/%d/stat" % pid) as handle:
        text = handle.read()
    fields = text[text.rindex(")") + 2:].split()
    return text[text.index("(") + 1:text.rindex(")")], int(fields[1]), fields[19]


def placed_by():
    """The run an order belongs to: the process that placed it, as its pid and start time.

    That is the nearest ancestor that is not sudo. An order typed at a shell has no run behind it, so each such
    order is its own.
    """
    pid = os.getppid()
    try:
        for _ in range(8):
            name, parent, since = started(pid)
            if name != "sudo":
                if name in SHELLS:
                    break
                return "%d.%s" % (pid, since)
            pid = parent
        return "%d.%s" % (os.getpid(), started(os.getpid())[2])
    except (OSError, ValueError):
        return "%d.0" % os.getpid()


def main(argv):
    if len(argv) < 2:
        print("usage: labsample PACKAGE_DIR TANK [TANK ...]")
        return 2
    site, tags = argv[0], argv[1:]
    if not (as_installed(BOOKS) and as_installed(ORDERS)):
        print("the laboratory is not available (its directories are not as installed)")
        return 1
    book = book_of(BOOKS, site)
    if book is None:
        print(NO_BOOK)
        return 1
    taken, text = answer(book, tags)
    if not taken:
        print(text)
        return 1
    for name in os.listdir(ORDERS):                                  # orders of runs more than a day old
        path = os.path.join(ORDERS, name)
        if time.time() - os.lstat(path).st_mtime > 86400:
            os.unlink(path)
    slot = os.path.join(ORDERS, "%s.%s" % (site, placed_by()))
    try:                                                             # created, never overwritten, never a link
        handle = os.open(slot, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        print(TAKEN)
        return 1
    with os.fdopen(handle, "w") as entry:
        entry.write(" ".join(tags))
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
