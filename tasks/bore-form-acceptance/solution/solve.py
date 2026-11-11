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
3. **The instrument.** The shop's form tester adds an error motion of its own to every record it takes, at
   the spindle's angle, and it is in no document. It is estimated from the tester's records and taken off them
   before anything is assessed: separately on each side of the day the log has the spindle re-greased, the line
   no part shares from the records' mean, and the line the setups' lobing shares from the setup pairs. See
   spindle_error. A scan from the metrology room carries none of it.
4. **The assessment.** For each section: the mean radius, referred to 20 C with 11.7 um/m K from the room
   temperature of that record, and the deviations with order 0 and order 1 dropped and order n scaled by
   exp(-pi (0.4697 n / 50)^2). Then, by minimum zone (a linear program, the deviations being microns on a radius
   of hundreds of millimetres):
   - roundness: the smallest radial separation of two concentric circles per section, worst section;
   - cylindricity: two coaxial cylinders over all three sections, axis free in position and tilt, the sections'
     mean radii carried in so that taper counts;
   - mating size: the largest inscribed (bore) or smallest circumscribed (journal) cylinder over all sections;
   - local sizes: diametrically opposite pairs, section by section.
5. **The sentence.** A bore accepts on size when its mating size is at or above the lower limit and its worst
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


def spindle_error(index, log, setup_of):
    """The error motion of the shop's form tester, which is in no document: only its records, taken together,
    show it. A record's angle is the spindle's angle and a part is clamped wherever it comes to rest, so what the
    machine adds sits at the same phase in every record and what a part carries sits wherever that part sat.

    Two states. The log has the spindle bearings re-greased and the preload reset part way through the
    inspection, so the records before that day and after it are two machines and are treated apart. Pooled, the
    two disagree in phase and nothing stands clear of the scatter.

    Two kinds of line. At an order no part has anything at, every record of a campaign agrees in amplitude and
    phase, and the campaign's mean is the machine. At an order the boring setups left lobing at, a record is the
    machine's vector plus the part's, the records do not agree, and their mean is the machine plus whatever the
    parts happen to add up to. The process note separates the two: features finished in one setup carry the same
    lobing, at whatever angle each was clamped. The angle between the two records of such a pair is fixed by the
    orders at which they agree in amplitude (turning a part changes phase, not amplitude). With that angle d, the
    pair is two equations at order k,  Fa = m + c  and  Fb = m + c exp(ik d),  so
    m = (Fa - Fb exp(-ik d)) / (1 - exp(-ik d)).  An order is the machine's when the pairs of a campaign agree on
    m. The campaign after the maintenance has one pair, which cannot vouch for itself, so it is solved at the
    orders the earlier campaign established: the orders are the bearing's geometry, which grease does not change.

    The honed bore's shop record belongs with its setup here. It was taken before the hone, when the bore still
    carried the setup's lobing, and it is the tester that is being characterised, not the bore."""
    day = next((r["date"] for r in log if "form tester" in r["machine"] and "spindle" in r["operation"]), None)
    spec, camp = {}, {}
    for f, r in index.items():
        if int(r["points_per_rev"]) < MIN_PTS or "form tester" not in r["instrument"]:
            continue
        secs = sections(os.path.join(DATA, r["file"].split("data/", 1)[1]))
        _, profs, _ = shape(secs, float(r["room_c"]))
        mean = np.mean(np.array(profs), axis=0)           # one clamping serves a record's three sections
        spec[f] = np.fft.rfft(mean) / len(mean)
        camp.setdefault("after" if (day and r["measured_on"] > day) else "before", []).append(f)
    n = 2 * (len(next(iter(spec.values()))) - 1)
    th = np.arange(n) / n * 2.0 * np.pi
    band = range(2, UPR + 1)

    def pairs(members):
        by = {}
        for f in members:
            by.setdefault(setup_of[f], []).append(f)
        return [v for v in by.values() if len(v) == 2]

    def angle(A, B):
        ks = np.array([k for k in band if 2.0 * max(abs(A[k]), abs(B[k])) > 0.3
                       and abs(abs(A[k]) - abs(B[k])) < 0.12 * max(abs(A[k]), abs(B[k]))])
        cross = A[ks] * np.conj(B[ks])
        d, step = 0.0, 2.0 * np.pi / 7200
        grid = np.arange(7200) * step
        for _ in range(4):                                # a coarse sweep of the turn, then three refinements
            d = grid[int(np.argmax((cross[None, :] * np.exp(1j * np.outer(grid, ks))).real.sum(axis=1)))]
            step /= 10.0
            grid = d + np.arange(-10, 11) * step
        return float(d)

    def solve(members, orders=None):
        m = np.zeros(n // 2 + 1, dtype=complex)
        agreed = {}
        for k in band:                                    # the lines the records agree on come out first
            mean = np.mean([spec[f][k] for f in members])
            if 2.0 * abs(mean) > 0.5 and max(abs(spec[f][k] - mean) for f in members) < 0.25 * abs(mean):
                agreed[k] = mean
                m[k] = mean
        turn = {tuple(p): angle(spec[p[0]] - m, spec[p[1]] - m) for p in pairs(members)}
        found = dict(agreed)
        for k in band:
            if k in agreed:
                continue
            est, wts = [], []
            for (a, b), d in turn.items():
                e = np.exp(-1j * k * d)
                if abs(1.0 - e) ** 2 > 0.2:               # a pair a whole lobe apart says nothing at this order
                    est.append((spec[a][k] - spec[b][k] * e) / (1.0 - e))
                    wts.append(abs(1.0 - e) ** 2)
            if not est:
                continue
            bar = np.average(est, weights=wts)
            vouched = len(est) >= 2 and 2.0 * abs(bar) > 0.5 and max(abs(e - bar) for e in est) < 0.35 * abs(bar)
            if (orders is None and vouched) or (orders is not None and k in orders):
                found[k] = bar
        return found

    lead = max(camp, key=lambda c: len(pairs(camp[c])))   # the campaign with the pairs to establish the orders
    orders = sorted(solve(camp[lead]))
    out = {}
    for key, members in camp.items():
        found = solve(members, orders)
        e = np.zeros(n)
        for k in orders:
            if k in found:
                e += 2.0 * (found[k].real * np.cos(k * th) - found[k].imag * np.sin(k * th))
        out[key] = e
        print("# the form tester %s %s: %d records, %d pair(s), error motion at orders %s (%s um), %.2f um peak "
              "to valley" % (key, day, len(members), len(pairs(members)), ",".join(str(k) for k in orders),
                             ", ".join("%.2f" % (2.0 * abs(found[k])) for k in orders if k in found),
                             e.max() - e.min()))
    return out, day


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
    spin, regrease = spindle_error(index, log, setup_of)
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
                key = "after" if (regrease and index[f]["measured_on"] > regrease) else "before"
                profs = [p - spin[key] for p in profs]
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
