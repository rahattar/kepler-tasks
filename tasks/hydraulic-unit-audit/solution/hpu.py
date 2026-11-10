"""Results of one press's hydraulic power unit log by plant procedure HP-2.

    python3 hpu.py PACKAGE_DIR OUT_JSON

Before the procedure the log is checked against the unit's physics:
- Pressure scale. While the pump is loaded, the motor's input power must equal the pump's hydraulic power over the
  pump's and the motor's efficiencies: P_el = p Q_th / (eta_hm eta_motor). The logged pressure is compared with the
  pressure this balance implies; a logger whose pressure channels are scaled wrong shows a constant ratio, and the
  pressures are divided by it (both channels come from the same logger configuration).
- Precharge. While the pump charges the accumulator with the press at rest, every litre the pump delivers goes into
  the accumulator, so the gas law with the right precharge reproduces the pressure rise from the pump flow. The
  precharge is fitted to the charging curves; a bladder accumulator loses precharge with time, so the figure of the
  last check need not hold.
"""
import csv
import json
import sys

import numpy as np

P_ATM = 1.013
N_POLY = 1.40
LOADED_BAR = 20.0


def read(d):
    u = json.load(open(d + "/unit.json"))
    t, ps, pp, pw = [], [], [], []
    with open(d + "/log.csv", newline="") as f:
        for r in csv.DictReader(f):
            t.append(float(r["time_s"])); ps.append(float(r["system_pressure_bar"]))
            pp.append(float(r["pump_pressure_bar"])); pw.append(float(r["motor_power_kw"]))
    return u, np.array(t), np.array(ps), np.array(pp), np.array(pw)


def smooth(x, n):
    k = np.ones(n) / n
    y = np.convolve(x, k, mode="same")
    h = n // 2
    for i in range(h):                      # edges: shrink the window
        y[i] = x[: i + h + 1].mean(); y[-1 - i] = x[-1 - i - h:].mean()
    return y


def pump_flow(u, p_pump, p_el):
    """Pump flow (m3/s) and theoretical flow while loaded, by HP-2."""
    pm, mo = u["pump"], u["motor"]
    tab = np.array([[r["pressure_bar"], r["volumetric"], r["hydromechanical"]] for r in pm["efficiency_table"]])
    loaded = p_pump > LOADED_BAR
    P_shaft = mo["efficiency"] * p_el                           # kW
    n = mo["synchronous_speed_rpm"] - (mo["synchronous_speed_rpm"] - mo["rated_speed_rpm"]) * P_shaft / mo["rated_power_kw"]
    q_th = pm["displacement_cm3_per_rev"] * 1e-6 * n / 60.0
    ev = np.interp(p_pump, tab[:, 0], tab[:, 1]); ehm = np.interp(p_pump, tab[:, 0], tab[:, 2])
    return np.where(loaded, q_th * ev, 0.0), np.where(loaded, q_th, 0.0), ehm, loaded


def pressure_scale(u, p_pump, p_el):
    """Ratio of the logged pressure to the pressure implied by the power balance, over loaded samples."""
    mo = u["motor"]
    ratios = []
    for _ in range(3):
        _, q_th, ehm, loaded = pump_flow(u, p_pump, p_el)
        w = loaded & (p_el > 2.0 * mo["unloaded_input_power_kw"])
        p_impl = p_el[w] * 1e3 * ehm[w] * mo["efficiency"] / q_th[w] / 1e5 - 0.0     # bar (gauge ~ absolute here)
        k = np.median(p_pump[w] / p_impl)
        ratios.append(k)
        p_pump = p_pump / k
    return float(np.prod(ratios))


def fit_precharge(u, t, ps, q_p, loaded):
    """Precharge (bar gauge) from the charging physics. While the pump is loaded, the press's demand is the pump
    flow less what goes into the accumulator, and that demand cannot be negative: oil never flows from the press
    back into the accumulator. The gas volume change per bar of precharge is known from the gas law, so over any
    window of loaded operation the precharge is at most (pump oil in) / (gas volume change per bar of precharge),
    with equality while the press is at rest. The precharge is the smallest ratio over 0.5 s windows of loaded
    operation (a low percentile, against the sample noise), which is where the press rests while the pump finishes
    charging."""
    V0 = u["accumulator"]["volume_l"] * 1e-3
    dt = t[1] - t[0]
    p_m = float(np.mean(ps)) + P_ATM
    win = int(round(1.0 / dt))
    pa = ps + P_ATM
    v1 = V0 / p_m * (p_m / pa) ** (1 / N_POLY)          # gas volume per bar(abs) of precharge
    ratios = []
    i = 0
    while i + win < len(t):
        if loaded[i:i + win + 1].all():
            dv = v1[i] - v1[i + win]                      # gas volume decrease per bar of precharge
            if dv > 0:
                ratios.append(np.sum(q_p[i:i + win]) * dt / dv)
        i += 1
    ratios = np.array(ratios)
    return float(np.percentile(ratios, 5.0)) - P_ATM


def results(u, t, ps, pp, pw, p0g):
    V0 = u["accumulator"]["volume_l"] * 1e-3
    dt = t[1] - t[0]
    q_p, q_th, ehm, loaded = pump_flow(u, pp, pw)
    p_m = float(np.mean(ps)) + P_ATM                              # mean state: isothermal from the precharge
    vg = V0 * (p0g + P_ATM) / p_m * (p_m / (ps + P_ATM)) ** (1 / N_POLY)
    dvg = np.zeros_like(vg)
    dvg[1:-1] = (vg[2:] - vg[:-2]) / (2 * dt)                     # central differences, as HP-2 states
    dvg[0] = (vg[1] - vg[0]) / dt; dvg[-1] = (vg[-1] - vg[-2]) / dt
    q_d = q_p + dvg
    starts = [i for i in range(1, len(t)) if loaded[i] and not loaded[i - 1]]
    out = []
    win = int(round(1.0 / dt))
    for a, b in zip(starts[:-1], starts[1:]):
        qd = q_d[a:b]; pa = (ps[a:b] + P_ATM) * 1e5
        oil = np.sum(qd) * dt
        peak = max(np.mean(qd[i:i + win]) for i in range(0, b - a - win + 1))
        e_h = np.sum(pa * qd) * dt
        e_e = np.sum(pw[a:b]) * 1e3 * dt
        out.append((oil * 1e3, peak * 6e4, e_h / 1e3, e_e / 1e3))
    m = np.mean(out, axis=0)
    return dict(oil_delivered_l=round(float(m[0]), 3), peak_flow_l_min=round(float(m[1]), 2),
                hydraulic_energy_kj=round(float(m[2]), 3), electrical_energy_kj=round(float(m[3]), 3),
                unit_efficiency=round(float(m[2] / m[3]), 4))


def main(d, out):
    u, t, ps, pp, pw = read(d)
    k = pressure_scale(u, pp, pw)
    if abs(k - 1.0) > 0.05:
        ps, pp = ps / k, pp / k
    q_p, _, _, loaded = pump_flow(u, pp, pw)
    p0g = fit_precharge(u, t, ps, q_p, loaded)
    doc = u["accumulator"]["precharge_bar"]
    if abs(p0g - doc) / doc < 0.05:
        p0g = doc
    r = results(u, t, ps, pp, pw, p0g)
    json.dump(r, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
