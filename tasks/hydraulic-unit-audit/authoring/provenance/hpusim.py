"""Hydraulic power unit with a bladder accumulator feeding a press: fixed-displacement pump on an induction motor,
unloading valve with hysteresis, accumulator gas with heat transfer to the shell, press demand profile per cycle.
Simulated at a fine step; logs at the data logger's rate."""
import numpy as np

R_N2 = 296.8      # J/(kg K)


def eta_v(p_bar, tab):
    return np.interp(p_bar, tab[:, 0], tab[:, 1])


def eta_hm(p_bar, tab):
    return np.interp(p_bar, tab[:, 0], tab[:, 2])


def simulate(U, cyc, n_cycles, rng, dt=0.002, fs=20.0, t_settle=3):
    """U: unit dict (Vg m3/rev, n_sync rpm, s_rated, P_rated W, idle_kw, V0 m3, p0_act Pa (actual precharge),
    T_amb K, tau_th s, p_on Pa, p_off Pa, table). cyc: demand profile list of (duration s, flow m3/s) plus dwell.
    Returns logger arrays (t, p_sys, p_pump, P_el) and true per-cycle results."""
    Vg, V0 = U["Vg"], U["V0"]
    tab = U["table"]
    # gas: adiabatic (nitrogen, 1.40) swings about its mean operating state, which is the isothermal state at the
    # reference pressure (the gas returns to the oil temperature over every cycle)
    p_ref = 0.5 * (U["p_on"] + U["p_off"]); V_ref = V0 * U["p0_act"] / p_ref
    p = U["p_off"]; Vgas = V_ref * (p_ref / p) ** (1 / 1.4)
    loaded = False
    period = sum(d for d, _ in cyc) + U["dwell"]
    total = (n_cycles + t_settle) * period
    n_steps = int(total / dt)
    log_every = int(round(1 / (fs * dt)))
    tl, ps, pp, pe = [], [], [], []
    truth = []
    cyc_t0 = -t_settle * period
    acc = dict(vol=0.0, energy=0.0, peak=0.0, eel=0.0)
    cyc_index = -t_settle
    for i in range(n_steps):
        t = i * dt - t_settle * period
        tc = t - cyc_index * period
        q_d = 0.0; el = 0.0
        for d, q in cyc:
            if tc < el + d:
                q_d = q; break
            el += d
        # unloading valve
        if p >= U["p_off"]:
            loaded = False
        if p <= U["p_on"]:
            loaded = True
        # pump
        if loaded:
            # motor speed from slip at this load (shaft power estimate from previous step's pressure)
            # shaft power = p * Q_th / eta_hm with Q_th = Vg n / 60; the motor's slip grows with shaft power
            n = U["n_sync"] * (1 - U["s_rated"] * (p * Vg * U["n_sync"] / 60 / eta_hm(p / 1e5, tab)) / U["P_rated"])
            q_th = Vg * n / 60
            q_pump = q_th * eta_v(p / 1e5, tab)
            P_shaft = p * q_th / eta_hm(p / 1e5, tab)
            P_el = P_shaft / U["eta_motor"]
            p_pump = p + U["dp_line"] * (q_pump / U["q_ref"]) ** 2
        else:
            q_pump = 0.0
            P_el = U["idle_kw"] * 1e3
            p_pump = U["p_unloaded"]
        # accumulator oil balance: oil in = q_pump - q_d
        dV_oil = (q_pump - q_d) * dt
        Vgas_new = Vgas - dV_oil
        if Vgas_new > V0:                      # accumulator empty of oil: pressure falls to precharge; clamp
            Vgas_new = V0
        Vgas = Vgas_new
        p = p_ref * (V_ref / Vgas) ** 1.4
        # truth accumulation
        if cyc_index >= 0:
            acc["vol"] += q_d * dt; acc["energy"] += p * q_d * dt; acc["peak"] = max(acc["peak"], q_d); acc["eel"] += P_el * dt
        if i % log_every == 0 and cyc_index >= 0:
            tl.append(t); ps.append(p); pp.append(p_pump); pe.append(P_el)
        if t - cyc_index * period >= period - 1e-9:
            if cyc_index >= 0:
                truth.append(dict(oil_delivered_l=acc["vol"] * 1e3, peak_flow_l_min=acc["peak"] * 6e4,
                                  hydraulic_energy_kj=acc["energy"] / 1e3, electrical_energy_kj=acc["eel"] / 1e3))
            acc = dict(vol=0.0, energy=0.0, peak=0.0, eel=0.0)
            cyc_index += 1
    return np.array(tl), np.array(ps), np.array(pp), np.array(pe), truth
