"""Writes the agent-visible records and documents of the GT-1 performance test from gt.py.  python3 gen.py OUT_DIR"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

LOG = [
    ("2026-10-13 07:30", "GT-1 start"),
    ("2026-10-13 08:15", "GT-1 at base load"),
    ("2026-10-13 08:30", "Gas sample S1 drawn at the fuel skid sample point"),
    ("2026-10-13 09:00", "Run A1 start"),
    ("2026-10-13 10:00", "Run A1 end"),
    ("2026-10-13 10:15", "Gas sample S2 drawn"),
    ("2026-10-13 10:30", "Run A2 start"),
    ("2026-10-13 11:30", "Run A2 end"),
    ("2026-10-13 11:45", "Gas sample S3 drawn"),
    ("2026-10-13 15:00", "Test day 1 data acquisition stopped"),
    ("2026-10-14 06:00", "GT-1 shut down and cooled; offline compressor water wash (detergent, two rinses)"),
    ("2026-10-14 13:00", "Inlet filter final-stage cartridges replaced"),
    ("2026-10-14 15:30", "Met mast data logger replaced (like-for-like unit from stores); sensors unchanged"),
    ("2026-10-15 07:30", "GT-1 start"),
    ("2026-10-15 08:15", "GT-1 at base load"),
    ("2026-10-15 08:30", "Gas sample S4 drawn at the fuel skid sample point"),
    ("2026-10-15 09:00", "Run L1 start"),
    ("2026-10-15 10:00", "Run L1 end"),
    ("2026-10-15 10:15", "Gas sample S5 drawn"),
    ("2026-10-15 10:30", "Run L2 start"),
    ("2026-10-15 11:30", "Run L2 end"),
    ("2026-10-15 11:45", "Gas sample S6 drawn"),
    ("2026-10-15 13:00", "Run L3 start"),
    ("2026-10-15 14:00", "Run L3 end"),
    ("2026-10-15 15:00", "Test day 2 data acquisition stopped"),
]

TAGS = [
    ("time", "end of the 1-minute averaging interval, plant local time", ""),
    ("gen_mw_jt001", "generator active power, test wattmeter JT-001 (on the generator PT and CT secondaries, primary values as scaled in the meter)", "MW"),
    ("gen_mvar_jt001", "generator reactive power, JT-001", "Mvar"),
    ("freq_hz", "generator frequency", "Hz"),
] + [("cit_%d_c" % i, "compressor inlet temperature, RTD %d of the 8-point array in the inlet plenum" % i, "degC") for i in range(1, 9)] + [
    ("pdt101_filter_dp_kpa", "PDT-101, differential pressure across the inlet filter stages", "kPa"),
    ("pt102_inlet_total_kpa_abs", "PT-102, compressor inlet (bellmouth) total pressure", "kPa abs"),
    ("pdt201_exhaust_kpa_g", "PDT-201, turbine exhaust static pressure above atmosphere at the diffuser exit", "kPa g"),
    ("fuel_coriolis_kg_s", "FT-301, fuel gas Coriolis mass flowmeter", "kg/s"),
    ("te301_fuel_meter_c", "TE-301, fuel gas temperature at FT-301", "degC"),
    ("te305_fuel_skid_c", "TE-305, fuel gas temperature at the turbine fuel skid inlet (after the fuel heater)", "degC"),
    ("igv_deg", "compressor inlet guide vane angle", "deg"),
    ("texh_avg_c", "turbine exhaust temperature, average of the control thermocouples", "degC"),
    ("ttrf_c", "exhaust temperature control reference", "degC"),
]


def main(out):
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    das, dcs, gc, spot = gt.simulate()
    log = LOG + [(d + " 12:00", "Inlet plenum air temperature spot check, reference thermometer (calibrated 2026-09) at the RTD array plane: %.1f degC" % v)
                 for d, v in spot.items()]
    log.sort(key=lambda r: r[0])
    das.to_csv(os.path.join(out, "test_das_1min.csv"), index=False)
    dcs.to_csv(os.path.join(out, "dcs_1min.csv"), index=False)
    gc.to_csv(os.path.join(out, "gas_analysis.csv"), index=False)
    pd.DataFrame(log, columns=["time", "entry"]).to_csv(os.path.join(out, "test_log.csv"), index=False)
    pd.DataFrame(TAGS, columns=["column", "description", "unit"]).to_csv(os.path.join(out, "test_das_columns.csv"), index=False)
    for n in sorted(os.listdir(os.path.join(HERE, "docs"))):
        txt = open(os.path.join(HERE, "docs", n)).read()
        open(os.path.join(out, "docs", n), "w").write(curves(txt))


def curves(txt):
    if "{CIT_TABLE}" not in txt:
        return txt
    cit = np.arange(-5, 41, 5)
    rows = ["| CIT (degC) | output factor | heat rate factor |", "|---|---|---|"]
    rows += ["| %d | %.4f | %.4f |" % (t, gt.f_cit(t), gt.g_cit(t)) for t in cit]
    dpi = np.arange(0.0, 3.01, 0.5)
    rin = ["| inlet loss (kPa) | output factor | heat rate factor |", "|---|---|---|"]
    rin += ["| %.1f | %.4f | %.4f |" % (d, gt.f_in(d), gt.g_in(d)) for d in dpi]
    dpe = np.arange(0.0, 6.01, 1.0)
    rex = ["| exhaust loss (kPa) | output factor | heat rate factor |", "|---|---|---|"]
    rex += ["| %.1f | %.4f | %.4f |" % (d, gt.f_ex(d), gt.g_ex(d)) for d in dpe]
    w = np.arange(0.002, 0.0201, 0.002)
    rh = ["| specific humidity (kg/kg dry air) | output factor | heat rate factor |", "|---|---|---|"]
    rh += ["| %.3f | %.4f | %.4f |" % (x, gt.f_hum(x), gt.g_hum(x)) for x in w]
    return (txt.replace("{CIT_TABLE}", "\n".join(rows)).replace("{IN_TABLE}", "\n".join(rin))
               .replace("{EX_TABLE}", "\n".join(rex)).replace("{HUM_TABLE}", "\n".join(rh))
               .replace("{W_REF}", "%.5f" % gt.W_REF))


if __name__ == "__main__":
    main(sys.argv[1])
