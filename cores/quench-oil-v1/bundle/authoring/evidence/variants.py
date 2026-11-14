"""Programs that stop short of the reference, made from solution/quench.py by changing one thing or two each.

  register           a charge is a line of the register, and only what the oil log shows renewed is sampled:
                     one sample for each renewed system. What is left of the allowance is not used.
  divided_only       tanks are sorted into charges by their analyses, as the reference does, so the divided
                     system's second charge is sampled; kept charges are not looked at. One sample is left over.
  divided_spare      the same, with the sample left over spent on the first kept system the register lists.
  changing_only      a charge is a line of the register, but a kept charge whose analyses climb faster than
                     ageing is sampled. One sample is left over where the site has a divided system.
  changing_stepped   everything the reference samples is sampled, but a kept charge takes the laboratory's
                     figure for every load instead of running linear in time to it (HT-5 section 5).

The first is what a program becomes when it is written to the two example sites, where every listed system
is one charge, every kept charge ages and the allowance equals the number of systems renewed.
"""
import os
import tempfile

import common

CALL = "    for system, groups in charges_of(tanks, samples).items():\n"
AS_LISTED = ("    as_listed = {system: [sum(groups, [])] for system, groups in charges_of(tanks, samples).items()}\n"
             "    for system, groups in as_listed.items():\n")
LOOK = ("        kept_and_changing = charge[0] not in renewed and changing(\n"
        "            [(date, oil[0]) for date, oil in analyses.get(charge, [])])\n")
NO_LOOK = "        kept_and_changing = False\n"
ORDER = "    order = list(first.values())\n"
SPARE = ORDER + '''    for t in tanks:                                      # the sample left over, on the first kept system
        if len(order) >= int(site["lab_samples"]):
            break
        if t["oil_system"] not in renewed and charge_of[t["tank"]] not in first:
            first[charge_of[t["tank"]]] = t["tank"]
            order.append(t["tank"])
'''
FOLLOW = "            oil = tuple(a + share * (b - a) for a, b in zip(last, now))\n"
STEP = "            oil = now\n"
KINDS = {
    "register": ((CALL, AS_LISTED), (LOOK, NO_LOOK)),
    "divided_only": ((LOOK, NO_LOOK),),
    "divided_spare": ((LOOK, NO_LOOK), (ORDER, SPARE)),
    "changing_only": ((CALL, AS_LISTED),),
    "changing_stepped": ((FOLLOW, STEP),),
}


def swap(text, old, new):
    assert text.count(old) == 1, "the reference no longer has the line this variant changes: %r" % old
    return text.replace(old, new)


def build(kind):
    """Writes the variant to a temporary file and returns its path."""
    with open(common.REFERENCE) as handle:
        text = handle.read()
    for old, new in KINDS[kind]:
        text = swap(text, old, new)
    handle, path = tempfile.mkstemp(prefix=kind + "_", suffix=".py")
    with os.fdopen(handle, "w") as out:
        out.write(text)
    os.chmod(path, 0o644)
    return path
