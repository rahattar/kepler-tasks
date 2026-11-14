#!/usr/bin/env python3
"""Cylinder pressure indicating to IS-2 for one cell package.

    python3 indicate.py PACKAGE_DIR OUT_CSV

1. Counts to readings: samples at an end of the converter's range are replaced (IS-2 section 3), each
   cylinder's counts are scaled by the system's scale over its transducer's gain, and each cycle's level is
   set at manifold pressure (section 4).
2. The indicating system's state (section 9): the encoder's index, each transducer's gain and each
   transducer's thermal-shock coefficient, fitted together on the mean cycles of the cycles that fired, so
   that the gross heat release is nil on the compression stretch and constant on the expansion stretch.
3. Every cycle at the true angle and pressure: the reading plus the thermal-shock deficit, then the work, the
   peak on the filtered record, the heat release and the burn angles (sections 8 and 11); the cycles that
   misfired (section 10) are left out of the means.
"""
import csv
import json
import os
import sys

import numpy as np
from scipy import optimize, signal

R_GAS = 287.0
TAU = 3.0e-3                                    # s, IS-2 section 3
CUT_OFF = 2500.0                                # Hz, IS-2 section 11
SYSTEM_ANGLE = -180.0 + 0.5 * np.arange(720)
RAILS = (-32768, 32767)
APPLY = {"despike", "index", "gains", "shock", "misfires", "filter"}     # what is carried out (all of IS-2)
STARTS = (0.0,)                                 # trial indices the fit starts from


def volume(theta, eng):
    """IS-2 section 2."""
    bore, stroke, rod = eng["bore_mm"] * 1e-3, eng["stroke_mm"] * 1e-3, eng["conrod_mm"] * 1e-3
    crank = stroke / 2
    swept = np.pi * bore * bore / 4 * stroke
    t = np.deg2rad(theta)
    lift = crank * (1 - np.cos(t)) + rod - np.sqrt(rod * rod - (crank * np.sin(t)) ** 2)
    return swept / (eng["compression_ratio"] - 1) + np.pi * bore * bore / 4 * lift


def gamma(temp, burned):
    """IS-2 section 6."""
    unburned = 1.375 - 6.99e-5 * temp
    return unburned + (1.330 - 4.50e-5 * temp - unburned) * burned


def coefficient(p, temp, vol, eng, speed):
    """Hohenberg's coefficient, W/(m2 K), IS-2 section 7 (p in Pa)."""
    piston = 2 * eng["stroke_mm"] * 1e-3 * speed / 60
    return 130.0 * vol ** -0.06 * (p * 1e-5) ** 0.8 * temp ** -0.4 * (piston + 1.4) ** 0.8


def despiked(record):
    """Counts as floats, a sample at an end of the range replaced by the mean of its neighbours."""
    counts = record.astype(np.float64)
    if "despike" not in APPLY:
        return counts
    bad = (record == RAILS[0]) | (record == RAILS[1])
    if bad.any():
        left = np.concatenate([counts[..., 1:2], counts[..., :-1]], axis=-1)
        right = np.concatenate([counts[..., 1:], counts[..., -2:-1]], axis=-1)
        counts = np.where(bad, 0.5 * (left + right), counts)
    return counts


def readings(counts, eng, point, gains):
    """Counts -> readings in Pa: the system's scale over the transducer's gain, the level at manifold pressure.
    `gains` and the point's values broadcast against counts[..., :1]."""
    p = counts * (eng["bar_per_count"] * 1e5)
    return (p - p[..., :20].mean(axis=-1, keepdims=True)) / gains + point["p_man"]


def deficit(p, theta, eng, point, shock):
    """s H in Pa for pressures p (rows by samples) at crank angles theta: H is the integral from inlet valve
    closing of the wall heat flux, each step at the mean of its ends, with memory TAU (IS-2 section 3). The
    recursion H_j = a H_(j-1) + TAU (1 - a) q_j is summed in closed form, so that rows of different speeds go
    together. `shock` and the point's values broadcast against p[..., :1]."""
    k0 = int(np.searchsorted(theta, eng["ivc_deg"]))
    k1 = int(np.searchsorted(theta, eng["evo_deg"], side="right"))           # flux is nil outside [k0, k1)
    vol = volume(theta[k0:k1], eng)
    pc = p[..., k0:k1]
    mass = point["p_man"] * volume(eng["ivc_deg"], eng) / (R_GAS * point["t_ivc"])
    temp = pc * vol / (mass * R_GAS)
    flux = coefficient(pc, temp, vol, eng, point["speed"]) * (temp - point["t_wall"])
    flux = np.concatenate([flux, np.zeros(flux.shape[:-1] + (p.shape[-1] - k1,))], axis=-1)
    step = 0.5 * (flux[..., 1:] + flux[..., :-1])
    each = 0.5 / (6.0 * point["speed"]) / TAU                                  # dt / TAU of a half-degree step
    rate = each * np.arange(step.shape[-1])
    H = np.zeros_like(p)
    H[..., k0 + 1:] = np.exp(-rate) * np.cumsum(np.exp(rate) * step, axis=-1) * TAU * (1 - np.exp(-each))
    return shock * H * 100.0


def pressures(read, theta, eng, point, shock):
    """The pressure in the cylinder: the reading plus the deficit, the deficit worked out from the pressure."""
    if "shock" not in APPLY or not np.any(shock):
        return read
    p = read
    for _ in range(2):
        p = read + deficit(p, theta, eng, point, shock)
    return p


def released(p, theta, eng, point, burned=None, until=1e-4, lo=None, hi=None, first=None):
    """Gross heat release Q (cycles by steps) summed from inlet valve closing, or from `lo`, to exhaust valve
    opening, or to `hi`, IS-2 section 8. With `burned` given, the burned fraction is held at it and nothing is
    repeated; `first` is the burned fraction the repetition starts from. Returns (Q at the end of every step,
    the angles of those ends, the burned fraction used)."""
    k0 = int(np.searchsorted(theta, eng["ivc_deg"] if lo is None else lo))
    k1 = int(np.searchsorted(theta, eng["evo_deg"] if hi is None else hi, side="right")) - 1
    pw, th = p[..., k0:k1 + 1], theta[k0:k1 + 1]
    vol = volume(th, eng)
    vm, dv = 0.5 * (vol[1:] + vol[:-1]), np.diff(vol)
    pm, dp = 0.5 * (pw[..., 1:] + pw[..., :-1]), np.diff(pw, axis=-1)
    mass = point["p_man"] * volume(eng["ivc_deg"], eng) / (R_GAS * point["t_ivc"])
    temp = pm * vm / (mass * R_GAS)
    dt = 0.5 / (6.0 * point["speed"])
    bore = eng["bore_mm"] * 1e-3
    wall = coefficient(pm, temp, vm, eng, point["speed"]) * (np.pi * bore * bore / 2 + 4 * vm / bore) * (temp - point["t_wall"]) * dt
    fixed = burned is not None
    if burned is not None:
        x = np.broadcast_to(burned, pm.shape)
    else:
        x = np.zeros_like(pm) if first is None else np.broadcast_to(first, pm.shape)
    unburned = 1.375 - 6.99e-5 * temp                 # section 6, worked out once
    burned_gas = 1.330 - 4.50e-5 * temp
    work, rise = pm * dv, vm * dp
    total = None
    for _ in range(1 if fixed else 30):
        g = unburned + (burned_gas - unburned) * x
        q = np.cumsum((g * work + rise) / (g - 1) + wall, axis=-1)
        if fixed:
            break
        share = np.clip(q / q[..., -1:], 0.0, 1.0)
        x = np.concatenate([0.5 * share[..., :1], 0.5 * (share[..., 1:] + share[..., :-1])], axis=-1)
        # a misfired cycle releases next to nothing and its burned fraction never settles; it is left out of
        # every result (section 10), so the repetition is judged on the cycles that fired
        if total is not None:
            lit = fired(q[..., -1]) if "misfires" in APPLY else np.ones(q.shape[:-1], dtype=bool)
            change = np.abs(q[..., -1] - total) / np.abs(q[..., -1])
            if not lit.any() or np.max(change[lit]) < until:
                break
        total = q[..., -1].copy()
    return q, th[1:], x


def fired(q_end):
    """IS-2 section 10, on (cylinders, cycles) totals."""
    if "misfires" not in APPLY:
        return np.ones_like(q_end, dtype=bool)
    return q_end >= 0.25 * np.median(q_end, axis=-1, keepdims=True)


def state(eng, points, counts):
    """(index, gains, shock coefficients): IS-2 section 9 on the mean cycles of the cycles that fired, every point
    and cylinder a row of one array."""
    ncyl = eng["cylinders"]
    unit = np.ones(ncyl)
    means = []
    for pt in points:
        q, _, _ = released(readings(counts[pt["point"]], eng, pt, 1.0), SYSTEM_ANGLE, eng, pt, burned=0.0)
        keep = fired(q[..., -1])
        means.append(np.stack([counts[pt["point"]][c][keep[c]].mean(axis=0) for c in range(ncyl)]))
    rows = np.concatenate(means)                                      # (points x cylinders, 720)
    of = np.tile(np.arange(ncyl), len(points))
    stack = {key: np.repeat([pt[key] for pt in points], ncyl)[:, None] for key in ("p_man", "t_ivc", "t_wall", "speed")}
    free_index, free_gain, free_shock = ("index" in APPLY), ("gains" in APPLY), ("shock" in APPLY)
    # the two stretches of section 9, held to the same samples whatever index is tried
    stretches = [(int(np.searchsorted(SYSTEM_ANGLE, eng["ivc_deg"] + 10.0)), int(np.searchsorted(SYSTEM_ANGLE, -40.0))),
                 (int(np.searchsorted(SYSTEM_ANGLE, 70.0)), int(np.searchsorted(SYSTEM_ANGLE, eng["evo_deg"] - 10.0)))]

    def unpack(v):
        at = int(free_index)
        index = v[0] if free_index else 0.0
        gains = v[at:at + ncyl] if free_gain else unit
        at += ncyl * free_gain
        shock = v[at:at + ncyl] if free_shock else 0 * unit
        return index, gains, shock

    def residual(v):
        index, gains, shock = unpack(v)
        theta = SYSTEM_ANGLE + index
        vol = volume(theta, eng)
        p = pressures(readings(rows, eng, stack, gains[of][:, None]), theta, eng, stack, shock[of][:, None])
        parts = []
        for (k0, k1), burnt in zip(stretches, (0.0, 1.0)):
            if burnt and not free_shock:
                continue
            q, _, _ = released(p, theta, eng, stack, burned=burnt, lo=theta[k0], hi=theta[k1])
            run = q / vol[k0 + 1:k1 + 1] / stack["p_man"]
            parts.append((run - run.mean(axis=-1, keepdims=True)).ravel())
        return np.concatenate(parts)

    start = [0.0] * free_index + [1.0] * (ncyl * free_gain) + [0.04] * (ncyl * free_shock)
    lower = [-4.0] * free_index + [0.9] * (ncyl * free_gain) + [0.0] * (ncyl * free_shock)
    upper = [4.0] * free_index + [1.1] * (ncyl * free_gain) + [0.15] * (ncyl * free_shock)
    if not start:
        return 0.0, unit, 0 * unit
    best = None
    for first in (STARTS if free_index else (0.0,)):
        v0 = np.array(start)
        if free_index:
            v0[0] = first
        fit = optimize.least_squares(residual, v0, bounds=(lower, upper), x_scale="jac", max_nfev=60)
        if best is None or fit.cost < best.cost:
            best = fit
    return unpack(best.x)


def results(eng, point, counts, index, gains, shock):
    """IS-2 sections 8 and 11 for every cycle of one point: (cylinders, cycles) arrays in the table's order, and
    which cycles fired."""
    theta = SYSTEM_ANGLE + index
    p = pressures(readings(counts, eng, point, np.asarray(gains)[:, None, None]), theta, eng, point,
                  np.asarray(shock)[:, None, None])
    vol = volume(theta, eng)
    swept = np.pi * (eng["bore_mm"] * 1e-3) ** 2 / 4 * eng["stroke_mm"] * 1e-3
    imep = (0.5 * (p[..., 1:] + p[..., :-1]) @ np.diff(vol)) / swept * 1e-5
    smooth = signal.sosfiltfilt(signal.butter(4, CUT_OFF, fs=12.0 * point["speed"], output="sos"), p, axis=-1) \
        if "filter" in APPLY else p
    top = np.clip(np.argmax(smooth, axis=-1), 10, 709)
    x = np.arange(-10, 11) * 0.5
    near = np.take_along_axis(smooth, top[..., None] + np.arange(-10, 11), axis=-1)
    fit = near @ np.linalg.pinv(np.stack([np.ones_like(x), x, x * x], axis=1)).T
    vertex = -fit[..., 1] / (2 * fit[..., 2])
    pmax = (fit[..., 0] + fit[..., 1] * vertex + fit[..., 2] * vertex * vertex) * 1e-5
    apmax = theta[top] + vertex
    _, _, typical = released(p.mean(axis=1, keepdims=True), theta, eng, point)     # each cylinder's mean cycle
    q, th, _ = released(p, theta, eng, point, first=typical)
    share = q / q[..., -1:]
    angles = []
    for level in (0.1, 0.5):
        k = np.clip(np.argmax(share >= level, axis=-1), 1, share.shape[-1] - 1)
        below = np.take_along_axis(share, (k - 1)[..., None], axis=-1)[..., 0]
        above = np.take_along_axis(share, k[..., None], axis=-1)[..., 0]
        angles.append(th[k - 1] + (level - below) / (above - below) * 0.5)
    q_end = q[..., -1]
    return [imep, pmax, apmax, angles[0], angles[1], q_end], fired(q_end)


def main(package, destination):
    with open(os.path.join(package, "engine.json")) as handle:
        eng = json.load(handle)
    points = []
    with open(os.path.join(package, "points.csv"), newline="") as handle:
        for row in csv.DictReader(handle):
            points.append(dict(point=row["point"], speed=float(row["speed_rpm"]), p_man=float(row["p_man_bar"]) * 1e5,
                               t_ivc=float(row["t_ivc_K"]), t_wall=float(row["t_wall_K"]), record=row["record"]))
    counts = {pt["point"]: despiked(np.load(os.path.join(package, pt["record"]))) for pt in points}
    index, gains, shock = state(eng, points, counts)
    sys.stderr.write("index %.3f degrees; gains %s; shock %s bar per kJ/m2\n" % (
        index, " ".join("%.4f" % g for g in gains), " ".join("%.4f" % s for s in shock)))
    with open(destination, "w", newline="") as handle:
        table = csv.writer(handle, lineterminator="\n")
        table.writerow(["point", "cylinder", "imep_bar", "pmax_bar", "apmax_deg", "ca10_deg", "ca50_deg", "q_gross_J"])
        for pt in points:
            values, keep = results(eng, pt, counts[pt["point"]], index, gains, shock)
            for c in range(eng["cylinders"]):
                table.writerow([pt["point"], c + 1] + ["%.4f" % v[c][keep[c]].mean() for v in values])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 indicate.py PACKAGE_DIR OUT_CSV")
    main(sys.argv[1], sys.argv[2])
