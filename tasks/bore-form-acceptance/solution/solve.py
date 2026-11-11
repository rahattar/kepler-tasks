"""Reference solution: sentences the fourteen features of the press overhaul on form and size to FM-7.

    python3 solve.py [DATA_DIR] [SCAN_DIR] [OUT_CSV]

It reads only /app/data and the scans it orders through `formscan`. The sealed definition is never read.

1. **What a record can carry.** FM-7 assesses the band 2 to 50 undulations a revolution, so a record needs more
   than 100 points a revolution to resolve it: the coordinate machine's 12 touch points cannot, whatever the
   feature's profile happens to be, and what they give is an aliased fraction of its form. A record also stops
   describing a feature when the machining log shows work on that feature after the day it was measured (the
   re-honed bore). Both kinds of feature need a scan.
2. **One scan can serve two features.** The machining log records which features were bored in one setup without
   unclamping. The lobing a setup leaves is the setup's, so a scanned feature gives the form error and the mating
   deviation of the other feature of its setup; those two numbers do not depend on where the angular origin sits.
   Its size is its own, and its own record carries that: twelve points average a mean radius well, and the taper
   from section to section is the part's own. So the features needing a scan are grouped by setup and one scan is
   ordered per group, which brings four needs inside the booking of four.
3. **The assessment.** For each section: the mean radius, referred to 20 C with 11.7 um/m K from the room
   temperature of that record, and the deviations with order 0 and order 1 dropped and order n scaled by
   exp(-pi (0.4697 n / 50)^2). Then, by minimum zone (a linear program, the deviations being microns on a radius
   of hundreds of millimetres):
   - roundness: the smallest radial separation of two concentric circles per section, worst section;
   - cylindricity: two coaxial cylinders over all three sections, axis free in position and tilt, the sections'
     mean radii carried in so that taper counts;
   - mating size: the largest inscribed (bore) or smallest circumscribed (journal) cylinder over all sections;
   - local sizes: diametrically opposite pairs, section by section.
4. **The sentence.** A bore accepts on size when its mating size is at or above the lower limit and its worst
   local size at or below the upper; a journal the other way about. Form accepts within tolerance. The two give
   accept, reject_size, reject_form or reject_both.
"""
import csv
import os
import subprocess
import sys

import numpy as np
from scipy.optimize import linprog

GAUSS, UPR, ALPHA, T_REF = 0.4697, 50, 11.7, 20.0
ROOM = 20.4                    # the metrology room's temperature, from docs/metrology_room.md
MIN_PTS = 2 * UPR + 1          # to resolve the assessment band at all
DATA = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
SCANS = sys.argv[2] if len(sys.argv) > 2 else "/app/scan_reports"
OUT = sys.argv[3] if len(sys.argv) > 3 else "/app/output/form.csv"


def rows(name):
    with open(os.path.join(DATA, name)) as f:
        return list(csv.DictReader(f))


def sections(path):
    """(angles rad, radii mm) for each section of a points file, in order along the feature."""
    secs = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            secs.setdefault(float(r["section_mm"]), []).append((float(r["angle_deg"]), float(r["radius_mm"])))
    out = []
    for z in sorted(secs):
        a = np.array(sorted(secs[z]))
        out.append((np.radians(a[:, 0]), a[:, 1]))
    return out


def profile(th, dev):
    """FM-7's assessment profile: order 0 and 1 out, Gaussian 50 UPR taper on the rest."""
    n = len(dev)
    F = np.fft.rfft(dev) / n
    out = np.zeros(n)
    for k in range(2, len(F)):
        g = float(np.exp(-np.pi * (GAUSS * k / UPR) ** 2))
        if g < 1e-6:
            break
        out += 2.0 * g * (F[k].real * np.cos(k * th) - F[k].imag * np.sin(k * th))
    return out


def minimax(cols, dev, what):
    m = np.column_stack(cols)
    k = m.shape[1]
    if what == "zone":
        A = np.vstack([np.c_[-m, -np.ones(len(dev)), np.zeros(len(dev))],
                       np.c_[m, np.ones(len(dev)), -np.ones(len(dev))]])
        r = linprog(c=np.r_[np.zeros(k + 1), 1.0], A_ub=A, b_ub=np.r_[-dev, dev],
                    bounds=[(-400, 400)] * (k + 1) + [(0, None)])
        return float(r.x[-1])
    if what == "inscribed":
        r = linprog(c=np.r_[np.zeros(k), -1.0], A_ub=np.c_[m, np.ones(len(dev))], b_ub=dev,
                    bounds=[(-400, 400)] * (k + 1))
        return float(r.x[-1])
    r = linprog(c=np.r_[np.zeros(k), 1.0], A_ub=np.c_[-m, -np.ones(len(dev))], b_ub=-dev,
                bounds=[(-400, 400)] * (k + 1))
    return float(r.x[-1])


def spindle_error(index, reg):
    """What every record of the shop's form tester carries at the same phase. A record's angle is the spindle's
    angle and a part is clamped wherever it comes to rest, so a component that repeats in amplitude AND phase
    across parts bored in different setups on different machines belongs to the measuring machine. It is in no
    document. Averaging the tester's records leaves it and averages the parts' own lobing down; the orders kept
    are those whose mean stands three standard errors clear of the scatter between parts, so that nothing of any
    one part's lobing is taken off the others."""
    per = []
    for f, r in index.items():
        if int(r["points_per_rev"]) < MIN_PTS or "form tester" not in r["instrument"]:
            continue
        secs = sections(os.path.join(DATA, r["file"].split("data/", 1)[1]))
        _, profs, _ = shape(secs, float(r["room_c"]))
        per.append(np.mean(np.array(profs), axis=0))
    A = np.array(per)
    n = A.shape[1]
    th = np.arange(n) / n * 2.0 * np.pi
    F = np.fft.rfft(A, axis=1) / n
    out = np.zeros(n)
    kept = []
    for k in range(2, min(F.shape[1], 120)):
        m = F[:, k].mean()
        sr = F[:, k].real.std(ddof=1) / np.sqrt(len(per))
        si = F[:, k].imag.std(ddof=1) / np.sqrt(len(per))
        if abs(m.real) > 3.0 * sr and abs(m.imag) > 3.0 * si:
            out += 2.0 * (m.real * np.cos(k * th) - m.imag * np.sin(k * th))
            kept.append(k)
    print("# the form tester's own error motion, from %d of its records: orders %s, %.2f um peak to valley"
          % (len(per), ",".join(str(k) for k in kept), out.max() - out.min()))
    return out


def shape(secs, T):
    """Mean radius at 20 C (mm) per section, and the assessment profile (um) per section."""
    means, profs, ths = [], [], []
    for th, r in secs:
        means.append(float(np.mean(r)) / (1.0 + ALPHA * 1e-6 * (T - T_REF)))
        profs.append(profile(th, (r - np.mean(r)) * 1000.0))
        ths.append(th)
    return means, profs, ths


def main():
    reg = {r["feature"]: r for r in rows("feature_register.csv")}
    draw = {r["feature"]: r for r in rows("drawing_requirements.csv")}
    index = {r["feature"]: r for r in rows("measurement_index.csv")}
    log = rows("machining_log.csv")
    setup_of, budget = {}, 0
    for r in log:
        for f in r["features_in_this_setup"].split():
            if f in index and r["setup"] != "-":
                setup_of[f] = r["setup"]
        if "booking of" in r["note"]:
            budget = int(r["note"].rsplit("booking of", 1)[1])

    # a record that cannot carry the feature's form: too few points for the band, or overtaken by later work
    need = []
    for f in index:
        pts = int(index[f]["points_per_rev"])
        later = [r for r in log if f in r["features_in_this_setup"].split() and r["setup"] == "-"
                 and r["date"] > index[f]["measured_on"] and "booking" not in r["note"]]
        if pts < MIN_PTS or later:
            need.append(f)
    groups = {}
    for f in need:
        groups.setdefault(setup_of.get(f, f), []).append(f)
    plan = [g[0] for g in groups.values()]
    assert len(plan) <= budget, (plan, budget)
    spin = spindle_error(index, reg)
    print("# needs a scan: %s" % " ".join(need))
    print("# scans ordered (one per boring setup): %s" % " ".join(plan))
    for f in plan:
        subprocess.run(["formscan", f], check=True)

    scanned = {}
    for name in sorted(os.listdir(SCANS)):
        for f in index:
            if name.endswith("_%s.csv" % f.lower().replace("-", "")):
                scanned[f] = sections(os.path.join(SCANS, name))
    out = [("feature", "form_um", "verdict")]
    for f in index:
        own = sections(os.path.join(DATA, index[f]["file"].split("data/", 1)[1]))
        T = float(index[f]["room_c"])
        shop_tester = "form tester" in index[f]["instrument"]
        if f in scanned:
            own, T = scanned[f], ROOM
            shop_tester = False
        means, _, _ = shape(own, T)
        # the shape comes from this feature's own scan, or from the feature of its setup that was scanned
        src = f if f in scanned else (
            next((g for g in scanned if setup_of.get(g) == setup_of.get(f)), None) if f in need else None)
        if src is None:
            _, profs, ths = shape(own, T)
            if shop_tester:                      # the machine's error motion is not this feature's form
                profs = [p - spin for p in profs]
        else:
            _, profs, ths = shape(scanned[src], ROOM)
        nom = float(reg[f]["nominal_mm"])
        bar = float(np.mean(means))
        zs = [(j - (len(profs) - 1) / 2.0) / (len(profs) - 1) for j in range(len(profs))]
        whole = [(means[j] - bar) * 1000.0 + profs[j] for j in range(len(profs))]
        c = [np.cos(np.concatenate(ths)), np.sin(np.concatenate(ths))]
        z = np.concatenate([np.full(len(t), zz) for t, zz in zip(ths, zs)])
        cols4 = c + [z * c[0], z * c[1]]
        if draw[f]["form_characteristic"] == "cylindricity":
            form = minimax(cols4, np.concatenate(whole), "zone")
        else:
            form = max(minimax([np.cos(t), np.sin(t)], p, "zone") for t, p in zip(ths, profs))
        kind = reg[f]["kind"]
        mat = minimax(cols4, np.concatenate(whole), "inscribed" if kind == "bore" else "circumscribed")
        mating = 2.0 * ((bar - nom / 2.0) * 1000.0 + mat)
        locs = []
        for j, (t, p) in enumerate(zip(ths, profs)):
            half = len(p) // 2
            pair = p[:half] + p[half:2 * half]
            locs.append(2.0 * (means[j] - nom / 2.0) * 1000.0 + pair)
        locs = np.concatenate(locs)
        lo, hi = float(draw[f]["size_lower_um"]), float(draw[f]["size_upper_um"])
        if kind == "bore":
            size_ok = mating >= lo and float(locs.max()) <= hi
        else:
            size_ok = mating <= hi and float(locs.min()) >= lo
        form_ok = form <= float(draw[f]["form_tolerance_um"])
        verdict = {(True, True): "accept", (False, True): "reject_size",
                   (True, False): "reject_form", (False, False): "reject_both"}[(size_ok, form_ok)]
        out.append((f, "%.2f" % form, verdict))
        print("# %-6s form %6.2f um  mating %+7.1f  worst local %+7.1f  -> %s"
              % (f, form, mating, locs.max() if kind == "bore" else locs.min(), verdict))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        csv.writer(fh).writerows(out)
    print("# written %s" % OUT)


if __name__ == "__main__":
    main()
