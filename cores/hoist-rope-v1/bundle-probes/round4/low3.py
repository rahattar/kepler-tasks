import sys, os, math
import numpy as np, pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}
ORDER = 8

def main():
    wd, out = sys.argv[1], sys.argv[2]
    cr = pd.read_csv(os.path.join(wd, 'cranes.csv'), skipinitialspace=True)
    sh = pd.read_csv(os.path.join(wd, 'sheaves.csv'), skipinitialspace=True)
    mv = pd.read_csv(os.path.join(wd, 'movements.csv'), skipinitialspace=True)
    sv = pd.read_csv(os.path.join(wd, 'surveys.csv'), skipinitialspace=True)
    for df in (cr, sh, mv, sv):
        df.columns = [c.strip() for c in df.columns]
        df['crane'] = df['crane'].astype(str).str.strip()
    lines = ['row,damage']
    for _, c in cr.iterrows():
        name = c['crane']; n = float(c['falls']); H = float(c['upper_block_height_m'])
        L = float(c['rope_length_m']); e = float(c['reeving_efficiency']); mb = float(c['block_mass_t'])
        b0, b1, b2, b3 = COEF[str(c['rope_construction']).strip()]
        s = sv[sv.crane == name]
        days = np.sort(s['day'].unique())
        last = s[s.day == days[-1]].sort_values('station_m')
        xs = last['station_m'].to_numpy(float)
        ns = len(xs)
        # diameter table per survey, at last-survey stations (nearest station)
        dtab = np.empty((len(days), ns))
        for i, dd in enumerate(days):
            t = s[s.day == dd].sort_values('station_m')
            tx = t['station_m'].to_numpy(float); td = t['diameter_mm'].to_numpy(float)
            j = np.clip(np.searchsorted(tx, xs), 1, len(tx) - 1) if len(tx) > 1 else np.zeros(ns, int)
            if len(tx) > 1:
                j = np.where(np.abs(tx[j - 1] - xs) <= np.abs(tx[j] - xs), j - 1, j)
            dtab[i] = td[j]
        m = mv[mv.crane == name]
        md = m['day'].to_numpy(float)
        h1 = m['from_height_m'].to_numpy(float); h2 = m['to_height_m'].to_numpy(float)
        S = (m['hook_load_t'].to_numpy(float) + mb) * 1000.0 * G / (n * e)
        lgS = np.log10(S)
        # epoch: last survey not later than movement
        ep = np.searchsorted(days, md, side='right') - 1
        ep = np.clip(ep, 0, len(days) - 1)
        hlo = np.minimum(h1, h2); hhi = np.maximum(h1, h2)
        dmg = np.zeros(ns)
        csh = sh[sh.crane == name]
        for _, r in csh.iterrows():
            p = float(r['parts']); a = float(r['offset_m']); D = float(r['diameter_mm']); w = float(r['bend_weight'])
            # x = L - a - p(H-h); increasing in h
            xlo = L - a - p * (H - hlo); xhi = L - a - p * (H - hhi)
            i0 = np.searchsorted(xs, xlo, side='right')  # first station > xlo
            i1 = np.searchsorted(xs, xhi, side='right')  # stations <= xhi ... use (xlo, xhi]
            for k in range(len(days)):
                sel = (ep == k) & (i1 > i0)
                if not sel.any():
                    continue
                d = dtab[k]
                rr = np.log10(D / d)
                kk = b1 + b3 * rr                    # exponent per station
                # 1/N = 10^-(b0 + b2 rr + kk*(lgS - 2 lgd))
                base = -(b0 + b2 * rr) + 2 * kk * np.log10(d)
                ls = lgS[sel]; a0 = i0[sel]; a1 = i1[sel]
                k0 = kk.mean(); c0 = ls.mean()
                u = ls - c0
                f = 10.0 ** (-k0 * ls)
                dk = -(kk - k0) * math.log(10.0)  # per station
                acc = np.zeros(ns)
                term = f.copy()
                fact = 1.0
                for q in range(ORDER + 1):
                    if q > 0:
                        term = term * u; fact *= q
                    diff = np.bincount(a0, term, ns + 1) - np.bincount(a1, term, ns + 1)
                    acc += np.cumsum(diff)[:ns] * dk ** q / fact
                # exp(dk*(ls)) = exp(dk*c0) * sum (dk u)^q/q!
                dmg += w * 10.0 ** base * np.exp(dk * c0) * acc
        for j in range(ns):
            lines.append('%s-%03d,%.9f' % (name, j + 1, dmg[j]))
    tmp = out + '.tmp'
    with open(tmp, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    if os.path.islink(out):
        os.unlink(out)
    os.replace(tmp, out)

if __name__ == '__main__':
    main()
