"""Seeded fleet generator for the commissioning-bench design.

Sixteen newly installed chill stations. Each carries incoming-inspection metrology that
is free to read: the two zone standoffs, the plate surface roughness Ra, the plate's
passivation lot, and that lot's recorded bath temperature. None carries thermal data --
the agent buys that from the bench, one run at a time, out of a fixed budget of eight.

SEALED STRUCTURE (never stated anywhere the agent can see):

    alpha_i = A0 + B * (Ra_i - RA_REF) + LOT_SLOPE * (min(T_bath_i, T_KNEE) - T_REF) + eps_i

Thermal accommodation rises with surface roughness, and falls with passivation bath
temperature up to a knee, above which the passivation layer has saturated and further
bath temperature changes nothing. All three inputs are in the inspection report. The
relation is not, and neither is its shape.

WHY THIS SHAPE. The previous version of this fleet had three lots with a fixed offset
each. Eight runs could sample every lot, a lot-intercept model then needed no
extrapolation at all, and the platform's easiness screen solved it three times out of
three. Here:

    * sixteen stations come from TWELVE lots, so a lot-intercept model cannot be
      fitted from eight runs: at least four lots are never measured, and their
      stations have no prediction;
    * the bath temperature is a continuous lot attribute that DOES predict the lot
      effect -- but through a saturating relation, a short steep ramp below the knee
      and a long flat plateau above it, which is precisely the shape a straight line
      or a low-order polynomial cannot follow and a hinge can;
    * the dwell allowance is 8%. Because the optimum dwell does not depend on the
      coefficient at all (the gap conductance depends on pressure and coefficient only
      through their ratio), the allowance acts purely as a tolerance on the
      coefficient: about +/-7-9% at 8% (authoring/evidence/allowance_window.txt),
      against about +/-24% at the 20% the previous version used. That is the scale at
      which an eight-run campaign's prediction errors actually lie, so where the
      campaign spends its runs, and what the covariate model is fitted to, decide
      the outcome.

Sized by Monte Carlo over campaigns and redrawn fleets (authoring/evidence/
design_mc.txt): lot intercepts, a straight line and a quadratic in bath temperature
essentially never clear the gate; a hinge in the accommodation coefficient clears
about 90% of redrawn fleets.

Realised per-station scatter EPS_RMS is the part no model explains, and sets the
floor on every honest hedge.

SEED: 20260919, fixed.
"""
import json
import os

import numpy as np

# The shipped instance is SEED 20260919. The override exists so the multi-seed
# calibration in authoring/evidence/ can redraw the instance without editing this
# file; with the variable unset the generator is byte-identical to the shipped data.
SEED = int(os.environ.get("FLEET_SEED") or "20260919")

A0 = 0.46          # sealed
B = 0.115          # sealed, per micrometre of Ra
RA_REF = 0.80      # micrometres

LOT_SLOPE = -0.030 # sealed, per degree C of bath temperature, below the knee
T_REF = 44.0       # degrees C, where the lot term is zero
T_KNEE = 48.0      # sealed: above this the passivation layer is saturated
EPS_RMS = 0.010    # sealed, station-to-station scatter the model cannot explain

BUDGET_RUNS = 8
MAX_RUN_S = 30.0

SPEC = {
    "target_mean_temperature_C": 50.0,
    "max_zone_difference_K": 25.0,
    "dwell_budget_fraction": 0.08,
    "dwell_budget_scope": "per station",
    "he_pressure_min_torr": 3.0,
    "he_pressure_max_torr": 60.0,
    "min_stations_commissioned": 15,
}

# Twelve passivation lots. Four of them supplied two plates; the rest one each. The
# bath temperature is the lot's process record and is copied onto each plate's
# traveller, which is where the inspection report picks it up.
LOTS = {
    "L01": 40.0, "L02": 42.0, "L03": 44.0, "L04": 46.0, "L05": 48.0, "L06": 50.0,
    "L07": 52.0, "L08": 54.0, "L09": 56.0, "L10": 58.0, "L11": 61.0, "L12": 64.0,
}

# name, inner standoff um, outer standoff um, Ra um, lot, incoming C, setpoint C
FLEET = [
    ("S01", 120.0, 250.0, 0.42, "L04", 250.0, 20.0),
    ("S02", 150.0, 300.0, 1.18, "L10", 265.0, 18.0),
    ("S03", 170.0, 380.0, 0.61, "L02", 240.0, 22.0),
    ("S04", 110.0, 250.0, 1.34, "L08", 258.0, 20.0),
    ("S05", 180.0, 350.0, 0.29, "L05", 245.0, 19.0),
    ("S06", 140.0, 320.0, 0.95, "L12", 270.0, 24.0),
    ("S07", 130.0, 300.0, 0.74, "L01", 235.0, 21.0),
    ("S08", 200.0, 400.0, 1.07, "L05", 255.0, 20.0),
    ("S09", 160.0, 330.0, 0.35, "L06", 262.0, 19.0),
    ("S10", 125.0, 270.0, 0.88, "L07", 248.0, 23.0),
    ("S11", 190.0, 360.0, 1.26, "L03", 252.0, 20.0),
    ("S12", 145.0, 310.0, 0.53, "L07", 268.0, 21.0),
    ("S13", 135.0, 290.0, 0.66, "L06", 258.0, 21.0),
    ("S14", 175.0, 345.0, 1.12, "L09", 246.0, 20.0),
    ("S15", 155.0, 325.0, 0.47, "L02", 263.0, 22.0),
    ("S16", 115.0, 260.0, 0.99, "L11", 250.0, 19.0),
]


def lot_term(t_bath):
    """The sealed lot effect: linear in bath temperature up to the knee, flat above."""
    return LOT_SLOPE * (min(t_bath, T_KNEE) - T_REF)


def build():
    rng = np.random.default_rng(SEED)
    rows = []
    for name, d_in, d_out, ra, lot, T0, Tsp in FLEET:
        t_bath = LOTS[lot]
        alpha = A0 + B * (ra - RA_REF) + lot_term(t_bath) + rng.normal(0.0, EPS_RMS)
        rows.append({
            "station": name,
            "inner_standoff_um": d_in,
            "outer_standoff_um": d_out,
            "plate_roughness_Ra_um": ra,
            "passivation_lot": lot,
            "passivation_bath_C": t_bath,
            "incoming_temperature_C": T0,
            "plate_setpoint_C": Tsp,
            "_alpha": round(float(alpha), 6),
        })
    return rows


def emit(outdir):
    rows = build()
    os.makedirs(outdir, exist_ok=True)
    public = {
        "description": "Newly installed vacuum chill stations. Zone standoffs from the "
                       "capacitance gauge at incoming inspection, gauge uncertainty "
                       "1.5 um. Plate surface roughness from the same inspection. "
                       "Passivation lot and that lot's bath temperature from the "
                       "plate traveller. The chiller module is the same part number "
                       "across the fleet. No thermal data: the bench is the only "
                       "source of that.",
        "zone_split_radius_mm": 75.0,
        "stations": [{k: v for k, v in r.items() if not k.startswith("_")}
                     for r in rows],
    }
    with open(os.path.join(outdir, "stations.json"), "w") as f:
        json.dump(public, f, indent=2)
    with open(os.path.join(outdir, "spec.json"), "w") as f:
        json.dump(SPEC, f, indent=2)
    with open(os.path.join(outdir, "wafer.json"), "w") as f:
        json.dump({
            "description": "Test wafer and chamber properties, measured or datasheet.",
            "diameter_mm": 300.0,
            "thickness_um": 775.0,
            "density_kg_m3": 2329.0,
            "specific_heat_J_kgK": "703 + 0.28*(T[K] - 300)",
            "thermal_conductivity_W_mK": 100.0,
            "top_face_emissivity": 0.70,
            "chamber_wall_temperature_C": 25.0,
            "backside_gas": "helium",
        }, f, indent=2)
    return rows


def emit_truth(path, rows=None):
    rows = rows or build()
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump({
            "note": "Sealed fleet definition. No precomputed answers; the per-station "
                    "optimum is re-derived from the physics module at grade time.",
            "spec": SPEC,
            "budget_runs": BUDGET_RUNS,
            "stations": rows,
        }, f, indent=2)
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit-data")
    ap.add_argument("--emit-truth")
    a = ap.parse_args()
    rows = build()
    if a.emit_data:
        emit(a.emit_data)
        print("data ->", a.emit_data)
    if a.emit_truth:
        print("truth ->", emit_truth(a.emit_truth, rows))
    for r in rows:
        print("  %s  Ra=%.2f  lot=%s  bath=%4.0f C  alpha=%.4f" %
              (r["station"], r["plate_roughness_Ra_um"], r["passivation_lot"],
               r["passivation_bath_C"], r["_alpha"]))
