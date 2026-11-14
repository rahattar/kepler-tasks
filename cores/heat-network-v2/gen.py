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
    # moved: substations connected at another node than the register has; bypass: substation bypasses leaking open
    "harbour_east": dict(role="example", seed=11, ring=8, chords=1, tree=(3, 3), hours=48, cold=-2.0, squeeze=0.08, share=1.0, moved=0, bypass=0),
    "mill_quarter": dict(role="example", seed=12, ring=10, chords=1, tree=(3, 2), hours=48, cold=1.0, squeeze=0.08, share=1.0, moved=0, bypass=0),
    "station_park": dict(role="pending", seed=13, ring=14, chords=2, tree=(4, 3), hours=72, cold=-4.0, squeeze=0.1, share=0.35, moved=1, bypass=1),
    "north_bank": dict(role="hidden", seed=21, ring=22, chords=3, tree=(5, 3), hours=96, cold=-8.0, squeeze=0.15, share=0.25, moved=1, bypass=0),
    "west_hill": dict(role="hidden", seed=22, ring=24, chords=4, tree=(5, 3), hours=96, cold=-11.0, squeeze=0.18, share=0.25, moved=0, bypass=1),
    "old_town": dict(role="hidden", seed=23, ring=20, chords=3, tree=(5, 3), hours=96, cold=-6.0, squeeze=0.12, share=0.25, moved=1, bypass=1),
    "river_side": dict(role="hidden", seed=24, ring=26, chords=4, tree=(5, 3), hours=96, cold=-14.0, squeeze=0.2, share=0.25, moved=2, bypass=0),
    "east_gate": dict(role="hidden", seed=25, ring=18, chords=2, tree=(5, 3), hours=96, cold=-3.0, squeeze=0.1, share=0.25, moved=0, bypass=0),
    "south_docks": dict(role="hidden", seed=26, ring=24, chords=3, tree=(5, 3), hours=96, cold=-9.0, squeeze=0.16, share=0.25, moved=0, bypass=2),
}
CLOSED = 4.0e9          # a closed bypass valve, as fitted: about 5 g/s at 1 bar


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
        if plant:                                   # the plant moves its supply temperature by at most 0.6 K an hour
            last = float(plant[-1]["supply_C"]); ts = min(last + 0.6, max(last - 0.6, ts))
        plant.append(dict(time_h=h, supply_C=round(ts, 1)))
    return dem, plant, tout


def package(net, dem, plant, init, points, hours, dp):
    pk = dict(head=dict(district=net["name"], plant_node=net["plant"], ground_C=8.0, hours=hours),
              nodes=net["nodes"], pipes=[{k: p[k] for k in ("pipe", "from_node", "to_node", "length_m", "volume_m3", "loss_time_h")} for p in net["pipes"]],
              subs=[dict({k: str(s[k]) for k in ("substation", "node", "return_C", "valve_capacity")}, bypass_resistance="%.3g" % CLOSED) for s in net["subs"]],
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
    w("pipes.csv", pk["pipes"], ["pipe", "from_node", "to_node", "length_m", "volume_m3", "loss_time_h"])
    w("substations.csv", pk["subs"], ["substation", "node", "return_C", "valve_capacity", "bypass_resistance"])
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
    dp = calibrate_dp(net, dem, plant, hours, spec, actual)
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
    camp_pipes, camp_items = campaigns(net, actual, np.random.default_rng(spec["seed"] + 1700))
    # a point is kept only where a correct reading of these campaigns, or of two other sets of campaigns with the
    # bypasses' resistances 1 per cent off, stays within 0.4 of the band: the answer must not hang on meter noise
    worst = {r["point"]: 0.0 for r in points}
    for c_, (seed_, f_) in enumerate(((None, 1.0), (spec["seed"] + 2700, 1.01), (spec["seed"] + 3700, 0.99))):
        cp_ = camp_pipes if seed_ is None else campaigns(net, actual, np.random.default_rng(seed_))[0]
        alt = dict(actual, R=from_campaigns(cp_), bypass={k: v * f_ for k, v in actual["bypass"].items()})
        got = T.simulate(pk, None, alt)
        for r in points:
            p_ = r["point"]; worst[p_] = max(worst[p_], abs(got[p_] - res[p_]) / band(p_, res[p_]))
    dropped = [r for r in points if worst[r["point"]] > 0.4]
    points = [r for r in points if worst[r["point"]] <= 0.4]
    pk = package(net, dem, plant, init, points, hours, dp)
    folder = os.path.join(DATA, "examples" if spec["role"] == "example" else "pending", name) if spec["role"] != "hidden" else os.path.join(HIDDEN, name)
    write(pk, folder)
    with open(os.path.join(folder, "campaign_pipes.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["campaign", "pipe", "flow_kg_s", "drop_Pa"]); wr.writeheader(); wr.writerows(camp_pipes)
    with open(os.path.join(folder, "campaign_flows.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["campaign", "item", "flow_kg_s", "dp_Pa"]); wr.writeheader(); wr.writerows(camp_items)
    rows_ = [dict(point=r["point"], value="%.6f" % res[r["point"]]) for r in points]
    out = os.path.join(folder, "expected.csv") if spec["role"] == "example" else os.path.join(HIDDEN, "_result_%s.csv" % name)
    os.makedirs(HIDDEN, exist_ok=True)
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["point", "value"]); wr.writeheader(); wr.writerows(rows_)
    json.dump(actual, open(os.path.join(HIDDEN, "_actual_%s.json" % name), "w"), indent=1)
    # what the records alone give
    plain = T.simulate(pk, None, {"R": from_campaigns(camp_pipes)})
    bad = sum(1 for r in points if abs(plain[r["point"]] - res[r["point"]]) > band(r["point"], res[r["point"]]))
    alone = {}
    for cond in ("node", "bypass"):
        if not actual[cond]: continue
        part = T.simulate(pk, None, {k: (v if k != cond else {}) for k, v in actual.items()})      # every other condition right
        alone[cond] = sum(1 for r in points if abs(part[r["point"]] - res[r["point"]]) > band(r["point"], res[r["point"]]))
        if alone[cond] < 20:
            raise SystemExit("%s: %s alone puts only %d points out" % (name, cond, alone[cond]))
    print(name, "pipes", len(net["pipes"]), "subs", len(net["subs"]), "reversing", flips, "valve-limited steps", sat_steps,
          "max courant %.2f" % max(facts["courant"]), "margin %.1f K" % facts["margin"], "conditions", json.dumps({k: v for k, v in actual.items() if k != "R"}),
          "records alone: %d of %d points out" % (bad, len(points)), "each alone", json.dumps(alone), "truth %.0f s" % secs,
          "dropped as noise-sensitive %d" % len(dropped), flush=True)


def from_campaigns(rows_):
    """HN-3: a pipe's resistance is its drop over m|m| in the campaign in which its drop was largest."""
    best = {}
    for r in rows_:
        d = float(r["drop_Pa"]); m = float(r["flow_kg_s"])
        if r["pipe"] not in best or abs(d) > abs(best[r["pipe"]][0]): best[r["pipe"]] = (d, m)
    return {p: d / (m * abs(m)) for p, (d, m) in best.items()}


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
    """Every pipe's resistance; the substations connected elsewhere than the register says; the bypasses open."""
    actual = {"R": {p["pipe"]: p["resistance_Pa_s2_kg2"] for p in net["pipes"]}, "node": {}, "bypass": {}}
    kids = {}
    for p in net["pipes"]:
        if p["kind"] == "tree": kids.setdefault(p["from_node"], []).append(p["to_node"])
    root = {}
    def mark(n, r):
        root[n] = r
        for c in kids.get(n, []): mark(c, r)
    ring = [p["from_node"] for p in net["pipes"] if p["kind"] == "ring"]
    for r in ring: mark(r, r)
    depth = {}
    def dep(n, d):
        depth[n] = d
        for c in kids.get(n, []): dep(c, d + 1)
    for r in ring: dep(r, 0)
    used = set()
    count = {}
    for s_ in net["subs"]: count[s_["node"]] = count.get(s_["node"], 0) + 1
    # a substation moved away leaves water flowing to its registered node: other substations there, or beyond it
    big = [s_ for s_ in net["subs"] if s_["design_kW"] >= 150 and depth.get(s_["node"], 0) >= 1
           and (count[s_["node"]] >= 2 or s_["node"] in kids)]
    order = list(rng.permutation(len(big)))
    for k in range(spec["moved"]):
        s_ = big[order.pop()]
        far = [n for n in net["nodes"] if depth.get(n, 0) >= 2 and n not in used and n != s_["node"]
               and abs(ring.index(root[n]) - ring.index(root[s_["node"]])) >= len(ring) // 3]
        b_ = far[int(rng.integers(len(far)))]
        actual["node"][s_["substation"]] = b_; used |= {b_, s_["node"]}
    for k in range(spec["bypass"]):
        while True:
            s_ = big[order.pop()]
            if s_["node"] not in used: break
        mb = float(rng.uniform(1.5, 3.0))
        actual["bypass"][s_["substation"]] = float("%.5g" % (1.0e5 / mb ** 2)); used.add(s_["node"])
    return actual


def campaigns(net, actual, rng, count=3):
    """Hydraulic test campaigns: on three mornings every pipe's flow and drop, and every substation's flow, logged
    together with the network as it is."""
    nodes = net["nodes"]; ix = {n: i for i, n in enumerate(nodes)}; N = len(nodes); plant = ix[net["plant"]]
    u = np.array([ix[p["from_node"]] for p in net["pipes"]]); v = np.array([ix[p["to_node"]] for p in net["pipes"]])
    R = np.array([actual["R"][p["pipe"]] for p in net["pipes"]])
    sn = np.array([ix[actual["node"].get(s_["substation"], s_["node"])] for s_ in net["subs"]])
    Rb = np.array([actual["bypass"].get(s_["substation"], CLOSED) for s_ in net["subs"]])
    pipes, items = [], []
    noise = lambda x, a: x * (1 + float(np.clip(rng.normal(0, a / 3), -a, a)))
    for c in range(1, count + 1):
        m_s = np.array([s_["design_kW"] / (CP * 45.0) * float(rng.uniform(0.45, 0.9)) for s_ in net["subs"]])
        h = solve_fixed(N, plant, u, v, R, sn, m_s)
        dpp = float(round(2 * h[sn].max() + float(rng.uniform(70000, 110000)), -2))
        for it in range(50):                                   # the bypasses take what the pressure gives them
            mb = np.sqrt(np.maximum(dpp - 2 * h[sn], 0) / Rb)
            h2 = solve_fixed(N, plant, u, v, R, sn, m_s + mb)
            if np.abs(h2 - h).max() < 1e-6: break
            h = h2
        h = h2
        dh = h[v] - h[u]; m = dh / np.sqrt(R * (np.abs(dh) + 1e-6))
        for p, mm, d in zip(net["pipes"], m, dh):          # drop p_from - p_to = h_to - h_from, with h the drop from the plant
            pipes.append(dict(campaign=str(c), pipe=p["pipe"], flow_kg_s="%.5f" % noise(mm, 0.001), drop_Pa="%.2f" % noise(d, 0.002)))
        items.append(dict(campaign=str(c), item="plant", flow_kg_s="%.4f" % noise((m_s + mb).sum(), 0.001), dp_Pa="%.0f" % dpp))
        for s_, ms in zip(net["subs"], m_s):
            items.append(dict(campaign=str(c), item=s_["substation"], flow_kg_s="%.5f" % noise(ms, 0.001), dp_Pa=""))
    return pipes, items


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
