"""Defective routes, measured by the verifier: the reference with one check left out or done the obvious way, each a
complete program run through tests/grade.py on the seven hidden jobs exactly as a submission.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ROUTES = [("the lowest limit over all speeds (the speed-independent bound)", dict(skip={"lobes"})),
          ("the programmed speed, not the machine's speed limit", dict(skip={"speed"})),
          ("the insert pockets of a face mill as its teeth", dict(skip={"inserts"})),
          ("every FRF file taken as receptance", dict(skip={"units"})),
          ("the accelerometer's flank ignored", dict(skip={"sign"})),
          ("the accelerometer's mass left in", dict(skip={"mass"})),
          ("the feed taken along machine X", dict(skip={"feed"})),
          ("every operation taken as climb milling", dict(skip={"milling"})),
          ("the latest test of the assembly, whatever its stickout", dict(skip={"stickout"})),
          ("the first test of the assembly at its stickout (before the spindle work)", dict(skip={"first"})),
          ("the records at face value: programmed speed, pockets, the latest test of the assembly",
           dict(skip={"speed", "inserts", "stickout"}))]
T = C.truth(); PK = sorted(T)
print("Routes as complete programs through tests/grade.py (run as %s); seven hidden jobs; accepted when at most %d is "
      "wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("%-84s %5s  %s" % ("route", "wrong", "jobs wrong (signed relative deviation from the truth)"))
for name, kw in ROUTES:
    r = C.verify(C.program(**kw))
    bad = ["%s %+.3f" % (p, C.dev(r["packages"][p])) if C.dev(r["packages"][p]) is not None else "%s error" % p
           for p in PK if not r["packages"][p]["right"]]
    print("%-84s %5d  %s  %s" % (name, r["wrong"], ", ".join(bad), "accepted" if r["accepted"] else "rejected"))
