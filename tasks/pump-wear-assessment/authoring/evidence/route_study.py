"""Shortcuts against the reference on the shipped bank. Figures: worst pump's |estimated - true| head deficit at
900 m3/h, m.

    python3 route_study.py > route_study.txt
"""
import methods as M


def show(name, kw):
    e, w, fails, _ = M.grade(M.estimate(**kw)[0])
    print("  %-88s worst %.3f (%s)  fails %2d  %s" % (name, e, w, len(fails), " ".join(fails)))


print("requirement %.1f m\n" % M.TOL)
show("reference", {})
print("\nrecords taken at face value")
show("header flowmeter's 3 % error before its recalibration left in", dict(cal=False))
show("P2's discharge readings on the wrong range (2026-10-04 to 10-11) left in", dict(span=False))
show("velocity-head difference between the 250 mm and 350 mm pipes left out", dict(velocity=False))
show("tapping heights from the installation sheet (P5 at 0.80 m) instead of the stopped-pump readings", dict(dz=False))
show("P4's impeller trim (315 of 330 mm) not applied", dict(p4_trim=False))
show("P3's certificate (run at 1450 rpm) used as if at 1480 rpm", dict(p3="asis"))
show("P9's VFD speed ignored", dict(speed=False))
print("\nevents inside the four weeks")
show("P1 held at one head ratio across its 2026-10-09 trip (starved, vibrating run before it)", dict(dry="const"))
show("P6's tapping offset as one median of all its stopped hours, across PT-606's 2026-10-06 calibration", dict(zero="single"))
show("P6's offset from the hours after the calibration applied to the whole window", dict(zero="post"))
show("both of the above (P1 one ratio, P6 one median)", dict(dry="const", zero="single"))
print("\npumps without a certificate of their own, and the pair that never runs apart")
show("P6 from the sister pumps' median certificate curve", dict(p6="sister"))
show("P6 from the OEM type test as run (340 mm), not trimmed to its 330 mm impeller", dict(p6="oem_raw"))
show("P10 from the supplier's catalogue curve", dict(p10="catalogue"))
show("P10 from its 2026 rig test as run (1490 rpm), not brought to 1480 rpm", dict(p10="rig_raw"))
show("P7 and P8 split by the header balance alone (the 2026-10-08 flow survey not used)", dict(survey=False))
show("survey flows as read (meter keyed for bare 254.46 mm steel; the line is lined to 250 mm)", dict(survey_bore="keyed"))
print("\na free wear slope per pump over the four weeks (rings wear over years; the balance cannot pin 20 unknowns)")
show("slope per pump", dict(slope=True))
