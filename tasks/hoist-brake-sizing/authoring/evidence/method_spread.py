"""Method spread: sound ways of doing the selection, each graded by the sealed definition.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt

Every method reads the records as the reference does and tests both linings across the temperatures their hoists
reach, including O2 near H05's 185-210 C, and H05's engagement at a reduced setting with AC switching. They differ in
the test temperatures, the order of the tests (so the laboratory's scatter draws differ), the curve through the
friction points, the form of the engagement law, how the emergency stop's own heating is treated, the backdriving
efficiency, and the rule that picks the setting inside the window. Each line gives the hoists that meet every
requirement under the sealed definition and, over the twelve selections, the smallest true margin (the smallest of
the five requirements' margins, as a fraction of the limit).
"""
import numpy as np

import common as C
import solve as R
from common import F, E

REF = C.REF_PLAN
LOW = [F(20), F(50), F(150), F(20, "O2"), F(150, "O2"), F(190, "O2"), F(250, "O2"), E("S16", 66, "AC")]
HIGH = [F(20), F(70), F(170), F(20, "O2"), F(170, "O2"), F(210, "O2"), F(270, "O2"), E("S16", 62, "AC")]
ENG70 = REF[:7] + [E("S16", 70, "AC")]


def centre_select(M, H, reach=R.REACH):
    """setting in the middle of the model's window on the size with the widest window"""
    picks = {}
    for hid, h in H.items():
        best = None
        for size in M.cat:
            r = R.margins(M, h, size)
            worst = np.min([r[k] for k in R.REQ], axis=0)
            worst = np.where(np.maximum(r["Tp"], r["Tend"]) <= M.top(M.cat[size]["lining"]) + reach, worst, -np.inf)
            ok = np.flatnonzero(worst >= 0)
            if not len(ok):
                continue
            i = int(ok[len(ok) // 2])
            if best is None or len(ok) > best[0]:
                best = (len(ok), size, int(R.SETTINGS[i]), {k: float(r[k][i]) for k in r})
        picks[hid] = best
    return picks


def line(name, picks):
    n, fails = C.grade(picks)
    worst = min(C.truth_margin(hid, p[1], p[2]) for hid, p in picks.items())
    print("%-78s %2d/12  smallest true margin %+.3f  %s" % (name, n, worst, " ".join(fails)), flush=True)
    return n


def main():
    print(__doc__.split("\n\n")[0].strip())
    print("Shipped scenario, laboratory seed %d.\n" % C.SEED)
    rows = [
        ("reference: O1 20/60/160, O2 20/160/200/260, engage S16 65 AC", dict(plan=REF)),
        ("reference tests in reverse order (other scatter draws)", dict(plan=REF[::-1])),
        ("reference tests, shape-preserving cubic (PCHIP) through the friction points", dict(plan=REF, cls=C.Pchip)),
        ("reference tests, engagement t100 (1 + kappa ln(100/setting))", dict(plan=REF, cls=C.LogLaw)),
        ("reference tests, friction held at the duty temperature through the stop", dict(plan=REF, stop_heating=False)),
        ("reference tests, backdriving efficiency taken as eta", dict(plan=REF, backdrive="eta")),
        ("reference tests, engagement test at S16 70 instead of 65", dict(plan=ENG70)),
        ("temperatures 10 C lower: O1 20/50/150, O2 20/150/190/250, engage S16 66", dict(plan=LOW)),
        ("temperatures 10 C higher: O1 20/70/170, O2 20/170/210/270, engage S16 62", dict(plan=HIGH)),
    ]
    for name, kw in rows:
        picks, n, fails = C.run(**kw)
        line(name, picks)
    M = C.model(C.lab(REF))
    line("reference tests, setting in the middle of the widest window", centre_select(M, C.H0))


if __name__ == "__main__":
    main()
