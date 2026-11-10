"""Method spread (the right side): the careful method with other reasonable choices of campaign, pair joint, trial
torque and trial order. Every variant should clear the gate; the spread shows how far inside the window the sound
methods land.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import numpy as np
import common as C

REF = ("J01", "J03", "J06", "J08", "J09", "J13")
TWO = ("J01", "J13", "J14", "J12", "J06", "J16")
VARIANTS = [
    ("reference: singles J01 J03 J06 J08 J09 J13, pattern J06, 60 percent", dict()),
    ("same, trials at 50 percent of the default torque", dict(fraction=0.5)),
    ("same, trials at 75 percent of the default torque", dict(fraction=0.75)),
    ("same, reversed trial order (other noise draws)", dict(order=REF[::-1])),
    ("J01 J13 J14 J12 J06 J16, pair on J01, piecewise reuse curve", dict(campaign=TWO, pj="J01")),
    ("same campaign, reuse as r sqrt(n)", dict(campaign=TWO, pj="J01", reuse="sqrt")),
    ("J01 J04 J14 J12 J06 J16, pair on J01", dict(campaign=("J01", "J04", "J14", "J12", "J06", "J16"), pj="J01")),
    ("pattern on J07 (not single-trialled; its K from the fit), reference singles", dict(pj="J07")),
]

def both_classes(campaign, pa, pb, fraction=0.6):
    """class B measured with its own pair instead of scaled from class A: two pattern trials, four singles"""
    rig = C.Rig()
    meas = C.singles(rig, list(campaign), fraction)
    ka, kb = C.pattern(rig, pa, fraction), C.pattern(rig, pb, fraction)
    pred = C.fit(meas, "iso")
    ratios = {"A": meas[pa] / ka, "B": meas[pb] / kb}
    return C.commit(meas, pred, ratios), ratios


BOTH = [
    ("both classes paired (J14 and J04, reused 4 and 1), singles J14 J04 J12 J16", (("J14", "J04", "J12", "J16"), "J14", "J04")),
]


if __name__ == "__main__":
    print("Method spread on the shipped scenario (seed %d): careful method, varied choices. Errors in percent of target;\n"
          "window +/-6 percent; gate 15 of 16.\n" % C.SEED)
    print("%-66s %5s  %-10s %-9s %-14s %s" % ("variant", "right", "worst err", "rms err", "crew A / B", "joints wrong"))
    for name, kw in VARIANTS:
        torques, ratios, m, _ = C.reference(**kw)
        n, bad, errs, _ = C.grade(torques)
        e = np.array(list(errs.values()))
        print("%-66s %2d/16  %+7.2f%%  %6.2f%%  %.3f / %.3f  %s" % (name, n, e[np.argmax(np.abs(e))],
              np.sqrt(np.mean(e ** 2)), ratios["A"], ratios["B"], ", ".join(bad) or "-"))
    for name, args in BOTH:
        torques, ratios = both_classes(*args)
        n, bad, errs, _ = C.grade(torques)
        e = np.array(list(errs.values()))
        print("%-66s %2d/16  %+7.2f%%  %6.2f%%  %.3f / %.3f  %s" % (name, n, e[np.argmax(np.abs(e))],
              np.sqrt(np.mean(e ** 2)), ratios["A"], ratios["B"], ", ".join(bad) or "-"))
    print("\nTrue crew ratios (sealed): A %.3f, B %.3f (8-bolt) and %.3f (6-bolt M24)." % (
        1 - C.TRUTH["J01"]["r"], 1 - C.TRUTH["J02"]["r"], 1 - C.TRUTH["J05"]["r"]))
