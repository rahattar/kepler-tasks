"""truth.py: the sealed result of a district package, and the audit of the design rules (bare core v1).

The package carries what the district has on record: surveys of its airways, the resistance each stopping was
built to, a work log. The truth is the physics of the district as it is: the sealed resistance of every
airway, stopping and fan duct (hidden/_true_<district>.json), carried through the log as in v0 (each change
gradual, the flow settling on the inertial equations).
"""
import csv, json, os, zlib
import numpy as np
from vnet import Net

def load(folder):
    rd = lambda n: list(csv.DictReader(open(os.path.join(folder, n))))
    d = dict(name=json.load(open(os.path.join(folder, "district.json")))["district"])
    d["allowance"] = json.load(open(os.path.join(folder, "district.json")))["survey_allowance"]
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
    d["surveys"] = [(r["date"], r["branch"], float(r["dp_Pa"]), float(r["q_m3_s"])) for r in rd("surveys.csv")]
    d["work"] = [(r["date"], r["branch"], r["work"]) for r in rd("work_log.csv")]
    return d

def network(d, Rfix, kP=1.0, metric="phys"):
    """Rfix: resistance of every airway, stopping and fan duct, by branch name."""
    nodes = {"ATM": 0}
    for b in d["branches"]:
        for x in (b["frm"], b["to"]): nodes.setdefault(x, len(nodes))
    idx = {b["branch"]: i for i, b in enumerate(d["branches"])}
    fans = {}
    for f, v in d["fans"].items():
        qs, ps = d["curves"][(v["model"], v["blade"])]
        fans[idx[v["branch"]]] = (np.array(qs), np.array(ps) * kP)
    if metric == "phys":
        inert = np.array([5.0 + 60.0 * (zlib.crc32(b["branch"].encode()) % 1000) / 1000.0 for b in d["branches"]])
    else:
        inert = np.ones(len(d["branches"]))
    net = Net(len(nodes), [nodes[b["frm"]] for b in d["branches"]], [nodes[b["to"]] for b in d["branches"]], fans, inert)
    def Rof(settings):
        R = np.zeros(len(d["branches"]))
        for i, b in enumerate(d["branches"]):
            if b["kind"] in ("airway", "stopping", "fan"): R[i] = Rfix[b["branch"]]
            elif b["kind"] == "regulator": R[i] = d["regs"][b["item"]][int(settings[b["item"]])]
            else: R[i] = d["doors"][b["item"]][0 if settings[b["item"]] == "closed" else 1]
        return R
    return net, Rof, sorted(fans), nodes

def simulate(d, Rfix, kR=1.0, kP=1.0, metric="phys", substeps=12, path="geo", every=False, dt0=0.5):
    net, Rof, fanb, nodes = network(d, Rfix, kP, metric)
    idx = {b["branch"]: i for i, b in enumerate(d["branches"])}
    t0 = d["log"][0][0]
    settings = {x: v for t, x, v in d["log"] if t == t0}
    events = [(t, x, v) for t, x, v in d["log"] if t != t0]
    rounds = sorted({t for p, t, b in d["points"]})
    R = Rof(settings) * kR
    y, it, ok = net.start(R)
    stable = ok; ev_limbs = []; rd_limbs = []; flows = {}
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
            rd_limbs.append(cur); qfan.append([q[b] for b in fanb])
            for p, i in by_round[t]: flows[p] = q[i]
    q = net.Z @ y; h, dd = net.law(q, R)
    now = {b["branch"]: (float(h[i]), float(q[i])) for i, b in enumerate(d["branches"])}   # the district as it stands at the end
    return dict(flows=flows, ev_limbs=ev_limbs, rd_limbs=rd_limbs, stable=stable, rounds=rounds, qfan=np.array(qfan),
                net=net, fanb=fanb, nfine=nfine, now=now, settings=settings)

def audit(folder, true_file, close_at=None, sim=None):
    """close_at: the time of the bulkhead closure whose outcome the records leave open, or None.
    The margin rule (every resistance 3 per cent up and down) holds for every round before it."""
    d = load(folder); Rtrue = json.load(open(true_file))["R"]
    base = sim or simulate(d, Rtrue)
    if not base["stable"]: return dict(ok=False, why="an unstable steady state on the way")
    lim = base["rd_limbs"]; n_st = sum(1 for l in lim if l != "RR")
    qmax = [base["net"].fans[b][0][-1] for b in base["fanb"]]
    if (base["qfan"] <= 0).any() or (base["qfan"] >= np.array(qmax)).any(): return dict(ok=False, why="a fan off its table")
    if any(set(l) - set("LR") for l in lim) or "LL" in lim: return dict(ok=False, why="a round off the two states wanted")
    onsets = sum(1 for a, b in zip(["RR"] + lim[:-1], lim) if a == "RR" and b != "RR")
    recov = sum(1 for a, b in zip(lim[:-1], lim[1:]) if a != "RR" and b == "RR")
    few = (8, 3, 2) if len(lim) > 20 else (3, 2, 1)
    if n_st < few[0] or len(lim) - n_st < few[0] or onsets < few[1] or recov < few[2]:
        return dict(ok=False, why="too little stall: stalled %d healthy %d onsets %d recoveries %d %s" % (n_st, len(lim) - n_st, onsets, recov, "".join("s" if l != "RR" else "." for l in lim)))
    nbefore = len(lim) if close_at is None else sum(1 for t in base["rounds"] if t < close_at)
    for kw in (dict(kR=0.97), dict(kR=1.03)):
        v = simulate(d, Rtrue, **kw)
        if v["rd_limbs"][:nbefore] != lim[:nbefore]: return dict(ok=False, why="thin margin: %s" % kw)
    pts = [p for p, t, b in d["points"]]
    f0 = np.array([base["flows"][p] for p in pts])
    for kw in (dict(substeps=40, dt0=0.05), dict(metric="ident"), dict(substeps=40, path="area"), dict(substeps=2, every=True)):
        v = simulate(d, Rtrue, **kw); f1 = np.array([v["flows"][p] for p in pts])
        if np.abs(f1 - f0).max() > 1e-3: return dict(ok=False, why="depends on how the change is made: %s" % kw)
    facts = dict(rounds=len(lim), rounds_stalled=n_st, points=len(pts), branches=len(d["branches"]), log_rows=len(d["log"]),
                 limbs="".join("s" if l != "RR" else "." for l in lim), allowance=d["allowance"])
    return dict(ok=True, base=base, facts=facts, d=d)
