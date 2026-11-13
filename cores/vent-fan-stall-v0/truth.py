"""truth.py: the sealed result of a district package, and the audit of the design rules.

The state of the district is carried through the log from the opening settings. A setting is changed
gradually (a regulator is wound, a door is swung), so the district moves through steady states: the changed
resistance is taken from its old value to its new one in small steps, and after each step the flow settles
under the air's own inertia (vnet.Net.settle). Where a step removes the state the district was in, the air's
dynamics take it to another. The audit repeats the record with finer steps, with the resistance moved along
another path between the same two values, with another inertia in every branch, and with every resistance 3 per cent
up and down (which is every fan pressure 3 per cent down and up); a record whose result depends on any of these is refused.
"""
import csv, os, zlib
import numpy as np
from vnet import Net

def load(folder):
    rd = lambda n: list(csv.DictReader(open(os.path.join(folder, n))))
    d = dict(name=os.path.basename(folder))
    d["branches"] = [dict(branch=r["branch"], frm=r["from_node"], to=r["to_node"], kind=r["kind"],
                          R=float(r["resistance_Ns2_m8"]) if r["resistance_Ns2_m8"] else None, item=r["item"]) for r in rd("branches.csv")]
    d["regs"] = {}
    for r in rd("regulators.csv"): d["regs"].setdefault(r["regulator"], {})[int(r["setting"])] = float(r["resistance_Ns2_m8"])
    d["doors"] = {r["door"]: (float(r["resistance_closed_Ns2_m8"]), float(r["resistance_open_Ns2_m8"])) for r in rd("doors.csv")}
    d["fans"] = {r["fan"]: dict(branch=r["branch"], model=r["model"], blade=int(r["blade_setting"])) for r in rd("fans.csv")}
    d["curves"] = {}
    for r in rd("fan_curves.csv"):
        c = d["curves"].setdefault((r["model"], int(r["blade_setting"])), ([], []))
        c[0].append(float(r["flow_m3_s"])); c[1].append(float(r["pressure_Pa"]))
    d["log"] = [(r["time"], r["item"], r["setting"]) for r in rd("log.csv")]
    d["points"] = [(r["point"], r["time"], r["branch"]) for r in rd("points.csv")]
    return d

def network(d, kP=1.0, metric="phys"):
    nodes = {"ATM": 0}
    for b in d["branches"]:
        for x in (b["frm"], b["to"]): nodes.setdefault(x, len(nodes))
    idx = {b["branch"]: i for i, b in enumerate(d["branches"])}
    fans = {}
    for f, v in d["fans"].items():
        qs, ps = d["curves"][(v["model"], v["blade"])]
        fans[idx[v["branch"]]] = (np.array(qs), np.array(ps) * kP)
    if metric == "phys":   # an inertance for every branch, sealed: it must not matter, and the audit checks that it does not
        inert = np.array([5.0 + 60.0 * (zlib.crc32(b["branch"].encode()) % 1000) / 1000.0 for b in d["branches"]])
    else:
        inert = np.ones(len(d["branches"]))
    net = Net(len(nodes), [nodes[b["frm"]] for b in d["branches"]], [nodes[b["to"]] for b in d["branches"]], fans, inert)
    def Rof(settings):
        R = np.zeros(len(d["branches"]))
        for i, b in enumerate(d["branches"]):
            if b["kind"] in ("airway", "fan"): R[i] = b["R"]
            elif b["kind"] == "regulator": R[i] = d["regs"][b["item"]][int(settings[b["item"]])]
            else: R[i] = d["doors"][b["item"]][0 if settings[b["item"]] == "closed" else 1]
        return R
    return net, Rof, sorted(fans)

def simulate(d, kR=1.0, kP=1.0, metric="phys", substeps=12, path="geo", every=False, dt0=0.5):
    """Carry the district through its log. A change that leaves every fan on its limb is one settling; a change
    on which a fan changes limb, and every change of a bulkhead door, an airlock door or a regulator at
    setting 2 or below, is taken in `substeps` steps of the resistance (every=True: all changes are)."""
    net, Rof, fanb = network(d, kP, metric)
    idx = {b["branch"]: i for i, b in enumerate(d["branches"])}
    t0 = d["log"][0][0]
    settings = {x: v for t, x, v in d["log"] if t == t0}
    events = [(t, x, v) for t, x, v in d["log"] if t != t0]
    rounds = sorted({t for p, t, b in d["points"]})
    R = Rof(settings) * kR
    y, it, ok = net.start(R)
    stable = ok; ev_limbs = []; rd_limbs = []; rd_settings = []; flows = {}
    by_round = {}
    for p, t, b in d["points"]: by_round.setdefault(t, []).append((p, idx[b]))
    seq = sorted([(t, 0, x, v) for t, x, v in events] + [(t, 1, None, None) for t in rounds])
    qfan = []; cur = net.limbs(net.Z @ y); nfine = 0
    def walk(y, R, Rn, n):
        ok = True
        for s in range(1, n + 1):
            lam = s / n
            Rl = R * (Rn / R) ** lam if path == "geo" else ((1 - lam) / np.sqrt(R) + lam / np.sqrt(Rn)) ** -2
            y, it, o = net.settle(y, Rl, dt0=dt0 * (100.0 if n == 1 else 1.0)); ok &= o
        return y, ok
    for t, kind, x, v in seq:
        if kind == 0:
            old = settings[x]; settings[x] = v; Rn = Rof(settings) * kR
            big = every or x.startswith(("SD", "AL")) or (x.startswith("REG") and min(int(old), int(v)) <= 2)
            if not big:
                y1, ok = walk(y, R, Rn, 1)
                if net.limbs(net.Z @ y1) != cur: big = True
            if big: y1, ok = walk(y, R, Rn, substeps); nfine += 1
            y = y1; stable &= ok; R = Rn; cur = net.limbs(net.Z @ y)
            ev_limbs.append((t, x, v, cur))
        else:
            q = net.Z @ y
            rd_limbs.append(cur); rd_settings.append(tuple(sorted((k, str(vv)) for k, vv in settings.items())))
            qfan.append([q[b] for b in fanb])
            for p, i in by_round[t]: flows[p] = q[i]
    return dict(flows=flows, ev_limbs=ev_limbs, rd_limbs=rd_limbs, rd_settings=rd_settings, stable=stable,
                rounds=rounds, qfan=np.array(qfan), net=net, Rof=Rof, fanb=fanb, nfine=nfine)

def other_states(d, settings_list):
    """For each settings tuple: the limbs of the steady state the district comes to when the configuration is
    approached from above (every resistance three times as high, then brought down) and from below (a third)."""
    net, Rof, fanb = network(d)
    out = []
    for st in settings_list:
        R = Rof(dict(st)); found = set()
        for k in (3.0, 1 / 3.0):
            y, it, ok = net.start(R * k)
            for s in range(1, 13): y, it, ok = net.settle(y, R * k ** (1 - s / 12))
            found.add(net.limbs(net.Z @ y))
        out.append(found)
    return out

def audit(folder, regime):
    d = load(folder)
    base = simulate(d)
    if not base["stable"]: return dict(ok=False, why="an unstable steady state on the way")
    lim = base["rd_limbs"]; n_st = sum(1 for l in lim if l != "RR")
    qmax = [base["net"].fans[b][0][-1] for b in base["fanb"]]
    if (base["qfan"] <= 0).any() or (base["qfan"] >= np.array(qmax)).any(): return dict(ok=False, why="a fan off its table")
    changes = [(t, x, v, l) for (t, x, v, l), prev in zip(base["ev_limbs"], ["RR"] + [e[3] for e in base["ev_limbs"]][:-1]) if l != prev]
    distinct = sorted(set(base["rd_settings"]))
    states = dict(zip(distinct, other_states(d, distinct)))
    seen = {}
    for s, l in zip(base["rd_settings"], lim): seen.setdefault(s, set()).add(l)
    twin = sum(1 for s, ls in seen.items() if len(ls) > 1)
    multi = sum(1 for s in distinct if len(states[s]) > 1)
    if regime == "clear":
        if any(l != "RR" for t, x, v, l in base["ev_limbs"]): return dict(ok=False, why="a fan leaves the healthy limb")
        if multi: return dict(ok=False, why="a surveyed configuration has more than one steady state")
    else:
        if any(set(l) - set("LR") for l in lim) or "LL" in lim: return dict(ok=False, why="a round off the two states wanted")
        onsets = sum(1 for a, b in zip(["RR"] + lim[:-1], lim) if a == "RR" and b != "RR")
        recov = sum(1 for a, b in zip(lim[:-1], lim[1:]) if a != "RR" and b == "RR")
        if n_st < 8 or len(lim) - n_st < 8 or onsets < 3 or recov < 2 or multi < len(distinct):
            return dict(ok=False, why="too little of the condition: stalled %d healthy %d onsets %d recoveries %d twins %d" % (n_st, len(lim) - n_st, onsets, recov, twin))
    pts = [p for p, t, b in d["points"]]
    f0 = np.array([base["flows"][p] for p in pts])
    for kw in (dict(kR=0.97), dict(kR=1.03)):      # a fan pressure scale k is the resistance scale 1/k
        v = simulate(d, **kw)
        if v["rd_limbs"] != base["rd_limbs"]: return dict(ok=False, why="thin margin: %s" % kw)
    for kw in (dict(substeps=40, dt0=0.05), dict(metric="ident"), dict(substeps=40, path="area"), dict(substeps=2, every=True)):
        v = simulate(d, **kw); f1 = np.array([v["flows"][p] for p in pts])
        if np.abs(f1 - f0).max() > 1e-3: return dict(ok=False, why="depends on how the change is made: %s" % kw)
    facts = dict(rounds=len(lim), rounds_stalled=n_st, limb_changes=len(changes), twin_configurations=twin,
                 distinct_round_configurations=len(distinct), configurations_with_two_states=multi,
                 points=len(pts), branches=len(d["branches"]), log_rows=len(d["log"]), meshes=base["net"].M,
                 changes_followed_in_steps=base["nfine"],
                 limbs="".join("s" if l != "RR" else "." for l in lim),
                 changes=[(t, x, str(v), l) for t, x, v, l in changes],
                 fan_flow_healthy=[float(base["qfan"][[i for i, l in enumerate(lim) if l == "RR"]].min()), float(base["qfan"].max())],
                 fan_flow_stalled_min=float(base["qfan"].min()))
    summary = "rounds %d stalled %d  limb changes %d  twins %d  two-state configs %d of %d  %s" % (
        len(lim), n_st, len(changes), twin, multi, len(distinct), facts["limbs"])
    return dict(ok=True, result=[(p, base["flows"][p]) for p in pts], facts=facts, summary=summary)
