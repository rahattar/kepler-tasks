"""Programs that stop short of the reference, each made from solution/airflow.py by one change.

The reference reads its `MODE` line; every variant is the reference with that one line replaced.

    worked_on    surveys the airways worked on since their last survey, and nothing else: stoppings as the
                 register books them, no fan read
    no_fan       finds the open stopping and surveys it, reads no fan
    as_booked    reads a fan with what is left of the allowance, takes every stopping as booked
    worked_out   the reference's records, but the open stopping's resistance worked out from the campaigns
                 and not surveyed (a sound variation: it is accepted)
    no_order     the reference with no survey order placed at all: every airway from its latest survey on file
"""
import atexit
import os
import tempfile

import common

MODES = {"worked_on": "legible", "no_fan": "stopping", "as_booked": "fan", "worked_out": "derive", "no_order": "full"}
SAYS = {"worked_on": "the airways worked on since their last survey, and nothing else",
        "no_fan": "the open stopping found and surveyed, no fan read",
        "as_booked": "a fan read with what is left of the allowance, every stopping as booked",
        "worked_out": "the open stopping's resistance worked out from the campaigns, not surveyed",
        "no_order": "no survey order placed: every airway from its latest survey on file, no fan read"}
ORDER = "    got = d.survey(order)\n"


def build(which):
    with open(common.REFERENCE) as handle:
        text = handle.read()
    line = 'MODE = "full"\n'
    assert text.count(line) == 1
    text = text.replace(line, 'MODE = "%s"\n' % MODES[which])
    if which == "no_order":
        assert text.count(ORDER) == 1
        text = text.replace(ORDER, "    got = {}; fan = None\n")
    fd, path = tempfile.mkstemp(prefix="variant_%s_" % which, suffix=".py")
    with os.fdopen(fd, "w") as out:
        out.write(text)
    os.chmod(path, 0o644)
    atexit.register(lambda: os.path.exists(path) and os.unlink(path))
    return path
