#!/usr/bin/env python3
"""A correct program that has not been made fast, and a second solution written apart from the reference.

    python3 naive_quench.py PACKAGE_DIR OUT_CSV

It reaches the same oil for every load as the reference and solves the same equations, with none of the
reference's code and by another method:

  * each load is cooled on its own, one after another;
  * the bar is a set of ordinary differential equations in time (finite differences on 60 radial intervals,
    the 1/r term written out, a fictitious node beyond the surface carrying the boundary condition) handed to
    a library stiff integrator with its own error control, where the reference marches a finite-volume
    scheme with steps of its own choosing;
  * the times at which the centre passes each temperature are roots of the integrator's own interpolant.

The oil is worked out differently too. Tanks are joined into charges through a graph: two tanks of a listed
system are joined when the analyses drawn from them in the same sample round, or failing that in the nearest
rounds, agree within four times the laboratory's repeatability. Each joined group is a charge. A kept charge
is sampled when a straight line fitted to its maximum cooling rate on file rises by more than 1.5 per cent of
its mean a round, three times what ageing can do.
"""
import csv
import json
import subprocess
import sys

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

N = 60
K_TABLE = {"C45": ([20, 300, 600, 800, 900], [50, 44, 34, 26, 26]), "42CrMo4": ([20, 300, 600, 800, 900], [43, 40, 33, 27, 27])}
C_TABLE = {"C45": ([20, 300, 600, 720, 800, 900], [470, 560, 750, 900, 650, 650]),
           "42CrMo4": ([20, 300, 600, 720, 800, 900], [460, 550, 720, 850, 640, 640])}


def h_oil(ts, oil):
    cr_max, t_p, cr_300 = oil
    h_p = 14200.0 * cr_max / (t_p - 40.0)
    h_300 = 14200.0 * cr_300 / 260.0
    return float(np.interp(ts, [100.0, 300.0, t_p, t_p + 120.0], [0.6 * h_300, h_300, h_p, 0.15 * h_p]))


def one_load(steel, diameter_mm, furnace, bath, oil):
    R = diameter_mm / 2000.0
    r = np.linspace(0.0, R, N + 1)
    dr = R / N
    kx, ky = K_TABLE[steel]
    cx, cy = C_TABLE[steel]

    def rate(t, T):
        k = np.interp(T, kx, ky)
        c = 7800.0 * np.interp(T, cx, cy)
        out = np.empty_like(T)
        kp = 0.5 * (k[1:] + k[:-1])                       # conductivity between neighbours
        # interior: (1/r) d/dr (r k dT/dr)
        east = kp[1:] * (r[1:-1] + 0.5 * dr) * (T[2:] - T[1:-1])
        west = kp[:-1] * (r[1:-1] - 0.5 * dr) * (T[1:-1] - T[:-2])
        out[1:-1] = (east - west) / (r[1:-1] * dr * dr) / c[1:-1]
        # centre: by symmetry the operator is 2 k d2T/dr2 there
        out[0] = 4.0 * kp[0] * (T[1] - T[0]) / (dr * dr) / c[0]
        # surface: fictitious node from -k dT/dr = h (Ts - Tb)
        q = h_oil(T[-1], oil) * (T[-1] - bath)
        ghost = T[-2] - 2.0 * dr * q / k[-1]
        east = k[-1] * (R + 0.5 * dr) * (ghost - T[-1])
        west = kp[-1] * (R - 0.5 * dr) * (T[-1] - T[-2])
        out[-1] = (east - west) / (R * dr * dr) / c[-1]
        return out

    def cold(t, T):
        return T[0] - 150.0
    cold.terminal = True
    run = solve_ivp(rate, (0.0, 1.0e5), np.full(N + 1, float(furnace)), method="BDF", dense_output=True,
                    events=cold, rtol=1e-7, atol=1e-5)
    end = run.t_events[0][0]

    def centre_at(level):
        return brentq(lambda t: run.sol(t)[0] - level, 0.0, end, xtol=1e-9)
    t800, t725, t675, t500 = (centre_at(v) for v in (800.0, 725.0, 675.0, 500.0))
    grid = np.linspace(0.0, end, 4000)
    field = run.sol(grid)
    return (t500 - t800, 50.0 / (t675 - t725), float((field[0] - field[-1]).max()), float(run.sol(t500)[-1]), end)


def read(package, name):
    with open(package + "/" + name, newline="") as handle:
        return list(csv.DictReader(handle))


def same_oil(a, b):
    """Whether the analyses drawn from two tanks are of one oil: compared in the rounds nearest each other."""
    gaps = sorted((abs(np.datetime64(da) - np.datetime64(db)), va, vb) for da, va in a for db, vb in b)
    nearest = [g for g in gaps if g[0] == gaps[0][0]]
    return any(abs(va - vb) <= 0.02 * min(va, vb) for _, va, vb in nearest)


def charges(tanks, samples):
    """{tank: an identifier of the charge it holds}."""
    system = {t["tank"]: t["oil_system"] for t in tanks}
    seen = {}
    for s in samples:
        seen.setdefault(s["sampled_at"], []).append((s["date"], float(s["cr_max_K_s"])))
    names = list(system)
    parent = {m: m for m in names}

    def root(m):
        while parent[m] != m:
            m = parent[m]
        return m

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if system[a] == system[b] and a in seen and b in seen and same_oil(seen[a], seen[b]):
                parent[root(b)] = root(a)
    for m in names:                                   # a tank never sampled goes with the first of its system
        if m not in seen:
            parent[m] = root(next(n for n in names if system[n] == system[m]))
    return {m: root(m) for m in names}


def kept_is_changing(history):
    """history: [(date, cr_max)], one per sample date. A least-squares slope against time, per round."""
    if len(history) < 3:
        return False
    t = np.array([(np.datetime64(d) - np.datetime64(history[0][0])).astype(int) for d, _ in history], float) / 182.0
    v = np.array([c for _, c in history])
    slope = np.polyfit(t, v, 1)[0]
    return slope / v.mean() > 0.015


def main(package, out):
    with open(package + "/site.json") as handle:
        site = json.load(handle)
    allowance = int(site["lab_samples"])
    tanks, log, samples, loads = (read(package, n + ".csv") for n in ("tanks", "oil_log", "oil_samples", "loads"))
    system = {t["tank"]: t["oil_system"] for t in tanks}
    charge = charges(tanks, samples)
    refilled = {}
    for job in log:
        if job["work"] == "CHARGE_RENEWED":
            refilled[job["oil_system"]] = max(job["date"], refilled.get(job["oil_system"], ""))
    keys = ("cr_max_K_s", "t_crmax_C", "cr_300_K_s")
    dated = {}                                        # charge -> {date: [figures of each sample]}
    for s in samples:
        c = charge[s["sampled_at"]]
        if system[c] in refilled and s["date"] >= refilled[system[c]]:
            continue
        dated.setdefault(c, {}).setdefault(s["date"], []).append(tuple(float(s[k]) for k in keys))
    history = {c: [(d, tuple(float(np.mean(col)) for col in zip(*v))) for d, v in sorted(by.items())]
               for c, by in dated.items()}
    ask = {}
    for t in tanks:
        c = charge[t["tank"]]
        if system[t["tank"]] in refilled or kept_is_changing([(d, f[0]) for d, f in history[c]]):
            ask.setdefault(c, t["tank"])
    assert len(ask) <= allowance, "more charges to sample than the laboratory will analyse"
    now = {}
    if ask:
        reply = subprocess.run(["labsample", package] + list(ask.values()), capture_output=True, text=True, check=True)
        for row in csv.DictReader(reply.stdout.splitlines()):
            now[charge[row["sampled_at"]]] = tuple(float(row[k]) for k in keys)
    drawn = np.datetime64(site["samples_drawn"])

    def oil_for(p):
        c = charge[p["tank"]]
        last_date, last = history[c][-1]
        if system[p["tank"]] in refilled:
            return now[c] if p["date"] > refilled[system[p["tank"]]] else last
        end = now.get(c, last)
        w = float((np.datetime64(p["date"]) - np.datetime64(last_date)).astype(int)) / float(
            (drawn - np.datetime64(last_date)).astype(int))
        return tuple((1.0 - w) * a + w * b for a, b in zip(last, end))

    with open(out, "w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["load", "t85_core_s", "cr700_core_K_s", "dT_max_K", "ts_core500_C", "t150_core_s"])
        for p in loads:
            got = one_load(p["steel"], float(p["diameter_mm"]), float(p["furnace_C"]), float(p["bath_C"]), oil_for(p))
            w.writerow([p["load"], "%.3f" % got[0], "%.4f" % got[1], "%.2f" % got[2], "%.2f" % got[3], "%.2f" % got[4]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
