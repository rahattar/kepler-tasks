#!/usr/bin/env python3
"""The test crew.

    lab.py nertest PACKAGE_DIR TANK [TANK ...]

For each depot the crew keeps a book: the number of tanks it will test for the depot's package and what an NER
test of each tank reads as the tank stands now. An order that is too long or names a tank the depot does not
have is turned down whole and is not counted. The crew takes one order for a depot in a run. A run is
the process that placed the order; an order typed at a shell is a run by itself. The order is entered before a
single figure is given out.
"""
import json, os, sys, time

sys.dont_write_bytecode = True
ROOT = os.environ.get("LAB_DIR", "/opt/lab")
BOOKS = os.path.join(ROOT, "sealed"); TAKEN = os.path.join(ROOT, "state")
SHELLS = ("sh", "bash", "dash", "ash", "zsh", "ksh")
HEAD = "tank,ner_pct_day,t_amb_C"

def proc(pid):
    with open("/proc/%d/stat" % pid) as f: s = f.read()
    rest = s[s.rindex(")") + 2:].split()
    return s[s.index("(") + 1:s.rindex(")")], rest[19]

def run_id():
    parent = os.getppid()
    try:
        name, born = proc(parent)
        if name in SHELLS: return "%d.%s" % (os.getpid(), proc(os.getpid())[1])
        return "%d.%s" % (parent, born)
    except (OSError, ValueError):
        return "%d.0" % os.getpid()

def main(a):
    if len(a) < 3 or a[0] != "nertest":
        print("usage: nertest PACKAGE_DIR TANK [TANK ...]"); return 2
    try:
        with open(os.path.join(a[1], "site.json")) as f: site = str(json.load(f)["site"])
    except (OSError, ValueError, KeyError, TypeError):
        print("%s is not a depot package: no site.json naming the depot" % a[1]); return 2
    book = None
    if site.replace("_", "").isalnum():
        try:
            with open(os.path.join(BOOKS, site + ".json")) as f: book = json.load(f)
        except (OSError, ValueError):
            pass
    if book is None:
        print("the crew takes no order for a depot of that name"); return 1
    tanks = a[2:]
    if len(tanks) > book["allowance"]:
        print("the crew tests at most %d tanks for this package" % book["allowance"]); return 1
    if len(set(tanks)) != len(tanks):
        print("a tank is named twice"); return 1
    for p in tanks:
        if p not in book["readings"]:
            print("the depot has no tank %s" % p); return 1
    os.makedirs(TAKEN, exist_ok=True)
    for n in os.listdir(TAKEN):
        q = os.path.join(TAKEN, n)
        if time.time() - os.lstat(q).st_mtime > 86400: os.unlink(q)
    try:
        h = os.open(os.path.join(TAKEN, "%s.%s" % (site, run_id())), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        print("an order for this package was already placed in this run; the crew takes one"); return 1
    with os.fdopen(h, "w") as f: f.write(" ".join(tanks))
    print(HEAD)
    for p in tanks: print(",".join([p] + [str(x) for x in book["readings"][p]]))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
