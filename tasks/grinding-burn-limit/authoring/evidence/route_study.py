"""Defective routes, measured by the verifier: the reference with one check left out or done the obvious way, each a
complete program run through tests/grade.py on the seven hidden jobs exactly as a submission.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ROUTES = [("every power record, whatever the wheel and coolant", dict(skip={"period"})),
          ("the wheel's state averaged over the records, not the end of the dressing interval", dict(skip={"interval"})),
          ("the first lot's certificate, not the part's lot", dict(skip={"lot"})),
          ("the first tempering temperature of a re-tempered lot", dict(skip={"retemper"})),
          ("the programmed work speed, not the table's speed limit", dict(skip={"speed"})),
          ("the job sheet's coolant temperature while the chiller is out", dict(skip={"chiller"})),
          ("a dressing interval in parts taken as mm3/mm per part", dict(skip={"parts"})),
          ("one idle power for all sessions", dict(skip={"idle"})),
          ("the records at face value: programmed speed and coolant temperature, every power record",
           dict(skip={"speed", "chiller", "period"}))]
T = C.truth(); PK = sorted(T)
print("Routes as complete programs through tests/grade.py (run as %s); seven hidden jobs; accepted when at most %d is "
      "wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("%-92s %5s  %s" % ("route", "wrong", "jobs wrong (signed relative deviation from the truth)"))
for name, kw in ROUTES:
    r = C.verify(C.program(**kw))
    bad = ["%s %+.3f" % (p, C.dev(r["packages"][p])) if C.dev(r["packages"][p]) is not None else "%s error" % p
           for p in PK if not r["packages"][p]["right"]]
    print("%-92s %5d  %s  %s" % (name, r["wrong"], ", ".join(bad), "accepted" if r["accepted"] else "rejected"))
