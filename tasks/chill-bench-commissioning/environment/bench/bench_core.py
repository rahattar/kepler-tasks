"""Sealed side of the commissioning bench.

In the shipped task this module lives in a docker-compose sidecar container and is
never present in the agent's container -- the agent reaches it over the compose
network and can no more read the fleet's accommodation coefficients than it can read
the verifier. The budget is decremented here, server side, so it cannot be gamed.

This prototype runs it as a local module so the shape can be measured before the
container plumbing is built.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import physics as ph
import make_fleet as fleet

SAMPLE_HZ = 10.0
NOISE_RMS_K = 0.5          # wafer thermocouples, per sample
OFFSET_RMS_K = 0.3         # per-run calibration offset on the test wafer
PLATE_NOISE_RMS_K = 0.08   # plate RTD is quieter
MAX_RUN_S = fleet.MAX_RUN_S
BUDGET_RUNS = fleet.BUDGET_RUNS

_ROWS = {r["station"]: r for r in fleet.build()}


def station(name):
    r = _ROWS[name]
    return ph.Station(name, r["inner_standoff_um"] * 1e-6, r["outer_standoff_um"] * 1e-6,
                      r["incoming_temperature_C"], r["plate_setpoint_C"],
                      r["_alpha"], r["_alpha"])


def names():
    return list(_ROWS)


def trace(name, pressure_torr, seconds, run_index):
    """One test-wafer run. Returns (header, rows) at 10 Hz with realistic noise."""
    if name not in _ROWS:
        raise KeyError(f"unknown station {name}")
    P = float(pressure_torr)
    if not (fleet.SPEC["he_pressure_min_torr"] <= P
            <= fleet.SPEC["he_pressure_max_torr"]):
        raise ValueError(
            f"pressure {P} Torr is outside the "
            f"{fleet.SPEC['he_pressure_min_torr']}-"
            f"{fleet.SPEC['he_pressure_max_torr']} Torr supply range")
    secs = float(seconds)
    if not (0.5 <= secs <= MAX_RUN_S):
        raise ValueError(f"run length must be between 0.5 and {MAX_RUN_S} s")

    st = station(name)
    t, Tm, Ti, To, Tp = ph.integrate(P, st, t_max=secs)
    stride = max(1, int(round(1.0 / (SAMPLE_HZ * ph.DT))))
    sel = slice(0, len(t), stride)
    t, Tm, Ti, To, Tp = t[sel], Tm[sel], Ti[sel], To[sel], Tp[sel]

    rng = np.random.default_rng(fleet.SEED + 7919 * run_index)
    off_m, off_i, off_o = rng.normal(0.0, OFFSET_RMS_K, 3)
    Tm = Tm + off_m + rng.normal(0.0, NOISE_RMS_K, Tm.size)
    Ti = Ti + off_i + rng.normal(0.0, NOISE_RMS_K, Ti.size)
    To = To + off_o + rng.normal(0.0, NOISE_RMS_K, To.size)
    Tp = Tp + rng.normal(0.0, PLATE_NOISE_RMS_K, Tp.size)

    header = ["time_s", "T_mean_C", "T_inner_C", "T_outer_C", "T_plate_rtd_C"]
    rows = [[f"{a:.2f}", f"{b:.3f}", f"{c:.3f}", f"{d:.3f}", f"{e:.3f}"]
            for a, b, c, d, e in zip(t, Tm, Ti, To, Tp)]
    return header, rows


def emit_truth(path):
    return fleet.emit_truth(path)


if __name__ == "__main__":
    print(json.dumps({n: _ROWS[n]["_alpha"] for n in _ROWS}, indent=2))
