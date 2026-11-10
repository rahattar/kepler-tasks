"""Defective routes, measured by the verifier: the reference with one check left out or done the obvious way, each a
complete program run through tests/grade.py on the seven hidden joints exactly as a submission.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ROUTES = [("the joint sheet's plates, not the replacement in the shop log", dict(skip={"plates"})),
          ("the joint sheet's heat of a plate, not the heat whose certificate lists the plate", dict(skip={"sheet_heat"})),
          ("the heat's cast analysis, not the plate's product analysis", dict(skip={"product"})),
          ("another plate's product analysis of the heat, for a plate without its own", dict(skip={"sister"})),
          ("the batch certificate's hydrogen, no moisture pick-up", dict(skip={"exposure"})),
          ("exposure from the first issue, through a return to the oven", dict(skip={"reissue"})),
          ("the joint sheet's electrode batch, not the batch the oven issued to the station", dict(skip={"issued"})),
          ("the climate logger of bay 1 for every station", dict(skip={"logger"})),
          ("mean current x mean voltage for the pulsed runs", dict(skip={"pulse"})),
          ("the sensed voltage as the arc voltage at monitors that sense at the power source", dict(skip={"cable"})),
          ("the cable drop of a pulsed run from its mean current only", dict(skip={"cable_mean"})),
          ("the monitor's current as recorded before its recalibration", dict(skip={"calib"})),
          ("the joint sheet's consumable batch, not the spool fitted later", dict(skip={"spool"})),
          ("every run the station's monitor recorded, other joints' runs too", dict(skip={"foreign"})),
          ("the WPS's nominal current, voltage and travel speed", dict(skip={"nominal"})),
          ("the hardness limit on every run, not only the capping runs", dict(skip={"hard_all"})),
          ("the hydrogen clause only (EN 1011-2 method B)", dict(skip={"no_hardness"})),
          ("the 3D cooling time only (thick-plate formula)", dict(skip={"3d"})),
          ("the 2D cooling time only (thin-plate formula)", dict(skip={"2d"})),
          ("the records at face value: sheet plates, heats and batches, cast analyses, no pick-up, U x I as sensed, all runs",
           dict(skip={"plates", "sheet_heat", "product", "exposure", "pulse", "calib", "spool", "issued", "foreign", "cable"}))]
T = C.truth(); PK = sorted(T)
print("Routes as complete programs through tests/grade.py (run as %s); seven hidden joints; accepted when at most %d is "
      "wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("%-104s %5s  %s" % ("route", "wrong", "joints wrong (signed deviation from the truth, C)"))
for name, kw in ROUTES:
    r = C.verify(C.program(**kw))
    bad = ["%s %+.1f" % (p, C.dev(r["packages"][p])) if C.dev(r["packages"][p]) is not None else "%s error" % p
           for p in PK if not r["packages"][p]["right"]]
    print("%-104s %5d  %s  %s" % (name, r["wrong"], ", ".join(bad), "accepted" if r["accepted"] else "rejected"))
