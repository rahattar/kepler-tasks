"""The second solution, naive_airflow.py: right, and too slow.

    python3 naive_run.py > naive_run.txt

It is run on the seven small districts with the limit set aside, where it has to be accepted, and then on the
six districts at the limit, where the checker has to stop it.
"""
import csv
import os

import common
from common import judge_airflow


def rows(directory, name, table):
    with open(os.path.join(directory, name, table)) as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def main():
    limit = judge_airflow.LIMIT_S
    print("authoring/evidence/naive_airflow.py, run by tests/judge_airflow.judge")
    print()
    print("the seven small districts, the limit set aside (3600 s a run):")
    small = common.run(common.SECOND, "small", limit=3600)
    print(common.lines(small))
    districts = common.sets("small")[0]
    plain = [(note["seconds"], rows(districts, name, "log.csv"), rows(districts, name, "branches.csv"))
             for name, note in small["districts"].items() if note["run"] == "in time"]
    widest = max(note.get("largest_error_over_band", 9e9) for note in small["districts"].values())
    print("  widest departure from the sealed results: %.2f of the band" % widest)
    print("  %.1f to %.1f s a run on districts of %d to %d branches and %d to %d log rows" % (
        min(p[0] for p in plain), max(p[0] for p in plain), min(p[2] for p in plain), max(p[2] for p in plain),
        min(p[1] for p in plain), max(p[1] for p in plain)))
    print()
    six_dir = common.sets("six")[0]
    sizes = [(rows(six_dir, name, "branches.csv"), rows(six_dir, name, "log.csv")) for name in sorted(os.listdir(six_dir))]
    print("the six districts, of %d to %d branches and %d to %d log rows, each run limited to %d s:" % (
        min(s[0] for s in sizes), max(s[0] for s in sizes), min(s[1] for s in sizes), max(s[1] for s in sizes), limit))
    six = common.run(common.SECOND)
    print(common.lines(six))
    print()
    ok = small["accepted"] and not six["accepted"] and six["stopped"].startswith("the run on") and len(six["districts"]) == 1
    print("the second solution is right where it is given the time and is stopped at the limit on the first of the six"
          if ok else "UNEXPECTED: not (accepted on the small districts and stopped at the limit on the six)")


if __name__ == "__main__":
    main()
