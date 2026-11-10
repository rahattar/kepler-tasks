"""A second program, written apart from solution/hpu.py and sharing no code with it.

    python3 independent_hpu.py PACKAGE_DIR OUT_JSON

Differences in method:
- pandas throughout, rolling-window statistics instead of sample loops;
- the pressure scale from a least-squares fit of the logged pump pressure against the pressure implied by the
  power balance over the loaded samples (not a median ratio), applied when the fitted slope is off 1 by 3 % or more;
- the precharge from the non-negativity of the press demand: over rolling 1 s windows of loaded operation the
  precharge cannot exceed (pump oil in) / (gas volume change per bar of precharge); the estimate is the minimum of
  that ratio after the windows' noise is allowed for (one standard deviation of the window scatter);
- cycles cut at the reload edges with pandas, the peak as the maximum of a rolling mean.
"""
import json
import sys

import numpy as np
import pandas as pd

PATM = 1.013


def main(src, dst):
    u = json.load(open(f"{src}/unit.json"))
    df = pd.read_csv(f"{src}/log.csv")
    dt = float(np.median(np.diff(df.time_s.values)))
    pm, mo, ac = u["pump"], u["motor"], u["accumulator"]
    tab = pd.DataFrame(pm["efficiency_table"]).sort_values("pressure_bar")

    def flows(p_pump, p_el):
        loaded = p_pump > 20.0
        p_sh = mo["efficiency"] * p_el
        n = mo["synchronous_speed_rpm"] - (mo["synchronous_speed_rpm"] - mo["rated_speed_rpm"]) * p_sh / mo["rated_power_kw"]
        q_th = pm["displacement_cm3_per_rev"] * 1e-6 * n / 60
        ev = np.interp(p_pump, tab.pressure_bar, tab.volumetric)
        ehm = np.interp(p_pump, tab.pressure_bar, tab.hydromechanical)
        return np.where(loaded, q_th * ev, 0.0), q_th, ehm, loaded

    # pressure scale: logged pump pressure against the power balance
    q_p, q_th, ehm, loaded = flows(df.pump_pressure_bar.values, df.motor_power_kw.values)
    w = loaded & (df.motor_power_kw.values > 2.5 * mo["unloaded_input_power_kw"])
    p_impl = df.motor_power_kw.values[w] * 1e3 * ehm[w] * mo["efficiency"] / q_th[w] / 1e5
    slope = float(np.dot(p_impl, df.pump_pressure_bar.values[w]) / np.dot(p_impl, p_impl))
    for _ in range(2):                      # the efficiency table is read at the corrected pressure
        q_p, q_th, ehm, loaded = flows(df.pump_pressure_bar.values / slope, df.motor_power_kw.values)
        p_impl = df.motor_power_kw.values[w] * 1e3 * ehm[w] * mo["efficiency"] / q_th[w] / 1e5
        slope = float(np.dot(p_impl, df.pump_pressure_bar.values[w]) / np.dot(p_impl, p_impl))
    if abs(slope - 1) >= 0.03:
        df["system_pressure_bar"] = df.system_pressure_bar / slope
        df["pump_pressure_bar"] = df.pump_pressure_bar / slope
    q_p, q_th, ehm, loaded = flows(df.pump_pressure_bar.values, df.motor_power_kw.values)
    df["q_p"] = q_p; df["loaded"] = loaded

    # precharge from the demand's non-negativity over rolling 1 s windows of loaded operation
    V0 = ac["volume_l"] * 1e-3
    p_abs = df.system_pressure_bar + PATM
    p_m = float(p_abs.mean())
    v1 = V0 / p_m * (p_m / p_abs) ** (1 / 1.4)              # gas volume per bar of precharge
    n = int(round(1.0 / dt))
    oil_in = df.q_p.rolling(n).sum() * dt
    dv = v1.shift(n) - v1                                     # gas volume decrease over the window, per bar
    all_loaded = df.loaded.astype(int).rolling(n + 1).min() == 1
    ratio = (oil_in / dv)[all_loaded & (dv > 0)]
    low = ratio.nsmallest(max(5, int(0.05 * len(ratio))))
    p0 = float(low.mean() + low.std()) - PATM
    if abs(p0 - ac["precharge_bar"]) / ac["precharge_bar"] < 0.05:
        p0 = ac["precharge_bar"]

    # HP-2
    vg = V0 * (p0 + PATM) / p_m * (p_m / p_abs) ** (1 / 1.4)
    dvg = pd.Series(np.gradient(vg.values, dt))
    dvg.iloc[0] = (vg.iloc[1] - vg.iloc[0]) / dt; dvg.iloc[-1] = (vg.iloc[-1] - vg.iloc[-2]) / dt
    df["q_d"] = df.q_p + dvg.values
    edges = np.flatnonzero(df.loaded.values[1:] & ~df.loaded.values[:-1]) + 1
    rows = []
    for a, b in zip(edges[:-1], edges[1:]):
        c = df.iloc[a:b]
        oil = c.q_d.sum() * dt
        peak = c.q_d.rolling(n).mean().max()
        e_h = ((c.system_pressure_bar + PATM) * 1e5 * c.q_d).sum() * dt
        e_e = c.motor_power_kw.sum() * 1e3 * dt
        rows.append((oil * 1e3, peak * 6e4, e_h / 1e3, e_e / 1e3))
    m = np.mean(rows, axis=0)
    json.dump(dict(oil_delivered_l=float(m[0]), peak_flow_l_min=float(m[1]), hydraulic_energy_kj=float(m[2]),
                   electrical_energy_kj=float(m[3]), unit_efficiency=float(m[2] / m[3])), open(dst, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
