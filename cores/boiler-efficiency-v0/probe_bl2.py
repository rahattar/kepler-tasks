#!/usr/bin/env python3
"""BE-3 boiler efficiency (losses method) for one boiler package.

usage: python3 efficiency.py BOILER_DIR OUT_CSV

Robustness beyond the literal BE-3 text, so that the fuel, gas and air are those
of the boiler as it ran:
 * Excess air is taken from the inlet O2 (zirconia probes, the more precise
   instrument); the CO share x is solved together with it so that a drifting
   CO2 analyser does not bias the result.  On clean data this agrees with the
   CO2 route to within the instruments' resolution.
 * If probes A and B disagree, the one consistent with the CO2 analyser is used.
 * Each bunker filling's logged delivery is checked against the gas analysis
   (measured CO2 vs that expected from O2 for the fuel); a filling whose gas
   plainly fits another delivery is reassigned to it.
"""
import sys, os, json
import numpy as np
import pandas as pd

KEYS = ['C', 'H', 'O', 'N', 'S', 'ash', 'moisture', 'hhv_kJ_kg']


def moles(C, H, O, N, S, u):
    nC = (C - u) / 12.011
    nH = H / 2.016
    nS = S / 32.06
    nO = O / 31.998
    nN = N / 28.013
    nth = nC + nH / 2 + nS - nO
    return nC, nS, nN, nth


def solve_gas(nC, nS, nN, nth, o2pct, co_ppm, co2_guess):
    """E and x from O2 and CO; returns E, x, predicted CO2 %."""
    f = o2pct / 100.0
    co2 = np.array(co2_guess, dtype=float)
    for _ in range(6):
        r = co_ppm / (1e4 * np.maximum(co2, 1.0))
        x = r / (1 + r)
        base = nC + nS + nN + 3.773 * nth + nC * x / 2
        E = (f * base - nC * x / 2) / (nth * (1 - 4.773 * f))
        D = base + 4.773 * E * nth
        co2 = 100 * nC * (1 - x) / D
    return E, x, co2


def rolling_median(v, win):
    s = pd.Series(v)
    return s.rolling(win, center=True, min_periods=max(5, win // 10)).median() \
        .bfill().ffill().fillna(0.0).values


def main(bdir, out):
    b = json.load(open(os.path.join(bdir, 'boiler.json')))
    h = pd.read_csv(os.path.join(bdir, 'hourly.csv'))
    dl = pd.read_csv(os.path.join(bdir, 'deliveries.csv'))
    dl['delivery'] = dl['delivery'].astype(str).str.strip()
    dl = dl.drop_duplicates('delivery', keep='last').set_index('delivery')
    bl = pd.read_csv(os.path.join(bdir, 'bunker_log.csv'))
    bl['delivery'] = bl['delivery'].astype(str).str.strip()
    fa = pd.read_csv(os.path.join(bdir, 'fly_ash.csv'))

    t = pd.to_datetime(h['hour'].astype(str).str.strip())
    order = np.argsort(t.values, kind='stable')
    h = h.iloc[order].reset_index(drop=True)
    t = t.iloc[order].reset_index(drop=True)
    h['date'] = t.dt.strftime('%Y-%m-%d')
    n = len(h)

    num = lambda c: pd.to_numeric(h[c], errors='coerce').values.astype(float)
    Q = num('heat_output_MW')
    co2m = num('co2_pct')
    co = np.nan_to_num(num('co_ppm'), nan=0.0)
    oa = num('o2_a_pct'); ob = num('o2_b_pct')
    o2out = num('o2_outlet_pct')
    Tout = num('gas_outlet_C'); Ta = num('air_inlet_C')
    w = num('humidity_kg_kg')

    # fly ash LOI per date (fraction; tolerate per-cent entries)
    fa['date'] = pd.to_datetime(fa['date'].astype(str).str.strip()).dt.strftime('%Y-%m-%d')
    fl = pd.to_numeric(fa['loi'], errors='coerce')
    fl = np.where(fl > 0.5, fl / 100.0, fl)
    lmap = dict(zip(fa['date'], fl))
    lf = h['date'].map(lmap).astype(float)
    lf = lf.fillna(np.nanmedian(fl)).values
    lb = float(b['bottom_ash_loi'])
    if lb > 0.5:
        lb /= 100.0

    # bunker fillings
    btimes = pd.to_datetime(bl['hour'].astype(str).str.strip())
    bo = np.argsort(btimes.values, kind='stable')
    bl = bl.iloc[bo].reset_index(drop=True)
    btv = btimes.values[bo]
    seg = np.clip(np.searchsorted(btv, t.values, side='right') - 1, 0, len(bl) - 1)
    logged = bl['delivery'].values.copy()
    known = np.array([d in dl.index for d in logged])
    names = list(dl.index)
    if not known.all():  # unknown names: fall back to previous known filling
        last = names[0]
        for i in range(len(logged)):
            if known[i]:
                last = logged[i]
            else:
                logged[i] = last
    assign = logged.copy()

    F = dl[KEYS].astype(float).values  # per delivery
    didx = {d: i for i, d in enumerate(names)}
    recv = pd.to_datetime(dl['received'].astype(str).str.strip(), errors='coerce').values

    # probe selection preliminary: mean
    o2in = np.where(np.isnan(oa), ob, np.where(np.isnan(ob), oa, (oa + ob) / 2))
    agree = np.abs(oa - ob) <= 0.25

    def fuel_cols(di):
        return [F[di, k] for k in range(8)]

    def resid(di_hour, o2):
        C, H, O, N, S, A, M, HHV = [F[di_hour, k] for k in range(8)]
        u = A * (0.8 * lf / (1 - lf) + 0.2 * lb / (1 - lb))
        nC, nS, nN, nth = moles(C, H, O, N, S, u)
        _, _, c = solve_gas(nC, nS, nN, nth, o2, co, co2m)
        return np.log(co2m / c)

    ok_meas = np.isfinite(co2m) & (co2m > 1)
    win = 481

    # --- fuel check per filling ---
    for _ in range(2):
        di_h = np.array([didx[assign[s]] for s in seg])
        r_log = resid(di_h, o2in)
        good = ok_meas & agree & np.isfinite(r_log)
        rr = np.where(good, r_log, np.nan)
        base = rolling_median(rr, win)
        # residuals for every candidate delivery
        R = np.empty((len(names), n))
        for j in range(len(names)):
            R[j] = resid(np.full(n, j), o2in) - base
        changed = False
        for s in np.unique(seg):
            m = (seg == s) & good
            if m.sum() < 3:
                continue
            dev = np.nanmedian(R[:, m], axis=1)
            cur = didx[assign[s]]
            if abs(dev[cur]) < 0.025:
                continue
            fill_t = btv[s]
            cand = [j for j in range(len(names))
                    if not (pd.notna(recv[j]) and recv[j] > fill_t + np.timedelta64(1, 'D'))]
            if not cand:
                continue
            best = min(cand, key=lambda j: abs(dev[j]))
            if abs(dev[best]) > 0.4 * abs(dev[cur]) or abs(dev[best]) > 0.02:
                continue
            close = [j for j in cand if abs(dev[j]) <= abs(dev[best]) + 0.01]
            # among equally fitting deliveries prefer the one logged nearest in time
            def dist(j):
                pos = np.where(bl['delivery'].values == names[j])[0]
                return (np.min(np.abs(pos - s)) if len(pos) else 10**6, abs(dev[j]))
            pick = min(close, key=dist)
            if pick != cur:
                assign[s] = names[pick]
                changed = True
        if not changed:
            break

    di_h = np.array([didx[assign[s]] for s in seg])

    # --- probe disagreement: use the probe consistent with CO2 ---
    bad = ~agree & np.isfinite(oa) & np.isfinite(ob)
    if bad.any():
        r_log = resid(di_h, o2in)
        base = rolling_median(np.where(ok_meas & agree, r_log, np.nan), win)
        ra = np.abs(resid(di_h, oa) - base)
        rb = np.abs(resid(di_h, ob) - base)
        pickA = np.where(np.isfinite(ra) & np.isfinite(rb), ra <= rb, np.isfinite(ra))
        o2in = np.where(bad, np.where(pickA, oa, ob), o2in)

    # --- BE-3 calculation ---
    C, H, O, N, S, A, M, HHV = [F[di_h, k] for k in range(8)]
    u = A * (0.8 * lf / (1 - lf) + 0.2 * lb / (1 - lb))
    nC, nS, nN, nth = moles(C, H, O, N, S, u)
    co2g = np.where(ok_meas, co2m, 15.0)
    E, x, _ = solve_gas(nC, nS, nN, nth, o2in, co, co2g)
    mdg = (44.010 * nC * (1 - x) + 28.010 * nC * x + 64.060 * nS
           + 31.998 * (E * nth + nC * x / 2)
           + 28.013 * (3.773 * (1 + E) * nth + nN))
    ma = 137.69 * (1 + E) * nth
    L = 0.9 * (o2out - o2in) / (20.95 - o2out)
    Tg = Tout + L * (1.005 / 1.05) * (Tout - Ta)
    Tr = Ta
    loss = (mdg * 1.02 * (Tg - Tr)
            + (9 * H + M) * (2501 + 1.88 * Tg - 4.19 * Tr)
            + ma * w * 1.88 * (Tg - Tr)
            + 33700 * u
            + 10110 * 28.010 * nC * x
            + 0.84 * 0.8 * A / (1 - lf) * (Tg - Tr)
            + 0.84 * 0.2 * A / (1 - lb) * (800 - Tr))
    pts = sorted(b['radiation_loss'], key=lambda p: p['load_fraction'])
    rad = np.interp(Q / float(b['rated_output_MW']),
                    [p['load_fraction'] for p in pts], [p['loss_pct'] for p in pts])
    eta = 100 - 100 * loss / HHV - rad
    Fk = 1000 * Q / (eta / 100 * HHV)

    d = pd.DataFrame({'date': h['date'], 'Q': Q, 'inp': 100 * Q / eta, 'c': 3.6 * Fk})
    g = d.groupby('date', sort=True).sum(min_count=1)
    res = pd.DataFrame({'date': g.index,
                        'efficiency_pct': np.round((100 * g['Q'] / g['inp']).values, 4),
                        'coal_t': np.round(g['c'].values, 3)})
    if os.path.lexists(out) and not os.path.isfile(out) or os.path.islink(out):
        os.unlink(out)
    tmp = out + '.tmp%d' % os.getpid()
    res.to_csv(tmp, index=False, float_format='%.4f')
    os.replace(tmp, out)
    for s in np.unique(seg):
        if assign[s] != logged[s]:
            print('filling %s: logged %s, fired as %s' % (bl['hour'][s], logged[s], assign[s]),
                  file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
