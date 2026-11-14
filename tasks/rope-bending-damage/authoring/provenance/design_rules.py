"""Recomputes, from the generator and the shipped files, the rules the data were designed to.

    python3 design_rules.py > ../evidence/design_rules.txt

Each line is a rule with the figures found; a rule that does not hold is marked PROBLEM and the script ends
with status 1. The figures come from works.draw (the same draw the shipped packages were written from, which
regenerate.py checks) and from rope.life, the sealed definition; no program that reads a package is run here.
"""
import hashlib
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
import rope  # noqa: E402
import works  # noqa: E402

STATED_CRANES, STATED_MOVEMENTS, STATED_ROPE_M = 6, 600000, 400.0      # the task statement's "up to"
held, failed = 0, 0


def rule(holds, text):
    global held, failed
    held += bool(holds)
    failed += not holds
    print(("- " if holds else "- PROBLEM: ") + text)


def span(values, form="%g"):
    return (form + " to " + form) % (min(values), max(values))


def file_hashes(folder):
    out = {}
    for base, _, names in os.walk(folder):
        for name in names:
            with open(os.path.join(base, name), "rb") as handle:
                out[os.path.join(base, name)] = hashlib.sha256(handle.read()).hexdigest()
    return out


def bands_out(reading, truth):
    """(stations more than a band out, widest departure in bands)."""
    depart = np.abs(reading - truth) / (works.BAND * truth.max())
    return int((depart > 1.0).sum()), float(depart.max())


def main():
    drawn = {spec["works"]: works.draw(spec) for spec in works.WORKS}
    by_role = {role: [s for s in works.WORKS if s["role"] == role] for role in ("example", "pending", "hidden")}
    names = [s["works"] for s in works.WORKS]
    rule(len(names) == len(set(names)) == 9 and [len(by_role[r]) for r in ("example", "pending", "hidden")] == [2, 1, 6],
         "9 works: 2 that go out with their results, 1 that goes out without, 6 the program is run on; no name twice")
    for spec in by_role["example"]:
        rule(os.path.isfile(os.path.join(works.BUNDLE, works.PLACE["example"], spec["works"], "expected.csv")),
             "%s carries expected.csv" % spec["works"])
    for spec in by_role["pending"]:
        folder = os.path.join(works.BUNDLE, works.PLACE["pending"], spec["works"])
        rule(sorted(os.listdir(folder)) == ["cranes.csv", "movements.csv", "sheaves.csv", "surveys.csv"],
             "%s carries its four record files and no results" % spec["works"])
    visible = file_hashes(os.path.join(works.BUNDLE, "environment", "data"))
    hidden = file_hashes(os.path.join(works.BUNDLE, "tests", "works"))
    shared = set(visible.values()) & set(hidden.values())
    rule(not shared, "no file of a works the program is run on is a file of a visible works (%d shared of %d)" % (len(shared), len(hidden)))

    def cranes_of(role):
        return [(spec, c) for spec in by_role[role] for c in drawn[spec["works"]][1]]

    seen = cranes_of("example") + cranes_of("pending")
    unseen = cranes_of("hidden")
    moves_seen = [sum(len(c["log"]) for c in drawn[s["works"]][1]) for s in by_role["example"] + by_role["pending"]]
    moves_unseen = [sum(len(c["log"]) for c in drawn[s["works"]][1]) for s in by_role["hidden"]]
    longest = max(c["L"] for _, c in unseen)
    rule(max(moves_unseen) <= STATED_MOVEMENTS and longest <= STATED_ROPE_M and max(s["cranes"] for s in by_role["hidden"]) <= STATED_CRANES,
         "a works the program is run on has %d cranes, %s movements and ropes of up to %g m; the statement's most is %d cranes, %d movements, %g m"
         % (by_role["hidden"][0]["cranes"], span(moves_unseen, "%d"), longest, STATED_CRANES, STATED_MOVEMENTS, STATED_ROPE_M))
    rule(True, "a visible works has 5 cranes and %s movements" % span(moves_seen, "%d"))
    rule(all(c["what"] == "sound" for _, c in cranes_of("example")),
         "in the two examples no rope was turned and every survey was counted from the drum anchorage")
    pending = {c["crane"]: c for _, c in cranes_of("pending")}
    kinds = sorted(c["what"] for c in pending.values())
    rule(kinds == ["dead_end", "sound", "sound", "sound", "turned"],
         "the pending works has one rope of each kind: " + "; ".join(
             "%s turned on day %.2f" % (n, c["turn_day"]) if c["what"] == "turned" else
             "%s surveyed from the dead end from day %.2f on" % (n, c["dead_end_from"])
             for n, c in pending.items() if c["what"] != "sound"))
    tally = {}
    for spec, c in unseen:
        tally.setdefault(c["what"], []).append(c["crane"])
    rule(len(tally.get("turned", [])) == 5 and len(tally.get("dead_end", [])) == 6 and len(tally.get("both", [])) == 1,
         "the six works: %d ropes turned (%s), %d surveyed from the dead end (%s), %d both, first surveyed from the dead end and later turned (%s), %d sound"
         % (len(tally["turned"]), ", ".join(tally["turned"]), len(tally["dead_end"]), ", ".join(tally["dead_end"]),
            len(tally["both"]), ", ".join(tally["both"]), len(tally["sound"])))
    sound_works = [s["works"] for s in by_role["hidden"] if all(c["what"] == "sound" for c in drawn[s["works"]][1])]
    rule(sound_works == ["coil_yard"], "one of the six works is sound throughout: %s" % ", ".join(sound_works))
    mixes = sorted(set((s["turned"], s["dead_end"], s["both"]) for s in by_role["hidden"]))
    rule((1, 1, 0) in mixes and len(mixes) >= 4,
         "ropes turned, surveyed from the dead end, both, by works: %s; the pending works has 1, 1, 0"
         % "; ".join("%s %d, %d, %d" % (s["works"], s["turned"], s["dead_end"], s["both"]) for s in by_role["hidden"]))

    # what each event does to a result, from the sealed definition
    worst_plain, least_out_listed, least_out_turn, least_out_hedge = 0.0, 10 ** 6, 10 ** 6, 10 ** 6
    least_rise, most_rise_elsewhere, most_ratio_event, least_ratio_elsewhere = 9.0, 0.0, 0.0, 9.0
    edge_widest = 0.0
    for spec, c in seen + unseen:
        days = drawn[spec["works"]][0]
        event_gaps = set()
        if c["turn_day"] is not None:
            event_gaps.add(max(k for k in range(len(days)) if days[k] < c["turn_day"]))
        if c["first_reversed"] is not None:
            event_gaps.add(c["first_reversed"] - 1)
        for k in range(len(days) - 1):
            earlier, later = works.as_written(c, k, days[k]), works.as_written(c, k + 1, days[k + 1])
            rise = float((later - earlier).max())
            ratio = float(np.sum((later - earlier[::-1]) ** 2) / np.sum((later - earlier) ** 2))
            if k in event_gaps:
                least_rise, most_ratio_event = min(least_rise, rise), max(most_ratio_event, ratio)
            else:
                most_rise_elsewhere = max(most_rise_elsewhere, rise)
                if k >= 2:
                    least_ratio_elsewhere = min(least_ratio_elsewhere, ratio)
        if c["what"] == "sound":
            continue
        truth = c["damage"]
        seed = None
        # the readings a program can take of the same records
        never_turned = np.zeros_like(truth)
        if c["turn_day"] is not None:
            # as written: the rope is taken never to have been turned
            crane_only = {k: c[k] for k in ("L", "H", "falls", "block", "eff", "construction", "d", "spacing", "sheaves")}
            for edge, label in ((0.0, "first"), (1.0, "last")):
                gap = max(k for k in range(len(days)) if days[k] < c["turn_day"])
                day = days[gap] + edge * (days[gap + 1] - days[gap]) + (1e-6 if edge == 0.0 else -1e-6)
                moved = element_damage(crane_only, c, days, day)
                edge_widest = max(edge_widest, bands_out(moved, truth)[1])
            never_turned = element_damage(crane_only, c, days, None)
            out, wide = bands_out(never_turned, truth)
            least_out_listed = min(least_out_listed, out)
            out_h, _ = bands_out(0.5 * (never_turned + truth), truth)
            least_out_hedge = min(least_out_hedge, out_h)
        if c["first_reversed"] is not None and c["what"] == "dead_end":
            # every mirroring a turn: the rope is taken to have been turned in the gap before that survey
            crane_only = {k: c[k] for k in ("L", "H", "falls", "block", "eff", "construction", "d", "spacing", "sheaves")}
            k = c["first_reversed"]
            as_turn = element_damage(crane_only, c, days, 0.5 * (days[k - 1] + days[k]))
            out, wide = bands_out(as_turn, truth)
            least_out_turn = min(least_out_turn, out)
            out_h, _ = bands_out(0.5 * (as_turn + truth), truth)
            least_out_hedge = min(least_out_hedge, out_h)
    rule(least_out_listed >= 8,
         "every turned rope, visible or not: read as if it had never been turned, at least %d of its stations are more than a band out" % least_out_listed)
    rule(least_out_turn >= 8,
         "every rope surveyed from the dead end: read as a rope turned in the gap before that survey, at least %d of its stations are more than a band out" % least_out_turn)
    rule(least_out_hedge >= 4,
         "the mean of the two readings is no way out: at least %d stations of every such rope are still more than a band out" % least_out_hedge)
    rule(edge_widest < 1.0,
         "the day of a turn does not decide: with the turn put at the first or at the last moment of its gap, no station of any turned rope is more than %.2f of a band out" % edge_widest)
    rule(least_rise >= 0.15 and most_rise_elsewhere <= 0.08,
         "a mirrored survey is plain: across it some station's diameter rises by at least %.2f mm, against %.2f mm at most between any two other surveys (the gauge repeats to about 0.02 mm)"
         % (least_rise, most_rise_elsewhere))
    rule(most_ratio_event <= 0.2 and least_ratio_elsewhere >= 1.2,
         "laid end for end on the survey before, a mirrored survey leaves at most %.2f of the squared difference it leaves as written; any other survey from the third on leaves at least %.2f times as much"
         % (most_ratio_event, least_ratio_elsewhere))

    for label, group in (("visible", seen), ("the six works", unseen)):
        rule(True, "%s: upper block at %s m, ropes of %s m with %s stations, %s falls, greatest damage of a rope %s"
             % (label, span([c["H"] for _, c in group]), span([c["L"] for _, c in group]),
                span([c["damage"].size for _, c in group], "%d"), span([c["falls"] for _, c in group], "%d"),
                span([float(c["damage"].max()) for _, c in group], "%.3f")))
    tall = [c["crane"] for _, c in unseen if c["H"] > max(v["H"] for _, v in seen)]
    long_ = [c["crane"] for _, c in unseen if c["L"] > max(v["L"] for _, v in seen)]
    rule(len(tall) >= 8 and len(long_) >= 5,
         "%d cranes of the six works have the upper block above every visible crane's, and %d have a longer rope than any visible one" % (len(tall), len(long_)))
    gaps = [b - a for spec in works.WORKS for a, b in zip(drawn[spec["works"]][0], drawn[spec["works"]][0][1:])]
    rule(min(gaps) >= 12.7 - 0.006 and max(gaps) <= 17.9 + 0.006, "two surveys of a rope are %s days apart" % span(gaps, "%.1f"))
    margins = []
    for spec, c in seen + unseen:
        if c["turn_day"] is not None:
            days = drawn[spec["works"]][0]
            margins.append(min(abs(c["turn_day"] - d) for d in days))
    rule(min(margins) >= 2.3, "no rope was turned within %.1f days of a survey" % min(margins))
    print("\n%d rules, %d hold" % (held + failed, held))
    return 1 if failed else 0


def element_damage(crane_only, c, days, turn_day):
    """The damage the sealed definition gives the elements of this crane's log for another day of turning (or
    none), with the diameters the surveys really read."""
    L = crane_only["L"]
    x_end = crane_only["spacing"] * (0.5 + np.arange(c["damage"].size))
    day, h_from, h_to, load = c["log"].T
    tension = (load + crane_only["block"]) * 1e3 * rope.G / (crane_only["falls"] * crane_only["eff"])
    low, high = np.minimum(h_from, h_to), np.maximum(h_from, h_to)
    damage = np.zeros(x_end.size)
    edges = list(days) + [np.inf]
    for k in range(len(days)):
        in_epoch = (day >= edges[k]) & (day < edges[k + 1])
        for sheave in crane_only["sheaves"]:
            for before in (True, False):
                if turn_day is None:
                    chosen, place = (in_epoch, x_end) if not before else (np.zeros(day.size, bool), x_end)
                else:
                    chosen = in_epoch & ((day < turn_day) == before)
                    place = L - x_end if before else x_end
                if not chosen.any():
                    continue
                meets = crane_only["H"] - (L - sheave["offset"] - place) / sheave["parts"]
                passed = (low[chosen][:, None] < meets[None, :]) & (meets[None, :] <= high[chosen][:, None])
                N = rope.endurance(tension[chosen][:, None], sheave["D"], c["readings"][k][None, :], crane_only["construction"])
                damage += sheave["weight"] * (passed / N).sum(0)
    return damage


if __name__ == "__main__":
    sys.exit(main())
