#!/usr/bin/env python3
"""BE-3 boiler efficiency (HHV, losses method), day by day.

usage: python3 efficiency.py BOILER_DIR OUT_CSV

Besides the BE-3 arithmetic, the gas and fuel are checked against each other so
that the result is for the boiler "as it ran" (BE-3 s.1):
  * the coal fired: the bunker log is checked filling by filling against the
    flue-gas analysis (CO2 vs O2 for that coal's composition); a filling whose
    gas clearly belongs to another delivery is reassigned to it;
  * the excess air: taken from the CO2 analyser as BE-3 s.3 says, unless the
    CO2 reading is inconsistent with the two O2 probes (analyser fault/drift),
    in which case it is taken from the O2 probes.  A probe that disagrees with
    the other one and the CO2 is dropped.
"""
import sys, os, json
import numpy as np
import pandas as pd

DIAG = os.environ.get('BE3_DIAG')


def rolling_median(v, win):
    return pd.Series(v).rolling(win, center=True, min_periods=1).median().values


def main(bd, out):
    b = json.load(open(os.path.join(bd, 'boiler.json')))
    h = pd.read_csv(os.path.join(bd, 'hourly.csv'))
    dl = pd.read_csv(os.path.join(bd, 'deliveries.csv'))
    bl = pd.read_csv(os.path.join(bd, 'bunker_log.csv'))
    fa = pd.read_csv(os.path.join(bd, 'fly_ash.csv'))
    n = len(h)
    if n == 0:
        open(out, 'w').write('date,efficiency_pct,coal_t\n')
        return
    t = pd.to_datetime(h['hour'].str.strip(), format='%Y-%m-%d %H:%M').values
    date = pd.Series(pd.to_datetime(t).strftime('%Y-%m-%d'))
    bl_t = pd.to_datetime(bl['hour'].str.strip(), format='%Y-%m-%d %H:%M').values
    order = np.argsort(bl_t, kind='stable')
    bl_t = bl_t[order]
    bl_d = bl['delivery'].astype(str).str.strip().values[order]
    seg = np.searchsorted(bl_t, t, side='right') - 1
    seg = np.clip(seg, 0, len(bl_t) - 1)

    dl['delivery'] = dl['delivery'].astype(str).str.strip()
    names = list(dl['delivery'])
    K = len(names)
    kidx = {k: i for i, k in enumerate(names)}
    recv = pd.to_datetime(dl['received']).values
    comp = {c: dl[c].values.astype(float) for c in ['C', 'H', 'O', 'N', 'S', 'ash', 'moisture', 'hhv_kJ_kg']}

    # fly ash LOI per hour
    fam = dict(zip(fa['date'].astype(str).str.strip(), fa['loi'].astype(float)))
    lf = date.map(fam)
    if lf.isna().any():
        s = pd.Series(lf.values, index=date.values)
        lf = pd.Series(lf.values).ffill().bfill()
        if lf.isna().any():
            lf = lf.fillna(np.nanmean(list(fam.values())) if fam else 0.0)
    lf = lf.values.astype(float)
    lb = float(b['bottom_ash_loi'])

    co2 = h['co2_pct'].values.astype(float)
    co = h['co_ppm'].values.astype(float)
    oa = h['o2_a_pct'].values.astype(float)
    ob = h['o2_b_pct'].values.astype(float)
    r = co / (1e4 * co2)
    x = r / (1 + r)

    # per-hour, per-delivery combustion quantities (n x K)
    A = comp['ash'][None, :]
    u = A * (0.8 * lf[:, None] / (1 - lf[:, None]) + 0.2 * lb / (1 - lb))
    nC = (comp['C'][None, :] - u) / 12.011
    nH = (comp['H'] / 2.016)[None, :]
    nS = (comp['S'] / 32.06)[None, :]
    nO = (comp['O'] / 31.998)[None, :]
    nN = (comp['N'] / 28.013)[None, :]
    nth = nC + nH / 2 + nS - nO

    def o2_from_co2(co2v, xv):
        xx = xv[:, None]
        base = nC + nS + nN + 3.773 * nth + nC * xx / 2
        E = (100 * nC * (1 - xx) / co2v[:, None] - base) / (4.773 * nth)
        D = base + 4.773 * E * nth
        return 100 * (E * nth + nC * xx / 2) / D

    O2c = o2_from_co2(co2, x)            # n x K

    # ---- probe consensus
    logged = np.array([kidx.get(d, -1) for d in bl_d])
    if (logged < 0).any():               # unknown delivery name: take nearest earlier known
        for i in range(len(logged)):
            if logged[i] < 0:
                logged[i] = logged[i - 1] if i > 0 and logged[i - 1] >= 0 else 0
    assign = logged.copy()
    W = 25
    dab = rolling_median(oa - ob, W)
    rows = np.arange(n)

    def probe_value(asg):
        o2c = O2c[rows, asg[seg]]
        ra = rolling_median(oa - o2c, W)
        rb = rolling_median(ob - o2c, W)
        bad = np.abs(dab) > 0.25
        p = (oa + ob) / 2
        use_a = bad & (np.abs(ra) <= np.abs(rb))
        use_b = bad & ~use_a
        p = np.where(use_a, oa, np.where(use_b, ob, p))
        return p, bad

    # ---- coal identification, filling by filling
    nseg = len(bl_t)
    seg_date = pd.to_datetime(bl_t).normalize().values
    cand = recv[None, :] <= seg_date[:, None] + np.timedelta64(0, 'D')   # nseg x K
    present = np.bincount(seg, minlength=nseg) > 0
    segcount = np.maximum(np.bincount(seg, minlength=nseg), 1)
    BW = 24 * 21 + 1
    for it in range(4):
        p, _ = probe_value(assign)
        R = p[:, None] - O2c                       # n x K
        rcur = R[rows, assign[seg]]
        base = rolling_median(rcur, BW)
        dev = np.zeros((nseg, K))
        for k in range(K):
            dev[:, k] = np.bincount(seg, weights=R[:, k] - base, minlength=nseg) / segcount
        new = assign.copy()
        for s in range(nseg):
            if not present[s]:
                continue
            c = cand[s].copy()
            c[logged[s]] = True
            if abs(dev[s, logged[s]]) < 0.3:
                new[s] = logged[s]
                continue
            ad = np.where(c, np.abs(dev[s]), np.inf)
            best = ad.min()
            if not np.isfinite(best) or best > 0.3 or best > abs(dev[s, logged[s]]) - 0.3:
                new[s] = logged[s]
                continue
            ok = np.where(ad <= best + 0.1)[0]
            # among equally good, most recently received
            new[s] = ok[np.argmax(recv[ok])]
        if np.array_equal(new, assign) and it > 0:
            break
        assign = new
    kh = assign[seg]

    # ---- excess air
    p, badp = probe_value(assign)
    o2c = O2c[rows, kh]
    co2bad = np.abs(rolling_median(p - o2c, W)) > 0.15

    g = lambda a: a[rows, kh] if a.ndim == 2 and a.shape[1] == K else a[0, kh]
    nC1 = nC[rows, kh]; nth1 = nth[rows, kh]; u1 = u[rows, kh]
    nS1 = comp['S'][kh] / 32.06; nN1 = comp['N'][kh] / 28.013
    Hf = comp['H'][kh]; M = comp['moisture'][kh]; Af = comp['ash'][kh]; HHV = comp['hhv_kJ_kg'][kh]

    base0 = nC1 + nS1 + nN1 + 3.773 * nth1
    E_c = (100 * nC1 * (1 - x) / co2 - (base0 + nC1 * x / 2)) / (4.773 * nth1)
    # from O2 (dry fraction o): o*D = E nth + nC x/2, D = base0 + nC x/2 + 4.773 E nth
    xo = x.copy()
    for _ in range(3):
        o = p / 100
        E_o = (o * (base0 + nC1 * xo / 2) - nC1 * xo / 2) / (nth1 * (1 - 4.773 * o))
        D = base0 + nC1 * xo / 2 + 4.773 * E_o * nth1
        co2_true = 100 * nC1 * (1 - xo) / D
        rr = co / (1e4 * co2_true)
        xo = rr / (1 + rr)
    E = np.where(co2bad, E_o, E_c)
    x = np.where(co2bad, xo, x)
    D = base0 + nC1 * x / 2 + 4.773 * E * nth1
    o2in = np.where(co2bad, p, 100 * (E * nth1 + nC1 * x / 2) / D)

    mdg = (nC1 * (1 - x) * 44.010 + nC1 * x * 28.010 + nS1 * 64.060
           + (E * nth1 + nC1 * x / 2) * 31.998 + (3.773 * (1 + E) * nth1 + nN1) * 28.013)
    ma = 137.69 * (1 + E) * nth1

    o2o = h['o2_outlet_pct'].values.astype(float)
    L = 0.9 * (o2o - o2in) / (20.95 - o2o)
    To = h['gas_outlet_C'].values.astype(float)
    Ta = h['air_inlet_C'].values.astype(float)
    w = h['humidity_kg_kg'].values.astype(float)
    Tg = To + L * (1.005 / 1.05) * (To - Ta)
    Tr = Ta
    loss = (mdg * 1.02 * (Tg - Tr)
            + (9 * Hf + M) * (2501 + 1.88 * Tg - 4.19 * Tr)
            + ma * w * 1.88 * (Tg - Tr)
            + 33700 * u1
            + 10110 * 28.010 * nC1 * x
            + 0.84 * 0.8 * Af / (1 - lf) * (Tg - Tr)
            + 0.84 * 0.2 * Af / (1 - lb) * (800 - Tr))
    Q = h['heat_output_MW'].values.astype(float)
    pts = sorted(b['radiation_loss'], key=lambda q: q['load_fraction'])
    rl = np.interp(Q / float(b['rated_output_MW']), [q['load_fraction'] for q in pts],
                   [q['loss_pct'] for q in pts])
    eta = 100 - 100 * loss / HHV - rl
    F = 1000 * Q / (eta / 100 * HHV)

    df = pd.DataFrame({'date': date, 'Q': Q, 'qe': 100 * Q / eta, 'coal': 3600 * F / 1000})
    gr = df.groupby('date', sort=True)
    sQ = gr['Q'].sum(); sqe = gr['qe'].sum(); sc = gr['coal'].sum()
    res = pd.DataFrame({'date': sQ.index, 'efficiency_pct': (100 * sQ / sqe).values, 'coal_t': sc.values})
    res.to_csv(out, index=False, float_format='%.4f')

    if DIAG:
        ch = np.where(assign != logged)[0]
        for s in ch:
            print('reassigned', str(bl_t[s])[:16], bl_d[s], '->', names[assign[s]], file=sys.stderr)
        print('co2 bad hours', int(co2bad.sum()), 'probe-disagree hours', int(badp.sum()), file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
