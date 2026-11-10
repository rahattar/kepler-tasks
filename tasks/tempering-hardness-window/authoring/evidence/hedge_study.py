"""Hedges: for each choice an agent must make, whether one setpoint is right for a batch under both answers.

    python3 authoring/evidence/hedge_study.py      (writes hedge_study.txt)

The gate is all 13 batches, so a hedge across batches (some batches one way, some the other) loses the batches given
the wrong answer. Within a batch, a hedge exists when the batch's windows under the two answers overlap.
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

S = C.S


def window_under(b, hardness):
    part, heat, D, loc, (lo, hi) = S.BATCHES[b]
    return set(T for T in range(S.TMIN[S.HEATS[heat][0]], 701) if lo <= hardness(T) <= hi)


def true_h(b):
    return lambda T: S.batch_hardness(b, T)


def heat_as(b, other):
    part, heat, D, loc, w = S.BATCHES[b]
    return lambda T: S.tempered(other, T, D, loc, S.soak_hours(D), S.NTEMPER[S.HEATS[heat][0]])


def single_read(b):
    """what a single-test, double-as-twice-the-time reading of the heat implies: the double temper plus the fresh martensite"""
    part, heat, D, loc, w = S.BATCHES[b]
    f = S.fmart(heat, S.jeq(D, loc))
    return lambda T: S.batch_hardness(b, T) + f * S.RA[heat] / (1 + np.exp(-(T - 520.0) / 10.0))


def supplier_hj(b):
    """the supplier's single-temper curve converted by Hollomon-Jaffe (an untested G52 heat taken as the curve)"""
    part, heat, D, loc, w = S.BATCHES[b]

    def h(T):
        Teq = S.t_equiv(T, S.soak_hours(D), 2)
        lo, hi = 300.0, 800.0
        for _ in range(50):
            m = 0.5 * (lo + hi)
            lo, hi = (m, hi) if S.t_equiv(m, 2.0, 1) < Teq else (lo, m)
        return S.tempered("52-typ", 0.5 * (lo + hi), D, loc, 2.0, 1)
    return h


def no_soak(b):
    part, heat, D, loc, w = S.BATCHES[b]
    return lambda T: S.tempered(heat, T, D, loc, 2.0, S.NTEMPER[S.HEATS[heat][0]])


def no_section(b):
    part, heat, D, loc, w = S.BATCHES[b]
    return lambda T: S.tempered(heat, T, 25.0, "half-radius", S.soak_hours(D), S.NTEMPER[S.HEATS[heat][0]])


CHOICES = [
    ("B09 on the batch list's heat 41-7731 or the log's 41-7864", [("B09", lambda b: heat_as(b, "41-7731"))]),
    ("43-2288 as its sibling 43-2210", [("B12", lambda b: heat_as(b, "43-2210"))]),
    ("G52 single test read with double = twice the time", [(b, single_read) for b in ("B06", "B07", "B08", "B11", "B13")]),
    ("an untested G52 heat as the supplier curve (Hollomon-Jaffe)", [(b, supplier_hj) for b in ("B06", "B07", "B08", "B11", "B13")]),
    ("52-1250 as 52-1312", [(b, lambda b: heat_as(b, "52-1312")) for b in ("B07", "B11")]),
    ("52-1312 as 52-1250", [(b, lambda b: heat_as(b, "52-1250")) for b in ("B06", "B08")]),
    ("52-1377 as 52-1312", [("B13", lambda b: heat_as(b, "52-1312"))]),
    ("52-1377 as 52-1250", [("B13", lambda b: heat_as(b, "52-1250"))]),
    ("soak time: 2 h or 1 h per 25 mm", [(b, no_soak) for b in S.BATCHES if S.BATCHES[b][2] > 50]),
    ("section: 25 mm half-radius or the batch's own", [(b, no_section) for b in S.BATCHES if S.BATCHES[b][2] != 25]),
]


def main():
    out = []
    for name, items in CHOICES:
        row = []
        for b, alt in items:
            Wt, Wa = window_under(b, true_h(b)), window_under(b, alt(b))
            common = sorted(Wt & Wa)
            row.append("%s %s" % (b, ("common %d-%d (%d C)" % (common[0], common[-1], len(common))) if common else "none"))
        nohedge = sum(r.endswith("none") for r in row)
        out.append("%s: no common setpoint on %d of %d batches\n    %s" % (name, nohedge, len(row), "; ".join(row)))
    return "\n".join(out)


if __name__ == "__main__":
    txt = main()
    print(txt)
    open(os.path.join(HERE, "hedge_study.txt"), "w").write(txt + "\n")
