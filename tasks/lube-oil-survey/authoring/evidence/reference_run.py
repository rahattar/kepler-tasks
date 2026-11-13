"""The reference through the checker: the six sites, the two example sites, and its order on the pending package.

    python3 reference_run.py > reference_run.txt
"""
import os
import shutil

import common
from common import grade_program

LIMIT = grade_program.RUN_LIMIT_S


def main():
    print("solution/bearing.py run by tests/grade_program.py: as nobody, one thread to a library, %d s allowed for a run" % LIMIT)
    print()
    print("The six sites")
    outcome = common.assess(common.REFERENCE)
    for name, entry in outcome.sites.items():
        print(common.line(name, entry))
    print("accepted" if outcome.accepted else "NOT ACCEPTED")
    times = [entry["seconds"] for entry in outcome.sites.values()]
    worst = max(max(entry["largest_error_over_band"].values()) for entry in outcome.sites.values())
    print("runs take %.1f to %.1f s; the limit of %d s is %.1f times the slowest run" % (
        min(times), max(times), LIMIT, LIMIT / max(times)))
    print("largest error at any point of any site: %.2f of its band" % worst)
    print("points in all: %d" % sum(entry["points"] for entry in outcome.sites.values()))
    print()
    print("The two example sites, expected.csv taken as the truth")
    root, sites, truths, books = common.visible_as_sites()
    seen = common.assess(common.REFERENCE, sites=sites, truths=truths, books=books)
    for name, entry in seen.sites.items():
        print(common.line(name, entry))
    print("accepted" if seen.accepted else "NOT ACCEPTED")
    shutil.rmtree(root)
    print()
    print("The pending package")
    package = os.path.join(common.VISIBLE, "pending", common.PENDING)
    desk = grade_program.Desk(common.PENDING, grade_program.lab.book_of(common.VISIBLE_BOOKS, common.PENDING))
    ended, seconds, raw = grade_program.run_site(common.REFERENCE, package, desk, LIMIT, os.geteuid() == 0,
                                                 common.TOOLS)
    rows = len(raw.decode().strip().splitlines()) - 1
    print("%-12s %5.1f s  %s, %d rows  order: %s" % (common.PENDING, seconds, ended, rows, " ".join(desk.order)))


if __name__ == "__main__":
    main()
