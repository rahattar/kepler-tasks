import sys, os, json, subprocess
import numpy as np, pandas as pd
np.seterr(all="ignore")

NX = 40
NIT = 3

def oil_params(o):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(o.nu50_cSt + 0.7)); y2 = np.log10(np.log10(o.nu100_cSt + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1)); A = y1 + B * np.log10(T1)
    return dict(A=A, B=B, rho=o.density_kg_m3, cp=o.cp_J_kgK, k=o.k_W_mK)

def nu(TC, A, B):
    return (10 ** (10 ** (A - B * np.log10(TC + 273.15))) - 0.7) * 1e-6

def pipe(m, D, L, Tin, Ta, Uo, A, B, rho, cp, k, nx=NX):
    """vectorized over all args (broadcast). m kg/s. returns dp Pa, Tout C."""
    m, D, L, Tin, Ta, Uo, A, B, rho, cp, k = np.broadcast_arrays(
        *[np.asarray(v, float) for v in (m, D, L, Tin, Ta, Uo, A, B, rho, cp, k)])
    area = np.pi * D * D / 4
    u = m / (rho * area)
    s = np.linspace(0, 1, nx + 1) ** 2
    Tw = [Tin.copy()]
    def rhs(x, Tb):
        nb = nu(Tb, A, B)
        Re = u * D / nb; Pr = nb * rho * cp / k
        Gz = Re * Pr * D / np.maximum(x, 1e-12)
        Nu0 = (3.66**3 + 0.7**3 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1 / 3)
        tw = Tw[0]
        for _ in range(4):
            nw = nu(tw, A, B)
            h = Nu0 * (nb / nw) ** 0.14 * k / D
            tw = (h * Tb + Uo * Ta) / (h + Uo)
        Tw[0] = tw
        nw = nu(tw, A, B)
        q = np.pi * D * Uo * (tw - Ta)
        f = 64 / Re * (nw / nb) ** 0.5
        g = f * rho * u * u / (2 * D)
        return -q / (m * cp), g
    Tb = Tin.copy(); p = np.zeros_like(Tb)
    def coef(x, T):
        nb = nu(T, A, B)
        Re = u * D / nb; Pr = nb * rho * cp / k
        Gz = Re * Pr * D / np.maximum(x, 1e-9 * L)
        Nu0 = (3.66**3 + 0.7**3 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1 / 3)
        tw = Tw[0]
        for _ in range(NIT):
            nw = nu(tw, A, B)
            h = Nu0 * (nb / nw) ** 0.14 * k / D
            tw = (h * T + Uo * Ta) / (h + Uo)
        Tw[0] = tw
        nw = nu(tw, A, B)
        a = np.pi * D * Uo * h / (h + Uo) / (m * cp)
        g = 64 / Re * (nw / nb) ** 0.5 * rho * u * u / (2 * D)
        return a, g
    for i in range(nx):
        x0 = s[i] * L; hx = (s[i + 1] - s[i]) * L; xm = x0 + hx / 2
        a0, g0 = coef(xm, Tb)
        Tm = Ta + (Tb - Ta) * np.exp(-a0 * hx / 2)
        a1, g1 = coef(xm, Tm)
        Tb = Ta + (Tb - Ta) * np.exp(-a1 * hx)
        p = p + g1 * hx
    return p, Tb

COVER = ('cover', 'lag', 'insul', 'clad', 'jacket', 'wrap')

def is_cover_job(j):
    j = str(j).lower()
    return any(c in j for c in COVER)

def fit_many(m, tin, tout, ta, D, L, op):
    """vectorized Uo fit by bisection in log U. op: dict of arrays."""
    lo = np.full(np.shape(m), np.log(1e-3)); hi = np.full(np.shape(m), np.log(80.0))
    for _ in range(42):
        mid = 0.5 * (lo + hi)
        _, T = pipe(m, D, L, tin, ta, np.exp(mid), **op)
        cold = T < tout   # too much loss -> U smaller
        hi = np.where(cold, mid, hi); lo = np.where(cold, lo, mid)
    return np.exp(0.5 * (lo + hi))

def main():
    pk, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pk, 'site.json')))
    oils = pd.read_csv(os.path.join(pk, 'oils.csv'))
    lines = pd.read_csv(os.path.join(pk, 'lines.csv'))
    surv = pd.read_csv(os.path.join(pk, 'surveys.csv'))
    work = pd.read_csv(os.path.join(pk, 'work_log.csv'))
    rec = pd.read_csv(os.path.join(pk, 'records.csv'))
    OP = {r.oil: oil_params(r) for r in oils.itertuples()}
    LN = {r.line: r for r in lines.itertuples()}

    pipes = []
    for r in lines.itertuples():
        pipes += [f'{r.line}-A'] + ([f'{r.line}-B'] if r.pipes == 2 else [])
    lastwork = {}
    for w in work.itertuples():
        if is_cover_job(w.job):
            lastwork[w.pipe] = max(lastwork.get(w.pipe, ''), str(w.date))
    # fit every survey on file, with its sensitivity to the reading tolerances (TS-2 5.4)
    sv = surv.reset_index(drop=True)
    ls = [LN[p.rsplit('-', 1)[0]] for p in sv['pipe']]
    keys = ['A', 'B', 'rho', 'cp', 'k']
    opv = {kk: np.array([OP[x.oil][kk] for x in ls]) for kk in keys}
    Dv = np.array([x.bore_mm for x in ls]) / 1000; Lv = np.array([x.length_m for x in ls], float)
    mv = sv.flow_t_h.values / 3.6; ti = sv.t_in_C.values; tt = sv.t_out_C.values; ta = sv.t_amb_C.values
    pert = [(1, 0, 0, 0), (1.002, 0, 0, 0), (1, .02, 0, 0), (1, 0, .02, 0), (1, 0, 0, .1)]
    ns = len(sv)
    rep = lambda v: np.tile(v, len(pert))
    M5 = np.concatenate([mv * f for f, _, _, _ in pert]); TI5 = np.concatenate([ti + d for _, d, _, _ in pert])
    TO5 = np.concatenate([tt + d for _, _, d, _ in pert]); TA5 = np.concatenate([ta + d for _, _, _, d in pert])
    U5 = fit_many(M5, TI5, TO5, TA5, rep(Dv), rep(Lv), {kk: rep(v) for kk, v in opv.items()}).reshape(len(pert), ns)
    sv['U'] = U5[0]; sv['sig'] = np.sqrt(np.sum((U5[1:] - U5[0]) ** 2, axis=0))
    sv['date'] = sv['date'].astype(str)

    UO = {}; need = []; drift = []
    for p in pipes:
        s = sv[(sv['pipe'] == p) & (sv['date'] > lastwork.get(p, ''))].sort_values('date')
        if len(s) == 0:
            need.append(p)
            s0 = sv[sv['pipe'] == p].sort_values('date')
            UO[p] = float(s0.U.iloc[-1]) if len(s0) else 5.0
            continue
        u = s.U.values; sg = np.maximum(s.sig.values, 1e-6)
        mean = np.average(u, weights=1 / sg ** 2)
        score = np.max(np.abs(u - mean) / sg) if len(u) > 1 else 0.0
        if score > 3.0:   # covering changing although no work logged: not as it stands
            drift.append((score, p)); UO[p] = float(u[-1])
        else:
            UO[p] = float(mean)
    allow = int(site.get('survey_allowance', 0))
    order = (need + [p for _, p in sorted(drift, reverse=True)])[:allow]
    if order:
        try:
            from io import StringIO
            res = subprocess.run(['heatsurvey', pk] + order, capture_output=True, text=True, timeout=60)
            nsv = pd.read_csv(StringIO(res.stdout))
            nsv = nsv[nsv['pipe'].isin(order)].reset_index(drop=True)
            if len(nsv):
                ls = [LN[p.rsplit('-', 1)[0]] for p in nsv['pipe']]
                op2 = {kk: np.array([OP[x.oil][kk] for x in ls]) for kk in keys}
                U = fit_many(nsv.flow_t_h.values / 3.6, nsv.t_in_C.values, nsv.t_out_C.values, nsv.t_amb_C.values,
                             np.array([x.bore_mm for x in ls]) / 1000, np.array([x.length_m for x in ls], float), op2)
                for p, x in zip(nsv['pipe'], U):
                    UO[p] = float(x)
            if len(nsv) < len(order):
                sys.stderr.write('heatsurvey: ' + res.stdout + res.stderr + '\n')
        except Exception as e:
            sys.stderr.write(f'heatsurvey failed: {e}\n')
    if os.environ.get('DEBUG'):
        sys.stderr.write(f'order {order}\n')

    dp = np.zeros(len(rec)); to = np.zeros(len(rec))
    rec = rec.reset_index(drop=True)
    # singles: all at once
    single = rec.line.map(lambda x: LN[x].pipes == 1).values
    if single.any():
        R = rec[single]
        l = [LN[x] for x in R.line]
        keys = ['A', 'B', 'rho', 'cp', 'k']
        op = {kk: np.array([OP[x.oil][kk] for x in l]) for kk in keys}
        P, T = pipe(R.flow_t_h.values / 3.6, np.array([x.bore_mm for x in l]) / 1000,
                    np.array([x.length_m for x in l], float), R.t_in_C.values, R.t_amb_C.values,
                    np.array([UO[x.line + '-A'] for x in l]), **op)
        dp[single] = P; to[single] = T
    # pairs
    pr = ~single
    if pr.any():
        R = rec[pr]; idx = np.where(pr)[0]
        l = [LN[x] for x in R.line]
        n = len(R)
        NS = 48
        sg = (np.arange(NS) + 0.5) / NS
        sg = np.concatenate([[1e-4], sg, [1 - 1e-4]]); NS = len(sg)
        keys = ['A', 'B', 'rho', 'cp', 'k']
        op = {kk: np.array([OP[x.oil][kk] for x in l])[:, None] for kk in keys}
        D = (np.array([x.bore_mm for x in l]) / 1000)[:, None]
        Lg = np.array([x.length_m for x in l], float)[:, None]
        M = (R.flow_t_h.values / 3.6)[:, None]
        Ti = R.t_in_C.values[:, None]; Ta = R.t_amb_C.values[:, None]
        UA = np.array([UO[x.line + '-A'] for x in l])[:, None]
        UB = np.array([UO[x.line + '-B'] for x in l])[:, None]
        def G(s):
            pa, ta = pipe(M * s, D, Lg, Ti, Ta, UA, **op)
            pb, tb = pipe(M * (1 - s), D, Lg, Ti, Ta, UB, **op)
            return pa - pb, pa, pb, ta, tb
        g = G(sg[None, :])[0]
        # brackets
        roots = [[] for _ in range(n)]
        bi, bj = np.where(np.sign(g[:, :-1]) != np.sign(g[:, 1:]))
        lo = sg[bj].copy(); hi = sg[bj + 1].copy(); glo = g[bi, bj]; ghi = g[bi, bj + 1]
        sel = lambda a: {kk: v[bi] for kk, v in a.items()}
        opb = {kk: v[bi, 0] for kk, v in op.items()}
        def Gb(s):
            pa, ta = pipe(M[bi, 0] * s, D[bi, 0], Lg[bi, 0], Ti[bi, 0], Ta[bi, 0], UA[bi, 0], **opb)
            pb, tb = pipe(M[bi, 0] * (1 - s), D[bi, 0], Lg[bi, 0], Ti[bi, 0], Ta[bi, 0], UB[bi, 0], **opb)
            return pa - pb
        side = np.zeros(len(bi))
        for it in range(30):
            s = (lo * ghi - hi * glo) / (ghi - glo)
            gs = Gb(s)
            same = np.sign(gs) == np.sign(glo)
            # illinois
            lo = np.where(same, s, lo); glo = np.where(same, gs, glo)
            ghi = np.where(same & (side == 1), ghi / 2, ghi)
            hi = np.where(~same, s, hi); ghi = np.where(~same, gs, ghi)
            glo = np.where(~same & (side == -1), glo / 2, glo)
            side = np.where(same, 1, -1)
            if np.max(hi - lo) < 1e-9: break
        sr = (lo * ghi - hi * glo) / (ghi - glo)
        for a, b in zip(bi, sr):
            roots[a].append(b)
        # hysteresis sequentially per line
        g0sign = np.sign(g[:, 0])
        chosen = np.zeros(n)
        pos = {}
        lines_r = R.line.values
        for i in range(n):
            r = np.array(sorted(roots[i]))
            ln = lines_r[i]
            if len(r) == 0:
                c = 0.5
            elif ln not in pos or len(r) == 1:
                if ln not in pos and len(r) != 1:
                    sys.stderr.write(f'{ln}: {len(r)} roots at start\n')
                c = r[len(r) // 2]
            else:
                sp = pos[ln]
                nb = np.sum(r < sp)
                sgn = g0sign[i] * (-1) ** nb   # sign of dpA-dpB at sp
                if sgn > 0:
                    c = r[nb - 1] if nb > 0 else r[0]
                else:
                    c = r[nb] if nb < len(r) else r[-1]
            pos[ln] = c; chosen[i] = c
        s = chosen[:, None]
        _, pa, pb, ta, tb = G(s)
        dp[idx] = 0.5 * (pa + pb)[:, 0]
        to[idx] = (s * ta + (1 - s) * tb)[:, 0]
    pd.DataFrame({'record': rec.record, 'dp_kPa': np.round(dp / 1000, 4), 't_out_C': np.round(to, 4)}).to_csv(out, index=False)

if __name__ == '__main__':
    main()
