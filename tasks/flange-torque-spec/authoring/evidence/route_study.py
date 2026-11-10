"""Route study (the wrong side): the shortcuts and partial methods an assembler might use, each graded on the shipped
scenario. Every route uses the rig as the agent would (8 slots, a pattern trial takes two, same deterministic noise).
Numbers: joints right of 16 (gate 15), and for the joints wrong the preload error in percent of target (window +/-6).

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

REC = C.record_ratios()
EIGHT = ["J01", "J16", "J02", "J06", "J05", "J12", "J04", "J10"]     # a good eight-joint single-bolt campaign


def handbook():
    return {j: C.K_HB * C.d_m(j) * C.target_N(j) for j in C.IDS}


def singles_only(kind, fraction=0.6, ratios=None):
    rig = C.Rig()
    meas = C.singles(rig, EIGHT, fraction)
    return C.commit(meas, C.fit(meas, kind), ratios or REC)


def all_pattern(camp=("J01", "J16", "J05", "J12")):
    """four pattern trials (the whole budget); torque scaled from each, the rest from a fit of K_eff with a class term"""
    import numpy as np
    rig = C.Rig()
    ke = {j: C.pattern(rig, j, 0.6) for j in camp}
    ids = list(ke)

    def row(j):
        thr, Ra, tp, re = C.feat(j)
        return [1.0, Ra - 2.0, max(0.0, tp - C.ALLOW_UM[thr]), 1.0 if C.SCHED[j]["flange_class"] == "B" else 0.0]
    A = np.array([row(j) for j in ids]); y = np.array([ke[j] for j in ids])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    return {j: (ke[j] if j in ke else float(np.array(row(j)) @ b)) * C.d_m(j) * C.target_N(j) for j in C.IDS}


ONE = ("J01", "J06", "J07", "J12", "J14", "J16")      # one reused joint (J14, four earlier assemblies)
TWO = ("J01", "J13", "J14", "J12", "J06", "J16")      # two reused joints (J13 one, J14 four)
ROUTES = [
    ("handbook K for every joint, no trials", handbook),
    ("8 single-bolt trials, ISO-allowance fit, the records' pattern ratios (the general approach)",
     lambda: singles_only("iso")),
    ("8 single-bolt trials, one fitted plating threshold, the records' pattern ratios",
     lambda: singles_only("hinge")),
    ("4 pattern trials (the whole allowance), torques scaled from them, K_eff fit for the rest", all_pattern),
    ("reference campaign, class B kept at the record ratio (class A measured)",
     lambda: C.reference(b_from_records=True)[0]),
    ("one reused joint trialled (J14), reuse straight in the number of assemblies",
     lambda: C.reference(campaign=ONE, pj="J01", reuse=True)[0]),
    ("one reused joint trialled (J14), its excess held for every reused joint",
     lambda: C.reference(campaign=ONE, pj="J01", reuse="flag")[0]),
    ("one reused joint trialled (J04), reuse straight in the number of assemblies",
     lambda: C.reference(campaign=("J01", "J04", "J06", "J12", "J07", "J16"), pj="J01", reuse=True)[0]),
    ("two reused joints trialled (J13, J14), reuse straight in the number of assemblies",
     lambda: C.reference(campaign=TWO, pj="J01", reuse=True)[0]),
    ("reference campaign, no reuse term", lambda: C.reference(reuse=False)[0]),
    ("reference campaign, one fitted plating threshold for all sizes", lambda: C.reference(kind="hinge")[0]),
    ("reference campaign, LINEAR plating term", lambda: C.reference(kind="linear")[0]),
    ("reference campaign, quadratic plating term", lambda: C.reference(kind="quad")[0]),
    ("reference campaign at the rig's default torque (J01 clipped at proof)", lambda: C.reference(fraction=None)[0]),
    ("near-sound: reference campaign, one constant reuse offset fitted to its two reused joints",
     lambda: C.reference(reuse="flag")[0]),
    ("careful: the reference (6 single-bolt trials, pattern pair on J06, ISO fit, reuse curve, crew ratios)",
     lambda: C.reference()[0]),
]

if __name__ == "__main__":
    print("Route study on the shipped scenario (seed %d). Window +/-6 percent of target preload, gate 15 of 16.\n" % C.SEED)
    print("%-104s %5s  %s" % ("route", "right", "joints wrong (error, percent of target; Y = bolt yielded)"))
    worst = []
    for i, (name, fn) in enumerate(ROUTES):
        n, bad, errs, jj = C.grade(fn())
        detail = ", ".join("%s %+.1f%%%s" % (j, errs[j], " Y" if jj[j].get("yielded") else "") for j in bad)
        print("%-104s %2d/16  %s" % (name, n, detail or "-"))
        if i < len(ROUTES) - 2 and bad and n < 15:
            worst.append(min(abs(errs[j]) for j in bad))
    print("\nPer-joint matrix ('x' = joint right, '.' = wrong); routes numbered as listed above:")
    print("    %s" % " ".join(j[1:] for j in C.IDS))
    passed_by = {j: [] for j in C.IDS}
    for i, (name, fn) in enumerate(ROUTES, 1):
        n, bad, errs, jj = C.grade(fn())
        print("%2d  %s   %2d/16" % (i, "  ".join("." if j in bad else "x" for j in C.IDS), n))
        if i <= len(ROUTES) - 2:
            for j in C.IDS:
                if j not in bad:
                    passed_by[j].append(i)
    nd = len(ROUTES) - 2
    print("\nDefective routes (1 to %d) that get each joint right; a joint every one of them got right would not" % nd)
    print("discriminate:")
    for j in C.IDS:
        print("  %s  %2d of %d  (%s)" % (j, len(passed_by[j]), nd, ", ".join(str(i) for i in passed_by[j]) or "-"))
    print("Every joint is failed by at least %d of the %d defective routes." % (min(nd - len(v) for v in passed_by.values()), nd))
    print("\nSmallest miss among the wrong joints of each rejected route: %s percent of target." %
          ", ".join("%.1f" % w for w in worst))
    _, crew, m, _ = C.reference()
    print("\nNotes:")
    print("- The records' pattern ratios %s are for their own sequence (incremental cross-pattern passes and two" %
          {k: round(v, 3) for k, v in REC.items()})
    print("  circular passes). The crew's single cross-pattern pass loses more: the reference's pair of trials on J06 gives")
    print("  crew ratios %s, a loss %.2f times the recorded one." % ({k: round(v, 3) for k, v in crew.items()}, m))
    print("- At the rig's default torque (handbook K at the joint's target) the low-friction joints J01 and J16 are taken")
    print("  past proof; a trial preload read there is clipped and the nut factor read from it is too high.")
    print("- Zinc-plated threads gain friction with every tightening, steeply over the first few and then levelling off.")
    print("  The maintenance log lists one to four earlier assemblies on J04, J08, J10, J11, J13 and J14. One reused trial")
    print("  cannot show the curve; a straight line through two over-reaches at the ends. With the curve flattening, one")
    print("  constant offset fitted to two mid-range counts lands close (the near-sound route above).")
    print("- The zinc galls only where the coating is thicker than the 6g thread's allowance |es|/4 (9.5 um on M16, 10.5")
    print("  on M20, 12.0 on M24): J05, J09 and J12. J10 (10.5 um on M24) is within its allowance.")
