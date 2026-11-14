import sys, os
import numpy as np, pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}


def main(wd, out):
    cr = pd.read_csv(os.path.join(wd, 'cranes.csv'), skipinitialspace=True)
    sh = pd.read_csv(os.path.join(wd, 'sheaves.csv'), skipinitialspace=True)
    mv = pd.read_csv(os.path.join(wd, 'movements.csv'), skipinitialspace=True)
    sv = pd.read_csv(os.path.join(wd, 'surveys.csv'), skipinitialspace=True)
    for df in (cr, sh, mv, sv):
        df.columns = [c.strip() for c in df.columns]
        df['crane'] = df['crane'].astype(str).str.strip()
    rows = []
    for _, c in cr.iterrows():
        name = c['crane']; n = float(c['falls']); H = float(c['upper_block_height_m'])
        L = float(c['rope_length_m']); e = float(c['reeving_efficiency'])
        mb = float(c['block_mass_t'])
        b0, b1, b2, b3 = COEF[str(c['rope_construction']).strip()]
        s = sv[sv.crane == name]
        if len(s) == 0:
            continue
        days = np.sort(s.day.unique())
        lastst = np.sort(s[s.day == days[-1]].station_m.to_numpy(float))
        # diameter table: survey index x station (fill from nearest survey if missing)
        piv = s.pivot_table(index='day', columns='station_m', values='diameter_mm', aggfunc='mean')
        piv = piv.reindex(index=days, columns=lastst).ffill().bfill()
        dtab = piv.to_numpy(float)  # (nsurv, nst)
        m = mv[mv.crane == name]
        dmg = np.zeros(len(lastst))
        if len(m):
            day = m.day.to_numpy(float)
            h0 = m.from_height_m.to_numpy(float); h1 = m.to_height_m.to_numpy(float)
            S = (m.hook_load_t.to_numpy(float) + mb) * 1000.0 * G / (n * e)
            si = np.searchsorted(days, day, side='right') - 1
            si = np.clip(si, 0, len(days) - 1)
            d = dtab[si]  # (nm, nst)
            lgS = np.log10(S)[:, None] - 2 * np.log10(d)
            x = lastst[None, :]
            for _, r in sh[sh.crane == name].iterrows():
                p = float(r['parts']); a = float(r['offset_m']); D = float(r['diameter_mm'])
                w = float(r['bend_weight'])
                xa = L - a - p * (H - h0); xb = L - a - p * (H - h1)
                lo = np.minimum(xa, xb)[:, None]; hi = np.maximum(xa, xb)[:, None]
                hit = (x >= lo) & (x <= hi) & (hi > lo)
                if not hit.any():
                    continue
                lgDd = np.log10(D / d)
                lgN = b0 + (b1 + b3 * lgDd) * lgS + b2 * lgDd
                dmg += np.where(hit, w * 10.0 ** (-lgN), 0.0).sum(0)
        for k, v in enumerate(dmg):
            rows.append(('%s-%03d' % (name, k + 1), v))
    pd.DataFrame(rows, columns=['row', 'damage']).to_csv(out, index=False, float_format='%.8g')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
