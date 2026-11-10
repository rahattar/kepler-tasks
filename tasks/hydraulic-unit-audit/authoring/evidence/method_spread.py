"""Correct side of the bound: the reference program with other sound settings, one at a time.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

VARIANTS = {
    "precharge from the fit always (never the record's figure)": [
        ("    if abs(p0g - doc) / doc < 0.05:\n        p0g = doc\n", "")],
    "precharge from the 10th percentile of the window ratios (not the 5th)": [
        ("np.percentile(ratios, 5.0)", "np.percentile(ratios, 10.0)")],
    "precharge from 0.5 s windows (not 1.0 s)": [
        ("    win = int(round(1.0 / dt))\n    pa = ps + P_ATM", "    win = int(round(0.5 / dt))\n    pa = ps + P_ATM")],
    "pressure scale from the mean ratio (not the median)": [
        ("        k = np.median(p_pump[w] / p_impl)", "        k = float(np.mean(p_pump[w] / p_impl))")],
    "pressure scale applied whenever it differs from 1 by more than 2 %": [
        ("    if abs(k - 1.0) > 0.05:", "    if abs(k - 1.0) > 0.02:")],
    "loaded threshold 15 bar (not 20)": [("LOADED_BAR = 20.0", "LOADED_BAR = 15.0")],
    "gauge pressures used in the gas law (atmospheric pressure left out)": [("P_ATM = 1.013", "P_ATM = 0.0")],
}


def main():
    base = open(C.SOLUTION).read()
    print("Hidden presses wrong (of 8); the bound is 1. Largest errors: oil, hydraulic and electrical energy in %,")
    print("peak flow in %, efficiency absolute.\n")
    worst = 0
    for name, edits in VARIANTS.items():
        text = base
        for old, new in edits:
            assert old in text, (name, old)
            text = text.replace(old, new)
        r = C.grade_text(text)
        worst = max(worst, r["wrong"])
        w = C.worst(r)
        print("%-70s %d  %s" % (name, r["wrong"], " ".join("%s %.2f" % (C.SHORT[k], v) for k, v in w.items())), flush=True)
    print("\nLargest count over all variants: %d" % worst)


if __name__ == "__main__":
    main()
