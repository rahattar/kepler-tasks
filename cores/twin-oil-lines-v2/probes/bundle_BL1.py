import sys, os, json, subprocess, io
import numpy as np
import pandas as pd

NS = int(os.environ.get("LINES_NS", "24"))
NWI = 3
NF = 161
NREF = 3
LN10 = np.log(10.0)

def oil_par(r):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(r.nu50_cSt + 0.7)); y2 = np.log10(np.log10(r.nu100_cSt + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1)); A = y1 + B * np.log10(T1)
    return dict(rho=float(r.density_kg_m3), cp=float(r.cp_J_kgK), k=float(r.k_W_mK), A=A, B=B)

def nu(A, B, Tc):
    return (10.0 ** (10.0 ** (A - B * np.log10(Tc + 273.15))) - 0.7) * 1e-6

def pipe(m, D, L, Uo, Tin, Ta, rho, cp, k, A, B):
    """All arguments broadcastable arrays. Returns dp (Pa), Tout (C)."""
    m, D, L, Uo, Tin, Ta, rho, cp, k, A, B = np.broadcast_arrays(*[np.asarray(v, float) for v in (m, D, L, Uo, Tin, Ta, rho, cp, k, A, B)])
    u = 4 * m / (np.pi * D * D * rho)
    GzC = 4 * m * cp / (np.pi * k)
    cP = 32 * rho * u / (D * D)
    cT = np.pi * D / (m * cp)
    kD = k / D
    def node(s, Tb):
        # returns cooling rate a (per unit s) and dp rate (per unit s)
        x = L * s ** 3
        dxds = 3 * L * s * s
        Gz = GzC / np.maximum(x, 1e-300)
        g = 1.077 * np.cbrt(Gz) - 0.7
        h0 = np.cbrt(3.66 ** 3 + 0.7 ** 3 + g ** 3) * kD
        nub = nu(A, B, Tb)
        Tw = (h0 * Tb + Uo * Ta) / (h0 + Uo)
        for _ in range(NWI):
            h = h0 * (nu(A, B, Tw) / nub) ** (-0.14)
            Tw = (h * Tb + Uo * Ta) / (h + Uo)
        r = nu(A, B, Tw) / nub
        h = h0 * r ** (-0.14)
        return cT * h * Uo / (h + Uo) * dxds, cP * nub * np.sqrt(r) * dxds
    Tb = Tin.copy(); P = np.zeros_like(m)
    hs = 1.0 / NS
    a0, p0 = node(0.0, Tb)
    a0 = np.zeros_like(m); p0 = np.zeros_like(m)
    for i in range(NS):
        s = i * hs
        d0 = Tb - Ta
        Tm = Tb; Te = Tb
        am = a0; ae = a0
        for it in range(2):
            am, pm = node(s + hs / 2, Tm)
            ae, pe = node(s + hs, Te)
            Eh = hs / 2 * (5 * a0 + 8 * am - ae) / 12
            E = hs / 6 * (a0 + 4 * am + ae)
            Tm = Ta + d0 * np.exp(-Eh)
            Te = Ta + d0 * np.exp(-E)
        P = P + hs / 6 * (p0 + 4 * pm + pe)
        Tb = Te; a0, p0 = node(s + hs, Te)
    return P, Tb

def fit_Uo(m, D, L, Tin, Tout, Ta, op):
    lo = np.full(len(m), np.log(1e-3)); hi = np.full(len(m), np.log(1e3))
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        _, T = pipe(m, D, L, np.exp(mid), Tin, Ta, *op)
        up = T > Tout
        lo = np.where(up, mid, lo); hi = np.where(up, hi, mid)
    return np.exp(0.5 * (lo + hi))

def main():
    np.seterr(all="ignore")
    pkg, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, "site.json")))
    oils = {r.oil: oil_par(r) for r in pd.read_csv(os.path.join(pkg, "oils.csv")).itertuples()}
    lines = pd.read_csv(os.path.join(pkg, "lines.csv"))
    surv = pd.read_csv(os.path.join(pkg, "surveys.csv"), dtype={"date": str})
    work = pd.read_csv(os.path.join(pkg, "work_log.csv"), dtype={"date": str})
    rec = pd.read_csv(os.path.join(pkg, "records.csv"))
    linfo = {}; pipes = {}
    for r in lines.itertuples():
        names = [r.line + "-A"] + ([r.line + "-B"] if int(r.pipes) == 2 else [])
        linfo[r.line] = (names, r.bore_mm / 1000.0, float(r.length_m), oils[r.oil])
        for n in names: pipes[n] = r.line
    def opv(lns):
        return [np.array([linfo[l][3][key] for l in lns]) for key in ("rho", "cp", "k", "A", "B")]
    cov = work[work.job.astype(str).str.lower().str.contains("cover")]
    lastw = cov.groupby("pipe").date.max().to_dict()
    keep = np.array([not (p in lastw and d <= lastw[p]) for p, d in zip(surv["pipe"], surv["date"])], bool)
    vs = surv[keep][["pipe", "line_flow_t_h", "flow_t_h", "t_in_C", "t_out_C", "t_amb_C"]]
    have = set(vs["pipe"])
    need = [p for p in pipes if p not in have]
    allow = int(site.get("survey_allowance", 0))
    order = need[:allow]
    if order and not os.environ.get("LINES_NOSURVEY"):
        try:
            res = subprocess.run(["heatsurvey", pkg] + order, capture_output=True, text=True, timeout=30)
            sys.stderr.write(res.stderr)
            df = pd.read_csv(io.StringIO(res.stdout))
            if os.environ.get("LINES_DEBUG"): sys.stderr.write(res.stdout)
            vs = pd.concat([vs, df[vs.columns]], ignore_index=True)
        except Exception as e:
            sys.stderr.write("survey failed: %r\n" % (e,))
    missing = [p for p in pipes if p not in set(vs["pipe"])]
    if missing:
        vs = pd.concat([vs, surv[surv["pipe"].isin(missing)][vs.columns]], ignore_index=True)
    ln = [pipes[p] for p in vs["pipe"]]
    U = fit_Uo(vs.flow_t_h.values / 3.6, np.array([linfo[l][1] for l in ln]), np.array([linfo[l][2] for l in ln]),
               vs.t_in_C.values, vs.t_out_C.values, vs.t_amb_C.values, opv(ln))
    vs = vs.assign(U=U)
    Uo = vs.groupby("pipe").U.mean().to_dict()
    if os.environ.get("LINES_DEBUG"):
        for p, g in vs.groupby("pipe"): sys.stderr.write("%s %s\n" % (p, np.round(g.U.values, 4)))
    n = len(rec)
    rl = rec.line.values
    D = np.array([linfo[l][1] for l in rl]); L = np.array([linfo[l][2] for l in rl])
    op = opv(rl)
    M = rec.flow_t_h.values / 3.6; Tin = rec.t_in_C.values; Ta = rec.t_amb_C.values
    UA = np.array([Uo[linfo[l][0][0]] for l in rl])
    pair = np.array([len(linfo[l][0]) == 2 for l in rl])
    UB = np.array([Uo[linfo[l][0][-1]] for l in rl])
    dp = np.zeros(n); to = np.zeros(n)
    s = ~pair
    if s.any():
        P, T = pipe(M[s], D[s], L[s], UA[s], Tin[s], Ta[s], *[o[s] for o in op])
        dp[s] = P / 1000; to[s] = T
    ip = np.nonzero(pair)[0]
    if len(ip):
        col = lambda v: v[ip][:, None]
        args = lambda: (col(D), col(L))
        def G(F, sel=None):  # F shape (len(sel), nf)
            if sel is None: sel = slice(None)
            col = lambda v: v[ip][sel][:, None]
            Pa, TA = pipe(F * col(M), col(D), col(L), col(UA), col(Tin), col(Ta), *[col(o) for o in op])
            Pb, TB = pipe((1 - F) * col(M), col(D), col(L), col(UB), col(Tin), col(Ta), *[col(o) for o in op])
            return Pa - Pb, Pa, Pb, TA, TB
        tg = (np.arange(NF) + 0.5) / NF
        Fg = 0.5 - 0.5 * np.cos(np.pi * tg)
        Gg = G(np.broadcast_to(Fg, (len(ip), NF)))[0]
        recs = rec.iloc[ip].assign(_j=np.arange(len(ip)))
        seqs = [g.sort_values("hour")._j.values for _, g in recs.groupby("line", sort=False)]
        nl = len(seqs); maxlen = max(len(q) for q in seqs)
        f = np.zeros(len(ip))
        fprev = np.full(nl, np.nan)
        lines_of = [recs.line.values[q[0]] for q in seqs]
        for step in range(maxlen):
            act = np.array([step < len(q) for q in seqs])
            js = np.array([seqs[i][step] for i in range(nl) if act[i]])
            li = np.nonzero(act)[0]
            fp = fprev[li]
            first = np.isnan(fp)
            gp = np.zeros(len(js))
            if (~first).any():
                sub = js[~first]
                gp[~first] = G(fp[~first][:, None], sub)[0][:, 0]
            lo = np.zeros(len(js)); hi = np.zeros(len(js)); glo = np.zeros(len(js)); ghi = np.zeros(len(js))
            for q, j in enumerate(js):
                g = Gg[j]
                if first[q]:
                    st = np.nonzero((g[:-1] < 0) & (g[1:] >= 0))[0]
                    if len(st) != 1: sys.stderr.write("warn: %d divisions at start of %s\n" % (len(st), lines_of[li[q]]))
                    i = st[0] if len(st) else (0 if g[0] >= 0 else NF - 2)
                    lo[q], hi[q], glo[q], ghi[q] = Fg[i], Fg[i + 1], g[i], g[i + 1]
                    continue
                x = fp[q]
                if gp[q] > 0:  # shift oil away from A: f decreases
                    idx = np.nonzero((Fg < x) & (g < 0))[0]
                    if len(idx) == 0:
                        lo[q], hi[q], glo[q], ghi[q] = Fg[0] * 0.5, Fg[0], -1.0, 1.0; continue
                    i = idx[-1]
                    lo[q], glo[q] = Fg[i], g[i]
                    if i + 1 < NF and Fg[i + 1] < x: hi[q], ghi[q] = Fg[i + 1], g[i + 1]
                    else: hi[q], ghi[q] = x, gp[q]
                else:
                    idx = np.nonzero((Fg > x) & (g > 0))[0]
                    if len(idx) == 0:
                        lo[q], hi[q], glo[q], ghi[q] = Fg[-1], 0.5 + 0.5 * Fg[-1], -1.0, 1.0; continue
                    i = idx[0]
                    hi[q], ghi[q] = Fg[i], g[i]
                    if i - 1 >= 0 and Fg[i - 1] > x: lo[q], glo[q] = Fg[i - 1], g[i - 1]
                    else: lo[q], glo[q] = x, gp[q]
            for _ in range(NREF):
                fs = lo[:, None] + (hi - lo)[:, None] * np.linspace(0, 1, 7)[None, 1:-1]
                gs = G(fs, js)[0]
                fs = np.concatenate([lo[:, None], fs, hi[:, None]], 1)
                gs = np.concatenate([glo[:, None], gs, ghi[:, None]], 1)
                ch = (gs[:, :-1] < 0) & (gs[:, 1:] >= 0)
                kk = np.where(ch.any(1), ch.argmax(1), 0)
                r = np.arange(len(js))
                lo, hi, glo, ghi = fs[r, kk], fs[r, kk + 1], gs[r, kk], gs[r, kk + 1]
            den = np.where(ghi != glo, ghi - glo, 1)
            ff = np.clip(lo - glo * (hi - lo) / den, lo, hi)
            f[js] = ff
            fprev[li] = ff
        _, Pa, Pb, TA, TB = G(f[:, None])
        dp[ip] = 0.5 * (Pa[:, 0] + Pb[:, 0]) / 1000
        to[ip] = f * TA[:, 0] + (1 - f) * TB[:, 0]
    pd.DataFrame({"record": rec.record, "dp_kPa": np.round(dp, 5), "t_out_C": np.round(to, 4)}).to_csv(out, index=False)

if __name__ == "__main__":
    main()
