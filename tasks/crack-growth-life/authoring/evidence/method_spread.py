"""Method spread: correct methods with different campaigns, test order (other scatter draws), fit details and interval
fractions, on the shipped scenario. Each must get every crack right, and the margins show how far a sound
assessment sits from the edges of the 0.40-0.50 window.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import numpy as np
import common as C


def show(nm, law, fraction=C.FRACTION, **kw):
    iv, lv = C.assess(law, fraction=fraction, **kw)
    n, ok, r = C.grade(iv)
    lr = [lv[c] / C.TRUTH[c] for c in C.IDS]
    print("%-96s %2d/16  life/true %.3f-%.3f  interval/life %.3f-%.3f  E01 %.2f E02 %.2f" % (
        nm, n, min(lr), max(lr), min(r.values()), max(r.values()), C.example_factor(law, "E01", **kw),
        C.example_factor(law, "E02", **kw)))
    return n, min(r.values()), max(r.values())


if __name__ == "__main__":
    print("Method spread on the shipped scenario (seed %d); window 0.40-0.50 of the true life, gate %d.\n" % (C.SEED, C.F.GATE))
    print("%-96s %5s" % ("method", "right"))
    res = []
    T, P = "threshold", "paris"
    fit = lambda camp, **kw: C.examples_for_heats(C.fit(C.lab(camp), **kw))  # noqa: E731
    REF = [(P, 0.20, "H1"), (P, 0.35, "H1"), (P, 0.45, "H1"), (P, 0.90, "H1"), (P, 0.70, "H4")]
    ref = fit(REF)
    print("reference fit: m %.2f, p %.2f, closure-free threshold %.2f (BS 7910's line 5.38 - 6.77 R where higher), "
          "U0 %.3f, closure-free from R %.2f; heat rate factors %s (H2 from E02); E01 needs x%.3f\n" % (
              ref.m, ref.p, ref.q[2], ref.q[4], ref.rc, ", ".join("%s %.2f" % kv for kv in sorted(ref.hf.items())),
              C.example_factor(ref, "E01")))
    res.append(show("reference: Paris H1 .20 .35 .45 .90, H4 .70; interval 0.447 x life", ref))
    for f in (0.43, 0.46):
        res.append(show("reference, interval %.3f x life" % f, ref, fraction=f))
    res.append(show("reversed order (other scatter draws)", fit(REF[::-1])))
    res.append(show("reference tests, threshold scaled to low R by the Paris closure", fit(REF, threshold="paris")))
    res.append(show("reference tests, one fitted threshold for every R", fit(REF, threshold="flat")))
    for camp in ([(P, .10), (P, .30), (P, .50), (P, .90), (P, .60, "H3")],
                 [(P, .10), (P, .25), (P, .45), (P, .90), (P, .50, "H3")],
                 [(P, .20), (P, .35), (P, .90), (P, .45, "H2"), (P, .70, "H4")],
                 [(P, .10), (P, .30), (P, .90), (P, .50, "H3")],
                 [(P, .15), (P, .30), (P, .80), (P, .50, "H3"), (P, .50, "H4")]):
        res.append(show(", ".join("%s %.2f %s" % (k[0], k[1], k[2] if len(k) > 2 else "H1") for k in camp), fit(camp)))
    print("\nEvery method above gets %d of 16 or more; across them the interval lies within %.3f to %.3f of the true "
          "life, against the window 0.40-0.50." % (min(n for n, _, _ in res), min(a for _, a, _ in res),
                                                    max(b for _, _, b in res)))
