"""second_run.py: the second solution, in its plain form and in its fast form. Writes second_run.txt.

The second solution was written apart from the reference (see second_lines.py). Two things are shown with it.

  The band. Both forms are compared with the sealed results; how far a separately written, correct program is
  from them is what the band has to leave room for.

  The limit. plain_lines.py is the method as first written. It is run on three small sites with the limit
  lifted, to show that it is right, and then on the six at the limit. second_lines.py is the same method made
  fast, and is run on every set at the limit.
"""
import common

LIFTED = 1800
SHOWN = ["west_jetty", "upper_yard", "kiln_road"]            # small sites: both conditions, a narrowing pipe, a declining covering

out = common.Sheet(__file__)
out.say("authoring/evidence/plain_lines.py: the second solution as first written")
out.say()
plain_small = common.run(common.PLAIN, "small", limit=LIFTED, only=SHOWN)
out.account("three small sites, the limit lifted to %d s" % LIFTED, plain_small)
out.say("  CPU time of a run: %.1f to %.1f s; largest error at any record: %.2f of the band"
        % (common.cpu_range(plain_small) + (common.largest_error(plain_small),)))
out.say()
plain_six = common.run(common.PLAIN, "six")
out.account("the six sites, limit %d s" % common.LIMIT, plain_six)
out.say()
out.say("authoring/evidence/second_lines.py: the same method made fast")
out.say()
fast = {}
for which, title in (("small", "the nine small sites"), ("beside", "the two examples and the pending site, the crew answering for all three"),
                     ("six", "the six sites")):
    fast[which] = common.run(common.SECOND, which)
    out.account("%s, limit %d s" % (title, common.LIMIT), fast[which])
    out.say("  CPU time of a run: %.1f to %.1f s; largest error at any record: %.2f of the band"
            % (common.cpu_range(fast[which]) + (common.largest_error(fast[which]),)))
    out.say()
widest = max(common.largest_error(v) for v in list(fast.values()) + [plain_small])
out.say("widest departure of the second solution from the sealed results, either form, any set: %.2f of the band" % widest)
ok = (plain_small["accepted"] and not plain_six["accepted"] and "used up" in plain_six["stopped"] and len(plain_six["sites"]) == 1
      and all(v["accepted"] for v in fast.values()))
out.say("plain form: %s on the small sites; on the six, %s" % ("accepted" if plain_small["accepted"] else "NOT accepted",
                                                              plain_six["stopped"] or "not stopped"))
out.say("fast form: %s" % ("accepted on all three sets inside the limit" if all(v["accepted"] for v in fast.values()) else "NOT accepted somewhere"))
out.say("second solution: %s" % ("as expected" if ok else "PROBLEM"))
out.close()
