"""BE-3 daily efficiency and coal fired for one boiler.

    python3 efficiency.py BOILER_DIR OUT_CSV

Excess air is taken from the two inlet O2 probes, which agree with each other and with the outlet probe. The
CO2 analyser is then a check on the fuel: for each delivery on file, the O2 reading and that delivery's
analysis give the CO2 the gas would hold. The residual of the CO2 reading against the logged delivery is the
analyser's own error (slow: its zero drifting) plus a step wherever the delivery fired is not the one logged.
A running median over three weeks follows the slow part; fillings whose residual stands off it are matched
to the delivery on file whose combustion leaves none.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

FLY = 0.8
WINDOW = "504h"        # three weeks: a mislabelled run of fillings is a few days
OFF = 0.25             # % CO2 off the running median, against the analyser's 0.1 and the probes' 0.05
EA_SOURCE = "o2"       # routes: "co2" the reading as it stands, "co2corr" the reading less the running median
IDENT = "median"       # routes: "none" the log as it stands, "naive" the delivery nearest the reading


def stoich(a, u):
    C, H, O, N, S, A, M = a
    nC = (C - u) / 12.011
    nS, nN2f = S / 32.06, N / 28.013
    nth = nC + H / 2.016 / 2 + nS - O / 31.998
    return nC, nS, nN2f, nth


def ea_from_o2(a, u, o2, x):
    nC, nS, nN2f, nth = stoich(a, u)
    D0 = nC + nS + nN2f + 3.773 * nth + nC * x / 2
    return (o2 * D0 - 50.0 * nC * x) / (nth * (100.0 - 4.773 * o2))


def co2_at(a, u, EA, x):
    nC, nS, nN2f, nth = stoich(a, u)
    D = nC + nS + nN2f + 3.773 * nth + nC * x / 2 + 4.773 * nth * EA
    return 100.0 * nC * (1 - x) / D


def main(pkg, out):
    boiler = json.load(open(os.path.join(pkg, "boiler.json")))
    hr = pd.read_csv(os.path.join(pkg, "hourly.csv"))
    dl = pd.read_csv(os.path.join(pkg, "deliveries.csv"))
    lg = pd.read_csv(os.path.join(pkg, "bunker_log.csv"))
    fa = pd.read_csv(os.path.join(pkg, "fly_ash.csv"))
    t = pd.to_datetime(hr["hour"])
    t_log = pd.to_datetime(lg["hour"])
    seg = np.searchsorted(t_log.values, t.values, side="right") - 1
    ids = list(dl["delivery"])
    A6 = dl[["C", "H", "O", "N", "S", "ash", "moisture"]].to_numpy(float)       # deliveries x 7
    hhv = dl["hhv_kJ_kg"].to_numpy(float)
    received = pd.to_datetime(dl["received"]).values
    logged_seg = np.array([ids.index(d) for d in lg["delivery"]])
    loi_f = hr["hour"].str[:10].map(dict(zip(fa["date"], fa["loi"]))).to_numpy(float)
    loi_b = float(boiler["bottom_ash_loi"])

    co2m = hr["co2_pct"].to_numpy(float)
    o2 = 0.5 * (hr["o2_a_pct"].to_numpy(float) + hr["o2_b_pct"].to_numpy(float))
    r = hr["co_ppm"].to_numpy(float) / (1e4 * co2m)
    x = r / (1 + r)

    # CO2 the gas would hold, for every delivery on file, hour by hour
    a_all = A6.T[:, :, None]                                               # 7 x deliveries x 1
    u_all = a_all[5] * (FLY * loi_f / (1 - loi_f) + (1 - FLY) * loi_b / (1 - loi_b))
    ea_all = ea_from_o2(a_all, u_all, o2, x)
    pred = co2_at(a_all, u_all, ea_all, x)                                 # deliveries x hours
    resid = co2m[None, :] - pred

    fired_seg = logged_seg.copy()
    for _ in range(3):
        own = resid[fired_seg[seg], np.arange(len(seg))]
        base = pd.Series(own, index=t).rolling(WINDOW, center=True, min_periods=24).median().to_numpy()
        new = fired_seg.copy()
        for j in range(len(lg)):
            sl = seg == j
            if not sl.any():
                continue
            if IDENT == "none":
                continue
            off = np.abs((resid[:, sl] - (0 if IDENT == "naive" else base[sl])).mean(axis=1))
            if off[logged_seg[j]] < OFF:
                new[j] = logged_seg[j]
                continue
            ok = (received <= t_log.values[j]) & (off < off.min() + 0.05)
            if not ok.any():
                ok = off < off.min() + 0.05
            new[j] = int(np.nonzero(ok)[0][np.argmax(received[ok])])
        if (new == fired_seg).all():
            break
        fired_seg = new

    k = fired_seg[seg]
    a = A6[k].T
    C, H, O, N, S, A, M = a
    u = A * (FLY * loi_f / (1 - loi_f) + (1 - FLY) * loi_b / (1 - loi_b))
    EA = ea_from_o2(a, u, o2, x)
    nC, nS, nN2f, nth = stoich(a, u)
    if EA_SOURCE != "o2":
        own = resid[k, np.arange(len(k))]
        base = pd.Series(own, index=t).rolling(WINDOW, center=True, min_periods=24).median().to_numpy()
        c = co2m - (base if EA_SOURCE == "co2corr" else 0.0)
        EA = (100.0 * nC * (1 - x) / c - (nC + nS + nN2f + 3.773 * nth + nC * x / 2)) / (4.773 * nth)
    co2, co, o2g = nC * (1 - x), nC * x, EA * nth + nC * x / 2
    n2 = 3.773 * (1 + EA) * nth + nN2f
    m_dg = 44.010 * co2 + 28.010 * co + 64.060 * nS + 31.998 * o2g + 28.013 * n2
    m_air = 137.69 * (1 + EA) * nth

    o2o = hr["o2_outlet_pct"].to_numpy(float)
    t_out = hr["gas_outlet_C"].to_numpy(float)
    t_air = hr["air_inlet_C"].to_numpy(float)
    Lm = 0.9 * (o2o - o2) / (20.95 - o2o)
    t_corr = t_out + Lm * 1.005 / 1.05 * (t_out - t_air)
    dT = t_corr - t_air
    L = (m_dg * 1.02 * dT + (9 * H + M) * (2501.0 + 1.88 * t_corr - 4.19 * t_air)
         + m_air * hr["humidity_kg_kg"].to_numpy(float) * 1.88 * dT + u * 33700.0 + 28.010 * co * 10110.0
         + FLY * A / (1 - loi_f) * 0.84 * dT + (1 - FLY) * A / (1 - loi_b) * 0.84 * (800.0 - t_air))
    rad = np.array([[p["load_fraction"], p["loss_pct"]] for p in boiler["radiation_loss"]])
    Q = hr["heat_output_MW"].to_numpy(float)
    eta = 100.0 - 100.0 * L / hhv[k] - np.interp(Q / boiler["rated_output_MW"], rad[:, 0], rad[:, 1])
    fuel_t = Q * 1000.0 / (eta / 100.0 * hhv[k]) * 3600.0 / 1000.0
    day = hr["hour"].str[:10]
    g = pd.DataFrame({"date": day, "Q": Q, "input": Q / eta, "coal": fuel_t}).groupby("date", sort=True).sum()
    res = pd.DataFrame({"date": g.index, "efficiency_pct": (g["Q"] / g["input"]).round(4),
                        "coal_t": g["coal"].round(3)})
    res.to_csv(out, index=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
