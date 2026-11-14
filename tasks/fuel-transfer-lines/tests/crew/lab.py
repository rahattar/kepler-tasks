#!/usr/bin/env python3
"""The survey crew's rule for heat-loss surveys of pipes as they stand now.

    lab.py heatsurvey PACKAGE_DIR PIPE [PIPE ...]
    lab.py heatsurvey site=NAME PIPE [PIPE ...]

For each site it answers for, the crew keeps a book: how many pipes it will survey for the site's package
(the package's survey_allowance) and what a heat-loss survey of each pipe reads today, with the pipe's line
at its survey rating. `weigh` is the whole rule for one order:

  - more pipes than the allowance, a pipe named twice, or a pipe the site does not have: the order is turned
    down whole, nothing is read out, and it does not count;
  - otherwise one row a pipe, in the order asked, under the columns of HEAD.

The crew takes one order for a package in a run. Run from a command line as above (where a program is being
written) a run is the process that placed the order, and an order typed at a shell is a run by itself; the
order is written down under <books>/../state before a single figure is given out. Where a finished program is
run and compared, the same `weigh` answers and the checker keeps the count.
"""
import json
import os
import sys
import time

sys.dont_write_bytecode = True

HEAD = "pipe,line_flow_t_h,flow_t_h,t_in_C,t_out_C,t_amb_C"
USAGE = "usage: heatsurvey PACKAGE_DIR PIPE [PIPE ...]"
NOT_A_PACKAGE = "%s is not a site package: it has no site.json that names the site"
NO_SUCH_SITE = "the survey crew takes no order for a site of that name"
ONE_A_RUN = "an order for this package was already placed in this run, and the crew takes one"
HOME = os.environ.get("LAB_DIR", "/opt/surveyors")
SHELLS = ("sh", "bash", "dash", "ash", "zsh", "ksh", "fish")


def site_named(package_dir):
    """The site a package is of, or None."""
    try:
        with open(os.path.join(package_dir, "site.json")) as handle:
            name = json.load(handle)["site"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return name if isinstance(name, str) else None


def book_of(shelf, site):
    """The crew's book for a site, or None where it keeps none."""
    if not (isinstance(site, str) and site and site.replace("_", "").isalnum()):
        return None
    try:
        with open(os.path.join(shelf, site + ".json")) as handle:
            book = json.load(handle)
    except (OSError, ValueError):
        return None
    return book if isinstance(book, dict) and "allowance" in book and "readings" in book else None


def weigh(book, pipes):
    """(taken, words): the readings as text, or the sentence that turns the order down."""
    if not pipes:
        return False, USAGE
    if len(pipes) > int(book["allowance"]):
        return False, "the crew surveys at most %d pipes for this package" % int(book["allowance"])
    if len(set(pipes)) != len(pipes):
        return False, "a pipe is named twice"
    for pipe in pipes:
        if pipe not in book["readings"]:
            return False, "the site has no pipe %s" % pipe[:40]
    rows = [",".join([pipe] + [str(figure) for figure in book["readings"][pipe]]) for pipe in pipes]
    return True, "\n".join([HEAD] + rows)


def _process(pid):
    """(name, parent, start time) of a process, from /proc."""
    with open("/proc/%d/stat" % pid) as handle:
        line = handle.read()
    rest = line[line.rindex(")") + 2:].split()
    return line[line.index("(") + 1:line.rindex(")")], int(rest[1]), rest[19]


def _run():
    """What stands for "this run": the process that placed the order, seen through sudo."""
    try:
        pid = os.getppid()
        name, parent, born = _process(pid)
        while name == "sudo" and parent > 1:
            pid = parent
            name, parent, born = _process(pid)
        if name in SHELLS:                                  # typed at a prompt, or a line of a shell script
            pid = os.getpid()
            born = _process(pid)[2]
        return "%d.%s" % (pid, born)
    except (OSError, ValueError, IndexError):
        return "%d.x" % os.getpid()


def main(words):
    if len(words) < 3 or words[0] != "heatsurvey":
        print(USAGE)
        return 2
    site = words[1][5:] if words[1].startswith("site=") else site_named(words[1])
    if site is None:
        print(NOT_A_PACKAGE % words[1])
        return 2
    book = book_of(os.path.join(HOME, "sealed"), site)
    if book is None:
        print(NO_SUCH_SITE)
        return 1
    taken, said = weigh(book, words[2:])
    if not taken:
        print(said)
        return 1
    slips = os.path.join(HOME, "state")
    os.makedirs(slips, exist_ok=True)
    for old in os.listdir(slips):                           # slips of runs long over
        try:
            if time.time() - os.lstat(os.path.join(slips, old)).st_mtime > 86400:
                os.unlink(os.path.join(slips, old))
        except OSError:
            pass
    try:
        slip = os.open(os.path.join(slips, "%s.%s" % (site, _run())), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        print(ONE_A_RUN)
        return 1
    with os.fdopen(slip, "w") as handle:
        handle.write(" ".join(words[2:]) + "\n")
    print(said)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
