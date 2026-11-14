import sys, numpy as np, pandas as pd
from math import factorial
G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}
K = 16

def clean(g):
    g = g.dropna(subset=['station_m', 'diameter_mm'])
    g = g.groupby('station_m', as_index=False).diameter_mm.median().sort_values('station_m')
    x = g.station_m.values.astype(float); d = g.diameter_mm.values.astype(float)
    med = np.median(d)
    bad = (np.abs(d - med) > 0.1 * med) | (d <= 0)
    if bad.any() and (~bad).sum() >= 2:
        d[bad] = np.interp(x[bad], x[~bad], d[~bad])
    return x, d

def surveys(s, L):
    s = s.dropna(subset=['day'])
    sdays = np.sort(s.day.unique())
    data = [clean(s[s.day == dd]) for dd in sdays]
    nL = int(round(L))
    xl, dl = data[-1]
    if len(xl) == nL:
        st = 0.5 + np.arange(nL)
    else:
        st = xl
    dia = []
    prev = None
    for x, d in data:
        if len(x) == len(st):
            v = d.copy()
            if prev is not None:
                a = v - v.mean(); b = prev - prev.mean()
                if np.dot(a[::-1], b) > np.dot(a, b) + 0.2 * np.linalg.norm(a) * np.linalg.norm(b):
                    v = v[::-1]
        else:
            v = np.interp(st, x, d)
        dia.append(v); prev = v
    # orient everything consistently with the last survey's ordering is assumed
    return np.array(dia), sdays, st

def main(wd, out):
    cr = pd.read_csv(wd + '/cranes.csv'); sh = pd.read_csv(wd + '/sheaves.csv')
    mv = pd.read_csv(wd + '/movements.csv'); sv = pd.read_csv(wd + '/surveys.csv')
    for df in (cr, sh, mv, sv):
        df.columns = [c.strip() for c in df.columns]
        df['crane'] = df['crane'].astype(str).str.strip()
    rows = []
    for _, c in cr.iterrows():
        name = c.crane; n = float(c.falls); H = float(c.upper_block_height_m); L = float(c.rope_length_m)
        b0, b1, b2, b3 = COEF[str(c.rope_construction).strip()]
        m = mv[mv.crane == name]
        m = m.iloc[np.argsort(m.day.values, kind='stable')]
        day = m.day.values.astype(float); h0 = m.from_height_m.values.astype(float); h1 = m.to_height_m.values.astype(float)
        S = np.maximum(m.hook_load_t.values.astype(float) + float(c.block_mass_t), 1e-6) * 1000 * G / (n * float(c.reeving_efficiency))
        lgS = np.log10(S)
        dia, sdays, st = surveys(sv[sv.crane == name], L)
        ns = len(st)
        ep = np.searchsorted(sdays, day, side='right') - 1
        ep = np.clip(ep, 0, len(sdays) - 1)
        lgd = np.log10(dia)  # (E, ns)
        dmg = np.zeros(ns)
        lc = 0.5 * (lgS.min() + lgS.max())
        ld = lgS - lc
        tmax = 3.5 * float(np.abs(ld).max()) * np.log(10)
        Kc = 2
        while Kc < 40 and tmax ** (Kc + 1) / factorial(Kc + 1) > 1e-7 * np.exp(-tmax):
            Kc += 1
        pw = [np.ones_like(ld)]
        for k in range(Kc):
            pw.append(pw[-1] * ld)
        for _, r in sh[sh.crane == name].iterrows():
            p = float(r.parts); a = float(r.offset_m); D = float(r.diameter_mm); w = float(r.bend_weight)
            x0 = L - a - p * (H - h0); x1 = L - a - p * (H - h1)
            lo = np.minimum(x0, x1); hi = np.maximum(x0, x1)
            i0 = np.searchsorted(st, lo, side='left'); i1 = np.searchsorted(st, hi, side='right')
            lr = np.log10(D) - lgd  # (E, ns)
            B = b1 + b3 * lr
            A = b0 + b2 * lr - 2 * lgd * B
            # lgN = A + B*lgS = A + B*lc + B*ld ; 1/N = 10^-(A+B lc) * exp(-B ln10 ld)
            E = len(sdays); nb = E * (ns + 1)
            sel = i1 > i0
            j0 = ep[sel] * (ns + 1) + i0[sel]; j1 = ep[sel] * (ns + 1) + i1[sel]
            t = -B * np.log(10)
            ser = np.zeros((E, ns))
            for k in range(Kc + 1):
                wk = pw[k][sel]
                mk = (np.bincount(j0, wk, nb) - np.bincount(j1, wk, nb)).reshape(E, ns + 1)
                mk = np.cumsum(mk, axis=1)[:, :ns]
                ser += mk * t ** k / factorial(k)
            dmg += w * (10 ** (-(A + B * lc)) * ser).sum(axis=0)
        for i in range(ns):
            rows.append('%s-%03d,%s' % (name, i + 1, np.format_float_positional(float(dmg[i]), precision=8, unique=False, fractional=False, trim='0')))
    import os
    if os.path.islink(out) or os.path.exists(out):
        os.unlink(out)
    with open(out, 'w') as f:
        f.write('row,damage\n' + '\n'.join(rows) + '\n')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
