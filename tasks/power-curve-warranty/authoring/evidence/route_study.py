"""Defective routes, measured by the verifier: the reference program with one record check left out (or all of them,
which is PP-12 applied to the records as they stand), each a complete program run through tests/grade.py on the six
hidden packages exactly as the verifier runs a submission.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt

A check left out means its fault goes through: a turbine's clock left as stamped; M1's clock taken as right, so the
turbines are aligned to it; the dead barometer replaced by the controllers' sea-level pressure unscaled; the yaw
position taken as recorded; a yaw step common to every turbine taken as each turbine's, not M1's vane's; the
commissioning NTF kept after the software update, or kept because no update falls inside the period; the
calibration turbine's anemometer taken as recorded; SCADA power taken as recorded; the certificate in the site
description kept after the mast anemometer was replaced; the turbine models of the site description kept after a
rotor upgrade.

With only the clock check left out, the reference's power scale check reads the sound-mode limit, now at the wrong
hours, as a scale error and raises the turbine's power; the second route leaves both out and shows the clock fault
alone: the sound-mode periods enter the curve.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ROUTES = [("clock check", {"clock"}), ("clock and SCADA power scale checks", {"clock", "scale"}),
          ("M1 clock check (turbines aligned to M1 as recorded)", {"mastclock"}),
          ("barometer replacement scaled to M1", {"pressure"}), ("yaw check", {"yaw"}),
          ("M1 vane check (every yaw step taken as the turbine's)", {"vane"}),
          ("NTF validity (software update; the commissioning NTF kept throughout)", {"ntf", "ntfcheck"}),
          ("commissioning NTF verified at the calibration turbine", {"ntfcheck"}),
          ("calibration-turbine anemometer check", {"drift"}),
          ("SCADA power scale check", {"scale"}), ("mast anemometer certificate from the service log", {"cert"}),
          ("rotor upgrades from the maintenance log", {"rotor"}),
          ("all of the above (PP-12 on the records as they stand)",
           {"clock", "mastclock", "pressure", "yaw", "vane", "ntf", "ntfcheck", "drift", "scale", "cert", "rotor"})]
T = C.truth()
print("Routes that leave out record checks, as complete programs through tests/grade.py (run as %s); six hidden "
      "packages, 59 turbines; accepted when at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("%-56s %6s  %-58s %s" % ("check left out", "wrong", "packages missed (turbines wrong)", "errors on wrong turbines"))
for name, skip in ROUTES:
    r = C.verify(C.reference_program(skip=skip))
    s = C.summary(r, T)
    errs = [e for p in s for (_, e, _, _) in s[p][2]]
    flips = sum(c != tc for p in s for (_, _, c, tc) in s[p][2])
    miss = ", ".join("%s (%d)" % (p, s[p][0]) for p in sorted(s) if s[p][0])
    rng = "%+.4f to %+.4f, %d claim(s) wrong" % (min(errs), max(errs), flips) if errs else "-"
    print("%-56s %6d  %-58s %s  %s" % (name, r["wrong"], miss, rng, "accepted" if r["accepted"] else "rejected"))
    for p in sorted(s):
        if s[p][2]:
            e = [abs(x[1]) for x in s[p][2]]
            print("    %-22s wrong %2d, |error| %.4f to %.4f" % (p, s[p][0], min(e), max(e)))
