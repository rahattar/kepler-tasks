"""Write the agent-visible data for v3 into $PUBLIC_DATA or ../public/data."""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path.insert(0, _os.path.join(_HERE, "..", "..", "tests"))
_sys.path.insert(0, _HERE)
import os, csv, json
import numpy as np
from world import build, SWITCH_DAY, EAST_STUCK
from zone import WEST, EAST
from chiller import cop, cap_kw, TS_MIN, TS_MAX
from instance import ISSUE, FC_LEN, LO_OCC, HI_OCC, ZONES
from sim import iso

HERE = os.path.dirname(os.path.abspath(__file__))


def main(seeds=None, out=None):
    out = out or os.environ.get("PUBLIC_DATA", os.path.join(HERE, "..", "..", "environment", "data"))
    os.makedirs(out, exist_ok=True)
    w = build(seeds=seeds)
    ep = w["ep_log"]
    with open(os.path.join(out, "trend_log.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        cols = ["time", "outdoor_temp_c", "facade_irradiance_west_w_m2", "facade_irradiance_east_w_m2",
                "doas_flow_fraction", "supply_setpoint_c", "supply_temp_c"]
        for z in ZONES:
            cols += [f"{z}_air_temp_c", f"{z}_slab_temp_c", f"{z}_return_temp_c", f"{z}_valve_command"]
        wr.writerow(cols)
        for i, (t, obs, sp, duty, X, last) in enumerate(w["log_rows"]):
            nxt = w["log_rows"][i + 1][1] if i + 1 < len(w["log_rows"]) else None
            if nxt is None:
                break
            # values measured at the end of interval t are the observation at t+1
            row = [obs["time"], f"{obs['outdoor_temp_c']:.2f}",
                   f"{nxt['facade_irradiance_w_m2']['west']:.1f}", f"{nxt['facade_irradiance_w_m2']['east']:.1f}",
                   f"{ep['sch']['doas'][t]:.2f}", f"{sp:.2f}", f"{nxt['supply_temp_c']:.2f}"]
            day = ep["d0"] + t // 96
            for z in ZONES:
                cmd = duty[z]
                if z == "east" and EAST_STUCK[0] <= day < EAST_STUCK[1]:
                    cmd = 1.0 if day < SWITCH_DAY else cmd   # BMS kept commanding the failed valve
                row += [f"{obs['zones'][z]['air_temp_c']:.2f}", f"{obs['zones'][z]['slab_temp_c']:.2f}",
                        f"{nxt['zones'][z]['return_temp_c']:.2f}", f"{cmd:.3f}"]
            wr.writerow(row)
    fc = w["fc_log"]
    with open(os.path.join(out, "forecast_archive.csv"), "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["issued", "valid_time", "outdoor_temp_c", "facade_irradiance_west_w_m2",
                     "facade_irradiance_east_w_m2"])
        for s in range(w["t_log0"], ep["n"], ISSUE):
            fo = fc.issue(s)
            for k in range(FC_LEN):
                if s + k >= ep["n"]:
                    break
                wr.writerow([iso(ep, s), iso(ep, s + k), f"{fo['Tout'][k]:.2f}", f"{fo['Iw'][k]:.1f}",
                             f"{fo['Ie'][k]:.1f}"])
    zone_common = {
        "floor_area_m2": 120.0, "depth_m": 6.0, "facade_length_m": 20.0, "clear_height_m": 2.9,
        "floor_to_floor_m": 3.6,
        "slab": {"system": "thermally activated building system (concrete core activation), cooling only",
                 "thickness_m": 0.26,
                 "concrete": {"conductivity_w_per_m_k": 1.8, "density_kg_per_m3": 2300, "specific_heat_j_per_kg_k": 900},
                 "pipes": {"material": "PE-Xa", "outer_diameter_mm": 20.0, "wall_thickness_mm": 2.0, "spacing_mm": 150,
                           "pipe_plane_above_soffit_m": 0.13},
                 "design_water_flow_kg_per_h_per_m2": 12.0,
                 "soffit": "exposed concrete, painted, no suspended ceiling or acoustic panels; emissivity 0.92",
                 "top_side": "raised access floor over a 150 mm unconditioned plenum; treated as adiabatic in the design calculation",
                 "embedded_sensor_above_soffit_m": 0.17},
        "envelope": {"facade_area_m2": 72.0, "window_to_wall_ratio": 0.55, "glazing_u_w_per_m2_k": 1.4,
                     "glazing_g_value": 0.25, "glazing": "double, solar-control coating",
                     "shading": "interior roller blinds in five bays, occupant-operated: occupants lower a bay when sun reaches their desks and reset the blinds when they arrive",
                     "opaque_u_w_per_m2_k": 0.35, "design_infiltration_ach": 0.1},
        "ventilation": {"system": "dedicated outdoor air system, sensible supply at 19 C, no recirculation",
                        "design_flow_l_per_s": 160.0,
                        "schedule": "full flow 06:00-19:00 on working days, 30 % of design flow at all other times"},
        "internal_gains": {"occupied": "working days 08:00-18:00", "design_occupied_w_per_m2": WEST["gain_occ"],
                           "lunch_hour_12_13_fraction_of_design": 0.8, "unoccupied_w_per_m2": WEST["gain_base"],
                           "radiant_fraction": 1 - WEST["conv_int"],
                           "note": "actual occupancy varies from day to day and is not metered"},
        "furnishings": "open-plan desks, storage and glazed partitions",
    }
    building = {
        "site": {"location": "Chicago, IL (O'Hare weather station)", "calendar": "working days are Monday-Friday except US federal holidays, when the building is closed"},
        "zones": {"west": dict(zone_common, facade_azimuth_deg=270, name="Level 3 west perimeter"),
                  "east": dict(zone_common, facade_azimuth_deg=90, name="Level 3 east perimeter")},
        "tabs_group": {
            "description": "both zones are served by one TABS manifold fed directly by a dedicated chiller; the chiller's leaving water is the slab supply for both zones",
            "zone_valves": "one on/off valve per zone; the BMS can hold each valve open for any whole number of minutes in a 15-minute interval (valve command = open fraction)",
            "sensors": "chiller leaving (supply) water temperature, and per zone: air temperature, embedded slab temperature, return water temperature; no flow meters",
            "balancing_note": "the commissioning report records both zones as balanced to design flow; they were not re-measured after the 2016 manifold replacement"},
    }
    json.dump(building, open(os.path.join(out, "building.json"), "w"), indent=2)
    Tq = np.arange(10, 41, 2.0); Sq = np.arange(TS_MIN, TS_MAX + 0.1, 1.0)
    chiller = {"type": "air-cooled chiller dedicated to the TABS group, variable leaving water temperature",
               "leaving_temp_setpoint_range_c": [TS_MIN, TS_MAX],
               "outdoor_temp_c": Tq.tolist(), "leaving_temp_c": Sq.tolist(),
               "cop": [[round(float(cop(s, T)), 3) for s in Sq] for T in Tq],
               "capacity_kw": [[round(float(cap_kw(s, T)), 3) for s in Sq] for T in Tq],
               "notes": ["COP is heat removed per unit of electrical input; tables are indexed [outdoor][leaving]; interpolate linearly",
                         "if the open valves call for more heat than the capacity, the leaving water temperature rises above its setpoint until supply matches demand"]}
    json.dump(chiller, open(os.path.join(out, "chiller.json"), "w"), indent=2)
    tariff = {"currency": "USD", "unit": "kWh electricity",
              "on_peak": {"days": "Monday-Friday except federal holidays", "hours": "12:00-19:00", "price": 0.18},
              "off_peak": {"price": 0.06, "applies": "all other times"}}
    json.dump(tariff, open(os.path.join(out, "tariff.json"), "w"), indent=2)
    comfort = {"occupied_hours": "working days 08:00-18:00", "applies_to": "each zone separately",
               "operative_temp_band_c": [LO_OCC, HI_OCC],
               "operative_temperature": "0.5 x air temperature + 0.5 x mean radiant temperature",
               "mean_radiant_temperature": "0.35 x soffit surface temperature + 0.12 x glazing inner surface temperature + 0.53 x mean temperature of the room's other surfaces and furnishings (view factors from the occupied zone)",
               "note": "no operative or globe temperature sensor is installed"}
    json.dump(comfort, open(os.path.join(out, "comfort.json"), "w"), indent=2)
    with open(os.path.join(out, "maintenance_log.txt"), "w") as f:
        f.write("2017-06-05 07:40  East zone TABS valve actuator not responding; valve found closed. Part ordered.\n")
        f.write("2017-06-09 17:10  East zone valve actuator replaced; valve strokes normally.\n")
        f.write("2017-06-17 00:00  TABS changed to night-only operation (valves open 20:00-07:00) to cut on-peak demand.\n")
    print("wrote", sorted(os.listdir(out)))


if __name__ == "__main__":
    main()
