"""Correct side of the bound: the reference program with other sound settings, one at a time, graded on the hidden
route packages.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

VARIANTS = {
    "unbalance at 1x above 3.0 mm/s (not 3.5)": ('if F[p]["one"] > 3.5:', 'if F[p]["one"] > 3.0:'),
    "unbalance at 1x above 4.5 mm/s": ('if F[p]["one"] > 3.5:', 'if F[p]["one"] > 4.5:'),
    "misalignment at 2x above 2.0 mm/s (not 2.5)": ('max(fe["two"] for fe in F.values()) > 2.5', 'max(fe["two"] for fe in F.values()) > 2.0'),
    "electrical line above 2.0 mm/s (not 2.5)": ("amp(mot[\"f\"], mot[\"v\"], 2 * drive_hz) > 2.5", "amp(mot[\"f\"], mot[\"v\"], 2 * drive_hz) > 2.0"),
    "envelope band 1000-8000 Hz (not 1500-7000)": ("def envelope(x, fs, lo=1500.0, hi=7000.0):", "def envelope(x, fs, lo=1000.0, hi=8000.0):"),
    "envelope lines 6x and 3x the floor (not 8x and 4x)": ("if a1 > 8 * floor and a2 > 4 * floor", "if a1 > 6 * floor and a2 > 3 * floor"),
    "channel drift limit 1.0 mm/s (not 0.5)": ("(f < 4)]) < 0.5", "(f < 4)]) < 1.0"),
    "half-order prominence 4x (not 5x)": ("prominent(f, v, h * fs_, 5)", "prominent(f, v, h * fs_, 4)"),
    "1x read within one bin either side": ("one=amp(f, v, fs_)", "one=amp(f, v, fs_, 1)"),
}

if __name__ == "__main__":
    base = open(C.SOLUTION).read()
    print("Hidden machines misdiagnosed (of 60); the bound is 2.\n")
    worst = 0
    r = C.grade_text(base)
    print("%-60s %d" % ("reference", r["wrong"]))
    for name, (old, new) in VARIANTS.items():
        assert base.count(old) == 1, name
        r = C.grade_text(base.replace(old, new))
        worst = max(worst, r["wrong"])
        print("%-60s %d  %s" % (name, r["wrong"], "; ".join(C.misses(r))))
    print("\nLargest count over all variants: %d" % worst)
