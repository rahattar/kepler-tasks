"""gen.py: builds the nine sites of the core from the sealed definition (line.py, pair.py).
core/environment/data/examples/<site>  two sites with results: warm season, every pair divides evenly
core/environment/data/pending/<site>   one site without results: cold season, pairs that stall one line
core/hidden/<site>                     six sites with truth.csv: five cold, one warm
"""
import csv, json, os, sys
import numpy as np
from line import walther, nu_m2s
from pair import KEYS, FR, single, splits, follow

HERE = os.path.dirname(os.path.abspath(__file__))
N_TRUTH = int(os.environ.get("N_TRUTH", "480")); N_CHECK = 96
FR_CHECK = np.concatenate([np.geomspace(2e-4, 0.30, 40), np.linspace(0.32, 0.497, 12)])

OILS = {  # density kg/m3, cp J/kgK, k W/mK, viscosity cSt at 50 C and at 100 C
    "FO-180": (950.0, 1900.0, 0.130, 180.0, 25.0),
    "FO-380": (975.0, 1880.0, 0.128, 380.0, 35.0),
    "FO-700": (990.0, 1860.0, 0.126, 700.0, 50.0),
    "VGO-90": (925.0, 1950.0, 0.132, 90.0, 16.0),
}
SITES = {  # seed, role, season, pairs, singles, oils
    "north_quay":  (31, "example", "warm", 5, 4, ["FO-180", "FO-380", "VGO-90"]),
    "east_depot":  (32, "example", "warm", 6, 3, ["FO-180", "FO-380", "FO-700"]),
    "west_jetty":  (33, "pending", "cold", 5, 4, ["FO-180", "FO-380", "FO-700"]),
    "south_wharf": (41, "hidden", "cold", 5, 4, ["FO-180", "FO-380", "VGO-90"]),
    "canal_basin": (42, "hidden", "cold", 6, 3, ["FO-380", "FO-700"]),
    "upper_yard":  (43, "hidden", "warm", 5, 4, ["FO-180", "FO-380", "FO-700"]),
    "kiln_road":   (44, "hidden", "cold", 5, 4, ["FO-180", "FO-700", "VGO-90"]),
    "tank_row":    (45, "hidden", "cold", 6, 3, ["FO-180", "FO-380", "FO-700"]),
    "boiler_lane": (46, "hidden", "cold", 5, 4, ["FO-380", "FO-700", "VGO-90"]),
}

def par_of(line, M, Tin, Ta):
    rho, cp, k, n50, n100 = OILS[line["oil"]]; A, B = walther(n50, n100)
    one = np.ones(len(M))
    return dict(D=one * line["bore_mm"] / 1e3, L=one * line["length_m"], Uo=one * line["u_o"], Tin=np.asarray(Tin, float),
                Ta=np.asarray(Ta, float), rho=one * rho, cp=one * cp, k=one * k, A=one * A, B=one * B)

def landmarks(line, Tin, Ta):
    """at fixed temperatures: the range of delivered flow over which the even division is unstable, and the
    range over which a stable uneven division exists [kg/s]; None where there is no such range."""
    rho, cp, k, n50, n100 = OILS[line["oil"]]
    mstar = line["u_o"] * np.pi * line["bore_mm"] / 1e3 * line["length_m"] / cp
    M = np.geomspace(0.03 * mstar, 30 * mstar, 110)
    sym, asym = splits(M, par_of(line, M, Tin * np.ones(len(M)), Ta * np.ones(len(M))), n=N_CHECK, fr=FR_CHECK, iters=18)
    uns = M[~sym[2]]
    r, root, dpa, Ta_, st = asym
    ua = M[np.unique(r[st])] if st.any() else np.zeros(0)
    return (uns.min(), uns.max()) if len(uns) else None, (ua.min(), ua.max()) if len(ua) else None, mstar

def reynolds(line, m, Tin):
    rho, cp, k, n50, n100 = OILS[line["oil"]]; A, B = walther(n50, n100)
    D = line["bore_mm"] / 1e3
    return 4 * m / (np.pi * D * rho * nu_m2s(A, B, Tin))

def history(rng, line, season, hours, lm):
    """hourly flow, inlet temperature and surroundings temperature of one line."""
    uns, ua, mstar = lm
    h = np.arange(hours)
    tin = line["t_set"] + 0.5 * np.cumsum(rng.normal(0, 0.12, hours)) * 0 + 0.4 * np.sin(2 * np.pi * (h + rng.uniform(0, 24)) / 37.0) + rng.normal(0, 0.15, hours)
    ta = line["t_amb"] + 0.8 * np.sin(2 * np.pi * (h - 15) / 24.0) + 0.5 * np.sin(2 * np.pi * (h + rng.uniform(0, 90)) / 90.0) + rng.normal(0, 0.1, hours)
    # load levels held for 8 to 36 hours
    def zone(z):
        if z == "H": lo, hi = (1.22 * max(ua[1], uns[1]), 1.8 * max(ua[1], uns[1])) if uns else (1.5 * mstar, 6 * mstar)
        elif z == "B": lo, hi = 1.18 * uns[1], 0.84 * ua[1]
        else: lo, hi = max(1.25 * uns[0], 0.45 * uns[1]), 0.82 * uns[1]
        return rng.uniform(lo, hi)
    flow = np.zeros(hours); t = 0; z = "H"; seq = []
    excursions = line["pipes"] == 2 and season == "cold" and uns is not None and ua is not None
    has_B = excursions and 1.18 * uns[1] < 0.84 * ua[1] * 0.93
    while t < hours:
        d = int(rng.integers(8, 37)); lev = zone(z)
        flow[t:t + d] = lev * (1 + rng.normal(0, 0.004, len(flow[t:t + d]))); seq.append(z); t += d
        if excursions:
            z = {"H": rng.choice(["U", "U", "B"] if has_B else ["U"]), "U": rng.choice(["B", "B", "H", "U"] if has_B else ["H", "U"]),
                 "B": rng.choice(["U", "H", "B"])}[z]
        else:
            z = "H"
    return np.round(flow * 3.6, 3), np.round(tin, 1), np.round(ta, 1), seq

def state_run(line, flow_th, tin, ta, n, fr=FR, scale=1.0, sub=0):
    """states of a pair through its records; with sub > 0, every step is walked in sub equal parts."""
    M = flow_th / 3.6 * scale
    if sub:
        w = np.linspace(0, 1, sub + 1)[1:]
        M = np.concatenate([[M[0]], (M[:-1, None] + (M[1:] - M[:-1])[:, None] * w).ravel()])
        tin = np.concatenate([[tin[0]], (tin[:-1, None] + (tin[1:] - tin[:-1])[:, None] * w).ravel()])
        ta = np.concatenate([[ta[0]], (ta[:-1, None] + (ta[1:] - ta[:-1])[:, None] * w).ravel()])
    par = par_of(line, M, tin, ta)
    sym, asym = splits(M, par, n=n, fr=fr, iters=44 if n >= 240 else 20)
    kind, dp, T, a, flags = follow(range(len(M)), sym, asym)
    if sub: kind = kind[::sub]
    return kind, dp, T, a, flags, M

def build(name):
    seed, role, season, npair, nsingle, oils = SITES[name]
    rng = np.random.default_rng(seed)
    lines, records, truth = [], [], {}
    tags = ["FL-%d%02d" % (1 + i // 4, 10 + 3 * i) for i in range(npair + nsingle)]
    order = list(rng.permutation(npair + nsingle)); n_calm = 0
    for i in range(npair + nsingle):
        pipes = 2 if order[i] < npair else 1
        for attempt in range(60):
            cold_pair = pipes == 2 and season == "cold"
            line = dict(line=tags[i], pipes=pipes, oil=str(rng.choice(oils)),
                        bore_mm=int(rng.choice([40, 50, 65, 80, 100, 125])), length_m=int(rng.integers(18, 95) * 10),
                        u_o=float(np.round(rng.uniform(5.0, 12.0) if cold_pair else rng.uniform(2.0, 9.0), 1)),
                        t_set=float(rng.integers(65, 96)), t_amb=float(np.round(rng.uniform(5.0, 13.0) if season == "cold" else rng.uniform(19.0, 30.0), 1)))
            hours = int(rng.integers(200, 301))
            lm = landmarks(line, line["t_set"], line["t_amb"]) if pipes == 2 else (None, None, line["u_o"] * np.pi * line["bore_mm"] / 1e3 * line["length_m"] / OILS[line["oil"]][1])
            if cold_pair and (lm[0] is None or lm[1] is None or lm[0][1] / lm[0][0] < 1.8): continue
            flow, tin, ta, seq = history(rng, line, season, hours, lm)
            if pipes == 1:
                if reynolds(line, flow / 3.6, tin).max() > 2000: continue
                dp, T = single(flow / 3.6, par_of(line, flow, tin, ta), N_TRUTH); kind = np.zeros(hours, int); break
            if reynolds(line, flow / 3.6, tin).max() > 2000: continue
            # the states must not hang on the model's last per cent: the same kinds with the flow 4 per cent
            # down and up, and with every step walked in 6 parts
            k0, _, _, _, f0, _ = state_run(line, flow, tin, ta, N_CHECK, FR_CHECK)
            if f0: continue
            if season != "cold" and k0.any(): continue
            bad = False
            for sc in (0.96, 1.04):
                k1, _, _, _, f1, _ = state_run(line, flow, tin, ta, N_CHECK, FR_CHECK, scale=sc)
                bad |= bool(f1) or not np.array_equal(k0, k1)
            if bad: continue
            k2, _, _, _, f2, _ = state_run(line, flow, tin, ta, N_CHECK, FR_CHECK, sub=6)
            if f2 or not np.array_equal(k0, k2): continue
            if season != "cold":
                # warm sites: nothing but the even division is steady and stable at any record
                M = flow / 3.6
                sym, asym = splits(M, par_of(line, M, tin, ta), n=N_CHECK, fr=FR_CHECK, iters=18)
                if asym[4].any() or not sym[2].all(): continue
            kind, dp, T, a, fl, _ = state_run(line, flow, tin, ta, N_TRUTH)
            if fl or not np.array_equal(kind, k0): continue
            break
        else:
            raise RuntimeError("no history for " + tags[i])
        lines.append(line)
        for h in range(hours):
            rid = "%s/%03d" % (line["line"], h)
            records.append(dict(record=rid, line=line["line"], hour=h, flow_t_h=flow[h], t_in_C=tin[h], t_amb_C=ta[h]))
            truth[rid] = (dp[h] / 1e3, T[h], int(kind[h]))
        print("  %s %s pipes %d %s bore %d L %d Uo %.1f  hours %d  uneven %d  (%s)" % (name, line["line"], pipes, line["oil"], line["bore_mm"],
              line["length_m"], line["u_o"], hours, int(kind.sum()), "".join(seq) if pipes == 2 else "-"), flush=True)
    base = {"example": "core/environment/data/examples", "pending": "core/environment/data/pending", "hidden": "core/hidden"}[role]
    out = os.path.join(HERE, base, name); os.makedirs(out, exist_ok=True)
    json.dump(dict(site=name, lines=len(lines), records=len(records)), open(os.path.join(out, "site.json"), "w"), indent=1)
    with open(os.path.join(out, "oils.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["oil", "density_kg_m3", "cp_J_kgK", "k_W_mK", "nu50_cSt", "nu100_cSt"])
        for o in oils: w.writerow([o] + ["%g" % x for x in OILS[o]])
    with open(os.path.join(out, "lines.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["line", "pipes", "bore_mm", "length_m", "u_o_W_m2K", "oil"])
        for l in lines: w.writerow([l["line"], l["pipes"], l["bore_mm"], l["length_m"], "%g" % l["u_o"], l["oil"]])
    with open(os.path.join(out, "records.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["record", "line", "hour", "flow_t_h", "t_in_C", "t_amb_C"])
        for r in records: w.writerow([r["record"], r["line"], r["hour"], "%.3f" % r["flow_t_h"], "%.1f" % r["t_in_C"], "%.1f" % r["t_amb_C"]])
    if role == "example":
        with open(os.path.join(out, "expected.csv"), "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n"); w.writerow(["record", "dp_kPa", "t_out_C"])
            for r in records: w.writerow([r["record"], "%.5g" % truth[r["record"]][0], "%.2f" % truth[r["record"]][1]])
    else:
        d = out if role == "hidden" else os.path.join(HERE, "core/pending_truth"); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "truth.csv" if role == "hidden" else name + ".csv"), "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n"); w.writerow(["record", "dp_kPa", "t_out_C", "uneven"])
            for r in records: w.writerow([r["record"], repr(float(truth[r["record"]][0])), repr(float(truth[r["record"]][1])), truth[r["record"]][2]])
    n_un = sum(v[2] for v in truth.values())
    print("%-12s %-8s %-5s lines %2d records %4d  uneven %4d" % (name, role, season, len(lines), len(records), n_un), flush=True)

if __name__ == "__main__":
    import warnings; warnings.simplefilter("ignore")
    for n in (sys.argv[1:] or list(SITES)):
        build(n)
