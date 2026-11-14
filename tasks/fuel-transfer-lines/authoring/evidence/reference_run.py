"""reference_run.py: solution/lines.py through the checker, on every set of sites. Writes reference_run.txt.

    the six sites of tests/sites, at the limit the task statement gives
    the three packages a program is written beside, the crew answering for all three
    the nine small sites
"""
import common

out = common.Sheet(__file__)
out.say("solution/lines.py run by tests/rerun.py, limit %d s a run on the clock and in CPU time" % common.LIMIT)
out.say()
six = common.run(common.REFERENCE, "six")
out.account("the six sites", six)
least, most = common.cpu_range(six)
out.say("  CPU time of a run: %.1f to %.1f s; the limit is %.1f times the longest" % (least, most, common.LIMIT / most))
out.say("  largest error at any record: %.2f of the band" % common.largest_error(six))
out.say()
beside = common.run(common.REFERENCE, "beside")
out.account("the two examples and the pending site, the crew answering for all three", beside)
out.say("  largest error at any record: %.2f of the band" % common.largest_error(beside))
out.say()
small = common.run(common.REFERENCE, "small")
out.account("the nine small sites", small)
out.say("  largest error at any record: %.2f of the band" % common.largest_error(small))
out.say()
verdicts = (six, beside, small)
out.say("reference: %s" % ("accepted on all three sets" if all(v["accepted"] for v in verdicts) else "PROBLEM, not accepted somewhere"))
out.close()
