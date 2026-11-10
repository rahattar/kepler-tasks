"""Route study: the reference and the ways an assessment can go wrong, each run on the shipped scenario through the
emulated laboratory, with every crack's result listed, so that the cracks each route gets right are identified one by
one. 'x' marks a crack whose interval (0.447 x the route's life) is within 0.40-0.50 of its true life.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import numpy as np
import common as C

T, P = "threshold", "paris"
REF = [(P, 0.20, "H1"), (P, 0.35, "H1"), (P, 0.45, "H1"), (P, 0.90, "H1"), (P, 0.70, "H4")]


def fit(camp, **kw):
    """a fit to a campaign, with each untested heat that has an example record read from that record (as the reference
    does for heat H2 from E02)"""
    return C.examples_for_heats(C.fit(C.lab(camp), **kw))


def routes():
    ref = fit(REF)
    base = C.fit(C.lab(REF))
    out = [("reference: Paris H1 .20 .35 .45 .90, H4 .70; linear closure, heat factors (H2 from E02), BS 7910 model",
            ref, {}, "sound")]
    # heats
    for nm, camp in (("H1 only: threshold .85, Paris .10 .30", [(T, .85), (P, .10), (P, .30)]),
                     ("H1 only: five Paris tests .10 .25 .40 .60 .90", [(P, .10), (P, .25), (P, .40), (P, .60), (P, .90)]),
                     ("H1 only: five Paris tests .20 .35 .45 .70 .90", [(P, .20), (P, .35), (P, .45), (P, .70), (P, .90)])):
        out.append((nm + ", H2 from E02, S460NL taken as H1", fit(camp), {}, "defect"))
    out.append(("reference tests, heat H2 taken as H1 (E02 used only as a check)", base, {}, "defect"))
    fs = [C.example_factor(base, e) for e in C.EXAMPLES]
    f = float(np.exp(np.mean(np.log(fs))))
    out.append(("reference tests, H2 as H1, one rate factor x%.2f fitted to both examples" % f, base, dict(fudge=f),
                "defect"))
    out.append(("reference tests, H2 as H1, E02's misfit put down to Mk (extrapolated past L/T = 2)", base,
                dict(mk="uncapped"), "defect"))
    out.append(("reference tests, one law for every heat (the S460NL test pooled; BS 7910's single law)",
                C.fit(C.lab(REF), heats="none"), {}, "defect"))
    # the R effect
    for nm, camp in (("threshold .85 H1, Paris .10 H1, Paris .50 H4", [(T, .85), (P, .10), (P, .50, "H4")]),
                     ("threshold .20 H1, Paris .90 H1, Paris .90 H4", [(T, .20), (P, .90), (P, .90, "H4")]),
                     ("Paris H1 .10 .50 .90, H3 .90, H4 .50 (the second H1 test at BS 7910's R 0.5 split)",
                      [(P, .10), (P, .50), (P, .90), (P, .90, "H3"), (P, .50, "H4")]),
                     ("Paris H1 .05 .60 .90, H3 .90, H4 .50", [(P, .05), (P, .60), (P, .90), (P, .90, "H3"), (P, .50, "H4")])):
        out.append((nm + ", linear closure fit", fit(camp), {}, "defect"))
    out.append(("reference tests, R effect interpolated between the tested R (no closure law)", fit(REF, rform="interp"), {},
                "defect"))
    out.append(("reference tests, Walker R-correction", fit(REF, rform="walker"), {}, "defect"))
    out.append(("reference tests, Newman closure function (alpha, Smax/sigma0 fitted)", fit(REF, rform="newman"), {},
                "defect"))
    out += [
        ("reference tests, no residual stress after PWHT (cycles from the dead load alone)", ref, dict(resid=0.0), "defect"),
        ("reference tests, PWHT residual stress 0.3 yield (BS 7910's value parallel to the weld)", ref, dict(resid=0.3),
         "defect"),
        ("reference tests, residual stress from the grade's specified minimum yield, not the certificate's", ref,
         dict(resid="nominal"), "defect"),
        ("reference tests, survey counts taken over all 35 days on both unloaders", ref, dict(stoppage=False), "defect"),
        ("reference tests, unloader 2's ranges raised but its cycles kept", ref, dict(cycles=False), "defect"),
        ("reference tests, no grab change at all", ref, dict(grab="none"), "defect"),
        ("reference tests, grab change applied to unloader 2's boom only", ref, dict(grab="boom"), "defect"),
        ("reference tests, site welds after PWHT missed (C12, C16 as PWHT)", ref, dict(site_welds=False), "defect"),
        ("reference tests, vibratory stress relief credited as PWHT", ref, dict(vsr=True), "defect"),
        ("reference tests, no weld-toe Mk", ref, dict(mk="none"), "defect"),
        ("reference tests, Mk extrapolated past L/T = 2", ref, dict(mk="uncapped"), "defect"),
        ("reference tests, Mk with L = attachment thickness", ref, dict(L="att"), "defect"),
        ("reference tests, Mk held at its value at the inspected depth", ref, dict(mk="const"), "defect"),
        ("no tests: handbook law and threshold, BS 7910 crack model", C.handbook_law, {}, "defect"),
    ]
    for nm, kw in (("no weld-toe Mk", dict(mk="none")), ("Mk held at its inspected-depth value", dict(mk="const"))):
        f = float(np.exp(np.mean([np.log(C.example_factor(base, e, **kw)) for e in C.EXAMPLES])))
        out.append(("reference tests, %s, rate x%.2f fitted to the examples" % (nm, f), base, dict(kw, fudge=f), "defect"))
    g = C.examples_for_heats(base, face_value=True)
    f = C.example_factor(base, "E01", face_value=True)
    out.append(("reference tests, the examples read with the excavation depth as the crack depth (rate x%.2f, H2 from "
                "E02 the same way)" % f, g, dict(fudge=f), "defect"))
    f = float(np.exp(np.mean([np.log(C.example_factor(C.handbook_law, e)) for e in C.EXAMPLES])))
    out.append(("no tests: handbook law x%.2f fitted to the examples" % f, C.handbook_law, dict(fudge=f), "defect"))
    for nm, camp, kw, kind in (
            ("Paris H1 .10 .30 .90, H3 .90, H4 .90, R effect interpolated between the tested R (no closure law)",
             [(P, .10), (P, .30), (P, .90), (P, .90, "H3"), (P, .90, "H4")], dict(rform="interp"), "defect"),
            ("Paris H1 .30 .70 .90, H3 .30, H4 .70 (both S460NL heats tested, but one H1 test in the closure band)",
             [(P, .90), (P, .70), (P, .30), (P, .30, "H3"), (P, .70, "H4")], {}, "defect"),
            ("reference tests, threshold scaled to low R by the Paris closure", REF, dict(threshold="paris"), "near-sound"),
            ("reference tests, one threshold for every R", REF, dict(threshold="flat"), "near-sound"),
            ("Paris H1 .20 .35 .90, H2 .45, H4 .70 (H2 tested instead of read from E02)",
             [(P, .20), (P, .35), (P, .90), (P, .45, "H2"), (P, .70, "H4")], {}, "near-sound"),
            ("Paris H1 .10 .30 .90, H3 .50 (four slots)", [(P, .10), (P, .30), (P, .90), (P, .50, "H3")], {},
             "near-sound")):
        out.append((nm, fit(camp, **kw), {}, kind))
    return out


if __name__ == "__main__":
    print(__doc__.strip().splitlines()[0])
    print("Seed %d; truth lives (months): %s\n" % (C.SEED, ", ".join("%s %.1f" % (c, C.TRUTH[c]) for c in C.IDS)))
    print("%-4s %-96s %5s %-11s %s" % ("", "route", "right", "kind", " ".join(c[1:] for c in C.IDS)))
    hits = {c: 0 for c in C.IDS}
    ndef = 0
    for i, (nm, law, kw, kind) in enumerate(routes(), 1):
        iv, lv = C.assess(law, **kw)
        n, ok, ratio = C.grade(iv)
        e1, e2 = C.example_factor(law, "E01", **{k: v for k, v in kw.items() if k not in ("fudge", "fudge_on")}), \
            C.example_factor(law, "E02", **{k: v for k, v in kw.items() if k not in ("fudge", "fudge_on")})
        best = max((sum(C.F.LO <= s * lv[c] / C.TRUTH[c] <= C.F.HI for c in C.IDS), s) for s in np.arange(0.30, 0.65, 0.001))
        print("%2d   %-96s %2d/16 %-11s %s" % (i, nm, n, kind, "  ".join("x" if c in ok else "." for c in C.IDS)))
        print("     life / true life %.2f to %.2f; examples' rate factors %.2f (E01) %.2f (E02); best single fraction %.3f "
              "gets %d" % (min(lv[c] / C.TRUTH[c] for c in C.IDS), max(lv[c] / C.TRUTH[c] for c in C.IDS), e1, e2, best[1],
                           best[0]))
        if kind == "defect":
            ndef += 1
            for c in C.IDS:
                hits[c] += c in ok
    print("\nAcross the %d defective routes, the number that get each crack right (no crack is a free pass for all of them):"
          % ndef)
    print("  " + ", ".join("%s %d" % (c, hits[c]) for c in C.IDS))
