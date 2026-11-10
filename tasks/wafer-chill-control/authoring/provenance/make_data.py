"""Seeded generator for wafer-chill-control. Disclosed; the verifier never runs it.

Writes the agent-visible data (inspection records, wafer and sensor sheet, production
specification, characterisation logs) and the sealed truth the verifier grades against
(station and film accommodation, the hidden wafer set). Every number in both comes from
the fixed seed below and the sealed plant in tests/plant.py; nothing is produced by
running the reference solution.

    python3 make_data.py --emit-data DIR     agent-visible files (environment/data)
    python3 make_data.py --emit-truth PATH   sealed truth (tests/truth.json)
    python3 make_data.py                     both, into the bundle

SEED: 20261003, fixed.
"""
import argparse
import csv
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import plant as pl  # noqa: E402

SEED = 20261003

# ---------------------------------------------------------------- sealed parameters
STATIONS = {
    # id: inner standoff um, outer standoff um, chiller setpoint C, plate accommodation
    "A": dict(inner_um=150.0, outer_um=300.0, setpoint_C=20.0, _alpha_plate=0.40),
    "B": dict(inner_um=120.0, outer_um=260.0, setpoint_C=18.0, _alpha_plate=0.33),
}
FILMS = {"bare": 0.36, "oxide": 0.29, "nitride": 0.45}   # wafer-side accommodation

SAG_RANGE_UM = (-50.0, 50.0)
T0_RANGE_C = (235.0, 265.0)
WAFERS_PER_STATION = 12
ALLOWANCE = 0.10

# characterisation: three films x three test-wafer sags per station, each run under a
# different command profile so the logs span the pressure range and its dynamics
CHAR_SAGS_UM = (-40.0, 0.0, 40.0)
CHAR_LEN_S = 20.0
TC_RMS = 0.20


def profile(kind, t):
    """Commanded pressure at time t for one of the characterisation profiles."""
    if kind == "const6":
        return 6.0
    if kind == "const14":
        return 14.0
    if kind == "const30":
        return 30.0
    if kind == "const55":
        return 55.0
    if kind == "step4to30":
        return 4.0 if t < 1.5 else 30.0
    if kind == "step45to8":
        return 45.0 if t < 2.0 else 8.0
    if kind == "ramp3to60":
        return min(60.0, 3.0 + 57.0 * t / 8.0)
    if kind == "stairs":
        return (5.0, 10.0, 20.0, 40.0)[min(3, int(t // 2.0))]
    if kind == "dip":
        return 3.0 if 3.0 <= t < 4.0 else 20.0
    raise ValueError(kind)


PROFILES = ["const6", "const14", "const30", "const55", "step4to30", "step45to8",
            "ramp3to60", "stairs", "dip"]


def wafer_for(station, film, sag_um, T0, n_rings=pl.N_RINGS):
    s = STATIONS[station]
    return pl.Wafer(s["inner_um"] * 1e-6, s["outer_um"] * 1e-6, s["setpoint_C"],
                    s["_alpha_plate"], FILMS[film], sag_um * 1e-6, T0, n_rings=n_rings)


def characterisation_run(station, film, sag_um, T0, kind, rng):
    """One instrumented test-wafer run, logged at the control rate."""
    w = wafer_for(station, film, sag_um, T0)
    Tw, Tp, P = w.landing()
    n_sub = int(round(pl.CTRL_DT / pl.DT))
    rows = []
    n = int(round(CHAR_LEN_S / pl.CTRL_DT))
    for k in range(n + 1):
        t = k * pl.CTRL_DT
        cmd = profile(kind, t)
        rd = w.reading(Tw, Tp, P, rng)
        ti, to = w.zone_means(Tw)
        tm = w.t_mean(Tw)
        rows.append([t, cmd, rd["pressure_torr"], rd["center_C"], rd["edge_C"],
                     rd["plate_C"],
                     float(ti[0]) + rng.normal(0.0, TC_RMS),
                     float(to[0]) + rng.normal(0.0, TC_RMS),
                     float(tm[0]) + rng.normal(0.0, TC_RMS)])
        if k == n:
            break
        for _ in range(n_sub):
            Tw, Tp, P = w.step(Tw, Tp, P, np.array([[cmd]]))
    return rows


HEADER = ["time_s", "pressure_cmd_torr", "pressure_torr", "center_spot_C", "edge_spot_C",
          "plate_rtd_C", "tc_inner_mean_C", "tc_outer_mean_C", "tc_mass_mean_C"]


def _csv(rows):
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(HEADER)
    for r in rows:
        wr.writerow(["%.1f" % r[0], "%.2f" % r[1], "%.3f" % r[2]] +
                    ["%.3f" % v for v in r[3:]])
    return buf.getvalue()


def build():
    """Returns (public files {relative path: text}, truth dict)."""
    rng = np.random.default_rng(SEED)
    files = {}

    # --- inspection records
    files["stations.json"] = json.dumps({
        "description": "Inspection records of the two chill stations. Zone standoffs from "
                       "the capacitance gauge, gauge uncertainty 1.5 um. Both stations use "
                       "the same chiller part.",
        "zone_split_radius_mm": pl.R_SPLIT * 1e3,
        "stations": [{"station": k, "inner_standoff_um": v["inner_um"],
                      "outer_standoff_um": v["outer_um"],
                      "plate_setpoint_C": v["setpoint_C"]} for k, v in STATIONS.items()],
    }, indent=2) + "\n"

    files["wafer.json"] = json.dumps({
        "description": "Wafer and chamber properties, measured or datasheet.",
        "diameter_mm": pl.D_WAFER * 1e3,
        "thickness_um": pl.T_WAFER * 1e6,
        "density_kg_m3": pl.RHO_SI,
        "specific_heat_J_kgK": "703 + 0.28*(T[K] - 300)",
        "thermal_conductivity_W_mK": pl.K_SI,
        "top_face_emissivity": pl.EMISSIVITY,
        "chamber_wall_temperature_C": round(pl.T_WALL - 273.15, 2),
        "backside_gas": "helium",
        "backside_films": list(FILMS),
    }, indent=2) + "\n"

    files["production.json"] = json.dumps({
        "description": "Production requirements and the wafer population the controller "
                       "must handle, in machine-readable form.",
        "stations": list(STATIONS),
        "control_period_s": pl.CTRL_DT,
        "pressure_command_min_torr": pl.P_MIN,
        "pressure_command_max_torr": pl.P_MAX,
        "chamber_pressure_at_landing_torr": pl.P_IDLE,
        "release_mass_mean_max_C": pl.T_TARGET,
        "zone_difference_max_K": pl.ZONE_CAP,
        "cycle_max_s": pl.T_CYCLE_MAX,
        "center_sag_range_um": list(SAG_RANGE_UM),
        "incoming_temperature_range_C": list(T0_RANGE_C),
        "backside_films": list(FILMS),
        "sensors": {
            "center_pyrometer_annulus_mm": [v * 1e3 for v in pl.SPOT_CENTER],
            "edge_pyrometer_annulus_mm": [v * 1e3 for v in pl.SPOT_EDGE],
            "plate_rtd": True,
            "chamber_manometer": True,
        },
        "hidden_wafers_per_station": WAFERS_PER_STATION,
        "cycle_allowance_fraction": ALLOWANCE,
    }, indent=2) + "\n"

    # --- characterisation logs
    index = []
    for si, station in enumerate(STATIONS):
        order = PROFILES[si * 4:] + PROFILES[:si * 4]      # a different pairing per station
        j = 0
        for film in FILMS:
            for sag in CHAR_SAGS_UM:
                T0 = float(np.round(rng.uniform(240.0, 260.0), 1))
                kind = order[j]
                j += 1
                rows = characterisation_run(station, film, sag, T0, kind, rng)
                name = "char_%s_%s_sag%+03d.csv" % (station, film, int(sag))
                files["characterization/" + name] = _csv(rows)
                index.append({"file": name, "station": station, "film": film,
                              "test_wafer_sag_um": sag,
                              "command_profile": kind})
    files["characterization/index.json"] = json.dumps({
        "description": "Instrumented test-wafer runs, logged at 10 Hz. Each test wafer "
                       "carries a thermocouple array; tc_* columns are its zone and mass "
                       "means. The other columns are the production sensors. Sag is the "
                       "test wafer's measured centre sag.",
        "columns": HEADER,
        "runs": index,
    }, indent=2) + "\n"

    # --- the hidden wafer set (sealed)
    wafers = []
    for station in STATIONS:
        n = WAFERS_PER_STATION
        # stratified over sag and incoming temperature, so both extremes are exercised
        sag_bins = (np.arange(n) + rng.uniform(0, 1, n)) / n
        t0_bins = (np.arange(n) + rng.uniform(0, 1, n)) / n
        rng.shuffle(t0_bins)
        films = [list(FILMS)[i % len(FILMS)] for i in range(n)]
        rng.shuffle(films)
        for i in range(n):
            sag = SAG_RANGE_UM[0] + (SAG_RANGE_UM[1] - SAG_RANGE_UM[0]) * sag_bins[i]
            T0 = T0_RANGE_C[0] + (T0_RANGE_C[1] - T0_RANGE_C[0]) * t0_bins[i]
            wafers.append({"id": "%s%02d" % (station, i + 1), "station": station,
                           "film": films[i], "_sag_um": round(float(sag), 2),
                           "_T0_C": round(float(T0), 2),
                           "_noise_seed": int(rng.integers(1, 2**31 - 1))})
    truth = {
        "seed": SEED,
        "allowance": ALLOWANCE,
        "stations": {k: dict(v) for k, v in STATIONS.items()},
        "films": {k: {"_alpha_wafer": v} for k, v in FILMS.items()},
        "wafers": wafers,
    }
    return files, truth


def emit_data(files, outdir):
    for rel, text in files.items():
        p = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)


def emit_truth(truth, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(truth, f, indent=1)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-data")
    ap.add_argument("--emit-truth")
    a = ap.parse_args()
    files, truth = build()
    if not a.emit_data and not a.emit_truth:
        a.emit_data = os.path.join(ROOT, "environment", "data")
        a.emit_truth = os.path.join(ROOT, "tests", "truth.json")
    if a.emit_data:
        emit_data(files, a.emit_data)
    if a.emit_truth:
        emit_truth(truth, a.emit_truth)


if __name__ == "__main__":
    main()
