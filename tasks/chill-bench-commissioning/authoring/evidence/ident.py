"""Second gate: is one run enough to pin a station's alpha, and which pressure helps?

Sensitivity of the observable trace to alpha, against 0.5 K measurement noise.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                "tests"))
import physics as ph
G = (120e-6, 250e-6, 250.0, 20.0)
def st(a): return ph.Station("X", *G, a, a)

print("d(observable)/d(alpha) at delta_alpha = 0.02, vs 0.5 K trace noise\n")
print("   P [Torr]   t_to_50 [s]   d t_to_50    T@5s shift [K]   peak zone [K]   d zone")
for P in (4.0, 6.0, 8.0, 12.0, 20.0, 30.0, 45.0, 60.0):
    rows = []
    for a in (0.40, 0.42, 0.44):
        t, Tm, Ti, To, Tp = ph.integrate(P, st(a), t_max=25.0)
        thit, dT = ph.cooldown_metrics(P, st(a), 50.0)
        i5 = int(round(5.0 / ph.DT))
        rows.append((thit, float(Tm[min(i5, len(Tm)-1)]), dT))
    dt_dalpha = (rows[2][0] - rows[0][0]) / 2.0
    dT5 = (rows[0][1] - rows[2][1]) / 2.0
    dz = (rows[2][2] - rows[0][2]) / 2.0
    print("   %6.1f    %8.3f     %+7.3f      %+7.3f          %7.2f      %+6.3f"
          % (P, rows[1][0], dt_dalpha, dT5, rows[1][2], dz))
print("\n(columns 4-6 are the CHANGE for delta_alpha = +0.02; noise on one sample is 0.5 K,")
print(" on a 10 Hz trace of ~100 points the effective noise on a fitted parameter is ~0.05 K)")
