"""Reference program for the core: the demand of an existing sprinkler system to FP-7, with one field test.

    python3 ref_demand.py PACKAGE_DIR OUT_JSON

It speaks the field-test protocol on stdout and stdin (core/data/docs/field_test_protocol.md): one line
`TEST {json}` out, one JSON line back, then the result is written to OUT_JSON.

Method:
1. The network: Hazen-Williams on every pipe, fittings by equivalent length scaled by (C/120)^1.85, open heads as
   emitters q = K sqrt(p). A design area's demand is found by Newton on every node's head with the base of the
   riser as the only source, its pressure unknown, and the head with the least margin held at its requirement.
2. The unknowns: each group whose C the package leaves open, and each valve not verified open, as a factor on
   its equivalent length.
3. The test is designed before it is spent: for every outlet, a range of flows each outlet can pass even if the
   unknowns are at their worst, and every pair of gauge ports, the readings' sensitivity to the unknowns is worked
   out; the test chosen is the one that leaves the demand's variance least, at the worst of a few prior points.
4. The unknowns are fitted to the two gauges' flowing readings (each relative to the base-of-riser reading), and
   the demand is searched over every placement the standard allows.
"""
import json
import math
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

HW_N = 1.85
PSI_FT = 0.433
P_HEAD_MIN = 7.0
P_RISER_MIN = 20.0
GAUGE_SD = 0.11          # a digital test gauge's scatter read to 0.1 psi, psi (protocol document)

ID_IN = {
    "40": {"1": 1.049, "1-1/4": 1.380, "1-1/2": 1.610, "2": 2.067, "2-1/2": 2.469, "3": 3.068, "4": 4.026,
           "6": 6.065, "8": 7.981},
    "10": {"1": 1.097, "1-1/4": 1.442, "1-1/2": 1.682, "2": 2.157, "2-1/2": 2.635, "3": 3.260, "4": 4.260,
           "6": 6.357, "8": 8.249},
}
EQUIV_FT = {
    "elbow": {"1": 2, "1-1/4": 3, "1-1/2": 4, "2": 5, "2-1/2": 6, "3": 7, "4": 10, "6": 14, "8": 18},
    "tee": {"1": 5, "1-1/4": 6, "1-1/2": 8, "2": 10, "2-1/2": 12, "3": 15, "4": 20, "6": 30, "8": 35},
    "gate valve": {"2": 1, "2-1/2": 1, "3": 1, "4": 2, "6": 3, "8": 4},
    "butterfly valve": {"2": 6, "2-1/2": 7, "3": 10, "4": 12, "6": 10, "8": 12},
    "check valve": {"2": 11, "2-1/2": 14, "3": 16, "4": 22, "6": 32, "8": 45},
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


class System:
    def __init__(self, pkg):
        self.pkg = pkg
        self.ids = sorted(pkg["nodes"])
        self.ix = {n: i for i, n in enumerate(self.ids)}
        self.n = len(self.ids)
        self.z = np.array([pkg["nodes"][k]["z"] for k in self.ids])
        P = pkg["pipes"]
        self.m = len(P)
        self.a = np.array([self.ix[p["from"]] for p in P])
        self.b = np.array([self.ix[p["to"]] for p in P])
        self.base = self.ix[pkg["riser_base"]]
        self.unknown = [("C", g) for g in sorted(pkg["groups"]) if pkg["groups"][g]["C"] is None]
        self.unknown += [("valve", v["pipe"]) for v in pkg["valves_unverified"]]
        self.pipe_ix = {p["id"]: i for i, p in enumerate(P)}
        # per pipe: diameter, length, equivalent length (C = 120) of fittings other than unverified valves, and of
        # those valves
        self.d = np.array([ID_IN[p["schedule"]][p["size"]] for p in P])
        self.L = np.array([p["length_ft"] for p in P])
        unv = {(v["pipe"], v["fitting"]) for v in pkg["valves_unverified"]}
        self.le_fixed = np.zeros(self.m)
        self.le_valve = np.zeros(self.m)
        for i, p in enumerate(P):
            for f in p["fittings"]:
                e = EQUIV_FT[f][p["size"]]
                if (p["id"], f) in unv:
                    self.le_valve[i] += e
                else:
                    self.le_fixed[i] += e
        self.group = [p["group"] for p in P]
        rows = np.concatenate([np.arange(self.m), np.arange(self.m)])
        cols = np.concatenate([self.a, self.b])
        vals = np.concatenate([np.ones(self.m), -np.ones(self.m)])
        self.Bp = sp.csr_matrix((vals, (rows, cols)), shape=(self.m, self.n))
        self.heads = {h["node"]: h for h in pkg["heads"]}
        hz = pkg["hazard"]
        self.q_min = hz["density_gpm_ft2"] * hz["spacing_branch_ft"] * hz["spacing_lines_ft"]

    def resist(self, theta):
        """Each pipe's resistance for given values of the unknowns."""
        C = np.array([self.pkg["groups"][g]["C"] or 0.0 for g in self.group], float)
        vf = np.ones(self.m)
        for (kind, key), v in zip(self.unknown, theta):
            if kind == "C":
                C[[i for i, g in enumerate(self.group) if g == key]] = v
            else:
                vf[self.pipe_ix[key]] = v
        le = self.le_fixed + self.le_valve * vf
        return 4.52 * (self.L + le * (C / 120.0) ** HW_N) / (C ** HW_N * self.d ** 4.87)

    # ---------------------------------------------------------------------------------------------- solvers
    def _links(self, em_nodes, em_K, r):
        k = len(em_nodes)
        Be = sp.csr_matrix((np.ones(k), (np.arange(k), em_nodes)), shape=(k, self.n))
        B = sp.vstack([self.Bp, Be]).tocsr()
        c = np.concatenate([np.zeros(self.m), PSI_FT * self.z[em_nodes]])
        R = np.concatenate([r, 1.0 / em_K ** 2])
        NN = np.concatenate([np.full(self.m, HW_N), np.full(k, 2.0)])
        return B, c, R, NN

    def solve_fixed_base(self, r, p_base, demand_node, Q_out, q0=None):
        """The test: the base at a given pressure, water drawn at one node. Node pressures."""
        B = self.Bp
        BT = B.T.tocsr()
        dem = np.zeros(self.n)
        dem[self.ix[demand_node]] = Q_out
        free = np.ones(self.n, bool)
        free[self.base] = False
        H = PSI_FT * self.z + p_base
        H[self.base] = p_base + PSI_FT * self.z[self.base]
        Q = np.full(self.m, Q_out / 10.0) if q0 is None else q0.copy()
        for _ in range(60):
            aq = np.maximum(np.abs(Q), 1e-4)
            hl = r * aq ** (HW_N - 1) * Q
            invD = 1.0 / (HW_N * r * aq ** (HW_N - 1))
            M = (BT @ sp.diags(invD) @ B).tocsr()
            rhs = -dem - BT @ (Q - invD * hl)
            Mf = M[free]
            H_old = H.copy()
            H[free] = spla.spsolve(Mf[:, free].tocsc(), rhs[free] - Mf[:, ~free] @ H[~free])
            Q_new = Q - invD * hl + invD * (B @ H)
            dq = np.max(np.abs(Q_new - Q))
            Q = Q_new
            if dq < 1e-8 * max(1.0, Q_out) and np.max(np.abs(H - H_old)) < 1e-7:
                break
        return H - PSI_FT * self.z, Q

    def area_demand(self, r, heads, q0=None):
        """Least base pressure at which every head of the area meets its requirement; the heads' flow there."""
        en = np.array([self.ix[h] for h in heads])
        eK = np.array([self.heads[h]["K"] for h in heads], float)
        req = np.maximum(P_HEAD_MIN, (self.q_min / eK) ** 2)
        B, c, R, NN = self._links(en, eK, r)
        BT = B.T.tocsr()
        keep = np.array([i for i in range(self.n) if i != self.base])
        nl = self.m + len(en)
        Q = np.full(nl, 5.0) if q0 is None or len(q0) != nl else q0.copy()
        crit = len(heads) - 1
        tried = set()
        while True:
            tried.add(crit)
            target = req[crit] + PSI_FT * self.z[en[crit]]
            H = None
            for _ in range(60):
                aq = np.maximum(np.abs(Q), 1e-4)
                hl = R * aq ** (NN - 1) * Q
                invD = 1.0 / (NN * R * aq ** (NN - 1))
                M = (BT @ sp.diags(invD) @ B).tocsr()
                rhs = -BT @ (Q - invD * (hl + c))
                A = sp.vstack([M[keep], sp.csr_matrix(([1.0], ([0], [en[crit]])), shape=(1, self.n))]).tocsc()
                H_old = H
                H = spla.spsolve(A, np.concatenate([rhs[keep], [target]]))
                Qn = Q - invD * (hl + c) + invD * (B @ H)
                Qn[self.m:] = np.maximum(Qn[self.m:], 0.0)
                dq = np.max(np.abs(Qn - Q))
                Q = Qn
                if H_old is not None and dq < 1e-7 * max(1.0, np.max(np.abs(Q))) and \
                        np.max(np.abs(H - H_old)) < 1e-6:
                    break
            p = H - PSI_FT * self.z
            marg = p[en] - req
            w = int(np.argmin(marg))
            if marg[w] >= -1e-7 or w in tried:
                break
            crit = w
        return float(p[self.base]), float(np.sum(Q[self.m:])), Q

    def placements(self):
        hz = self.pkg["hazard"]
        cover = hz["spacing_branch_ft"] * hz["spacing_lines_ft"]
        n_heads = math.ceil(hz["area_ft2"] / cover - 1e-9)
        lines = sorted(self.pkg["lines"], key=lambda l: l["number"])
        width = min(len(l["heads"]) for l in lines)
        m = min(math.ceil(1.2 * math.sqrt(hz["area_ft2"]) / hz["spacing_branch_ft"] - 1e-9), width)
        k = math.ceil(n_heads / m)
        rem = n_heads - m * (k - 1)
        out = []
        for j0 in range(len(lines) - k + 1):
            win = lines[j0:j0 + k]
            for c0 in range(width - m + 1):
                hs = []
                for t, ln in enumerate(win):
                    hs += ln["heads"][c0:c0 + (m if t < k - 1 else rem)]
                out.append(((win[0]["number"], c0 + 1), hs))
        return out

    def search(self, r, stride=1):
        """The most demanding placement: (label, base pressure, heads' flow, heads)."""
        best = None
        q0 = None
        pl = self.placements()
        if stride > 1:
            pl = [x for x in pl if (x[0][0] % stride == 0 or x[0][1] % stride == 0)]
        for label, hs in pl:
            P, q, q0 = self.area_demand(r, hs, q0)
            if best is None or P > best[1]:
                best = (label, P, q, hs)
        return best


def supply_at(pkg, Q):
    s = pkg["supply"]
    return s["static_psi"] - (s["static_psi"] - s["residual_psi"]) * (Q / s["flow_gpm"]) ** HW_N


def to_theta(sysm, x):
    """Search coordinates (log scale) to the unknowns' values."""
    return np.exp(x)


def file_misfit(pkg, opened):
    """The tests on file against the package with the groups in `opened` left open as well: the open values
    (as they were at those tests) fitted, the sum of squared residuals over the gauges' variance, and its
    degrees of freedom."""
    import copy
    from scipy.optimize import least_squares
    p2 = copy.deepcopy(pkg)
    for g in opened:
        p2["groups"][g]["C"] = None
    S = System(p2)
    nodes = {o["id"]: o["node"] for o in pkg["outlets"]}
    tests = pkg.get("tests_on_file", [])
    y = np.array([t["gauges"][g]["flowing_psi"] - t["base_of_riser"]["flowing_psi"]
                  for t in tests for g in sorted(t["gauges"])])
    k = len(S.unknown)
    lo = np.array([55.0 if kind == "C" else 1.0 for kind, _ in S.unknown])
    hi = np.array([125.0 if kind == "C" else 1000.0 for kind, _ in S.unknown])

    def resid(x):
        r = S.resist(np.exp(x))
        out = []
        for t in tests:
            pb = t["base_of_riser"]["flowing_psi"]
            p, _ = S.solve_fixed_base(r, pb, nodes[t["outlet"]], t["flow_gpm"])
            out += [p[S.ix[g]] - pb for g in sorted(t["gauges"])]
        return (np.array(out) - y) / (GAUGE_SD * math.sqrt(2.0))

    if k == 0:
        return float(np.sum(resid(np.zeros(0)) ** 2)), len(y)
    x0 = np.log(np.where([kind == "C" for kind, _ in S.unknown], 100.0, 1.5))
    fit = least_squares(resid, x0, bounds=(np.log(lo), np.log(hi)), diff_step=1e-3)
    return float(2 * fit.cost), len(y) - k


def aged_groups(pkg):
    """Groups the register carries a C for which the flow tests on file do not bear out. A registered C is the
    pipe as entered; the tests on file are the pipe as it was found later. Where the tests cannot be reproduced
    with the registered figures, the one registered group whose release reproduces them has aged, and its C today
    is open like any other pipe whose condition the records do not settle."""
    if not pkg.get("tests_on_file"):
        return []
    chi, dof = file_misfit(pkg, [])
    log("tests on file against the register: chi2 %.1f on %d" % (chi, dof))
    if chi < 25.0 + 3.0 * dof:
        return []
    cands = [g for g in sorted(pkg["groups"]) if pkg["groups"][g]["C"] is not None]
    scored = sorted((file_misfit(pkg, [g])[0], g) for g in cands)
    log("released one at a time:", [(g, round(c, 1)) for c, g in scored])
    best_chi, best = scored[0]
    return [best] if best_chi < 0.2 * chi else []


def main(argv):
    pkg_dir, out_path = argv[1], argv[2]
    with open(pkg_dir.rstrip("/") + "/system.json") as f:
        pkg = json.load(f)
    for g in aged_groups(pkg):
        log("registered C not borne out by the tests on file:", g)
        pkg["groups"][g]["C"] = None
    S = System(pkg)
    k = len(S.unknown)
    log("unknowns:", S.unknown)
    # prior: aged pipe between C 55 and 120, a valve not verified open between fully open and 1000 times its
    # equivalent length
    lo = np.array([55.0 if kind == "C" else 1.0 for kind, _ in S.unknown])
    hi = np.array([120.0 if kind == "C" else 1000.0 for kind, _ in S.unknown])
    mid = np.sqrt(lo * hi)
    theta_hat = mid.copy()
    if k:
        # where the demand is likely decided: a coarse search at the prior's middle
        r_mid = S.resist(mid)
        label, P0, q0, hs = S.search(r_mid, stride=3)
        log("prior middle: placement", label, "P %.1f" % P0)

        def dem(th):
            return S.area_demand(S.resist(th), hs)[0]

        def sens(th):
            base = dem(th)
            g = np.zeros(k)
            for i in range(k):
                t2 = th.copy()
                t2[i] *= 1.02
                g[i] = (dem(t2) - base) / (math.log(1.02))
            return g                                          # dP / d ln(theta)

        points = [mid, lo * 0 + np.sqrt(lo * mid), np.sqrt(hi * mid)]
        s_pts = [sens(th) for th in points]
        best = None
        for o in pkg["outlets"]:
            # the flow the outlet passes with the unknowns at their worst, and well inside it
            worst = np.where([kind == "C" for kind, _ in S.unknown], lo, hi)
            r_w = S.resist(worst)
            qmax = None
            for Q in np.geomspace(20, 1500, 40):
                pb = supply_at(pkg, Q)
                if pb < P_RISER_MIN + 5:
                    break
                p, _ = S.solve_fixed_base(r_w, pb, o["node"], Q)
                if p[S.ix[o["node"]]] < 1.15 * (Q / o["K"]) ** 2:
                    break
                qmax = Q
            if qmax is None:
                continue
            for Q in [qmax, 0.8 * qmax, 0.6 * qmax]:
                pb = supply_at(pkg, Q)
                J_pts = []
                for th in points:
                    p0, _ = S.solve_fixed_base(S.resist(th), pb, o["node"], Q)
                    J = np.zeros((len(pkg["gauge_ports"]), k))
                    for i in range(k):
                        t2 = th.copy()
                        t2[i] *= 1.02
                        p2, _ = S.solve_fixed_base(S.resist(t2), pb, o["node"], Q)
                        J[:, i] = [(p2[S.ix[g]] - p0[S.ix[g]]) / math.log(1.02) for g in pkg["gauge_ports"]]
                    J_pts.append(J)
                G = pkg["gauge_ports"]
                for a in range(len(G)):
                    for b in range(a + 1, len(G)):
                        worst_var = 0.0
                        for J, s in zip(J_pts, s_pts):
                            Jr = J[[a, b]]
                            cov_y = GAUGE_SD ** 2 * np.array([[2.0, 1.0], [1.0, 2.0]])   # each relative to base
                            F = Jr.T @ np.linalg.solve(cov_y, Jr)
                            try:
                                cov_t = np.linalg.inv(F + 1e-9 * np.eye(k))
                            except np.linalg.LinAlgError:
                                cov_t = np.eye(k) * 1e6
                            worst_var = max(worst_var, float(s @ cov_t @ s))
                        if best is None or worst_var < best[0]:
                            best = (worst_var, o["id"], float(Q), [G[a], G[b]], o["node"])
        var, oid, Q, gauges, onode = best
        Q = round(Q, 0)
        log("test: %s at %.0f gpm, gauges %s; expected sd of the demand %.2f psi" % (oid, Q, gauges, math.sqrt(var)))
        print("TEST " + json.dumps({"outlet": oid, "flow_gpm": Q, "gauges": gauges}), flush=True)
        rep = json.loads(sys.stdin.readline())
        log("report:", rep)
        if "refused" not in rep:
            pb = rep["base_of_riser"]["flowing_psi"]
            y = np.array([rep["gauges"][g]["flowing_psi"] - pb for g in gauges])

            def resid(x):
                th = np.exp(x)
                p, _ = S.solve_fixed_base(S.resist(th), pb, onode, rep["flow_gpm"])
                return np.array([p[S.ix[g]] - pb for g in gauges]) - y

            from scipy.optimize import least_squares
            fit = least_squares(resid, np.log(mid), bounds=(np.log(lo * 0.7), np.log(hi * 1.5)),
                                x_scale=1.0, diff_step=1e-3)
            theta_hat = np.exp(fit.x)
            log("fitted:", dict(zip([u[1] for u in S.unknown], np.round(theta_hat, 2))), "cost", fit.cost)
    r = S.resist(theta_hat)
    label, P, q, _hs = S.search(r)
    res = {"area": list(label), "pressure_psi": round(P, 3), "flow_gpm": round(q + pkg["hazard"]["hose_gpm"], 2),
           "unknowns": {"%s:%s" % u: round(float(v), 3) for u, v in zip(S.unknown, theta_hat)}}
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1)
    log("result:", res)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
