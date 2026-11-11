#!/usr/bin/env python3
"""Sound variations on the assessment. Every one must get all nine valves right on the shipped records, and the
spread of their areas must sit well inside the band the verifier allows.

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
    ("the viscosity iteration stopped after two passes", dict(kviter=2)),
    ("least squares throughout", dict(fit="ls", uaw="ratio", pumpfit="ls")),
    ("high travel points and the mean ratio", dict(fit="high", uaw="ratio")),
    ("least squares, mean ratio and two viscosity passes", dict(fit="ls", uaw="ratio", kviter=2)),
]


def main():
    want_seeds = "--seeds" in sys.argv
    mod, tru = common.truth()
    d = solve.load(common.DATA)
    tol = mod.TOL

    results, worst_rel = [], {}
    for name, sw in METHODS:
        rows = common.run(d, **sw)
        n, notes = common.compare(rows, tru, tol)
        rel = max(abs((need - tru[vid]["area"]) / tru[vid]["area"]) for vid, _, need, _ in rows)
        at = max(rows, key=lambda r: abs((r[2] - tru[r[0]]["area"]) / tru[r[0]]["area"]))[0]
        results.append((name, n, notes, rel, at))
        worst_rel[name] = rel

    counts, seed_rel = {}, {}
    if want_seeds:
        tmp = tempfile.mkdtemp(prefix="rv_ms_")
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
                    rows = common.run(ds, **sw)
                    k, _ = common.compare(rows, tru, tol)
                    counts[name] = counts.get(name, 0) + (1 if k == len(tru) else 0)
                    r = max(abs((need - tru[vid]["area"]) / tru[vid]["area"]) for vid, _, need, _ in rows)
                    seed_rel[name] = max(seed_rel.get(name, 0.0), r)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("Sound variations, graded against the sealed definition. Area tolerance %.3f relative.\n" % tol)
    print("| Method | Right of 9 | Worst area | At | Seeds with 9 | Worst over seeds |")
    print("|---|---|---|---|---|---|")
    for name, n, notes, rel, at in results:
        print("| %s | %d | %.4f | %s | %s | %s |" % (
            name, n, rel, at,
            ("%d of %d" % (counts.get(name, 0), len(SEEDS))) if want_seeds else "-",
            ("%.4f" % seed_rel[name]) if want_seeds else "-"))
    bad = [name for name, n, _, _, _ in results if n != len(tru)]
    print("\nmethods that do not get all nine: %s" % (", ".join(bad) if bad else "none"))
    print("worst relative area over all sound methods on the shipped records: %.4f against a band of %.4f"
          % (max(worst_rel.values()), tol))
    if want_seeds:
        print("worst relative area over all sound methods and all %d seeds: %.4f"
              % (len(SEEDS), max(seed_rel.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
