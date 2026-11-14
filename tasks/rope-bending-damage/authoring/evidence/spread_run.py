"""Other sound ways of taking a step, each through the verifier's bench; and how much the day of a turn matters.

    python3 spread_run.py > spread_run.txt

variants.SOUND are the reference with one step taken another defensible way. All must be accepted on the six
works and on the visible ones, and the band has to be at least twice the widest departure any of them shows.
After them, two programs that are not sound choices but mark the edge: a turn put at the very start and at
the very end of its gap between two surveys. They too must stay inside the band, or a result would hang on a
day that no record gives.
"""
import sys

import common
import variants

EDGES = [("turn_at_start", "a turn is put at the first moment of its gap", 0.0),
         ("turn_at_end", "a turn is put at the last moment of its gap", 1.0)]


def main():
    visible = common.visible_as_works()
    widest_sound, bad = 0.0, 0
    print("sound variations\n")
    for name, what, changes in variants.SOUND:
        program = variants.make(changes)
        six, seen = common.judge(program), common.judge(program, visible)
        wide = max(common.widest(six) or 9.9, common.widest(seen) or 9.9)
        widest_sound = max(widest_sound, wide)
        bad += not (six["accepted"] and seen["accepted"])
        print("%-22s %s\n    the six works: %s, widest %.2f of the band; the visible works: %s, widest %.2f"
              % (name, what, "accepted" if six["accepted"] else "NOT ACCEPTED", common.widest(six) or 9.9,
                 "accepted" if seen["accepted"] else "NOT ACCEPTED", common.widest(seen) or 9.9))
    reference = max(common.widest(common.judge(common.REFERENCE)), common.widest(common.judge(common.REFERENCE, visible)))
    widest_sound = max(widest_sound, reference)
    print("\nthe reference itself: widest %.2f of the band" % reference)
    print("widest departure of a sound program: %.2f of the band; the band is %.1f times that" % (widest_sound, 1.0 / widest_sound))
    print("\nthe day of a turn, at its two edges\n")
    for name, what, share in EDGES:
        program = variants.make([(variants.HALF_LINE, "            half = days[k] + %.1f * (until - days[k])\n" % share)])
        six, seen = common.judge(program), common.judge(program, visible)
        bad += not (six["accepted"] and seen["accepted"])
        print("%-22s %s\n    the six works: %s, widest %.2f of the band; the visible works: %s, widest %.2f"
              % (name, what, "accepted" if six["accepted"] else "NOT ACCEPTED", common.widest(six) or 9.9,
                 "accepted" if seen["accepted"] else "NOT ACCEPTED", common.widest(seen) or 9.9))
    problem = bad or widest_sound > 0.5
    print("\n%d programs, %d not accepted somewhere" % (len(variants.SOUND) + len(EDGES), bad))
    if problem:
        print("PROBLEM")
    return 1 if problem else 0


if __name__ == "__main__":
    sys.exit(main())
