"""Defective routes, measured by the verifier: the reference with one check left out or done the obvious way, each a
complete program run through tests/grade.py on the six hidden fans exactly as a submission.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ROUTES = [("gyroscopic coupling left out (the standstill frequencies of the new rotor)", dict(skip={"gyro"})),
          ("forward-whirl critical speeds only", dict(skip={"backward"})),
          ("rotor changes dated by the register's entry date", dict(skip={"entered"})),
          ("the test modeled with the rotor as it is now", dict(skip={"test_rotor"})),
          ("the test modeled with the rotor as built", dict(skip={"datasheet_rotor"})),
          ("shaft revisions left out", dict(skip={"shaft"})),
          ("the latest test, whatever its condition", dict(skip={"condition"})),
          ("the first (commissioning) test", dict(skip={"first"})),
          ("records taken at face value: latest test, rotor as it is now, entry dates", dict(skip={"condition", "test_rotor", "entered"}))]
T = C.truth(); PK = sorted(T)
print("Routes as complete programs through tests/grade.py (run as %s); six hidden fans; accepted when at most %d is "
      "wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("%-78s %5s  %s" % ("route", "wrong", "fans wrong (larger signed deviation of the two critical speeds)"))
for name, kw in ROUTES:
    r = C.verify(C.program(**kw))
    bad = ["%s %+.3f" % (p, C.worst(r["packages"][p])) if C.worst(r["packages"][p]) is not None else "%s error" % p
           for p in PK if not r["packages"][p]["right"]]
    print("%-78s %5d  %s  %s" % (name, r["wrong"], ", ".join(bad), "accepted" if r["accepted"] else "rejected"))
