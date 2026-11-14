"""The second solution, written apart from the reference, in two forms: naive_airflow.py, right and too slow, and
fast_airflow.py, the same method with its two solvers made fast, right and inside the limit.

    python3 naive_run.py > naive_run.txt

naive_airflow.py is run on the seven small districts with the limit set aside, where it has to be accepted,
and then on the six districts at the limit, where the checker has to stop it. fast_airflow.py is run on the
small districts, the three beside the program and the six at the limit, and has to be accepted on all.
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
    print()
    print("authoring/evidence/fast_airflow.py, the same method: the district without its fans solved by sparse Newton")
    print("from the last state and kept for every log entry, the fans carried by the rule of VS-4 section 5 and")
    print("not integrated")
    print()
    print("the seven small districts, each run limited to %d s:" % limit)
    fs = common.run(common.FAST, "small")
    print(common.lines(fs))
    print()
    print("the three packages beside the program, each run limited to %d s:" % limit)
    fb = common.run(common.FAST, "beside")
    print(common.lines(fb))
    print()
    print("the six districts, each run limited to %d s:" % limit)
    f6 = common.run(common.FAST)
    print(common.lines(f6))
    times = [note["seconds"] for note in f6["districts"].values()]
    cpu = [note["cpu_seconds"] for note in f6["districts"].values()]
    widest = max(note.get("largest_error_over_band", 9e9) for s_ in (fs, fb, f6) for note in s_["districts"].values())
    print("  runs of %.1f to %.1f s, %.1f to %.1f s of CPU; the limit of %d s is %.1f times the slowest" % (
        min(times), max(times), min(cpu), max(cpu), limit, limit / max(max(times), max(cpu))))
    print("  widest departure of fast_airflow.py from the sealed results, all sixteen districts: %.2f of the band" % widest)
    print()
    ok = fs["accepted"] and fb["accepted"] and f6["accepted"]
    print("the same method made fast is accepted on all three sets, inside the limit"
          if ok else "UNEXPECTED: fast_airflow.py is not accepted everywhere")


if __name__ == "__main__":
    main()
