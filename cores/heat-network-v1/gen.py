"""gen.py: districts for the heat-network core. python3 gen.py [district ...]"""
import csv, json, math, os, sys, copy
import numpy as np
import truth as T

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "core", "environment", "data")
HIDDEN = os.path.join(HERE, "hidden")
RHO, CP = 975.0, 4.19
DNS = [0.065, 0.08, 0.1, 0.125, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6]

# ring: ring nodes; chords: extra links across it; tree: (depth, max branches); hours of record;
# cold: outdoor mean deg C; squeeze: plant pressure difference against what the far substations need
SITES = {
    # fouled: substations returning hotter than their register; throttle: a pipe far above its registered resistance
    "harbour_east": dict(role="example", seed=11, ring=8, chords=1, tree=(3, 3), hours=48, cold=-2.0, squeeze=0.08, share=1.0, fouled=0, throttle=False),
    "mill_quarter": dict(role="example", seed=12, ring=10, chords=1, tree=(3, 2), hours=48, cold=1.0, squeeze=0.08, share=1.0, fouled=0, throttle=False),
    "station_park": dict(role="pending", seed=13, ring=14, chords=2, tree=(4, 3), hours=72, cold=-4.0, squeeze=0.1, share=0.35, fouled=1, throttle=True),
    "north_bank": dict(role="hidden", seed=21, ring=22, chords=3, tree=(5, 3), hours=96, cold=-8.0, squeeze=0.15, share=0.25, fouled=1, throttle=False),
    "west_hill": dict(role="hidden", seed=22, ring=24, chords=4, tree=(5, 3), hours=96, cold=-11.0, squeeze=0.18, share=0.25, fouled=0, throttle=True),
    "old_town": dict(role="hidden", seed=23, ring=20, chords=3, tree=(5, 3), hours=96, cold=-6.0, squeeze=0.12, share=0.25, fouled=2, throttle=True),
    "river_side": dict(role="hidden", seed=24, ring=26, chords=4, tree=(5, 3), hours=96, cold=-14.0, squeeze=0.2, share=0.25, fouled=2, throttle=False),
    "east_gate": dict(role="hidden", seed=25, ring=18, chords=2, tree=(5, 3), hours=96, cold=-3.0, squeeze=0.1, share=0.25, fouled=0, throttle=False),
    "south_docks": dict(role="hidden", seed=26, ring=24, chords=3, tree=(5, 3), hours=96, cold=-9.0, squeeze=0.16, share=0.25, fouled=0, throttle=True),
}


def dn_for(m, vel):
    d = math.sqrt(4 * m / (RHO * math.pi * vel))
    return next((x for x in DNS if x >= d), DNS[-1])


def build(name, spec):
    rng = np.random.default_rng(spec["seed"])
    nodes = []; pipes = []; subs = []
    nr = spec["ring"]
    ring = ["R%02d" % i for i in range(nr)]
    nodes += ring
    plant = ring[0]
    sector = {}
    for i, r in enumerate(ring):
        sector[r] = "residential" if i < nr // 2 else ("commercial" if i < 3 * nr // 4 else "mixed")
    links = [(ring[i], ring[(i + 1) % nr], "ring") for i in range(nr)]
    for c in range(spec["chords"]):
        while True:
            a, b = sorted(rng.choice(nr, 2, replace=False))
            if 1 < b - a < nr - 1 and a != 0: break
        links.append((ring[a], ring[b], "chord"))
    children = {}
    def grow(parent, depth, label, sec):
        if depth == 0: return
        for k in range(int(rng.integers(1, spec["tree"][1] + 1))):
            nm = "%s%d" % (label, k + 1)
            nodes.append(nm); sector[nm] = sec
            links.append((parent, nm, "tree")); children.setdefault(parent, []).append(nm)
            if rng.random() < 0.8: grow(nm, depth - 1, nm, sec)
    for r in ring[1:]:
        grow(r, spec["tree"][0], "T" + r[1:] + "_", sector[r])
    # substations: every leaf, most tree nodes, some ring nodes
    is_leaf = {n: n not in children for n in nodes}
    sid = 0
    for n in nodes:
        if n == plant: continue
        p_ = 1.0 if (is_leaf[n] and n not in ring) else (0.6 if n not in ring else 0.3)
        if rng.random() < p_:
            sid += 1
            qd = float(rng.uniform(80, 600))
            subs.append(dict(substation="S%03d" % sid, node=n, design_kW=qd, return_C=round(float(rng.uniform(40, 55)), 1),
                             kind=sector[n]))
    # design flows: tree pipes carry their subtree, ring and chords a share of the whole
    md = {s["node"]: 0.0 for s in subs}
    for s in subs: md[s["node"]] = md.get(s["node"], 0) + s["design_kW"] / (CP * 45.0)
    def subtree(n):
        return md.get(n, 0.0) + sum(subtree(c) for c in children.get(n, []))
    total = sum(md.values())
    for a, b, kind in links:
        m = subtree(b) if kind == "tree" else (0.45 * total if kind == "ring" else 0.2 * total)
        vel = float(rng.uniform(0.55, 0.85))
        D = dn_for(max(m, 0.3), vel)
        L = float(rng.uniform(220, 520)) if kind == "tree" else float(rng.uniform(320, 700))
        A = math.pi * D * D / 4
        f = float(rng.uniform(0.018, 0.026))
        R = f * L / D / (2 * RHO * A * A)
        U = 0.12 + 0.35 * D                    # W/(m K)
        tau = RHO * CP * 1000 * A / U / 3600.0
        pipes.append(dict(pipe="P%03d" % (len(pipes) + 1), from_node=a, to_node=b, length_m=round(L, 1),
                          volume_m3=round(A * L, 4), resistance_Pa_s2_kg2=float("%.6g" % R), loss_time_h=round(tau, 2), kind=kind))
    for s in subs:
        m_d = s["design_kW"] / (CP * 45.0)
        s["valve_capacity"] = float("%.6g" % (1.25 * m_d / math.sqrt(60000.0)))
    return dict(name=name, nodes=nodes, plant=plant, pipes=pipes, subs=subs)


PROFILE = {
    "residential": [0.6, 0.55, 0.55, 0.55, 0.6, 0.85, 1.35, 1.5, 1.25, 0.8, 0.6, 0.55, 0.55, 0.55, 0.55, 0.6, 0.8, 1.2, 1.45, 1.45, 1.25, 1.0, 0.8, 0.65],
    "commercial": [0.15, 0.15, 0.15, 0.15, 0.15, 0.2, 0.45, 1.1, 1.65, 1.7, 1.7, 1.65, 1.6, 1.65, 1.65, 1.6, 1.45, 0.95, 0.45, 0.25, 0.2, 0.15, 0.15, 0.15],
    "mixed": [0.6, 0.6, 0.6, 0.6, 0.65, 0.75, 0.95, 1.1, 1.15, 1.1, 1.05, 1.0, 1.0, 1.0, 1.0, 1.0, 1.05, 1.1, 1.1, 1.05, 0.95, 0.85, 0.75, 0.65],
}


def weather(spec, rng, hours):
    t = np.arange(hours + 1)
    trend = np.cumsum(rng.normal(0, 0.35, hours + 1))
    return spec["cold"] + 4.0 * np.sin(2 * math.pi * (t - 9) / 24.0) + trend


def schedules(net, spec, rng):
    hours = spec["hours"]
    tout = weather(spec, rng, hours)
    dem = []
    for s in net["subs"]:
        noise = rng.normal(0, 0.04, hours + 1)
        for h in range(hours):
            load = max(0.05, (18.0 - tout[h]) / 33.0)
            q = s["design_kW"] * load * PROFILE[s["kind"]][h % 24] * (1 + noise[h])
            dem.append(dict(time_h=h, substation=s["substation"], heat_kW=round(max(q, 0.05 * s["design_kW"]), 2)))
    plant = []
    for h in range(hours):
        ts = min(110.0, max(72.0, 72.0 + 38.0 * (8.0 - tout[h]) / 23.0))
        plant.append(dict(time_h=h, supply_C=round(ts, 1)))
    return dem, plant, tout


def package(net, dem, plant, init, points, hours, dp):
    pk = dict(head=dict(district=net["name"], plant_node=net["plant"], ground_C=8.0, hours=hours),
              nodes=net["nodes"], pipes=[{k: p[k] for k in ("pipe", "from_node", "to_node", "length_m", "volume_m3", "resistance_Pa_s2_kg2", "loss_time_h")} for p in net["pipes"]],
              subs=[{k: str(s[k]) for k in ("substation", "node", "return_C", "valve_capacity")} for s in net["subs"]],
              demand=[{k: str(v) for k, v in r.items()} for r in dem],
              plant=[dict(time_h=str(r["time_h"]), supply_C=str(r["supply_C"]), dp_Pa=str(dp[i])) for i, r in enumerate(plant)],
              init=init, points=points)
    return pk


def write(pk, folder):
    os.makedirs(folder, exist_ok=True)
    json.dump(pk["head"], open(os.path.join(folder, "network.json"), "w"), indent=1)
    def w(name, rows_, cols):
        with open(os.path.join(folder, name), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader()
            for r in rows_: wr.writerow({c: r[c] for c in cols})
    w("nodes.csv", [dict(node=n) for n in pk["nodes"]], ["node"])
    w("pipes.csv", pk["pipes"], ["pipe", "from_node", "to_node", "length_m", "volume_m3", "resistance_Pa_s2_kg2", "loss_time_h"])
    w("substations.csv", pk["subs"], ["substation", "node", "return_C", "valve_capacity"])
    w("demand.csv", pk["demand"], ["time_h", "substation", "heat_kW"])
    w("plant.csv", pk["plant"], ["time_h", "supply_C", "dp_Pa"])
    w("initial.csv", pk["init"], ["kind", "name", "network", "temp_C"])
    w("points.csv", pk["points"], ["point", "time_h", "item", "quantity"])


class Weak(Exception):
    pass


def make(name):
    boost = 1.0
    for attempt in range(6):
        try:
            return make_once(name, boost)
        except Weak as w:
            print("%s: %s; the throttle made stronger" % (name, w), flush=True)
            boost *= 1.6
    raise SystemExit("%s: no throttle strong enough" % name)


def make_once(name, boost):
    spec = SITES[name]
    rng = np.random.default_rng(spec["seed"] + 500)
    net = build(name, spec)
    hours = spec["hours"]
    dem, plant, tout = schedules(net, spec, rng)
    crng = np.random.default_rng(spec["seed"] + 900)
    actual = conditions(net, spec, crng)
    if actual["resistance"]:
        (pn, rv), = actual["resistance"].items(); r0 = net["pipes"][conditions.pipe]["resistance_Pa_s2_kg2"]
        actual["resistance"][pn] = float("%.6g" % (r0 + boost * (rv - r0)))
    dp = calibrate_dp(net, dem, plant, hours, spec, actual)
    for attempt in range(8):
        miss = throttle_misses(net, actual, dp)
        if not actual["resistance"] or miss >= 400: break
        # too little: the same pipe, half as much again
        (pn, rv), = actual["resistance"].items(); r0 = net["pipes"][conditions.pipe]["resistance_Pa_s2_kg2"]
        actual["resistance"][pn] = float("%.6g" % (r0 + 1.5 * (rv - r0)))
        dp = calibrate_dp(net, dem, plant, hours, spec, actual)
    else:
        raise SystemExit("%s: the throttle does not put enough substations at their limit" % name)
    first = [r for r in dem if r["time_h"] < 24]
    init0 = [dict(kind="pipe", name=p["pipe"], network=w, temp_C=str(plant[0]["supply_C"] - 5 if w == "supply" else 45.0)) for p in net["pipes"] for w in ("supply", "return")] + \
            [dict(kind="node", name=n, network=w, temp_C=str(plant[0]["supply_C"] - 5 if w == "supply" else 45.0)) for n in net["nodes"] for w in ("supply", "return")]
    pk = package(net, first, plant[:24], init0, [], 24, dp[:24])
    facts = {}
    T.simulate(pk, facts, actual)
    fin = facts["final"]
    init = [dict(kind="pipe", name=p["pipe"], network="supply", temp_C="%.4f" % fin["sup"][j]) for j, p in enumerate(net["pipes"])] + \
           [dict(kind="pipe", name=p["pipe"], network="return", temp_C="%.4f" % fin["ret"][j]) for j, p in enumerate(net["pipes"])] + \
           [dict(kind="node", name=n, network="supply", temp_C="%.4f" % fin["Ts"][i]) for i, n in enumerate(net["nodes"])] + \
           [dict(kind="node", name=n, network="return", temp_C="%.4f" % fin["Trn"][i]) for i, n in enumerate(net["nodes"])]
    points = []
    for h in range(1, hours + 1):
        pick = [s for s in net["subs"] if rng.random() < spec["share"]]
        for s in pick:
            for q, tag in (("supply_C", "T"), ("return_C", "R"), ("heat_kW", "Q")):
                points.append(dict(point="H%03d-%s-%s" % (h, s["substation"], tag), time_h=str(h), item=s["substation"], quantity=q))
        points.append(dict(point="H%03d-PLANT-R" % h, time_h=str(h), item="plant", quantity="return_C"))
    pk = package(net, dem, plant, init, points, hours, dp)
    facts = {}
    import time; t0 = time.time()
    res = T.simulate(pk, facts, actual)
    secs = time.time() - t0
    sign = np.array(facts["sign"]); flips = int(((sign[1:] * sign[:-1]) < 0).any(axis=0).sum())
    sat_steps = int((np.array(facts["sat"]) > 0).sum())
    mrng = np.random.default_rng(spec["seed"] + 1300)
    meters = []
    for i, s in enumerate(net["subs"]):
        e = facts["meter_kWh"][i] * (1 + float(np.clip(mrng.normal(0, 0.0008), -0.0025, 0.0025)))
        vol = facts["meter_vol"][i] * (1 + float(np.clip(mrng.normal(0, 0.0008), -0.0025, 0.0025)))
        meters.append(dict(substation=s["substation"], energy_kWh="%.2f" % e, volume_m3="%.3f" % vol))
    surv = survey(net, actual, np.random.default_rng(spec["seed"] + 1700))
    folder = os.path.join(DATA, "examples" if spec["role"] == "example" else "pending", name) if spec["role"] != "hidden" else os.path.join(HIDDEN, name)
    write(pk, folder)
    with open(os.path.join(folder, "meters.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["substation", "energy_kWh", "volume_m3"]); wr.writeheader(); wr.writerows(meters)
    with open(os.path.join(folder, "pressure_survey.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["item", "flow_kg_s", "dp_Pa"]); wr.writeheader(); wr.writerows(surv)
    rows_ = [dict(point=r["point"], value="%.6f" % res[r["point"]]) for r in points]
    out = os.path.join(folder, "expected.csv") if spec["role"] == "example" else os.path.join(HIDDEN, "_result_%s.csv" % name)
    os.makedirs(HIDDEN, exist_ok=True)
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["point", "value"]); wr.writeheader(); wr.writerows(rows_)
    json.dump(actual, open(os.path.join(HIDDEN, "_actual_%s.json" % name), "w"), indent=1)
    # what the records alone give
    plain = T.simulate(pk)
    bad = sum(1 for r in points if abs(plain[r["point"]] - res[r["point"]]) > band(r["point"], res[r["point"]]))
    alone = {}
    for cond in ("return_C", "resistance"):
        if not actual[cond]: continue
        part = T.simulate(pk, None, {k: v for k, v in actual.items() if k != cond})      # every other condition right
        alone[cond] = sum(1 for r in points if abs(part[r["point"]] - res[r["point"]]) > band(r["point"], res[r["point"]]))
        if alone[cond] < 20:
            if cond == "resistance": raise Weak("the throttle alone puts only %d points out" % alone[cond])
            raise SystemExit("%s: %s alone puts only %d points out" % (name, cond, alone[cond]))
    print(name, "pipes", len(net["pipes"]), "subs", len(net["subs"]), "reversing", flips, "valve-limited steps", sat_steps,
          "max courant %.2f" % max(facts["courant"]), "margin %.1f K" % facts["margin"], "conditions", json.dumps(actual),
          "records alone: %d of %d points out" % (bad, len(points)), "each alone", json.dumps(alone), "throttle misses %d" % miss, "truth %.0f s" % secs, flush=True)


def band(point, value):
    return 0.5 if point.endswith(("-T", "-R")) else max(0.02 * abs(value), 1.0)


def calibrate_dp(net, dem, plant, hours, spec, actual):
    """The plant's pressure difference for each day: the share `squeeze` of substations would be short at the day's
    heaviest hour. Found from a run with valves that never limit, of the network as it is."""
    big = copy.deepcopy(net)
    for s_ in big["subs"]: s_["valve_capacity"] = 1e6
    init = [dict(kind="pipe", name=p["pipe"], network=w, temp_C=str(plant[0]["supply_C"] - 5 if w == "supply" else 45.0)) for p in net["pipes"] for w in ("supply", "return")] + \
           [dict(kind="node", name=n, network=w, temp_C=str(plant[0]["supply_C"] - 5 if w == "supply" else 45.0)) for n in net["nodes"] for w in ("supply", "return")]
    pk = package(big, dem, plant, init, [], hours, [1e6] * hours)
    f = {}
    T.simulate(pk, f, actual)
    h = np.array(f["h"]); mw = np.array(f["mw"])
    K = np.array([s_["valve_capacity"] for s_ in net["subs"]])
    sidx = [net["nodes"].index(s_["node"]) for s_ in net["subs"]]
    need = 2 * h[:, sidx] + (mw / K) ** 2
    dp = []
    for day in range((hours + 23) // 24):
        rows_ = need[day * 720:(day + 1) * 720]
        peak = rows_.max(axis=1).argmax()
        dp += [round(float(np.quantile(rows_[peak], 1.0 - spec["squeeze"])), 0)] * 24
    calibrate_dp.last = dict(need=need, m=np.array(f["m"]))
    return dp[:hours]


def conditions(net, spec, rng):
    """Which substations return hotter than their register says, and which pipe is far above its resistance."""
    actual = {"return_C": {}, "resistance": {}}
    count = {}
    for s_ in net["subs"]: count[s_["node"]] = count.get(s_["node"], 0) + 1
    kids = {}
    for p in net["pipes"]:
        if p["kind"] == "tree": kids.setdefault(p["from_node"], []).append(p["to_node"])
    leaf = lambda n: n not in kids
    pool = [s_ for s_ in net["subs"] if count[s_["node"]] == 1 and leaf(s_["node"]) and s_["return_C"] <= 46.5 and s_["design_kW"] >= 150]
    for s_ in rng.choice(pool, spec["fouled"], replace=False) if spec["fouled"] else []:
        actual["return_C"][s_["substation"]] = round(s_["return_C"] + float(rng.uniform(9.0, 14.0)), 1)
    if spec["throttle"]:
        md = {}
        for s_ in net["subs"]: md[s_["node"]] = md.get(s_["node"], 0) + s_["design_kW"] / (CP * 45.0)
        nsub = {}
        def walk(n):
            a = (1 if n in md else 0) + sum(walk(c) for c in kids.get(n, []))
            nsub[n] = a; return a
        for r in [p["from_node"] for p in net["pipes"] if p["kind"] != "tree"]: walk(r)
        flow = {}
        def mflow(n): return md.get(n, 0.0) + sum(mflow(c) for c in kids.get(n, []))
        cand = [p for p in net["pipes"] if p["kind"] == "tree" and 6 <= nsub.get(p["to_node"], 0) <= 40]
        p = cand[int(rng.integers(len(cand)))]
        m = mflow(p["to_node"])
        extra = float(rng.uniform(40000.0, 70000.0))           # Pa more drop at design flow, each way
        actual["resistance"][p["pipe"]] = float("%.6g" % (p["resistance_Pa_s2_kg2"] + extra / m ** 2))
        below = set()
        def down(n):
            below.add(n)
            for c in kids.get(n, []): down(c)
        down(p["to_node"])
        conditions.below = [i for i, s_ in enumerate(net["subs"]) if s_["node"] in below]
        conditions.pipe = [q["pipe"] for q in net["pipes"]].index(p["pipe"])
    return actual


def throttle_misses(net, actual, dp):
    """Substation-steps at which the throttled pipe puts a substation at its valve limit where the registered
    resistance would not (valves taken as unlimited, so the flows are the same both ways)."""
    if not actual["resistance"]: return 0
    j = conditions.pipe; p = net["pipes"][j]
    dR = actual["resistance"][p["pipe"]] - p["resistance_Pa_s2_kg2"]
    need = calibrate_dp.last["need"]; m = calibrate_dp.last["m"][:, j]
    d = np.repeat(np.array(dp), 30)[:need.shape[0]]
    sub = need[:, conditions.below]
    return int(((sub > d[:, None]) & (sub - 2 * dR * (m ** 2)[:, None] <= d[:, None])).sum())


def survey(net, actual, rng):
    """A pressure survey on a cold morning before the record: every substation's metered flow, and the pressure
    difference logged at its node, with the network as it is."""
    nodes = net["nodes"]; ix = {n: i for i, n in enumerate(nodes)}; N = len(nodes); plant = ix[net["plant"]]
    u = np.array([ix[p["from_node"]] for p in net["pipes"]]); v = np.array([ix[p["to_node"]] for p in net["pipes"]])
    R = np.array([actual["resistance"].get(p["pipe"], p["resistance_Pa_s2_kg2"]) for p in net["pipes"]])
    sn = np.array([ix[s_["node"]] for s_ in net["subs"]])
    m_s = np.array([s_["design_kW"] / (CP * 45.0) * float(rng.uniform(0.6, 0.85)) for s_ in net["subs"]])
    h = solve_fixed(N, plant, u, v, R, sn, m_s)
    dpp = float(round(2 * h[sn].max() + float(rng.uniform(70000, 110000)), -2))
    rows_ = [dict(item="plant", flow_kg_s="%.3f" % m_s.sum(), dp_Pa="%.0f" % dpp)]
    for s_, m, n in zip(net["subs"], m_s, sn):
        rows_.append(dict(item=s_["substation"], flow_kg_s="%.4f" % (m * (1 + float(np.clip(rng.normal(0, 0.0004), -0.001, 0.001)))),
                          dp_Pa="%.0f" % (dpp - 2 * h[n] + float(np.clip(rng.normal(0, 70.0), -200, 200)))))
    return rows_


def solve_fixed(N, plant, u, v, R, sn, m_s, DELTA=1e-6):
    import scipy.sparse as sp
    from scipy.sparse.linalg import spsolve
    free = np.array([i for i in range(N) if i != plant]); pos = -np.ones(N, int); pos[free] = np.arange(N - 1)
    h = np.zeros(N)
    for it in range(300):
        dh = h[v] - h[u]; a = np.abs(dh); m = dh / np.sqrt(R * (a + DELTA))
        g = (a + 2 * DELTA) / (2 * np.sqrt(R) * (a + DELTA) ** 1.5)
        res = np.bincount(v, m, N) - np.bincount(u, m, N) - np.bincount(sn, m_s, N)
        if np.abs(res[free]).max() < 1e-11 * m_s.sum(): return h
        Jr = np.concatenate([v, v, u, u]); Jc = np.concatenate([v, u, u, v]); Jv = np.concatenate([g, -g, g, -g])
        k = (pos[Jr] >= 0) & (pos[Jc] >= 0)
        J = sp.csc_matrix((Jv[k], (pos[Jr[k]], pos[Jc[k]])), shape=(N - 1, N - 1))
        step = spsolve(J, -res[free]); lam = 1.0
        while True:
            hn = h.copy(); hn[free] += lam * step
            dh2 = hn[v] - hn[u]; m2 = dh2 / np.sqrt(R * (np.abs(dh2) + DELTA))
            r2 = np.bincount(v, m2, N) - np.bincount(u, m2, N) - np.bincount(sn, m_s, N)
            if np.abs(r2[free]).sum() < np.abs(res[free]).sum() or lam < 1e-6: break
            lam *= 0.5
        h = hn
    raise SystemExit("survey hydraulics did not converge")


def design_dp(net):
    """Twice the largest supply drop to a substation at design flows, through the tree only, plus 60 kPa."""
    par = {}
    for p in net["pipes"]:
        if p["kind"] == "tree": par[p["to_node"]] = p
    md = {}
    for s in net["subs"]: md[s["node"]] = md.get(s["node"], 0) + s["design_kW"] / (CP * 45.0)
    kids = {}
    for p in net["pipes"]:
        if p["kind"] == "tree": kids.setdefault(p["from_node"], []).append(p["to_node"])
    def sub(n): return md.get(n, 0.0) + sum(sub(c) for c in kids.get(n, []))
    best = 0.0
    for s in net["subs"]:
        n = s["node"]; drop = 0.0
        while n in par:
            p = par[n]; drop += p["resistance_Pa_s2_kg2"] * sub(n) ** 2; n = p["from_node"]
        best = max(best, drop)
    total = sum(md.values())
    ring_drop = max(p["resistance_Pa_s2_kg2"] for p in net["pipes"] if p["kind"] == "ring") * (0.45 * total) ** 2 * len(net["nodes"]) ** 0 * 3
    return 2 * (best + ring_drop) + 60000.0


if __name__ == "__main__":
    for nm in (sys.argv[1:] or list(SITES)): make(nm)
