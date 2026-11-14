import numpy as np

RHO = 7800.0
KT = [20, 300, 600, 800, 900.]
KV = {'C45': [50, 44, 34, 26, 26.], '42CrMo4': [43, 40, 33, 27, 27.]}
CT = [20, 300, 600, 720, 800, 900.]
CV = {'C45': [470, 560, 750, 900, 650, 650.], '42CrMo4': [460, 550, 720, 850, 640, 640.]}
TMIN, TMAX = -50, 1000
NT = TMAX - TMIN + 1
STEELS = ['C45', '42CrMo4']


def _tables():
    g = np.arange(TMIN, TMAX + 1, dtype=float)
    k = []; c = []; H = []
    for s in STEELS:
        kk = np.interp(g, KT, KV[s]); cc = np.interp(g, CT, CV[s])
        hh = np.concatenate([[0], np.cumsum(0.5 * (cc[1:] + cc[:-1]))])
        k.append(kk); c.append(cc); H.append(hh)
    k = np.concatenate(k); c = np.concatenate(c); H = np.concatenate(H)
    dk = np.append(np.diff(k), 0); dc = np.append(np.diff(c), 0)
    return k, dk, c, dc, H


KTAB, DKTAB, CTAB, DCTAB, HTAB = _tables()


def _idx(T, base):
    x = np.clip(T, TMIN, TMAX - 1e-9) - TMIN
    i = x.astype(np.int64)
    u = x - i
    return i + base, u


def hcoef(ts, hx, hy):
    """h and dh/dTs at surface temps ts (B,), knots hx,hy (4,B)"""
    h = np.where(ts <= hx[0], hy[0], hy[3])
    dh = np.zeros_like(ts)
    for j in range(3):
        s = (hy[j+1] - hy[j]) / (hx[j+1] - hx[j])
        m = (ts > hx[j]) & (ts <= hx[j+1])
        h = np.where(m, hy[j] + s * (ts - hx[j]), h)
        dh = np.where(m, s, dh)
    return h, dh


def solve(c45, R, Tf, Tb, hp, h300, Tcr, N=30, dTstep=3.0, iters=2, th=0.5):
    B = len(R)
    R = np.asarray(R, float); Tf = np.asarray(Tf, float); Tb = np.asarray(Tb, float)
    base = np.where(np.asarray(c45), 0, NT)[None, :]
    hx = np.stack([np.full(B, 100.), np.full(B, 300.), Tcr, Tcr + 120])
    hy = np.stack([0.6 * h300, h300, hp, 0.15 * hp])
    xi = np.linspace(0, 1, N + 1); dxi = xi[1]
    vol = np.empty(N + 1); vol[0] = dxi**2 / 8; vol[1:N] = xi[1:N] * dxi; vol[N] = (1 - dxi / 4) * dxi / 2
    face = (xi[:-1] + xi[1:]) / 2
    RV = RHO * vol[:, None] * R[None, :]**2          # (N+1,B)
    G = (face / dxi)[:, None]                         # (N,1)
    A = R
    T = np.repeat(Tf[None, :], N + 1, 0)
    t = np.zeros(B); dt = np.full(B, 0.01)
    done = np.zeros(B, bool)
    targets = [800., 725., 675., 500., 150.]
    tc = np.full((5, B), np.nan)
    dTmax = np.zeros(B); ts500 = np.full(B, np.nan)
    it = 0
    while True:
        it += 1
        To = T
        i, u = _idx(To, base)
        Ho = HTAB[i] + CTAB[i] * u + 0.5 * DCTAB[i] * u * u
        Tm = 0.5 * (To[1:] + To[:-1])
        j, v = _idx(Tm, base[:, :]) if True else None
        Co = G * (KTAB[j] + DKTAB[j] * v)
        flo = Co * (To[1:] - To[:-1])
        Lo = np.zeros_like(To)
        Lo[:-1] += flo; Lo[1:] -= flo
        hs, _ = hcoef(To[N], hx, hy)
        Lo[N] -= A * hs * (To[N] - Tb)
        Tn = To.copy()
        rdt = 1.0 / dt
        for _ in range(iters):
            i, u = _idx(Tn, base)
            Hn = HTAB[i] + CTAB[i] * u + 0.5 * DCTAB[i] * u * u
            cp = CTAB[i] + DCTAB[i] * u
            Tm = 0.5 * (Tn[1:] + Tn[:-1])
            j, v = _idx(Tm, base)
            C = th * G * (KTAB[j] + DKTAB[j] * v)
            ts = Tn[N]
            hs, dhs = hcoef(ts, hx, hy)
            F = RV * (Hn - Ho) * rdt - (1 - th) * Lo
            fl = C * (Tn[1:] - Tn[:-1])
            F[:-1] -= fl; F[1:] += fl
            F[N] += th * A * hs * (ts - Tb)
            dg = RV * cp * rdt
            dg[:-1] += C; dg[1:] += C
            dg[N] += th * A * (hs + dhs * (ts - Tb))
            Tn = Tn + thomas(-C, dg, -F)
        T = Tn
        act = ~done
        c0 = To[0]; c1 = T[0]
        for k, Tt in enumerate(targets):
            m = act & np.isnan(tc[k]) & (c1 <= Tt)
            if m.any():
                f = (c0[m] - Tt) / (c0[m] - c1[m])
                tc[k, m] = t[m] + f * dt[m]
                if k == 3:
                    ts500[m] = To[N, m] + f * (T[N, m] - To[N, m])
        dTmax = np.where(act, np.maximum(dTmax, T[0] - T[N]), dTmax)
        t = np.where(act, t + dt, t)
        done = done | ~np.isnan(tc[4])
        if done.all() or it > 100000:
            break
        ch = np.abs(T - To).max(0)
        dt = dt * np.clip(dTstep / np.maximum(ch, 1e-9), 0.5, 1.5)
    return dict(t85=tc[3] - tc[0], cr700=50 / (tc[2] - tc[1]), dTmax=dTmax, ts500=ts500, t150=tc[4], steps=it)


def thomas(off, b, d):
    """symmetric tridiagonal: off (N,B) couples i,i+1; b (N+1,B)"""
    n = b.shape[0]
    cp = np.empty_like(off); dp = np.empty_like(d)
    den = b[0]
    cp[0] = off[0] / den; dp[0] = d[0] / den
    for i in range(1, n):
        den = b[i] - off[i-1] * cp[i-1]
        if i < n - 1:
            cp[i] = off[i] / den
        dp[i] = (d[i] - off[i-1] * dp[i-1]) / den
    x = np.empty_like(d)
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i+1]
    return x


# ---------------------------------------------------------------- oil
import sys, os, json, subprocess
import pandas as pd
from datetime import date as _date

FIG = ['cr_max_K_s', 't_crmax_C', 'cr_300_K_s']


def dnum(s):
    y, m, d = map(int, str(s)[:10].split('-'))
    return _date(y, m, d).toordinal()


def rel(a, b):
    return max(abs(a[0] / b[0] - 1), abs(a[2] / b[2] - 1), abs(a[1] - b[1]) / 400.0)


def build_charges(tanks, systems, samples):
    """group tanks into charges: register system, split by disagreeing analyses"""
    reg = dict(zip(tanks.tank, tanks.oil_system))
    bytank = {}
    for r in samples.itertuples():
        bytank.setdefault(r.sampled_at, []).append((dnum(r.date), np.array([r.cr_max_K_s, r.t_crmax_C, r.cr_300_K_s], float)))
    charges = []  # list of dict(system, tanks, split)

    def agree(a, b):
        sa = bytank.get(a, []); sb = bytank.get(b, [])
        best = None
        for da, fa in sa:
            for db, fb in sb:
                gap = abs(da - db) / 182.0
                tol = 0.012 + 0.006 * gap
                ok = rel(fa, fb) <= tol
                if gap < 0.1:
                    return ok
                if best is None or gap < best[0]:
                    best = (gap, ok)
        return None if best is None else best[1]

    for sysname in systems.oil_system:
        ts = [t for t in tanks.tank if reg[t] == sysname]
        groups = []
        nos = []
        for t in ts:
            if t not in bytank:
                nos.append(t); continue
            placed = False
            for g in groups:
                votes = [agree(t, o) for o in g]
                votes = [v for v in votes if v is not None]
                if votes and sum(votes) * 2 >= len(votes):
                    g.append(t); placed = True; break
            if not placed:
                groups.append([t])
        if not groups:
            groups = [[]]
        groups.sort(key=len, reverse=True)
        groups[0].extend(nos)
        for k, g in enumerate(groups):
            if g:
                charges.append(dict(system=sysname, tanks=g, main=(k == 0)))
    return charges, bytank


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, 'site.json')))
    nlab = int(site.get('lab_samples', 0))
    dlab = dnum(site['samples_drawn'])
    tanks = pd.read_csv(os.path.join(pkg, 'tanks.csv'), dtype=str)
    systems = pd.read_csv(os.path.join(pkg, 'oil_systems.csv'), dtype=str)
    log = pd.read_csv(os.path.join(pkg, 'oil_log.csv'), dtype=str)
    samples = pd.read_csv(os.path.join(pkg, 'oil_samples.csv'))
    loads = pd.read_csv(os.path.join(pkg, 'loads.csv'))
    for c in ['oil_system', 'kind']:
        systems[c] = systems[c].str.strip()
    tanks['tank'] = tanks.tank.str.strip(); tanks['oil_system'] = tanks.oil_system.str.strip()
    samples['sampled_at'] = samples.sampled_at.astype(str).str.strip()
    loads['tank'] = loads.tank.astype(str).str.strip()
    # systems referenced by tanks but not in register
    extra = sorted(set(tanks.oil_system) - set(systems.oil_system))
    if extra:
        systems = pd.concat([systems, pd.DataFrame({'oil_system': extra, 'kind': 'single', 'oil_type': ''})])
    # loads' tanks not in tank list
    for t in sorted(set(loads.tank) - set(tanks.tank)):
        tanks = pd.concat([tanks, pd.DataFrame({'tank': [t], 'oil_system': ['?' + t], 'volume_m3': ['']})])
        systems = pd.concat([systems, pd.DataFrame({'oil_system': ['?' + t], 'kind': 'single', 'oil_type': ''})])
    renew = {}
    for r in log.itertuples():
        if str(r.work).strip().upper() == 'CHARGE_RENEWED':
            renew.setdefault(str(r.oil_system).strip(), []).append(dnum(r.date))
    for k in renew:
        renew[k] = sorted(set(renew[k]))
    charges, bytank = build_charges(tanks, systems, samples)
    ldate = {}
    for r in loads.itertuples():
        ldate.setdefault(r.tank, []).append(dnum(r.date))
    for ch in charges:
        ren = renew.get(ch['system'], []) if ch['main'] else []
        ch['ren'] = ren
        last_ren = ren[-1] if ren else -10**9
        ch['last_ren'] = last_ren
        # analyses per date (mean over tanks of charge)
        an = {}
        for t in ch['tanks']:
            for d, f in bytank.get(t, []):
                an.setdefault(d, []).append(f)
        ch['an'] = sorted((d, np.mean(v, 0)) for d, v in an.items())
        dl = [d for t in ch['tanks'] for d in ldate.get(t, [])]
        ch['need_after'] = any(d > last_ren for d in dl) and bool(dl)
        cur = [(d, f) for d, f in ch['an'] if d > last_ren]
        ch['cur'] = cur
        ch['trend'] = None
        ch['score'] = 0.0
        if not ch['need_after']:
            ch['must'] = False; continue
        if ren and not cur:
            ch['must'] = True; ch['score'] = 100.0
        elif not cur:
            ch['must'] = True; ch['score'] = 50.0
        else:
            ch['must'] = False
            # trend from analyses of current charge
            ds = np.array([d for d, _ in cur], float); fs = np.array([f for _, f in cur])
            if len(cur) >= 2:
                A = np.vstack([ds - ds[-1], np.ones_like(ds)]).T
                coef = np.linalg.lstsq(A, fs, rcond=None)[0]
                slope = coef[0]
                ch['trend'] = slope
                rate = abs(slope[0] / fs[-1, 0]) * 182.0
                rate2 = abs(slope[2] / fs[-1, 2]) * 182.0
                proj = max(rate, rate2) * (dlab - ds[-1]) / 182.0
                # scatter of residuals
                res = fs - (A @ coef)
                sc = np.abs(res[:, [0, 2]] / fs[-1, [0, 2]]).max()
                ch['score'] = proj + 2 * sc + (5.0 if max(rate, rate2) > 0.006 else 0.0)
            else:
                ch['score'] = 5.0
            if not ch['main']:
                ch['score'] += 10.0
            # loads beyond latest analysis needing extrapolation
            dmax = max(dl)
            if dmax <= ds[-1]:
                ch['score'] = 0.0
    # choose lab order
    order = sorted([c for c in charges if c['need_after'] and c['score'] > 0], key=lambda c: -c['score'])[:nlab]
    labres = {}
    if order:
        names = []
        for c in order:
            # pick the tank with most loads
            t = max(c['tanks'], key=lambda t: len(ldate.get(t, [])))
            names.append(t); c['labtank'] = t
        sys.stderr.write('lab order: %s\n' % ' '.join(names))
        try:
            p = subprocess.run(['labsample', pkg] + names, capture_output=True, text=True, timeout=30)
            for line in p.stdout.splitlines():
                parts = [x.strip() for x in line.split(',')]
                if len(parts) >= 4 and parts[0] in names:
                    try:
                        labres[parts[0]] = np.array([float(parts[1]), float(parts[2]), float(parts[3])])
                    except ValueError:
                        pass
            if p.returncode != 0 or len(labres) < len(names):
                sys.stderr.write(p.stdout + p.stderr)
        except Exception as e:
            sys.stderr.write('labsample failed: %r\n' % e)
    for c in order:
        t = c.get('labtank')
        if t in labres:
            c['lab'] = labres[t]
            # a split-off tank of a renewed system whose oil now differs from its own history: it was renewed with it
            if not c['main'] and not c['ren'] and renew.get(c['system']) and c['cur']:
                a, f = c['cur'][-1]
                pr = f + (c['trend'] * (dlab - a) if c['trend'] is not None else 0)
                if rel(c['lab'], pr) > 0.03:
                    c['ren'] = renew[c['system']]
                    c['last_ren'] = c['ren'][-1]
                    c['cur'] = []

    def figs(ch, d):
        an = ch['an']; ren = ch['ren']
        # segment containing d
        prev_ren = max([r for r in ren if r <= d], default=None)
        nxt_ren = min([r for r in ren if r > d], default=None)
        lo = prev_ren if prev_ren is not None else -10**9
        hi = nxt_ren if nxt_ren is not None else 10**9
        seg = [(a, f) for a, f in an if lo <= a < hi]
        if nxt_ren is not None:
            # old charge (renewed later): latest analysis up to d holds
            if not seg:
                seg = [(a, f) for a, f in an if a < hi]
            if not seg:
                seg = an
            past = [f for a, f in seg if a <= d]
            return past[-1] if past else seg[0][1]
        # current charge
        pts = list(seg)
        if 'lab' in ch:
            pts = [p for p in pts if p[0] != dlab] + [(dlab, ch['lab'])]
        elif pts and ch['trend'] is not None and not ren:
            a, f = pts[-1]
            pts.append((dlab, f + ch['trend'] * (dlab - a)))
        elif pts and ch['trend'] is not None:
            a, f = pts[-1]
            pts.append((dlab, f + ch['trend'] * (dlab - a)))
        pts.sort(key=lambda p: p[0])
        if not pts:
            # fallback: latest analysis of anything earlier
            if an:
                return an[-1][1]
            return None
        if ren and len([p for p in pts]) and 'lab' in ch and len(seg) == 0:
            return ch['lab']
        ds = [p[0] for p in pts]
        if d <= ds[0]:
            return pts[0][1]
        if d >= ds[-1]:
            return pts[-1][1]
        for (a, fa), (b, fb) in zip(pts[:-1], pts[1:]):
            if a <= d <= b:
                w = (d - a) / (b - a)
                return fa + w * (fb - fa)
        return pts[-1][1]

    tank2ch = {}
    for c in charges:
        for t in c['tanks']:
            tank2ch[t] = c
    allf = [f for c in charges for _, f in c['an']]
    deff = np.mean(allf, 0) if allf else np.array([80., 580., 7.])
    F = np.zeros((len(loads), 3))
    for i, r in enumerate(loads.itertuples()):
        c = tank2ch.get(r.tank)
        f = figs(c, dnum(r.date)) if c else None
        F[i] = deff if f is None else f
    hp = 14200.0 * F[:, 0] / (F[:, 1] - 40.0)
    h3 = 14200.0 * F[:, 2] / 260.0
    c45 = loads.steel.astype(str).str.strip().str.upper().str.replace(' ', '') == 'C45'
    res = solve(c45.values, loads.diameter_mm.values / 2000.0, loads.furnace_C.values.astype(float),
                loads.bath_C.values.astype(float), hp, h3, F[:, 1].astype(float), N=30, dTstep=2.5)
    o = pd.DataFrame({'load': loads['load'],
                      't85_core_s': np.round(res['t85'], 4), 'cr700_core_K_s': np.round(res['cr700'], 5),
                      'dT_max_K': np.round(res['dTmax'], 4), 'ts_core500_C': np.round(res['ts500'], 4),
                      't150_core_s': np.round(res['t150'], 4)})
    o.to_csv(out, index=False)


if __name__ == '__main__':
    main()
