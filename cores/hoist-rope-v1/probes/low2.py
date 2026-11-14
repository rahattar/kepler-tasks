import sys, os
import numpy as np, pandas as pd
G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}

def main(wd, out):
    rd = lambda f: pd.read_csv(os.path.join(wd, f), skipinitialspace=True)
    cr, sh, mv, sv = rd('cranes.csv'), rd('sheaves.csv'), rd('movements.csv'), rd('surveys.csv')
    for df in (cr, sh, mv, sv):
        df.columns = [c.strip() for c in df.columns]
        df['crane'] = df['crane'].astype(str).str.strip()
    rows = []
    for _, c in cr.iterrows():
        name = c['crane']; n = float(c['falls']); H = float(c['upper_block_height_m'])
        L = float(c['rope_length_m'])
        b0, b1, b2, b3 = COEF[str(c['rope_construction']).strip().lower()]
        s = sv[sv.crane == name]
        days = np.sort(s['day'].unique())
        last = s[s.day == days[-1]].sort_values('station_m')
        st = last['station_m'].to_numpy(float)
        # diameter table: survey index x station
        D = np.empty((len(days), len(st)))
        for i, dday in enumerate(days):
            si = s[s.day == dday]
            D[i] = np.interp(st, si['station_m'].to_numpy(float)[np.argsort(si['station_m'].to_numpy(float))],
                             si.sort_values('station_m')['diameter_mm'].to_numpy(float))
        m = mv[mv.crane == name]
        md = m['day'].to_numpy(float)
        h1 = m['from_height_m'].to_numpy(float); h2 = m['to_height_m'].to_numpy(float)
        S = (m['hook_load_t'].to_numpy(float) + float(c['block_mass_t'])) * 1000 * G / (n * float(c['reeving_efficiency']))
        si = np.searchsorted(days, md + 1e-9, side='right') - 1
        si = np.clip(si, 0, None)
        dam = np.zeros(len(st))
        for _, q in sh[sh.crane == name].iterrows():
            p = float(q['parts']); a = float(q['offset_m']); Dm = float(q['diameter_mm']); w = float(q['bend_weight'])
            x1 = L - a - p * (H - h1); x2 = L - a - p * (H - h2)
            lo = np.minimum(x1, x2); hi = np.maximum(x1, x2)
            for k0 in range(0, len(md), 20000):
                sl = slice(k0, k0 + 20000)
                mask = (st[None, :] >= lo[sl, None]) & (st[None, :] <= hi[sl, None]) & (hi[sl, None] > lo[sl, None])
                d = D[si[sl]]
                r = np.log10(Dm / d)
                lgN = b0 + (b1 + b3 * r) * np.log10(S[sl, None] / d**2) + b2 * r
                dam += (mask * w * 10.0 ** (-lgN)).sum(0)
        for j in range(len(st)):
            rows.append((f"{name}-{j+1:03d}", dam[j]))
    pd.DataFrame(rows, columns=['row', 'damage']).to_csv(out, index=False, float_format='%.6e')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
