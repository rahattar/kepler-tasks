"""Programs that stop short of the reference, made from solution/quench.py by changing one thing each.

  register         a charge is a line of the register: one laboratory sample for each listed system whose oil
                   was renewed. What is left of the allowance is not used.
  register_spare   the same, and what is left of the allowance is spent on tanks not yet sampled, in the
                   order the package lists them; a tank whose own sample stands apart from its system's
                   takes its own figures.

  on_file_only     tanks are sorted into charges by their analyses for the oil on file, as the reference
                   does, but the laboratory order is still one sample for each listed system that was renewed,
                   and that sample is taken for every tank of the system.

The first two are what a program becomes when it is written to the two example sites, where every listed
system is one charge and the allowance equals the number of systems renewed. The third has seen that a listed
system can be two charges and has not carried it through to the order.
"""
import os
import tempfile

import common

CALL = "    for system, groups in charges_of(tanks, samples).items():\n"
AS_LISTED = ("    as_listed = {system: [sum(groups, [])] for system, groups in charges_of(tanks, samples).items()}\n"
             "    for system, groups in as_listed.items():\n")
ORDER = "    order = list(first.values())\n"
SPARE = ORDER + '''    for t in tanks:                                      # what is left of the allowance, on unsampled tanks
        if len(order) >= int(site["lab_samples"]):
            break
        if t["oil_system"] in renewed and t["tank"] not in order:
            order.append(t["tank"])
'''
TAKE = "            fresh[charge_of[row[\"sampled_at\"]]] = figures(row)\n"
TAKE_OWN = '''            charge = charge_of[row["sampled_at"]]
            if charge not in fresh:
                fresh[charge] = figures(row)
            elif abs(figures(row)[0] / fresh[charge][0] - 1.0) > APART:
                own[row["sampled_at"]] = figures(row)
'''
USE = "        oil = fresh[charge] if (charge[0] in renewed and p[\"date\"] > renewed[charge[0]]) else on_file[charge]\n"
USE_OWN = '''        oil = fresh[charge] if (charge[0] in renewed and p["date"] > renewed[charge[0]]) else on_file[charge]
        if p["tank"] in own and charge[0] in renewed and p["date"] > renewed[charge[0]]:
            oil = own[p["tank"]]
'''
FRESH = "    fresh = {}\n"


def swap(text, old, new):
    assert text.count(old) == 1, "the reference no longer has the line this variant changes: %r" % old
    return text.replace(old, new)


FIRST = "            first.setdefault(charge, t[\"tank\"])\n"
FIRST_LISTED = "            first.setdefault(charge[0], t[\"tank\"])\n"
TAKE_LISTED = """            for charge in set(charge_of.values()):
                if charge[0] == charge_of[row["sampled_at"]][0]:
                    fresh[charge] = figures(row)
"""


def build(kind):
    """Writes the variant to a temporary file and returns its path."""
    with open(common.REFERENCE) as handle:
        text = handle.read()
    if kind == "on_file_only":
        text = swap(text, FIRST, FIRST_LISTED)
        text = swap(text, TAKE, TAKE_LISTED)
    else:
        text = swap(text, CALL, AS_LISTED)
    if kind == "on_file_only":
        pass
    elif kind == "register_spare":
        text = swap(text, ORDER, SPARE)
        text = swap(text, FRESH, FRESH + "    own = {}\n")
        text = swap(text, TAKE, TAKE_OWN)
        text = swap(text, USE, USE_OWN)
    elif kind != "register":
        raise ValueError(kind)
    handle, path = tempfile.mkstemp(prefix=kind + "_", suffix=".py")
    with os.fdopen(handle, "w") as out:
        out.write(text)
    os.chmod(path, 0o644)
    return path
