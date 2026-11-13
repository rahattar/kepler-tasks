"""Programs that stop short of the reference. Four are written to the visible results: each is accepted on both
examples, and all but the sound variation fail on the six districts. The fifth places no survey order and is
out of band on the examples themselves.

    python3 records_run.py > records_run.txt
"""
import common
import variants


def main():
    print("programs made from the reference by variants.py, one change each, run by tests/judge_airflow.judge")
    print()
    surprises = 0
    for which in ("worked_on", "no_fan", "as_booked", "worked_out", "no_order"):
        program = variants.build(which)
        print("%s: %s" % (which, variants.SAYS[which]))
        beside = common.run(program, "beside")
        examples = {name: note for name, note in beside["districts"].items() if name in ("north_field", "east_decline")}
        fine = all(note.get("points_out_of_band") == 0 for note in examples.values())
        print("  the two examples: %s" % ("accepted" if fine else "not accepted (points out of band: %s)" % ", ".join(
            "%s %d" % (name, note.get("points_out_of_band", -1)) for name, note in examples.items())))
        six = common.run(program)
        print(common.lines(six, "  "))
        out = {name: note.get("points_out_of_band", -1) for name, note in six["districts"].items()}
        print("  districts with points out of band: %d of %d; points out at each: %s" % (
            sum(1 for v in out.values() if v != 0), len(out), ", ".join("%s %d" % kv for kv in out.items())))
        want = which == "worked_out"
        if fine != (which != "no_order") or six["accepted"] != want:
            surprises += 1
            print("  UNEXPECTED")
        print()
    print("nothing unexpected" if not surprises else "UNEXPECTED: %d" % surprises)


if __name__ == "__main__":
    main()
