#!/usr/bin/env python3
"""Writes unit 400's records from the sealed definition.

    python3 gen.py <output directory>

Observations (metered flows, logged travels, tested heads, measured temperatures) carry the scatter the instrument
schedule states, drawn from the seed in seed.json. Facts (dimensions, elevations, set pressures, orifice letters,
SIL ratings) are written exactly.
"""
import csv
import datetime as dt
import importlib.util
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import docs  # noqa: E402
import isim as S  # noqa: E402

DAY0 = dt.date(2026, 9, 25)
NDAYS = 42
TREND0 = dt.datetime(2026, 10, 20, 2, 0)
TREND_N = 48            # four readings a day for twelve days

# the unit's streams at the throughput it runs, kg/h, all metered by coriolis meters but the feed
STREAMS = dict(feed=15250.0, fuel=800.0, c2=2900.0, c3=4270.0, c4=3650.0, bottoms=3630.0,
               t401_reflux=3480.0, t402_feed=11550.0, t402_reflux=1570.0, t402_distillate=7920.0,
               c3_vapour=4878.0, t401_bypass=1735.0, t402_bypass=1176.0)


def wcsv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def wtext(path, text):
    with open(path, "w") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def steam_p_at(t_C):
    """Invert the steam table: the pressure whose saturation temperature is t_C."""
    rows = S.SAT["steam"]
    if t_C <= rows[0][1]:
        return rows[0][0]
    if t_C >= rows[-1][1]:
        return rows[-1][0]
    for a, b in zip(rows, rows[1:]):
        if a[1] <= t_C <= b[1]:
            return a[0] + (t_C - a[1]) / (b[1] - a[1]) * (b[0] - a[0])
    raise ValueError(t_C)


# --------------------------------------------------------------------------- the 2019 study
def study_model():
    """A copy of the sealed model set back to the plant as the 2019 study found it."""
    spec = importlib.util.spec_from_file_location("isim_2019", os.path.join(HERE, "isim.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.FEED_NOW = S.FEED_DESIGN
    m.COMP_LAST = dict(S.COMP_FIRST)
    m.RD_NOW = m.comp_mw(m.COMP_LAST) / m.MW_AIR
    for c in m.CV.values():
        c["actual"] = c["sheet"]
    m.reb_ua = lambda n: m.REB[n]["design_kw"] / (
        m.sat("steam", m.REB[n]["steam_barg"] + m.ATM, "t") - m.REB[n]["bot_normal_C"])
    m.PUMP["now_shutoff_m"] = m.PUMP["sheet_shutoff_m"]
    m.raised_now = lambda item: 0.0
    m.DRIVEN["K-901"]["supply"] = "essential"        # the air compressor stood on the essential supply then
    m.FLARE["tip_k"] = m.TIP_K_OLD                   # and the stack carried its original tip
    m.TIE_IN["PSV-407"] = m.TIE_IN_SHEET["PSV-407"]  # before the lateral was re-routed
    for v in ("V-403", "T-401"):
        m.VESSEL[v]["insul"]["fire_rated"] = False
    for it in m.ITEMS.values():
        it["set_now"] = it["set_reg"]
    m._TRUTH = None
    return m


def study_rows():
    m = study_model()
    out = []
    for c in m.CONTINGENCIES:
        parts = m.relieving_set(c)
        load = sum(w for w, _ in parts.values())
        out.append("| `%s` | %s | %.0f | %.2f |" % (
            c, " ".join(sorted(parts)) or "none", load, m.header_pressure(parts)))
    return "\n".join(out)


# --------------------------------------------------------------------------- the records
def operating_record(rng):
    """Daily record of the unit. Flow columns are what each meter indicates; the feed meter is FE-4011.

    Each flow column is scaled so that its mean over the record is exactly the stream it measures, and each steam
    column so that the mean of the coefficient-area it implies, day by day, is exactly the reboiler's. The record
    is therefore the unit at the throughput the sealed definition gives, read through the instruments.
    """
    n = NDAYS
    g = 1.0
    gs = []
    for _ in range(n):
        g = float(np.clip(1.0 + 0.65 * (g - 1.0) + rng.normal(0.0, 0.012), 0.94, 1.06))
        gs.append(g)
    dates = [(DAY0 + dt.timedelta(days=i)).isoformat() for i in range(n)]

    flows = {}
    for key in ("feed", "fuel", "c2", "c3", "c4", "bottoms", "t401_reflux", "t402_feed",
                "t402_reflux", "t402_distillate"):
        v = np.array([STREAMS[key] * gs[i] * rng.normal(1.0, 0.004) for i in range(n)])
        flows[key] = v * (STREAMS[key] / v.mean())
    shown_feed = flows["feed"] * math.sqrt(S.RD_CONFIG / S.RD_NOW)

    temps, press = {}, {}
    for key, nominal, sd in (("v401_temp_C", 38.0, 0.6), ("v402_temp_C", S.ITEMS["PSV-409"]["t_relief_C"], 0.6),
                             ("p401_temp_C", S.PUMP["temp_C"], 0.8)):
        v = np.array([nominal + rng.normal(0.0, sd) for _ in range(n)])
        temps[key] = v - v.mean() + nominal
    for vid, key, sd in (("PSV-401", "v401", 0.25), ("PSV-409", "v402", 0.10), ("PSV-403", "t401", 0.20),
                         ("PSV-406", "t402", 0.20), ("PSV-404", "v403", 0.15), ("PSV-408", "v404", 0.15),
                         ("PSV-407", "v405", 0.15), ("PSV-405", "p401_discharge", 0.30)):
        nominal = S.ITEMS[vid]["p_norm"]
        v = np.array([nominal + rng.normal(0.0, sd) for _ in range(n)])
        press[key] = v - v.mean() + nominal

    steam = {}
    for reb, prefix in (("E-403", "t401"), ("E-406", "t402")):
        r = S.REB[reb]
        ua = S.reb_ua(reb)
        ts_nom = S.sat("steam", r["steam_barg"] + S.ATM, "t")
        t_bot = np.array([r["bot_normal_C"] + rng.normal(0.0, 0.4) for _ in range(n)])
        t_bot = t_bot - t_bot.mean() + r["bot_normal_C"]
        p_shown, w_shown, implied = [], [], []
        for i in range(n):
            ts_day = r["bot_normal_C"] + (ts_nom - r["bot_normal_C"]) * gs[i]
            p_true = steam_p_at(ts_day)
            q = ua * (ts_day - t_bot[i])
            p_rd = round(p_true - S.ATM + float(rng.normal(0.0, 0.12)), 2)
            w = q * 3600.0 / S.sat("steam", p_true, "latent") * float(rng.normal(1.0, 0.008))
            p_shown.append(p_rd)
            w_shown.append(w)
            dts = S.sat("steam", p_rd + S.ATM, "t") - t_bot[i]
            implied.append(w * S.sat("steam", p_rd + S.ATM, "latent") / 3600.0 / dts)
        scale = ua / (sum(implied) / n)
        steam[reb] = (p_shown, [w * scale for w in w_shown], t_bot)

    rows = []
    for i in range(n):
        row = [dates[i], round(shown_feed[i], 0)]
        for k in ("fuel", "c2", "c3", "c4", "bottoms"):
            row.append(round(flows[k][i], 0))
        row += [round(press["v401"][i], 2), round(temps["v401_temp_C"][i], 1),
                round(press["v402"][i], 2), round(temps["v402_temp_C"][i], 1)]
        for reb, prefix in (("E-403", "t401"), ("E-406", "t402")):
            p_shown, w_shown, t_bot = steam[reb]
            row += [round(press[prefix][i], 2), round(t_bot[i], 1),
                    round(p_shown[i], 2), round(w_shown[i], 0)]
        row += [round(flows["t401_reflux"][i], 0), round(flows["t402_feed"][i], 0),
                round(flows["t402_reflux"][i], 0), round(flows["t402_distillate"][i], 0),
                round(press["v403"][i], 2), round(press["v404"][i], 2), round(press["v405"][i], 2),
                round(press["p401_discharge"][i], 2), round(temps["p401_temp_C"][i], 1)]
        rows.append(row)
    header = ["date", "fe_4011_feed_kgh", "fe_4021_fuel_gas_kgh", "fe_4034_ethane_kgh",
              "fe_4072_propane_kgh", "fe_4038_butane_kgh", "fe_4051_bottoms_kgh",
              "v401_pressure_barg", "v401_temp_C", "v402_pressure_barg", "v402_temp_C",
              "t401_pressure_barg", "t401_bottoms_C", "e403_steam_barg", "e403_steam_kgh",
              "t402_pressure_barg", "t402_bottoms_C", "e406_steam_barg", "e406_steam_kgh",
              "fe_4033_t401_reflux_kgh", "fe_4035_t402_feed_kgh", "fe_4036_t402_reflux_kgh",
              "fe_4037_t402_distillate_kgh", "v403_pressure_barg", "v404_pressure_barg",
              "v405_pressure_barg", "p401_discharge_barg", "p401_temp_C"]
    return header, rows, gs


def travel_for(tag, w_true, p_up, p_dn, t_up):
    """The travel at which the valve as it is passes w_true at those conditions."""
    c = S.CV[tag]
    st = c["stream"]
    if st == "feed_gas":
        mw, k, z = S.feed_mw(), S.gas(st, p_up, "k"), S.gas(st, p_up, "z")
        t_K = t_up + 273.15
    else:
        mw, k, z = S.sat(st, p_up, "mw"), S.sat(st, p_up, "k"), S.sat(st, p_up, "z")
        t_K = S.sat(st, p_up, "t") + 273.15
    unit = S.valve_flow(1.0, c["xt"], c["fp"], k, p_up, p_dn, S.gas_density(p_up, t_K, mw, z))
    if unit <= 0.0:
        return None
    return 1.0 + math.log((w_true / unit) / (c["actual"] / 1.156)) / math.log(c["r"])


def control_valve_trend(rng, gs):
    """Four readings a day for twelve days on each of the unit's five pressure control valves. The feed and fuel
    gas valves follow the unit's throughput on the day; the bypass and propane vapour valves have their own.
    """
    plan = {"PV-4001": ("feed", True), "PV-4021": ("fuel", True), "PV-4031": ("t401_bypass", False),
            "PV-4061": ("t402_bypass", False), "PV-4071": ("c3_vapour", False)}
    day0 = (TREND0.date() - DAY0).days
    rows = []
    for tag, (stream, tied) in plan.items():
        c = S.CV[tag]
        g = 1.0
        for i in range(TREND_N):
            if tied:
                g = gs[min(day0 + i // 4, len(gs) - 1)]
            else:
                g = float(np.clip(1.0 + 0.7 * (g - 1.0) + rng.normal(0.0, 0.030), 0.86, 1.14))
            ts = TREND0 + dt.timedelta(hours=6 * i)
            p_up = c["p_up"] * rng.normal(1.0, 0.002)
            p_dn = c["p_dn"] * rng.normal(1.0, 0.002)
            t_up = c["t_up"] + float(rng.normal(0.0, 0.5))
            w_true = STREAMS[stream] * g
            h = travel_for(tag, w_true, p_up, p_dn, t_up)
            if h is None or not 0.12 <= h <= 0.96:
                continue
            w_shown = S.indicated(c["meter"], w_true) * rng.normal(1.0, 0.005)
            rows.append([tag, ts.strftime("%Y-%m-%d %H:%M"),
                         round(100.0 * h + float(rng.normal(0.0, 0.30)), 2),
                         round(p_up, 3), round(p_dn, 3), round(t_up, 1), round(w_shown, 1)])
    header = ["tag", "timestamp", "travel_pct", "upstream_bara", "downstream_bara",
              "upstream_temp_C", "flow_kgh"]
    return header, rows


def pump_tests(rng):
    rows = []
    tests = [("2019-05-14", S.PUMP["sheet_shutoff_m"], "works performance test, new pump"),
             ("2022-06-02", 585.0, "routine performance test"),
             ("2024-07-19", 582.0, "performance test after the unit modification")]
    for date, shut, note in tests:
        for q in (0.0, 48.0, 96.0, 120.0):
            rows.append([date, "P-401", round(q, 1),
                         round(S.pump_head(shut, q) + float(rng.normal(0.0, 0.8)), 1), 2975, note])
    return ["test_date", "pump", "flow_m3h", "head_m", "speed_rpm", "note"], rows


def gas_analyses(rng):
    rows = []
    dates = [dt.date(2019, 1, 11) + dt.timedelta(days=int(round(i * 2846 / 10))) for i in range(11)]
    keys = ("n2", "co2", "c1", "c2", "c3", "ic4", "nc4", "c5plus")
    for j, d in enumerate(dates):
        f = j / (len(dates) - 1.0)
        comp = {}
        for k in keys:
            v = S.COMP_FIRST[k] + f * (S.COMP_LAST[k] - S.COMP_FIRST[k])
            if j not in (0, len(dates) - 1):
                v *= rng.normal(1.0, 0.012)
            comp[k] = v
        tot = sum(comp.values())
        comp = {k: comp[k] / tot for k in keys}
        if j in (0, len(dates) - 1):
            src = S.COMP_FIRST if j == 0 else S.COMP_LAST
            comp = dict(src)
        rows.append([d.isoformat()] + ["%.4f" % comp[k] for k in keys])
    return ["sample_date"] + list(keys), rows


def main(out, seed=None):
    if seed is None:
        seed = json.load(open(os.path.join(HERE, "seed.json")))["seed"]
    rng = np.random.default_rng([seed, 1])
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)

    wtext(os.path.join(out, "docs", "standard.md"), docs.STANDARD)
    wtext(os.path.join(out, "docs", "unit_400.md"), docs.UNIT)
    wtext(os.path.join(out, "docs", "vessel_data.md"), docs.VESSELS)
    wtext(os.path.join(out, "docs", "flare_system.md"), docs.FLARE_SYSTEM)
    wtext(os.path.join(out, "docs", "flare_load_study_2019.md"), docs.STUDY.format(rows=study_rows(), tip_k_old="%.2f" % S.TIP_K_OLD))
    wtext(os.path.join(out, "docs", "field_testing.md"), docs.FIELD.format(budget=S.BUDGET))

    # ---- the relief valve register, as issued with the plant
    rows = []
    for vid in S.IDS:
        it = S.ITEMS[vid]
        rows.append([vid, it["item"], it["fluid"], "%.0f" % it["mawp"], "%.1f" % it["set_reg"],
                     S.FIRE_ZONE.get(it["item"], ""),
                     "balanced bellows" if S.BELLOWS[vid] else "conventional",
                     "main flare header", " ".join(it["cases"])])
    wcsv(os.path.join(out, "relief_valve_register.csv"),
         ["valve", "protected_item", "relieving_fluid", "mawp_barg", "set_pressure_barg",
          "fire_zone", "bonnet", "discharges_to", "causes_admitted"], rows)

    # ---- the shop record of every overhaul
    hist_notes = [
        ["PSV-401", "2023-05-11", "overhaul and test", "popped at 62.4 barg before stripping"],
        ["PSV-401", "2026-04-22", "overhaul and test", "nozzle and disc lapped, spring reset"],
        ["PSV-402", "2024-09-30", "overhaul and test", "routine"],
        ["PSV-403", "2023-11-07", "overhaul and test", "routine"],
        ["PSV-403", "2026-05-19", "overhaul and test", "guide and spindle renewed"],
        ["PSV-404", "2021-08-16", "overhaul and test", "nozzle and disc lapped"],
        ["PSV-404", "2025-10-02", "overhaul and test", "routine"],
        ["PSV-405", "2024-03-25", "overhaul and test", "routine"],
        ["PSV-406", "2025-02-13", "overhaul and test", "routine"],
        ["PSV-407", "2025-04-18", "overhaul and test", "nozzle found cut by debris and replaced"],
        ["PSV-408", "2024-11-21", "overhaul and test", "routine"],
        ["PSV-409", "2022-07-04", "overhaul and test", "routine"],
        ["PSV-409", "2026-03-09", "reset in situ", "set pressure lowered on instruction 400-EI-0318"],
        ["PSV-403", "2026-06-14", "reset in situ",
         "set pressure lowered on instruction 400-EI-0327 after the T-401 relief review"],
    ]
    latest = {}
    for vid, date, _, _ in hist_notes:
        latest[vid] = max(latest.get(vid, ""), date)
    hist = []
    for vid, date, work, note in hist_notes:
        it = S.ITEMS[vid]
        setp = it["set_now"] if date == latest[vid] else it["set_reg"]
        hist.append([vid, date, work, "%.1f" % setp, note])
    wcsv(os.path.join(out, "valve_history.csv"),
         ["valve", "work_date", "work", "as_left_set_barg", "note"],
         sorted(hist, key=lambda r: (r[0], r[1])))

    # ---- control valve data sheets, with the position each valve takes when it loses air
    rows = []
    src = {"PV-4001": "feed gas from the pipeline into V-401",
           "PV-4021": "fuel gas let-down from V-401 into V-402",
           "PV-4031": "T-401 pressure, condenser bypass",
           "PV-4061": "T-402 pressure, condenser bypass",
           "PV-4071": "propane vapour from T-403 into V-405"}
    for tag, c in S.CV.items():
        rows.append([tag, src[tag], "equal percentage", "%.0f" % c["r"], "%.1f" % c["sheet"],
                     "%.2f" % c["xt"], "%.2f" % c["fp"], c["meter"], S.FAIL_POSITION[tag]])
    rows.append(["FV-4051", "P-401 discharge flow to storage", "linear", "30", "110.0",
                 "0.64", "1.00", "FE-4051", S.FAIL_POSITION["FV-4051"]])
    wcsv(os.path.join(out, "control_valve_data.csv"),
         ["tag", "service", "characteristic", "rangeability", "data_sheet_cv_rated",
          "xt", "fp", "flow_measurement", "position_on_air_failure"], rows)

    # ---- the unit's fire zones
    wcsv(os.path.join(out, "fire_zones.csv"), ["zone", "items", "description"],
         [["A", " ".join(sorted(k for k, v in S.FIRE_ZONE.items() if v == "A")),
           "inlet separation and fuel gas, west of the pipe rack"],
          ["B", " ".join(sorted(k for k, v in S.FIRE_ZONE.items() if v == "B")),
           "deethaniser and its overhead system"],
          ["C", " ".join(sorted(k for k, v in S.FIRE_ZONE.items() if v == "C")),
           "debutaniser, its overhead system and the product drum"]])

    # ---- what drives the unit, and which supply each driver stands on
    label = {"E-404": "T-401 overhead condenser, water cooled, two circulating pumps",
             "E-407": "T-402 overhead condenser, air cooled, four fans",
             "P-401": "T-402 bottoms product pump",
             "K-901": "instrument air compressor in unit 900, with a receiver at the unit limit",
             "SIS": "safety instrumented system logic and field devices"}
    rows = []
    for tag in ("E-404", "E-407", "K-901", "P-401", "SIS"):
        d = S.DRIVEN[tag]
        rows.append([tag, label[tag], d["serves"], d["medium"] or "none",
                     "motor" if tag != "SIS" else "none", d["supply"]])
    wcsv(os.path.join(out, "drive_schedule.csv"),
         ["tag", "description", "serves", "cooling_medium", "driver", "electrical_supply"], rows)

    h, r, gs = operating_record(rng)
    wcsv(os.path.join(out, "operating_record.csv"), h, r)
    h2, r2 = control_valve_trend(rng, gs)
    wcsv(os.path.join(out, "control_valve_trend.csv"), h2, r2)
    h, r = pump_tests(rng)
    wcsv(os.path.join(out, "pump_test_record.csv"), h, r)
    h, r = gas_analyses(rng)
    wcsv(os.path.join(out, "gas_analysis.csv"), h, r)

    # ---- instruments
    inst = [
        ["FE-4011", "unit feed gas", "orifice plate with flow computer", "0 to 25000 kg/h",
         "fixed relative density %.3f entered at commissioning" % S.RD_CONFIG, "2026-02-17", "1.0"],
        ["FE-4021", "fuel gas to V-402", "coriolis", "0 to 3000 kg/h", "measured", "2026-02-17", "0.5"],
        ["FE-4033", "T-401 reflux", "coriolis", "0 to 8000 kg/h", "measured", "2026-01-29", "0.5"],
        ["FE-4034", "ethane product", "coriolis", "0 to 6000 kg/h", "measured", "2026-01-29", "0.5"],
        ["FE-4035", "T-402 feed", "coriolis", "0 to 20000 kg/h", "measured", "2026-03-04", "0.5"],
        ["FE-4036", "T-402 reflux", "coriolis", "0 to 4000 kg/h", "measured", "2026-03-04", "0.5"],
        ["FE-4037", "T-402 overhead product", "coriolis", "0 to 14000 kg/h", "measured", "2026-03-04", "0.5"],
        ["FE-4038", "butane product", "coriolis", "0 to 8000 kg/h", "measured", "2026-01-29", "0.5"],
        ["FE-4051", "bottoms product", "coriolis", "0 to 8000 kg/h", "measured", "2026-02-02", "0.5"],
        ["FE-4071", "propane vapour to V-405", "coriolis", "0 to 9000 kg/h", "measured", "2026-02-02", "0.5"],
        ["FE-4072", "propane product", "coriolis", "0 to 8000 kg/h", "measured", "2026-01-29", "0.5"],
        ["PT-4012", "V-401 pressure, control", "pressure transmitter", "0 to 100 barg", "", "2026-04-20", "0.3"],
        ["PT-4013", "V-401 pressure, protection", "pressure transmitter", "0 to 100 barg", "", "2026-04-20", "0.3"],
        ["PT-4021", "V-402 pressure, control", "pressure transmitter", "0 to 25 barg", "", "2026-04-20", "0.3"],
        ["PT-4022", "V-402 pressure, protection", "pressure transmitter", "0 to 25 barg", "", "2026-04-20", "0.3"],
        ["PT-4031", "T-401 pressure, control", "pressure transmitter", "0 to 50 barg", "", "2026-01-29", "0.3"],
        ["PT-4061", "T-402 pressure, control", "pressure transmitter", "0 to 25 barg", "", "2026-03-04", "0.3"],
        ["PT-4063", "T-402 pressure, protection", "pressure transmitter", "0 to 25 barg", "", "2026-03-04", "0.3"],
        ["PT-4071", "V-405 pressure, control", "pressure transmitter", "0 to 25 barg", "", "2026-02-02", "0.3"],
        ["TI-4014", "V-401 gas temperature", "resistance thermometer", "0 to 120 C", "", "2026-04-20", "0.5"],
        ["TI-4034", "T-401 bottoms temperature", "resistance thermometer", "0 to 200 C", "", "2026-01-29", "0.5"],
        ["TI-4064", "T-402 bottoms temperature", "resistance thermometer", "0 to 250 C", "", "2026-03-04", "0.5"],
    ]
    wcsv(os.path.join(out, "instrument_schedule.csv"),
         ["tag", "service", "type", "range", "flow_computer_density", "last_calibration",
          "stated_uncertainty_pct"], inst)

    # ---- the safety instrumented system
    rows = []
    desc = {"SIF-4011": "closes the feed shutdown valve XV-4013 on high V-401 pressure",
            "SIF-4031": "closes the T-401 feed on high T-401 pressure",
            "SIF-4061": "closes the T-402 feed and the E-406 steam on high T-402 pressure",
            "SIF-4091": "closes PV-4021 on high V-402 pressure"}
    prevents = {"SIF-4011": "V-401 control valve failure", "SIF-4031": "T-401 loss of overhead cooling",
                "SIF-4061": "T-402 loss of overhead cooling", "SIF-4091": "V-402 control valve failure"}
    final = {"SIF-4011": "XV-4013", "SIF-4031": "XV-4032", "SIF-4061": "XV-4062 and XV-4065",
             "SIF-4091": "PV-4021"}
    test = {"SIF-4011": "2026-06-08", "SIF-4031": "2026-05-26", "SIF-4061": "2026-07-14",
            "SIF-4091": "2025-11-30"}
    for name, s in sorted(S.SIF.items()):
        rows.append([name, desc[name], prevents[name], "SIL %d" % s["sil"], s["proof"],
                     s["initiator"], final[name], test[name]])
    wcsv(os.path.join(out, "sis_register.csv"),
         ["sif", "description", "contingency_prevented", "sil", "proof_test_interval_months",
          "initiating_element", "final_elements", "last_proof_test"], rows)

    # ---- exchangers
    e = S.EXCH["E-402"]
    wcsv(os.path.join(out, "exchanger_data.csv"),
         ["item", "service", "shell_side", "shell_inlet_temp_C", "tube_side", "tube_inlet_temp_C",
          "shell_design_barg", "tube_design_barg", "tubes", "tube_od_mm", "tube_wall_mm", "tube_bore_mm",
          "surface_m2", "design_duty_kw", "design_basis"],
         [["E-402", "feed/bottoms exchanger", "bottoms product", "%.0f" % S.PUMP["temp_C"],
           "feed liquid", "%.0f" % e["hi_temp_C"],
           "%.0f" % e["shell_mawp"], "%.0f" % e["hi_barg"], e["tubes"], "19.05", "1.67",
           "%.2f" % e["tube_id_mm"], "212", "1980", "unit feed 310 t/d"],
          ["E-403", "T-401 reboiler", "T-401 bottoms", "78", "13 barg steam", "195", "31", "15",
           "284", "25.40", "2.11", "21.18", "268", "%.0f" % S.REB["E-403"]["design_kw"],
           "unit feed 310 t/d"],
          ["E-406", "T-402 reboiler", "T-402 bottoms", "79", "13 barg steam", "195", "18", "15",
           "396", "25.40", "2.00", "21.40", "402", "%.0f" % S.REB["E-406"]["design_kw"],
           "unit feed 310 t/d"]])

    # ---- fluid properties
    rows = []
    for stream in sorted(S.SAT):
        for r in S.SAT[stream]:
            rows.append([stream, "%.1f" % r[0], "%.0f" % r[1], "%.0f" % r[2], "%.2f" % r[3],
                         "%.3f" % r[4], "%.3f" % r[5], "%.0f" % r[6], "%.2f" % r[7]])
    wcsv(os.path.join(out, "fluid_properties.csv"),
         ["stream", "pressure_bara", "saturation_temp_C", "latent_heat_kj_per_kg", "vapour_molar_mass",
          "vapour_k", "vapour_z", "liquid_density_kg_per_m3", "liquid_viscosity_cp"], rows)
    rows = [["feed_gas", "%.1f" % r[0], "%.3f" % r[1], "%.3f" % r[2]] for r in S.GAS["feed_gas"]]
    wcsv(os.path.join(out, "gas_properties.csv"), ["stream", "pressure_bara", "k", "z"], rows)
    rows = []
    for stream in sorted(S.LIQ):
        for r in S.LIQ[stream]:
            rows.append([stream, "%.0f" % r[0], "%.0f" % r[1], "%.2f" % r[2], "%.5f" % r[3], "%.2f" % r[4]])
    wcsv(os.path.join(out, "liquid_properties.csv"),
         ["stream", "temperature_C", "density_kg_per_m3", "viscosity_cp",
          "cubical_expansion_per_C", "specific_heat_kj_per_kg_K"], rows)

    wcsv(os.path.join(out, "pump_data.csv"),
         ["pump", "service", "pumped_fluid", "temperature_C", "rated_flow_m3h", "rated_head_m",
          "data_sheet_shutoff_head_m", "speed_rpm", "normal_suction_pressure_barg", "stages"],
         [["P-401", "T-402 bottoms product to storage", "bottoms_product", "%.0f" % S.PUMP["temp_C"],
           "%.0f" % S.PUMP["rated_m3h"], "%.0f" % S.PUMP["rated_head_m"],
           "%.0f" % S.PUMP["sheet_shutoff_m"], 2975, "%.1f" % S.PUMP["suction_barg"], 6]])

    wcsv(os.path.join(out, "component_properties.csv"),
         ["component", "name", "molar_mass_kg_per_kmol"],
         [[c, n, "%.3f" % S.COMP_M[c]] for c, n in
          (("n2", "nitrogen"), ("co2", "carbon dioxide"), ("c1", "methane"), ("c2", "ethane"),
           ("c3", "propane"), ("ic4", "iso-butane"), ("nc4", "n-butane"),
           ("c5plus", "pentanes and heavier, as n-pentane"))])

    wcsv(os.path.join(out, "flare_tie_ins.csv"),
         ["device", "protects", "isometric", "tie_in_m_from_stack_base"],
         [[v, S.ITEMS[v]["item"], iso, "%.0f" % S.TIE_IN_SHEET[v]]
          for v, iso in (("PSV-401", "400-ISO-0411"), ("PSV-402", "400-ISO-0411"),
                         ("PSV-403", "400-ISO-0412"), ("PSV-404", "400-ISO-0412"),
                         ("PSV-405", "400-ISO-0413"), ("PSV-406", "400-ISO-0413"),
                         ("PSV-407", "400-ISO-0414"), ("PSV-408", "400-ISO-0414"),
                         ("PSV-409", "400-ISO-0414"))])

    # ---- modifications and maintenance
    wcsv(os.path.join(out, "modification_register.csv"),
         ["number", "date", "description", "documents_revised"],
         [["MOD-2021-14", "2021-08-16", "PSV-404 uprated from a G to an H orifice after the review of the T-401 overhead system; inlet pipework unchanged",
           "relief valve register rev 3"],
          ["MOD-2024-07", "2024-06-28",
           "unit capacity increase to a nominal 360 t/d: new feed heater, larger feed pump impeller, "
           "T-402 re-set 0.90 m higher on an extended skirt to clear the new reboiler pipework",
           "process flow diagrams, P and I diagrams, isometrics, foundation drawings, vessel elevations "
           "sheet 4"],
          ["MOD-2025-02", "2025-03-11",
           "V-403 and T-401 insulation replaced with a fire-resistant system to specification S-1140",
           "insulation schedule, vessel data book insulation table"],
          ["MOD-2024-11", "2024-09-05",
           "unit 400 switchboard rebuilt: the K-901 instrument air compressor transferred from the essential "
           "supply to the normal supply, the safety instrumented system left on the essential supply",
           "single line diagrams, drive schedule"],
          ["MOD-2026-05", "2026-06-30",
           "low pressure flare header taken out of service and its devices tied into the main header",
           "flare system note issue 3, relief valve register"],
          ["MOD-2025-09", "2025-07-16",
           "flare stack tip replaced with a unit of the same bore from another vendor; no performance data "
           "supplied with it",
           "flare system note issue 3"],
          ["MOD-2026-09", "2026-09-24",
           "PSV-407 tail pipe re-routed onto the new V-405 relief lateral, moving its tie-in on the main "
           "header from 92 m to 206 m from the stack base; header itself unaltered",
           "isometric 400-ISO-0414 marked up, not yet re-issued"]])

    log = [
        ["2024-06-28", "T-402", "foundation and skirt extension completed; column re-set and re-levelled"],
        ["2024-07-19", "P-401", "performance test after the modification"],
        ["2024-09-30", "PSV-402", "overhaul; rupture disc renewed"],
        ["2024-11-21", "PSV-408", "overhaul"],
        ["2025-01-08", "E-402", "shell inspected; no retube required"],
        ["2025-02-13", "PSV-406", "overhaul"],
        ["2025-03-11", "V-403", "insulation renewed to specification S-1140; certificate FRC-2251 filed"],
        ["2025-03-14", "T-401", "insulation renewed to specification S-1140; certificate FRC-1987 filed"],
        ["2025-04-18", "PSV-407", "overhaul; nozzle replaced from stores"],
        ["2025-06-02", "PV-4031", "actuator diaphragm renewed; stroked and calibrated"],
        ["2025-08-19", "P-401", "mechanical seal renewed"],
        ["2026-07-28", "P-401",
         "rotating element renewed: impeller replaced with a trimmed spare to bring the absorbed power within "
         "the motor rating, wear rings and balance drum replaced; not performance tested"],
        ["2025-10-02", "PSV-404", "overhaul"],
        ["2025-11-30", "SIF-4091", "proof test"],
        ["2026-01-29", "unit 400", "instrument calibration round, T-401 section"],
        ["2026-02-02", "unit 400", "instrument calibration round, product section"],
        ["2026-02-17", "unit 400", "instrument calibration round, feed section"],
        ["2026-03-04", "unit 400", "instrument calibration round, T-402 section"],
        ["2026-03-09", "PSV-409", "set pressure reset in situ to instruction 400-EI-0318"],
        ["2026-04-20", "unit 400", "instrument calibration round, separator section"],
        ["2026-04-22", "PSV-401", "overhaul; nozzle and disc lapped"],
        ["2026-05-07", "PV-4001", "plug and seat ring replaced; valve stroked and the loop checked"],
        ["2026-05-19", "PSV-403", "overhaul; guide and spindle renewed"],
        ["2026-05-26", "SIF-4031", "proof test"],
        ["2026-06-08", "SIF-4011", "proof test"],
        ["2026-06-15", "PV-4071", "plug and seat ring replaced; valve stroked and the loop checked"],
        ["2026-07-02", "PV-4021", "plug and seat ring replaced; valve stroked and the loop checked"],
        ["2026-07-14", "SIF-4061", "proof test"],
        ["2026-09-03", "T-402", "tray 14 downcomer clamp replaced during a short shutdown"],
        ["2026-10-06", "E-403", "steam trap renewed"],
        ["2024-09-05", "K-901", "supply changed over during the switchboard rebuild; compressor restarted "
         "and the receiver proved"],
        ["2026-06-30", "flare system", "low pressure header blanked and its devices tied into the main header"],
    ]
    wcsv(os.path.join(out, "maintenance_log.csv"), ["date", "item", "work"], log)
    if os.environ.get("GEN_QUIET") != "1":
        print("wrote %d files to %s" % (len(os.listdir(out)) + len(os.listdir(os.path.join(out, "docs"))) - 1, out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "environment", "data"))
