#!/usr/bin/env python3
"""Sound variations on the study. Every one must get all six contingencies right on the shipped records, and the
spread of their loads and pressures must sit well inside the band the verifier allows.

    python3 method_spread.py [--seeds]
"""
import os
import shutil
import sys
import tempfile

import common
import solve

SEEDS = list(range(7301, 7321))

METHODS = [
    ("the reference", {}),
    ("the trend fitted by least squares", dict(fit="ls")),
    ("only trend points above 60 per cent travel", dict(fit="high")),
    ("the reboiler from the record's mean duty over its mean difference", dict(uaw="ratio")),
    ("the pump curve by least squares on all four points", dict(pumpfit="ls")),
    ("least squares throughout", dict(fit="ls", uaw="ratio", pumpfit="ls")),
    ("high travel points and the mean ratio", dict(fit="high", uaw="ratio")),
    ("least squares and the mean ratio together", dict(fit="ls", uaw="ratio")),
]


# readings the standard does not sanction but the tolerance absorbs: reported so the margin is visible
TOLERATED = [
    ("every length of header taken with the whole mixture's properties", dict(mixprops="total")),
    ("the whole mixture's properties and least squares throughout",
     dict(mixprops="total", fit="ls", uaw="ratio")),
]


def spread(rows, tru):
    """The worst relative departure from the sealed answer, over the load and the pressure."""
    worst_load = worst_back = 0.0
    for name, devices, total, back in rows:
        t = tru[name]
        if t["load"]:
            worst_load = max(worst_load, abs((total - t["load"]) / t["load"]))
        if t["back"] > 0.01:
            worst_back = max(worst_back, abs((back - t["back"]) / t["back"]))
    return worst_load, worst_back


def main():
    want_seeds = "--seeds" in sys.argv
    sealed, tru = common.truth()
    reports = common.crew_reports(sealed)
    d = solve.load(common.DATA)

    results = []
    for name, sw in METHODS:
        rows = common.run(d, reports, **sw)
        n, notes = common.compare(rows, sealed, tru)
        results.append((name, n, spread(rows, tru), common.worst(notes)))

    seed_worst = {}
    if want_seeds:
        tmp = tempfile.mkdtemp(prefix="fl_ms_")
        os.environ["GEN_QUIET"] = "1"
        import gen
        try:
            for seed in SEEDS:
                out = os.path.join(tmp, "data")
                shutil.rmtree(out, ignore_errors=True)
                os.makedirs(os.path.join(out, "docs"), exist_ok=True)
                gen.main(out, seed)
                ds = solve.load(out)
                for name, sw in METHODS:
                    k, _ = common.compare(common.run(ds, reports, **sw), sealed, tru)
                    seed_worst[name] = min(seed_worst.get(name, 6), k)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("Sound variations, graded against the sealed definition. Tolerance %.3f relative.\n" % sealed.TOL)
    print("| Method | Right of 6 | Worst load | Worst pressure | Worst seed |")
    print("|---|---|---|---|---|")
    for name, n, (wl, wb), bad in results:
        worst = "%d of 6" % seed_worst[name] if want_seeds else "-"
        print("| %s | %d%s | %.3f%% | %.3f%% | %s |"
              % (name, n, "" if n == 6 else " (%s)" % bad, 100.0 * wl, 100.0 * wb, worst))
    wl = max(r[2][0] for r in results)
    wb = max(r[2][1] for r in results)
    print("\nwidest load spread %.3f%% and pressure spread %.3f%% against a band of %.1f%%"
          % (100.0 * wl, 100.0 * wb, 100.0 * sealed.TOL))
    print()
    print("Readings the standard does not sanction, which the tolerance nevertheless absorbs:\n")
    print("| Reading | Right of 6 | Worst load | Worst pressure |")
    print("|---|---|---|---|")
    for name, sw in TOLERATED:
        rows = common.run(d, reports, **sw)
        n, _ = common.compare(rows, sealed, tru)
        tl, tb = spread(rows, tru)
        print("| %s | %d | %.3f%% | %.3f%% |" % (name, n, 100.0 * tl, 100.0 * tb))
    print()
    print("methods that miss a contingency: %s"
          % (", ".join(n for n, k, _, _ in results if k != 6) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
