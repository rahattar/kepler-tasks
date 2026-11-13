#!/usr/bin/env python3
"""Cylinder pressure indicating to IS-2 for one cell package.

    python3 indicate.py PACKAGE_DIR OUT_CSV

Three steps.

1. What the indicating system did to the pressure. A record is the cylinder pressure as the indicating system
   has it: at the system's angles and on the system's scale. Whether those are the crank angle and the
   pressure is settled from the records themselves, on the compression stroke, where the physics is known:
   until combustion starts the gross heat release of IS-2 section 7 is nil at every angle. The encoder's index
   error and the transducer's gain are the two numbers that make it so (rig_state).
2. IS-2 on every cycle, at the crank angles and pressures of step 1 (session_results).
3. The table: the mean over the cycles of each point and cylinder.

Everything is done for all cycles of a point at once; a package of 20,000 cycles takes about two seconds.
"""
import csv
import json
import os
import sys

import numpy as np

R_GAS = 287.0
SYSTEM_ANGLE = -180.0 + 0.5 * np.arange(720)      # the indicating system's angle for the samples of a cycle
RIG = "index and gain"                            # what step 1 settles


def volume(theta, eng):
    """IS-2 section 2."""
    bore, stroke, rod = eng["bore_mm"] * 1e-3, eng["stroke_mm"] * 1e-3, eng["conrod_mm"] * 1e-3
    crank = stroke / 2
    swept = np.pi * bore * bore / 4 * stroke
    t = np.deg2rad(theta)
    lift = crank * (1 - np.cos(t)) + rod - np.sqrt(rod * rod - (crank * np.sin(t)) ** 2)
    return swept / (eng["compression_ratio"] - 1) + np.pi * bore * bore / 4 * lift


def gamma(temp, burned):
    """IS-2 section 5."""
    unburned = 1.375 - 6.99e-5 * temp
    return unburned + (1.330 - 4.50e-5 * temp - unburned) * burned


def wall_factor(eng, speed, vol_mid):
    """Everything in the wall heat of one half-degree step that does not depend on the pressure (section 6)."""
    bore = eng["bore_mm"] * 1e-3
    piston_speed = 2 * eng["stroke_mm"] * 1e-3 * speed / 60
    area = np.pi * bore * bore / 2 + 4 * vol_mid / bore
    return 130.0 * vol_mid ** -0.06 * (piston_speed + 1.4) ** 0.8 * area * 0.5 / (6.0 * speed)


def pressures(record, eng, point, gain):
    """Cycles by samples, in Pa: counts to pressure by the system's scale and the transducer's gain, then the
    level of section 3 (the mean of the first ten degrees is the manifold pressure)."""
    p = record.reshape(-1, 720).astype(np.float64) * (eng["bar_per_count"] * 1e5 / gain)
    p += point["p_man"] - p[:, :20].mean(axis=1, keepdims=True)
    return p


def rig_state(eng, points, records):
    """(index error in degrees, transducer gain).

    The mean cycle of each point and cylinder is taken over the samples from 12 degrees after inlet valve
    closing to 47 degrees before top dead centre, where no charge of these engines has begun to burn. For a
    trial index error and gain the gross heat release of section 7 is summed along that stretch. On the right
    pair the sum stays at nil; an index error bends it one way along the stroke and a gain error another, so
    the two are told apart by its shape. The sum is weighted by 1/V, which makes it the size of a pressure
    error, a free level is taken out, and the squares are minimised by Gauss-Newton from the best point of a
    coarse grid.
    """
    if RIG == "as the system has it":
        return 0.0, 1.0
    means = [pressures(records[pt["point"]], eng, pt, 1.0).reshape(eng["cylinders"], -1, 720).mean(axis=1) for pt in points]
    first = int(np.searchsorted(SYSTEM_ANGLE, eng["ivc_deg"] + 12.0))
    last = int(np.searchsorted(SYSTEM_ANGLE, -47.0))

    def residual(state):
        index, gain = state
        vol = volume(SYSTEM_ANGLE[first:last + 1] + index, eng)
        vol_mid, dvol = 0.5 * (vol[1:] + vol[:-1]), np.diff(vol)
        weight = 1.0 / vol[1:]
        parts = []
        for pt, mean in zip(points, means):
            p = (mean[:, first:last + 1] - pt["p_man"]) / gain + pt["p_man"]
            p_mid = 0.5 * (p[:, 1:] + p[:, :-1])
            temp = p_mid * vol_mid / (pt["p_man"] * volume(eng["ivc_deg"], eng) / pt["t_ivc"])
            g = gamma(temp, 0.0)
            heat = (g * p_mid * dvol + vol_mid * (p[:, 1:] - p[:, :-1])) / (g - 1) + wall_factor(eng, pt["speed"], vol_mid) * (
                p_mid * 1e-5) ** 0.8 * temp ** -0.4 * (temp - pt["t_wall"])
            run = np.cumsum(heat, axis=1) * weight / pt["p_man"]
            run -= (run * weight).sum(axis=1, keepdims=True) / (weight * weight).sum() * weight
            parts.append(run.ravel())
        return np.concatenate(parts)

    free = {"index and gain": [0, 1], "index alone": [0], "gain alone": [1]}[RIG]
    best, state = None, None
    for index in (np.arange(-4.0, 4.01, 0.5) if 0 in free else [0.0]):
        for gain in (np.arange(0.88, 1.121, 0.03) if 1 in free else [1.0]):
            r = residual((index, gain))
            if best is None or r @ r < best:
                best, state = r @ r, np.array([index, gain])
    step = np.array([1e-3, 1e-4])
    for _ in range(12):
        r0 = residual(state)
        jac = np.empty((len(r0), len(free)))
        for column, which in enumerate(free):
            moved = state.copy()
            moved[which] += step[which]
            jac[:, column] = (residual(moved) - r0) / step[which]
        change = np.linalg.lstsq(jac, -r0, rcond=None)[0]
        state[free] += change
        if np.max(np.abs(change) / step[free]) < 1.0:
            break
    return float(state[0]), float(state[1])


def session_results(eng, point, record, index, gain):
    """IS-2 sections 3 to 8 for every cycle of one point: six arrays over the cycles, in the table's order."""
    p = pressures(record, eng, point, gain)
    theta = SYSTEM_ANGLE + index
    vol = volume(theta, eng)
    swept = np.pi * (eng["bore_mm"] * 1e-3) ** 2 / 4 * eng["stroke_mm"] * 1e-3
    imep = (0.5 * (p[:, 1:] + p[:, :-1]) @ np.diff(vol)) / swept * 1e-5
    top = np.clip(np.argmax(p, axis=1), 10, 709)
    x = np.arange(-10, 11) * 0.5
    fit = np.take_along_axis(p, top[:, None] + np.arange(-10, 11)[None, :], axis=1) @ np.linalg.pinv(
        np.stack([np.ones_like(x), x, x * x], axis=1)).T
    vertex = -fit[:, 1] / (2 * fit[:, 2])
    out = [imep, (fit[:, 0] + fit[:, 1] * vertex + fit[:, 2] * vertex * vertex) * 1e-5, theta[top] + vertex]

    k0 = int(np.searchsorted(theta, eng["ivc_deg"]))
    k1 = int(np.searchsorted(theta, eng["evo_deg"], side="right")) - 1
    pw, th = p[:, k0:k1 + 1], theta[k0:k1 + 1]
    vol_mid, dvol = 0.5 * (vol[k0 + 1:k1 + 1] + vol[k0:k1]), np.diff(vol[k0:k1 + 1])
    p_mid, dp = 0.5 * (pw[:, 1:] + pw[:, :-1]), pw[:, 1:] - pw[:, :-1]
    temp = p_mid * vol_mid / (point["p_man"] * volume(eng["ivc_deg"], eng) / point["t_ivc"])
    wall = wall_factor(eng, point["speed"], vol_mid) * (p_mid * 1e-5) ** 0.8 * temp ** -0.4 * (temp - point["t_wall"])
    burned = np.zeros_like(p_mid)
    total = None
    for _ in range(20):
        g = gamma(temp, burned)
        released = np.cumsum((g * p_mid * dvol + vol_mid * dp) / (g - 1) + wall, axis=1)
        share = np.clip(released / released[:, -1:], 0.0, 1.0)
        burned = np.concatenate([0.5 * share[:, :1], 0.5 * (share[:, 1:] + share[:, :-1])], axis=1)
        if total is not None and np.max(np.abs(released[:, -1] - total) / np.abs(released[:, -1])) < 1e-6:
            break
        total = released[:, -1].copy()
    share = np.concatenate([np.zeros((len(p), 1)), released / released[:, -1:]], axis=1)
    rows = np.arange(len(p))
    for level in (0.1, 0.5):
        k = np.clip(np.argmax(share >= level, axis=1), 1, share.shape[1] - 1)
        below, above = share[rows, k - 1], share[rows, k]
        out.append(th[k - 1] + (level - below) / (above - below) * 0.5)
    out.append(released[:, -1])
    return out


def main(package, destination):
    with open(os.path.join(package, "engine.json")) as handle:
        eng = json.load(handle)
    points = []
    with open(os.path.join(package, "points.csv"), newline="") as handle:
        for row in csv.DictReader(handle):
            points.append(dict(point=row["point"], speed=float(row["speed_rpm"]), p_man=float(row["p_man_bar"]) * 1e5,
                               t_ivc=float(row["t_ivc_K"]), t_wall=float(row["t_wall_K"]), record=row["record"]))
    records = {pt["point"]: np.load(os.path.join(package, pt["record"])) for pt in points}
    index, gain = rig_state(eng, points, records)
    sys.stderr.write("index error %.3f degrees, transducer gain %.4f\n" % (index, gain))
    with open(destination, "w", newline="") as handle:
        table = csv.writer(handle, lineterminator="\n")
        table.writerow(["point", "cylinder", "imep_bar", "pmax_bar", "apmax_deg", "ca10_deg", "ca50_deg", "q_gross_J"])
        for pt in points:
            per_cycle = session_results(eng, pt, records[pt["point"]], index, gain)
            for cylinder in range(eng["cylinders"]):
                table.writerow([pt["point"], cylinder + 1] + [
                    "%.4f" % values.reshape(eng["cylinders"], -1)[cylinder].mean() for values in per_cycle])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python3 indicate.py PACKAGE_DIR OUT_CSV")
    main(sys.argv[1], sys.argv[2])
