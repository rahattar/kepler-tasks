"""RS-4 bending damage of hoist ropes, one works package.

python3 ropes.py WORKS_DIR OUT_CSV

The surveys are also used to follow each rope element through events the
package does not log explicitly:
  * rope turned end for end (profile of a survey matches the mirror image of
    the previous one): positions x -> L - x from the moment of the turn;
  * rope renewed (diameters jump up): damage counts only from the renewal.
The moment of such an event inside the survey interval is estimated from how
well the measured wear in that interval matches the bendings.
"""
import sys, os
import numpy as np, pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}


def read(wd, f):
    df = pd.read_csv(os.path.join(wd, f), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()
    return df


def bend_matrix(sheaves, L, H, h1, h2, lgS, b, pos, lgd):
    """damage per movement (rows) and element (cols); pos, lgd shape (M,K)."""
    b0, b1, b2, b3 = b
    out = np.zeros(pos.shape)
    for p, a, D, w in sheaves:
        x1 = L - a - p * (H - h1); x2 = L - a - p * (H - h2)
        lo = np.minimum(x1, x2)[:, None]; hi = np.maximum(x1, x2)[:, None]
        ins = (pos >= lo) & (pos <= hi) & (hi > lo)
        if not ins.any():
            continue
        lgDd = np.log10(D) - lgd
        lgN = b0 + (b1 + b3 * lgDd) * (lgS[:, None] - 2 * lgd) + b2 * lgDd
        out += np.where(ins, w * 10.0 ** (-lgN), 0.0)
    return out


def crane_damage(c, sh, m, s):
    n = float(c['falls']); H = float(c['upper_block_height_m']); L = float(c['rope_length_m'])
    b = COEF[str(c['rope_construction']).strip()]
    sheaves = [(float(r['parts']), float(r['offset_m']), float(r['diameter_mm']), float(r['bend_weight']))
               for _, r in sh.iterrows()]
    m = m.iloc[np.argsort(m['day'].values, kind='stable')]
    day = m['day'].values.astype(float)
    h1 = m['from_height_m'].values.astype(float); h2 = m['to_height_m'].values.astype(float)
    S = (m['hook_load_t'].values.astype(float) + float(c['block_mass_t'])) * 1000 * G / (n * float(c['reeving_efficiency']))
    lgS = np.log10(S)
    sdays = np.sort(s['day'].unique())
    prof = []
    for dd in sdays:
        q = s[s.day == dd].sort_values('station_m')
        q = q.groupby('station_m', as_index=False)['diameter_mm'].mean()
        prof.append((q['station_m'].values.astype(float), q['diameter_mm'].values.astype(float)))
    st = prof[-1][0]
    K = len(st)

    def at(i, x):
        return np.interp(x, prof[i][0], prof[i][1])

    # ---- events between surveys
    events = []  # (index of later survey, kind)
    for i in range(1, len(sdays)):
        xs = prof[i][0]; bnew = prof[i][1]
        e_id = np.abs(bnew - at(i - 1, xs)).mean()
        e_rv = np.abs(bnew - at(i - 1, L - xs)).mean()
        rise = np.mean(bnew - at(i - 1, xs if e_id <= e_rv else L - xs))
        if rise > 0.08:
            events.append((i, 'renew'))
        elif e_rv < 0.6 * e_id and e_id - e_rv > 0.05:
            events.append((i, 'reverse'))

    # flip state after each survey, for the whole rope, ignoring timing (piecewise)
    def wear_fit(i, kind, flip_before):
        """estimate time of the event between survey i-1 and i."""
        t0, t1 = sdays[i - 1], sdays[i]
        sel = (day >= t0) & (day < t1)
        if sel.sum() < 2:
            return 0.5 * (t0 + t1)
        idx = np.nonzero(sel)[0]
        xs = prof[i][0]
        pos = np.broadcast_to(xs, (len(idx), len(xs)))
        lgd = np.broadcast_to(np.log10(np.mean(prof[i - 1][1])), pos.shape)
        R = bend_matrix(sheaves, L, H, h1[idx], h2[idx], lgS[idx], b, pos, lgd)  # fixed positions
        C = np.vstack([np.zeros(len(xs)), np.cumsum(R, 0)])
        tot = C[-1]
        times = np.r_[day[idx], t1]
        if kind == 'reverse':
            inc = at(i - 1, L - xs) - prof[i][1]
            # element at new x was at L - x before the turn
            Cr = np.vstack([np.interp(L - xs, xs, row) for row in C])
            best, bt = -2, 0.5 * (t0 + t1)
            for j in range(0, len(C), max(1, len(C) // 200)):
                pred = Cr[j] + tot - C[j]
                if pred.std() == 0 or inc.std() == 0:
                    continue
                r = np.corrcoef(inc, pred)[0, 1]
                if r > best:
                    best, bt = r, times[j] if j < len(idx) else t1
            return bt
        else:
            # renewal: amplitude from the wear/damage ratio of the next interval
            if i + 1 < len(sdays):
                sel2 = (day >= sdays[i]) & (day < sdays[i + 1])
                if sel2.sum() > 0:
                    idx2 = np.nonzero(sel2)[0]
                    pos2 = np.broadcast_to(xs, (len(idx2), len(xs)))
                    R2 = bend_matrix(sheaves, L, H, h1[idx2], h2[idx2], lgS[idx2], b, pos2,
                                     np.broadcast_to(np.log10(np.mean(prof[i][1])), pos2.shape)).sum(0)
                    w2 = np.clip(prof[i][1] - at(i + 1, xs), 0, None)
                    if R2.sum() > 0 and w2.sum() > 0:
                        ratio = w2.sum() / R2.sum()
                        new0 = np.max([np.percentile(p[1], 95) for p in prof[:1]])
                        wear = np.clip(new0 - prof[i][1], 0, None).sum()
                        need = wear / ratio
                        rem = tot.sum() - C.sum(1)
                        j = int(np.argmin(np.abs(rem - need)))
                        return times[j] if j < len(idx) else t1
            return 0.5 * (t0 + t1)

    flip = 0
    timeline = []  # (time, kind)
    for i, kind in events:
        t = wear_fit(i, kind, flip)
        timeline.append((t, kind))
        if kind == 'reverse':
            flip ^= 1
    start = -np.inf
    for t, kind in timeline:
        if kind == 'renew':
            start = t
    # number of reversals after a time -> parity
    rev_t = np.array([t for t, k in timeline if k == 'reverse' and t >= start])

    def flipped(t):  # is element position mirrored at time t relative to final
        return (len(rev_t) - np.searchsorted(rev_t, t, side='right')) % 2

    # diameters per survey at each element's position at that survey
    dtab = np.empty((len(sdays), K))
    for i, dd in enumerate(sdays):
        f = flipped(dd)
        dtab[i] = at(i, L - st if f else st)
    lgdt = np.log10(dtab)
    sidx = np.clip(np.searchsorted(sdays, day, side='right') - 1, 0, None)
    use = day >= start
    fm = flipped(day).astype(bool)
    dmg = np.zeros(K)
    CH = 20000
    ids = np.nonzero(use)[0]
    for a0 in range(0, len(ids), CH):
        ii = ids[a0:a0 + CH]
        pos = np.where(fm[ii][:, None], L - st[None, :], st[None, :])
        dmg += bend_matrix(sheaves, L, H, h1[ii], h2[ii], lgS[ii], b, pos, lgdt[sidx[ii]]).sum(0)
    return st, dmg, timeline


def main(wd, out):
    cr = read(wd, 'cranes.csv'); sh = read(wd, 'sheaves.csv')
    mv = read(wd, 'movements.csv'); sv = read(wd, 'surveys.csv')
    rows = []
    for _, c in cr.iterrows():
        name = str(c['crane'])
        st, dmg, tl = crane_damage(c, sh[sh.crane == name], mv[mv.crane == name], sv[sv.crane == name])
        if os.environ.get('ROPES_DEBUG'):
            print(name, tl, file=sys.stderr)
        for k in range(len(st)):
            rows.append((f"{name}-{k + 1:03d}", dmg[k]))
    pd.DataFrame(rows, columns=['row', 'damage']).to_csv(out, index=False, float_format='%.8g')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
