"""The unoptimised second solution, naive_quench.py, through the checker.

    python3 naive_run.py > naive_run.txt

First on the six sites cut down to every 40th load, with the limit set aside, to show that it is
right and how far a separately written solution stands from the sealed results. Then on the six sites as they
are, at the limit.
"""
import os
import shutil

import common
from common import grade_program

NAIVE = os.path.join(common.HERE, "naive_quench.py")
EVERY = 40


def main():
    print("authoring/evidence/naive_quench.py run by tests/grade_program.py: as nobody, one thread to a library")
    print()
    print("The six sites with every %dth load kept, 3 600 s allowed for a run" % EVERY)
    root, sites, truths = common.staged(common.HIDDEN, every=EVERY)
    thin = common.assess(NAIVE, sites=sites, truths=truths, limit=3600)
    shutil.rmtree(root)
    for name, entry in thin.sites.items():
        print(common.line(name, entry))
    print("accepted" if thin.accepted else "NOT ACCEPTED")
    points = sum(entry["points"] for entry in thin.sites.values())
    seconds = sum(entry["seconds"] for entry in thin.sites.values())
    rate = seconds / points
    widest = max(max(entry["largest_error_over_band"].values()) for entry in thin.sites.values())
    print("%d loads in %.0f s: %.2f s a load" % (points, seconds, rate))
    print("its widest departure from the sealed results at any of those loads is %.2f of a band, so every band "
          "is at least %.0f times the widest departure of a separately written solution" % (widest, 1.0 / widest))
    full = {name: len(common.rows_of(os.path.join(common.SITES, name, "loads.csv"))) for name in common.HIDDEN}
    print("at that rate the sites as they are, of %d to %d loads, would take %.0f to %.0f s a run, %.0f to %.0f "
          "times the limit of %d s" % (min(full.values()), max(full.values()), rate * min(full.values()),
                                       rate * max(full.values()), rate * min(full.values()) / grade_program.RUN_LIMIT_S,
                                       rate * max(full.values()) / grade_program.RUN_LIMIT_S, grade_program.RUN_LIMIT_S))
    print()
    print("The six sites as they are, %d s allowed for a run" % grade_program.RUN_LIMIT_S)
    outcome = common.assess(NAIVE)
    for name, entry in outcome.sites.items():
        print(common.line(name, entry))
    print("sites run: %d of %d; stopped: %s" % (len(outcome.sites), len(common.HIDDEN), outcome.stopped or "no"))
    print("accepted" if outcome.accepted else "not accepted")


if __name__ == "__main__":
    main()
