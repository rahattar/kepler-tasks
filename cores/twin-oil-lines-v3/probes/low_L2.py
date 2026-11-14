#!/usr/bin/env python3
"""TS-2 heated oil transfer lines: pressure drop and outlet temperature per record."""
import math, sys, os, json, shutil, subprocess, io
import numpy as np
import pandas as pd
from scipy.optimize import brentq

NS = 10

# ---------------------------------------------------------------- physics
def visc_params(nu50, nu100):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(nu50 + 0.7)); y2 = np.log10(np.log10(nu100 + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1)); A = y1 + B * np.log10(T1)
    return A, B

def nu_si(A, B, Tc):
    T = np.maximum(Tc + 273.15, 150.0)
    return (10 ** (10 ** (A - B * np.log10(T))) - 0.7) * 1e-6

def pipe(m,D,L,Tin,Ta,Uo,op,ns=NS,nit=5):
    rho,cp,k,A,B=op
    m=float(m);D=float(D);L=float(L);Tin=float(Tin);Ta=float(Ta);Uo=float(Uo)
    nu=lambda Tc:(10**(10**(A-B*math.log10(Tc+273.15)))-0.7)*1e-6
    u=4*m/(math.pi*D*D*rho); c1=u*D*D*rho*cp/k; cdp=32*rho*u/(D*D); cq=math.pi*D/(m*cp)
    def rhs(s,th):
        dT=math.exp(th); Tb=Ta+dT
        x=L*s*s; dxds=2*L*s
        nub=nu(Tb)
        if x<=0: return -cq*Uo*dxds, cdp*nub*dxds
        Nu0=(3.66**3+0.7**3+(1.077*(c1/x)**(1/3)-0.7)**3)**(1/3)
        kd=k/D; Tw=Ta+0.5*dT; nuw=nu(Tw)
        for _ in range(nit):
            h=Nu0*(nub/nuw)**0.14*kd
            Tw=Ta+h/(h+Uo)*dT; nuw=nu(Tw)
        ueff=Uo*(Tw-Ta)/dT
        return -cq*ueff*dxds, cdp*math.sqrt(nub*nuw)*dxds
    h=1.0/ns; th=math.log(Tin-Ta); p=0.0
    for i in range(ns):
        s=i*h
        k1,p1=rhs(s,th); k2,p2=rhs(s+h/2,th+h/2*k1); k3,p3=rhs(s+h/2,th+h/2*k2); k4,p4=rhs(s+h,th+h*k3)
        th+=h/6*(k1+2*k2+2*k3+k4); p+=h/6*(p1+2*p2+2*p3+p4)
    return p, Ta+math.exp(th)

def fitU(flow_th, D, L, tin, tout, ta, op):
    f = lambda U: float(pipe(flow_th / 3.6, D, L, tin, ta, U, op)[1]) - tout
    lo, hi = 1e-3, 500.0
    if f(lo) < 0: return lo
    if f(hi) > 0: return hi
    return brentq(f, lo, hi, xtol=1e-7, rtol=1e-9)

def dp_of(flow_th, D, L, tin, ta, U, op):
    return float(pipe(flow_th / 3.6, D, L, tin, ta, U, op)[0])

# ---------------------------------------------------------------- tolerances (TS-2 5.4)
def U_sigma(x, D, L, op, U):
    """worst-case spread of Uo from reading tolerances of one survey"""
    tot = 0.0
    for dfl, dti, dto, dta in ((x.flow_t_h * 0.002, 0, 0, 0), (0, .02, 0, 0), (0, 0, .02, 0), (0, 0, 0, .1)):
        U2 = fitU(x.flow_t_h + dfl, D, L, x.t_in_C + dti, x.t_out_C + dto, x.t_amb_C + dta, op)
        tot += abs(U2 - U)
    return tot

# ---------------------------------------------------------------- main
def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, 'site.json')))
    oils = pd.read_csv(os.path.join(pkg, 'oils.csv')).set_index('oil')
    lines = pd.read_csv(os.path.join(pkg, 'lines.csv'), dtype={'line': str}).set_index('line')
    surv = pd.read_csv(os.path.join(pkg, 'surveys.csv'), dtype={'pipe': str, 'date': str})
    work = pd.read_csv(os.path.join(pkg, 'work_log.csv'), dtype={'pipe': str, 'date': str, 'job': str})
    recs = pd.read_csv(os.path.join(pkg, 'records.csv'), dtype={'record': str, 'line': str})
    allowance = int(site.get('survey_allowance', 0))

    OP = {}
    for name, x in oils.iterrows():
        A, B = visc_params(float(x.nu50_cSt), float(x.nu100_cSt))
        OP[name] = (float(x.density_kg_m3), float(x.cp_J_kgK), float(x.k_W_mK), float(A), float(B))

    pipe_line = {}
    for ln, L in lines.iterrows():
        for s in ('A', 'B')[:int(L.pipes)]:
            pipe_line[ln + '-' + s] = ln

    cover = work[work.job.str.lower().str.contains('covering')]
    last_cover = cover.groupby('pipe')['date'].max().to_dict()

    # --- per-pipe Uo from history
    info = {}   # pipe -> dict(U, need(score), D)
    for p, ln in pipe_line.items():
        L = lines.loc[ln]; op = OP[L.oil]; D = L.bore_mm / 1000.0
        g = surv[surv['pipe'] == p].sort_values('date')
        lc = last_cover.get(p)
        valid = g[g.date > lc] if lc is not None else g
        Us, sig = [], []
        for _, x in valid.iterrows():
            U = fitU(x.flow_t_h, D, L.length_m, x.t_in_C, x.t_out_C, x.t_amb_C, op)
            Us.append(U); sig.append(U_sigma(x, D, L.length_m, op, U))
        rec = dict(D=D, status='ok')
        if not Us:
            rec['status'] = 'unknown'
            allU = [fitU(x.flow_t_h, D, L.length_m, x.t_in_C, x.t_out_C, x.t_amb_C, op) for _, x in g.iterrows()]
            rec['U'] = allU[-1] if allU else 5.0
        else:
            changing = False
            for i in range(len(Us) - 1):
                if abs(Us[i + 1] - Us[i]) > (sig[i] + sig[i + 1]):
                    changing = True
            if changing:
                rec['status'] = 'changing'
                rec['U'] = Us[-1]
                rec['drift'] = abs(Us[-1] - Us[0])
            else:
                rec['U'] = float(np.mean(Us))
        rec['Us'] = Us
        info[p] = rec

    # --- bore in service from history surveys of pairs
    def pair_bore_fit(ln, rowA, rowB, UA, UB):
        """rows: survey rows for A and B (same campaign or crew). returns (DA, DB, UA, UB)."""
        L = lines.loc[ln]; op = OP[L.oil]; D0 = L.bore_mm / 1000.0; Lm = L.length_m
        return D0, D0, UA, UB

    # Survey dp ratio check per pair per campaign (deposit detection)
    def deposit_fit(ln, rows):
        """rows: dict pipe->survey row (with line_flow). Fits bore of the pipe with lower dp so dp match."""
        L = lines.loc[ln]; op = OP[L.oil]; D0 = L.bore_mm / 1000.0; Lm = L.length_m
        pA, pB = ln + '-A', ln + '-B'
        res = {}
        if pA in rows and pB in rows:
            xa, xb = rows[pA], rows[pB]
            fa = xa.flow_t_h; fb = xb.flow_t_h
            ra = dict(fl=fa, tin=xa.t_in_C, tout=xa.t_out_C, ta=xa.t_amb_C)
            rb = dict(fl=fb, tin=xb.t_in_C, tout=xb.t_out_C, ta=xb.t_amb_C)
        else:
            return None
        UA = fitU(ra['fl'], D0, Lm, ra['tin'], ra['tout'], ra['ta'], op)
        UB = fitU(rb['fl'], D0, Lm, rb['tin'], rb['tout'], rb['ta'], op)
        dA = dp_of(ra['fl'], D0, Lm, ra['tin'], ra['ta'], UA, op)
        dB = dp_of(rb['fl'], D0, Lm, rb['tin'], rb['ta'], UB, op)
        ratio = dA / dB
        if abs(ratio - 1) < 0.008:
            return dict(DA=D0, DB=D0, UA=UA, UB=UB, ratio=ratio)
        # lower-dp pipe has deposit
        if dA < dB:
            low, r, target, U0 = 'A', ra, dB, UA
        else:
            low, r, target, U0 = 'B', rb, dA, UB
        def resid(Dd):
            U = fitU(r['fl'], Dd, Lm, r['tin'], r['tout'], r['ta'], op)
            return dp_of(r['fl'], Dd, Lm, r['tin'], r['ta'], U, op) - target
        try:
            Dd = brentq(resid, D0 * 0.3, D0, xtol=1e-7)
        except ValueError:
            Dd = D0
        U = fitU(r['fl'], Dd, Lm, r['tin'], r['tout'], r['ta'], op)
        out = dict(DA=D0, DB=D0, UA=UA, UB=UB, ratio=ratio)
        out['D' + low] = Dd; out['U' + low] = U
        return out

    pair_dev = {}
    for ln, L in lines.iterrows():
        if int(L.pipes) != 2: continue
        g = surv[surv['pipe'].str.startswith(ln + '-')]
        fits = []
        for date in sorted(g.date.unique()):
            rows = {x['pipe']: x for _, x in g[g.date == date].iterrows()}
            fd = deposit_fit(ln, rows)
            if fd is not None: fits.append(fd)
        if not fits: continue
        fitd = fits[-1]
        pair_dev[ln] = abs(fits[-1]['ratio'] - 1) + abs(fits[-1]['ratio'] - fits[0]['ratio'])
        D0 = L.bore_mm / 1000.0
        for s in 'AB':
            p = ln + '-' + s
            bores = [f['D' + s] for f in fits]
            if max(bores) - min(bores) > 0.004 * D0 and info[p]['status'] != 'unknown':
                info[p]['status'] = 'deposit'
                info[p]['drift'] = 4 * (max(bores) - min(bores)) / D0
            if abs(fitd['D' + s] - info[p]['D']) > 1e-9:
                info[p]['D'] = fitd['D' + s]
                lc = last_cover.get(p)
                gp = surv[surv['pipe'] == p]
                valid = gp[gp.date > lc] if lc is not None else gp
                Us = [fitU(x.flow_t_h, info[p]['D'], L.length_m, x.t_in_C, x.t_out_C, x.t_amb_C, OP[L.oil])
                      for _, x in valid.iterrows()]
                if Us:
                    info[p]['U'] = Us[-1] if info[p]['status'] in ('changing', 'deposit') else float(np.mean(Us))
        sys.stderr.write('%s bores %s\n' % (ln, [(round(float(f['DA'])*1000, 2), round(float(f['DB'])*1000, 2), round(float(f['ratio']), 4)) for f in fits]))

    # --- survey crew order
    need = []
    for p, rec in info.items():
        if rec['status'] == 'unknown': need.append((0, 0.0, p))
        elif rec['status'] in ('changing', 'deposit'): need.append((1, -rec.get('drift', 0) / max(rec['U'], 1e-9), p))
    need.sort()
    order = [p for _, _, p in need][:allowance]
    # spare orders: one pipe of pairs not yet covered, to read their present division
    covered = {pipe_line[p] for p in order}
    spare = []
    for ln, L in lines.iterrows():
        if int(L.pipes) == 2 and ln not in covered:
            spare.append((-pair_dev.get(ln, 0.0), ln))
    spare.sort()
    for _, ln in spare:
        if len(order) >= allowance: break
        order.append(ln + '-A')
    sys.stderr.write('order: %s\n' % order)
    if order:
        crew = run_crew(pkg, order)
        for p, x in crew.items():
            ln = pipe_line[p]; L = lines.loc[ln]; op = OP[L.oil]
            other = None
            if int(L.pipes) == 2:
                other = ln + '-' + ('B' if p.endswith('A') else 'A')
            # deposit check using division read
            D = info[p]['D']
            U = fitU(x.flow_t_h, D, L.length_m, x.t_in_C, x.t_out_C, x.t_amb_C, op)
            if other is not None:
                fo = x.line_flow_t_h - x.flow_t_h
                if other in crew:
                    pass
                else:
                    Do, Uo_ = info[other]['D'], info[other]['U']
                    dpo = dp_of(fo, Do, L.length_m, x.t_in_C, x.t_amb_C, Uo_, op)
                    dpp = dp_of(x.flow_t_h, D, L.length_m, x.t_in_C, x.t_amb_C, U, op)
                    if dpp < dpo * (1 - 0.008):
                        def resid(Dd):
                            Ux = fitU(x.flow_t_h, Dd, L.length_m, x.t_in_C, x.t_out_C, x.t_amb_C, op)
                            return dp_of(x.flow_t_h, Dd, L.length_m, x.t_in_C, x.t_amb_C, Ux, op) - dpo
                        try:
                            D = brentq(resid, D * 0.3, D, xtol=1e-7)
                            U = fitU(x.flow_t_h, D, L.length_m, x.t_in_C, x.t_out_C, x.t_amb_C, op)
                        except ValueError:
                            pass
                    elif dpo < dpp * (1 - 0.008):
                        # the other pipe has a bore below the one assumed
                        def resid2(Dd):
                            return dp_of(fo, Dd, L.length_m, x.t_in_C, x.t_amb_C, Uo_, op) - dpp
                        try:
                            info[other]['D'] = brentq(resid2, Do * 0.3, Do, xtol=1e-7)
                        except ValueError:
                            pass
                    sys.stderr.write('crew %s dp ratio %.4f D %.2f\n' % (p, dpp / dpo, D * 1000))
            info[p]['D'] = D; info[p]['U'] = U; info[p]['status'] = 'crew'
        # pairs where both pipes surveyed by crew: deposit fit from crew readings
        done = set()
        for p in crew:
            ln = pipe_line[p]
            if int(lines.loc[ln].pipes) == 2 and ln not in done and (ln + '-A') in crew and (ln + '-B') in crew:
                done.add(ln)
                fitd = deposit_fit(ln, {q: crew[q] for q in (ln + '-A', ln + '-B')})
                for s in 'AB':
                    info[ln + '-' + s]['D'] = fitd['D' + s]; info[ln + '-' + s]['U'] = fitd['U' + s]

    # --- records
    results = {}
    for ln, g in recs.groupby('line', sort=False):
        g = g.sort_values('hour')
        L = lines.loc[ln]; op = OP[L.oil]; Lm = L.length_m
        if int(L.pipes) == 1:
            r = info[ln + '-A']
            for rid, fl, ti, ta in zip(g.record, g.flow_t_h, g.t_in_C, g.t_amb_C):
                dp, T = pipe(fl / 3.6, r['D'], Lm, ti, ta, r['U'], op)
                results[rid] = (dp / 1000, T)
            continue
        rA, rB = info[ln + '-A'], info[ln + '-B']
        a_prev = None
        for _, x in g.iterrows():
            M = x.flow_t_h / 3.6; ti = x.t_in_C; ta = x.t_amb_C
            def both(a):
                pa, Ta_ = pipe(a * M, rA['D'], Lm, ti, ta, rA['U'], op)
                pb, Tb_ = pipe((1 - a) * M, rB['D'], Lm, ti, ta, rB['U'], op)
                return pa, pb, Ta_, Tb_
            cache = {}
            def gfun(a):
                if a not in cache:
                    pa, pb, _, _ = both(a); cache[a] = pa - pb
                return cache[a]
            def root(lo, hi):
                return brentq(gfun, lo, hi, xtol=1e-7)
            if a_prev is None:
                gg = [gfun(t) for t in GRID0]
                idx = [i for i in range(len(GRID0) - 1) if (gg[i] > 0) != (gg[i + 1] > 0)]
                if not idx:
                    a = GRID0[int(np.argmin(np.abs(gg)))]
                else:
                    if len(idx) > 1:
                        sys.stderr.write('warning: %s first record has %d divisions\n' % (ln, len(idx)))
                    i = min(idx, key=lambda i: abs(GRID0[i] - 0.5))
                    a = root(GRID0[i], GRID0[i + 1])
            else:
                g0 = gfun(a_prev)
                a = None
                if g0 == 0:
                    a = a_prev
                elif g0 > 0:
                    hi_a = a_prev
                    for t in GRID[GRID < a_prev][::-1]:
                        if gfun(t) <= 0:
                            a = root(t, hi_a); break
                        hi_a = t
                    if a is None: a = GRID[0]
                else:
                    lo_a = a_prev
                    for t in GRID[GRID > a_prev]:
                        if gfun(t) >= 0:
                            a = root(lo_a, t); break
                        lo_a = t
                    if a is None: a = GRID[-1]
            pa, pb, tA, tB = both(a)
            results[x.record] = (0.5 * (pa + pb) / 1000, a * tA + (1 - a) * tB)
            a_prev = a

    with open(out_csv, 'w') as f:
        f.write('record,dp_kPa,t_out_C\n')
        for rid in recs.record:
            dp, T = results[rid]
            f.write(f'{rid},{dp:.6g},{T:.4f}\n')

_g = np.concatenate([np.geomspace(1e-4, 0.02, 20), np.linspace(0.025, 0.5, 96)])
GRID = np.unique(np.concatenate([_g, 1 - _g]))
GRID0 = [float(t) for t in GRID[::2]]

def run_crew(pkg, order):
    exe = shutil.which('heatsurvey')
    if exe is None and os.path.exists('/tmp/ol3_L2/app/heatsurvey'):
        exe = '/tmp/ol3_L2/app/heatsurvey'
    if exe is None:
        return {}
    try:
        r = subprocess.run([exe, pkg] + list(order), capture_output=True, text=True, timeout=30)
        if r.returncode != 0 or not r.stdout.strip():
            sys.stderr.write('heatsurvey failed: ' + r.stderr + '\n'); return {}
        df = pd.read_csv(io.StringIO(r.stdout), dtype={'pipe': str})
        return {x['pipe']: x for _, x in df.iterrows()}
    except Exception as e:
        sys.stderr.write('heatsurvey error: %s\n' % e); return {}

if __name__ == '__main__':
    main()
