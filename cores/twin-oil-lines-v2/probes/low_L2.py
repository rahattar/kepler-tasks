import sys, os, csv, json, subprocess
import numpy as np

NSTEP = int(os.environ.get('NSTEP', 40))
NGRID = int(os.environ.get('NGRID', 41))

def rd(p):
    with open(p) as f:
        return list(csv.DictReader(f))

def visc_coeffs(nu50, nu100):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(nu50 + 0.7)); y2 = np.log10(np.log10(nu100 + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1))
    A = y1 + B * np.log10(T1)
    return A, B

def nu_of(T, A, B):
    return (10 ** (10 ** (A - B * np.log10(T + 273.15))) - 0.7) * 1e-6

class P:
    """vectorised pipe set"""
    def __init__(s, D, L, rho, cp, k, A, B):
        s.D, s.L, s.rho, s.cp, s.k, s.A, s.B = [np.asarray(v, float) for v in (D, L, rho, cp, k, A, B)]

def run(p, m, Tin, Ta, Uo, idx=None):
    """m kg/s. returns Tout, dp (Pa)"""
    if idx is None:
        D, L, rho, cp, k, A, B = p.D, p.L, p.rho, p.cp, p.k, p.A, p.B
    else:
        D, L, rho, cp, k, A, B = [a[idx] for a in (p.D, p.L, p.rho, p.cp, p.k, p.A, p.B)]
    m = np.asarray(m, float); Tin = np.asarray(Tin, float); Ta = np.asarray(Ta, float); Uo = np.asarray(Uo, float)
    u = 4 * m / (np.pi * D**2 * rho)
    Tw_prev = [0.5 * (Tin + Ta)]

    def deriv(x, Tb):
        Tb = np.maximum(Tb, Ta + 1e-6)
        nub = nu_of(Tb, A, B)
        Re = u * D / nub
        Pr = nub * rho * cp / k
        Gz = Re * Pr * D / np.maximum(x, 1e-300)
        Nu0 = (3.66**3 + 0.7**3 + (1.077 * Gz**(1/3) - 0.7)**3) ** (1/3)
        mub = nub
        Tw = Tw_prev[0]
        Tw = np.clip(Tw, Ta, Tb)
        for _ in range(6):
            nuw = nu_of(Tw, A, B)
            h = Nu0 * (mub / nuw)**0.14 * k / D
            Tw_new = (h * Tb + Uo * Ta) / (h + Uo)
            if np.max(np.abs(Tw_new - Tw)) < 1e-9:
                Tw = Tw_new; break
            Tw = Tw_new
        Tw_prev[0] = Tw
        nuw = nu_of(Tw, A, B)
        q = np.pi * D * Uo * (Tw - Ta)
        dT = -q / (m * cp)
        f = 64 / Re * (nuw / nub)**0.5
        dP = f * rho * u**2 / (2 * D)
        return dT, dP

    # x = L t^3, dx = 3 L t^2 dt ; RK4 in t
    n = NSTEP
    h_t = 1.0 / n
    Tb = Tin.copy(); pr = np.zeros_like(Tb)
    for i in range(n):
        t0 = i * h_t
        def g(t, T):
            if t == 0:
                # dT/dx ~ x^-1/3 -> dT/dt finite*t ... use tiny t
                t = 1e-9
            dT, dP = deriv(L * t**3, T)
            j = 3 * L * t**2
            return dT * j, dP * j
        k1 = g(t0, Tb)
        k2 = g(t0 + h_t/2, Tb + h_t/2 * k1[0])
        k3 = g(t0 + h_t/2, Tb + h_t/2 * k2[0])
        k4 = g(t0 + h_t, Tb + h_t * k3[0])
        Tb = Tb + h_t/6 * (k1[0] + 2*k2[0] + 2*k3[0] + k4[0])
        pr = pr + h_t/6 * (k1[1] + 2*k2[1] + 2*k3[1] + k4[1])
    return Tb, pr


def fit_uo(p, m, Ti, To, Ta):
    lo = np.full(len(m), -3.0); hi = np.full(len(m), 4.0)
    for _ in range(36):
        mid = (lo + hi) / 2
        T, _ = run(p, m, Ti, Ta, 10**mid)
        big = T < To
        hi = np.where(big, mid, hi); lo = np.where(big, lo, mid)
    return 10**((lo + hi) / 2)


def main(pkg, out):
    site = json.load(open(os.path.join(pkg, 'site.json')))
    oils = {o['oil']: o for o in rd(os.path.join(pkg, 'oils.csv'))}
    lines = {l['line']: l for l in rd(os.path.join(pkg, 'lines.csv'))}
    sv = rd(os.path.join(pkg, 'surveys.csv'))
    wl = rd(os.path.join(pkg, 'work_log.csv'))
    recs = rd(os.path.join(pkg, 'records.csv'))

    def pipes_of(ln):
        n = int(lines[ln]['pipes'])
        return [ln + '-A'] + ([ln + '-B'] if n == 2 else [])

    def props(names):
        cols = [[] for _ in range(7)]
        for pn in names:
            l = lines[pn.rsplit('-', 1)[0]]; o = oils[l['oil']]
            a, b = visc_coeffs(float(o['nu50_cSt']), float(o['nu100_cSt']))
            for c, v in zip(cols, (float(l['bore_mm']) / 1000, float(l['length_m']), float(o['density_kg_m3']),
                                   float(o['cp_J_kgK']), float(o['k_W_mK']), a, b)):
                c.append(v)
        return P(*cols)

    allp = [pp for ln in lines for pp in pipes_of(ln)]
    # last covering work per pipe
    lastwork = {}
    for w in wl:
        j = w['job'].lower()
        if 'cover' in j or 'insul' in j or 'lagg' in j or 'clad' in j:
            lastwork[w['pipe']] = max(lastwork.get(w['pipe'], ''), w['date'])
    use = [s for s in sv if s['date'] > lastwork.get(s['pipe'], '')]
    have = {s['pipe'] for s in use}
    need = [pp for pp in allp if pp not in have]
    # all surveys fitted together
    rows = [(s['pipe'], s['flow_t_h'], s['t_in_C'], s['t_out_C'], s['t_amb_C']) for s in use]
    if need:
        allow = int(site.get('survey_allowance', 0))
        order = need[:allow]
        try:
            r = subprocess.run(['heatsurvey', pkg] + order, capture_output=True, text=True, timeout=30)
            for row in csv.DictReader(r.stdout.strip().splitlines()):
                if row.get('pipe') in order:
                    rows.append((row['pipe'], row['flow_t_h'], row['t_in_C'], row['t_out_C'], row['t_amb_C']))
        except Exception as e:
            sys.stderr.write('heatsurvey failed: %s\n' % e)
    names = [r[0] for r in rows]
    U = fit_uo(props(names), np.array([float(r[1]) for r in rows]) / 3.6,
               np.array([float(r[2]) for r in rows]), np.array([float(r[3]) for r in rows]),
               np.array([float(r[4]) for r in rows]))
    acc = {}
    for n_, u in zip(names, U):
        acc.setdefault(n_, []).append(u)
    Uo = {k: float(np.mean(v)) for k, v in acc.items()}
    for pp in allp:
        if pp not in Uo:
            # fallback: latest pre-work survey
            old = [s for s in sv if s['pipe'] == pp]
            sys.stderr.write('no valid survey for %s\n' % pp)
            if old:
                acc2 = fit_uo(props([pp]), np.array([float(old[-1]['flow_t_h'])]) / 3.6,
                              np.array([float(old[-1]['t_in_C'])]), np.array([float(old[-1]['t_out_C'])]),
                              np.array([float(old[-1]['t_amb_C'])]))
                Uo[pp] = float(acc2[0])
            else:
                Uo[pp] = 5.0

    M = np.array([float(r['flow_t_h']) for r in recs]) / 3.6
    Ti = np.array([float(r['t_in_C']) for r in recs]); Ta = np.array([float(r['t_amb_C']) for r in recs])
    lnames = [r['line'] for r in recs]
    pA = props([ln + '-A' for ln in lnames])
    UA = np.array([Uo[ln + '-A'] for ln in lnames])
    pair = np.array([int(lines[ln]['pipes']) == 2 for ln in lnames])
    dp = np.zeros(len(recs)); To = np.zeros(len(recs))
    s = ~pair
    if s.any():
        To[s], dp[s] = run(pA, M[s], Ti[s], Ta[s], UA[s], np.where(s)[0])
    ix = np.where(pair)[0]
    if len(ix):
        UB = np.array([Uo[lnames[i] + '-B'] for i in ix])
        UAp = UA[ix]; Mp = M[ix]; Tip = Ti[ix]; Tap = Ta[ix]

        def resid(a):
            TA, dA = run(pA, a * Mp, Tip, Tap, UAp, ix)
            TB, dB = run(pA, (1 - a) * Mp, Tip, Tap, UB, ix)
            return np.log(dA / dB), TA, TB, dA, dB
        G = 0.5 - 0.495 * np.cos(np.linspace(0, np.pi, NGRID))
        F = np.array([resid(np.full(len(ix), g))[0] for g in G])  # (nG, n)
        lo = np.zeros(len(ix)); hi = np.zeros(len(ix)); flo = np.zeros(len(ix)); fhi = np.zeros(len(ix))
        prev = {}
        nG = len(G)
        for q, i_ in enumerate(ix):
            ln = lnames[i_]
            ap = prev.get(ln, 0.5)
            f = F[:, q]
            j0 = int(np.clip(np.searchsorted(G, ap) - 1, 0, nG - 2))
            t = (ap - G[j0]) / (G[j0 + 1] - G[j0])
            fp = f[j0] + t * (f[j0 + 1] - f[j0])
            k = None
            if fp > 0:   # dpA > dpB: flow moves to B, a decreases
                for kk in range(j0, -1, -1):
                    if f[kk] <= 0:
                        k = kk; break
                if k is None:
                    k = 0
            else:
                for kk in range(j0 + 1, nG):
                    if f[kk] >= 0:
                        k = kk - 1; break
                if k is None:
                    k = nG - 2
            lo[q], hi[q], flo[q], fhi[q] = G[k], G[k + 1], f[k], f[k + 1]
            # estimate root for continuity
            den = f[k] - f[k + 1]
            prev[ln] = G[k] + (f[k] / den if den != 0 else 0.5) * (G[k + 1] - G[k])
        side = np.zeros(len(ix))
        for _ in range(40):
            den = flo - fhi
            a1 = np.where(np.abs(den) > 0, lo + flo / np.where(den == 0, 1, den) * (hi - lo), 0.5 * (lo + hi))
            a1 = np.clip(a1, np.minimum(lo, hi), np.maximum(lo, hi))
            r = resid(a1); f1 = r[0]
            if np.max(np.abs(f1)) < 1e-8:
                break
            same = f1 * flo > 0
            # Illinois
            fhi = np.where(same & (side == 1), fhi / 2, fhi)
            flo = np.where(~same & (side == -1), flo / 2, flo)
            lo = np.where(same, a1, lo); flo = np.where(same, f1, flo)
            hi = np.where(same, hi, a1); fhi = np.where(same, fhi, f1)
            side = np.where(same, 1, -1)
        _, TA, TB, dA, dB = r
        To[ix] = a1 * TA + (1 - a1) * TB   # constant cp: mass-weighted mixing
        dp[ix] = 0.5 * (dA + dB)
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for r_, d_, t_ in zip(recs, dp, To):
            w.writerow([r_['record'], '%.4f' % (d_ / 1e3), '%.4f' % t_])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
