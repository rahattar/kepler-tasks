"""Correct side of the bound: the reference program with other sound settings, one at a time.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

VARIANTS = {
    "full-load threshold 0.95 (not 0.92)": ("                    if r >= 0.92:\n", "                    if r >= 0.95:\n"),
    "full-load threshold 0.88": ("                    if r >= 0.92:\n", "                    if r >= 0.88:\n"),
    "blow-down starting level 0.55 (not 0.6)": (
        "                        frac[i] = max(0.0, (r - 0.6) / 0.4)", "                        frac[i] = max(0.0, (r - 0.55) / 0.45)"),
    "supply high-pass over 11 intervals (not 31) for the clock check": (
        "    kern = np.ones(31) / 31.0", "    kern = np.ones(11) / 11.0"),
    "discharge pressure from the stamped pressure log (no second pass)": (
        "    supply, power = supply_power(p_end)", "    pass"),
}

if __name__ == "__main__":
    base = open(C.SOLUTION).read()
    print("Hidden sites wrong (of 8); the bound is 1.\n")
    worst = 0
    for name, (old, new) in VARIANTS.items():
        assert base.count(old) == 1, name
        r = C.grade_text(base.replace(old, new))
        worst = max(worst, r["wrong"])
        print("%-70s %d  %s" % (name, r["wrong"], "; ".join(C.misses(r))))
    print("\nLargest count over all variants: %d" % worst)
