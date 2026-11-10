"""How the fitted ratings in isim.py were set, and a check that they still follow from the rules.

    python3 authoring/provenance/tune.py

Design rules. The frame's stroke, the bores, the rods, the clearances, the pocket volumes, the weights, the
temperatures, the pipeline pressure and the contract flow are the plant's; the ratings below are fitted.

1. The six cylinders are to be governed by at least four different requirements of the standard, so that no answer
   can be had by finding one limit and carrying it across. Pin reversal governs none of them: it is met throughout
   every range with at least twice the standard's least angle, so a solver who keeps the inertia load finds it
   slack and a solver who drops it finds no range at all.
2. Each governing bound stands at least 5 per cent clear of the cylinder's runner-up, so that a route which misses
   a term flips the requirement rather than landing on the same one by luck.
3. Every cylinder is capable at today's duty, with at least 1 per cent of margin on every requirement. The machine
   is tightly rated for the duty it runs now, which is why the study is being done at all.
4. One rating of each cylinder decides which requirement governs it, and that rating is the whole step a data sheet
   would carry (5 kN of rod load or allowable gas load, 2 kW of power) nearest the figure that puts its
   requirement's bound at the authored target below. The ratings that do not govern are set so that their own
   requirements bind inside the range as well, but below the governing one by the margin rule 2 asks for; rule 2
   is what checks them.

   | cylinder | the rating that decides it      | its requirement       | target bar |
   |---|---|---|---|
   | 1A | rated rod load of throw 1       | rod load in tension   | 19.3 |
   | 1B | rated power                     | cylinder power        | 22.6 |
   | 2A | rated power                     | cylinder power        | 19.4 |
   | 2B | rated power                     | cylinder power        | 20.6 |
   | 3A | the de-rated crosshead load     | rod load in compression | 18.6 |
   | 3B | none: the discharge temperature limit is the standard's and is shared | discharge temperature | - |

The script recomputes every fitted rating from these rules and fails if any differs from isim's.
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isim as S  # noqa: E402

GAP = 0.05
TODAY = 0.01
LABELS = 4
INTENDED = {"1A": "rod_load_tension", "1B": "cylinder_power", "2A": "cylinder_power",
            "2B": "cylinder_power", "3A": "rod_load_compression", "3B": "discharge_temperature"}
KNOB = {"1A": ("rod", 5.0, 19.3), "1B": ("kw", 2.0, 22.6), "2A": ("kw", 2.0, 19.4),
        "2B": ("kw", 2.0, 20.6), "3A": ("derate", 5.0, 18.6), "3B": (None, None, None)}
CURVE = {"rod_load_compression": "comp", "rod_load_tension": "tens", "gas_load": "gas",
         "cylinder_power": "kw"}


def curves(cid):
    """the peak each requirement reaches at every field pressure of the range, in its own units"""
    m = S.margins(cid)
    lim = S.rod_limit(cid)
    return {"comp": lim / (m["rod_load_compression"] + 1.0), "tens": lim / (m["rod_load_tension"] + 1.0),
            "gas": S.CYL[cid]["glim"] / (m["gas_load"] + 1.0),
            "kw": S.CYL[cid]["kw"] / (m["cylinder_power"] + 1.0),
            "td": S.TD_LIMIT / (m["discharge_temperature"] + 1.0)}


def fitted(cid):
    """the rating the rule asks for, and the peaks the other requirements reach"""
    g, _, _, _, inside = S.table()
    c = curves(cid)
    knob, step, target = KNOB[cid]
    want = None
    if knob is not None:
        key = CURVE[INTENDED[cid]]
        want = step * round(float(np.interp(target, g, c[key])) / step)
        if knob == "rod":
            want = 5.0 * round(want / S.BULLETIN / 5.0)
    peaks = {k: float(np.max(v[inside])) for k, v in c.items()}
    return want, peaks


def main():
    bad = 0
    g, p12, p23, speed, inside = S.table()
    print("the duty: field %.2f bar, pipeline %.1f bar, contract %.1f kmol/h" % (
        S.FIELD_TODAY, S.PIPE, S.CONTRACT))
    print("today the interstage pressures settle at %.2f and %.2f bar and the speed is %.1f rev/min" % (
        p12[-1], p23[-1], speed[-1]))
    print("the range runs from %.2f bar, where the speed reaches the rated %.0f, up to %.2f bar\n" % (
        g[inside][0], S.FRAME["rpm_rated"], g[-1]))

    print("fitted ratings")
    for cid in sorted(S.CYL):
        knob, step, target = KNOB[cid]
        want, _ = fitted(cid)
        if knob is None:
            print("  %-3s none: the standard's discharge temperature limit of %.0f C decides it" % (
                cid, S.TD_LIMIT))
        else:
            have = {"rod": S.ROD_RATED[S.CYL[cid]["throw"]], "kw": S.CYL[cid]["kw"],
                    "derate": S.DERATED.get(cid)}[knob]
            ok = have == want
            bad += not ok
            print("  %-3s %-8s %7.1f   the rule asks for %7.1f   %s" % (
                cid, knob, have, want, "matches isim" if ok else "DIFFERS"))

    print("\ncylinders")
    labels = {}
    for cid in sorted(S.CYL):
        ps, who = S.ps_min(cid)
        labels[who] = labels.get(who, 0) + 1
        b = {r: S.bound(cid, r) for r in S.REQ}
        order = sorted(((v, r) for r, v in b.items() if v is not None), reverse=True)
        gap = (order[0][0] - order[1][0]) / order[0][0] if len(order) > 1 else 1.0
        m = S.margins(cid)
        today = min(float(m[q][-1]) for q in S.REQ)
        rev = float(np.min((m["pin_reversal"][inside] + 1.0) * S.REV_MIN))
        fine = (who == INTENDED[cid]) and gap >= GAP and today >= TODAY and rev >= 2 * S.REV_MIN
        bad += not fine
        print("  %-3s %7.2f bar  %-22s gap %5.1f %% to %-22s margin today %5.1f %%  reversal >= %3.0f deg  %s" % (
            cid, ps, who, 100.0 * gap, order[1][1] if len(order) > 1 else "-", 100.0 * today, rev,
            "ok" if fine else "FAILS"))

    print("\nrequirements")
    for r in S.REQ:
        n = labels.get(r, 0)
        fine = n == 0 if r == "pin_reversal" else True
        bad += not fine
        print("  %-22s governs %d cylinder(s)   %s" % (r, n, "ok" if fine else "FAILS"))
    distinct = len([r for r in S.REQ if labels.get(r, 0)])
    bad += distinct < LABELS
    print("  %d different requirements govern the six cylinders   %s" % (
        distinct, "ok" if distinct >= LABELS else "FAILS"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
