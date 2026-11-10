"""Chooses the laboratory's scatter seed.

    python3 authoring/provenance/seed_screen.py      (writes authoring/evidence/seed_screen.txt)

The seed drives only the laboratory's scatter (one normal draw of NOISE HRC per test). Starting from 6401, the first
seed is taken on which
  - nine sound plans (the reference, its tests in reverse order, PCHIP, Hollomon-Jaffe constants 19 and 21, the
    laboratory temperatures 10 C below and above, 52-1250 tested at B07, and the independent solution) all get 13 of
    13 with at least 0.5 HRC to spare on every batch, and
  - no reading those plans draw lies more than 2.5 standard deviations from its mean.
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "evidence"))
import common as C  # noqa: E402
import independent  # noqa: E402

REF = C.REF_PLAN
PLANS = [("reference", dict(plan=REF)), ("reverse order", dict(plan=REF[::-1])),
         ("PCHIP", dict(plan=REF, model_kw=dict(interp="pchip"))), ("C 19", dict(plan=REF, model_kw=dict(c_hj=19.0))),
         ("C 21", dict(plan=REF, model_kw=dict(c_hj=21.0))), ("lab -10 C", dict(plan=REF, lab_dT=-10)),
         ("lab +10 C", dict(plan=REF, lab_dT=10)), ("52-1250 at B07", dict(plan=[("B07", True)] + REF[1:]))]
MIN_MARGIN = 0.5
MAX_Z = 2.5


def zmax(lab):
    S = C.S
    return max(abs(h - S.tempered(heat, T, D, loc, 2.0, n)) / S.NOISE for heat, T, D, loc, n, h in lab.log)


def screen(seed):
    worst, z = 99.0, 0.0
    for name, kw in PLANS:
        temps, lab = C.run(seed=seed, **kw)
        worst = min(worst, min(C.margin(b, T) for b, T in temps.items()))
        z = max(z, zmax(lab))
    temps, n, txt = independent.main(seed)
    worst = min(worst, min(C.margin(b, T) for b, T in temps.items()))
    return worst, z


def main():
    lines = [__doc__.strip().splitlines()[0], ""]
    for seed in range(6401, 6501):
        worst, z = screen(seed)
        ok = worst >= MIN_MARGIN and z <= MAX_Z
        lines.append("seed %d: smallest margin over the nine sound plans %+.3f HRC, largest reading offset %.2f sigma %s" % (
            seed, worst, z, "ACCEPTED" if ok else "rejected"))
        if ok:
            lines.append("")
            lines.append("chosen seed %d (limits: margin >= %.1f HRC, offsets <= %.1f sigma)" % (seed, MIN_MARGIN, MAX_Z))
            return seed, "\n".join(lines)
    raise SystemExit("no seed found")


if __name__ == "__main__":
    seed, txt = main()
    print(txt)
    open(os.path.join(ROOT, "authoring", "evidence", "seed_screen.txt"), "w").write(txt + "\n")
