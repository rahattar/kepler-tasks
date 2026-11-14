"""Programs that stop short of the reference, made from solution/quench.py by changing one thing or two each.

  register           what the records say in words: one analysis for each system the oil log shows renewed,
                     every tank's agitation as the register records it. Test bars not read.
  agitation_only     the test bars read for agitation only: each tank's factor is the one its bars fit. The
                     order is the log's; what is left of the allowance is not used.
  changing_only      the test bars read for the oil only: a kept charge whose bars drift is analysed. Every
                     tank's agitation as the register records it.
  spare_on_kept      agitation from the test bars; the analysis left over spent on the first kept system the
                     register lists, without looking at the bars for it.
  changing_stepped   both read; a changing charge takes the laboratory's figure for every load instead of
                     running linear in time to it (HT-5 section 5).

The first is what a program becomes when it is written to the two example sites, where every propeller runs,
every kept charge ages and the allowance equals the number of systems renewed.
"""
import os
import tempfile

import common

DETECT = ("        if drift([b for b, _ in mine], [m for _, m in mine]) < -DRIFT:\n"
          "            moving.add(charge)\n")
NO_DETECT = "        pass\n"
FIT = "        agitation[t[\"tank\"]] = min(miss, key=miss.get)\n"
AS_STATED = "        agitation[t[\"tank\"]] = stated[t[\"tank\"]]\n"
FOLLOW = "        return tuple(a + share * (b - a) for a, b in zip(last, now))\n"
STEP = "        return now\n"
ORDER = "    order = list(first.values())\n"
SPARE = ORDER + '''    for t in tanks:                                      # the analysis left over, on the first kept system
        if len(order) >= int(site["lab_samples"]):
            break
        if charge_of[t["tank"]][0] not in renewed and charge_of[t["tank"]] not in first:
            first[charge_of[t["tank"]]] = t["tank"]
            order.append(t["tank"])
'''
KINDS = {
    "register": ((DETECT, NO_DETECT), (FIT, AS_STATED)),
    "agitation_only": ((DETECT, NO_DETECT),),
    "changing_only": ((FIT, AS_STATED),),
    "spare_on_kept": ((DETECT, NO_DETECT), (ORDER, SPARE)),
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
