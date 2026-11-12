"""Sprinkler system hydraulics to the site standard FP-7 (core/data/docs/fp7_hydraulics.md): the truth side.

Used by the generator: the truth, the examples' expected results and the readings of each system's re-rating
campaign. The reference program (ref_rerate.py) carries its own implementation, written from the standard alone.

Units are the standard's: pressure psi, flow gpm, length ft, diameter in.
"""
import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HW_N = 1.85
PSI_PER_FT = 0.433                      # water, per foot of elevation
P_MIN_HEAD = 7.0                        # least pressure at an operating sprinkler

# internal diameter, in, by nominal size and schedule
ID_IN = {
    "40": {"1": 1.049, "1-1/4": 1.380, "1-1/2": 1.610, "2": 2.067, "2-1/2": 2.469, "3": 3.068, "4": 4.026,
           "6": 6.065, "8": 7.981},
    "10": {"1": 1.097, "1-1/4": 1.442, "1-1/2": 1.682, "2": 2.157, "2-1/2": 2.635, "3": 3.260, "4": 4.260,
           "6": 6.357, "8": 8.249},
}
# equivalent length, ft of pipe, for C = 120, by fitting and nominal size
EQUIV_FT = {
    "elbow": {"1": 2, "1-1/4": 3, "1-1/2": 4, "2": 5, "2-1/2": 6, "3": 7, "4": 10, "6": 14, "8": 18},
    "tee": {"1": 5, "1-1/4": 6, "1-1/2": 8, "2": 10, "2-1/2": 12, "3": 15, "4": 20, "6": 30, "8": 35},
    "gate valve": {"2": 1, "2-1/2": 1, "3": 1, "4": 2, "6": 3, "8": 4},
    "butterfly valve": {"2": 6, "2-1/2": 7, "3": 10, "4": 12, "6": 10, "8": 12},
    "check valve": {"2": 11, "2-1/2": 14, "3": 16, "4": 22, "6": 32, "8": 45},
}


def resistance(pipe, C, valve_factor=1.0):
    """psi per gpm^1.85 for one pipe: Hazen-Williams over its length plus its fittings' equivalent length, the
    equivalent lengths (tabled for C = 120) multiplied by (C/120)^1.85; a valve's equivalent length multiplied by
    `valve_factor` (1 for a valve fully open)."""
    d = ID_IN[pipe["schedule"]][pipe["size"]]
    le = 0.0
    for f in pipe.get("fittings", []):
        e = EQUIV_FT[f][pipe["size"]]
        le += e * (valve_factor if f.endswith("valve") and f != "check valve" else 1.0)
    l_eff = pipe["length_ft"] + le * (C / 120.0) ** HW_N
    return 4.52 * l_eff / (C ** HW_N * d ** 4.87)


class Network:
    """A pipe network with fixed-pressure nodes, fixed demands and emitters (q = K sqrt(p) to atmosphere),
    solved by the global gradient method on node heads expressed in psi (pressure plus 0.433 z)."""

    def __init__(self, system, C, valve_factor=None):
        self.sys = system
        self.ids = sorted(system["nodes"])
        self.ix = {n: i for i, n in enumerate(self.ids)}
        self.z = np.array([system["nodes"][n]["z"] for n in self.ids])
        vf = valve_factor or {}
        self.pipes = system["pipes"]
        self.a = np.array([self.ix[p["from"]] for p in self.pipes])
        self.b = np.array([self.ix[p["to"]] for p in self.pipes])
        self.r = np.array([resistance(p, C[p["group"]], vf.get(p["id"], 1.0)) for p in self.pipes])

    def solve(self, fixed, demand=None, emitters=None, q0=None, tol=1e-7, itmax=80):
        """fixed: {node: pressure psi}; demand: {node: gpm drawn}; emitters: {node: K}. Returns node pressures
        (dict), pipe flows (array, + from->to), emitter flows (dict) and every link's flow (for a warm start)."""
        n = len(self.ids)
        em = emitters or {}
        e_ix = np.array([self.ix[k] for k in em], int)
        e_k = np.array([em[k] for k in em], float)
        m_p = len(self.pipes)
        m = m_p + len(e_ix)
        rows = np.concatenate([np.arange(m_p), np.arange(m_p), m_p + np.arange(len(e_ix))])
        cols = np.concatenate([self.a, self.b, e_ix])
        vals = np.concatenate([np.ones(m_p), -np.ones(m_p), np.ones(len(e_ix))])
        B = sp.csr_matrix((vals, (rows, cols)), shape=(m, n))   # +1 at a link's start, -1 at its end
        c = np.concatenate([np.zeros(m_p), PSI_PER_FT * self.z[e_ix]])   # an emitter ends at atmosphere
        R = np.concatenate([self.r, 1.0 / e_k ** 2])
        NN = np.concatenate([np.full(m_p, HW_N), np.full(len(e_ix), 2.0)])
        dem = np.zeros(n)
        for k, v in (demand or {}).items():
            dem[self.ix[k]] += v
        fixed_ix = np.array([self.ix[k] for k in fixed], int)
        free = np.ones(n, bool)
        free[fixed_ix] = False
        H = PSI_PER_FT * self.z.copy()
        H[fixed_ix] = [fixed[k] + PSI_PER_FT * self.z[self.ix[k]] for k in fixed]
        Q = np.full(m, 5.0) if q0 is None or len(q0) != m else q0.copy()
        BT = B.T.tocsr()
        for _it in range(itmax):
            aq = np.maximum(np.abs(Q), 1e-4)
            hl = R * aq ** (NN - 1) * Q
            invD = 1.0 / (NN * R * aq ** (NN - 1))
            M = (BT @ sp.diags(invD) @ B).tocsr()
            rhs = -dem - BT @ (Q - invD * (hl + c))
            Mff = M[free][:, free]
            Mfx = M[free][:, ~free]
            H_old = H.copy()
            H[free] = spla.spsolve(Mff.tocsc(), rhs[free] - Mfx @ H[~free])
            Q_new = Q - invD * (hl + c) + invD * (B @ H)
            if len(e_ix):
                Q_new[m_p:] = np.maximum(Q_new[m_p:], 0.0)      # a sprinkler does not draw water in
            dq = np.max(np.abs(Q_new - Q))
            Q = Q_new
            if dq < tol * max(1.0, np.max(np.abs(Q))) and np.max(np.abs(H - H_old)) < 1e-6:
                break
        p = {k: float(H[i] - PSI_PER_FT * self.z[i]) for k, i in self.ix.items()}
        qe = {k: float(Q[m_p + j]) for j, k in enumerate(em)}
        return p, Q[:m_p].copy(), qe, Q


def _links(net, em):
    e_ix = np.array([net.ix[k] for k in em], int)
    e_k = np.array([em[k] for k in em], float)
    m_p = len(net.pipes)
    m = m_p + len(e_ix)
    n = len(net.ids)
    rows = np.concatenate([np.arange(m_p), np.arange(m_p), m_p + np.arange(len(e_ix))])
    cols = np.concatenate([net.a, net.b, e_ix])
    vals = np.concatenate([np.ones(m_p), -np.ones(m_p), np.ones(len(e_ix))])
    B = sp.csr_matrix((vals, (rows, cols)), shape=(m, n))
    c = np.concatenate([np.zeros(m_p), PSI_PER_FT * net.z[e_ix]])
    R = np.concatenate([net.r, 1.0 / e_k ** 2])
    NN = np.concatenate([np.full(m_p, HW_N), np.full(len(e_ix), 2.0)])
    return B, c, R, NN, m_p, m


def solve_critical(net, base, crit, p_crit, emitters, q0=None, itmax=60, tol=1e-9):
    """The network with the base of the riser as the only source, its pressure unknown, and the pressure at one
    head fixed: Newton on every node's head, continuity at every node but the base, plus that one condition."""
    B, c, R, NN, m_p, m = _links(net, emitters)
    n = len(net.ids)
    BT = B.T.tocsr()
    ib, ic = net.ix[base], net.ix[crit]
    keep = np.array([i for i in range(n) if i != ib])
    H = PSI_PER_FT * net.z.copy() + p_crit + 20.0
    Q = np.full(m, 5.0) if q0 is None or len(q0) != m else q0.copy()
    target = p_crit + PSI_PER_FT * net.z[ic]
    for _it in range(itmax):
        aq = np.maximum(np.abs(Q), 1e-4)
        hl = R * aq ** (NN - 1) * Q
        invD = 1.0 / (NN * R * aq ** (NN - 1))
        M = (BT @ sp.diags(invD) @ B).tocsr()
        rhs = -BT @ (Q - invD * (hl + c))
        A = sp.vstack([M[keep], sp.csr_matrix(([1.0], ([0], [ic])), shape=(1, n))]).tocsc()
        bvec = np.concatenate([rhs[keep], [target]])
        H_old = H
        H = spla.spsolve(A, bvec)
        Q_new = Q - invD * (hl + c) + invD * (B @ H)
        Q_new[m_p:] = np.maximum(Q_new[m_p:], 0.0)
        dq = np.max(np.abs(Q_new - Q))
        Q = Q_new
        if dq < 1e-7 * max(1.0, np.max(np.abs(Q))) and np.max(np.abs(H - H_old)) < tol * 1e3:
            break
    p = H - PSI_PER_FT * net.z
    return p, Q


def demand_fast(net, system, heads, q0=None):
    """demand_of by the constrained Newton: fix the head with the least margin at its requirement and solve for
    the base pressure; move to another head if one then falls short."""
    req, _q = area_requirements(system, heads)
    by_node = {h["node"]: h for h in system["heads"]}
    em = {n: by_node[n]["K"] for n in heads}
    crit = heads[-1]
    tried = set()
    for _round in range(len(heads)):
        tried.add(crit)
        p, Q = solve_critical(net, system["riser_base"], crit, req[crit], em, q0)
        margins = {h: p[net.ix[h]] - req[h] for h in heads}
        worst = min(margins, key=margins.get)
        if margins[worst] >= -1e-7 or worst in tried:
            break
        crit = worst
        q0 = Q
    m_p = len(net.pipes)
    return float(p[net.ix[system["riser_base"]]]), float(np.sum(Q[m_p:])), Q


def area_requirements(system, heads):
    """Each operating head's least pressure: 7 psi, or the pressure that gives it the design density over its
    coverage, whichever is higher."""
    hz = system["hazard"]
    q_min = hz["density_gpm_ft2"] * hz["spacing_branch_ft"] * hz["spacing_lines_ft"]
    by_node = {h["node"]: h for h in system["heads"]}
    return {n: max(P_MIN_HEAD, (q_min / by_node[n]["K"]) ** 2) for n in heads}, q_min


def demand_of(net, system, heads, guess=None):
    """The least pressure at the base of the riser at which every head of the area meets its requirement, and the
    heads' total flow there."""
    req, _q = area_requirements(system, heads)
    by_node = {h["node"]: h for h in system["heads"]}
    em = {n: by_node[n]["K"] for n in heads}
    base = system["riser_base"]
    q0 = [None]

    def margin(P0):
        p, _qp, qe, Qall = net.solve({base: P0}, emitters=em, q0=q0[0])
        q0[0] = Qall
        return min(p[n] - req[n] for n in heads), sum(qe.values())

    lo = guess or 30.0
    m_lo, _ = margin(lo)
    hi = lo
    while m_lo > 0:
        lo *= 0.7
        m_lo, _ = margin(lo)
    hi = lo * 1.5
    m_hi, _ = margin(hi)
    while m_hi < 0:
        lo, m_lo = hi, m_hi
        hi *= 1.5
        m_hi, _ = margin(hi)
    for _ in range(100):                                    # Illinois-modified regula falsi on the margin
        mid = hi - m_hi * (hi - lo) / (m_hi - m_lo)
        m_mid, qt = margin(mid)
        if abs(m_mid) < 1e-7:
            return mid, qt
        if (m_mid > 0) == (m_hi > 0):
            hi, m_hi = mid, m_mid
            m_lo *= 0.5
        else:
            lo, m_lo = mid, m_mid
            m_hi *= 0.5
        if abs(hi - lo) < 1e-7:
            break
    return mid, qt


def placements(system):
    """Every placement of the design area the standard allows (section 5): k adjacent branch lines, the same
    columns on each, m heads on each full line and the remainder on the window's highest-numbered line, at the
    window's lowest-numbered columns."""
    hz = system["hazard"]
    cover = hz["spacing_branch_ft"] * hz["spacing_lines_ft"]
    n_heads = math.ceil(hz["area_ft2"] / cover - 1e-9)
    m = math.ceil(1.2 * math.sqrt(hz["area_ft2"]) / hz["spacing_branch_ft"] - 1e-9)
    lines = sorted(system["lines"], key=lambda l: l["number"])
    width = min(len(l["heads"]) for l in lines)
    m = min(m, width)
    k = math.ceil(n_heads / m)
    rem = n_heads - m * (k - 1)
    out = []
    for j0 in range(0, len(lines) - k + 1):
        win = lines[j0:j0 + k]
        for c0 in range(0, width - m + 1):
            heads = []
            for t, ln in enumerate(win):
                cols = range(c0, c0 + (m if t < k - 1 else rem))
                heads += [ln["heads"][c] for c in cols]
            out.append(((win[0]["number"], c0 + 1), heads))
    return out


def design_demand(system, C, valve_factor=None, only=None):
    """The most demanding placement: its label, the pressure at the base of the riser and the flow there (the
    heads' flow plus the inside hose allowance)."""
    net = Network(system, C, valve_factor)
    best = None
    q0 = None
    for label, heads in (only or placements(system)):
        P, q, Qall = demand_fast(net, system, heads, q0)
        q0 = Qall
        if best is None or P > best[1]:
            best = (label, P, q)
    label, P, q = best
    return dict(area=list(label), pressure_psi=P, flow_gpm=q + system["hazard"]["hose_gpm"])


GAUGE_SD = 0.10                         # a digital test gauge's scatter, psi; it is read to 0.1 psi


def read(v, rng):
    return round(v + rng.gauss(0.0, GAUGE_SD), 1)


def supply_pressure(supply, Q):
    return supply["static_psi"] - (supply["static_psi"] - supply["residual_psi"]) * (Q / supply["flow_gpm"]) ** HW_N


def outlet_limit(system, truth, supply, outlet):
    """The most an outlet can pass: the flow at which the pressure the system gives it equals (Q/K)^2."""
    net = Network(system, truth["C"], truth["valves"])
    base = system["riser_base"]
    lo, hi = 1.0, 4000.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        pb = supply_pressure(supply, mid)
        ok = pb > 20.0
        if ok:
            p, _a, _b, _c = net.solve({base: pb}, demand={outlet["node"]: mid})
            ok = p[outlet["node"]] >= (mid / outlet["K"]) ** 2
        if ok:
            lo = mid
        else:
            hi = mid
    return lo


def campaign(system, truth, supply, plan, rng):
    """The true pressures of a campaign's runs, before any gauge is read. `plan` is a list of (outlet id or
    None, flow gpm); a run with no outlet is a static run. Returns one dict per run: outlet, flow, and the true
    pressure at the base of the riser and at every gauge port."""
    net = Network(system, truth["C"], truth["valves"])
    base = system["riser_base"]
    outs = {o["id"]: o for o in system["outlets"]}
    z = {n: system["nodes"][n]["z"] for n in system["nodes"]}
    ports = [base] + list(system["gauge_ports"])
    runs = []
    for outlet, Q in plan:
        drift = rng.uniform(-1.5, 1.5)                 # the supply's static moves a little through the day
        if outlet is None:
            pb = supply["static_psi"] + drift
            p = {n: pb - PSI_PER_FT * (z[n] - z[base]) for n in ports}
        else:
            pb = supply_pressure(supply, Q) + drift
            pall, _a, _b, _c = net.solve({base: pb}, demand={outs[outlet]["node"]: Q})
            p = {n: pall[n] for n in ports}
        runs.append({"outlet": outlet, "flow_gpm": Q, "p": p})
    return runs
