"""A second solution, written separately from solution/solve.py and from common.py: pandas for the records, a
Nelder-Mead minimax instead of a linear program, the machine's error motion taken as the median across the
tester's records with every order above 1 um kept, cylindricity parameterised by the two end radii rather than by
position and tilt, and the other feature of each pair scanned. It is graded against the sealed definition only at
the end.

    python3 independent.py > independent.txt
"""
import csv
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "provenance"))
import isim as SEALED  # noqa: E402  (grading only)

DATA = os.path.join(HERE, "..", "..", "environment", "data")
PLAN = ["RJ-44", "CB-25", "RJ-43", "RJ-45"]       # RJ-44 shares its setup with the re-honed bore
G = 0.4697


def load(path):
    d = pd.read_csv(path)
    return [(np.radians(g["angle_deg"].to_numpy()), g["radius_mm"].to_numpy())
            for _, g in d.groupby("section_mm", sort=True)]


def prof(th, r):
    dev = (r - r.mean()) * 1000.0
    n = len(dev)
    F = np.fft.rfft(dev) / n
    k = np.arange(len(F))
    w = np.exp(-np.pi * (G * k / 50.0) ** 2)
    w[0] = w[1] = 0.0
    F = F * w
    out = np.zeros(n)
    for i in range(2, len(F)):
        if w[i] < 1e-6:
            break
        out += 2.0 * (F[i].real * np.cos(i * th) - F[i].imag * np.sin(i * th))
    return out


def zone_circle(th, p):
    f = lambda c: float(np.ptp(p - c[0] * np.cos(th) - c[1] * np.sin(th)))
    return float(minimize(f, [0.0, 0.0], method="Nelder-Mead",
                          options=dict(xatol=1e-4, fatol=1e-4, maxiter=4000)).fun)


def _cols(ths, u):
    """The axis is given by its offset at the two ends of the feature, so a section at u takes (1-u) of one end
    and u of the other. A minimum zone in these four unknowns is a smooth constrained problem, so SLSQP solves it
    exactly where a simplex search on the non-smooth maximum stalls."""
    th = np.concatenate(ths)
    uu = np.concatenate([np.full(len(t), v) for t, v in zip(ths, u)])
    c, s = np.cos(th), np.sin(th)
    return np.column_stack([(1 - uu) * c, (1 - uu) * s, uu * c, uu * s])


def zone_cyl(ths, ps, u):
    A, d = _cols(ths, u), np.concatenate(ps)
    x0 = np.r_[np.zeros(4), d.max(), d.min()]            # unknowns: axis (4), then the two radii of the zone
    cons = [dict(type="ineq", fun=lambda x: x[4] - (d - A @ x[:4])),
            dict(type="ineq", fun=lambda x: (d - A @ x[:4]) - x[5])]
    r = minimize(lambda x: x[4] - x[5], x0, method="SLSQP", constraints=cons,
                 options=dict(maxiter=400, ftol=1e-9))
    return float(r.x[4] - r.x[5])


def gauge(ths, ps, u, bore):
    A, d = _cols(ths, u), np.concatenate(ps)
    if bore:
        cons = [dict(type="ineq", fun=lambda x: (d - A @ x[:4]) - x[4])]
        r = minimize(lambda x: -x[4], np.r_[np.zeros(4), d.min()], method="SLSQP", constraints=cons,
                     options=dict(maxiter=400, ftol=1e-9))
    else:
        cons = [dict(type="ineq", fun=lambda x: x[4] - (d - A @ x[:4]))]
        r = minimize(lambda x: x[4], np.r_[np.zeros(4), d.max()], method="SLSQP", constraints=cons,
                     options=dict(maxiter=400, ftol=1e-9))
    return float(r.x[4])


def main():
    reg = pd.read_csv(os.path.join(DATA, "feature_register.csv")).set_index("feature")
    draw = pd.read_csv(os.path.join(DATA, "drawing_requirements.csv")).set_index("feature")
    idx = pd.read_csv(os.path.join(DATA, "measurement_index.csv")).set_index("feature")
    log = pd.read_csv(os.path.join(DATA, "machining_log.csv"))
    setup = {}
    for _, r in log.iterrows():
        if r["setup"] != "-":
            for f in str(r["features_in_this_setup"]).split():
                setup[f] = r["setup"]
    feats = list(idx.index)
    recs = {f: load(os.path.join(DATA, "measurements", os.path.basename(idx.loc[f, "file"]))) for f in feats}
    dense = [f for f in feats if idx.loc[f, "points_per_rev"] >= 101]
    tester = [f for f in dense if "form tester" in idx.loc[f, "instrument"]]

    # The machine's error motion, found by a different test from the reference's: an order belongs to the machine
    # when its phase is the same in every record (the parts are clamped at unrelated angles, so their own lobing
    # scatters in phase). The mean resultant length of the phases is 1 for a machine order and about 1/sqrt(N) for
    # a part order. The amplitude is then the median across the records, which ignores an odd part.
    # The test runs on each side of the day the log has the tester's spindle re-greased: a bearing that has been
    # re-greased and re-preloaded does not run as it ran before, so the records before and after that day are two
    # machines, and one estimate over all of them describes neither. Pooled, the phases disagree and the test
    # keeps nothing at all, which is the symptom of having mixed two states rather than of a clean machine.
    service = [r["date"] for _, r in log.iterrows() if r["setup"] == "-"
               and "greas" in (str(r["operation"]) + str(r["note"])).lower()]
    cut = max(service) if service else None
    sides = {}
    for f in tester:
        sides.setdefault("after" if cut and idx.loc[f, "measured_on"] > cut else "before", []).append(f)
    err = {}
    for side in sorted(sides):
        stack = np.array([np.mean([prof(t, r) for t, r in recs[f]], axis=0) for f in sides[side]])
        n = stack.shape[1]
        th0 = np.arange(n) / n * 2.0 * np.pi
        F = np.fft.rfft(stack, axis=1) / n
        e = np.zeros(n)
        kept = []
        for k in range(2, 120):
            col = F[:, k]
            if np.median(2 * np.abs(col)) < 0.5:
                continue
            unit = col / np.abs(col)
            a = np.abs(col)
            # the machine writes the same amplitude as well as the same phase into every record it touches, so an
            # order is the machine's only if both agree; phase alone lets a part order through when the side of
            # the service date being tested holds only a few records
            if abs(unit.mean()) > 0.9 and float(a.max() / a.min()) < 1.5:
                ph = np.angle(unit.mean())
                amp = float(np.median(np.abs(col)))
                e += 2.0 * amp * np.cos(k * th0 + ph)
                kept.append(k)
        err[side] = e
        print("# machine error motion by phase agreement, %s %s: orders %s, %.2f um peak to valley"
              % (side, cut, kept, float(np.ptp(e))))

    scans = {}
    for k, f in enumerate(PLAN, 1):
        scans[f] = [(t, r) for t, r in SEALED.scan(f, k, SEALED.SEED_SCAN)]
    stale = [f for f in feats if any(f in str(r["features_in_this_setup"]).split() and r["setup"] == "-"
                                     and r["date"] > idx.loc[f, "measured_on"] and "booking" not in str(r["note"])
                                     for _, r in log.iterrows())]
    need = [f for f in feats if f not in dense or f in stale]

    out, wrong = {}, []
    for f in feats:
        src, T = f, float(idx.loc[f, "measured_on"] and idx.loc[f, "room_c"])
        sub = ("after" if cut and idx.loc[f, "measured_on"] > cut else "before") if f in tester else None
        secs = recs[f]
        if f in scans:
            secs, T, sub = scans[f], SEALED.T_ROOM, None
        elif f in need:
            sib = [g for g in PLAN if setup.get(g) == setup.get(f) and g != f]
            if sib:
                secs, T, sub = scans[sib[0]], SEALED.T_ROOM, None
        ps = [prof(t, r) - (err[sub] if sub else 0.0) for t, r in secs]
        ths = [t for t, _ in secs]
        own = recs[f] if f not in scans else scans[f]
        means = [float(r.mean()) / (1 + 11.7e-6 * (float(idx.loc[f, "room_c"]) - 20.0)) if f not in scans
                 else float(r.mean()) / (1 + 11.7e-6 * (SEALED.T_ROOM - 20.0)) for _, r in own]
        nom = float(reg.loc[f, "nominal_mm"])
        bar = float(np.mean(means))
        u = np.linspace(0.0, 1.0, len(ps))
        whole = [(means[j] - bar) * 1000.0 + ps[j] for j in range(len(ps))]
        if draw.loc[f, "form_characteristic"] == "cylindricity":
            form = zone_cyl(ths, whole, u)
        else:
            form = max(zone_circle(t, p) for t, p in zip(ths, ps))
        bore = reg.loc[f, "kind"] == "bore"
        mating = 2.0 * ((bar - nom / 2.0) * 1000.0 + gauge(ths, whole, u, bore))
        loc = []
        for j, (t, p) in enumerate(zip(ths, ps)):
            h = len(p) // 2
            loc.append(2.0 * (means[j] - nom / 2.0) * 1000.0 + p[:h] + p[h:2 * h])
        loc = np.concatenate(loc)
        lo, hi = float(draw.loc[f, "size_lower_um"]), float(draw.loc[f, "size_upper_um"])
        size_ok = (mating >= lo and loc.max() <= hi) if bore else (mating <= hi and loc.min() >= lo)
        form_ok = form <= float(draw.loc[f, "form_tolerance_um"])
        v = {(True, True): "accept", (False, True): "reject_size",
             (True, False): "reject_form", (False, False): "reject_both"}[(size_ok, form_ok)]
        out[f] = (form, v)
    print("# scans ordered: %s" % " ".join(PLAN))

    # The sheet goes to the verifier, as a sheet, and the verifier decides: this script holds no opinion about
    # what counts as right. tests/grade_form.py is run as its own process, so it reads its own sealed copy.
    d = tempfile.mkdtemp()
    sheet = os.path.join(d, "form.csv")
    with open(sheet, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["feature", "form_um", "verdict"])
        for f in feats:
            w.writerow([f, "%.2f" % out[f][0], out[f][1]])
    grader = os.path.join(HERE, "..", "..", "tests", "grade_form.py")
    r = subprocess.run([sys.executable, "-B", grader, sheet], capture_output=True, text=True)
    print(r.stdout.rstrip())
    if r.returncode or "rejected" in r.stdout.splitlines()[-1]:
        print("# the verifier did not accept this sheet")
    return out


if __name__ == "__main__":
    main()
