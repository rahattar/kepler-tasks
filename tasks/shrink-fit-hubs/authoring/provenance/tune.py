"""How the peak torques and yield strengths in sfsim.py were set, and a check that they still follow from the rules.

    python3 authoring/provenance/tune.py

Design rules. Each joint's window of whole-micrometre mean interferences (hub at its heating limit) is one contiguous
run whose width is 9 % of the interference that carries the pressure at its lower edge (the least interference less
the smoothing and any loss in running), and at least 8 um. The upper edge is set by the hub stress (J01-J03, J05,
J07, J08, J10-J12; the yield strength is the hub grade's) or, for J04, J06 and J09, by the clearance at the heating
limit (the yield strength is then set 6 % above what the edge needs, rounded up to 10 MPa). The peak torque is then
the largest multiple of 10 N m that the least interference at the lower edge carries 1.5 times over, at rest and in
running. The script recomputes every value from sfsim's geometry, materials and limits and fails if any differs.
"""
import copy
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfsim as S  # noqa: E402

FRAC, WMIN = 0.09, 8
HEATCAP = {"J04", "J06", "J09"}


def top_of(J, jid):
    j = J[jid]
    j["Tpeak"] = 1e-6
    return max(m for m in range(5, 900) if (lambda a: a["stress"] >= 0 and (jid not in HEATCAP or a["clear"] >= 0))(
        S.margins(jid, m, j["Tlim"], J)))


def tune(J, jid, w):
    j = J[jid]
    if jid in HEATCAP:
        j["Re"] = 5000.0
        hi = top_of(J, jid)
        dmax = hi * 1e-3 + S.span(j["d"]) / 2
        need = max(1.2 * S.vm_bore(j, S.pressure(j, dmax - S.smoothing(j) + dd), rot) for _, dd, rot in S.states(j))
        j["Re"] = float(np.ceil(need * 1.06 / 10.0) * 10.0)
    hi = top_of(J, jid)
    lo = hi - w + 1
    dmin = lo * 1e-3 - S.span(j["d"]) / 2
    cap = min(S.tcap(j, dmin - S.smoothing(j) + dd)[0] for _, dd, _ in S.states(j))
    j["Tpeak"] = float(np.floor(cap / 1.5 / 10.0) * 10.0)
    pp = (lo - S.span(j["d"]) * 1e3 / 2) - (S.smoothing(j) + max(S.thermal_loss(j) + S.centrifugal_loss(j), 0.0)) * 1e3
    return lo, hi, pp


def main():
    J = copy.deepcopy(S.JOINTS)
    bad = 0
    for jid in J:
        w = 22
        for _ in range(6):
            w = max(WMIN, int(round(FRAC * tune(J, jid, w)[2])))
        lo, hi, _ = tune(J, jid, w)
        same = J[jid]["Tpeak"] == S.JOINTS[jid]["Tpeak"] and J[jid]["Re"] == S.JOINTS[jid]["Re"]
        win = S.fit_window(jid)
        same = same and win[0] == lo and win[-1] == hi and len(win) == hi - lo + 1
        bad += not same
        print("%s window %d-%d um (%d)  Tpeak %.0f N m  Re %.0f MPa  %s" % (jid, lo, hi, w, J[jid]["Tpeak"], J[jid]["Re"],
                                                                           "matches sfsim" if same else "DIFFERS"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
