"""Defective routes, measured by the verifier: the reference with one check left out or done the obvious way, each a
complete program run through tests/grade.py on the seven hidden chambers exactly as a submission.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ROUTES = [("the chamber sheet's pumps, not the pumps the records' controller reports", dict(skip={"header_pumps"})),
          ("the chamber sheet's gauges for every record, not the gauges each record names", dict(skip={"header_gauges"})),
          ("each gauge's latest calibration for every record, not the one in force on the record's date", dict(skip={"cert_date"})),
          ("every record in the chamber's folder, another chamber's record too", dict(skip={"misfiled"})),
          ("the chamber sheet's crossover pressure, not the controller's", dict(skip={"header_crossover"})),
          ("the chamber sheet's volume after a load lock merge, not the volume of the records' roughing", dict(skip={"volume"})),
          ("every record taken as empty, its load's outgassing not taken out", dict(skip={"record_load"})),
          ("one air leak over all records, through a door seal replacement", dict(skip={"seal"})),
          ("the spool piece left out (its volume and its outgassing)", dict(skip={"spool"})),
          ("the records from before the internals were rebuilt, and the sheet's volume", dict(skip={"internals"})),
          ("the chamber sheet's roughing line, not the rerouted one", dict(skip={"line"})),
          ("the records after a nitrogen vent fitted with the air-vent records", dict(skip={"n2"})),
          ("the cold cathode reading taken as the pressure, no water vapor correction", dict(skip={"water"})),
          ("the roughing pump's speed without the roughing line", dict(skip={"conductance"})),
          ("the roughing line's molecular conductance only", dict(skip={"molecular"})),
          ("each pump at its nominal speed, not its speed curve", dict(skip={"nominal"})),
          ("the job's load left out", dict(skip={"no_load"})),
          ("the records at face value: the sheet's pumps, gauges, crossover and volume, latest calibrations, empty records, one leak, all records",
           dict(skip={"header_pumps", "header_gauges", "cert_date", "misfiled", "header_crossover", "volume", "record_load", "seal",
                      "internals", "n2"}))]
T = C.truth(); PK = sorted(T)
print("Routes as complete programs through tests/grade.py (run as %s); seven hidden chambers; accepted when at most %d is "
      "wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("%-106s %5s  %s" % ("route", "wrong", "chambers wrong (signed deviation from the truth, percent)"))
for name, kw in ROUTES:
    r = C.verify(C.program(**kw))
    bad = ["%s %+.1f" % (p, 100 * C.dev(r["packages"][p])) if C.dev(r["packages"][p]) is not None else "%s error" % p
           for p in PK if not r["packages"][p]["right"]]
    print("%-106s %5d  %s  %s" % (name, r["wrong"], ", ".join(bad), "accepted" if r["accepted"] else "rejected"))
