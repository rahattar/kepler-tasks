#!/usr/bin/env python3
"""The field team.

    lab.py gdsurvey NETWORK_OR_PACKAGE ITEM [ITEM ...]

For each network it serves the team holds a book: the number of items it will survey or prove for the
network's package, and what it reads at every main, boundary valve and customer meter with the network as it
stands now. An order for more items than the allowance, one naming an item twice and one naming an item the
network does not have are refused whole, and a refused order is not the network's order. The team takes one
order for a network in a run: a run is the process that placed the order, and an order typed at a shell is a
run by itself. GASCREW_BOOKS names the folder of books and GASCREW_STATE the folder where orders are noted.
"""
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BOOKS = os.environ.get("GASCREW_BOOKS") or os.path.join(HERE, "dev")
ORDERS = os.environ.get("GASCREW_STATE") or os.path.join(HERE, "state_dev")
USAGE = "usage: gdsurvey PACKAGE_DIR ITEM [ITEM ...]"
HEADS = {"mains": "main,p_from_barg,dp_bar,q_m3h", "valves": "valve,p_node_barg,p_neighbour_barg,q_m3h",
         "meters": "meter,registers_pct"}


def book(network):
    if not network or not network.replace("_", "").replace("-", "").isalnum():
        return None
    try:
        with open(os.path.join(BOOKS, network + ".json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def answer(held, items):
    if not items:
        return False, USAGE
    if len(items) > held["allowance"]:
        return False, "the field team surveys or proves at most %d items for this package" % held["allowance"]
    if len(set(items)) != len(items):
        return False, "an item is named twice"
    for it in items:
        if not any(it in held[k] for k in HEADS):
            return False, "no main, boundary valve or meter %s in this network" % it
    lines = []
    for kind, head in HEADS.items():
        mine = [it for it in items if it in held[kind]]
        if not mine:
            continue
        lines.append(head)
        for it in mine:
            v = held[kind][it]
            if kind == "mains":
                lines.append("%s,%.4f,%.6g,%.6g" % (it, v[0], v[1], v[2]))
            elif kind == "valves":
                lines.append("%s,%.4f,%.4f,%.6g" % (it, v[0], v[1], v[2]))
            else:
                lines.append("%s,%.1f" % (it, v))
    return True, "\n".join(lines)


def process(pid):
    with open("/proc/%d/stat" % pid) as handle:
        line = handle.read()
    rest = line[line.rindex(")") + 2:].split()
    return line[line.index("(") + 1:line.rindex(")")], int(rest[1]), rest[19]


def run_of_caller():
    """The nearest ancestor that is not a shell or the gdsurvey wrapper."""
    pid = os.getppid()
    try:
        for _ in range(6):
            name, parent, since = process(pid)
            if name in ("sh", "bash", "dash", "zsh"):
                break
            return "%d.%s" % (pid, since)
        return "%d.%s" % (os.getpid(), process(os.getpid())[2])
    except (OSError, ValueError):
        return "%d.0" % os.getpid()


def main(argv):
    if len(argv) < 3 or argv[0] != "gdsurvey":
        print(USAGE)
        return 2
    network = argv[1]
    if os.path.isdir(network):
        try:
            with open(os.path.join(network, "network.json")) as handle:
                network = str(json.load(handle)["network"])
        except (OSError, ValueError, KeyError, TypeError):
            print("%s is not a network package: no network.json naming the network" % argv[1])
            return 2
    held = book(network)
    if held is None:
        print("the field team has not been to a network of that name")
        return 1
    taken, words = answer(held, argv[2:])
    if not taken:
        print(words)
        return 1
    os.makedirs(ORDERS, exist_ok=True)
    for name in os.listdir(ORDERS):
        old = os.path.join(ORDERS, name)
        if time.time() - os.lstat(old).st_mtime > 86400:
            os.unlink(old)
    try:
        slot = os.open(os.path.join(ORDERS, "%s.%s" % (network, run_of_caller())),
                       os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("an order was already placed for this package in this run; the field team takes one")
        return 1
    with os.fdopen(slot, "w") as entry:
        entry.write(" ".join(argv[2:]))
    print(words)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
