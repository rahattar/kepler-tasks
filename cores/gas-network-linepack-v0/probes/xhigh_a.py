#!/usr/bin/env python3
"""Design-day governor inlet pressures to GD-3 for one network package.

    python3 designday.py PACKAGE_DIR OUT_CSV

1. Every main takes K from its latest survey made after its last renewal,
   relining or laying (GD-3 s.2).
2. The campaigns on file are checked node by node: the flows into a node must
   balance within the survey accuracy.  At a boundary valve node an imbalance
   means the valve passes gas whatever the register says (GD-3 s.6); at a
   customer node the balance against the meter at 13:00 on the campaign day
   shows a meter outside its 1 per cent.
3. One order goes to the field team (gdsurvey), within the allowance: open
   valves and mains no survey measured as they stand, then the valves and meters
   the campaigns call into question, then whatever else is doubtful.  Where an
   item cannot be had, it is estimated from the campaigns (valves, meters) or
   from the size and bore of the main.
4. The design day, 240 implicit steps of 0.1 h from 06:00 with linepack and the
   PRS limits (GD-3 s.3-8), is repeated until it closes on itself, and the lowest
   pressure at each governor is written.
"""
import sys
import os
import json
import math
import subprocess
import time

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu

P0 = 1.01325          # bar, standard / atmospheric
EXPO = 0.82           # p1^2 - p2^2 = K Q |Q|^0.82
NSTEP = 240
DT = 0.1              # h
KCHANGE = {"RENEWED", "RELINED", "LAID"}
PIMIN = 1e-6         # floor on squared absolute pressure (numerical guard only)


def log(*a):
    print(*a, file=sys.stderr)


# --------------------------------------------------------------------------
# package
# --------------------------------------------------------------------------
def read_csv(pkg, name):
    return pd.read_csv(os.path.join(pkg, name), dtype=str, skipinitialspace=True)


def survey_k(pf_barg, dp, q):
    pf = pf_barg + P0
    pt = pf - dp
    den = q * abs(q) ** EXPO
    if not np.isfinite(den) or den == 0.0:
        return float("nan")
    k = (pf * pf - pt * pt) / den
    return k if (np.isfinite(k) and k > 0) else float("nan")


class Package:
    def __init__(self, pkg):
        self.pkg = pkg
        try:
            with open(os.path.join(pkg, "network.json")) as f:
                meta = json.load(f)
        except Exception:
            meta = {}
        self.name = meta.get("network", os.path.basename(os.path.normpath(pkg)))
        try:
            self.allowance = int(meta.get("survey_allowance", 0))
        except Exception:
            self.allowance = 0

        m = read_csv(pkg, "mains.csv")
        m = m.dropna(subset=["main"]).drop_duplicates("main", keep="last")
        self.mains = m["main"].str.strip().tolist()
        self.mfrom = m["from_node"].str.strip().tolist()
        self.mto = m["to_node"].str.strip().tolist()
        self.mlen = m["length_m"].astype(float).to_numpy()
        self.mdia = m["diameter_mm"].astype(float).to_numpy()
        self.mmat = m["material"].fillna("").str.strip().tolist() if "material" in m else [""] * len(m)
        nodes = []
        seen = set()
        for a, b in zip(self.mfrom, self.mto):
            for x in (a, b):
                if x not in seen:
                    seen.add(x)
                    nodes.append(x)
        self.nodes = nodes
        self.nidx = {n: i for i, n in enumerate(nodes)}

        # surveys
        s = read_csv(pkg, "surveys.csv")
        s["main"] = s["main"].str.strip()
        s["date"] = s["date"].str.strip()
        for c in ("p_from_barg", "dp_bar", "q_m3h"):
            s[c] = pd.to_numeric(s[c], errors="coerce")
        self.surveys = s

        # work
        try:
            w = read_csv(pkg, "work_log.csv")
            w["main"] = w["main"].str.strip()
            w["date"] = w["date"].str.strip()
            w["work"] = w["work"].str.strip().str.upper()
        except Exception:
            w = pd.DataFrame(columns=["date", "main", "work"])
        self.work = w

        p = read_csv(pkg, "prs.csv")
        self.prs = [(r["prs"].strip(), r["node"].strip(), float(r["set_point_barg"]),
                     float(r["capacity_m3h"])) for _, r in p.iterrows()]

        g = read_csv(pkg, "governors.csv")
        self.govs = [(r["governor"].strip(), r["node"].strip()) for _, r in g.iterrows()]

        dd = read_csv(pkg, "design_day.csv")
        dd["governor"] = dd["governor"].str.strip()
        dd["hour"] = pd.to_numeric(dd["hour"], errors="coerce")
        dd["demand_m3h"] = pd.to_numeric(dd["demand_m3h"], errors="coerce")
        self.design = dd

        try:
            c = read_csv(pkg, "customers.csv")
            self.customers = [(r["customer"].strip(), r["node"].strip(), r["meter"].strip())
                              for _, r in c.iterrows()]
        except Exception:
            self.customers = []
        try:
            cm = read_csv(pkg, "customer_meters.csv")
            cm["meter"] = cm["meter"].str.strip()
            cm["q_m3h"] = pd.to_numeric(cm["q_m3h"], errors="coerce")
            cm["time"] = pd.to_datetime(cm["time"].str.strip(), format="%Y-%m-%d %H:%M",
                                        errors="coerce")
            self.meters = cm.dropna(subset=["time", "q_m3h"])
        except Exception:
            self.meters = pd.DataFrame(columns=["time", "meter", "q_m3h"])

        try:
            bv = read_csv(pkg, "boundary_valves.csv")
            self.valves = [(r["valve"].strip(), r["node"].strip(), str(r["neighbour"]).strip(),
                            float(r["neighbour_pressure_barg"]), str(r["state"]).strip().lower())
                           for _, r in bv.iterrows()]
        except Exception:
            self.valves = []


# --------------------------------------------------------------------------
# hydraulics
# --------------------------------------------------------------------------
class Network:
    """Nodes, links (mains and passing boundary valves), storage and supplies."""

    def __init__(self, nodes, lf, lt, K, ext_pi, C, prs_nodes, prs_set, prs_cap):
        self.n = len(nodes)
        self.nl = len(K)
        self.lf = np.asarray(lf, dtype=np.int64)   # -1 for an external (neighbour) end
        self.lt = np.asarray(lt, dtype=np.int64)
        self.K = np.asarray(K, dtype=float)
        self.ext = np.asarray(ext_pi, dtype=float)  # pi of the external from-end, 0 if none
        self.C = np.asarray(C, dtype=float)          # m3(st) per bar abs
        self.prs_nodes = np.asarray(prs_nodes, dtype=np.int64)
        self.prs_set = np.asarray(prs_set, dtype=float)  # bar abs
        self.prs_cap = np.asarray(prs_cap, dtype=float)

        n, nl = self.n, self.nl
        rows, cols, vals = [], [], []
        for j in range(nl):
            if self.lf[j] >= 0:
                rows.append(j); cols.append(self.lf[j]); vals.append(-1.0)
            rows.append(j); cols.append(self.lt[j]); vals.append(1.0)
        self.A = sp.csr_matrix((vals, (rows, cols)), shape=(nl, n))
        self.AT = self.A.T.tocsr()
        # Laplacian assembly pattern
        inner = self.lf >= 0
        jj = np.arange(nl)
        ji = jj[inner]
        a = self.lf[inner]
        b = self.lt[inner]
        self.Lr = np.concatenate([a, b, a, b, self.lt[~inner], np.arange(n)])
        self.Lc = np.concatenate([a, b, b, a, self.lt[~inner], np.arange(n)])
        self.Lj = np.concatenate([ji, ji, ji, ji, jj[~inner]])
        self.Ls = np.concatenate([np.ones(2 * len(ji)), -np.ones(2 * len(ji)),
                                  np.ones(int((~inner).sum()))])
        self.qmin = 1e-4

    def pi_link(self, pi):
        """pi_from - pi_to for each link."""
        pf = np.where(self.lf >= 0, pi[np.maximum(self.lf, 0)], self.ext)
        return pf - pi[self.lt]

    def flows_from_pi(self, pi):
        d = self.pi_link(pi)
        return np.sign(d) * (np.abs(d) / self.K) ** (1.0 / (1.0 + EXPO))

    def solve_step(self, pi, Q, p_prev, D, mode, dt, tol=1e-8, maxit=100):
        """One implicit step for a fixed PRS state: Newton on the link and node
        equations (flows Q and squared pressures pi), the node equations reduced
        to the nodes whose pressure is not held, with a backtracking line search on
        the norm of the residuals.  mode[k] for PRS k: 0 holds its set point,
        1 delivers nothing, 2 delivers its capacity.
        Returns pi, Q, the PRS deliveries, whether it converged, iterations."""
        n = self.n
        K = self.K
        A, AT = self.A, self.AT
        pn = self.prs_nodes
        S = np.zeros(n)
        fixed = np.zeros(n, dtype=bool)
        for k in range(len(pn)):
            if mode[k] == 0:
                fixed[pn[k]] = True
                pi[pn[k]] = self.prs_set[k] ** 2
            elif mode[k] == 2:
                S[pn[k]] = self.prs_cap[k]
        free = np.nonzero(~fixed)[0]
        nf = len(free)
        pos = -np.ones(n, dtype=np.int64)
        pos[free] = np.arange(nf)
        Lr, Lc = pos[self.Lr], pos[self.Lc]
        keep = (Lr >= 0) & (Lc >= 0)
        nlap = len(self.Lj)
        keep_l = keep[:nlap]
        keep_d = keep[nlap:]
        Lr_l, Lc_l = Lr[:nlap][keep_l], Lc[:nlap][keep_l]
        Lj_l, Ls_l = self.Lj[keep_l], self.Ls[keep_l]
        Lr_d = Lr[nlap:][keep_d]
        rr = np.concatenate([Lr_l, Lr_d])
        cc = np.concatenate([Lc_l, Lr_d])
        cdt = self.C / dt
        SD = S - D
        qmin = self.qmin
        wfloor = (1.0 + EXPO) * K * 10.0 ** EXPO   # merit weight floor: 10 m3/h

        def resid(pi_, Q_):
            aQ_ = np.abs(Q_)
            r1_ = K * Q_ * aQ_ ** EXPO - self.pi_link(pi_)
            p_ = np.sqrt(np.maximum(pi_, PIMIN))
            r2_ = AT @ Q_ + SD - cdt * (p_ - p_prev)
            return r1_, r2_, aQ_, p_

        r1, r2, aQ, p = resid(pi, Q)
        ok = False
        it = 0
        for it in range(maxit):
            G = (1.0 + EXPO) * K * np.maximum(aQ, qmin) ** EXPO
            Gi = 1.0 / G
            B = cdt / (2.0 * p)
            rhs = r2 - AT @ (Gi * r1)
            data = np.concatenate([Gi[Lj_l] * Ls_l, B[free][Lr_d]])
            M = sp.csc_matrix((data, (rr, cc)), shape=(nf, nf))
            dpi = np.zeros(n)
            if nf:
                try:
                    dpi[free] = splu(M, permc_spec="MMD_AT_PLUS_A").solve(rhs[free])
                except RuntimeError:
                    reg = 1e-9 * float(np.max(np.abs(M.diagonal()))) + 1e-12
                    M = M + sp.identity(nf, format="csc") * reg
                    dpi[free] = splu(M, permc_spec="MMD_AT_PLUS_A").solve(rhs[free])
                if not np.all(np.isfinite(dpi)):
                    break
            dQ = -Gi * (r1 + A @ dpi)
            dpfull = float(np.max(np.abs(dpi))) / (2.0 * max(float(np.min(p)), 1e-3)) if nf else 0.0
            if dpfull < tol:
                pi = np.maximum(pi + dpi, PIMIN)
                Q = Q + dQ
                p = np.sqrt(pi)
                ok = True
                break
            w = 1.0 / np.maximum(G, wfloor)
            r2f = r2[free]
            phi0 = math.sqrt(float(np.dot(w * r1, w * r1) + np.dot(r2f, r2f)))
            lam = 1.0
            low = dpi < -0.9 * pi
            if low.any():
                lam = max(min(1.0, float(np.min(-0.9 * pi[low] / dpi[low]))), 1e-12)
            while True:
                pit = np.maximum(pi + lam * dpi, PIMIN)
                Qt = Q + lam * dQ
                r1t, r2t, aQt, pt = resid(pit, Qt)
                r2tf = r2t[free]
                phi = math.sqrt(float(np.dot(w * r1t, w * r1t) + np.dot(r2tf, r2tf)))
                if phi <= (1.0 - 1e-4 * lam) * phi0 or lam < 1.0 / 64 or phi0 < 1e-9:
                    break
                lam *= 0.5
            pi, Q, r1, r2, aQ, p = pit, Qt, r1t, r2t, aQt, pt
            if lam == 1.0 and dpfull < 1e3 * tol:
                # quadratic convergence: the next correction is far below tol
                ok = True
                break
        # deliveries of the PRS
        bal = AT @ Q - D - cdt * (p - p_prev)
        md = np.asarray(mode)
        Sk = np.where(md == 0, -bal[pn], np.where(md == 2, self.prs_cap, 0.0)) if len(pn) else np.zeros(0)
        return pi, Q, Sk, ok, it + 1

    def step(self, pi, Q, p_prev, D, mode, dt):
        """Implicit step with the PRS complementarity resolved."""
        mode = list(mode)
        tried = set()
        total_it = 0
        for _ in range(4 * len(mode) + 4):
            tried.add(tuple(mode))
            pi1, Q1, Sk, ok, nit = self.solve_step(pi.copy(), Q.copy(), p_prev, D, mode, dt)
            total_it += nit
            p1 = np.sqrt(pi1)
            new = list(mode)
            for k in range(len(mode)):
                pk = p1[self.prs_nodes[k]]
                sk = self.prs_set[k]
                if mode[k] == 0:
                    if Sk[k] < -1e-7:
                        new[k] = 1
                    elif Sk[k] > self.prs_cap[k] + 1e-7:
                        new[k] = 2
                elif mode[k] == 1:
                    if pk < sk - 1e-9:
                        new[k] = 0
                else:
                    if pk > sk + 1e-9:
                        new[k] = 0
            if new == mode:
                return pi1, Q1, Sk, mode, total_it
            if tuple(new) in tried:
                # cycling: switch one at a time
                for k in range(len(mode)):
                    if new[k] != mode[k]:
                        cand = list(mode)
                        cand[k] = new[k]
                        if tuple(cand) not in tried:
                            new = cand
                            break
                else:
                    return pi1, Q1, Sk, mode, total_it
            mode = new
        return pi1, Q1, Sk, mode, total_it


def run_design_day(net, demand_by_hour, max_days=40, tol=1e-5, cpu_limit=8.0):
    """demand_by_hour: (24, n) by clock hour.  Returns (NSTEP, n) gauge pressures
    at the ends of the steps of the design day, one of a run of identical days:
    the day is repeated from its own end state until it closes on itself."""
    n = net.n
    hours = [int(math.floor(6.0 + (k + 0.5) * DT)) % 24 for k in range(NSTEP)]
    # start: the steady state of the last hour of the day (06:00), or of the
    # quietest hour if the PRS could not carry that hour steadily
    tot = demand_by_hour.sum(axis=1)
    h0 = 5 if tot[5] <= net.prs_cap.sum() else int(np.argmin(tot))
    pset = net.prs_set.max() if len(net.prs_set) else 7.0
    pi = np.full(n, pset ** 2)
    Q = np.full(net.nl, 100.0)
    mode = [0] * len(net.prs_nodes)
    p_prev = np.sqrt(pi)
    for _ in range(2):
        pi, Q, Sk, mode, _ = net.step(pi, Q, p_prev, demand_by_hour[h0], mode, 1e4)
        p_prev = np.sqrt(pi)
    p_start = np.sqrt(pi)
    res = np.zeros((NSTEP, n))
    it_total = 0
    t0 = time.process_time()
    diff = float("inf")
    for day in range(max_days):
        p_prev = p_start.copy()
        failed = False
        for k in range(NSTEP):
            try:
                pi, Q, Sk, mode, nit = net.step(pi, Q, p_prev, demand_by_hour[hours[k]], mode, DT)
            except Exception as e:      # outside the scope of GD-3: keep what we have
                log("step failed:", e)
                failed = True
                res[k:] = res[k - 1] if k else p_prev
                break
            it_total += nit
            p_prev = np.sqrt(pi)
            res[k] = p_prev
        if failed:
            break
        diff = float(np.max(np.abs(p_prev - p_start)))
        p_start = p_prev.copy()
        if diff < tol:
            break
        used = time.process_time()
        if used + (used - t0) / (day + 1) > cpu_limit:
            log("stopping for time")
            break
    log(f"days={day + 1} periodic closure={diff:.2e} bar newton its={it_total}")
    return res - P0


# --------------------------------------------------------------------------
# resistances, demand, the order with the field team
# --------------------------------------------------------------------------
def plan_mains(P):
    """K of every main of the register from the surveys on file (GD-3 s.2).

    Returns K (None where no survey on file measured the main as it stands now),
    the mains that need a survey, and the mains whose only usable survey was made
    on the day of the work (it cannot be told whether it came after the work)."""
    s = P.surveys
    s = s[s["main"].isin(set(P.mains))]
    s = s.dropna(subset=["p_from_barg", "dp_bar", "q_m3h"])
    surv = {}
    rows = {}
    for r in s.itertuples(index=False):
        k = survey_k(r.p_from_barg, r.dp_bar, r.q_m3h)
        rows.setdefault(r.main, []).append(r.date)
        if np.isfinite(k):
            surv.setdefault(r.main, []).append((r.date, k, abs(r.q_m3h)))
    lastwork = {}
    for r in P.work.itertuples(index=False):
        if r.work in KCHANGE:
            if r.date >= lastwork.get(r.main, ("", ""))[0]:
                lastwork[r.main] = (r.date, r.work)
    K = {}
    need = []        # (main, |Q| of its last survey or None)
    sameday = []     # (main, consistency with the survey before the work)
    noflow = []      # surveyed as it stands, but no flow to measure K by
    for m in P.mains:
        lw, wk = lastwork.get(m, ("", ""))
        sv = sorted(surv.get(m, []), key=lambda x: x[0])
        after = [x for x in sv if x[0] > lw]
        if after:
            K[m] = after[-1][1]
            continue
        if any(d > lw for d in rows.get(m, [])):
            K[m] = None
            noflow.append(m)
            continue
        same = [x for x in sv if lw and x[0] == lw]
        if same and wk == "LAID":
            # the main was there to be surveyed on that day
            K[m] = same[-1][1]
            continue
        if same:
            before = [x for x in sv if x[0] < lw]
            K[m] = same[-1][1]
            if before:
                ratio = same[-1][1] / before[-1][1]
                sameday.append((m, abs(ratio - 1.0)))
            else:
                sameday.append((m, 1.0))
            continue
        K[m] = None
        need.append((m, sv[-1][2] if sv else None))
    return K, need, sameday, noflow


class Campaigns:
    """Node balances and pressures from the survey campaigns on file."""

    def __init__(self, P):
        s = P.surveys.dropna(subset=["p_from_barg", "dp_bar", "q_m3h"])
        mf = dict(zip(P.mains, P.mfrom))
        mt = dict(zip(P.mains, P.mto))
        s = s[s["main"].isin(set(P.mains))]
        self.dates = sorted(s["date"].unique())
        self.inflow, self.bound, self.press, self.surveyed = {}, {}, {}, {}
        self.at_node = {}
        for m, a, b in zip(P.mains, P.mfrom, P.mto):
            self.at_node.setdefault(a, []).append(m)
            self.at_node.setdefault(b, []).append(m)
        self.laid = {}
        for r in P.work.itertuples(index=False):
            if r.work == "LAID":
                self.laid[r.main] = max(self.laid.get(r.main, ""), r.date)
        for d in self.dates:
            g = s[s["date"] == d]
            self.surveyed[d] = set(g["main"])
            inflow, bound, pr = {}, {}, {}
            for r in g.itertuples(index=False):
                a, b, q = mf[r.main], mt[r.main], r.q_m3h
                inflow[b] = inflow.get(b, 0.0) + q
                inflow[a] = inflow.get(a, 0.0) - q
                bound[a] = bound.get(a, 0.0) + 0.01 * abs(q)
                bound[b] = bound.get(b, 0.0) + 0.01 * abs(q)
                pr.setdefault(a, []).append(r.p_from_barg)
                pr.setdefault(b, []).append(r.p_from_barg - r.dp_bar)
            self.inflow[d], self.bound[d] = inflow, bound
            self.press[d] = {k: float(np.mean(v)) for k, v in pr.items()}

    def complete(self, d, node):
        """Whether campaign d read every main joined at the node that was there."""
        if node not in self.inflow[d]:
            return False
        for m in self.at_node.get(node, []):
            if m not in self.surveyed[d] and not self.laid.get(m, "") >= d:
                return False
        return True

    def latest_with(self, node):
        for d in reversed(self.dates):
            if self.complete(d, node):
                return d
        return None


def check_valves(P, camp):
    """Evidence from the latest campaign that a boundary valve passes gas.
    Returns {valve: (z, q_in, K estimate or nan)}."""
    out = {}
    for (v, node, nb, pnb, st) in P.valves:
        d = camp.latest_with(node)
        if d is None:
            out[v] = (0.0, 0.0, float("nan"))
            continue
        q = -camp.inflow[d][node]           # gas into the network through the valve
        bnd = max(camp.bound[d][node], 1e-6)
        z = abs(q) / bnd
        kest = float("nan")
        if node in camp.press[d] and q != 0:
            pn = camp.press[d][node] + P0
            pb = pnb + P0
            k = (pb * pb - pn * pn) / (q * abs(q) ** EXPO)
            if np.isfinite(k) and k > 0:
                kest = k
        out[v] = (z, q, kest)
    return out


def check_meters(P, camp):
    """Registration of every customer meter estimated from the campaigns that fall
    in its record.  Returns {meter: (score, r estimate)}; score > 1 means the
    meter is out of its 1 per cent beyond any error of the surveys."""
    out = {}
    mt = P.meters
    if not len(mt):
        return out
    key = mt.set_index(["meter", "time"])["q_m3h"]
    key = key[~key.index.duplicated()]
    for (cu, node, meter) in P.customers:
        sm = so = sb = 0.0
        for d in camp.dates:
            if not camp.complete(d, node):
                continue
            try:
                q = float(key.loc[(meter, pd.Timestamp(d + " 13:00"))])
            except Exception:
                continue
            sm += q
            so += camp.inflow[d][node]
            sb += camp.bound[d][node] + 0.01 * abs(q)
        if so > 0 and sm > 0:
            r = sm / so
            u = sb / so
            out[meter] = ((abs(r - 1.0) - 0.01) / max(u, 1e-6), r)
    return out


def _surface(mat):
    """Bore surface of a main: polyethylene for PE mains and PE-lined mains."""
    m = mat.upper()
    return "PE" if m.startswith("PE") else m


def estimate_k(P, K):
    """Fallback K for mains no survey measured as they stand (only where the field
    team could not be asked): K ~ c(bore surface) L D^-4.82, c from the mains of
    the same surface that were surveyed."""
    c_by_mat = {}
    allc = []
    for i, m in enumerate(P.mains):
        if K.get(m) is not None and P.mdia[i] > 0 and P.mlen[i] > 0:
            c = K[m] * (P.mdia[i] / 1000.0) ** 4.82 / P.mlen[i]
            c_by_mat.setdefault(_surface(P.mmat[i]), []).append(c)
            allc.append(c)
    call = float(np.median(allc)) if allc else 1.2e-13
    est = {}
    for i, m in enumerate(P.mains):
        if K.get(m) is None:
            cs = c_by_mat.get(_surface(P.mmat[i]))
            c = float(np.median(cs)) if cs else call
            est[m] = c * P.mlen[i] / (P.mdia[i] / 1000.0) ** 4.82
    return est


def customer_profiles(P):
    """Mean weekday flow by clock hour for every meter, as registered."""
    mt = P.meters
    prof = {}
    if len(mt):
        wk = mt[mt["time"].dt.dayofweek < 5]
        g = wk.groupby(["meter", wk["time"].dt.hour])["q_m3h"].mean()
        for (meter, h), v in g.items():
            prof.setdefault(meter, np.zeros(24))[int(h)] = v
    return prof


def order_field_team(P, items):
    """Place the one order; returns dicts of main, valve and meter readings."""
    res = {"main": {}, "valve": {}, "meter": {}}
    if not items:
        return res
    try:
        out = subprocess.run(["gdsurvey", P.pkg] + list(items), capture_output=True,
                             text=True, timeout=60)
    except Exception as e:
        log("gdsurvey failed:", e)
        return res
    if out.returncode != 0:
        log("gdsurvey refused:", out.stderr.strip()[:500], out.stdout.strip()[:500])
    log("gdsurvey answered:\n" + out.stdout.strip() + "\n" + out.stderr.strip())
    kind = None
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        f = [x.strip() for x in line.split(",")]
        if f[0] in ("main", "valve", "meter") and len(f) > 1 and not _isnum(f[1]):
            kind = f[0]
            continue
        if kind is None:
            continue
        try:
            vals = [float(x) for x in f[1:]]
        except ValueError:
            continue
        res[kind][f[0]] = vals
    return res


def _isnum(x):
    try:
        float(x)
        return True
    except ValueError:
        return False


def main():
    if len(sys.argv) != 3:
        print("usage: designday.py PACKAGE_DIR OUT_CSV", file=sys.stderr)
        sys.exit(2)
    pkg, out = sys.argv[1], sys.argv[2]
    P = Package(pkg)
    camp = Campaigns(P)
    K, need, sameday, noflow = plan_mains(P)
    vchk = check_valves(P, camp)
    mchk = check_meters(P, camp)
    prof = customer_profiles(P)
    vstate = {v[0]: v[4] for v in P.valves}

    # ---- the order: what GD-3 cannot do without first, then the doubtful
    first = []
    # boundary valves registered open: no survey across them on file
    for v in sorted((v for v in vstate if vstate[v] == "open"),
                    key=lambda v: -vchk[v][0]):
        first.append(v)
    # mains no survey on file measured as they stand: laid first, then by flow
    for m, q in sorted(need, key=lambda x: -(1e12 if x[1] is None else x[1])):
        first.append(m)
    # evidence in the campaigns: closed valves that pass gas, meters out of
    # their accuracy; strongest first
    evid = []
    for v, st in vstate.items():
        if st != "open" and vchk[v][0] > 1.2:
            evid.append((vchk[v][0], v))
    for meter, (sc, r) in mchk.items():
        if sc > 1.0:
            evid.append((sc, meter))
    evid.sort(reverse=True)
    second = [x[1] for x in evid]
    # mains surveyed on the day of their work: those whose K did not change
    # across the work first (the survey was then likely made before it)
    second += [m for m, dev in sorted(sameday, key=lambda x: x[1])]
    # then, with what is left of the allowance: the other meters, most doubtful
    # first, the closed valves, and mains surveyed with no flow to read
    def mkey(c):
        sc = mchk.get(c[2], (0.0, 1.0))[0]
        return (-sc, -float(np.mean(prof.get(c[2], np.zeros(24)))))
    rest = [c[2] for c in sorted(P.customers, key=mkey) if c[2] not in second]
    rest += [v for v in sorted(vstate, key=lambda v: -vchk[v][0])
             if v not in first and v not in second]
    rest += list(noflow)
    items = []
    for it in first + second + rest:
        if it not in items:
            items.append(it)
    items = items[:max(P.allowance, 0)]
    log("valve checks:", {k: (round(v[0], 2), round(v[1], 1)) for k, v in vchk.items()})
    log("meter checks:", {k: (round(v[0], 2), round(v[1], 4)) for k, v in mchk.items()})
    log("mains needing a survey:", [m for m, _ in need], "same-day:", sameday, "no flow:", noflow)
    log("order:", items)
    got = order_field_team(P, items)

    # ---- resistances of the mains
    for m in [m for m, _ in need] + [m for m, _ in sameday] + list(noflow):
        r = got["main"].get(m)
        if r is not None and len(r) >= 3:
            k = survey_k(r[0], r[1], r[2])
            if np.isfinite(k):
                K[m] = k
    est = estimate_k(P, K)
    for m, k in est.items():
        log("no survey of", m, "as it stands: K estimated from its size and material")
        K[m] = k

    n = len(P.nodes)
    ni = P.nidx
    # ---- linepack (GD-3 s.3)
    vol = np.zeros(n)
    for i in range(len(P.mains)):
        v = math.pi * (P.mdia[i] / 1000.0) ** 2 * P.mlen[i] / 8.0
        vol[ni[P.mfrom[i]]] += v
        vol[ni[P.mto[i]]] += v
    C = vol / P0
    lf = [ni[a] for a in P.mfrom]
    lt = [ni[b] for b in P.mto]
    Ks = [K[m] for m in P.mains]
    ext = [0.0] * len(P.mains)
    # ---- boundary valves that pass gas (GD-3 s.6)
    for (v, node, nb, pnb, st) in P.valves:
        if node not in ni:
            continue
        r = got["valve"].get(v)
        kv = float("nan")
        if r is not None and len(r) >= 3:
            pn_, pb_, q_ = r[0] + P0, r[1] + P0, r[2]
            den = q_ * abs(q_) ** EXPO
            if den != 0:
                kv = (pb_ ** 2 - pn_ ** 2) / den
            if not (np.isfinite(kv) and kv > 0):
                log("valve", v, "passes nothing in the field survey")
                continue
        else:
            passing = st == "open" or vchk[v][0] > 1.2
            if not passing:
                continue
            kv = vchk[v][2]
            if not (np.isfinite(kv) and kv > 0):
                log("valve", v, "registered", st, "without a usable survey: taken as passing nothing")
                continue
            log("valve", v, "not surveyed: K from the campaign balance at its node")
        lf.append(-1)
        lt.append(ni[node])
        Ks.append(kv)
        ext.append((pnb + P0) ** 2)
    prs_nodes = [ni[p[1]] for p in P.prs]
    prs_set = [p[2] + P0 for p in P.prs]
    prs_cap = [p[3] for p in P.prs]
    net = Network(P.nodes, lf, lt, Ks, ext, C, prs_nodes, prs_set, prs_cap)

    # ---- demand (GD-3 s.7)
    D = np.zeros((24, n))
    dd = P.design.dropna(subset=["hour", "demand_m3h"])
    gnode = dict(P.govs)
    gdem = {}
    for r in dd.itertuples(index=False):
        gdem[(r.governor, int(r.hour) % 24)] = r.demand_m3h
    for (g, h), q in gdem.items():
        if g in gnode and gnode[g] in ni:
            D[h, ni[gnode[g]]] += q
    for (cu, node, meter) in P.customers:
        if node not in ni:
            continue
        q = prof.get(meter, np.zeros(24)).copy()
        r = got["meter"].get(meter)
        if r is not None and len(r) >= 1 and r[0] > 0:
            if abs(r[0] - 100.0) > 1.0:
                log("meter", meter, "proved at", r[0], "per cent: its record corrected")
                q = q * 100.0 / r[0]
            # a meter proved within its 1 per cent: its record stands
        elif meter in mchk and mchk[meter][0] > 1.0:
            log("meter", meter, "not proved: registration taken from the campaigns",
                round(mchk[meter][1], 4))
            q = q / mchk[meter][1]
        D[:, ni[node]] += q

    res = run_design_day(net, D)
    pmin = res.min(axis=0)
    with open(out, "w") as f:
        f.write("governor,min_pressure_barg\n")
        for g, node in P.govs:
            val = pmin[ni[node]] if node in ni else float("nan")
            f.write(f"{g},{val:.4f}\n")


if __name__ == "__main__":
    main()
