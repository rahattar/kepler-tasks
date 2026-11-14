"""variants.py: programs made from solution/lines.py by one change each, as text.

Each entry is (what the program does, [(text of the reference, text that replaces it), ...]). `make(name)`
returns the program's text and refuses to if a piece of the reference it is to replace is not there exactly
once, so a variant can never quietly be the reference.

WRITTEN_TO_THE_EXAMPLES   programs that reproduce both examples' results and leave something out
NO_ORDER                  the reference with the survey order left out altogether
SOUND                     other ways of doing what the reference does; these have to be accepted
"""
import os

REFERENCE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "solution", "lines.py")
ORDER = "    order = list(dict.fromkeys(worked_on + sorted(narrower) + sorted(moving)))[:site.allowance]\n"
FIND = "    worked_on, narrower, moving = pipes_to_survey(site, on_file)\n"

WRITTEN_TO_THE_EXAMPLES = {
    "covering_jobs_only": ("surveys the pipes whose covering was worked on since the last campaign, and nothing else",
                           [(FIND, FIND + "    narrower, moving = {}, []\n")]),
    "no_division_check": ("as the reference, but never compares a pair's surveyed division with one pressure drop",
                          [(FIND, FIND + "    narrower = {}\n")]),
    "no_trend_check": ("as the reference, but never compares a pipe's coefficient from campaign to campaign",
                       [(FIND, FIND + "    moving = []\n")]),
    "bore_of_the_register": ("finds the narrower pipe and surveys it, then takes a coefficient from the new reading with the bore of the register",
                             [("    bore, uo = as_they_stand(site, on_file, narrower, fresh)\n",
                               "    bore, uo = as_they_stand(site, on_file, {}, fresh)\n")]),
    "bore_from_the_file": ("finds the narrower pipe and does not survey it: its bore from the last campaign on file",
                           [(ORDER, "    order = list(dict.fromkeys(worked_on + sorted(moving)))[:site.allowance]\n")]),
}
NO_ORDER = {
    "no_order": ("the reference with no survey order placed", [(ORDER, "    order = []\n")]),
}
SOUND = {
    "finer_steps": ("120 steps along a pipe for 50", [("STEPS = 50  ", "STEPS = 120 ")]),
    "other_thresholds": ("a pair's drops apart by 3 per cent for 6, a coefficient moved by 8 per cent for 5",
                         [("DROPS_APART = 0.06  ", "DROPS_APART = 0.03  "), ("COEFFICIENT_MOVED = 0.05  ", "COEFFICIENT_MOVED = 0.08  ")]),
    "order_reversed": ("the same pipes ordered in the opposite sequence",
                       [(ORDER, ORDER + "    order = order[::-1]\n")]),
}
EVERY = dict(WRITTEN_TO_THE_EXAMPLES, **NO_ORDER, **SOUND)


def make(name):
    with open(REFERENCE) as handle:
        text = handle.read()
    for old, new in EVERY[name][1]:
        if text.count(old) != 1:
            raise SystemExit("variants.py: %s: %r is in the reference %d times" % (name, old.strip()[:60], text.count(old)))
        text = text.replace(old, new)
    return text
