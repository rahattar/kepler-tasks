"""Programs that stop short, and the same method done other sound ways, each run by the verifier's checker.

    python3 route_run.py > route_run.txt

A route is the reference with one thing left out or got wrong (variants.ROUTES). Each is run on the two
example packages against their results, and on the six cells at the limit. A sound variation
(variants.SOUND) is run on the six cells and must be accepted.
"""
import os
import subprocess
import sys
import tempfile

import common
import variants


def main():
    cells_dir, results_dir = common.examples_as_cells()
    hidden = [c["cell"] for c in common.HIDDEN]
    failed_by = {name: [] for name in hidden}
    ok = True
    print("Routes that stop short. Each row: the two example packages, then the cells with rows out of band.\n")
    for name, what, changes in variants.ROUTES:
        path = common.program(variants.made(changes))
        on_examples = common.assess(path, cells_dir=cells_dir, results_dir=results_dir)
        report = common.assess(path)
        out = [cell for cell, finding in report["cells"].items() if finding.get("rows_out", 1) > 0]
        for cell in out:
            failed_by[cell].append(name)
        least = min((max(finding["widest"].values()) for cell, finding in report["cells"].items()
                     if finding.get("rows_out", 0) > 0), default=None)
        print("route: %s\n  %s" % (name, what))
        print("  examples: %s" % ("accepted" if on_examples["accepted"] else "not accepted (%s)" % common.line_for(on_examples)))
        print("  cells with rows out: %d of %d (%s)" % (len(out), len(hidden), common.line_for(report)))
        if least is not None:
            print("  at the cell it misses least, its widest departure is %.1f bands" % least)
        print("  %s\n" % ("accepted" if report["accepted"] else "not accepted"))
        ok = ok and not report["accepted"]
    print("How many of these routes each cell stops:")
    for cell in hidden:
        c = next(c for c in common.HIDDEN if c["cell"] == cell)
        kind = ("index %+.2f degrees" % c["index_deg"] if c["index_deg"] else "") + (
            (", " if c["index_deg"] and c["gain"] != 1 else "") + ("gain %.2f" % c["gain"] if c["gain"] != 1 else ""))
        print("  %s (%s): %d of %d" % (cell, kind or "index and gain exact", len(failed_by[cell]), len(variants.ROUTES)))

    print("\nWhat the route `index alone` reports where only the gain is out (the program's own line on stderr):")
    alone = common.program(variants.made(variants.ROUTES[1][2]))
    places = [("pending", c) for c in common.PENDING if c["gain"] != 1 and not c["index_deg"]] + [
        ("cells", c) for c in common.HIDDEN if c["gain"] != 1 and not c["index_deg"]]
    for group, c in places:
        package = os.path.join(common.VISIBLE, "pending", c["cell"]) if group == "pending" else os.path.join(common.CELLS, c["cell"])
        with tempfile.TemporaryDirectory() as box:
            ran = subprocess.run([sys.executable, "-B", alone, package, os.path.join(box, "out.csv")], capture_output=True, text=True)
        print("  %s (gain %.3f, index exact): %s" % (c["cell"], c["gain"], ran.stderr.strip()))

    print("\nSound variations of the method. Each must be accepted.\n")
    spread = 0.0
    for name, changes in variants.SOUND:
        report = common.assess(common.program(variants.made(changes)))
        wide = common.widest(report)
        spread = max(spread, wide or 99.0)
        print("%-82s %s, widest departure %.2f of a band" % (name, "accepted" if report["accepted"] else "NOT ACCEPTED", wide))
        ok = ok and report["accepted"]
    print("\nwidest departure of any sound variation: %.2f of a band" % spread)
    if ok:
        print("%d routes, 0 accepted; %d sound variations, 0 not accepted" % (len(variants.ROUTES), len(variants.SOUND)))
    else:
        print("PROBLEM: a route was accepted or a sound variation was not; see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
