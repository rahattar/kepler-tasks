#!/usr/bin/env python3
"""Choosing the seed. The seed drives only the scatter of the records: every answer comes from the parameters in
isim.py, so a seed cannot change the truth, only how well a sound method recovers it.

A seed is acceptable when, on the records it generates,

 1. every sound variation of method_spread.py gets all six contingencies right;
 2. every defective route of route_study.py fails;
 3. the worst relative departure of any sound variation, on either number, is at most half the verifier's band.

    python3 seed_screen.py [first] [count]
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "evidence"))

import common  # noqa: E402
import gen  # noqa: E402
import method_spread  # noqa: E402
import route_study  # noqa: E402
import solve  # noqa: E402

HALF = 0.5


def main():
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 7301
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    sealed, tru = common.truth()
    reports = common.crew_reports(sealed)
    tol = sealed.TOL
    os.environ["GEN_QUIET"] = "1"
    tmp = tempfile.mkdtemp(prefix="fl_ss_")
    chosen = None
    print("Seeds screened on three conditions. Band %.3f relative; the third condition wants the worst\n"
          "sound method within %.3f.\n" % (tol, HALF * tol))
    print("| seed | sound methods right of 8 | worst sound departure | defective routes that pass | acceptable |")
    print("|---|---|---|---|---|")
    try:
        for seed in range(first, first + count):
            out = os.path.join(tmp, "data")
            shutil.rmtree(out, ignore_errors=True)
            os.makedirs(os.path.join(out, "docs"), exist_ok=True)
            gen.main(out, seed)
            d = solve.load(out)
            nsound, worst = 0, 0.0
            for name, sw in method_spread.METHODS:
                rows, sizing = common.run(d, reports, **sw)
                k, _ = common.compare(rows, sealed, tru, sizing)
                nsound += 1 if k == len(tru) + 1 else 0
                wl, wb = method_spread.spread(rows, tru)
                worst = max(worst, wl, wb)
            passers = []
            for name, sw in route_study.ROUTES:
                rows, sizing = common.run(d, reports, **sw)
                k, _ = common.compare(rows, sealed, tru, sizing)
                if k == len(tru) + 1:
                    passers.append(name)
            ok = (nsound == len(method_spread.METHODS) and not passers and worst <= HALF * tol)
            if ok and chosen is None:
                chosen = seed
            print("| %d | %d of %d | %.4f | %d | %s |" % (
                seed, nsound, len(method_spread.METHODS), worst, len(passers), "yes" if ok else "no"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    shipped = int(open(os.path.join(HERE, "seed.json")).read().split(":")[1].strip(" }\n"))
    print("\nfirst acceptable seed: %s" % (chosen if chosen else "none in this range"))
    print("shipped seed: %d" % shipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
