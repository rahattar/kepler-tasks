"""Programs made from the reference by one change each.

`ROUTES` are ways of stopping short: each is the reference with one step left out or one reading taken on
trust. `SOUND` are other sound ways of taking a step, which must all be accepted. Each change replaces one
passage of solution/ropes.py, and `make` refuses to go on if the passage is not there exactly once, so a
change can never silently become no change.
"""
import common

SETTLE_VERDICT = """                if lost.std() > 0 and laid.std() > 0:
                    verdict = np.corrcoef(lost, laid[::-1])[0, 1] > np.corrcoef(lost, laid)[0, 1]
"""
MIRROR_TEST = "        changed.append(end_for_end < 0.5 * as_written)\n"
TURNED_LINE = "    turned = [changed[k] and from_dead_end[k] == from_dead_end[k + 1] for k in range(K - 1)]\n"
DIAMETER_LINE = "        diameter = profile[k][::-1] if other_way[k] != from_dead_end[k] else profile[k]\n"
HALF_LINE = "            half = 0.5 * (days[k] + until)\n"
TENSION_LINE = "        tension = ((log[\"hook_load_t\"].to_numpy(float) + float(row[\"block_mass_t\"])) * 1e3 * G\n"
WEIGHT_LINE = "            total[order] += weight * 10.0 ** (-c) * np.exp(-delta * centre) * series\n"
MEETS_LINE = "            meets = self.H - (self.L - offset - place) / parts          # hook height with the sheave on the element\n"
NOMINAL_LINE = "        nominal = np.full(x.size, float(np.median(profile[0])))\n"

ROUTES = [
    ("as_written",
     "RS-4 on the surveys as written: damage summed at each station, no survey laid against another",
     [(MIRROR_TEST, "        changed.append(False)\n")]),
    ("all_turns",
     "every survey that mirrors the one before is taken for a rope turned end for end",
     [(SETTLE_VERDICT, "                pass\n")]),
    ("all_from_other_end",
     "every survey that mirrors the one before is taken for a survey started from the other end; no rope is followed",
     [(TURNED_LINE, "    turned = [False] * (K - 1)\n    flip, from_dead_end = False, []\n    for k in range(K):\n"
                    "        from_dead_end.append(flip)\n        flip = flip != (k < K - 1 and changed[k])\n")]),
    ("places_from_dead_end",
     "a sheave's place on the rope, a + p (H - h), is taken as x, which is measured from the drum anchorage",
     [(MEETS_LINE, "            meets = self.H - (place - offset) / parts\n")]),
    ("no_block_mass",
     "the tension is reckoned from the hook load alone",
     [(TENSION_LINE, "        tension = ((log[\"hook_load_t\"].to_numpy(float) + 0.0 * float(row[\"block_mass_t\"]) + 1e-9) * 1e3 * G\n")]),
    ("drum_as_sheave",
     "a bending over the drum is counted like a bending over a sheave",
     [(WEIGHT_LINE, "            total[order] += 10.0 ** (-c) * np.exp(-delta * centre) * series\n")]),
]

SOUND = [
    ("turn_at_a_third",
     "a turn is put a third of the way into its gap between two surveys",
     [(HALF_LINE, "            half = days[k] + (until - days[k]) / 3.0\n")]),
    ("turn_at_two_thirds",
     "a turn is put two thirds of the way into its gap",
     [(HALF_LINE, "            half = days[k] + 2.0 * (until - days[k]) / 3.0\n")]),
    ("mirror_by_correlation",
     "a survey is taken to mirror the one before when it correlates better with it end for end than as written",
     [(MIRROR_TEST, "        changed.append(np.corrcoef(profile[k + 1], profile[k][::-1])[0, 1] > np.corrcoef(profile[k + 1], profile[k])[0, 1] + 0.3)\n")]),
    ("mirror_strict",
     "a survey is taken to mirror the one before only when end for end fits four times better",
     [(MIRROR_TEST, "        changed.append(end_for_end < 0.25 * as_written)\n")]),
    ("end_by_first_survey",
     "the bendings that settle which end a run of surveys was counted from are reckoned with the first survey's diameters",
     [(NOMINAL_LINE, "        nominal = profile[0].copy()\n")]),
    ("elements_not_diameters",
     "elements are followed for their bendings, but each diameter is read at the station as written (the thinning moves N by a few per cent only)",
     [(DIAMETER_LINE, "        diameter = profile[k]\n")]),
    ("nominal_diameter",
     "the diameter as new is used in N for every bending; the surveys serve only to settle the rope",
     [(DIAMETER_LINE, "        diameter = np.full(x.size, float(np.median(profile[0])))\n")]),
    ("longer_series",
     "eight terms of the power series in ln S in place of five",
     [("TERMS = 5 ", "TERMS = 8 ")]),
]


def make(changes):
    """The reference's text with the changes made, as a program file."""
    with open(common.REFERENCE) as handle:
        text = handle.read()
    for old, new in changes:
        if text.count(old) != 1:
            raise SystemExit("variants.py: a passage it changes is no longer in solution/ropes.py exactly once:\n" + old)
        text = text.replace(old, new)
    return common.as_file(text)
