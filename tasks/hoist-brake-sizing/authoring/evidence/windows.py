"""Windows: for every hoist and size, the settings that meet every MS-14 requirement under the sealed definition,
and the best smallest margin, with the requirement that bounds the window on each side.

    python3 authoring/evidence/windows.py > authoring/evidence/windows.txt

The scenario keeps every size clear of a knife-edge: no size's best margin lies between -0.05 and +0.035, so a hoist is
never decided by a size that only just works or only just fails.
"""
import numpy as np

import common as C

S = C.S
SET = np.arange(50, 101.0)


def main():
    print(__doc__.split("\n\n")[0].strip())
    print("Shipped scenario. Margins are fractions of each limit; a window is the run of whole-percent settings with "
          "every margin >= 0.\n")
    near = []
    for hid in C.IDS:
        parts = []
        for size in S.SIZES:
            r = S.margins(hid, size, SET)
            m = np.array([r[k] for k in S.REQUIREMENTS])
            w = m.min(axis=0)
            best = float(w.max())
            if -0.05 < best < 0.035:
                near.append("%s %s %+.3f" % (hid, size, best))
            if best < -0.2:
                continue
            ok = SET[w >= 0]
            if len(ok):
                lo, hi = int(ok[0]), int(ok[-1])
                below = S.REQUIREMENTS[int(np.argmin(m[:, max(int(lo - 50) - 1, 0)]))] if lo > 50 else "-"
                above = S.REQUIREMENTS[int(np.argmin(m[:, min(int(hi - 50) + 1, 50)]))] if hi < 100 else "-"
                parts.append("%s %d-%d %%, best %+.3f (below: %s, above: %s)" % (size, lo, hi, best, below, above))
            else:
                parts.append("%s none, best %+.3f" % (size, best))
        h = S.HOISTS[hid]
        print("%s (%s): %s" % (hid, h["name"], "; ".join(parts)))
    print("\nSizes with a best margin in the dead zone (-0.05, +0.035): %s" % (", ".join(near) or "none"))


if __name__ == "__main__":
    main()
