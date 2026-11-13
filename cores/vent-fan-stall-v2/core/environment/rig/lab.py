#!/usr/bin/env python3
"""The survey crew.

    lab.py pqsurvey PACKAGE_DIR BRANCH [BRANCH ...]

For a district the crew holds a book: how many branches it will survey for the district's package, and what
a pressure-quantity survey of each branch reads with the district as it stands now. An order of more branches
than the allowance, or naming a branch the district does not have, is refused whole and does not count. One
order is taken for a district in a run, and a run is the process that placed the order; an order typed at a
shell is a run of its own. The order is written down before any figure is given.
"""
import json, os, sys, time

sys.dont_write_bytecode = True
HOME = os.environ.get("LAB_DIR", "/opt/lab")
BOOKS = os.path.join(HOME, "sealed"); ORDERS = os.path.join(HOME, "state")
SHELLS = ("sh", "bash", "dash", "ash", "zsh", "ksh")
USAGE = "usage: pqsurvey PACKAGE_DIR BRANCH [BRANCH ...]"

def answer(book, branches):
    if len(branches) > book["allowance"]:
        return False, "the crew surveys at most %d branches for this package" % book["allowance"]
    if len(set(branches)) != len(branches):
        return False, "a branch is named twice"
    for b in branches:
        if b not in book["readings"]: return False, "no branch %s in this district" % b
    lines = ["branch,dp_Pa,q_m3_s"]
    for b in branches:
        dp, q = book["readings"][b]; lines.append("%s,%.5g,%.5g" % (b, dp, q))
    return True, "\n".join(lines)

def started(pid):
    with open("/proc/%d/stat" % pid) as f: text = f.read()
    fields = text[text.rindex(")") + 2:].split()
    return text[text.index("(") + 1:text.rindex(")")], int(fields[1]), fields[19]

def placed_by():
    pid = os.getppid()
    try:
        name, parent, since = started(pid)
        if name in SHELLS: return "%d.%s" % (os.getpid(), started(os.getpid())[2])
        return "%d.%s" % (pid, since)
    except (OSError, ValueError):
        return "%d.0" % os.getpid()

def main(argv):
    if len(argv) < 3 or argv[0] != "pqsurvey":
        print(USAGE); return 2
    try:
        with open(os.path.join(argv[1], "district.json")) as f: name = str(json.load(f)["district"])
    except (OSError, ValueError, KeyError, TypeError):
        print("%s is not a district package: no district.json naming the district" % argv[1]); return 2
    if not name.replace("_", "").isalnum():
        print("the crew holds nothing for a district of that name"); return 1
    try:
        with open(os.path.join(BOOKS, name + ".json")) as f: book = json.load(f)
    except (OSError, ValueError):
        print("the crew holds nothing for a district of that name"); return 1
    ok, text = answer(book, argv[2:])
    if not ok:
        print(text); return 1
    os.makedirs(ORDERS, exist_ok=True)
    for n in os.listdir(ORDERS):
        p = os.path.join(ORDERS, n)
        if time.time() - os.lstat(p).st_mtime > 86400: os.unlink(p)
    slot = os.path.join(ORDERS, "%s.%s" % (name, placed_by()))
    try:
        h = os.open(slot, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        print("an order was already placed for this package in this run; the crew takes one"); return 1
    with os.fdopen(h, "w") as f: f.write(" ".join(argv[2:]))
    print(text); return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
