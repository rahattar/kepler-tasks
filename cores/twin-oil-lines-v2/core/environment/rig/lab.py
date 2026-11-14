#!/usr/bin/env python3
"""The survey crew.

    lab.py heatsurvey PACKAGE_DIR PIPE [PIPE ...]

For each site the crew keeps a book: the number of pipes it will survey for the site's package and what a
heat-loss survey of each pipe reads as the pipe stands now. An order that is too long or names a pipe the site
does not have is turned down whole and is not counted. The crew takes one order for a site in a run. A run is
the process that placed the order; an order typed at a shell is a run by itself. The order is entered before a
single figure is given out.
"""
import json, os, sys, time

sys.dont_write_bytecode = True
ROOT = os.environ.get("LAB_DIR", "/opt/lab")
BOOKS = os.path.join(ROOT, "sealed"); TAKEN = os.path.join(ROOT, "state")
SHELLS = ("sh", "bash", "dash", "ash", "zsh", "ksh")
HEAD = "pipe,line_flow_t_h,flow_t_h,t_in_C,t_out_C,t_amb_C"

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
    if len(a) < 3 or a[0] != "heatsurvey":
        print("usage: heatsurvey PACKAGE_DIR PIPE [PIPE ...]"); return 2
    try:
        with open(os.path.join(a[1], "site.json")) as f: site = str(json.load(f)["site"])
    except (OSError, ValueError, KeyError, TypeError):
        print("%s is not a site package: no site.json naming the site" % a[1]); return 2
    book = None
    if site.replace("_", "").isalnum():
        try:
            with open(os.path.join(BOOKS, site + ".json")) as f: book = json.load(f)
        except (OSError, ValueError):
            pass
    if book is None:
        print("the crew takes no order for a site of that name"); return 1
    pipes = a[2:]
    if len(pipes) > book["allowance"]:
        print("the crew surveys at most %d pipes for this package" % book["allowance"]); return 1
    if len(set(pipes)) != len(pipes):
        print("a pipe is named twice"); return 1
    for p in pipes:
        if p not in book["readings"]:
            print("the site has no pipe %s" % p); return 1
    os.makedirs(TAKEN, exist_ok=True)
    for n in os.listdir(TAKEN):
        q = os.path.join(TAKEN, n)
        if time.time() - os.lstat(q).st_mtime > 86400: os.unlink(q)
    try:
        h = os.open(os.path.join(TAKEN, "%s.%s" % (site, run_id())), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        print("an order for this package was already placed in this run; the crew takes one"); return 1
    with os.fdopen(h, "w") as f: f.write(" ".join(pipes))
    print(HEAD)
    for p in pipes: print(",".join([p] + [str(x) for x in book["readings"][p]]))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
