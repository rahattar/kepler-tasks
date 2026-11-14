#!/usr/bin/env python3
"""TS-2 heated oil line calculation for one site package.
Usage: python3 lines.py PACKAGE_DIR OUT_CSV"""
import csv, os, re, subprocess, sys
import numpy as np

N_STEPS = 24  # RK4 steps in s = (x/L)^(1/3); converged far below 0.1 %


def oil_AB(n50, n100):
    y1 = np.log10(np.log10(n50 + 0.7)); y2 = np.log10(np.log10(n100 + 0.7))
    x1 = np.log10(323.15); x2 = np.log10(373.15)
    B = (y1 - y2) / (x2 - x1)
    return y1 + B * x1, B


def nu(T, A, B):
    return (10.0 ** (10.0 ** (A - B * np.log10(T + 273.15))) - 0.7) * 1e-6


def integ(D, L, m, Tin, Ta, Uo, rho, cp, k, A, B, N=N_STEPS):
    """Vectorised TS-2 section 3 integration. Returns (dp Pa, Tout C)."""
    D, L, m, Tin, Ta, Uo, rho, cp, k, A, B = np.broadcast_arrays(
        *[np.asarray(v, float) for v in (D, L, m, Tin, Ta, Uo, rho, cp, k, A, B)])
    u = m / (rho * np.pi * D ** 2 / 4)
    c3 = 3.66 ** 3 + 0.7 ** 3

    def F(s, y, Tw):
        # y = ln(Tb - Ta): stays well-behaved even when the oil cools to ambient
        Tb = Ta + np.exp(y)
        x = np.maximum(L * s ** 3, 1e-300)
        nb = nu(Tb, A, B)
        Re = u * D / nb
        Gz = Re * (nb * rho * cp / k) * D / x
        base = (c3 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1 / 3) * k / D
        for _ in range(5):
            nw = nu(Tw, A, B)
            h = base * (nb / nw) ** 0.14
            Tw = (h * Tb + Uo * Ta) / (h + Uo)
        nw = nu(Tw, A, B)
        h = base * (nb / nw) ** 0.14
        J = 3 * L * s ** 2
        dy = -np.pi * D * Uo * h / (h + Uo) / (m * cp) * J
        dp = 64 / Re * np.sqrt(nw / nb) * rho * u ** 2 / (2 * D) * J
        return dy, dp, Tw

    y = np.log(Tin - Ta); Tw = Tin.copy(); P = np.zeros_like(Tin); hs = 1.0 / N
    for i in range(N):
        s0 = i * hs
        k1 = F(s0, y, Tw)
        k2 = F(s0 + hs / 2, y + hs / 2 * k1[0], k1[2])
        k3 = F(s0 + hs / 2, y + hs / 2 * k2[0], k2[2])
        k4 = F(s0 + hs, y + hs * k3[0], k3[2])
        y = y + hs / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        P = P + hs / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        Tw = k4[2]
    Tb = Ta + np.exp(y)
    return P, Tb


def fit_U(D, L, m, Ti, To, Ta, rho, cp, k, A, B):
    """Uo (W/m2K, referred to the bore) reproducing the surveyed outlet temperature (5.2)."""
    lo = np.full(len(m), 0.01); hi = np.full(len(m), 500.0)
    for _ in range(45):
        mid = np.sqrt(lo * hi)
        _, T = integ(D, L, m, Ti, Ta, mid, rho, cp, k, A, B)
        big = T < To
        hi = np.where(big, mid, hi); lo = np.where(big, lo, mid)
    return np.sqrt(lo * hi)


FGRID = np.concatenate([np.geomspace(2e-4, 0.02, 14), np.linspace(0.03, 0.97, 95),
                        1 - np.geomspace(0.02, 2e-4, 14)])


def pair_roots(D, L, M, Ti, Ta, UA, UB, rho, cp, k, A, B, it=36):
    """Section 4: all stable splits (fraction of the flow in pipe A) at which both pipes have
    the same pressure drop.  Returns, per record, a list of (f, dp, Tmix, stable) in order of f."""
    n = len(M); G = len(FGRID)
    rep = lambda v: np.repeat(np.broadcast_to(np.asarray(v, float), (n,)), G)
    a = [rep(v) for v in (D, L, M, Ti, Ta, UA, UB, rho, cp, k, A, B)]
    D_, L_, M_, Ti_, Ta_, UA_, UB_, r_, c_, k_, A_, B_ = a
    f = np.tile(FGRID, n)
    pA, _ = integ(D_, L_, M_ * f, Ti_, Ta_, UA_, r_, c_, k_, A_, B_)
    pB, _ = integ(D_, L_, M_ * (1 - f), Ti_, Ta_, UB_, r_, c_, k_, A_, B_)
    g = (pA - pB).reshape(n, G)
    ok = np.isfinite(g)
    # roots: stable where g goes from negative to positive with increasing f, unstable otherwise
    br = np.argwhere(ok[:, :-1] & ok[:, 1:] & ((g[:, :-1] < 0) != (g[:, 1:] < 0)))
    up = g[br[:, 0], br[:, 1]] < 0
    rec, j = br[:, 0], br[:, 1]
    lo = FGRID[j].copy(); hi = FGRID[j + 1].copy()
    P = [np.asarray(v, float)[rec] if np.ndim(v) else v for v in
         (np.broadcast_to(D, (n,)), np.broadcast_to(L, (n,)), M, np.broadcast_to(Ti, (n,)),
          np.broadcast_to(Ta, (n,)), UA, UB, np.broadcast_to(rho, (n,)), np.broadcast_to(cp, (n,)),
          np.broadcast_to(k, (n,)), np.broadcast_to(A, (n,)), np.broadcast_to(B, (n,)))]
    D_, L_, M_, Ti_, Ta_, UA_, UB_, r_, c_, k_, A_, B_ = P
    for _ in range(it):
        fm = (lo + hi) / 2
        a1, _ = integ(D_, L_, M_ * fm, Ti_, Ta_, UA_, r_, c_, k_, A_, B_)
        b1, _ = integ(D_, L_, M_ * (1 - fm), Ti_, Ta_, UB_, r_, c_, k_, A_, B_)
        neg = (a1 < b1) == up
        lo = np.where(neg, fm, lo); hi = np.where(neg, hi, fm)
    fm = (lo + hi) / 2
    a1, ta = integ(D_, L_, M_ * fm, Ti_, Ta_, UA_, r_, c_, k_, A_, B_)
    b1, tb = integ(D_, L_, M_ * (1 - fm), Ti_, Ta_, UB_, r_, c_, k_, A_, B_)
    out = [[] for _ in range(n)]
    for i, ff, pa, pb, t1, t2, st in zip(rec, fm, a1, b1, ta, tb, up):
        out[i].append((ff, (pa + pb) / 2, ff * t1 + (1 - ff) * t2, bool(st)))   # mixed by mass, cp constant
    return out


COVER = re.compile(r'cover|lag|insul|clad|jacket', re.I)
NOT_WORK = re.compile(r'inspect|check|survey|photograph|examin', re.I)


def main(pkg, out):
    rd = lambda f: list(csv.DictReader(open(os.path.join(pkg, f), newline='')))
    import json
    site = json.load(open(os.path.join(pkg, 'site.json')))
    oils = {o['oil']: o for o in rd('oils.csv')}
    lines = {l['line']: l for l in rd('lines.csv')}
    surveys = rd('surveys.csv'); work = rd('work_log.csv'); recs = rd('records.csv')

    def props(ln):
        l = lines[ln]; o = oils[l['oil']]
        A, B = oil_AB(float(o['nu50_cSt']), float(o['nu100_cSt']))
        return (float(l['bore_mm']) / 1000, float(l['length_m']), float(o['density_kg_m3']),
                float(o['cp_J_kgK']), float(o['k_W_mK']), A, B)

    pipes = {}
    for ln, l in lines.items():
        for s in ('A', 'B')[:int(l['pipes'])]:
            pipes[f'{ln}-{s}'] = ln
    # last date of covering work per pipe (5.3)
    last_work = {}
    for w in work:
        if w['pipe'] in pipes and COVER.search(w['job']) and not NOT_WORK.search(w['job']):
            last_work[w['pipe']] = max(last_work.get(w['pipe'], ''), w['date'])

    def fit_rows(rows, d=None):
        P = [props(pipes[r['pipe']]) for r in rows]
        D, L, rho, cp, k, A, B = [np.array(c) for c in zip(*P)]
        g = lambda c: np.array([float(r[c]) for r in rows]) + (d.get(c, 0.0) if d else 0.0)
        fl = np.array([float(r['flow_t_h']) for r in rows]) * (1 + (d or {}).get('rel_flow', 0.0))
        return fit_U(D, L, fl / 3.6, g('t_in_C'), g('t_out_C'), g('t_amb_C'), rho, cp, k, A, B)

    valid = [s for s in surveys if s['pipe'] in pipes and s['date'] > last_work.get(s['pipe'], '')]
    Uo = {}; drift = {}
    if valid:
        U0 = fit_rows(valid)
        # worst-case reading tolerance of each survey's Uo (5.4)
        tol = np.zeros_like(U0)
        for d in ({'rel_flow': 0.002}, {'t_in_C': 0.02}, {'t_out_C': 0.02}, {'t_amb_C': 0.1}):
            tol += np.abs(fit_rows(valid, d) - U0)
        per = {}
        for s, u, t in zip(valid, U0, tol):
            per.setdefault(s['pipe'], []).append((s['date'], u, t))
        for p, v in per.items():
            v.sort()
            # covering that has changed since it was surveyed (wetting, damage ...): the surveys
            # disagree by more than their reading tolerances allow
            z = max([abs(a[1] - b[1]) / (a[2] + b[2]) for a in v for b in v if a[0] < b[0]], default=0)
            if z > 0.7:
                drift[p] = z
                print(f'note: {p} Uo has changed between surveys: ' +
                      ' '.join(f'{a[0]}:{a[1]:.3f}' for a in v), file=sys.stderr)
                Uo_last = v[-1][1]
                Uo[p] = Uo_last          # provisional; resurveyed below if allowance permits
            else:
                Uo[p] = float(np.mean([a[1] for a in v]))
    stale = {p: v for p, v in drift.items()}
    need = [p for p in pipes if p not in Uo]
    # pipes with no valid survey come first, then the most clearly changed coverings
    need += sorted(stale, key=lambda p: -stale[p])
    need = [p for p in pipes if p not in Uo]
    if need:
        allow = int(site.get('survey_allowance', 0))
        if len(need) > allow:
            print('warning: survey allowance too small, not resurveyed:', need[allow:], file=sys.stderr)
            need = need[:allow]
        if need:
            try:
                txt = subprocess.run(['heatsurvey', pkg] + need, capture_output=True, text=True,
                                     timeout=40).stdout
                rows = [r for r in csv.DictReader(txt.splitlines()) if r.get('pipe') in pipes]
                if rows:
                    for r, u in zip(rows, fit_rows(rows)):
                        Uo[r['pipe']] = float(u)
                        print(f'survey {r["pipe"]}: Uo {u:.3f}', file=sys.stderr)
            except Exception as e:
                print('survey failed:', e, file=sys.stderr)
        for p in pipes:   # fallback: newest survey on file, even if before work
            if p not in Uo:
                old = sorted((s['date'], i) for i, s in enumerate(surveys) if s['pipe'] == p)
                Uo[p] = float(fit_rows([surveys[old[-1][1]]])[0]) if old else 5.0
                print('warning: no current survey for', p, file=sys.stderr)

    dp = np.zeros(len(recs)); To = np.zeros(len(recs))
    for kind in ('1', '2'):
        idx = [i for i, r in enumerate(recs) if lines[r['line']]['pipes'] == kind]
        if not idx: continue
        P = [props(recs[i]['line']) for i in idx]
        D, L, rho, cp, k, A, B = [np.array(c) for c in zip(*P)]
        g = lambda c: np.array([float(recs[i][c]) for i in idx])
        M = g('flow_t_h') / 3.6; Ti = g('t_in_C'); Ta = g('t_amb_C')
        UA = np.array([Uo[recs[i]['line'] + '-A'] for i in idx])
        if kind == '1':
            p, T = integ(D, L, M, Ti, Ta, UA, rho, cp, k, A, B)
        else:
            UB = np.array([Uo[recs[i]['line'] + '-B'] for i in idx])
            roots = pair_roots(D, L, M, Ti, Ta, UA, UB, rho, cp, k, A, B)
            p = np.zeros(len(idx)); T = np.zeros(len(idx))
            # the records of a line are a run in time order: the split stays on the branch it
            # was on (nearest stable split to the previous hour's)
            order = sorted(range(len(idx)), key=lambda j: (recs[idx[j]]['line'], float(recs[idx[j]]['hour'])))
            prev = {}
            for j in order:
                ln = recs[idx[j]]['line']; rs = roots[j]
                if not rs:
                    print('warning: no split found for', recs[idx[j]]['record'], file=sys.stderr)
                    p[j], T[j] = np.nan, np.nan; continue
                f0 = prev.get(ln, 0.5)
                if ln not in prev and sum(t[3] for t in rs) > 1:
                    print('note: first record of', ln, 'has several stable splits:',
                          [round(t[0], 3) for t in rs if t[3]], file=sys.stderr)
                # the split relaxes from the previous hour's value to the stable split of the
                # basin it lies in: the basins are bounded by the unstable splits
                lo_u = max([t[0] for t in rs if not t[3] and t[0] <= f0], default=-1.0)
                hi_u = min([t[0] for t in rs if not t[3] and t[0] > f0], default=2.0)
                cand = [t for t in rs if t[3] and lo_u < t[0] < hi_u]
                if not cand:
                    cand = [t for t in rs if t[3]] or rs
                r = min(cand, key=lambda t: abs(t[0] - f0))
                prev[ln] = r[0]; p[j], T[j] = r[1], r[2]
        dp[idx] = p / 1000; To[idx] = T
    with open(out, 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['record', 'dp_kPa', 't_out_C'])
        for r, a, b in zip(recs, dp, To):
            w.writerow([r['record'], f'{a:.4f}', f'{b:.4f}'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
