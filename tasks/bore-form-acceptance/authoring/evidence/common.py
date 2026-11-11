"""Shared engine for the evidence scripts. It reads the shipped records the agent reads, orders scans through the
metrology room's own function, and uses the sealed definition only for the scan and for grading.

    sentence(plan, **route)   the sentence every feature gets under one route
    grade(answers)            against the sealed truth

A feature's sentence depends only on which record its shape comes from, which record its size comes from, and the
route; those are memoised, so a study can cross every way of spending the booking without recomputing the fits.
"""
import csv
import importlib.util
import os
import sys
import tempfile

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "provenance"))
import isim as S  # noqa: E402

DATA = os.path.join(HERE, "..", "..", "environment", "data")

# Grading goes through the verifier's own module, on a written sheet, so what a study measures is what the
# verifier would decide: the same CSV reader, the same two-decimal figures, the same comparison, the same gate.
# tests/sealed/isim.py is byte-identical to the copy imported above (preflight.py checks that), and truth() is a
# pure function of the feature, so it is memoised here; without that a study of a thousand bookings would spend
# its life re-solving the same fourteen minimum-zone problems. verifier_runs.py goes further and runs the whole
# pytest verifier in a clean subprocess on complete sheets.
_spec = importlib.util.spec_from_file_location(
    "grade_form_evidence", os.path.join(HERE, "..", "..", "tests", "grade_form.py"))
GRADER = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(GRADER)
_truth_memo = {}
_truth_real = GRADER.S.truth
GRADER.S.truth = lambda k: _truth_memo[k] if k in _truth_memo else _truth_memo.setdefault(k, _truth_real(k))

TOL_FORM = GRADER.TOL   # um, the band the verifier allows on a reported form error
ALPHA = 11.7
MIN_PTS = 101           # fewer points a revolution than this cannot resolve the 2 to 50 UPR band


def _rows(name):
    with open(os.path.join(DATA, name)) as f:
        return list(csv.DictReader(f))


INDEX = {r["feature"]: r for r in _rows("measurement_index.csv")}
DRAW = {r["feature"]: r for r in _rows("drawing_requirements.csv")}
REG = {r["feature"]: r for r in _rows("feature_register.csv")}
LOG = _rows("machining_log.csv")
ORDER = list(INDEX)
SETUP_OF = {}
for _r in LOG:
    if _r["setup"] != "-":
        for _f in _r["features_in_this_setup"].split():
            SETUP_OF[_f] = _r["setup"]
# a record that cannot carry its feature's form: too few points for the band, or overtaken by later work
STALE = [f for f in ORDER if any(f in r["features_in_this_setup"].split() and r["setup"] == "-"
                                 and r["date"] > INDEX[f]["measured_on"] and "booking" not in r["note"]
                                 for r in LOG)]
SPARSE = [f for f in ORDER if int(INDEX[f]["points_per_rev"]) < MIN_PTS]
NEED = [f for f in ORDER if f in SPARSE or f in STALE]
BUDGET = S.BUDGET
_cache = {}


def shop_record(f):
    rows = _rows(os.path.join("measurements", os.path.basename(INDEX[f]["file"])))
    secs = {}
    for r in rows:
        secs.setdefault(float(r["section_mm"]), []).append((float(r["angle_deg"]), float(r["radius_mm"])))
    out = []
    for z in sorted(secs):
        a = np.array(sorted(secs[z]))
        out.append((np.radians(a[:, 0]), a[:, 1]))
    return out, float(INDEX[f]["room_c"])


def scan_record(f, k):
    return list(S.scan(f, k, S.SEED_SCAN)), S.T_ROOM


def _source(src):
    return shop_record(src[0]) if src[1] is None else scan_record(src[0], src[1])


def band_pass(th, dev, filt):
    """filt: "band" is FM-7 (order 0 and 1 out, Gaussian 50 UPR taper); "order1" centres the profile but leaves the
    waviness in; "none" takes the deviations as measured, eccentricity and all."""
    if filt == "band":
        return S.assess_profile(th, dev)
    if filt == "none":
        return dev
    n = len(dev)
    F = np.fft.rfft(dev) / n
    return dev - F[0].real - 2.0 * (F[1].real * np.cos(th) - F[1].imag * np.sin(th))


def section_data(secs, T, tcorr=True, filt="band"):
    means, profs, ths = [], [], []
    for th, r in secs:
        m = float(np.mean(r))
        if tcorr:
            m = m / (1.0 + ALPHA * 1e-6 * (T - 20.0))
        means.append(m)
        profs.append(band_pass(th, (r - np.mean(r)) * 1000.0, filt))
        ths.append(th)
    return means, profs, ths


_spin = {}


def regrease_date():
    """The day the maintenance log says the form tester's spindle was re-greased and its preload reset."""
    for r in LOG:
        if "form tester" in r["machine"] and "spindle" in r["operation"]:
            return r["date"]
    return None


def tester_groups():
    """The tester's records, split by whether they were taken before or after that maintenance. Its error motion
    is not the same on the two sides of it, so one estimate pooled over all of them belongs to neither."""
    day = regrease_date()
    groups = {}
    for g in ORDER:
        if g in SPARSE:
            continue
        key = "after" if (day and INDEX[g]["measured_on"] > day) else "before"
        groups.setdefault(key, []).append(g)
    return groups


def group_of(f):
    day = regrease_date()
    return "after" if (day and INDEX[f]["measured_on"] > day) else "before"


def _spectrum(g, filt):
    """The Fourier coefficients of one tester record: its sections averaged, since one clamping serves all three."""
    secs, T = shop_record(g)
    _, p, _ = section_data(secs, T, filt=filt)
    a = np.mean(np.array(p), axis=0)
    return np.fft.rfft(a) / len(a), len(a)


def _twins(members):
    """The pairs of records in a campaign whose features were finished in one boring setup. The honed bore's
    record counts with its setup: it was taken before the hone, when the bore still had the setup's lobing."""
    by = {}
    for g in members:
        by.setdefault(SETUP_OF[g], []).append(g)
    return [tuple(v) for v in by.values() if len(v) == 2]


def _rotation(Fa, Fb, m, skip=()):
    """The angle by which record a's part sits round from record b's, their features being twins of one setup.
    The twins carry the same lobing, so with the machine's share m taken off, a's coefficient at order k is b's
    turned by k times that angle; the angle is the one that makes all the orders agree at once."""
    # Turning a part round changes the phase of each order and leaves its amplitude alone. So the orders to fix
    # the angle with are those at which the two records agree in amplitude: where they do not, something other
    # than the shared lobing is in one of them, the machine or a mark of the part's own, and that order would
    # pull the angle off. Using every order here costs a few hundredths of a radian, and eleven times that is
    # enough to spoil the machine's vector at order 11.
    A, B = Fa - m, Fb - m
    ks = np.array([k for k in range(2, 51) if k not in skip and 2.0 * max(abs(A[k]), abs(B[k])) > 0.3
                   and abs(abs(A[k]) - abs(B[k])) < 0.12 * max(abs(A[k]), abs(B[k]))])
    cross = A[ks] * np.conj(B[ks])
    grid = np.linspace(0.0, 2.0 * np.pi, 7200, endpoint=False)
    score = (cross[None, :] * np.exp(1j * np.outer(grid, ks))).real.sum(axis=1)
    d = grid[int(np.argmax(score))]
    for step in (2e-4, 2e-5, 2e-6):                       # refine about the best grid point
        fine = d + np.arange(-5, 6) * step
        d = fine[int(np.argmax((cross[None, :] * np.exp(1j * np.outer(fine, ks))).real.sum(axis=1)))]
    return float(d)


def twin_model(group, filt="band", orders=None, tell=None):
    """The tester's error motion in one campaign, order by order, with the parts' lobing told apart from it.

    A record's coefficient at order k is the machine's, m, plus the part's. Where no part has anything at that
    order the records of a campaign agree and their mean is m. Where the setups left lobing at that order they do
    not agree, and the mean is m plus whatever the parts happen to sum to. The twins settle it: the two records
    of a setup's pair are  Fa = m + c  and  Fb = m + c exp(ik d)  with d the angle between the two clampings,
    which the other orders fix, so  m = (Fa - Fb exp(-ik d)) / (1 - exp(-ik d)).  Every pair of the campaign has
    to give the same m, which is what tells a machine order from a part that merely differs from its twin.

    orders=None finds the machine's orders, which needs two pairs to agree; a campaign with one pair is given the
    orders found in the other, the orders being the spindle bearing's geometry, which a re-grease does not alter.
    Returns the coefficients (zero off the machine's orders)."""
    members = tester_groups()[group]
    F = {g: _spectrum(g, filt)[0] for g in members}
    n = _spectrum(members[0], filt)[1]
    pairs = _twins(members)
    m = np.zeros(n // 2 + 1, dtype=complex)
    found = set()
    # The lines every record of the campaign agrees on need no angle to find, and they have to come out before
    # any angle is fitted: a line that is the same in both records of a pair says the parts sit at the same
    # angle, whatever angle they sit at, and it is strong enough to drag the fit there.
    for k in range(2, 51):
        mean = np.mean([F[g][k] for g in members])
        if 2.0 * abs(mean) > 0.5 and max(abs(F[g][k] - mean) for g in members) < 0.25 * abs(mean):
            m[k] = mean
            found.add(k)
    for sweep in range(4):                                # the machine's share and the angles settle together
        ang = {p: _rotation(F[p[0]], F[p[1]], m, skip=found) for p in pairs}
        m = np.zeros_like(m)
        now = set()
        for k in range(2, 51):
            mean = np.mean([F[g][k] for g in members])
            agree = max(abs(F[g][k] - mean) for g in members) < 0.25 * abs(mean)
            est, wts = [], []
            for p in pairs:
                turn = np.exp(-1j * k * ang[p])
                w = abs(1.0 - turn) ** 2
                if w > 0.2:                               # a pair clamped a whole lobe apart says nothing here
                    est.append((F[p[0]][k] - F[p[1]][k] * turn) / (1.0 - turn))
                    wts.append(w)
            bar = np.average(est, weights=wts) if est else 0.0
            if orders is None:
                is_machine = (agree and 2.0 * abs(mean) > 0.5) or (
                    len(est) >= 2 and 2.0 * abs(bar) > 0.5 and max(abs(e - bar) for e in est) < 0.35 * abs(bar))
            else:
                is_machine = k in orders
            if tell is not None and sweep == 3 and (is_machine or 2.0 * abs(mean) > 1.0):
                tell.append((k, 2.0 * abs(mean), agree, [2.0 * abs(e) for e in est], is_machine))
            if is_machine:
                now.add(k)
                m[k] = mean if agree else bar
        found = now
    return m, sorted(found)


def spindle_orders(filt="band"):
    """The machine's orders, from whichever campaign has the pairs to establish them."""
    best = max(tester_groups(), key=lambda g: len(_twins(tester_groups()[g])))
    return twin_model(best, filt)[1]


def spindle_of(group, filt="band", how="twins"):
    """The error motion of the tester in one of its states, as a profile to take off its records.

      twins        the sound route: twin_model above
      lines        only the orders at which a campaign's records agree, which is the line no part shares
      epoch        the campaign's mean vector at the machine's orders, as if no part had anything there
      mean         the campaign's whole average profile
      significant  with group None: one error for the whole inspection, the orders whose pooled mean stands
                   three standard errors clear of the scatter, which is what a solver gets who does not notice
                   the maintenance
    """
    key = (group, filt, how)
    if key in _spin:
        return _spin[key]
    members = tester_groups()[group] if group else [g for g in ORDER if g not in SPARSE]
    F = np.array([_spectrum(g, filt)[0] for g in members])
    n = _spectrum(members[0], filt)[1]
    th = np.arange(n) / n * 2.0 * np.pi

    def profile(coef):
        out = np.zeros(n)
        for k in np.nonzero(coef)[0]:
            out += 2.0 * (coef[k].real * np.cos(k * th) - coef[k].imag * np.sin(k * th))
        return out

    coef = np.zeros(F.shape[1], dtype=complex)
    if how == "twins":
        coef = twin_model(group, filt, orders=spindle_orders(filt))[0]
    elif how == "mean":
        coef[2:51] = F[:, 2:51].mean(axis=0)
    elif how == "epoch":
        for k in spindle_orders(filt):
            coef[k] = F[:, k].mean()
    elif how == "lines":
        for k in range(2, 51):
            mean = F[:, k].mean()
            if 2.0 * abs(mean) > 0.5 and max(abs(F[:, k] - mean)) < 0.25 * abs(mean):
                coef[k] = mean
    else:
        for k in range(2, 51):
            mean = F[:, k].mean()
            se = (F[:, k].real.std(ddof=1) + 1j * F[:, k].imag.std(ddof=1)) / np.sqrt(max(len(members), 2))
            if abs(mean.real) > 3.0 * se.real and abs(mean.imag) > 3.0 * se.imag:
                coef[k] = mean
    _spin[key] = profile(coef)
    return _spin[key]


def _strike(p, orders):
    """A profile with the given orders removed outright, machine and part alike."""
    Fp = np.fft.rfft(p)
    for k in orders:
        Fp[k] = 0.0
    return np.fft.irfft(Fp, len(p))


DETAIL = {}


def assess(f, shape_src, size_src, route):
    """One feature's form error and sentence. shape_src and size_src are (feature, scan index or None)."""
    key = (f, shape_src, size_src, tuple(sorted(route.items())))
    if key in _cache:
        return _cache[key]
    how = route.get("how", "mz")
    filt = route.get("filt", "band")
    kind = route.get("kindover") or DRAW[f]["form_characteristic"]
    size = route.get("size", "mating")
    tcorr = route.get("tcorr", True)
    mat = route.get("mat", "cyl")
    nom = float(REG[f]["nominal_mm"])
    is_bore = REG[f]["kind"] == "bore"
    spin = route.get("spindle", "remove")
    ssecs, sT = _source(shape_src)
    _, profs, ths = section_data(ssecs, sT, tcorr=tcorr, filt=filt)
    zsecs, zT = _source(size_src)
    means, mprofs, mths = section_data(zsecs, zT, tcorr=tcorr, filt=filt)
    if spin != "keep":                         # only the tester's records carry it; a scan is from the room
        # `est`, not `how`: that name is the reference figure's, and sharing it once switched a route off unseen
        est = {"remove": "twins", "pooled": "significant"}.get(spin, spin)
        grp = None if spin == "pooled" else group_of(shape_src[0] if shape_src[1] is None else f)
        e = spindle_of(grp, filt, est)
        if spin == "delete":                   # the machine's orders struck out of the record altogether
            e = None
        if e is None:
            strike = lambda p: _strike(p, spindle_orders(filt))
        else:
            strike = lambda p: p - e
        if shape_src[1] is None and shape_src[0] not in SPARSE:
            profs = [strike(p) for p in profs]
        if size_src[1] is None and size_src[0] not in SPARSE:
            mprofs = [strike(p) for p in mprofs]
    n = len(profs)
    zs = [(j - (n - 1) / 2.0) for j in range(n)]
    bar = float(np.mean(means))
    whole = [(means[j] - bar) * 1000.0 + profs[j] for j in range(n)]
    if how == "ls":
        form = max(float(p.max() - p.min()) for p in profs) if kind != "cylindricity" else \
            float(np.concatenate(whole).max() - np.concatenate(whole).min())
    elif kind == "cylindricity":
        form = S.cylindricity(ths, whole, zs)
    else:
        form = max(S.roundness(t, p) for t, p in zip(ths, profs))
    off = (bar - nom / 2.0) * 1000.0
    if size != "mating":
        mating = 2.0 * off
    elif mat == "cyl":
        mating = 2.0 * (off + S.mating_cyl(REG[f]["kind"], ths, whole, zs))
    else:
        per = [S.mating_dev(REG[f]["kind"], ths[j], whole[j]) for j in range(n)]
        mating = 2.0 * (off + (min(per) if is_bore else max(per)))
    locs = np.concatenate([2.0 * (means[j] - nom / 2.0) * 1000.0 + S.local_sizes(mths[j], mprofs[j])
                           for j in range(len(mprofs))])
    lo, hi = float(DRAW[f]["size_lower_um"]), float(DRAW[f]["size_upper_um"])
    two_point = route.get("local", True)      # False: the mating size alone, Taylor's second requirement skipped
    if is_bore:
        size_ok = mating >= lo and (float(locs.max()) <= hi or not two_point)
    else:
        size_ok = mating <= hi and (float(locs.min()) >= lo or not two_point)
    form_ok = form <= float(DRAW[f]["form_tolerance_um"])
    v = {(True, True): "accept", (False, True): "reject_size",
         (True, False): "reject_form", (False, False): "reject_both"}[(size_ok, form_ok)]
    DETAIL[key] = dict(form=float(form), mating=float(mating), tol=float(DRAW[f]["form_tolerance_um"]),
                       lo=lo, hi=hi, locmax=float(locs.max()), locmin=float(locs.min()), bore=is_bore)
    _cache[key] = (float(form), v)
    return _cache[key]


def sentence(plan=(), transfer=True, **route):
    """plan: the features a scan is ordered for, in the order ordered."""
    idx = {f: k for k, f in enumerate(plan, 1)}
    out = {}
    for f in ORDER:
        if f in idx:
            shape = size = (f, idx[f])
        else:
            shape = size = (f, None)
            if transfer and f in NEED:
                sib = [g for g in plan if SETUP_OF.get(g) == SETUP_OF.get(f) and g != f]
                if sib:
                    shape = (sib[0], idx[sib[0]])
        out[f] = assess(f, shape, size, route)
    return out


TRUTH = {f: S.truth(f) for f in ORDER}


def sheet_of(ans, path):
    """Write a sentencing sheet the way the task asks for it: the header, then 14 rows to two decimals."""
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["feature", "form_um", "verdict"])
        for f in ORDER:
            w.writerow([f, "%.2f" % ans[f][0], ans[f][1]])
    return path


def score(ans):
    """The verifier's own result for a sheet of answers, read back from a written sheet."""
    with tempfile.TemporaryDirectory() as d:
        return GRADER.score(sheet_of(ans, os.path.join(d, "form.csv")))


def grade(ans):
    """worst form error, where, the features sentenced wrong, and the per-feature detail, from the verifier."""
    r = score(ans)
    if "error" in r:
        raise AssertionError("the verifier would not read the sheet: %s" % r["error"])
    worst, where, wrong, det = 0.0, "", [], {}
    for f in ORDER:
        v = r["features"][f]
        det[f] = (v["form_error_um"], v["verdict"], v["ok"])
        if abs(v["form_error_um"]) > worst:
            worst, where = abs(v["form_error_um"]), f
        if not v["ok"]:
            wrong.append(f)
    assert r["accepted"] == (not wrong), r
    return worst, where, wrong, det


def plan_reference():
    """The booking the records call for: the features no record can carry, grouped by boring setup."""
    groups = {}
    for f in NEED:
        groups.setdefault(SETUP_OF.get(f, f), []).append(f)
    return [g[0] for g in groups.values()]
