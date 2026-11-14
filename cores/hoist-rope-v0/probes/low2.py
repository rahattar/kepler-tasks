import sys, os
import numpy as np, pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}

def main(wd, out):
    cr = pd.read_csv(os.path.join(wd, 'cranes.csv'))
    sh = pd.read_csv(os.path.join(wd, 'sheaves.csv'))
    mv = pd.read_csv(os.path.join(wd, 'movements.csv'))
    sv = pd.read_csv(os.path.join(wd, 'surveys.csv'))
    for df in (cr, sh, mv, sv):
        df['crane'] = df['crane'].astype(str).str.strip()
    rows = []
    for _, c in cr.iterrows():
        name = c['crane']; n = float(c['falls']); H = float(c['upper_block_height_m'])
        L = float(c['rope_length_m'])
        b0, b1, b2, b3 = COEF[str(c['rope_construction']).strip()]
        m = mv[mv.crane == name]
        day = m['day'].to_numpy(float)
        h0 = m['from_height_m'].to_numpy(float); h1 = m['to_height_m'].to_numpy(float)
        S = (m['hook_load_t'].to_numpy(float) + float(c['block_mass_t'])) * 1000 * G / (n * float(c['reeving_efficiency']))
        s = sv[sv.crane == name]
        sdays = np.sort(s['day'].unique())
        last = s[s.day == sdays[-1]].sort_values('station_m')
        st = last['station_m'].to_numpy(float)
        # diameter matrix: survey x station (interpolated to last survey's stations)
        dmat = np.empty((len(sdays), len(st)))
        for i, sd in enumerate(sdays):
            q = s[s.day == sd].sort_values('station_m')
            dmat[i] = np.interp(st, q['station_m'].to_numpy(float), q['diameter_mm'].to_numpy(float))
        idx = np.searchsorted(sdays, day, side='right') - 1
        idx = np.clip(idx, 0, None)
        dam = np.zeros(len(st))
        lgS = np.log10(S)
        for _, k in sh[sh.crane == name].iterrows():
            p = float(k['parts']); a = float(k['offset_m']); D = float(k['diameter_mm']); w = float(k['bend_weight'])
            x0 = L - a - p * (H - h0); x1 = L - a - p * (H - h1)
            lo = np.minimum(x0, x1); hi = np.maximum(x0, x1)
            for j, x in enumerate(st):
                sel = (lo <= x) & (x <= hi) & (lo < hi)
                if not sel.any():
                    continue
                d = dmat[idx[sel], j]
                r = np.log10(D / d)
                lgN = b0 + (b1 + b3 * r) * (lgS[sel] - 2 * np.log10(d)) + b2 * r
                dam[j] += w * np.sum(10.0 ** (-lgN))
        for j in range(len(st)):
            rows.append(('%s-%03d' % (name, j + 1), dam[j]))
    with open(out, 'w') as f:
        f.write('row,damage\n')
        for r, v in rows:
            f.write('%s,%.6g\n' % (r, v))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
