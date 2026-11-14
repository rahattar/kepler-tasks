"""gen.py: the depots. Writes core/environment/data/{docs,examples,pending}, core/environment/rig (the test
crew, answering for the examples), hidden/<site>/ with truth.csv, hidden_lab/{sealed,truth}."""
import csv, json, math, os, random, shutil, sys
import numpy as np
from cs4 import sat, t_of_p, vent_per_J, ua_from_ner, hold, ATM, T_NBP

HERE = os.path.dirname(os.path.abspath(__file__))
CAPS = [11.0, 20.0, 30.0, 33.0, 50.0, 60.0]
RELIEF = [8.0, 10.0, 12.0, 14.0]
JOBS_OTHER = ["relief valve replaced", "outlet valve repacked", "gauge transmitter replaced", "pressure builder coil tested",
              "road fill line hose renewed", "level gauge serviced"]
JOBS_INSUL = ["annular space re-evacuated", "vacuum pumped out and perlite topped up"]

# name, kind, seed, tanks, legible, degraded, gauge
SITES = [
    ("north_moor",  "example", 11, 6, 1, False, False),
    ("east_basin",  "example", 12, 7, 2, False, False),
    ("west_quarry", "pending", 13, 7, 1, True,  "low"),
    ("south_fen",   "hidden",  21, 6, 1, True,  "high"),
    ("mill_lane",   "hidden",  22, 8, 2, True,  "low"),
    ("river_cut",   "hidden",  23, 5, 1, True,  False),
    ("high_wold",   "hidden",  24, 7, 1, True,  False),
    ("kiln_end",    "hidden",  25, 6, 2, False, "low"),
    ("salt_marsh",  "hidden",  26, 6, 1, False, False),
]

def dates(start, n):
    import datetime as dt
    d0 = dt.date.fromisoformat(start); return [(d0 + dt.timedelta(days=i)).isoformat() for i in range(n)]

def build(name, kind, seed, ntank, nleg, degraded, gauge):
    R = random.Random(seed); G = np.random.default_rng(seed)
    year = 2025
    f_site = R.uniform(1.00, 1.09)
    tanks = []
    for i in range(ntank):
        cap = R.choice(CAPS); ner = round(R.uniform(0.18, 0.42) * (30.0 / cap) ** 0.25, 3)
        tanks.append(dict(tank="T%d" % (i + 1), capacity_m3=cap, relief_barg=R.choice(RELIEF), ner_pct_day=ner,
                          ner_t_amb_C=round(R.uniform(12, 21), 1), ner_date="%d-%02d-%02d" % (R.randint(2009, 2021), R.randint(1, 12), R.randint(1, 28))))
    for t in tanks:
        t["ua_reg"] = ua_from_ner(t["ner_pct_day"], t["capacity_m3"], t["ner_t_amb_C"])
        t["ua"] = f_site * t["ua_reg"]; t["k"] = 1.0; t["kind"] = "sound"
    idx = list(range(ntank)); R.shuffle(idx)
    togglers = idx[:3]                      # tanks taken out of service for a while in the campaigns
    deg = togglers[0] if degraded else None
    gtarget = None
    if deg is not None:
        g = R.uniform(1.6, 2.4); tanks[deg]["ua"] *= g; tanks[deg]["kind"] = "vacuum lost x%.2f" % g
    rest = [i for i in idx if i != deg]; R.shuffle(rest)
    legible = rest[:nleg]
    gi = None
    if gauge:
        cand = [i for i in rest[nleg:]]; gi = R.choice(cand)
        tanks[gi]["k"] = R.uniform(0.87, 0.91) if gauge == "low" else R.uniform(1.09, 1.13)
        tanks[gi]["kind"] = "gauge reads x%.3f" % tanks[gi]["k"]
    # campaigns
    camps = [("%d-01-%02d" % (year, R.randint(5, 15)), R.randint(32, 42), 3.0),
             ("%d-04-%02d" % (year, R.randint(5, 15)), R.randint(32, 42), 11.0),
             ("%d-07-%02d" % (year, R.randint(5, 15)), R.randint(32, 42), 19.0)]
    daily = []; depot = []; work = []
    # isolation periods: each toggler once, in a random campaign
    iso = {}
    for j, ti in enumerate(togglers):
        c = R.randrange(3); n = camps[c][1]; L = R.randint(9, 13) if ti == deg else R.randint(6, 11); a = R.randint(4, n - L - 3)
        iso[ti] = (c, a, a + L)
    for t in tanks:
        rho = sat(t_of_p(2.6 + ATM))[1]; t["mmax"] = t["capacity_m3"] * rho * 0.9
        t["draw"] = R.uniform(0.025, 0.06) * t["mmax"]; t["m"] = R.uniform(0.4, 0.85) * t["mmax"]
    for c, (start, n, tmean) in enumerate(camps):
        ds = dates(start, n); ph_base = R.uniform(2.2, 2.9)
        for d in range(n):
            tamb = tmean + 3.5 * math.sin(d / 5.3 + c) + G.normal(0, 1.5)
            ph = ph_base + G.normal(0, 0.08)
            tsat = t_of_p(ph + ATM); meter = 0.0
            for i, t in enumerate(tanks):
                ins = 1
                if i in iso and iso[i][0] == c and iso[i][1] <= d < iso[i][2]: ins = 0
                filled = 0.0
                if ins == 0:
                    if d == iso[i][1]:
                        work.append((ds[d], t["tank"], R.choice(JOBS_OTHER)))
                    t["m"] = 0.0; gauge_r = 0.0
                else:
                    gauge_r = t["k"] * t["m"] + G.normal(0, 0.002 * t["mmax"])
                    boil = t["ua"] * (tamb + 273.15 - tsat) * 86400 * vent_per_J(tsat)
                    meter += boil
                    w = 0.0 if t["m"] == 0 else t["draw"] * max(0.3, 1 + G.normal(0, 0.15))
                    if t["m"] - w < 0.33 * t["mmax"] or t["m"] == 0:
                        filled = round((R.uniform(0.84, 0.9) * t["mmax"] - max(t["m"] - w, 0)) / 10) * 10
                    t["m"] = max(t["m"] - w - boil, 0) + filled
                daily.append((ds[d], t["tank"], ins, "%.0f" % max(gauge_r, 0) if ins else "", "%.0f" % filled if filled else "0"))
            depot.append((ds[d], "%.1f" % tamb, "%.3f" % ph, "%.1f" % (meter * (1 + G.normal(0, 0.010)))))
    # a few other jobs on file, and insulation work after the last campaign
    for i, t in enumerate(tanks):
        if R.random() < 0.5:
            work.append(("%d-%02d-%02d" % (year - 1, R.randint(1, 12), R.randint(1, 28)), t["tank"], R.choice(JOBS_OTHER)))
    if gi is not None:
        work.append(("%d-%02d-%02d" % (year - 1, R.randint(1, 12), R.randint(1, 28)), tanks[gi]["tank"], "gauge transmitter replaced"))
    last = depot[-1][0]
    for i in legible:
        t = tanks[i]; t["ua"] = t["ua_reg"] * R.uniform(0.88, 1.22); t["kind"] = "insulation work"
        work.append(("%d-%02d-%02d" % (year, 9, R.randint(1, 25)), t["tank"], R.choice(JOBS_INSUL)))
    work.sort()
    # holding plan
    hd = R.randint(24, 36); hstart = "%d-11-%02d" % (year, R.randint(3, 20)); p_close = round(R.uniform(2.3, 2.8), 2)
    hamb = [round(6.5 + 3 * math.sin(d / 4.1) + G.normal(0, 1.2), 1) for d in range(hd)]
    plan = []
    for i, t in enumerate(tanks):
        rho = sat(t_of_p(p_close + ATM))[1]
        frac = R.uniform(0.70, 0.86) if t["k"] == 1 else R.uniform(0.70, 0.76)
        cg = round(frac * t["capacity_m3"] * rho / 10) * 10
        plan.append((t["tank"], cg))
    truth = []
    for (tk, cg), t in zip(plan, tanks):
        for d, p, v, st in hold(t["capacity_m3"], cg / t["k"], p_close, t["relief_barg"], t["ua"], hamb, hd):
            truth.append((tk + "/%d" % d, tk, d, p, v, st))
    allowance = len(legible) + (1 if degraded else 0)
    # crew book: NER test of every tank as it stands now
    book = {"allowance": allowance, "readings": {}}
    for t in tanks:
        tt = round(R.uniform(10, 18), 1)
        ner = t["ua"] * (tt + 273.15 - T_NBP) / vent_per_J(T_NBP) * 0 + t["ua"] * (tt + 273.15 - T_NBP) * vent_per_J(T_NBP) * 86400 / (t["capacity_m3"] * sat(T_NBP)[1]) * 100
        book["readings"][t["tank"]] = ["%.4f" % (ner * (1 + G.normal(0, 0.002))), "%.1f" % tt]
    return dict(name=name, kind=kind, tanks=tanks, daily=daily, depot=depot, work=work, plan=plan, hamb=hamb, hd=hd,
                hstart=hstart, p_close=p_close, truth=truth, book=book, allowance=allowance, f=f_site,
                legible=[tanks[i]["tank"] for i in legible], deg=tanks[deg]["tank"] if deg is not None else None,
                gauge=tanks[gi]["tank"] if gi is not None else None, togglers=[tanks[i]["tank"] for i in togglers])

def wcsv(path, head, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows)

def write(s, d):
    os.makedirs(d, exist_ok=True)
    json.dump({"site": s["name"], "tanks": len(s["tanks"]), "test_allowance": s["allowance"], "holding_start": s["hstart"],
               "holding_days": s["hd"], "close_barg": s["p_close"]}, open(os.path.join(d, "site.json"), "w"), indent=1)
    wcsv(os.path.join(d, "tanks.csv"), ["tank", "capacity_m3", "relief_barg", "ner_pct_day", "ner_t_amb_C", "ner_date"],
         [(t["tank"], t["capacity_m3"], t["relief_barg"], t["ner_pct_day"], t["ner_t_amb_C"], t["ner_date"]) for t in s["tanks"]])
    wcsv(os.path.join(d, "depot_log.csv"), ["date", "t_amb_C", "header_barg", "meter_kg"], s["depot"])
    wcsv(os.path.join(d, "tank_log.csv"), ["date", "tank", "in_service", "gauge_kg", "filled_kg"], s["daily"])
    wcsv(os.path.join(d, "work_log.csv"), ["date", "tank", "job"], s["work"])
    wcsv(os.path.join(d, "plan.csv"), ["tank", "close_gauge_kg"], s["plan"])
    wcsv(os.path.join(d, "holding.csv"), ["day", "t_amb_C"], [(i + 1, a) for i, a in enumerate(s["hamb"])])

def res_rows(s):
    return [(r, tk, d, "%.3f" % p, "%.1f" % v, st) for r, tk, d, p, v, st in s["truth"]]

if __name__ == "__main__":
    core = os.path.join(HERE, "core", "environment"); 
    for p in ("core", "hidden", "hidden_lab"): shutil.rmtree(os.path.join(HERE, p), ignore_errors=True)
    os.makedirs(os.path.join(core, "data", "docs")); os.makedirs(os.path.join(core, "rig", "sealed"))
    shutil.copy(os.path.join(HERE, "lab.py"), os.path.join(core, "rig", "lab.py"))
    for f in os.listdir(os.path.join(HERE, "docs_src")): shutil.copy(os.path.join(HERE, "docs_src", f), os.path.join(core, "data", "docs", f))
    os.makedirs(os.path.join(HERE, "hidden_lab", "sealed")); os.makedirs(os.path.join(HERE, "hidden_lab", "truth"))
    info = {}
    for row in SITES:
        s = build(*row); n = s["name"]
        info[n] = dict(kind=s["kind"], f=round(s["f"], 4), legible=s["legible"], degraded=s["deg"], gauge=s["gauge"], togglers=s["togglers"],
                       tanks={t["tank"]: t["kind"] for t in s["tanks"]}, allowance=s["allowance"],
                       states=sorted(set(r[5] for r in s["truth"])))
        head = ["record", "tank", "day", "p_barg", "vented_kg", "state"]
        if s["kind"] == "example":
            d = os.path.join(core, "data", "examples", n); write(s, d)
            wcsv(os.path.join(d, "expected.csv"), head, res_rows(s))
            json.dump(s["book"], open(os.path.join(core, "rig", "sealed", n + ".json"), "w"))
        elif s["kind"] == "pending":
            write(s, os.path.join(core, "data", "pending", n))
        else:
            d = os.path.join(HERE, "hidden", n); write(s, d); wcsv(os.path.join(d, "truth.csv"), head, res_rows(s))
        if s["kind"] != "example" or True:
            json.dump(s["book"], open(os.path.join(HERE, "hidden_lab", "sealed", n + ".json"), "w"))
            wcsv(os.path.join(HERE, "hidden_lab", "truth", n + ".csv"), head, res_rows(s))
    json.dump(info, open(os.path.join(HERE, "hidden_lab", "what_is_true.json"), "w"), indent=1)
    for n, v in info.items(): print(n, v["kind"], "f=%.3f" % v["f"], "leg", v["legible"], "deg", v["degraded"], "gauge", v["gauge"], "tog", v["togglers"], v["states"])
