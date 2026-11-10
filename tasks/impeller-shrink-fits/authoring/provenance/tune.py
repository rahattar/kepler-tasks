"""How the heating limits of the clearance-limited parts and the OEM bore hoop stresses in isim.py were set, and a
check that they still follow from the rules.

    python3 authoring/provenance/tune.py

Design rules. The yield strengths are the certificates' (FV520B 880-905 MPa, Ti-6Al-4V 860, 42CrMo4 650-700). Each
part's window of whole-micrometre mean interferences (oven at the heating limit) is one contiguous run whose lower
edge is set by retention at the least interference (15 MPa, or twice the stage torque) at rest or at trip speed. For
the impellers S1, S3, S4 and S6 its upper edge is set by the hub stress at trip speed: the OEM bore hoop stress at MCS
is the largest whole MPa that makes the window 9 um (12 um for S3, whose hub runs hot enough that the expansion of
FV520B between 100 C and its test temperature is uncertain by a few um). For S2, S5, S6, BD and TC the
upper edge is the clearance at the heating limit, which is the one the records state (S2 240 C after its recoating,
S5 285, S6 375, BD 220 and TC 190 C); the OEM bore growths of S2, S5 and S6 and the drum's and collar's outside
diameters were chosen to make the windows of S2 9 um and of the others 7 um. An impeller limited
by clearance has its hoop stress set so that its stress limit lies 25 um above the clearance limit. The script
recomputes every value from isim's geometry, materials, survey and spin-test growths and fails if any differs.
"""
import copy
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isim as S  # noqa: E402

HEAT = {"S2", "S5", "S6", "BD", "TC"}
FIXED_LIMIT = {"S2", "S5", "S6", "BD", "TC"}
W = {"S1": 9, "S3": 12, "S4": 9}
WH = 8


def bottom(J, pid):
    j = J[pid]
    keep = (j["Re"], j["Tlim"])
    j["Re"], j["Tlim"] = 1e5, 600
    lo = min(S.window(pid, J))
    j["Re"], j["Tlim"] = keep
    return lo


def hoop_for(J, pid, top_um):
    j = J[pid]
    dmax = top_um * 1e-3 + S.band(j["d"]) / 2
    run = S.states(j)[1][1]
    p = S.pressure(j, dmax - S.smoothing(j) + run)
    A = j["Re"] / 1.2
    st = (-p + np.sqrt(4 * A * A - 3 * p * p)) / 2.0
    return (st - p * S.Ch(j)) / (S.TRIP ** 2 * S.spin_scale(j))


def main():
    J = copy.deepcopy(S.PARTS)
    bad = 0
    for pid, j in J.items():
        lo = bottom(J, pid)
        if pid in FIXED_LIMIT:
            keep = j["Re"]
            j["Re"] = 1e5
            top = S.window(pid, J)[-1]
            j["Re"] = keep
            if j["h_mcs"]:
                j["h_mcs"] = float(np.floor(hoop_for(J, pid, top + 25)))
        elif pid in HEAT:
            keep = j["Re"]
            j["Re"] = 1e5
            best = None
            for Tl in range(150, 450, 5):
                j["Tlim"] = Tl
                w = S.window(pid, J)
                if not w:
                    continue
                wdt = w[-1] - lo + 1
                if 8 <= wdt <= 14 and (best is None or abs(wdt - WH) < abs(best[1] - WH)):
                    best = (Tl, wdt, w[-1])
            j["Re"] = keep
            j["Tlim"] = best[0]
            if j["h_mcs"]:
                j["h_mcs"] = float(np.floor(hoop_for(J, pid, best[2] + 25)))
        else:
            j["h_mcs"] = float(np.floor(hoop_for(J, pid, lo + W[pid] - 1)))
        w = S.window(pid, J)
        same = j["Tlim"] == S.PARTS[pid]["Tlim"] and j["h_mcs"] == S.PARTS[pid]["h_mcs"] and w == S.window(pid)
        bad += not same
        print("%s window %d-%d um (%d)  heating limit %d C  OEM hoop at the spin-test speed %s  %s" % (
            pid, w[0], w[-1], len(w), j["Tlim"], "%.0f MPa" % j["h_mcs"] if j["h_mcs"] else "(ring)",
            "matches isim" if same else "DIFFERS"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
