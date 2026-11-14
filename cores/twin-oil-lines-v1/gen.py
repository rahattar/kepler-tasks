"""gen.py: the sites of core v1, from the sealed definition (line.py, pair.py).

core/environment/data/examples/<site>   two sites with results; the crew's book for each in core/environment/rig/sealed
core/environment/data/pending/<site>    one site without results; its book in hidden_lab only
hidden/<site>                           six sites with truth.csv; books in hidden_lab/sealed

A site: lines of one pipe or of a pair, three heat-loss survey campaigns of every pipe on file, a work log, and
an hourly run of records for every line. What is true of a pipe and not on any record:
  recovered  covering renewed or repaired after the last campaign (logged): the legible need
  narrowed   one pipe of a pair has lost 6 to 10 per cent of its bore (never logged, never surveyed)
  declining  one pipe's covering is failing: its coefficient rises campaign by campaign and has gone on rising
"""
import csv, json, os, sys
import numpy as np
from line import walther, nu_m2s, march
from pair import roots, follow, FR, FR_CHECK, pipe

HERE = os.path.dirname(os.path.abspath(__file__))
N_TRUTH = int(os.environ.get("N_TRUTH", "480")); N_CHECK = 96
OILS = {"FO-180": (950.0, 1900.0, 0.130, 180.0, 25.0), "FO-380": (975.0, 1880.0, 0.128, 380.0, 35.0),
        "FO-700": (990.0, 1860.0, 0.126, 700.0, 50.0), "VGO-90": (925.0, 1950.0, 0.132, 90.0, 16.0)}
CAMPAIGNS = ["2026-03-11", "2026-06-17", "2026-09-23"]
SITES = {  # seed, role, narrowed, declining, station temperature now, at the three campaigns
    "north_quay":  (51, "example", 0, 0, 8.0, (9.5, 22.0, 15.0)),
    "east_depot":  (52, "example", 0, 0, 11.0, (11.0, 24.5, 16.5)),
    "west_jetty":  (53, "pending", 1, 1, 7.0, (8.5, 21.0, 14.0)),
    "south_wharf": (61, "hidden", 1, 1, 9.0, (10.0, 23.0, 15.5)),
    "canal_basin": (62, "hidden", 1, 1, 6.0, (8.0, 20.5, 13.5)),
    "upper_yard":  (63, "hidden", 1, 0, 10.0, (10.5, 23.5, 16.0)),
    "kiln_road":   (64, "hidden", 0, 1, 7.5, (9.0, 21.5, 14.5)),
    "tank_row":    (65, "hidden", 0, 1, 12.0, (11.5, 24.0, 17.0)),
    "boiler_lane": (66, "hidden", 0, 0, 8.5, (9.5, 22.5, 15.0)),
}
NP, NS = int(os.environ.get("N_PAIRS", "20")), int(os.environ.get("N_SINGLES", "10"))
JOBS = ["valve gland repacked", "supports repainted", "thermometer pocket renewed", "flange gasket renewed", "drain valve renewed"]

def oilpar(oil, n):
    rho, cp, k, n50, n100 = OILS[oil]; A, B = walther(n50, n100); o = np.ones(n)
    return dict(rho=o * rho, cp=o * cp, k=o * k, A=o * A, B=o * B)

def pairpar(lines, idx, M, Tin, Ta, when):
    """parameters of pair cases; idx: line index of each case; when: 0..2 campaign, 3 now."""
    p = {k: np.zeros(len(idx)) for k in ("Da", "Db", "Ua", "Ub", "L", "rho", "cp", "k", "A", "B")}
    for q, (i, w) in enumerate(zip(idx, when)):
        l = lines[i]; o = oilpar(l["oil"], 1)
        p["Da"][q], p["Db"][q] = l["Dtrue"][0], l["Dtrue"][1]
        p["Ua"][q], p["Ub"][q] = l["U"][0][w], l["U"][1][w]; p["L"][q] = l["length_m"]
        for k in ("rho", "cp", "k", "A", "B"): p[k][q] = o[k][0]
    p["Tin"] = np.asarray(Tin, float); p["Ta"] = np.asarray(Ta, float)
    return p

def solve_pairs(lines, idx, M, Tin, Ta, when, n, fr):
    return roots(np.asarray(M, float), pairpar(lines, idx, M, Tin, Ta, when), n=n, fr=fr, iters=40 if n >= 240 else 22)

def landmarks(lines, pairs, tnow):
    """for each pair at its set temperature and the station temperature now: the delivered flow at which the
    weaker pipe's share falls below a quarter going down, and that at which it comes back going up [kg/s]."""
    G = 64; idx = []; M = []
    for i in pairs:
        l = lines[i]; ms = l["Umean"] * np.pi * l["bore_mm"] / 1e3 * l["length_m"] / OILS[l["oil"]][1]
        g = np.geomspace(0.04 * ms, 25 * ms, G); idx += [i] * G; M += list(g)
    M = np.array(M); n = len(M)
    sol = solve_pairs(lines, idx, M, [lines[i]["t_set"] for i in idx], [tnow] * n, [3] * n, N_CHECK, FR_CHECK)
    out = {}
    for q, i in enumerate(pairs):
        c = np.arange(q * G, (q + 1) * G)
        down, f1 = follow(c[::-1], sol); up, f2 = follow(c, sol, start=sol[1][down[int(c[0])]])
        sd = np.array([min(sol[1][down[int(k)]], 1 - sol[1][down[int(k)]]) for k in c]); su = np.array([min(sol[1][up[int(k)]], 1 - sol[1][up[int(k)]]) for k in c])
        low_d = np.nonzero(sd < 0.25)[0]; low_u = np.nonzero(su < 0.25)[0]
        out[i] = (M[c][low_d.max()], M[c][low_u.max()], M[c][low_d.min()]) if len(low_d) and len(low_u) else None
    return out

def draw_site(name):
    seed, role, nX, nZ, tnow, tcamp = SITES[name]
    rng = np.random.default_rng(seed)
    oils = list(rng.choice(sorted(OILS), size=3, replace=False))
    lines = []
    order = rng.permutation(NP + NS)
    for i in range(NP + NS):
        pipes = 2 if order[i] < NP else 1
        U0 = rng.uniform(5.0, 11.0) if pipes == 2 else rng.uniform(2.5, 9.0)
        l = dict(line="FL-%d%02d" % (1 + i // 8, 11 + 2 * (i % 8) + i // 8), pipes=pipes, oil=str(rng.choice(oils)),
                 bore_mm=int(rng.choice([40, 50, 65, 80, 100, 125])), length_m=int(rng.integers(20, 90) * 10), t_set=float(rng.integers(66, 94)))
        us = [U0] if pipes == 1 else [U0, U0 * rng.uniform(0.8, 1.25)]
        l["U"] = [[u, u, u, u] for u in us]; l["Dtrue"] = [l["bore_mm"] / 1e3] * pipes; l["kind"] = ["sound"] * pipes
        lines.append(l)
    names = [(i, p) for i, l in enumerate(lines) for p in range(l["pipes"])]
    pick = list(rng.permutation(len(names)))
    def take(cond=lambda i, p: True):
        for k in pick:
            i, p = names[k]
            if lines[i]["kind"][p] == "sound" and cond(i, p) and all(x == "sound" for x in lines[i]["kind"]):
                pick.remove(k); return i, p
        raise RuntimeError("no pipe left")
    log = []
    nL = int(rng.integers(3, 5))
    for _ in range(nL):                                     # covering renewed or repaired after the last campaign
        i, p = take(); f = rng.uniform(0.42, 0.6); job = "covering renewed"
        if rng.random() < 0.3: f = rng.uniform(0.62, 0.74); job = "covering repaired"
        lines[i]["U"][p][3] *= f; lines[i]["kind"][p] = "recovered"
        log.append(("2026-10-%02d" % rng.integers(5, 29), i, p, job))
    for _ in range(3):                                      # the same jobs before the last campaign: surveyed since
        i, p = take(); c = int(rng.integers(1, 3)); f = rng.uniform(0.45, 0.7)
        for w in range(c, 4): lines[i]["U"][p][w] *= f
        lines[i]["kind"][p] = "earlier"
        log.append((["2026-05-%02d", "2026-08-%02d"][c - 1] % rng.integers(4, 27), i, p, "covering renewed" if f < 0.6 else "covering repaired"))
    for _ in range(nX):
        i, p = take(lambda i, p: lines[i]["pipes"] == 2)
        lines[i]["Dtrue"][p] *= rng.uniform(0.90, 0.935); lines[i]["kind"][p] = "narrowed"
    for _ in range(nZ):
        i, p = take(); g = rng.uniform(1.15, 1.22)
        lines[i]["U"][p] = [lines[i]["U"][p][0] * x for x in (1.0, g, g * rng.uniform(1.17, 1.25), g * 1.21 * rng.uniform(1.45, 1.7))]
        lines[i]["kind"][p] = "declining"
    for _ in range(int(rng.integers(8, 13))):               # jobs that touch nothing TS-2 uses
        i, p = names[int(rng.integers(len(names)))]
        log.append(("2026-%02d-%02d" % (rng.integers(2, 11), rng.integers(1, 28)), i, p, str(rng.choice(JOBS))))
    for l in lines: l["Umean"] = float(np.mean([u[3] for u in l["U"]]))
    return dict(name=name, role=role, rng=rng, lines=lines, log=sorted(log), oils=oils, tnow=tnow, tcamp=tcamp,
                allowance=nL + nX + nZ, legible=nL)

def reynolds(l, p, m, Tin):
    rho, cp, k, n50, n100 = OILS[l["oil"]]; A, B = walther(n50, n100)
    return 4 * m / (np.pi * l["Dtrue"][p] * rho * nu_m2s(A, B, Tin))

def history(rng, l, hours, lm, tnow, calm=False):
    h = np.arange(hours)
    tin = l["t_set"] + 0.4 * np.sin(2 * np.pi * (h + rng.uniform(0, 24)) / 37.0) + rng.normal(0, 0.15, hours)
    ta = tnow + 0.8 * np.sin(2 * np.pi * (h - 15) / 24.0) + rng.normal(0, 0.1, hours)
    ms = l["Umean"] * np.pi * l["bore_mm"] / 1e3 * l["length_m"] / OILS[l["oil"]][1]
    def level(z):
        if lm is None:
            if calm:                                        # kept laminar: well inside Re 2000 at the set temperature
                rho, cp, k, n50, n100 = OILS[l["oil"]]; A, B = walther(n50, n100)
                top = 2000 * np.pi * min(l["Dtrue"]) * rho * nu_m2s(A, B, l["t_set"] + 1.0) / 4 * l["pipes"]
                return rng.uniform(0.35, 0.85) * top if l["pipes"] == 1 else rng.uniform(0.25, 0.55) * top
            return rng.uniform(1.5 * ms, 6 * ms)
        dn, up, lo = lm
        if z == "H": return rng.uniform(1.25 * up, 2.0 * up)
        if z == "B": return rng.uniform(1.12 * dn, 0.88 * up)
        return rng.uniform(max(0.5 * dn, 1.3 * lo), 0.84 * dn)
    hasB = lm is not None and 1.12 * lm[0] < 0.82 * lm[1]
    hasU = not calm and lm is not None and max(0.5 * lm[0], 1.3 * lm[2]) < 0.8 * lm[0]
    flow = np.zeros(hours); t = 0; z = "H"; seq = ""
    while t < hours:
        d = int(rng.integers(5, 13)); flow[t:t + d] = level(z) * (1 + rng.normal(0, 0.004, len(flow[t:t + d]))); seq += z; t += d
        if hasU: z = {"H": "U", "U": str(rng.choice(["B", "H"] if hasB else ["H"])), "B": str(rng.choice(["U", "H"]))}[z]
    return np.round(flow * 3.6, 3), np.round(tin, 1), np.round(ta, 1), seq

def run_pairs(lines, hist, n, fr, scale=1.0, sub=0):
    """the state of every pair through its records. hist: {line index: (flow t/h, tin, ta)}."""
    idx, M, Tin, Ta, seg = [], [], [], [], {}
    for i, (flow, tin, ta) in hist.items():
        m = flow / 3.6 * scale
        if sub:
            w = np.linspace(0, 1, sub + 1)[1:]
            ex = lambda v: np.concatenate([[v[0]], (v[:-1, None] + (v[1:] - v[:-1])[:, None] * w).ravel()])
            m, tin, ta = ex(m), ex(np.asarray(tin, float)), ex(np.asarray(ta, float))
        seg[i] = (len(M), len(m)); idx += [i] * len(m); M += list(m); Tin += list(tin); Ta += list(ta)
    sol = solve_pairs(lines, idx, M, Tin, Ta, [3] * len(M), n, fr)
    out = {}
    for i, (s0, cnt) in seg.items():
        pick, flags = follow(range(s0, s0 + cnt), sol)
        ks = [pick.get(c) for c in range(s0, s0 + cnt)]
        if any(k is None for k in ks): out[i] = None; continue
        ks = np.array(ks)
        sh = sol[1][ks]; step = sub if sub else 1
        out[i] = dict(share=sh[::step], dp=sol[2][ks][::step], T=sol[3][ks][::step], flags=flags)
    return out

def build(name):
    s = draw_site(name); rng = s["rng"]; lines = s["lines"]
    pairs = [i for i, l in enumerate(lines) if l["pipes"] == 2]
    lm = landmarks(lines, pairs, s["tnow"])
    # survey rating of each line: well above anything the pair does at low flow, the same at every campaign
    for i, l in enumerate(lines):
        ms = l["Umean"] * np.pi * l["bore_mm"] / 1e3 * l["length_m"] / OILS[l["oil"]][1]
        l["m_survey"] = (2.4 * lm[i][1] if lm.get(i) else 5 * ms) if l["pipes"] == 2 else 3.5 * ms
        l["m_survey"] = round(l["m_survey"] * 3.6, 2) / 3.6
    # histories of the lines, redrawn until the states do not hang on the last per cent
    hist = {}; todo = list(range(len(lines))); seqs = {}; fails = {}
    for i, l in enumerate(lines):
        # a line whose ordinary flows would leave the laminar scope is kept calm from the start
        rho, cp, k, n50, n100 = OILS[l["oil"]]; A, B = walther(n50, n100)
        top = 2000 * np.pi * min(l["Dtrue"]) * rho * nu_m2s(A, B, l["t_set"] + 1.0) / 4 * l["pipes"]
        ms = l["Umean"] * np.pi * l["bore_mm"] / 1e3 * l["length_m"] / OILS[l["oil"]][1]
        if (l["pipes"] == 1 and 6 * ms > 0.9 * top) or (l["pipes"] == 2 and (2.0 * lm[i][1] if lm.get(i) else 6 * ms) > 0.55 * top): fails[i] = 8
    for attempt in range(40):
        for i in todo:
            l = lines[i]; hours = int(rng.integers(36, 49))
            # a line that will not give a robust history in eight draws is kept on high flow throughout
            calm = fails.get(i, 0) >= 8
            flow, tin, ta, seq = history(rng, l, hours, None if calm else lm.get(i), s["tnow"], calm=calm)
            hist[i] = (flow, tin, ta); seqs[i] = seq
        tp = {i: hist[i] for i in todo if lines[i]["pipes"] == 2}
        bad = set(); cls = lambda r: np.minimum(r["share"], 1 - r["share"]) < 0.3
        if tp:
            base = run_pairs(lines, tp, N_CHECK, FR_CHECK)
            lo = run_pairs(lines, tp, N_CHECK, FR_CHECK, scale=0.96); hi = run_pairs(lines, tp, N_CHECK, FR_CHECK, scale=1.04)
            fine = run_pairs(lines, tp, N_CHECK, FR_CHECK, sub=6)
            for i in tp:
                b = base[i]
                if b is None or b["flags"] or lo[i] is None or hi[i] is None or fine[i] is None or lo[i]["flags"] or hi[i]["flags"] or fine[i]["flags"]:
                    bad.add(i); continue
                if not (np.array_equal(cls(b), cls(lo[i])) and np.array_equal(cls(b), cls(hi[i]))): bad.add(i); continue
                if np.max(np.abs(b["share"] - fine[i]["share"])) > 0.02: bad.add(i); continue
                m = hist[i][0] / 3.6
                if max(reynolds(lines[i], 0, m * b["share"], hist[i][1]).max(), reynolds(lines[i], 1, m * (1 - b["share"]), hist[i][1]).max()) > 2000: bad.add(i)
        for i in todo:
            if lines[i]["pipes"] == 1 and reynolds(lines[i], 0, hist[i][0] / 3.6, hist[i][1]).max() > 2000: bad.add(i)
        todo = sorted(bad)
        for i in todo:
            fails[i] = fails.get(i, 0) + 1
            if os.environ.get("WHY") and lines[i]["pipes"] == 1:
                print("   attempt %d single %s Re %.0f" % (attempt, lines[i]["line"], reynolds(lines[i], 0, hist[i][0] / 3.6, hist[i][1]).max()), flush=True)
            if os.environ.get("WHY") and lines[i]["pipes"] == 2:
                b = base[i]; why = "none" if b is None else str(b["flags"][:2])
                if b is not None and not b["flags"]:
                    m = hist[i][0] / 3.6
                    why = "lo %s hi %s fine %s  cls lo %s hi %s  dshare %.3f  Re %.0f" % (
                        lo[i] and lo[i]["flags"][:1], hi[i] and hi[i]["flags"][:1], fine[i] and fine[i]["flags"][:1],
                        np.array_equal(cls(b), cls(lo[i])) if lo[i] else None, np.array_equal(cls(b), cls(hi[i])) if hi[i] else None,
                        np.max(np.abs(b["share"] - fine[i]["share"])) if fine[i] else -1,
                        max(reynolds(lines[i], 0, m * b["share"], hist[i][1]).max(), reynolds(lines[i], 1, m * (1 - b["share"]), hist[i][1]).max()))
                print("   attempt %d line %s kinds %s lm %s seq %s: %s" % (attempt, lines[i]["line"], lines[i]["kind"], lm.get(i), seqs[i], why), flush=True)
        if not todo: break
    else:
        raise RuntimeError("no robust history for lines %s of %s" % (todo, name))
    # truth
    truth = {}; stalled = 0
    tp = {i: hist[i] for i in pairs}
    res = run_pairs(lines, tp, N_TRUTH, FR)
    chk = run_pairs(lines, tp, N_CHECK, FR_CHECK)
    for i in pairs:
        assert not res[i]["flags"] and np.max(np.abs(res[i]["share"] - chk[i]["share"])) < 0.02, (name, lines[i]["line"], res[i]["flags"])
        for h in range(len(hist[i][0])):
            truth["%s/%02d" % (lines[i]["line"], h)] = (res[i]["dp"][h] / 1e3, res[i]["T"][h], float(res[i]["share"][h]))
        stalled += int((np.minimum(res[i]["share"], 1 - res[i]["share"]) < 0.3).sum())
    for i, l in enumerate(lines):
        if l["pipes"] == 1:
            flow, tin, ta = hist[i]; o = oilpar(l["oil"], len(flow))
            dp, T = march(flow / 3.6, l["Dtrue"][0], l["length_m"], l["U"][0][3], tin, ta, o["rho"], o["cp"], o["k"], o["A"], o["B"], n=N_TRUTH)
            for h in range(len(flow)): truth["%s/%02d" % (l["line"], h)] = (dp[h] / 1e3, T[h], 1.0)
    # the heat-loss runs: three campaigns on file and the pipe as it stands now (the crew's book)
    runs = {}
    for w in range(4):
        ta_w = s["tcamp"][w] if w < 3 else s["tnow"]
        t1 = {i: round(l["t_set"] + float(rng.normal(0, 0.5)), 1) for i, l in enumerate(lines)}
        sol = solve_pairs(lines, pairs, [lines[i]["m_survey"] for i in pairs], [t1[i] for i in pairs], [ta_w] * len(pairs), [w] * len(pairs), N_TRUTH, FR)
        for q, i in enumerate(pairs):
            k = np.nonzero(sol[0] == q)[0]
            assert len(k) == 1 and sol[4][k[0]], (name, lines[i]["line"], "survey state not unique", w)
            sh = sol[1][k[0]]; m = lines[i]["m_survey"]
            for p, (frac, T2) in enumerate(((sh, sol[5][k[0]]), (1 - sh, sol[6][k[0]]))):
                runs[(w, i, p)] = (m * 3.6, m * frac * 3.6, t1[i], T2, ta_w)
        for i, l in enumerate(lines):
            if l["pipes"] == 1:
                o = oilpar(l["oil"], 1)
                dp, T = march(np.array([l["m_survey"]]), l["Dtrue"][0], l["length_m"], l["U"][0][w], t1[i], ta_w, o["rho"], o["cp"], o["k"], o["A"], o["B"], n=N_TRUTH)
                runs[(w, i, 0)] = (l["m_survey"] * 3.6, l["m_survey"] * 3.6, t1[i], T[0], ta_w)
    def reading(r):   # what the crew writes down: flows good to 0.2 per cent, oil temperatures to 0.02 K
        return ("%.4f" % (r[0] * (1 + rng.normal(0, 0.0005))), "%.4f" % (r[1] * (1 + rng.normal(0, 0.0005))), "%.2f" % (r[2] + rng.normal(0, 0.004)),
                "%.2f" % (r[3] + rng.normal(0, 0.004)), "%.1f" % r[4])
    pid = lambda i, p: "%s-%s" % (lines[i]["line"], "AB"[p])
    base = {"example": "core/environment/data/examples", "pending": "core/environment/data/pending", "hidden": "hidden"}[s["role"]]
    out = os.path.join(HERE, base, name); os.makedirs(out, exist_ok=True)
    nrec = sum(len(hist[i][0]) for i in range(len(lines)))
    json.dump(dict(site=name, lines=len(lines), records=nrec, survey_allowance=s["allowance"]), open(os.path.join(out, "site.json"), "w"), indent=1)
    W = lambda fn, head, rows: csv.writer(open(os.path.join(out, fn), "w", newline=""), lineterminator="\n").writerows([head] + rows)
    W("oils.csv", ["oil", "density_kg_m3", "cp_J_kgK", "k_W_mK", "nu50_cSt", "nu100_cSt"], [[o] + ["%g" % x for x in OILS[o]] for o in s["oils"]])
    W("lines.csv", ["line", "pipes", "bore_mm", "length_m", "oil"], [[l["line"], l["pipes"], l["bore_mm"], l["length_m"], l["oil"]] for l in lines])
    W("surveys.csv", ["date", "pipe", "line_flow_t_h", "flow_t_h", "t_in_C", "t_out_C", "t_amb_C"],
      [[CAMPAIGNS[w], pid(i, p)] + list(reading(runs[(w, i, p)])) for w in range(3) for i, l in enumerate(lines) for p in range(l["pipes"])])
    W("work_log.csv", ["date", "pipe", "job"], [[d, pid(i, p), job] for d, i, p, job in s["log"]])
    W("records.csv", ["record", "line", "hour", "flow_t_h", "t_in_C", "t_amb_C"],
      [["%s/%02d" % (l["line"], h), l["line"], h, "%.3f" % hist[i][0][h], "%.1f" % hist[i][1][h], "%.1f" % hist[i][2][h]] for i, l in enumerate(lines) for h in range(len(hist[i][0]))])
    book = dict(allowance=s["allowance"], readings={pid(i, p): list(reading(runs[(3, i, p)])) for i, l in enumerate(lines) for p in range(l["pipes"])})
    for d in ["hidden_lab/sealed"] + (["core/environment/rig/sealed"] if s["role"] == "example" else []):
        os.makedirs(os.path.join(HERE, d), exist_ok=True); json.dump(book, open(os.path.join(HERE, d, name + ".json"), "w"))
    recs = [r for r in csv.DictReader(open(os.path.join(out, "records.csv")))]
    if s["role"] == "example":
        W("expected.csv", ["record", "dp_kPa", "t_out_C"], [[r["record"], "%.5g" % truth[r["record"]][0], "%.2f" % truth[r["record"]][1]] for r in recs])
    tdir = out if s["role"] == "hidden" else os.path.join(HERE, "hidden_lab", "truth"); os.makedirs(tdir, exist_ok=True)
    with open(os.path.join(tdir, "truth.csv" if s["role"] == "hidden" else name + ".csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["record", "dp_kPa", "t_out_C", "share_a"])
        for r in recs: w.writerow([r["record"], repr(float(truth[r["record"]][0])), repr(float(truth[r["record"]][1])), "%.4f" % truth[r["record"]][2]])
    sealed = dict(site=name, allowance=s["allowance"], legible=s["legible"],
                  pipes={pid(i, p): dict(kind=l["kind"][p], bore_true_mm=l["Dtrue"][p] * 1e3, u=l["U"][p]) for i, l in enumerate(lines) for p in range(l["pipes"])},
                  histories={l["line"]: seqs[i] for i, l in enumerate(lines)})
    os.makedirs(os.path.join(HERE, "hidden_lab", "sites"), exist_ok=True)
    json.dump(sealed, open(os.path.join(HERE, "hidden_lab", "sites", name + ".json"), "w"), indent=1)
    odd = ["%s %s" % (k, v["kind"]) for k, v in sealed["pipes"].items() if v["kind"] not in ("sound", "earlier")]
    print("%-12s %-8s lines %d pipes %d records %d  allowance %d (legible %d)  records with a pipe under 0.3: %d  | %s" % (
        name, s["role"], len(lines), len(sealed["pipes"]), nrec, s["allowance"], s["legible"], stalled, "; ".join(odd)), flush=True)

if __name__ == "__main__":
    import warnings; warnings.simplefilter("ignore")
    for n in (sys.argv[1:] or list(SITES)):
        build(n)
