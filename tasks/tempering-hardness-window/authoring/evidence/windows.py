"""Each batch's window of setpoints, and how far each heat departs from the supplier's typical curve.

    python3 authoring/evidence/windows.py      (writes windows.txt)
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

S = C.S


def main():
    out = ["Windows: whole-degree setpoints from the grade's minimum to 700 C that put the batch inside its range",
           "(production soak 1 h per 25 mm, at least 2 h; G52 double tempered). Slope: HRC per C at the window's middle.",
           ""]
    out.append("%-4s %-8s %5s %-11s %-9s %-11s %5s %6s %s" % ("batch", "heat", "D mm", "location", "range", "window C",
                                                          "width", "slope", "minimum"))
    widths = []
    for b, (part, heat, D, loc, (lo, hi)) in S.BATCHES.items():
        W = S.window(b)
        mid = W[len(W) // 2]
        slope = (S.batch_hardness(b, mid - 2) - S.batch_hardness(b, mid + 2)) / 4.0
        g = S.HEATS[heat][0]
        widths.append(len(W))
        out.append("%-5s %-8s %5.0f %-11s %4.0f-%-4.0f %4d-%-6d %5d %6.3f %d C%s" % (
            b, heat, D, loc, lo, hi, W[0], W[-1], len(W), slope, S.TMIN[g],
            "" if W[0] > S.TMIN[g] else "  (window starts at the minimum)"))
        assert W == list(range(W[0], W[-1] + 1)), "window not contiguous"
    out.append("windows are contiguous; widths %d to %d C" % (min(widths), max(widths)))
    out.append("")
    out.append("Departure of each batch's heat from the supplier's typical heat of its grade, at the batch's own diameter,")
    out.append("location and production tempering, at the window's middle (HRC; + harder):")
    for b, (part, heat, D, loc, (lo, hi)) in S.BATCHES.items():
        W = S.window(b)
        mid = W[len(W) // 2]
        g = S.HEATS[heat][0]
        typ = S.tempered(S.SUPPLIER_TYPICAL[g], mid, D, loc, S.soak_hours(D), S.NTEMPER[g])
        out.append("  %s %s %+.2f" % (b, heat, S.batch_hardness(b, mid) - typ))
    out.append("")
    out.append("G52: a single temper against a double temper at the same Hollomon-Jaffe parameter (the double temper's")
    out.append("total time), 25 mm half-radius, HRC (single minus double):")
    for heat in ("52-1250", "52-1312", "52-1377", "52-typ"):
        row = []
        for T in (560, 580, 600, 620):
            Teq4 = S.t_equiv(T, 2.0, 2)                       # 2 x 2 h at T
            lo_, hi_ = 300.0, 800.0                           # the single 2 h temperature with the same parameter
            for _ in range(60):
                m = 0.5 * (lo_ + hi_)
                lo_, hi_ = (m, hi_) if S.t_equiv(m, 2.0, 1) < Teq4 else (lo_, m)
            Ts = 0.5 * (lo_ + hi_)
            row.append("%d C %+.2f" % (T, S.tempered(heat, Ts) - S.tempered(heat, T, n=2)))
        out.append("  %-8s %s" % (heat, "   ".join(row)))
    out.append("")
    out.append("G52 heats against each other at each G52 batch's own conditions, at the batch window's middle (HRC):")
    for b in ("B06", "B07", "B08", "B11", "B13"):
        part, heat, D, loc, w = S.BATCHES[b]
        W = S.window(b)
        mid = W[len(W) // 2]
        hs = {h: S.tempered(h, mid, D, loc, S.soak_hours(D), 2) for h in ("52-1250", "52-1312", "52-1377", "52-typ")}
        out.append("  %s (%s) %d C: %s" % (b, heat, mid, "  ".join("%s %.2f" % (h, v) for h, v in hs.items())))
    return "\n".join(out)


if __name__ == "__main__":
    txt = main()
    print(txt)
    open(os.path.join(HERE, "windows.txt"), "w").write(txt + "\n")
