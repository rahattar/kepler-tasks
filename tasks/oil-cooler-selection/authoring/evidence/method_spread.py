"""Correct side of the bound: the reference program with other sound settings, one at a time.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

VARIANTS = {
    "baffle spacing searched in 1 mm steps (not 5 mm)": ("for sp in range(lo, hi + 1, 5):", "for sp in range(lo, hi + 1, 1):"),
    "baffle spacing searched in 25 mm steps": ("for sp in range(lo, hi + 1, 5):", "for sp in range(lo, hi + 1, 25):"),
    "water transmitter offset from the mean, not the median": (
        "    offset = float(np.median(ci[ok] - ch[ok]))", "    offset = float(np.mean(ci[ok] - ch[ok]))"),
    "tracking limit 0.5 K (not 0.8 K)": ("    bad |= roll > 0.8\n", "    bad |= roll > 0.5\n"),
    "tracking limit 1.5 K": ("    bad |= roll > 0.8\n", "    bad |= roll > 1.5\n"),
    "glitch limit for temperatures halved": ("    oil_in = clean_glitches(col[oil_tag], 20.0)", "    oil_in = clean_glitches(col[oil_tag], 10.0)"),
    "frozen after 2 h of identical values (not 1 h)": ("def frozen_mask(x, n=6):", "def frozen_mask(x, n=12):"),
}

if __name__ == "__main__":
    base = open(C.SOLUTION).read()
    print("Hidden cases wrong (of 8); the bound is 1.\n")
    worst = 0
    for name, (old, new) in VARIANTS.items():
        assert base.count(old) == 1, name
        r = C.grade_text(base.replace(old, new))
        worst = max(worst, r["wrong"])
        print("%-60s %d  %s" % (name, r["wrong"], "; ".join(C.misses(r))))
    print("\nLargest count over all variants: %d" % worst)
