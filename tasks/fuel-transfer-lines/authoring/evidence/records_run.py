"""records_run.py: programs written to the visible results, and sound variations. Writes records_run.txt.

Every program is solution/lines.py with one change (variants.py). Each is run on the two examples, whose
results a program's author has, and on the six sites.
"""
import common
import variants

out = common.Sheet(__file__)
EXAMPLES = ["east_depot", "north_quay"]
problems = []


def both(name):
    program = common.written(variants.make(name), "lines.py")
    return common.run(program, "beside", only=EXAMPLES), common.run(program, "six")


def out_of_band(verdict):
    return {site: note.get("records_out_of_band") for site, note in verdict["sites"].items()}


out.say("programs that reproduce the examples and leave something out")
for name, (what, _) in variants.WRITTEN_TO_THE_EXAMPLES.items():
    examples, six = both(name)
    out.say()
    out.say("%s: %s" % (name, what))
    out.account("  the two examples", examples)
    out.account("  the six sites", six)
    missed = [site for site, n in out_of_band(six).items() if n]
    out.say("  sites with records out of band: %d of 6 (%s)" % (len(missed), ", ".join("%s %d" % (s, out_of_band(six)[s]) for s in missed)))
    if not examples["accepted"] or six["accepted"]:
        problems.append(name)
out.say()
out.say("no survey order at all")
for name, (what, _) in variants.NO_ORDER.items():
    examples, six = both(name)
    out.account("  the two examples", examples)
    out.account("  the six sites", six)
    if examples["accepted"] or six["accepted"]:
        problems.append(name)
out.say()
out.say("sound variations of the reference")
for name, (what, _) in variants.SOUND.items():
    examples, six = both(name)
    out.say()
    out.say("%s: %s" % (name, what))
    out.account("  the two examples", examples)
    out.account("  the six sites", six)
    if not (examples["accepted"] and six["accepted"]):
        problems.append(name)
out.say()
out.say("records: %s" % ("every program ends as it should" if not problems else "PROBLEM with " + ", ".join(problems)))
out.close()
