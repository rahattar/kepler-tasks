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
    "harbour_east": dict(role="example", seed=11, ring=8, chords=1, tree=(3, 3), hours=48, cold=-2.0, squeeze=0.08, share=1.0),
    "mill_quarter": dict(role="example", seed=12, ring=10, chords=1, tree=(3, 2), hours=48, cold=1.0, squeeze=0.08, share=1.0),
    "station_park": dict(role="pending", seed=13, ring=14, chords=2, tree=(4, 3), hours=72, cold=-4.0, squeeze=0.1, share=0.35),
    "north_bank": dict(role="hidden", seed=21, ring=22, chords=3, tree=(5, 3), hours=96, cold=-8.0, squeeze=0.15, share=0.25),
    "west_hill": dict(role="hidden", seed=22, ring=24, chords=4, tree=(5, 3), hours=96, cold=-11.0, squeeze=0.18, share=0.25),
    "old_town": dict(role="hidden", seed=23, ring=20, chords=3, tree=(5, 3), hours=96, cold=-6.0, squeeze=0.12, share=0.25),
    "river_side": dict(role="hidden", seed=24, ring=26, chords=4, tree=(5, 3), hours=96, cold=-14.0, squeeze=0.2, share=0.25),
    "east_gate": dict(role="hidden", seed=25, ring=18, chords=2, tree=(5, 3), hours=96, cold=-3.0, squeeze=0.1, share=0.25),
    "south_docks": dict(role="hidden", seed=26, ring=24, chords=3, tree=(5, 3), hours=96, cold=-9.0, squeeze=0.16, share=0.25),
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


def make(name):
    spec = SITES[name]
    rng = np.random.default_rng(spec["seed"] + 500)
    net = build(name, spec)
    hours = spec["hours"]
    dem, plant, tout = schedules(net, spec, rng)
    # plant pressure difference: what the farthest substation needs at design, squeezed
    dp = calibrate_dp(net, dem, plant, hours, spec)
    # spin-up: one day at the opening conditions, from a crude start
    first = [r for r in dem if r["time_h"] < 24]
    init0 = [dict(kind="pipe", name=p["pipe"], network="supply", temp_C=plant[0]["supply_C"] - 5) for p in net["pipes"]] + \
            [dict(kind="pipe", name=p["pipe"], network="return", temp_C=45.0) for p in net["pipes"]] + \
            [dict(kind="node", name=n, network="supply", temp_C=plant[0]["supply_C"] - 5) for n in net["nodes"]] + \
            [dict(kind="node", name=n, network="return", temp_C=45.0) for n in net["nodes"]]
    pk = package(net, first, plant[:24], [{k: str(v) for k, v in r.items()} for r in init0], [], 24, dp[:24])
    facts = {}
    T.simulate(pk, facts)
    fin = facts["final"]
    init = [dict(kind="pipe", name=p["pipe"], network="supply", temp_C="%.4f" % fin["sup"][j]) for j, p in enumerate(net["pipes"])] + \
           [dict(kind="pipe", name=p["pipe"], network="return", temp_C="%.4f" % fin["ret"][j]) for j, p in enumerate(net["pipes"])] + \
           [dict(kind="node", name=n, network="supply", temp_C="%.4f" % fin["Ts"][i]) for i, n in enumerate(net["nodes"])] + \
           [dict(kind="node", name=n, network="return", temp_C="%.4f" % fin["Trn"][i]) for i, n in enumerate(net["nodes"])]
    points = []
    for h in range(1, hours + 1):
        pick = [s for s in net["subs"] if rng.random() < spec["share"]]
        for s in pick:
            for q in ("supply_C", "heat_kW"):
                points.append(dict(point="H%03d-%s-%s" % (h, s["substation"], "T" if q == "supply_C" else "Q"), time_h=str(h), item=s["substation"], quantity=q))
        points.append(dict(point="H%03d-PLANT-T" % h, time_h=str(h), item="plant", quantity="return_C"))
    pk = package(net, dem, plant, init, points, hours, dp)
    facts = {}
    import time; t0 = time.time()
    res = T.simulate(pk, facts)
    secs = time.time() - t0
    sign = np.array(facts["sign"]); flips = int(((sign[1:] * sign[:-1]) < 0).any(axis=0).sum())
    sat_steps = int((np.array(facts["sat"]) > 0).sum())
    folder = os.path.join(DATA, "examples" if spec["role"] == "example" else "pending", name) if spec["role"] != "hidden" else os.path.join(HIDDEN, name)
    write(pk, folder)
    rows_ = [dict(point=r["point"], value="%.6f" % res[r["point"]]) for r in points]
    out = os.path.join(folder, "expected.csv") if spec["role"] == "example" else os.path.join(HIDDEN, "_result_%s.csv" % name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["point", "value"]); wr.writeheader(); wr.writerows(rows_)
    print(name, "pipes", len(net["pipes"]), "subs", len(net["subs"]), "pipes reversing", flips,
          "steps with a valve at its limit", sat_steps, "of", hours * 30, "max courant %.2f" % max(facts["courant"]),
          "truth %.0f s" % secs, flush=True)


def calibrate_dp(net, dem, plant, hours, spec):
    """The plant's pressure difference for each day: the share `squeeze` of substations would be short at the day's
    heaviest hour. Found from a run with valves that never limit."""
    big = copy.deepcopy(net)
    for s_ in big["subs"]: s_["valve_capacity"] = 1e6
    init = [dict(kind="pipe", name=p["pipe"], network=w, temp_C=str(plant[0]["supply_C"] - 5 if w == "supply" else 45.0)) for p in net["pipes"] for w in ("supply", "return")] + \
           [dict(kind="node", name=n, network=w, temp_C=str(plant[0]["supply_C"] - 5 if w == "supply" else 45.0)) for n in net["nodes"] for w in ("supply", "return")]
    pk = package(big, dem, plant, init, [], hours, [1e6] * hours)
    f = {}
    T.simulate(pk, f)
    h = np.array(f["h"]); mw = np.array(f["mw"])
    K = np.array([s_["valve_capacity"] for s_ in net["subs"]])
    sidx = [net["nodes"].index(s_["node"]) for s_ in net["subs"]]
    need = 2 * h[:, sidx] + (mw / K) ** 2               # plant pressure difference each substation needs, each step
    dp = []
    for day in range((hours + 23) // 24):
        rows_ = need[day * 720:(day + 1) * 720]
        peak = rows_.max(axis=1).argmax()
        dp_day = float(np.quantile(rows_[peak], 1.0 - spec["squeeze"]))
        dp += [round(dp_day, 0)] * 24
    return dp[:hours]


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
