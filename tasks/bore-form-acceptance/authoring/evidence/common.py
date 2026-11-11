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


def spindle_estimate(filt="band", how="significant"):
    """The component every record of the shop's form tester carries at the same phase. A part's lobing sits at
    whatever phase it was clamped at, so averaging the tester's records leaves the machine's error motion and
    averages the parts down. Nothing in the documents gives this; only the records of several parts together.

    how="significant" keeps only the orders whose mean stands clear of the scatter between parts (3 standard
    errors), which is the orders the machine actually contributes; how="mean" subtracts the whole average, and so
    takes a share of every part's own lobing off every other part."""
    return spindle_of(None, filt, how)


def spindle_of(group, filt="band", how="significant"):
    """The error motion of the tester in one of its states. group=None pools every record, which is what a solver
    gets who does not notice the maintenance."""
    key = (group, filt, how)
    if key in _spin:
        return _spin[key]
    members = tester_groups()[group] if group else [g for g in ORDER if g not in SPARSE]
    per = []
    for g in members:
        secs, T = shop_record(g)
        _, p, _ = section_data(secs, T, filt=filt)
        per.append(np.mean(np.array(p), axis=0))       # one mounting per record, so its sections share a phase
    A = np.array(per)
    th = np.arange(A.shape[1]) / A.shape[1] * 2.0 * np.pi
    if how == "mean":
        _spin[key] = A.mean(axis=0)
        return _spin[key]
    F = np.fft.rfft(A, axis=1) / A.shape[1]
    out = np.zeros(A.shape[1])
    for k in range(2, min(F.shape[1], 120)):
        m = F[:, k].mean()
        se = (F[:, k].real.std(ddof=1) + 1j * F[:, k].imag.std(ddof=1)) / np.sqrt(max(len(per), 2))
        if abs(m.real) > 3.0 * se.real and abs(m.imag) > 3.0 * se.imag:
            out += 2.0 * (m.real * np.cos(k * th) - m.imag * np.sin(k * th))
    _spin[key] = out
    return _spin[key]


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
    if spin in ("remove", "mean", "pooled"):   # only the tester's records carry it; a scan is from the room
        how = "mean" if spin == "mean" else "significant"
        grp = None if spin == "pooled" else group_of(shape_src[0] if shape_src[1] is None else f)
        e = spindle_of(grp, filt, how)
        if shape_src[1] is None and shape_src[0] not in SPARSE:
            profs = [p - e for p in profs]
        if size_src[1] is None and size_src[0] not in SPARSE:
            mprofs = [p - e for p in mprofs]
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
