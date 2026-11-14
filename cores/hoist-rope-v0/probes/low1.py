import sys, os
import numpy as np, pandas as pd
G = 9.80665
B = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}

def main(wd, out):
    rd = lambda f: pd.read_csv(os.path.join(wd, f), skipinitialspace=True)
    cr, sh, mv, sv = rd('cranes.csv'), rd('sheaves.csv'), rd('movements.csv'), rd('surveys.csv')
    for df in (cr, sh, mv, sv):
        df.columns = [c.strip() for c in df.columns]
        df['crane'] = df['crane'].astype(str).str.strip()
    sh['sheave'] = sh['sheave'].astype(str).str.strip()
    rows = []
    for _, c in cr.iterrows():
        name = c['crane']; n = float(c['falls']); H = float(c['upper_block_height_m'])
        L = float(c['rope_length_m']); b0, b1, b2, b3 = B[str(c['rope_construction']).strip().lower()]
        s = sv[sv.crane == name]
        days = np.sort(s['day'].unique())
        last = s[s.day == days[-1]].sort_values('station_m')
        st = last['station_m'].to_numpy(float)
        K = len(st)
        # diameter at each final station for every survey (interpolated along rope)
        dmat = np.empty((len(days), K))
        for i, dy in enumerate(days):
            si = s[s.day == dy].sort_values('station_m')
            dmat[i] = np.interp(st, si['station_m'].to_numpy(float), si['diameter_mm'].to_numpy(float))
        m = mv[mv.crane == name]
        md = m['day'].to_numpy(float)
        h0 = m['from_height_m'].to_numpy(float); h1 = m['to_height_m'].to_numpy(float)
        S = (m['hook_load_t'].to_numpy(float) + float(c['block_mass_t'])) * 1000 * G / (n * float(c['reeving_efficiency']))
        lgS = np.log10(S)
        idx = np.searchsorted(days, md, side='right') - 1
        idx = np.clip(idx, 0, len(days) - 1)
        dmg = np.zeros(K)
        for _, q in sh[sh.crane == name].iterrows():
            p = float(q['parts']); a = float(q['offset_m']); D = float(q['diameter_mm']); w = float(q['bend_weight'])
            xa = L - a - p * (H - h0); xb = L - a - p * (H - h1)
            lo = np.minimum(xa, xb); hi = np.maximum(xa, xb)
            for i in range(len(days)):
                sel = idx == i
                if not sel.any(): continue
                d = dmat[i]; l = np.log10(D / d); lgd2 = 2 * np.log10(d)
                lo_i, hi_i, lgS_i = lo[sel], hi[sel], lgS[sel]
                for k in range(K):
                    pas = (lo_i <= st[k]) & (st[k] < hi_i)
                    if not pas.any(): continue
                    lgN = b0 + (b1 + b3 * l[k]) * (lgS_i[pas] - lgd2[k]) + b2 * l[k]
                    dmg[k] += w * np.sum(10.0 ** (-lgN))
        for k in range(K):
            rows.append((f"{name}-{k+1:03d}", dmg[k]))
    pd.DataFrame(rows, columns=['row', 'damage']).to_csv(out, index=False, float_format='%.8g')

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
