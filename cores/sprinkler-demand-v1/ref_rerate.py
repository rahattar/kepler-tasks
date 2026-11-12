"""Reference program for the core: the demand of an existing sprinkler system to FP-7, rated as its re-rating
campaign shows it to be.

    python3 ref_rerate.py PACKAGE_DIR OUT_JSON

Method:
1. The network: Hazen-Williams on every pipe, fittings by equivalent length scaled by (C/120)^1.85. A pipe's
   resistance is then linear in m = (120/C)^1.85 of its group and in the factor f of a valve on it, and those
   are the variables fitted.
2. The campaign: every reading is taken as  run level + gauge zero - elevation head - friction loss + scatter.
   A level for every run and a zero for every gauge are fitted with the pipe condition, so the residual is the
   doubly centred table of reading + head + loss. A gauge's zero error and the base gauge's scatter drop out.
3. The fit starts with the groups the register leaves open. If it is worse than the gauges' scatter allows, one
   more thing is let go at a time: a registered C, a valve's factor, two ports entered against each other, a
   run's flow. Candidates are ranked from one linearisation at the current fit (no new network solves for the
   port pairs and the flows), the best few are refitted in full, and the one that restores the fit is kept.
4. The demand is searched over every placement the standard allows, by Newton on every node's head with the
   base of the riser as the only source and the head with the least margin held at its requirement.
"""
import csv
import itertools
import json
import math
import os
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.optimize import least_squares, lsq_linear

HW_N = 1.85
PSI_FT = 0.433
P_HEAD_MIN = 7.0
SD = 0.105               # a gauge's scatter (0.1 psi) with its reading to 0.1 psi
GOOD = 1.6               # reduced chi-square below which a fit is as good as the gauges allow
C_LO, C_HI = 40.0, 150.0
F_HI = 5000.0

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
VALVES = ("gate valve", "butterfly valve")


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
        self.groups = sorted(pkg["groups"])
        self.gidx = np.array([self.groups.index(p["group"]) for p in P])
        d = np.array([ID_IN[p["schedule"]][p["size"]] for p in P])
        k = 4.52 / (120.0 ** HW_N * d ** 4.87)
        self.aL = k * np.array([p["length_ft"] for p in P])          # times m of the group
        self.b_fit = np.zeros(self.m)
        self.b_val = np.zeros(self.m)                                # times the valve's factor
        for i, p in enumerate(P):
            for f in p["fittings"]:
                e = EQUIV_FT[f][p["size"]] * k[i]
                if f in VALVES:
                    self.b_val[i] += e
                else:
                    self.b_fit[i] += e
        self.valve_pipes = [i for i in range(self.m) if self.b_val[i] > 0]
        self.pipe_id = [p["id"] for p in P]
        rows = np.concatenate([np.arange(self.m), np.arange(self.m)])
        cols = np.concatenate([self.a, self.b])
        vals = np.concatenate([np.ones(self.m), -np.ones(self.m)])
        self.Bp = sp.csr_matrix((vals, (rows, cols)), shape=(self.m, self.n))
        self.BpT = self.Bp.T.tocsr()
        self.free = np.ones(self.n, bool)
        self.free[self.base] = False
        self.heads = {h["node"]: h for h in pkg["heads"]}
        hz = pkg["hazard"]
        self.q_min = hz["density_gpm_ft2"] * hz["spacing_branch_ft"] * hz["spacing_lines_ft"]
        reg = [pkg["groups"][g]["C"] for g in self.groups]
        self.m_reg = np.array([(120.0 / c) ** HW_N if c is not None else 1.0 for c in reg])
        self.open_groups = [i for i, c in enumerate(reg) if c is None]

    def resist(self, mg, vf):
        """Each pipe's resistance for the groups' m and the pipes' valve factors (an array over pipes)."""
        return self.aL * mg[self.gidx] + self.b_fit + self.b_val * vf

    # ---------------------------------------------------------------------------------------------- solvers
    def test_drops(self, r, node, Q_out, q0=None):
        """A test run: water drawn at one node, every sprinkler shut. The fall in head (psi) from the base of the
        riser to every node, and the pipe flows."""
        B, BT, free = self.Bp, self.BpT, self.free
        dem = np.zeros(self.n)
        dem[node] = Q_out
        H = np.zeros(self.n)
        Q = np.full(self.m, Q_out / 10.0) if q0 is None else q0.copy()
        for _ in range(60):
            aq = np.maximum(np.abs(Q), 1e-4)
            hl = r * aq ** (HW_N - 1) * Q
            invD = 1.0 / (HW_N * r * aq ** (HW_N - 1))
            M = (BT @ sp.diags(invD) @ B).tocsr()
            rhs = -dem - BT @ (Q - invD * hl)
            H_old = H.copy()
            H[free] = spla.spsolve(M[free][:, free].tocsc(), rhs[free])
            Q_new = Q - invD * hl + invD * (B @ H)
            dq = np.max(np.abs(Q_new - Q))
            Q = Q_new
            if dq < 1e-9 * max(1.0, Q_out) and np.max(np.abs(H - H_old)) < 1e-8:
                break
        return -H, Q

    def _links(self, em_nodes, em_K, r):
        k = len(em_nodes)
        Be = sp.csr_matrix((np.ones(k), (np.arange(k), em_nodes)), shape=(k, self.n))
        B = sp.vstack([self.Bp, Be]).tocsr()
        c = np.concatenate([np.zeros(self.m), PSI_FT * self.z[em_nodes]])
        R = np.concatenate([r, 1.0 / em_K ** 2])
        NN = np.concatenate([np.full(self.m, HW_N), np.full(k, 2.0)])
        return B, c, R, NN

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

    def search(self, r):
        """The most demanding placement: (label, base pressure, heads' flow)."""
        best = None
        q0 = None
        for label, hs in self.placements():
            P, q, q0 = self.area_demand(r, hs, q0)
            if best is None or P > best[1]:
                best = (label, P, q)
        return best


class Campaign:
    """The campaign's table of readings and the fit of the system's condition to it."""

    def __init__(self, S, rows):
        self.S = S
        pkg = S.pkg
        self.g = [pkg["riser_base"]] + list(pkg["gauge_ports"])
        self.gi = np.array([S.ix[n] for n in self.g])
        runs = {}
        for row in rows:
            r = runs.setdefault(int(row["run"]), {"outlet": row["outlet"] or None,
                                                  "flow": float(row["flow_gpm"]), "read": {}})
            r["read"][row["port"]] = float(row["reading_psi"])
        self.runs = [runs[k] for k in sorted(runs)]
        self.Y = np.array([[r["read"][n] for n in self.g] for r in self.runs])
        self.h = PSI_FT * (S.z[self.gi] - S.z[S.base])
        outs = {o["id"]: S.ix[o["node"]] for o in pkg["outlets"]}
        self.flowing = [(k, outs[r["outlet"]], r["flow"]) for k, r in enumerate(self.runs)
                        if r["outlet"] is not None and r["flow"] > 0]
        self.q0 = {}
        self.nsolve = 0
        self.var = [("C", i) for i in S.open_groups]         # what is fitted: ("C", group) or ("valve", pipe)
        self.swap = None                                     # two gauge columns entered against each other
        self.flow_run = None                                 # a run whose flow is fitted
        self.x = None

    # -- variables: x holds m for a group, f for a valve, and last (if any) the fitted run's flow factor^1.85
    def bounds(self, var, flow):
        lo = [(120.0 / C_HI) ** HW_N if k == "C" else 1.0 for k, _i in var] + ([0.3 ** HW_N] if flow else [])
        hi = [(120.0 / C_LO) ** HW_N if k == "C" else F_HI for k, _i in var] + ([3.0 ** HW_N] if flow else [])
        return np.array(lo), np.array(hi)

    def start(self, var, flow):
        S = self.S
        cur = dict(zip(self.var, self.x)) if self.x is not None else {}
        x = [cur.get(v, S.m_reg[v[1]] if v[0] == "C" else 1.0) for v in var]
        return np.array(x + ([1.0] if flow else []))

    def condition(self, var, x):
        S = self.S
        mg = S.m_reg.copy()
        vf = np.ones(S.m)
        for (k, i), v in zip(var, x):
            if k == "C":
                mg[i] = v
            else:
                vf[i] = v
        return mg, vf

    def drops(self, var, x):
        """Fall in head from the base to every gauge, each run at its recorded flow (zero for static runs)."""
        mg, vf = self.condition(var, x)
        r = self.S.resist(mg, vf)
        L = np.zeros(self.Y.shape)
        for k, node, q in self.flowing:
            d, Q = self.S.test_drops(r, node, q, self.q0.get(k))
            self.nsolve += 1
            self.q0[k] = Q
            L[k] = d[self.gi]
        return L

    @staticmethod
    def centre(E):
        return E - E.mean(axis=1, keepdims=True) - E.mean(axis=0, keepdims=True) + E.mean()

    def table(self, swap):
        Y = self.Y
        if swap:
            Y = Y.copy()
            Y[:, [swap[0], swap[1]]] = Y[:, [swap[1], swap[0]]]
        return Y + self.h[None, :]

    def dof(self, nx):
        R, G = self.Y.shape
        return R * G - R - G + 1 - nx

    def fit(self, var, swap, flow_run):
        """Least squares on the doubly centred table. Returns (x, reduced chi-square)."""
        T = self.table(swap)
        nv = len(var)

        def resid(x):
            L = self.drops(var, x[:nv])
            if flow_run is not None:
                L[flow_run] *= x[-1]
            return self.centre(T + L).ravel() / SD

        x0 = self.start(var, flow_run is not None)
        if len(x0) == 0:
            r = resid(x0)
            return x0, float(r @ r) / self.dof(0)
        lo, hi = self.bounds(var, flow_run is not None)
        x0 = np.clip(x0, lo + 1e-9, hi - 1e-9)
        sol = least_squares(resid, x0, bounds=(lo, hi), x_scale="jac", diff_step=1e-4, xtol=1e-9, ftol=1e-9,
                            max_nfev=40)
        return sol.x, float(sol.fun @ sol.fun) / self.dof(len(x0))

    # -- one linearisation at the current fit ranks every candidate
    def rank(self):
        S = self.S
        var, x = self.var, self.x
        nv = len(var)
        T = self.table(self.swap)
        L = self.drops(var, x[:nv])
        Lf = L.copy()
        if self.flow_run is not None:
            Lf[self.flow_run] *= x[-1]
        e0 = self.centre(T + Lf).ravel()
        lo, hi = self.bounds(var, self.flow_run is not None)

        def column(v, at, step):
            """d(centred loss table)/d(variable), by a forward difference."""
            xs = np.concatenate([x[:nv], [at + step]])
            Lp = self.drops(var + [v], xs)
            if self.flow_run is not None:
                Lp[self.flow_run] *= x[-1]
            return self.centre(Lp - Lf).ravel() / step

        cols, blo, bhi = [], [], []
        for j, v in enumerate(var):
            step = 0.02 * x[j] if v[0] == "C" else max(0.05 * x[j], 0.5)
            xs = x[:nv].copy()
            xs[j] += step
            Lp = self.drops(var, xs)
            if self.flow_run is not None:
                Lp[self.flow_run] *= x[-1]
            cols.append(self.centre(Lp - Lf).ravel() / step)
            blo.append(lo[j] - x[j])
            bhi.append(hi[j] - x[j])
        if self.flow_run is not None:
            row = np.zeros(L.shape)
            row[self.flow_run] = L[self.flow_run]
            cols.append(self.centre(row).ravel())
            blo.append(lo[-1] - x[-1])
            bhi.append(hi[-1] - x[-1])
        J0 = np.array(cols).T if cols else np.zeros((len(e0), 0))

        def predicted(e, extra=None, elo=0.0, ehi=0.0):
            A = J0 if extra is None else np.column_stack([J0, extra])
            if A.shape[1] == 0:
                return float(e @ e)
            b_lo = np.array(blo + ([elo] if extra is not None else []))
            b_hi = np.array(bhi + ([ehi] if extra is not None else []))
            sol = lsq_linear(A, -e, bounds=(np.minimum(b_lo, -1e-12), np.maximum(b_hi, 1e-12)))
            rr = e + A @ sol.x
            return float(rr @ rr)

        out = []
        have = set(var)
        for i in range(len(S.groups)):
            v = ("C", i)
            if v in have:
                continue
            at = S.m_reg[i]
            c = column(v, at, 0.05 * at)
            out.append((predicted(e0, c, (120.0 / C_HI) ** HW_N - at, (120.0 / C_LO) ** HW_N - at), v))
        for i in S.valve_pipes:
            v = ("valve", i)
            if v in have:
                continue
            c = column(v, 1.0, 20.0)
            out.append((predicted(e0, c, 0.0, F_HI - 1.0), v))
        if self.swap is None:
            for i, j in itertools.combinations(range(1, len(self.g)), 2):
                e = self.centre(self.table((i, j)) + Lf).ravel()
                out.append((predicted(e), ("swap", (i, j))))
        if self.flow_run is None:
            for k, _node, _q in self.flowing:
                row = np.zeros(L.shape)
                row[k] = L[k]
                out.append((predicted(e0, self.centre(row).ravel(), 0.3 ** HW_N - 1.0, 3.0 ** HW_N - 1.0),
                            ("flow", k)))
        out.sort(key=lambda t: t[0])
        return out

    def settle(self, top=3, depth=3):
        """Fit as recorded; while the fit is poor, let go the one more thing that best restores it."""
        self.x, chi = self.fit(self.var, self.swap, self.flow_run)
        log("as recorded: chi %.2f (%d solves)" % (chi, self.nsolve))
        found = []
        while chi > GOOD and len(found) < depth:
            ranked = self.rank()
            log("  ranked: " + "; ".join("%s %s %.0f" % (v[0], v[1], c / SD ** 2 / self.dof(len(self.x) + 1))
                                         for c, v in ranked[:5]))
            best = None
            for _c, v in ranked[:top]:
                var = self.var + [v] if v[0] in ("C", "valve") else list(self.var)
                swap = v[1] if v[0] == "swap" else self.swap
                flow = v[1] if v[0] == "flow" else self.flow_run
                x, c2 = self.fit(var, swap, flow)
                if best is None or c2 < best[0]:
                    best = (c2, v, var, swap, flow, x)
            if best is None or best[0] > 0.9 * chi:
                break
            chi, v, self.var, self.swap, self.flow_run, self.x = best
            found.append(v)
            log("  let go %s %s: chi %.2f (%d solves)" % (v[0], v[1], chi, self.nsolve))
        return found, chi


def main(pkg_dir, out_path):
    with open(os.path.join(pkg_dir, "system.json")) as f:
        pkg = json.load(f)
    with open(os.path.join(pkg_dir, "campaign.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    S = System(pkg)
    camp = Campaign(S, rows)
    found, chi = camp.settle()
    nv = len(camp.var)
    mg, vf = camp.condition(camp.var, camp.x[:nv])
    label, P, q = S.search(S.resist(mg, vf))
    names = []
    for k, v in found:
        if k == "C":
            names.append("registered C of %s" % S.groups[v])
        elif k == "valve":
            names.append("valve on %s" % S.pipe_id[v])
        elif k == "swap":
            names.append("ports %s and %s entered against each other" % (camp.g[v[0]], camp.g[v[1]]))
        else:
            names.append("flow of run %d" % (v + 1))
    res = {"area": list(label), "pressure_psi": round(P, 3), "flow_gpm": round(q + pkg["hazard"]["hose_gpm"], 2),
           "fit_chi2": round(chi, 2), "let_go": names,
           "condition": {"C": {g: round(120.0 / mg[i] ** (1 / HW_N), 1) for i, g in enumerate(S.groups)},
                         "valves": {S.pipe_id[i]: round(float(vf[i]), 1) for i in S.valve_pipes}}}
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1)
    log(json.dumps(res))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
