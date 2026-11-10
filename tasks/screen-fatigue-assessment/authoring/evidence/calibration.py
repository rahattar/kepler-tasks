"""Recomputes every screen's damage from the sealed definition (screens.truth(): the operating log, the bank, the
event ensembles) and sets it against screens.DAMAGE, which the verifier uses; also the split by source.

    python3 calibration.py > calibration.txt
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "provenance"))
import screens as S

bank, log = S.truth()
print("screen  DAMAGE   recomputed  rel.diff   steady  events(start, braked stop, coast-down)")
for u in S.UNITS:
    b = bank[u]
    print("  %-4s  %.4f  %.6f   %+.1e   %.2f    %.2f" % (u, S.DAMAGE[u], b["D"], b["D"] / S.DAMAGE[u] - 1, b["D_steady"] / b["D"], b["D_events"] / b["D"]))
