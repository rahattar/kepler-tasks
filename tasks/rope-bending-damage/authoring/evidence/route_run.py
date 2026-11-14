"""Programs that stop short, each through the verifier's bench.

    python3 route_run.py > route_run.txt

Each program is the reference with one step left out or one reading taken on trust (variants.ROUTES). For each:
what the bench says on the two examples (the works whose results an author has), on the pending works, and on
the six works. Every one of them must be refused on the six works; then, for each of the six works, how many
of the routes it stops.
"""
import sys

import common
import variants


def main():
    examples = common.visible_as_works(("examples",))
    pending = common.visible_as_works(("pending",))
    stops = {spec["works"]: [] for spec in common.HIDDEN}
    wrong = 0
    for name, what, changes in variants.ROUTES:
        program = variants.make(changes)
        on_examples = common.judge(program, examples)
        on_pending = common.judge(program, pending)
        on_six = common.judge(program)
        for works in common.works_out(on_six):
            stops[works].append(name)
        least = min((note["widest"] for note in on_six["trials"] if note.get("rows_out")), default=0.0)
        print("%s: %s" % (name, what))
        print("    the two examples: %s" % ("accepted" if on_examples["accepted"] else "not accepted (%s)" % ", ".join(common.ropes_out(on_examples))))
        print("    the pending works: %s" % ("every row right" if on_pending["accepted"] else ", ".join(common.ropes_out(on_pending)) + " rows out"))
        print("    the six works: %s; works with rows out: %d of 6 (%s)" % ("ACCEPTED" if on_six["accepted"] else "not accepted",
              len(common.works_out(on_six)), ", ".join(common.ropes_out(on_six))))
        print("    its widest departure at the works it misses least: %.1f bands\n" % least)
        wrong += on_six["accepted"]
    print("how many of the %d routes each works stops" % len(variants.ROUTES))
    for works, by in stops.items():
        print("    %-12s %d (%s)" % (works, len(by), ", ".join(by)))
    few = [works for works, by in stops.items() if len(by) < 3]
    print("\n%d routes, %d accepted on the six works; works that stop fewer than three routes: %s" % (len(variants.ROUTES), wrong, ", ".join(few) or "none"))
    if wrong or few:
        print("PROBLEM")
    return 1 if wrong or few else 0


if __name__ == "__main__":
    sys.exit(main())
