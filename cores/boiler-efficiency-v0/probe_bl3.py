#!/usr/bin/env python3
"""BE-3 boiler efficiency (losses method, HHV) per day, from a boiler package.

Usage: python3 efficiency.py BOILER_DIR OUT_CSV

BE-3 asks for the fuel and gas "as the boiler ran", so the records are
cross-checked before use:
  * Excess air is found from the inlet O2 (two zirconia probes, finer
    resolution) and not from the single CO2 analyser, which may drift.
  * The coal actually fired is checked against the gas: for a given fuel the
    flue-gas CO2 is fixed by the O2.  The CO2 analyser's (slowly varying)
    offset is tracked with a long rolling median; a bunker filling whose gas
    does not fit the logged delivery is reassigned to the received delivery
    whose analysis fits.
  * Where the two O2 probes disagree, the one consistent with the CO2 is used.
"""
import sys, os, json
import numpy as np
import pandas as pd

WIN_H = 15 * 24          # rolling window for the CO2 analyser offset, hours
FUEL_TOL = 0.25          # CO2 %-points: misfit that marks a filling as mislogged
NEAR = 0.06              # candidates within this of the best fit count as equal
PROBE_TOL = 0.25         # O2 %-points: probes A and B disagree


def fuel_terms(F, u):
    nC = (F["C"] - u) / 12.011
    nS = F["S"] / 32.06
    nN2 = F["N"] / 28.013
    nth = nC + F["H"] / 2.016 / 2 + nS - F["O"] / 31.998
    return nC, nS, nN2, nth


def co2_pred(F, u, o2pct, x):
    nC, nS, nN2, nth = fuel_terms(F, u)
    base = nC + nS + nN2 + 3.773 * nth + nC * x / 2
    f = o2pct / 100.0
    E = (f * base - nC * x / 2) / (nth * (1 - 4.773 * f))
    D = base + 4.773 * E * nth
    return 100 * nC * (1 - x) / D


def o2_pred(F, u, co2pct, x):
    nC, nS, nN2, nth = fuel_terms(F, u)
    base = nC + nS + nN2 + 3.773 * nth + nC * x / 2
    E = (100 * nC * (1 - x) / co2pct - base) / (4.773 * nth)
    D = base + 4.773 * E * nth
    return 100 * (E * nth + nC * x / 2) / D


def centred_median(th, v, win):
    """Median of v over hours within +-win/2 of each hour (th sorted)."""
    lo = np.searchsorted(th, th - win / 2, "left")
    hi = np.searchsorted(th, th + win / 2, "right")
    # downsample to keep it fast: compute at every 6th hour and interpolate
    step = 6
    k = np.arange(0, len(th), step)
    if k[-1] != len(th) - 1:
        k = np.append(k, len(th) - 1)
    med = np.array([np.median(v[lo[i]:hi[i]]) for i in k])
    return np.interp(th, th[k], med)


def main(bdir, out):
    cfg = json.load(open(os.path.join(bdir, "boiler.json")))
    h = pd.read_csv(os.path.join(bdir, "hourly.csv"))
    dl = pd.read_csv(os.path.join(bdir, "deliveries.csv"))
    dl["delivery"] = dl["delivery"].astype(str).str.strip()
    dl = dl.drop_duplicates("delivery", keep="last").set_index("delivery")
    bl = pd.read_csv(os.path.join(bdir, "bunker_log.csv"))
    bl["delivery"] = bl["delivery"].astype(str).str.strip()
    fa = pd.read_csv(os.path.join(bdir, "fly_ash.csv"))

    t = pd.to_datetime(h["hour"].astype(str).str.strip(), format="%Y-%m-%d %H:%M")
    order = np.argsort(t.values, kind="stable")
    h = h.iloc[order].reset_index(drop=True); t = t.iloc[order].reset_index(drop=True)
    th = (t.values.astype("datetime64[s]").astype(np.int64)) / 3600.0
    date = t.dt.strftime("%Y-%m-%d").values

    bt = pd.to_datetime(bl["hour"].astype(str).str.strip(), format="%Y-%m-%d %H:%M")
    bo = np.argsort(bt.values, kind="stable")
    bl = bl.iloc[bo].reset_index(drop=True); bt = bt.iloc[bo].reset_index(drop=True)
    seg = np.clip(np.searchsorted(bt.values, t.values, side="right") - 1, 0, len(bl) - 1)
    nseg = len(bl)

    names = list(dl.index)
    recv = pd.to_datetime(dl["received"]).values
    comp = {k: dl[k].values.astype(float) for k in ["C", "H", "O", "N", "S", "ash", "moisture", "hhv_kJ_kg"]}

    fad = dict(zip(fa["date"].astype(str).str.strip(), fa["loi"].astype(float)))
    loi = np.array([fad.get(d, np.nan) for d in date])
    if np.isnan(loi).any():  # missing day: nearest available value
        s = pd.Series(loi).interpolate(limit_direction="both")
        loi = s.fillna(np.nanmean(list(fad.values())) if fad else 0.0).values
    lb = float(cfg["bottom_ash_loi"])

    Q = h["heat_output_MW"].values.astype(float)
    co2 = h["co2_pct"].values.astype(float)
    co = h["co_ppm"].values.astype(float)
    oa = h["o2_a_pct"].values.astype(float); ob = h["o2_b_pct"].values.astype(float)
    o2out = h["o2_outlet_pct"].values.astype(float)
    Tout = h["gas_outlet_C"].values.astype(float); Ta = h["air_inlet_C"].values.astype(float)
    w = h["humidity_kg_kg"].values.astype(float)
    o2in = 0.5 * (oa + ob)

    rr = co / (1e4 * co2); x = rr / (1 + rr)

    def fuel_of(idx):
        return {k: v[idx] for k, v in comp.items()}

    def u_of(idx):
        A = comp["ash"][idx]
        return A * (0.8 * loi / (1 - loi) + 0.2 * lb / (1 - lb))

    # ---- identify the coal fired, filling by filling --------------------------
    logged = np.array([names.index(d) if d in names else -1 for d in bl["delivery"]])
    assign = logged.copy()
    if (assign < 0).any():
        assign[assign < 0] = 0
    # residual CO2 (measured - predicted from O2) for each candidate delivery
    R = np.empty((len(names), len(t)))
    for j in range(len(names)):
        F = {k: v[j] for k, v in comp.items()}
        u = F["ash"] * (0.8 * loi / (1 - loi) + 0.2 * lb / (1 - lb))
        R[j] = co2 - co2_pred(F, u, o2in, x)
    seg_cnt = np.bincount(seg, minlength=nseg)
    seg_date = bt.values.astype("datetime64[D]")
    for _ in range(4):
        r = R[assign[seg], np.arange(len(t))]
        b = centred_median(th, r, WIN_H)
        dev = R - b  # (ndeliv, nhours)
        S = np.zeros((len(names), nseg))
        for j in range(len(names)):
            S[j] = np.bincount(seg, weights=dev[j], minlength=nseg)
        with np.errstate(invalid="ignore", divide="ignore"):
            M = np.abs(S / np.maximum(seg_cnt, 1))
        new = assign.copy()
        for s in range(nseg):
            if seg_cnt[s] == 0:
                continue
            lg = logged[s]
            if lg >= 0 and M[lg, s] <= FUEL_TOL:
                new[s] = lg
                continue
            ok = recv.astype("datetime64[D]") <= seg_date[s]
            if not ok.any():
                ok[:] = True
            cand = np.where(ok)[0]
            best = cand[np.argmin(M[cand, s])]
            if lg >= 0 and M[lg, s] <= M[best, s] + NEAR:
                new[s] = lg; continue
            near = [c for c in cand if M[c, s] <= M[best, s] + NEAR]
            pref = []
            for nb in range(s - 1, -1, -1):  # previous filling actually fired
                if seg_cnt[nb]:
                    pref.append(new[nb]); break
            for nb in range(s + 1, nseg):
                if seg_cnt[nb]:
                    pref.append(logged[nb] if logged[nb] >= 0 else assign[nb]); break
            pick = None
            for p in pref:
                if p in near:
                    pick = p; break
            if pick is None:
                pick = max(near, key=lambda c: (recv[c], -M[c, s]))
            new[s] = pick
        if np.array_equal(new, assign):
            break
        assign = new

    if os.environ.get("BE3_DEBUG"):
        for s_ in np.where(assign != logged)[0]:
            sys.stderr.write(f"filling {bl['hour'][s_]} logged {bl['delivery'][s_]} -> {names[assign[s_]]}\n")
        sys.stderr.write(f"probe disagreements: {(np.abs(oa-ob)>PROBE_TOL).sum()}\n")
    fidx = assign[seg]
    F = fuel_of(fidx)
    u = u_of(fidx)

    # ---- O2 probes that disagree: keep the one consistent with the CO2 --------
    r = R[fidx, np.arange(len(t))]
    b = centred_median(th, r, WIN_H)
    dis = np.abs(oa - ob) > PROBE_TOL
    if dis.any():
        o2c = o2_pred(F, u, co2 - b, x)
        pick_a = np.abs(oa - o2c) <= np.abs(ob - o2c)
        o2in = np.where(dis, np.where(pick_a, oa, ob), o2in)

    # ---- BE-3 sections 3 to 6 ----------------------------------------------
    C, H, A, M, HHV = F["C"], F["H"], F["ash"], F["moisture"], F["hhv_kJ_kg"]
    nC, nS, nN2, nth = fuel_terms(F, u)
    base = nC + nS + nN2 + 3.773 * nth + nC * x / 2
    f = o2in / 100.0
    E = (f * base - nC * x / 2) / (nth * (1 - 4.773 * f))
    mdg = (nC * (1 - x) * 44.010 + nC * x * 28.010 + nS * 64.060
           + (E * nth + nC * x / 2) * 31.998 + (3.773 * (1 + E) * nth + nN2) * 28.013)
    ma = 137.69 * (1 + E) * nth
    L = 0.9 * (o2out - o2in) / (20.95 - o2out)
    Tg = Tout + L * (1.005 / 1.05) * (Tout - Ta)
    Tr = Ta
    loss = (mdg * 1.02 * (Tg - Tr)
            + (9 * H + M) * (2501 + 1.88 * Tg - 4.19 * Tr)
            + ma * w * 1.88 * (Tg - Tr)
            + 33700 * u
            + 10110 * 28.010 * nC * x
            + 0.84 * 0.8 * A / (1 - loi) * (Tg - Tr)
            + 0.84 * 0.2 * A / (1 - lb) * (800 - Tr))
    pts = sorted(cfg["radiation_loss"], key=lambda p: p["load_fraction"])
    rad = np.interp(Q / float(cfg["rated_output_MW"]),
                    [p["load_fraction"] for p in pts], [p["loss_pct"] for p in pts])
    eta = 100 - 100 * loss / HHV - rad
    Fk = 1000 * Q / (eta / 100 * HHV)

    # ---- section 7 ------------------------------------------------------------
    d = pd.DataFrame({"date": date, "Q": Q, "inp": 100 * Q / eta, "coal": 3.6 * Fk})
    g = d.groupby("date", sort=True).sum()
    res = pd.DataFrame({"date": g.index,
                        "efficiency_pct": np.round(100 * g["Q"].values / g["inp"].values, 4),
                        "coal_t": np.round(g["coal"].values, 3)})
    res.to_csv(out, index=False, float_format="%.4f")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
