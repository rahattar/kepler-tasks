"""Can one answer be right under both readings of a choice?

The audit asks for a cause and two quantities. The cause is a single name, so a solver cannot hedge it; what it can
try is to get the quantities right while naming the wrong mechanism, and so lose only one field. This script asks
whether that is possible, chamber by chamber:

- for every chamber and every cause other than the true one, it builds the sheet a solver would write if it
  attributed the chamber's gas load to that mechanism instead, keeping everything else sound, and scores it. The
  attribution changes the gas the gauge is reading, so it changes the correction of MS-BP clause 5 and with it the
  gas load; the question is whether the change is large enough that a wrong attribution is also a wrong number.

- it then reports, for each chamber, whether any single gas load lies within tolerance of the value both the true
  and the nearest wrong attribution imply. Where one does, a solver that hedges the cause still fails the chamber
  on the cause, so the chamber is never carried by the hedge.

A chamber whose quantity survives a wrong attribution is not a fault: the cause is graded on its own. The study is
here to record which chambers those are, so the gate is read with that in mind.

    python3 -I hedge_study.py  > hedge_study.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402

sys.path.insert(0, os.path.join(C.TASK, "solution"))
import diagnose as D                                                    # noqa: E402

CAUSES = list(D.gas_correction.__globals__["SPECIES"]) + ["permeation"]


def reattributed(cid, data, certs, fix, vac, cause):
    """The gas load a solver reaches on this chamber if it puts the whole non-computable part of the gas budget
    down to `cause`, with everything else done as the reference does it.

    The front end is the reference's own `front_end`, not a copy of it: everything up to the attribution has to
    be exactly what the audit does, or the deviations below measure the copy's drift instead of the hedge."""
    cfg, pts, s_eff = D.front_end(cid, data, certs, fix, vac)

    n = len(pts)
    W = [D.nominal_wall(cfg, p) for p in pts]
    QP = [D.perm_of(cfg, p) for p in pts]
    corr = [1.0] * n
    q_total = 0.0
    for _ in range(25):
        q = [pts[i]["p_n2"] * corr[i] * s_eff for i in range(n)]
        if cause == "wall-outgassing":
            # everything that is not permeation is taken as wall gas
            coef = [max((q[i] - QP[i]) / W[i], 0.0) if W[i] > 0 else 0.0 for i in range(n)]
            c_w = sum(coef) / n
            parts = [{"wall-outgassing": c_w * W[i], "permeation": QP[i]} for i in range(n)]
        elif cause == "permeation":
            # the whole gas load is taken as permeation
            parts = [{"permeation": q[i]} for i in range(n)]
        else:
            # a constant leak or a trapped volume: air in either case, so the correction is the same
            y = [q[i] - QP[i] for i in range(n)]
            cols = [W, [1.0] * n]
            c, _ss = D._lstsq_nonneg(cols, y)
            parts = [{"wall-outgassing": c[0] * W[i], "permeation": QP[i], cause: c[1]} for i in range(n)]
        new = [D.gas_correction(parts[i], D.seal_at(cfg, pts[i]["date"])[0]) for i in range(n)]
        if max(abs(a - b) for a, b in zip(new, corr)) < 1e-10:
            corr = new
            break
        corr = new
    q = [pts[i]["p_n2"] * corr[i] * s_eff for i in range(n)]

    # refer the same budget to the reference condition
    if cause == "permeation":
        mat, cm = D.seal_at(cfg, D.AUDIT)
        scale = q[-1] / QP[-1] if QP[-1] > 0 else 1.0
        total = scale * D.q_perm(mat, cm, D.T_REF)
    elif cause == "wall-outgassing":
        c_w = sum(max((q[i] - QP[i]) / W[i], 0.0) if W[i] > 0 else 0.0 for i in range(n)) / n
        _p, total = D.at_reference(cfg, c_w, 0.0, 0.0, None)
    else:
        y = [q[i] - QP[i] for i in range(n)]
        c, _ss = D._lstsq_nonneg([W, [1.0] * n], y)
        if cause == "virtual-leak":
            _p, total = D.at_reference(cfg, c[0], 0.0, c[1] * 2.718281828, 16.0)
        else:
            _p, total = D.at_reference(cfg, c[0], c[1], 0.0, None)
    return total, s_eff


def main():
    data = D.load_data(C.DATA)
    certs = data["certs"]
    fix = D.crossed_serials(data, certs)
    vac = C.place_order(C.REFERENCE_PLAN)
    tr = C.truth()
    ref = C.reference_answers()

    rows = []
    both = []
    accepted = []
    # Every chamber against every one of the five causes but its own, so the table covers the whole space and
    # the README can say so. pump-speed is included: it is not a reattribution of the gas load - clause 6 awards
    # it on the speed ratio - so the quantities stay the reference's and only the cause changes, which is the
    # purest form of the hedge and worth having in the record rather than assumed.
    for cid in C.IDS:
        true_cause = tr[cid]["cause"]
        q_true = tr[cid]["q_total"]
        for cause in ("wall-outgassing", "air-leak", "virtual-leak", "permeation", "pump-speed"):
            if cause == true_cause:
                continue
            if cause == "pump-speed":
                q_alt, s_alt = ref[cid][1], ref[cid][2]
            else:
                # No blanket except here. Every reattribution is arithmetic on the same records, so it is always
                # computable; an exception means this script is broken, not that the hedge is unavailable.
                q_alt, s_alt = reattributed(cid, data, certs, fix, vac, cause)

            # Scored through the task's own grader, on a complete sheet, exactly as the verifier reads one. The
            # deviation below is the grader's, not this script's arithmetic: a study that computes its own
            # verdict is not evidence about the grader.
            sheet = {c: ref[c] for c in C.IDS}
            sheet[cid] = (cause, q_alt, s_alt)
            r = C.score(sheet)
            v = r["chambers"][cid]
            dev = v["q_dev"]
            inside = v["ok_q"]
            if inside:
                both.append((cid, cause))
            if r["accepted"]:
                accepted.append((cid, cause))
            rows.append([cid, true_cause, cause, "%.3e" % q_alt, "%+.2f%%" % (100 * dev),
                         "yes" if inside else "no", "%d/%d" % (r["npass"], len(C.IDS)),
                         "accepted" if r["accepted"] else "rejected"])

    print(C.report("Every chamber under every cause but its own, each a whole sheet through the grader", rows,
                   ["chamber", "true cause", "attributed to", "gas load", "deviation", "quantity in band",
                    "right", "verdict"]))

    print("cases: %d (each of %d chambers against each of the other %d causes)"
          % (len(rows), len(C.IDS), 4))
    if accepted:
        print("%d PROBLEM(S): these hedged sheets were accepted" % len(accepted))
        for cid, cause in accepted:
            print("  %s named %s and still passed" % (cid, cause))
    else:
        print("none of the %d hedged sheets is accepted: the cause is graded on its own, so a sheet that names"
              % len(rows))
        print("the wrong mechanism fails that chamber whatever its quantity does.")
    print("")
    if both:
        print("Cases whose gas load stays in the band under the wrong cause (%d of %d) - the cause alone decides"
              % (len(both), len(rows)))
        print("them:")
        for cid, cause in both:
            print("  %s under %s" % (cid, cause))
    else:
        print("On every chamber a wrong attribution also puts the gas load outside the band.")
    print("")
    print("the reference's own answers, for comparison:")
    for cid in C.IDS:
        cause, q, s = ref[cid]
        print("  %s %-16s q %.4e  s %7.1f" % (cid, cause, q, s))
    C.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
