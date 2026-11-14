#!/usr/bin/env python3
"""ref_lines.py PACKAGE_DIR OUT_CSV: reference for core v1.

Outside coefficients from the heat-loss runs (TS-2 5.2); one order to the survey crew for the pipes whose
covering was worked on since the last campaign, a pipe of a pair that the runs on file show to be narrower than
laid, and a pipe whose coefficient moves from campaign to campaign with no work on it; each pair followed
through its records hour by hour."""

import numpy as np

def walther(nu50_cSt, nu100_cSt):
    z = lambda nu: np.log10(np.log10(np.asarray(nu, float) + 0.7))
    T1, T2 = np.log10(323.15), np.log10(373.15)
    B = (z(nu50_cSt) - z(nu100_cSt)) / (T2 - T1); A = z(nu50_cSt) + B * T1
    return A, B

def nu_m2s(A, B, T_C):
    return (10.0 ** (10.0 ** (A - B * np.log10(T_C + 273.15))) - 0.7) * 1e-6

def march(mdot, D, L, Uo, Tin, Ta, rho, cp, k, A, B, n=240, grade=3.0):
    """pressure drop [Pa] and outlet bulk temperature [C]; midpoint rule on stations crowded to the inlet, each step taken with the local decay of (Tb - Ta) so that a nearly stagnant line stays stable."""
    mdot, D, L, Uo, Tin, Ta, rho, cp, k, A, B = np.broadcast_arrays(*[np.asarray(a, float) for a in (mdot, D, L, Uo, Tin, Ta, rho, cp, k, A, B)])
    s = np.linspace(0.0, 1.0, n + 1) ** grade
    v = mdot / (rho * np.pi * D * D / 4.0)
    Tb = Tin.copy(); dp = np.zeros(mdot.shape)
    c1 = 3.66 ** 3 + 0.7 ** 3

    def local(Tb, xm):
        nub = nu_m2s(A, B, Tb)
        Gz = (v * D / nub) * (nub * rho * cp / k) * D / xm
        Nu0 = (c1 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1.0 / 3.0) * k / D
        Tw = (Nu0 * Tb + Uo * Ta) / (Nu0 + Uo)
        for _ in range(60):
            phi = nub / nu_m2s(A, B, Tw)
            hi = Nu0 * phi ** 0.14
            Tn = (hi * Tb + Uo * Ta) / (hi + Uo)
            done = np.max(np.abs(Tn - Tw)) < 1e-7
            Tw = Tn
            if done: break
        phi = nub / nu_m2s(A, B, Tw)
        hi = Nu0 * phi ** 0.14
        rate = np.pi * D * hi * Uo / (hi + Uo) / (mdot * cp)      # 1/m: d(Tb - Ta)/dx = -rate (Tb - Ta)
        grad = 32.0 * nub * rho * v / (D * D) / np.sqrt(phi)
        return rate, grad

    for i in range(n):
        h = (s[i + 1] - s[i]) * L; xm = 0.5 * (s[i] + s[i + 1]) * L
        r1, _ = local(Tb, xm)
        r2, g2 = local(Ta + (Tb - Ta) * np.exp(-0.5 * h * r1), xm)
        Tb = Ta + (Tb - Ta) * np.exp(-h * r2)
        dp = dp + h * g2
    return dp, Tb


import csv, os, subprocess, sys

MODE = "noorder"          # full | legible | noorder | narrow | decline   (the ladder; the reference is full)
N_STEPS = 100
_t = np.geomspace(2e-4, 0.30, 26)
FR = np.concatenate([_t, np.linspace(0.32, 0.68, 19), (1 - _t)[::-1]])


def run(m, D, L, U, Tin, Ta, oil, n=N_STEPS):
    return march(m, D, L, U, Tin, Ta, oil["rho"], oil["cp"], oil["k"], oil["A"], oil["B"], n=n)


def illinois(g, lo, hi, glo, ghi, tol, its=30):
    """root of g between lo and hi (arrays), g(lo) and g(hi) of opposite sign."""
    for _ in range(its):
        x = (lo * ghi - hi * glo) / (ghi - glo)
        gx = g(x)
        same = gx * glo > 0
        ghi = np.where(same, ghi * 0.5, gx); hi = np.where(same, hi, x)
        glo2 = np.where(same, gx, glo * 0.5); lo = np.where(same, x, lo); glo = glo2
        if np.max(np.abs(hi - lo) / tol) < 1.0: break
    return (lo * ghi - hi * glo) / (ghi - glo)


def derive_u(q, D, L, Tin, Tout, Ta, oil):
    """TS-2 5.2: the outside coefficient for which the pipe gives the outlet temperature that was read."""
    g = lambda u: run(q, D, L, np.exp(u), Tin, Ta, oil)[1] - Tout
    lo = np.full(len(q), np.log(0.05)); hi = np.full(len(q), np.log(200.0))
    return np.exp(illinois(g, lo, hi, g(lo), g(hi), 1e-7))


def pair_roots(M, P):
    """every steady division: (case, share of A, dp, mixed outlet temperature), by case and share."""
    R, J = len(M), len(FR)
    a = FR[None, :] * M[:, None]
    big = {k: np.repeat(v, J) for k, v in P.items()}
    f = (run(a.ravel(), big["Da"], big["L"], big["Ua"], big["Tin"], big["Ta"], big)[0]
         - run((M[:, None] - a).ravel(), big["Db"], big["L"], big["Ub"], big["Tin"], big["Ta"], big)[0]).reshape(R, J)
    sg = np.where(f >= 0, 1.0, -1.0)
    r, j = np.nonzero(sg[:, :-1] * sg[:, 1:] < 0)
    Q = {k: v[r] for k, v in P.items()}; Mr = M[r]
    g = lambda x: run(x, Q["Da"], Q["L"], Q["Ua"], Q["Tin"], Q["Ta"], Q)[0] - run(Mr - x, Q["Db"], Q["L"], Q["Ub"], Q["Tin"], Q["Ta"], Q)[0]
    slo = sg[r, j].copy()
    flo = np.where(f[r, j] == 0, -1e-30, f[r, j]); fhi = np.where(f[r, j + 1] == 0, 1e-30, f[r, j + 1])
    x = illinois(g, a[r, j].copy(), a[r, j + 1].copy(), flo, fhi, 1e-8 * Mr)
    d1, T1 = run(x, Q["Da"], Q["L"], Q["Ua"], Q["Tin"], Q["Ta"], Q); d2, T2 = run(Mr - x, Q["Db"], Q["L"], Q["Ub"], Q["Tin"], Q["Ta"], Q)
    return r, x / Mr, 0.5 * (d1 + d2), (x * T1 + (Mr - x) * T2) / Mr, slo < 0


def main(pkg, out):
    rd = lambda n: list(csv.DictReader(open(os.path.join(pkg, n))))
    oils = {r["oil"]: r for r in rd("oils.csv")}; lines = {r["line"]: r for r in rd("lines.csv")}
    surveys = rd("surveys.csv"); log = rd("work_log.csv"); rec = rd("records.csv")
    import json
    allowance = int(json.load(open(os.path.join(pkg, "site.json")))["survey_allowance"])

    def oilpar(names):
        o = [oils[n] for n in names]
        A, B = walther(np.array([float(x["nu50_cSt"]) for x in o]), np.array([float(x["nu100_cSt"]) for x in o]))
        return dict(rho=np.array([float(x["density_kg_m3"]) for x in o]), cp=np.array([float(x["cp_J_kgK"]) for x in o]),
                    k=np.array([float(x["k_W_mK"]) for x in o]), A=A, B=B)

    line_of = lambda p: p.rsplit("-", 1)[0]
    D0 = {p: float(lines[line_of(p)]["bore_mm"]) / 1e3 for p in {s["pipe"] for s in surveys}}
    Lm = {p: float(lines[line_of(p)]["length_m"]) for p in D0}

    def u_of(rows, bore=None):
        """outside coefficient from heat-loss runs (rows of surveys.csv or of the crew)."""
        names = [line_of(r["pipe"]) for r in rows]
        return derive_u(np.array([float(r["flow_t_h"]) for r in rows]) / 3.6, np.array([(bore or D0)[r["pipe"]] for r in rows]),
                        np.array([Lm[r["pipe"]] for r in rows]), np.array([float(r["t_in_C"]) for r in rows]),
                        np.array([float(r["t_out_C"]) for r in rows]), np.array([float(r["t_amb_C"]) for r in rows]), oilpar([lines[n]["oil"] for n in names]))

    dates = sorted({s["date"] for s in surveys})
    U = {}                                                   # (pipe, date) -> Uo with the bore as laid
    for s, u in zip(surveys, u_of(surveys)): U[(s["pipe"], s["date"])] = u
    row = {(s["pipe"], s["date"]): s for s in surveys}
    covering = {}                                            # pipe -> dates of covering work
    for j in log:
        if "covering" in j["job"]: covering.setdefault(j["pipe"], []).append(j["date"])
    last = dates[-1]
    legible = sorted(p for p, ds in covering.items() if max(ds) > last)

    # a pair's two pipes have one pressure drop: check it on the runs on file with the bores as laid
    def dp_of(p, d, bore=None, u=None):
        s = row[(p, d)]; o = oilpar([lines[line_of(p)]["oil"]])
        return run(np.array([float(s["flow_t_h"]) / 3.6]), (bore or D0[p]), Lm[p], (u if u is not None else U[(p, d)]), float(s["t_in_C"]), float(s["t_amb_C"]), o)[0][0]
    narrowed = {}
    if MODE in ("full", "narrow"):
        for ln, l in lines.items():
            if l["pipes"] != "2": continue
            a, b = ln + "-A", ln + "-B"
            ratio = [np.log(dp_of(a, d) / dp_of(b, d)) for d in dates]
            if min(ratio) > 0.06: narrowed[b] = a            # B shows too little drop at its flow: B is narrower than laid
            elif max(ratio) < -0.06: narrowed[a] = b
    # a covering that changes with no work on it is not the covering that was surveyed
    declining = []
    if MODE in ("full", "decline"):
        for p in D0:
            worked = [d for d in covering.get(p, []) if d > dates[-2]]
            if not worked and abs(np.log(U[(p, dates[-1])] / U[(p, dates[-2])])) > 0.05 and p not in legible: declining.append(p)
    order = [] if MODE == "noorder" else (legible + sorted(narrowed) + sorted(declining))[:allowance]
    now = {}
    if order:
        r = subprocess.run(["heatsurvey", pkg] + order, capture_output=True, text=True)
        got = list(csv.DictReader(r.stdout.splitlines())) if r.returncode == 0 else []
        now = {g["pipe"]: g for g in got}

    Unow = {p: U[(p, last)] for p in D0}; Dnow = dict(D0)
    plain = [p for p in now if p not in narrowed]
    if plain:
        for p, u in zip(plain, u_of([now[p] for p in plain])): Unow[p] = u
    for p, mate in narrowed.items():
        # the bore for which the pipe has its mate's pressure drop at the flows that were read
        s = now.get(p) or row[(p, last)]
        o = oilpar([lines[line_of(p)]["oil"]])
        if p in now:
            qm = (float(s["line_flow_t_h"]) - float(s["flow_t_h"])) / 3.6
            dpm = run(np.array([qm]), D0[mate], Lm[mate], Unow[mate], float(s["t_in_C"]), float(s["t_amb_C"]), o)[0][0]
        else:
            dpm = dp_of(mate, last)
        q1 = np.array([float(s["flow_t_h"]) / 3.6]); t1 = float(s["t_in_C"]); t2 = float(s["t_out_C"]); ta = float(s["t_amb_C"])
        lo, hi = 0.6 * D0[p], 1.0 * D0[p]
        for _ in range(3):                                   # three passes over 24 bores at once
            Dg = np.linspace(lo, hi, 24); og = {k: np.repeat(v, 24) for k, v in o.items()}
            ug = derive_u(np.repeat(q1, 24), Dg, Lm[p], t1, t2, ta, og)
            dg = run(np.repeat(q1, 24), Dg, Lm[p], ug, t1, ta, og)[0]
            k = int(np.argmax(dg < dpm))                     # the first bore wide enough
            lo, hi = Dg[max(k - 1, 0)], Dg[k]
        w = (dg[max(k - 1, 0)] - dpm) / (dg[max(k - 1, 0)] - dg[k]) if k > 0 else 0.0
        Dnow[p] = lo + w * (hi - lo); Unow[p] = u_of([s], {p: Dnow[p]})[0]

    # the records
    n = len(rec); dp = np.zeros(n); T = np.zeros(n)
    M = np.array([float(r["flow_t_h"]) for r in rec]) / 3.6; Tin = np.array([float(r["t_in_C"]) for r in rec]); Ta = np.array([float(r["t_amb_C"]) for r in rec])
    two = np.array([lines[r["line"]]["pipes"] == "2" for r in rec])
    O = oilpar([lines[r["line"]]["oil"] for r in rec])
    Lr = np.array([float(lines[r["line"]]["length_m"]) for r in rec])
    Da = np.array([Dnow[r["line"] + "-A"] for r in rec]); Ua = np.array([Unow[r["line"] + "-A"] for r in rec])
    s1 = ~two
    if s1.any():
        dp[s1], T[s1] = run(M[s1], Da[s1], Lr[s1], Ua[s1], Tin[s1], Ta[s1], {k: v[s1] for k, v in O.items()})
    t = np.nonzero(two)[0]
    if len(t):
        P = {k: v[t] for k, v in O.items()}
        P.update(Da=Da[t], Ua=Ua[t], Db=np.array([Dnow[rec[i]["line"] + "-B"] for i in t]), Ub=np.array([Unow[rec[i]["line"] + "-B"] for i in t]), L=Lr[t], Tin=Tin[t], Ta=Ta[t])
        r, share, d, Tm, stable = pair_roots(M[t], P)
        by = {}
        for i in range(len(r)): by.setdefault(int(r[i]), []).append(i)
        seq = {}
        for q, i in enumerate(t): seq.setdefault(rec[i]["line"], []).append((float(rec[i]["hour"]), q))
        for items in seq.values():
            prev = None
            for _, q in sorted(items):
                idx = by.get(q, [])
                if not idx: continue
                sh = share[idx]
                if prev is None:
                    st = [i for i in idx if stable[i]]; k = st[int(np.argmin(np.abs(share[st] - 0.5)))] if st else idx[0]
                else:
                    below = int(np.sum(sh < prev))
                    k = idx[below - 1] if below % 2 == 1 else idx[min(below, len(idx) - 1)]
                dp[t[q]], T[t[q]] = d[k], Tm[k]; prev = share[k]
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["record", "dp_kPa", "t_out_C"])
        for r_, a_, b_ in zip(rec, dp, T): w.writerow([r_["record"], "%.6g" % (a_ / 1e3), "%.4f" % b_])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
