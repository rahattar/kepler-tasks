"""truth.py: the sealed calculation of HN-3, written plainly. One deque of parcels a pipe, Newton's method on the
supply pressures with the valve limits, every step in the order HN-3 section 5 gives.

    python3 truth.py PACKAGE_DIR OUT_CSV
"""
import csv, json, math, os, sys
from collections import deque
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

RHO, CP, DT = 975.0, 4.19, 120.0


def rows(folder, name):
    with open(os.path.join(folder, name), newline="") as f:
        return list(csv.DictReader(f))


def load(folder):
    d = json.load(open(os.path.join(folder, "network.json")))
    nodes = [r["node"] for r in rows(folder, "nodes.csv")]
    pipes = rows(folder, "pipes.csv")
    subs = rows(folder, "substations.csv")
    demand = rows(folder, "demand.csv")
    plant = rows(folder, "plant.csv")
    init = rows(folder, "initial.csv")
    points = rows(folder, "points.csv")
    return dict(head=d, nodes=nodes, pipes=pipes, subs=subs, demand=demand, plant=plant, init=init, points=points)


class Steps:
    """A piecewise-constant schedule: value at time t is the last entry at or before t."""
    def __init__(self, times, values):
        o = np.argsort(times, kind="stable")
        self.t = np.asarray(times, float)[o]; self.v = [values[i] for i in o]
    def at(self, t):
        i = int(np.searchsorted(self.t, t + 1e-9, side="right")) - 1
        return self.v[max(i, 0)]


def pop(content, vol, from_right, t, tg, tau):
    """Take `vol` of water from one end of a pipe; return its heat content (m3 * deg C) at time t."""
    heat = 0.0; left = vol
    while left > 1e-15 and content:
        part = content[-1] if from_right else content[0]
        v, t0, te = part
        temp = tg + (t0 - tg) * math.exp(-(t - te) / tau)
        if v <= left + 1e-15:
            heat += v * temp; left -= v
            content.pop() if from_right else content.popleft()
        else:
            heat += left * temp; part[0] = v - left; left = 0.0
    if left > 1e-9:
        raise SystemExit("a pipe passed more than its volume in one step")
    return heat


def simulate(pkg, facts=None):
    head = pkg["head"]; tg = float(head["ground_C"]); hours = int(head["hours"])
    nodes = pkg["nodes"]; ix = {n: i for i, n in enumerate(nodes)}; N = len(nodes)
    plant = ix[head["plant_node"]]
    P = len(pkg["pipes"])
    u = np.array([ix[r["from_node"]] for r in pkg["pipes"]]); v = np.array([ix[r["to_node"]] for r in pkg["pipes"]])
    R = np.array([float(r["resistance_Pa_s2_kg2"]) for r in pkg["pipes"]])
    V = np.array([float(r["volume_m3"]) for r in pkg["pipes"]])
    tau = np.array([float(r["loss_time_h"]) * 3600.0 for r in pkg["pipes"]])
    pname = {r["pipe"]: i for i, r in enumerate(pkg["pipes"])}
    S = len(pkg["subs"]); sname = {r["substation"]: i for i, r in enumerate(pkg["subs"])}
    snode = np.array([ix[r["node"]] for r in pkg["subs"]])
    Tr = np.array([float(r["return_C"]) for r in pkg["subs"]])
    K = np.array([float(r["valve_capacity"]) for r in pkg["subs"]])
    dem = {}
    for r in pkg["demand"]:
        dem.setdefault(r["substation"], ([], []))
        dem[r["substation"]][0].append(float(r["time_h"]) * 3600.0); dem[r["substation"]][1].append(float(r["heat_kW"]))
    dsched = [Steps(*dem[r["substation"]]) for r in pkg["subs"]]
    ps = Steps([float(r["time_h"]) * 3600.0 for r in pkg["plant"]], [(float(r["supply_C"]), float(r["dp_Pa"])) for r in pkg["plant"]])
    sup = [None] * P; ret = [None] * P
    Ts = np.zeros(N); Trn = np.zeros(N)
    for r in pkg["init"]:
        if r["kind"] == "pipe":
            j = pname[r["name"]]
            (sup if r["network"] == "supply" else ret)[j] = deque([[V[j], float(r["temp_C"]), 0.0]])
        else:
            (Ts if r["network"] == "supply" else Trn)[ix[r["name"]]] = float(r["temp_C"])
    free = np.array([i for i in range(N) if i != plant]); pos = -np.ones(N, int); pos[free] = np.arange(N - 1)
    h = np.zeros(N)                      # supply pressure drop from the plant, Pa
    steps = hours * 30
    heat_acc = np.zeros(S); out = {}
    want_points = {}
    for r in pkg["points"]:
        want_points.setdefault(int(round(float(r["time_h"]) * 30)), []).append(r)
    DELTA = 1e-6
    for k in range(1, steps + 1):
        t0 = (k - 1) * DT; t1 = k * DT
        Tsup_plant, dpp = ps.at(t0)
        Q = np.array([s_.at(t0) for s_ in dsched])
        mwant = Q / (CP * (Ts[snode] - Tr))
        # ---- hydraulics: Newton on h at every node but the plant
        for it in range(200):
            dh = h[v] - h[u]                            # flow u->v where the drop grows along it
            a = np.abs(dh)
            m = dh / np.sqrt(R * (a + DELTA))
            g = (a + 2 * DELTA) / (2 * np.sqrt(R) * (a + DELTA) ** 1.5)   # dm/d(dh)
            dpn = dpp - 2.0 * h[snode]
            mmax = K * np.sqrt(np.maximum(dpn, 0.0))
            sat = mmax < mwant
            msub = np.where(sat, mmax, mwant)
            gsub = np.where(sat & (dpn > 0), K / np.sqrt(np.maximum(dpn, 1e-30)), 0.0)    # -d msub / dh
            res = np.zeros(N)
            np.add.at(res, v, m); np.add.at(res, u, -m); np.add.at(res, snode, -msub)
            r_ = res[free]
            if np.abs(r_).max() < 1e-10 * max(1.0, msub.sum()):
                break
            # d res / d h: m = f(h_v - h_u), res[v] += m, res[u] -= m, res[n] -= substation flow
            Jr = np.concatenate([v, v, u, u, snode]); Jc = np.concatenate([v, u, u, v, snode])
            Jv = np.concatenate([g, -g, g, -g, gsub])
            keep = (pos[Jr] >= 0) & (pos[Jc] >= 0)
            J = sp.csc_matrix((Jv[keep], (pos[Jr[keep]], pos[Jc[keep]])), shape=(N - 1, N - 1))
            step = spsolve(J, -r_)
            lam = 1.0; base = np.abs(r_).sum()
            while True:
                hn = h.copy(); hn[free] += lam * step
                dh2 = hn[v] - hn[u]; m2 = dh2 / np.sqrt(R * (np.abs(dh2) + DELTA))
                dp2 = dpp - 2.0 * hn[snode]; ms2 = np.minimum(mwant, K * np.sqrt(np.maximum(dp2, 0.0)))
                r2 = np.zeros(N); np.add.at(r2, v, m2); np.add.at(r2, u, -m2); np.add.at(r2, snode, -ms2)
                if np.abs(r2[free]).sum() < base or lam < 1e-4:
                    h = hn; break
                lam *= 0.5
        else:
            raise SystemExit("hydraulics did not converge at step %d" % k)
        dh = h[v] - h[u]; m = dh / np.sqrt(R * (np.abs(dh) + DELTA))
        dpn = dpp - 2.0 * h[snode]; msub = np.minimum(mwant, K * np.sqrt(np.maximum(dpn, 0.0)))
        vol = np.abs(m) * DT / RHO
        if np.any(vol >= V):
            raise SystemExit("a pipe passed its volume in one step at step %d" % k)
        # ---- supply transport: outflows from the content at the start of the step
        avol = np.zeros(N); aheat = np.zeros(N)
        for j in range(P):
            if vol[j] <= 0: continue
            if m[j] > 0:
                avol[v[j]] += vol[j]; aheat[v[j]] += pop(sup[j], vol[j], True, t1, tg, tau[j])
            else:
                avol[u[j]] += vol[j]; aheat[u[j]] += pop(sup[j], vol[j], False, t1, tg, tau[j])
        net = 0.0
        for j in range(P):
            if u[j] == plant: net += m[j]
            if v[j] == plant: net -= m[j]
        if net > 0:
            avol[plant] += net * DT / RHO; aheat[plant] += net * DT / RHO * Tsup_plant
        Ts = np.where(avol > 0, aheat / np.where(avol > 0, avol, 1.0), Ts)
        for j in range(P):
            if vol[j] <= 0: continue
            if m[j] > 0: sup[j].appendleft([vol[j], Ts[u[j]], t1])
            else: sup[j].append([vol[j], Ts[v[j]], t1])
        heat = msub * CP * (Ts[snode] - Tr)
        heat_acc += heat
        # ---- return transport: flows reversed
        avol = np.zeros(N); aheat = np.zeros(N)
        for j in range(P):
            if vol[j] <= 0: continue
            if m[j] > 0:                 # return water goes v -> u: leaves at the u end
                avol[u[j]] += vol[j]; aheat[u[j]] += pop(ret[j], vol[j], False, t1, tg, tau[j])
            else:
                avol[v[j]] += vol[j]; aheat[v[j]] += pop(ret[j], vol[j], True, t1, tg, tau[j])
        sv = msub * DT / RHO
        np.add.at(avol, snode, sv); np.add.at(aheat, snode, sv * Tr)
        Trn = np.where(avol > 0, aheat / np.where(avol > 0, avol, 1.0), Trn)
        for j in range(P):
            if vol[j] <= 0: continue
            if m[j] > 0: ret[j].append([vol[j], Trn[v[j]], t1])
            else: ret[j].appendleft([vol[j], Trn[u[j]], t1])
        if facts is not None:
            facts.setdefault("sign", []).append(np.sign(np.where(np.abs(m) > 1e-6, m, 0.0))); facts.setdefault("m", []).append(m.copy()); facts.setdefault("dpn", []).append(dpn.copy()); facts.setdefault("h", []).append(h.copy()); facts.setdefault("mw", []).append(mwant.copy())
            facts.setdefault("sat", []).append(int((msub < mwant - 1e-12).sum()))
            facts.setdefault("courant", []).append(float((vol / V).max()))
        if k % 30 == 0:
            for r in want_points.get(k, []):
                if r["quantity"] == "supply_C": out[r["point"]] = Ts[snode[sname[r["item"]]]]
                elif r["quantity"] == "heat_kW": out[r["point"]] = heat_acc[sname[r["item"]]] / 30.0
                elif r["quantity"] == "return_C": out[r["point"]] = Trn[plant]
            heat_acc[:] = 0.0
    if facts is not None:
        facts["final"] = dict(sup=[sum(p_[0] * (tg + (p_[1] - tg) * math.exp(-(steps * DT - p_[2]) / tau[j])) for p_ in sup[j]) / V[j] for j in range(P)],
                              ret=[sum(p_[0] * (tg + (p_[1] - tg) * math.exp(-(steps * DT - p_[2]) / tau[j])) for p_ in ret[j]) / V[j] for j in range(P)],
                              Ts=Ts.tolist(), Trn=Trn.tolist())
    return out


def main(folder, out_csv):
    pkg = load(folder)
    res = simulate(pkg)
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["point", "value"])
        for r in pkg["points"]: w.writerow([r["point"], "%.6f" % res[r["point"]]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
