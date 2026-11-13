"""The reference through the checker: the six districts at the limit, the three packages it was written beside,
and the seven small districts.

    python3 reference_run.py > reference_run.txt
"""
import common
from common import judge_airflow


def main():
    limit = judge_airflow.LIMIT_S
    print("solution/airflow.py, run by tests/judge_airflow.judge")
    print()
    print("the six districts, each run limited to %d s:" % limit)
    six = common.run(common.REFERENCE)
    print(common.lines(six))
    times = [note["seconds"] for note in six["districts"].values()]
    print("  runs of %.1f to %.1f s; the limit of %d s is %.1f times the slowest" % (min(times), max(times), limit, limit / max(times)))
    print("  points: %d at %d districts; largest error at any of them %.2f of the band" % (
        sum(note["points"] for note in six["districts"].values()), len(six["districts"]),
        max(note.get("largest_error_over_band", 9e9) for note in six["districts"].values())))
    print()
    print("the three packages beside the program (the examples against their own results, the pending district")
    print("against its sealed result, the crew answering for all three as it does where the program is checked):")
    beside = common.run(common.REFERENCE, "beside")
    print(common.lines(beside))
    print()
    print("the seven small districts:")
    small = common.run(common.REFERENCE, "small")
    print(common.lines(small))
    print()
    ok = six["accepted"] and beside["accepted"] and small["accepted"]
    print("reference accepted on all three sets" if ok else "UNEXPECTED: the reference is not accepted everywhere")


if __name__ == "__main__":
    main()
