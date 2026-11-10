"""Answers that do not use the records cell by cell, against the 3 pp bound.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import numpy as np

import methods as M

TRUE = M.TRUE
vals = np.array([TRUE[c] for c in M.CELLS])

if __name__ == "__main__":
    best, at = 0, None
    for k in np.arange(60.0, 110.0, 0.1):
        n = int(np.sum(np.abs(vals - k) <= 3.0))
        if n > best:
            best, at = n, k
    print("True capabilities: %s" % ", ".join("%s %.1f" % (c, TRUE[c]) for c in M.CELLS))
    print("Best single value for every cell: %.1f %% satisfies %d of 8 cells" % (at, best))
    print("Every cell at design (100 %%): %d of 8" % int(np.sum(np.abs(vals - 100.0) <= 3.0)))
    raw = dict(no_c3_zero=True, c6_trusted=True, no_bypass=True, c2_trusted=True, c4_trusted=True, no_recirc=True,
               flume_trusted=True, end="median")
    d = M.misses(raw)
    ok = sum(abs(v) <= 3.0 for v in d.values())
    print("TP-31 on the records as they stand (clock and units converted, no record fault removed, median of the "
          "record): %d of 8 (%s)" % (ok, " ".join("%s %+.1f" % (c, d[c]) for c in M.CELLS)))
