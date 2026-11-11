"""Sealed definition: form and size acceptance of fourteen finish-machined features of a hydraulic press overhaul
(eight cylinder and gland bores, six ram journals). Lengths in mm, deviations in um, angles in rad, temperature in C.

A feature's surface is a closed radial profile at each of three axial sections: a sum of harmonics in part
coordinates (the lobing the boring setup leaves, plus the part's own small content), on a mean radius that varies
from section to section. What a record holds is that surface plus the setup eccentricity of the measurement (order
1, tens of um), sampled at the record's angular density, at the record's temperature.

The assessment profile of standard FM-7 is the measured deviations with order 1 removed and a Gaussian 50 UPR
low-pass applied. On it:
- form is the minimum-zone value: a roundness callout takes the worst section, a cylindricity callout one zone
  over all three sections, with the axis free in position and tilt;
- the mating size is the maximum inscribed circle of a bore and the minimum circumscribed circle of a journal;
- a local size is a diametrically opposite pair.
All sizes are referred to 20 C with the material's expansion coefficient. The drawing's envelope requirement makes
a bore acceptable in size when its mating size is at least the lower limit and no local size exceeds the upper;
for a journal, mating size at most the upper limit and no local size below the lower.

Two things the records cannot give:
- seven features were measured only on the coordinate machine at CMM_PTS points a revolution, which cannot assess
  a 50 UPR band at all (Nyquist); their setup lobing is above that, so what the sparse points give is not the form
  error but an aliased fraction of it;
- of those seven, six were bored in pairs in one setup (SETUP_OF), so the two of a pair carry the same setup
  lobing, and form and mating deviation, both independent of the angular origin, carry from one to the other. The
  seventh was bored alone.
The metrology room's booking is BUDGET dense scans, so the pairs have to be recognised.
"""
import numpy as np
from scipy.optimize import linprog

GAUSS = 0.4697          # ISO 16610-21 Gaussian filter constant, sqrt(ln 2 / pi)
UPR_CUTOFF = 50         # FM-7 assessment band: orders 2 to 50
ALPHA = 11.7            # um/m K, the steel of every part (FM-7 and the drawings)
T_REF = 20.0
SECTIONS = (0.25, 0.50, 0.75)   # fraction of the feature's length
TESTER_PTS = 1800       # roundness tester, and the metrology room's dense scan: 0.2 degree steps
CMM_PTS = 12            # touch points a revolution of the coordinate machine's bore program
BUDGET = 4              # dense scans the metrology room's booking allows
SEED_SCAN = 4409        # drives the scatter of a scan, nothing else
# The shop's form tester RT-1 has a worn spindle, and its error motion rides on every profile it measures, at the
# same phase in every record because a record's angle is the spindle's angle. A part's own lobing sits at whatever
# phase the part was clamped at, so the two separate: a component that is identical in phase across parts bored in
# different setups on different machines belongs to the measuring machine, not to the parts. Nothing in the
# records says so; only the records of several parts together show it. The metrology room's tester is certified
# and its error motion is below the noise.
# The error motion of the shop's form tester, order -> (amplitude um, phase rad in the machine's own reference).
# Its spindle bearings were re-greased and the preload reset on the evening of REGREASE (the maintenance log dates
# it), which left the machine with a different error motion. Records taken before that date carry the first,
# records after it the second. One estimate pooled over all of them belongs to neither.
SPINDLE_BEFORE = {23: (4.62, 0.95), 29: (3.87, 2.35)}
SPINDLE_AFTER = {23: (3.10, 2.40), 29: (2.45, 0.60)}
REGREASE = "2026-09-30"
# Two features came off the boring bar with an ovality of their own: a thin wall clamped once takes a form the
# setup's lobing does not explain, and the part keeps it after release. That ovality is what decides those two
# features, and it decides them on a local size, not on the mating size. A plug gauge goes through an oval bore on
# its minor axis, so the bore's mating size clears the lower limit comfortably, while a pair of opposite points
# across the major axis is over the upper limit; an oval journal is the other way about, inside the ring gauge on
# its major axis and under the lower limit across its minor. That is Taylor's principle with both halves doing
# work, and it is why one size figure, however carefully it is found, cannot sentence a part.

# How large the setup's lobing came out on each part. The parts of one setup were clamped once and finished
# together, so within a setup it is the same.
AMP = {f: 1.00 for f in ("CB-21", "RJ-41", "CB-24", "CB-25", "CB-22", "RJ-44", "GB-31", "GB-32", "CB-23",
                         "RJ-46", "RJ-42", "RJ-43", "CB-26", "RJ-45")}

# Harmonic content a boring setup leaves: order -> (amplitude um, phase rad). The sparse setups (S2, S4, S6, S8)
# are above the 50 UPR band's Nyquist limit for CMM_PTS points.
# Which orders are even and which odd is not decoration. A two-point size adds the radii of opposite points, so
# every odd order cancels in it: an odd-lobed feature has a nearly constant two-point size however far out of
# round it is, and only its mating size can catch it. The two oval features are the other way about, and only a
# two-point size catches them. That is both halves of Taylor's principle earning their place, and it is why S6
# and S8 carry their amplitude at odd orders while the ovality of CB-26 and RJ-46 sits at order 2.
SETUP = {
    "S1": {2: (4.98, 0.35), 3: (6.63, 1.10), 6: (1.54, 2.40), 17: (0.95, 0.90)},
    "S2": {2: (1.44, 0.80), 7: (3.16, 0.95), 9: (2.81, 2.20), 11: (1.98, 0.40), 13: (1.65, 1.70)},
    "S3": {2: (4.24, 0.00), 3: (1.53, 0.60), 5: (2.37, 0.25), 9: (0.77, 1.30)},
    "S4": {3: (1.90, 1.45), 7: (4.14, 0.20), 9: (5.51, 1.05), 13: (3.29, 2.60), 15: (2.34, 0.75)},
    "S5": {2: (3.94, 1.20), 4: (5.75, 0.45), 7: (1.91, 2.05), 19: (1.08, 0.30)},
    "S6": {2: (2.07, 0.55), 9: (6.59, 1.60), 11: (4.40, 0.85), 13: (3.43, 2.30), 19: (1.83, 1.15)},
    "S7": {2: (7.71, 0.90), 3: (4.61, 2.15), 6: (3.56, 0.70), 11: (1.78, 1.80)},
    "S8": {2: (1.39, 0.10), 9: (6.56, 1.35), 12: (4.91, 2.45), 15: (3.14, 0.60)},
}

# id -> kind, nominal mm, size limits as deviations from nominal in um, tolerance kind and value in um, setup,
# where the record comes from, mean radius deviation per section in um, the part's own harmonics, taper
FEATURES = {
    "CB-21": dict(kind="bore", nom=320.0, lim=(0, 57), tol=("cylindricity", 27.5), setup="S1", src="tester",
                  mean=(13.0, 16.0, 14.0), own={23: (0.55, 1.42), 5: (1.1, 0.4), 17: (0.6, 1.9)}, tilt=(2.0, -1.0)),
    "CB-22": dict(kind="bore", nom=320.0, lim=(0, 57), tol=("cylindricity", 20.0), setup="S3", src="tester",
                  mean=(0.6, 2.7, 4.8), own={29: (0.48, 0.21), 7: (0.9, 1.6), 19: (0.5, 0.3)}, tilt=(3.5, 1.5)),
    "CB-23": dict(kind="bore", nom=250.0, lim=(0, 52), tol=("roundness", 15.0), setup="S5", src="tester",
                  mean=(13.1, 14.6, 13.6), own={23: (0.61, 2.70), 6: (1.0, 2.2), 18: (0.7, 0.8)}, tilt=(0.5, 0.0)),
    "CB-24": dict(kind="bore", nom=250.0, lim=(0, 52), tol=("roundness", 11.5), setup="S2", src="cmm",
                  mean=(12.8, 13.8, 12.3), own={5: (0.4, 1.1), 17: (0.3, 0.5)}, tilt=(0.5, 0.5)),
    "CB-25": dict(kind="bore", nom=250.0, lim=(0, 52), tol=("roundness", 11.5), setup="S2", src="cmm",
                  mean=(3.3, 4.8, 2.3), own={5: (0.3, 2.6), 17: (0.4, 1.8)}, tilt=(-0.5, 0.5)),
    "CB-26": dict(kind="bore", nom=400.0, lim=(0, 63), tol=("cylindricity", 33.0), setup="S7", src="tester",
                  mean=(17.4, 23.4, 20.4), own={2: (9.5, 0.90), 29: (0.52, 1.05), 4: (1.2, 0.9), 16: (0.6, 2.4)},
                  tilt=(4.0, -2.5)),
    "GB-31": dict(kind="bore", nom=180.0, lim=(0, 46), tol=("roundness", 17.0), setup="S4", src="tester",
                  mean=(6.2, 7.2, 6.7), own={23: (0.44, 0.33), 4: (0.4, 0.7), 19: (0.3, 2.1)}, tilt=(0.0, 0.5)),
    "GB-32": dict(kind="bore", nom=180.0, lim=(0, 46), tol=("roundness", 24.0), setup="S4", src="tester",
                  mean=(17.4, 17.9, 16.4), own={29: (0.57, 2.21), 4: (0.3, 1.9), 19: (0.4, 0.6)}, tilt=(0.5, -0.5)),
    "RJ-41": dict(kind="journal", nom=300.0, lim=(-52, 0), tol=("cylindricity", 30.0), setup="S1", src="tester",
                  mean=(-5.9, -9.4, -6.6), own={29: (0.50, 1.77), 5: (1.0, 1.3), 15: (0.6, 0.4)}, tilt=(2.5, 1.0)),
    "RJ-42": dict(kind="journal", nom=300.0, lim=(-52, 0), tol=("roundness", 22.5), setup="S6", src="cmm",
                  mean=(-20.7, -21.7, -20.2), own={5: (0.4, 0.2), 18: (0.3, 1.4)}, tilt=(0.5, 0.0)),
    "RJ-43": dict(kind="journal", nom=300.0, lim=(-52, 0), tol=("roundness", 22.5), setup="S6", src="cmm",
                  mean=(-10.3, -11.8, -9.8), own={5: (0.3, 1.7), 18: (0.4, 2.3)}, tilt=(-0.5, 0.5)),
    "RJ-44": dict(kind="journal", nom=220.0, lim=(-46, 0), tol=("roundness", 17.5), setup="S3", src="tester",
                  mean=(-9.4, -10.4, -9.9), own={23: (0.46, 0.64), 6: (0.9, 0.5), 17: (0.5, 1.2)}, tilt=(0.5, -0.5)),
    "RJ-45": dict(kind="journal", nom=220.0, lim=(-46, 0), tol=("roundness", 18.5), setup="S8", src="cmm",
                  mean=(-13.8, -14.8, -12.8), own={4: (0.4, 2.0), 17: (0.3, 0.9)}, tilt=(0.0, 0.5)),
    "RJ-46": dict(kind="journal", nom=180.0, lim=(-40, 0), tol=("roundness", 26.5), setup="S5", src="tester",
                  mean=(-12.9, -14.4, -13.4), own={2: (6.69, 1.20), 29: (0.59, 1.19), 7: (1.1, 1.8), 16: (0.6, 0.1)},
                  tilt=(0.5, 0.0)),
}
# feed waviness, order -> amplitude um: above the 50 UPR assessment band, so it belongs to no form error, but it
# is in every record and swamps the form of a profile assessed unfiltered
WAVY = {f: {110 + 7 * i: a for i, a in enumerate((0.75, 0.55, 0.40))} for i, f in enumerate(FEATURES)}
LENGTH = {"CB-21": 640.0, "CB-22": 640.0, "CB-23": 480.0, "CB-24": 480.0, "CB-25": 480.0, "CB-26": 820.0,
          "GB-31": 150.0, "GB-32": 120.0, "RJ-41": 600.0, "RJ-42": 450.0, "RJ-43": 450.0, "RJ-44": 520.0,
          "RJ-45": 450.0, "RJ-46": 300.0}           # the feature's own length, mm: the sections sit along it
ORDER = list(FEATURES)
SPARSE = tuple(f for f, d in FEATURES.items() if d["src"] == "cmm")
# CB-22 as the shop measured it, before the re-hone of 2026-10-03: the score it was honed to clear, and the
# material the hone had not yet taken out. The truth, and a scan, are of the bore as it stands now.
# A hone follows the bore it is in. It takes out size and it changes the lobing, but it does not correct taper,
# so the pre-hone surface carries the same taper as the present one, DROP micrometres smaller in diameter.
PRE_HONE = {"CB-22": dict(drop=4.5, extra={4: (3.6, 2.05), 6: (2.4, 0.80), 10: (1.7, 1.55)})}


def pre_hone_mean(f):
    """The section means of the surface as it was before the hone: today's taper, shifted down by the stock."""
    return tuple(m - PRE_HONE[f]["drop"] / 2.0 for m in FEATURES[f]["mean"])
# the room temperature of each shop record, and of the metrology room
T_SHOP = {"CB-21": 23.4, "CB-22": 23.4, "CB-23": 22.1, "CB-24": 24.2, "CB-25": 24.2, "CB-26": 21.3,
          "GB-31": 24.6, "GB-32": 24.6, "RJ-41": 23.4, "RJ-42": 22.8, "RJ-43": 22.8, "RJ-44": 22.1,
          "RJ-45": 24.6, "RJ-46": 21.3}
T_ROOM = 20.4
# CB-22 was re-honed after the shop measured it, so its shop record is of the surface before that
REHONED = ("CB-22",)


# Where the jaws or the steady bore against the part, and how deep the mark is (um) and how wide (rad). The mark
# is what opens the gap between a mating size and a mean diameter: a plug gauge is stopped by the mark while the
# mean radius barely notices it, so a bore whose mean diameter sits mid-tolerance can still be under its lower
# limit on the gauge. It does not make a least-squares zone differ from a minimum-zone one. With orders 0 and 1
# dropped the least-squares centre is already the origin, and under a translation of the centre a single narrow
# feature moves the zone's high and low points together, so the origin is the minimax centre too.
MARK = {"CB-21": (3.4, 0.30, 1.15), "CB-22": (4.1, 0.26, 2.40), "CB-23": (2.9, 0.33, 0.55),
        "CB-24": (3.8, 0.28, 1.90), "CB-25": (3.8, 0.28, 1.90), "CB-26": (4.6, 0.24, 0.20),
        "GB-31": (3.1, 0.31, 2.75), "GB-32": (3.1, 0.31, 2.75), "RJ-41": (3.6, 0.29, 1.60),
        "RJ-42": (3.3, 0.30, 0.85), "RJ-43": (3.3, 0.30, 0.85), "RJ-44": (2.7, 0.34, 2.10),
        "RJ-45": (3.9, 0.27, 0.40), "RJ-46": (3.0, 0.32, 1.35)}


def local_mark(f, th, psi=0.0):
    """The mark the clamping left, in part coordinates: a dimple, narrow against the lobing."""
    depth, width, where = MARK[f]
    d = np.angle(np.exp(1j * (th - psi - where)))
    return -depth * np.exp(-(d / width) ** 2)


def mount_phase(f, rng):
    """Where the part happened to sit on the instrument. Form and size do not depend on it; the separation of the
    machine's error motion from the part's lobing does."""
    return float(rng.uniform(0.0, 2.0 * np.pi))


def harmonics(f):
    """The setup's lobing, plus the part's own content. Two parts finished in one setup without unclamping carry
    the same lobing, which is what lets a scan of one of them carry the form error and the mating deviation of the
    other; each still takes its own size from its own record. AMP is a per-part scale on the lobing, left at 1.00
    for every part: a round of authoring tried making it differ from part to part, and the transfer then became
    asymmetric (a twin 3 per cent low in amplitude cost 3 um, one 15 per cent high cost far more), which penalises
    the booking for a choice the records give no way to make. The hook is kept, the values are not used."""
    a = AMP.get(f, 1.0)
    h = {n: (amp * a, ph) for n, (amp, ph) in SETUP[FEATURES[f]["setup"]].items()}
    h.update(FEATURES[f]["own"])
    return h


def surface(f, j, th):
    """True radial deviation (um) of feature f at section j, in part coordinates, before any measurement."""
    d = FEATURES[f]
    out = np.full(len(th), d["mean"][j])
    for n, (a, ph) in harmonics(f).items():
        out = out + a * np.cos(n * th - ph)
    tx, ty = d["tilt"]
    z = SECTIONS[j] - 0.5
    return out + 2.0 * z * (tx * np.cos(th) + ty * np.sin(th)) + local_mark(f, th)



def measured(f, j, pts, rng, T=None, ecc=None, pre=False, spindle=False, psi=0.0):
    """One record's points at section j, as radius in mm: the surface (tip-filtered if the big ball was used), the
    feed waviness, the setup eccentricity of that measurement, thermal size, and the instrument's noise."""
    d = FEATURES[f]
    th = np.arange(pts) / pts * 2.0 * np.pi
    mean = d["mean"]
    h = harmonics(f)
    if pre and f in PRE_HONE:
        mean = pre_hone_mean(f)
        h = dict(h)
        h.update(PRE_HONE[f]["extra"])
    out = np.full(len(th), mean[j])
    for n, (a, ph) in h.items():               # the part, at the phase it was clamped at
        out = out + a * np.cos(n * (th - psi) - ph)
    tx, ty = d["tilt"]
    z = SECTIONS[j] - 0.5
    out = out + 2.0 * z * (tx * np.cos(th) + ty * np.sin(th))
    out = out + local_mark(f, th, psi)           # the mark the clamping left, carried round with the part
    for n, a in WAVY[f].items():                 # feed marks, far above the assessment band
        out = out + a * np.cos(n * (th - psi) - 0.37 * n)
    if spindle:                                  # the measuring machine's error motion, in its own reference
        for n, (a, ph) in (SPINDLE_AFTER if spindle == "after" else SPINDLE_BEFORE).items():
            out = out + a * np.cos(n * th - ph)
    e = ecc if ecc is not None else rng.uniform(15.0, 60.0)
    pe = rng.uniform(0, 2 * np.pi)
    out = out + e * np.cos(th - pe)
    T = T_ROOM if T is None else T
    out = out + d["nom"] / 2.0 * ALPHA * 1e-3 * (T - T_REF)
    return th, d["nom"] / 2.0 + (out + rng.normal(0.0, 0.12, len(th))) / 1000.0


def assess_profile(th, dev):
    """FM-7's assessment profile: order 1 out, Gaussian 50 UPR low-pass."""
    n = len(dev)
    F = np.fft.rfft(dev) / n
    out = np.zeros(n)
    for k in range(2, len(F)):
        g = float(np.exp(-np.pi * (GAUSS * k / UPR_CUTOFF) ** 2))
        if g < 1e-6:
            break
        out = out + 2.0 * g * (F[k].real * np.cos(k * th) - F[k].imag * np.sin(k * th))
    return out


def _lp(cols, dev, what):
    """Minimax fits, linearised (deviations are microns on a radius of hundreds of mm).
    cols: the columns of the reference feature's degrees of freedom. what: zone, mic or mcc."""
    m = np.column_stack(cols)
    k = m.shape[1]
    if what == "zone":                       # vars: params, hi, t ; hi - t <= dev - m p <= hi
        A = np.vstack([np.c_[-m, -np.ones(len(dev)), np.zeros(len(dev))],
                       np.c_[m, np.ones(len(dev)), -np.ones(len(dev))]])
        b = np.r_[-dev, dev]
        r = linprog(c=np.r_[np.zeros(k + 1), 1.0], A_ub=A, b_ub=b,
                    bounds=[(-400, 400)] * (k + 1) + [(0, None)])
        return float(r.x[-1])
    if what == "mic":                        # largest inscribed: max m0 with dev - m p >= m0
        r = linprog(c=np.r_[np.zeros(k), -1.0], A_ub=np.c_[m, np.ones(len(dev))], b_ub=dev,
                    bounds=[(-400, 400)] * (k + 1))
        return float(r.x[-1])
    r = linprog(c=np.r_[np.zeros(k), 1.0], A_ub=np.c_[-m, -np.ones(len(dev))], b_ub=-dev,
                bounds=[(-400, 400)] * (k + 1))
    return float(r.x[-1])


def roundness(th, dev):
    return _lp([np.cos(th), np.sin(th)], dev, "zone")


def cylindricity(ths, devs, zs):
    th = np.concatenate(ths)
    dev = np.concatenate(devs)
    z = np.concatenate([np.full(len(t), zz) for t, zz in zip(ths, zs)])
    c, s = np.cos(th), np.sin(th)
    return _lp([c, s, z * c, z * s], dev, "zone")


def mating_dev(kind, th, dev):
    """Radial deviation of the mating circle: largest inscribed for a bore, smallest circumscribed for a journal."""
    return _lp([np.cos(th), np.sin(th)], dev, "mic" if kind == "bore" else "mcc")


def mating_cyl(kind, ths, devs, zs):
    """The mating gauge over the whole feature: the largest inscribed cylinder of a bore, the smallest
    circumscribed cylinder of a journal, free in position and tilt."""
    th = np.concatenate(ths)
    dev = np.concatenate(devs)
    z = np.concatenate([np.full(len(t), zz) for t, zz in zip(ths, zs)])
    c, s = np.cos(th), np.sin(th)
    return _lp([c, s, z * c, z * s], dev, "mic" if kind == "bore" else "mcc")


def local_sizes(th, dev):
    """Diametrically opposite pairs, as a deviation on the diameter (um)."""
    n = len(dev)
    half = n // 2
    return 2.0 * np.array([(dev[i] + dev[i + half]) / 2.0 for i in range(half)])


def truth(f):
    """The sealed answer for feature f: form error (um) and the verdict, from the true surface at 20 C."""
    d = FEATURES[f]
    ths, devs = [], []
    for j in range(len(SECTIONS)):
        th = np.arange(TESTER_PTS) / TESTER_PTS * 2.0 * np.pi
        ths.append(th)
        devs.append(assess_profile(th, surface(f, j, th)))
    kind, tol = d["tol"]
    zs = [s - 0.5 for s in SECTIONS]
    bar = sum(d["mean"]) / len(d["mean"])
    whole = [(d["mean"][j] - bar) + devs[j] for j in range(len(SECTIONS))]   # taper kept, about the mean size
    if kind == "cylindricity":
        form = cylindricity(ths, whole, zs)
    else:
        form = max(roundness(t, p) for t, p in zip(ths, devs))
    # the mating gauge is a cylinder over the whole feature; a local size belongs to its own section
    mating = 2.0 * (bar + mating_cyl(d["kind"], ths, whole, zs))
    locs = np.concatenate([2.0 * d["mean"][j] + local_sizes(ths[j], devs[j]) for j in range(len(SECTIONS))])
    lo, hi = d["lim"]
    if d["kind"] == "bore":
        worst_local = max(locs)
        size_ok = mating >= lo and worst_local <= hi
    else:
        worst_local = min(locs)
        size_ok = mating <= hi and worst_local >= lo
    form_ok = form <= tol
    verdict = {(True, True): "accept", (False, True): "reject_size",
               (True, False): "reject_form", (False, False): "reject_both"}[(size_ok, form_ok)]
    return dict(form=form, verdict=verdict, mating=mating, local=worst_local, tol=tol, lim=d["lim"],
                form_margin=tol - form,
                size_margin=(mating - lo if d["kind"] == "bore" else hi - mating),
                local_margin=(hi - worst_local if d["kind"] == "bore" else worst_local - lo))


def scan(f, k, seed):
    """One dense scan from the metrology room's booking: three sections, TESTER_PTS points, at T_ROOM, on the
    room's certified tester, so no machine error motion rides on it."""
    rng = np.random.default_rng([seed, k, ORDER.index(f)])
    psi = mount_phase(f, rng)
    out = []
    for j in range(len(SECTIONS)):
        th, dev = measured(f, j, TESTER_PTS, rng, psi=psi)
        out.append((th, dev))
    return out
