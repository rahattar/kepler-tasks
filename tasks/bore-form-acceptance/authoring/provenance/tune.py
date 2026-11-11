"""Tuning aid, not shipped behaviour: given a target verdict and margin for every feature, it solves the mean size
each one needs and prints the FEATURES table to paste back into isim.py, then the truths that result.

    python3 tune.py            check the table as it stands
    python3 tune.py solve      print the table that hits the targets
"""
import sys

import numpy as np

import isim as S

# feature -> target verdict, target form (um) through its setup's amplitude scale, drawing tolerance (um),
# target size margin (um, signed: positive accepts)
TARGET = {
    "CB-21": ("accept",      27.5,  +11.0),
    "CB-22": ("reject_size", 20.0,   -9.0),
    "CB-23": ("reject_form", 15.0,   +7.0),
    "CB-24": ("reject_form", 11.5,  +12.0),
    "CB-25": ("reject_both", 11.5,   -8.0),
    "CB-26": ("reject_size", 33.0,   -6.0, "local"),
    "GB-31": ("reject_both", 17.0,   -7.0),
    "GB-32": ("accept",      24.0,  +13.0),
    "RJ-41": ("reject_size", 30.0,   -8.0),
    "RJ-42": ("reject_form", 22.5,  +12.0),
    "RJ-43": ("reject_both", 22.5,   -9.0),
    "RJ-44": ("accept",      17.5,   +5.0),
    "RJ-45": ("reject_form", 18.5,   +4.5),
    "RJ-46": ("reject_size", 26.5,  -11.0, "local"),
}
# the form each setup's lobing should give, chosen so that every "accept" sits 1.5 to 3 um inside its tolerance
# (a least-squares zone, 8 to 20 % high, then falls outside) and every form reject is clear of it
# The form each setup's lobing is scaled to reach, read on the feature named in SETUP_REF (the first feature of
# the setup in ORDER unless named). The values are chosen so that, within each verdict, no two features' form
# errors are closer than twice the grading band: a sheet that names one form figure and one verdict for all 14
# features must not be able to earn credit on two of them. preflight.py enforces the spacing.
SETUP_FORM = {"S1": 24.0, "S2": 15.0, "S3": 14.0, "S4": 20.5, "S5": 18.5, "S6": 26.0, "S7": 29.5, "S8": 22.0}

# Where the setup's scale is read off a feature other than the first: S3's scale is set from RJ-44, whose
# roundness does not depend on CB-22's taper, so CB-22's taper can then be solved for on its own.
SETUP_REF = {"S3": "RJ-44"}

# The form each feature is meant to land on, for the spacing check below. The second feature of a setup is
# brought to its value by its own taper (a cylindricity callout) or its own ovality (RJ-46).
FORM_WANT = {"CB-21": 24.0, "CB-22": 16.5, "CB-23": 18.5, "CB-24": 15.0, "CB-25": 15.0, "CB-26": 29.5,
             "GB-31": 20.5, "GB-32": 20.5, "RJ-41": 26.5, "RJ-42": 26.0, "RJ-43": 26.0, "RJ-44": 14.0,
             "RJ-45": 22.0, "RJ-46": 23.1}


def profiles(f, scale=None):
    """The assessment profile of the true surface at each section, with the setup amplitudes optionally scaled."""
    old = None
    if scale is not None:
        old = S.SETUP[S.FEATURES[f]["setup"]]
        S.SETUP[S.FEATURES[f]["setup"]] = {n: (a * scale, p) for n, (a, p) in old.items()}
    ths, devs = [], []
    for j in range(len(S.SECTIONS)):
        th = np.arange(S.TESTER_PTS) / S.TESTER_PTS * 2.0 * np.pi
        ths.append(th)
        devs.append(S.assess_profile(th, S.surface(f, j, th)))
    if old is not None:
        S.SETUP[S.FEATURES[f]["setup"]] = old
    return ths, devs


def form_of(f, ths, devs):
    """The form error truth() would report, so SETUP_FORM and FORM_WANT are in the units of the answer. A
    cylindricity zone is taken over the sections about the mean size, which is what keeps the taper in it; the
    taper is a property of the feature and not of the setup's lobing, so for the second feature of a setup it is
    the knob that moves its form without moving its twin's."""
    d = S.FEATURES[f]
    kind = d["tol"][0]
    if kind != "cylindricity":
        return max(S.roundness(t, p) for t, p in zip(ths, devs))
    bar = sum(d["mean"]) / len(d["mean"])
    whole = [(d["mean"][j] - bar) + devs[j] for j in range(len(S.SECTIONS))]
    return S.cylindricity(ths, whole, [s - 0.5 for s in S.SECTIONS])


def solve():
    # one amplitude scale per setup, from the first feature that uses it
    scales = {}
    for s, target in SETUP_FORM.items():
        f = SETUP_REF.get(s) or next(f for f in S.ORDER if S.FEATURES[f]["setup"] == s)
        lo, hi = 0.3, 3.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if form_of(f, *profiles(f, mid)) < target:
                lo = mid
            else:
                hi = mid
        scales[s] = round((lo + hi) / 2, 4)
    print("# setup amplitude scales:", scales)
    rows = []
    for f in S.ORDER:
        d = S.FEATURES[f]
        sc = scales[d["setup"]]
        ths, devs = profiles(f, sc)
        patt = [m - d["mean"][0] for m in d["mean"]]        # keep the shape of the mean variation
        mdev = [S.mating_dev(d["kind"], t, p) for t, p in zip(ths, devs)]
        verdict, tol, smarg = TARGET[f][:3]
        on = TARGET[f][3] if len(TARGET[f]) > 3 else "mating"
        lo, hi = d["lim"]
        if on == "local":
            # place the mean from the two-point extreme instead: these features are decided by a local size
            pairs = [S.local_sizes(t, p) for t, p in zip(ths, devs)]
            if d["kind"] == "bore":
                m = (hi - smarg - max(2.0 * q + float(pr.max()) for q, pr in zip(patt, pairs))) / 2.0
            else:
                m = (lo + smarg - min(2.0 * q + float(pr.min()) for q, pr in zip(patt, pairs))) / 2.0
        elif d["kind"] == "bore":
            m = (smarg + lo) / 2.0 - min(p + q for p, q in zip(patt, mdev))
        else:
            m = (hi - smarg) / 2.0 - max(p + q for p, q in zip(patt, mdev))
        mean = tuple(round(m + p, 1) for p in patt)
        harm = {n: (round(a * sc, 2), p) for n, (a, p) in S.SETUP[d["setup"]].items()}
        rows.append((f, d, mean, tol, harm))
    print("\n# paste into isim.py: SETUP (scaled) and FEATURES (mean, tol)")
    print("SETUP = {")
    for s in SETUP_FORM:
        h = {n: (round(a * scales[s], 2), p) for n, (a, p) in S.SETUP[s].items()}
        print('    "%s": {%s},' % (s, ", ".join("%d: (%.2f, %.2f)" % (n, a, p) for n, (a, p) in sorted(h.items()))))
    print("}")
    for f, d, mean, tol, _ in rows:
        print('    "%s": mean=%s, tol=("%s", %.1f),' % (f, mean, d["tol"][0], tol))


def check():
    print("%-7s %-8s %-13s %6s %5s %7s %7s %7s  %-12s %s" % (
        "feat", "kind", "tol", "form", "tol", "formMg", "sizeMg", "locMg", "verdict", "target"))
    bad = 0
    for f in S.ORDER:
        t = S.truth(f)
        d = S.FEATURES[f]
        want = TARGET[f][0]
        flag = "" if t["verdict"] == want else "   <-- wanted %s" % want
        bad += t["verdict"] != want
        print("%-7s %-8s %-13s %6.2f %5.1f %+7.2f %+7.1f %+7.1f  %-12s%s" % (
            f, d["kind"], d["tol"][0], t["form"], t["tol"], t["form_margin"], t["size_margin"],
            t["local_margin"], t["verdict"], flag))
    print("\n%d of %d features off target" % (bad, len(S.ORDER)))
    v = {}
    for f in S.ORDER:
        k = S.truth(f)["verdict"]
        v[k] = v.get(k, 0) + 1
    print("verdicts:", v)
    print("sparse (no usable form in the records):", ", ".join(S.SPARSE))
    pairs = {}
    for f in S.SPARSE:
        pairs.setdefault(S.FEATURES[f]["setup"], []).append(f)
    print("sparse setups:", {k: v for k, v in pairs.items()})


if __name__ == "__main__":
    (solve if "solve" in sys.argv else check)()
