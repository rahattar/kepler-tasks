#!/usr/bin/env python3
"""Design-day pressures to GD-3 for one network package.

    python3 designday.py PACKAGE_DIR OUT_CSV

Writes OUT_CSV with the header governor,min_pressure_barg: the lowest pressure
at every district governor's node over the 240 steps of the periodic design
day (GD-3 sections 2 to 9).

Before calculating, the program places the package's one order with the field
team (`gdsurvey`, network_package.md "The field team") for the items whose
values the records cannot give:
  * mains renewed, relined or laid after their latest survey on file, and
    mains with no survey at all (GD-3 section 2);
  * boundary valves registered open, and valves registered closed that the
    survey campaigns show to be passing gas (node balance at the valve node);
  * customer meters that the survey campaigns show to register wrongly
    (node balance at the customer's node against the meter record).
"""
import csv
import datetime
import json
import math
import os
import re
import subprocess
import time
import sys

import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import splu

PATM = 1.01325          # bar, standard pressure, absolute = gauge + PATM
EXPO = 1.82             # p_from^2 - p_to^2 = K Q |Q|^0.82
ALPHA = 1.0 / EXPO
DT = 0.1                # h, step length
NSTEP = 240             # steps in the design day
START_HOUR = 6          # the design day runs from 06:00
Q_MIN = 0.01            # m3/h: floor of |Q| in the Newton linearisation of a link
SIG = 0.01 / math.sqrt(3.0)   # sd of a reading "within 1 per cent" (uniform)
WORKS_NEW_K = ("RENEWED", "RELINED", "LAID")
CPU_BUDGET = 8.0        # s of process CPU time: a run must finish within 10 s
CPU_SOFT = 5.5          # past this, a step that will not converge is cut short

DEBUG = bool(os.environ.get("DESIGNDAY_DEBUG"))


def log(*a):
    if DEBUG:
        print(*a, file=sys.stderr)


# --------------------------------------------------------------------------
# reading the package
# --------------------------------------------------------------------------
def read_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = []
        for row in csv.DictReader(fh):
            clean = {}
            for k, v in row.items():
                if k is None:
                    continue
                clean[k.strip().lower()] = (v or "").strip()
            if any(clean.values()):
                rows.append(clean)
        return rows


def fnum(s, default=None):
    try:
        x = float(s)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    return x


def norm_date(s):
    """'YYYY-MM-DD' (possibly with a time after it) -> 'YYYY-MM-DD'."""
    s = (s or "").strip()
    return s[:10]


class Package:
    def __init__(self, d):
        self.dir = d
        try:
            with open(os.path.join(d, "network.json"), encoding="utf-8-sig") as fh:
                meta = json.load(fh)
        except Exception:
            meta = {}
        self.name = meta.get("network", os.path.basename(os.path.normpath(d)))
        try:
            self.allowance = int(meta.get("survey_allowance", 0))
        except (TypeError, ValueError):
            self.allowance = 0

        # mains
        self.mains = []          # (name, from, to, L, D)
        seen = set()
        for r in read_rows(os.path.join(d, "mains.csv")):
            name = r.get("main", "")
            if not name or name in seen:
                continue
            seen.add(name)
            self.mains.append((name, r.get("from_node", ""), r.get("to_node", ""),
                               fnum(r.get("length_m"), 0.0) or 0.0,
                               fnum(r.get("diameter_mm"), 0.0) or 0.0,
                               r.get("material", "")))
        self.main_index = {m[0]: i for i, m in enumerate(self.mains)}

        nodes = []
        nset = set()
        for m in self.mains:
            for n in (m[1], m[2]):
                if n not in nset:
                    nset.add(n)
                    nodes.append(n)

        # surveys: date -> {main: (pf_abs, pt_abs, q)}
        self.campaigns = {}
        for r in read_rows(os.path.join(d, "surveys.csv")):
            name = r.get("main", "")
            pf = fnum(r.get("p_from_barg"))
            dp = fnum(r.get("dp_bar"))
            q = fnum(r.get("q_m3h"))
            date = norm_date(r.get("date", ""))
            if name not in self.main_index or pf is None or dp is None or q is None:
                continue
            pfa = pf + PATM
            self.campaigns.setdefault(date, {})[name] = (pfa, pfa - dp, q)

        # work log: main -> list of (date, work)
        self.works = {}
        for r in read_rows(os.path.join(d, "work_log.csv")):
            self.works.setdefault(r.get("main", ""), []).append(
                (norm_date(r.get("date", "")), r.get("work", "").strip().upper()))

        self.prs = []
        for r in read_rows(os.path.join(d, "prs.csv")):
            sp = fnum(r.get("set_point_barg"))
            cap = fnum(r.get("capacity_m3h"))
            if sp is None or cap is None:
                continue
            self.prs.append((r.get("prs", ""), r.get("node", ""), sp + PATM, max(cap, 0.0)))

        self.governors = [(r.get("governor", ""), r.get("node", ""))
                          for r in read_rows(os.path.join(d, "governors.csv"))
                          if r.get("governor", "")]

        self.gov_demand = {}     # governor -> [24]
        for r in read_rows(os.path.join(d, "design_day.csv")):
            g = r.get("governor", "")
            h = fnum(r.get("hour"))
            q = fnum(r.get("demand_m3h"))
            if h is None or q is None:
                continue
            h = int(round(h)) % 24
            arr = self.gov_demand.setdefault(g, [None] * 24)
            arr[h] = q

        self.customers = [(r.get("customer", ""), r.get("node", ""), r.get("meter", ""))
                          for r in read_rows(os.path.join(d, "customers.csv"))
                          if r.get("customer", "")]

        # meter record: meter -> {time: q}
        self.meter_rec = {}
        path = os.path.join(d, "customer_meters.csv")
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8-sig") as fh:
                rd = csv.reader(fh)
                header = [h.strip().lower() for h in next(rd, [])]
                try:
                    it, im, iq = header.index("time"), header.index("meter"), header.index("q_m3h")
                except ValueError:
                    it, im, iq = 0, 1, 2
                for row in rd:
                    if len(row) <= max(it, im, iq):
                        continue
                    q = fnum(row[iq])
                    if q is None:
                        continue
                    t = " ".join(row[it].strip().replace("T", " ").split())[:16]
                    self.meter_rec.setdefault(row[im].strip(), {})[t] = q

        self.valves = []
        for r in read_rows(os.path.join(d, "boundary_valves.csv")):
            pnb = fnum(r.get("neighbour_pressure_barg"))
            self.valves.append((r.get("valve", ""), r.get("node", ""), r.get("neighbour", ""),
                                None if pnb is None else pnb + PATM,
                                r.get("state", "").strip().lower()))

        for n in ([p[1] for p in self.prs] + [g[1] for g in self.governors]
                  + [c[1] for c in self.customers] + [v[1] for v in self.valves]):
            if n and n not in nset:
                nset.add(n)
                nodes.append(n)
        self.nodes = nodes
        self.node_index = {n: i for i, n in enumerate(nodes)}


# --------------------------------------------------------------------------
# what the records give, and what the field team must give
# --------------------------------------------------------------------------
def k_of(pf, pt, q):
    """K from a reading, or None when the reading cannot give one."""
    if q == 0:
        return None
    dsq = pf * pf - pt * pt
    k = dsq / (q * abs(q) ** (EXPO - 1.0))
    if not (k > 0 and math.isfinite(k)):
        return None
    return k


def main_k_from_records(pkg):
    """For every main: (K or None, status).  status: 'ok' (K of its latest
    survey, made after any renewal, relining or laying), 'older' (its latest
    survey gives no K, an earlier one after the work does), 'sameday' (only a
    survey on the day of the work), 'need' (no survey after the work)."""
    out = {}
    dates = sorted(pkg.campaigns)
    for name, f, t, L, D, mat in pkg.mains:
        last_work = ""
        for date, work in pkg.works.get(name, []):
            if work in WORKS_NEW_K and date > last_work:
                last_work = date
        k_after = None
        k_same = None
        skipped = False
        for date in reversed(dates):          # latest survey first
            rec = pkg.campaigns[date].get(name)
            if rec is None:
                continue
            k = k_of(*rec)
            if k is None:                     # a reading that gives no K (no flow)
                skipped = True
                continue
            if date > last_work:
                k_after = k
                break
            if date == last_work and k_same is None:
                k_same = k
            if date <= last_work:
                break
        if k_after is not None:
            out[name] = (k_after, "older" if skipped else "ok")
        elif k_same is not None:
            out[name] = (k_same, "sameday")
        else:
            out[name] = (None, "need")
    return out


def campaign_balances(pkg):
    """For every campaign: node -> (net inflow from mains, sum q^2, sum |q|),
    only for nodes all of whose mains were read (or could not yet exist)."""
    laid = {}
    for name, ws in pkg.works.items():
        for date, work in ws:
            if work == "LAID":
                laid[name] = max(laid.get(name, ""), date)
    res = {}
    for date, recs in pkg.campaigns.items():
        net = {}
        s2 = {}
        s1 = {}
        bad = set()
        for name, f, t, L, D, mat in pkg.mains:
            rec = recs.get(name)
            if rec is None:
                if laid.get(name, "") >= date:
                    continue     # not laid yet at the campaign: no flow
                bad.add(f)
                bad.add(t)
                continue
            q = rec[2]
            net[f] = net.get(f, 0.0) - q
            net[t] = net.get(t, 0.0) + q
            for n in (f, t):
                s2[n] = s2.get(n, 0.0) + q * q
                s1[n] = s1.get(n, 0.0) + abs(q)
        res[date] = {n: (net[n], s2[n], s1[n]) for n in net if n not in bad}
    return res


def campaign_node_pressure(pkg, date, node):
    vals = []
    for name, f, t, L, D, mat in pkg.mains:
        rec = pkg.campaigns[date].get(name)
        if rec is None:
            continue
        if f == node:
            vals.append(rec[0])
        if t == node:
            vals.append(rec[1])
    return sum(vals) / len(vals) if vals else None


def assess(pkg, kinfo):
    """Decide what the field team must give.

    Returns (required, optional, est_valve, est_meter):
      required   [(priority, item, why)]  items the records cannot give
      optional   [(score, item, why)]     items worth an order if room is left
      est_valve  valve -> K from the campaigns (used only if not surveyed)
      est_meter  meter -> registered/true from the campaigns (ditto)

    The campaign test: a campaign reads every main in a steady hour, so the
    mains' flows balance at every node, less what the node's customer takes
    or what its boundary valve passes.  A reading is within 1 per cent of
    the flow, and a sound meter within 1 per cent of the gas through it, so a
    misbalance beyond those bounds shows a passing valve or a wrong meter."""
    bal = campaign_balances(pkg)
    dates = sorted(bal)
    required = []
    optional = []
    est_valve = {}
    est_meter = {}

    last_q = {}
    for date in dates:
        for name, rec in pkg.campaigns[date].items():
            last_q[name] = abs(rec[2])
    for name, f, t, L, D, mat in pkg.mains:
        k, st = kinfo[name]
        if st == "need":
            # LAID mains (no flow on file) first, then by the flow they carry
            required.append((0, -last_q.get(name, 1e12), name,
                             "main without a survey since its work"))
        elif st == "sameday":
            optional.append((1e6, name, "main surveyed on the day of its work"))
        elif st == "older":
            optional.append((1e5, name, "main whose latest survey gives no K"))

    # boundary valves
    for vname, node, nb, pnb, state in pkg.valves:
        latest = None
        sum_net = sum_var = 0.0
        for date in dates:
            b = bal[date].get(node)
            if b is not None:
                latest = (date,) + b
                sum_net += b[0]
                sum_var += (SIG * math.sqrt(b[1]) + 0.05) ** 2
        if latest is not None and pnb is not None:
            date, net, s2, s1 = latest
            vflow = -net      # flow into the network through the valve
            if abs(vflow) > 4 * (SIG * math.sqrt(s2) + 0.05):
                p_node = campaign_node_pressure(pkg, date, node)
                if p_node is not None:
                    k = k_of(pnb, p_node, vflow)
                    if k is not None:
                        est_valve[vname] = k
        if state == "open":
            required.append((0, -1e12, vname, "open boundary valve"))
            continue
        if latest is None:
            optional.append((2.0, vname, "closed valve, no campaign balance"))
            continue
        date, net, s2, s1 = latest
        z = abs(net) / (SIG * math.sqrt(s2) + 0.05)
        strict = abs(net) > 0.01 * s1 + 0.5
        if strict and z > 4:
            required.append((1, -z, vname, "closed valve passing gas (z=%.1f, %.0f m3/h)"
                             % (z, -net)))
        else:
            z_all = abs(sum_net) / math.sqrt(sum_var) if sum_var > 0 else 0.0
            optional.append((max(z, z_all), vname, "closed valve (z=%.1f)" % max(z, z_all)))

    # customer meters
    for cname, node, meter in pkg.customers:
        rec = pkg.meter_rec.get(meter, {})
        num = var = sreg = snet = 0.0
        strict = False
        n_used = 0
        for date in dates:
            b = bal[date].get(node)
            reg = rec.get(date + " 13:00")
            if b is None or reg is None:
                continue
            net, s2, s1 = b
            e = reg - net
            num += e
            var += SIG * SIG * s2 + 0.05 ** 2     # readings: independent per campaign
            sreg += reg
            snet += net
            n_used += 1
            if abs(e) > 0.01 * s1 + 0.01 * abs(reg) + 0.5:
                strict = True
        if n_used == 0:
            optional.append((2.0, meter, "meter not checkable against a campaign"))
            continue
        var += (SIG * sreg) ** 2                  # a sound meter's own error: one bias
        z = abs(num) / math.sqrt(var)
        if snet > 0 and sreg > 0:
            est_meter[meter] = sreg / snet
        if strict and z > 4:
            required.append((1, -z, meter, "meter registering wrongly (z=%.1f, ratio %.3f)"
                             % (z, sreg / snet if snet else float("nan"))))
        else:
            optional.append((z, meter, "meter (z=%.1f)" % z))
    required.sort(key=lambda r: (r[0], r[1]))
    required = [(r[0], r[2], r[3]) for r in required]
    return required, optional, est_valve, est_meter


def build_order(pkg, required, optional):
    """Required items first, then optional ones by evidence, to the allowance."""
    allowance = max(pkg.allowance, 0)
    order = []
    for pri, item, why in required:
        if len(order) < allowance and item not in order:
            order.append(item)
    for score, item, why in sorted(optional, key=lambda x: -x[0]):
        if len(order) >= allowance:
            break
        if item not in order:
            order.append(item)
    return order


def parse_field(text, out):
    header = None
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().split(",")]
        if not cells or not cells[0]:
            continue
        key = cells[0].lower()
        if key in out and len(cells) > 1:
            header = [c.lower() for c in cells]
            continue
        if header is None or len(cells) != len(header):
            continue
        out[header[0]][cells[0]] = dict(zip(header, cells))


def place_order(pkg_dir, items):
    """Place the package's one order with the field team (gdsurvey).
    Returns {'main': {...}, 'valve': {...}, 'meter': {...}} of the rows read.
    An order that the team refuses outright (an item it does not know, too
    many items) is not an order placed, so it is corrected and placed again."""
    out = {"main": {}, "valve": {}, "meter": {}}
    items = list(dict.fromkeys(i for i in items if i))
    for attempt in range(6):
        if not items:
            return out
        try:
            proc = subprocess.run(["gdsurvey", pkg_dir] + items, capture_output=True,
                                  text=True, timeout=30)
        except Exception as exc:          # no field team: carry on from the records
            log("gdsurvey failed:", exc)
            return out
        log("gdsurvey rc", proc.returncode, (proc.stdout if proc.returncode else "").strip(),
            proc.stderr.strip())
        parse_field(proc.stdout, out)
        if proc.returncode == 0:
            return out
        msg = proc.stdout + "\n" + proc.stderr
        m = re.search(r"no main, boundary valve or meter (\S+)", msg)
        if m and m.group(1) in items:
            items.remove(m.group(1))
            continue
        m = re.search(r"at most (\d+) item", msg)
        if m and int(m.group(1)) < len(items):
            items = items[:int(m.group(1))]
            continue
        if "named twice" in msg:
            items = list(dict.fromkeys(items))
            continue
        return out
    return out


# --------------------------------------------------------------------------
# fallback estimate of a main's K from the others (used only when the field
# team cannot give a survey of it)
# --------------------------------------------------------------------------
def regress_k(pkg, kvals):
    """log K = b log L + c log D + offset(material), fitted on the mains with
    a K; returns a predictor."""
    xs, ys, mats = [], [], []
    for name, f, t, L, D, mat in pkg.mains:
        k = kvals.get(name)
        if k is None or L <= 0 or D <= 0:
            continue
        xs.append((math.log(L), math.log(D)))
        ys.append(math.log(k))
        mats.append(mat.upper())
    if len(ys) < 5:
        return lambda L, D, mat: 1e-7 * (max(L, 1.0) / 1000.0) * (200.0 / max(D, 1.0)) ** 4.82
    ml = sorted(set(mats))
    X = np.zeros((len(ys), 2 + len(ml)))
    for i, ((lL, lD), m) in enumerate(zip(xs, mats)):
        X[i, 0] = lL
        X[i, 1] = lD
        X[i, 2 + ml.index(m)] = 1.0
    coef, *_ = np.linalg.lstsq(X, np.array(ys), rcond=None)
    off = {m: coef[2 + i] for i, m in enumerate(ml)}
    pe = [v for m, v in off.items() if "PE" in m]
    allo = list(off.values())

    def pred(L, D, mat):
        m = mat.upper()
        if m in off:
            o = off[m]
        elif "PE" in m and pe:
            o = sum(pe) / len(pe)
        else:
            o = sum(allo) / len(allo)
        return math.exp(coef[0] * math.log(max(L, 1.0)) + coef[1] * math.log(max(D, 1.0)) + o)
    return pred


# --------------------------------------------------------------------------
# the design day
# --------------------------------------------------------------------------
class Network:
    """Nodes 0..n-1 are the network's; nodes n..n+nv-1 stand for the
    neighbouring networks behind passing boundary valves, held at their
    register pressure and holding no gas.  Links are the mains, then the
    valves (from the neighbour to the network's node, GD-3 section 6)."""

    def __init__(self, n_nodes, mf, mt, mk, cap_v, vnode, vpnb, vk,
                 prs_node, prs_sp, prs_cap, demand):
        n = n_nodes
        nv = len(vnode)
        self.n = n
        self.nt = n + nv
        nt = self.nt
        self.lf = np.concatenate([np.asarray(mf, dtype=np.int64),
                                  np.arange(n, nt, dtype=np.int64)])
        self.lt = np.concatenate([np.asarray(mt, dtype=np.int64),
                                  np.asarray(vnode, dtype=np.int64)])
        self.lk = np.concatenate([np.asarray(mk, dtype=float), np.asarray(vk, dtype=float)])
        self.cdt = np.concatenate([np.asarray(cap_v, dtype=float), np.zeros(nv)]) / DT
        self.fixed_nodes = np.arange(n, nt, dtype=np.int64)
        self.fixed_p = np.asarray(vpnb, dtype=float)
        self.pn = np.asarray(prs_node, dtype=np.int64)
        self.psp = np.asarray(prs_sp, dtype=float)
        self.pcap = np.asarray(prs_cap, dtype=float)
        self.demand = np.concatenate([demand, np.zeros((24, nv))], axis=1)
        self.kinv = self.lk ** (-ALPHA)
        self.qmin = Q_MIN

        lf, lt = self.lf, self.lt
        rows = np.concatenate([np.arange(nt), lt, lt, lf, lf])
        cols = np.concatenate([np.arange(nt), lf, lt, lf, lt])
        key = cols * nt + rows
        ukey, inv = np.unique(key, return_inverse=True)
        self.nnz = len(ukey)
        ucol = ukey // nt
        self.urow = ukey % nt
        self.indices = self.urow.astype(np.int32)
        self.indptr = np.searchsorted(ucol, np.arange(nt + 1)).astype(np.int32)
        self.diag_slot = inv[:nt]
        nl = len(lf)
        self.link_slots = inv[nt:]               # tf, tt, ff, ft blocks of nl each
        self.nl = nl

    def q_of_p(self, p):
        """Flows of the links for pressures p (exact law)."""
        dsq = p[self.lf] ** 2 - p[self.lt] ** 2
        return np.sign(dsq) * self.kinv * np.abs(dsq) ** ALPHA

    def step(self, p_old, p_guess, q_guess, dem, mode, stats):
        """One implicit step (GD-3 section 8).

        Newton on node pressures and link flows together (the link law is
        linearised in Q, which behaves well at small flows).  A PRS is in one
        of three modes (GD-3 section 5): 0 holds its node at the set point
        (delivery between nothing and capacity), 1 delivers its capacity with
        the node below the set point, 2 delivers nothing with the node above
        it; the modes are found by an active-set iteration inside Newton."""
        nt = self.nt
        lf, lt, K = self.lf, self.lt, self.lk
        p = p_guess.copy()
        p[self.fixed_nodes] = self.fixed_p
        Q = q_guess.copy()
        mode = mode.copy()
        pn = self.pn
        npr = len(pn)
        switches = 0
        maxstep = np.inf
        maxdq = np.inf
        dirich = np.zeros(nt, dtype=bool)
        dirich[self.fixed_nodes] = True
        itmax = 60 if time.process_time() < CPU_SOFT else 6
        for it in range(itmax):
            pf = p[lf]
            pt = p[lt]
            dsq = pf * pf - pt * pt
            aq = np.abs(Q)
            hq = K * Q * aq ** (EXPO - 1.0)
            c = 1.0 / (EXPO * K * np.maximum(aq, self.qmin) ** (EXPO - 1.0))
            Qt = Q + c * (dsq - hq)
            F = (np.bincount(lt, Qt, nt) - np.bincount(lf, Qt, nt)
                 - dem - self.cdt * (p - p_old))
            if npr:
                need = -F[pn]            # delivery that balances the node as it stands
                if switches < 12:
                    new_mode = mode.copy()
                    for j in range(npr):
                        if mode[j] == 0:
                            if need[j] > self.pcap[j] + 1e-4:
                                new_mode[j] = 1
                            elif need[j] < -1e-4:
                                new_mode[j] = 2
                        elif mode[j] == 1:
                            if p[pn[j]] > self.psp[j] + 1e-9:
                                new_mode[j] = 0
                        elif p[pn[j]] < self.psp[j] - 1e-9:
                            new_mode[j] = 0
                    if np.any(new_mode != mode):
                        switches += 1
                        mode = new_mode
                        maxstep = np.inf
                setm = mode == 0
                F[pn] += np.where(mode == 1, self.pcap, 0.0) * (~setm)
                dirich[pn] = setm
                F[pn[setm]] = self.psp[setm] - p[pn[setm]]
            F[self.fixed_nodes] = 0.0
            res = np.max(np.abs(F[~dirich])) if nt > 0 else 0.0
            if maxstep < 1e-7 and maxdq < 1e-3 and res < 1e-3:
                break
            g2f = c * 2.0 * pf
            g2t = c * 2.0 * pt
            vals = np.concatenate([g2f, -g2t, -g2f, g2t])
            data = np.bincount(self.link_slots, vals, self.nnz)
            data += np.bincount(self.diag_slot, -self.cdt, self.nnz)
            data[dirich[self.urow]] = 0.0
            data[self.diag_slot[dirich]] = -1.0
            J = csc_matrix((data, self.indices, self.indptr), shape=(nt, nt))
            try:
                dp = splu(J, permc_spec="MMD_AT_PLUS_A").solve(-F)
            except RuntimeError:         # singular: steady the diagonal a little
                data[self.diag_slot] -= 1e-3 * (1.0 + np.abs(data[self.diag_slot]))
                J = csc_matrix((data, self.indices, self.indptr), shape=(nt, nt))
                dp = splu(J, permc_spec="MMD_AT_PLUS_A").solve(-F)
            if not np.all(np.isfinite(dp)):
                stats["noconv"] += 1
                break
            stats["lu"] += 1
            mx = float(np.max(np.abs(dp)))
            if mx > 0.5:                 # damping of large steps
                dp *= 0.5 / mx
            Qn = Qt + c * (2.0 * pf * dp[lf] - 2.0 * pt * dp[lt])
            maxdq = float(np.max(np.abs(Qn - Q))) if len(Q) else 0.0
            Q = Qn
            p += dp
            np.maximum(p, 0.05, out=p)
            maxstep = mx
        else:
            stats["noconv"] += 1
        stats["steps"] += 1
        stats["maxit"] = max(stats["maxit"], it)
        return p, Q, mode

    def day(self, p0, q0, mode0, stats):
        p = p0.copy()
        Q = q0.copy()
        mode = mode0.copy()
        traj = np.empty((NSTEP, self.n))
        prev = p.copy()
        qprev = Q.copy()
        for k in range(NSTEP):
            hour = (START_HOUR + k // 10) % 24
            if k % 10 and k > 0:
                guess, qguess = p + (p - prev), Q + (Q - qprev)
            else:
                guess, qguess = p, Q
            newp, newq, mode = self.step(p, guess, qguess, self.demand[hour], mode, stats)
            if not (np.all(np.isfinite(newp)) and np.all(np.isfinite(newq))):
                newp, newq, mode = self.step(p, p, Q, self.demand[hour], mode, stats)
                if not (np.all(np.isfinite(newp)) and np.all(np.isfinite(newq))):
                    newp, newq = p.copy(), Q.copy()
            prev, qprev = p, Q
            p, Q = newp, newq
            traj[k] = p[:self.n]
        return traj, p, Q, mode


def solve_design_day(net, p_init):
    """Repeat the design day until its end state is its start state."""
    stats = {"lu": 0, "steps": 0, "noconv": 0, "maxit": 0}
    p0 = np.concatenate([p_init, net.fixed_p])
    q0 = net.q_of_p(p0)
    mode0 = np.zeros(len(net.pn), dtype=np.int64)
    traj = None
    for d in range(40):
        t_day = time.process_time()
        traj, p_end, q_end, mode = net.day(p0, q0, mode0, stats)
        diff = float(np.max(np.abs(p_end - p0)))
        log("day", d, "end-start max diff %.2e" % diff, "lu", stats["lu"])
        p0, q0, mode0 = p_end, q_end, mode
        if diff < 1e-5:
            break
        now = time.process_time()
        if now + (now - t_day) > CPU_BUDGET:      # no time for another day
            log("stopping on CPU time with end-start diff", diff)
            break
    return traj, stats


# --------------------------------------------------------------------------
def build_model(pkg_dir, field=None):
    """Read the package, place the order (unless `field` is given) and return
    (pkg, model dict)."""
    pkg = Package(pkg_dir)
    kinfo = main_k_from_records(pkg)
    required, optional, est_valve, est_meter = assess(pkg, kinfo)
    order = build_order(pkg, required, optional)
    log("required", required)
    log("order", order)
    if field is None:
        field = place_order(pkg_dir, order)
    log("field", field)

    # mains' K
    kvals = {name: k for name, (k, st) in kinfo.items() if k is not None and st == "ok"}
    for name, row in field["main"].items():
        pf = fnum(row.get("p_from_barg"))
        dp = fnum(row.get("dp_bar"))
        q = fnum(row.get("q_m3h"))
        if pf is None or dp is None or q is None or name not in pkg.main_index:
            continue
        k = k_of(pf + PATM, pf + PATM - dp, q)
        if k is not None:
            kvals[name] = k
    pred = None
    mk = []
    for name, f, t, L, D, mat in pkg.mains:
        k = kvals.get(name)
        if k is None:
            k0, st = kinfo[name]
            if k0 is not None:
                k = k0
            else:
                if pred is None:
                    pred = regress_k(pkg, kvals)
                k = pred(L, D, mat)
                log("main", name, "K estimated", k)
        mk.append(k)

    flagged = set(r[1] for r in required)

    # boundary valves that pass gas
    vnode, vpnb, vk = [], [], []
    for vname, node, nb, pnb, state in pkg.valves:
        if pnb is None or node not in pkg.node_index:
            continue
        k = None
        known = False
        row = field["valve"].get(vname)
        if row is not None:
            pn_ = fnum(row.get("p_node_barg"))
            pb_ = fnum(row.get("p_neighbour_barg"))
            q = fnum(row.get("q_m3h"))
            if pn_ is not None and pb_ is not None and q is not None:
                known = True
                if q != 0:
                    k = k_of(pb_ + PATM, pn_ + PATM, q)
                    if k is None:       # pressures read alike: K from |dp^2|
                        dsq = abs((pb_ + PATM) ** 2 - (pn_ + PATM) ** 2)
                        k = max(dsq, 1e-6) / abs(q) ** EXPO
                elif abs(pb_ - pn_) < 0.005:
                    known = False       # no flow and no pressure difference: no K
        if not known and (state == "open" or vname in flagged):
            # no reading to be had: K from the latest campaign's balance
            k = est_valve.get(vname)
            if k is None:
                log("valve", vname, "without a reading or a campaign estimate: no flow")
        if k is not None:
            vnode.append(pkg.node_index[node])
            vpnb.append(pnb)
            vk.append(k)
            log("valve", vname, "K", k)

    # demand
    n = len(pkg.nodes)
    demand = np.zeros((24, n))
    for gname, node in pkg.governors:
        arr = pkg.gov_demand.get(gname)
        if arr is None or node not in pkg.node_index:
            continue
        for h in range(24):
            if arr[h] is not None:
                demand[h, pkg.node_index[node]] += arr[h]
    for cname, node, meter in pkg.customers:
        if node not in pkg.node_index:
            continue
        # the gas the meter registers, as a fraction of the gas through it: a
        # meter proved outside the 1 per cent of a sound meter is corrected,
        # a sound one is taken as it registers
        frac = 1.0
        row = field["meter"].get(meter)
        pct = fnum(row.get("registers_pct")) if row is not None else None
        if pct is not None and pct > 0:
            if abs(pct - 100.0) > 1.0:
                frac = pct / 100.0
        elif meter in est_meter and meter in flagged:
            frac = est_meter[meter]
        sums = [0.0] * 24
        cnts = [0] * 24
        for t, q in pkg.meter_rec.get(meter, {}).items():
            try:
                dte = datetime.date(int(t[0:4]), int(t[5:7]), int(t[8:10]))
                hh = int(t[11:13]) if len(t) >= 13 else 0
            except ValueError:
                continue
            if dte.weekday() >= 5:
                continue
            sums[hh % 24] += q
            cnts[hh % 24] += 1
        for h in range(24):
            if cnts[h]:
                demand[h, pkg.node_index[node]] += sums[h] / cnts[h] / frac
        log("customer", cname, meter, "frac", frac)

    # linepack
    cap_v = np.zeros(n)
    mf, mt = [], []
    for name, f, t, L, D, mat in pkg.mains:
        v = math.pi * (D / 1000.0) ** 2 * L / 8.0
        i, j = pkg.node_index[f], pkg.node_index[t]
        cap_v[i] += v
        cap_v[j] += v
        mf.append(i)
        mt.append(j)
    cap_v /= PATM

    prs_node = [pkg.node_index[p[1]] for p in pkg.prs if p[1] in pkg.node_index]
    prs_sp = [p[2] for p in pkg.prs if p[1] in pkg.node_index]
    prs_cap = [p[3] for p in pkg.prs if p[1] in pkg.node_index]
    model = dict(n=n, mf=mf, mt=mt, mk=mk, cap_v=cap_v, vnode=vnode, vpnb=vpnb, vk=vk,
                 prs_node=prs_node, prs_sp=prs_sp, prs_cap=prs_cap, demand=demand)
    return pkg, model


def run_model(model):
    net = Network(model["n"], model["mf"], model["mt"], model["mk"], model["cap_v"],
                  model["vnode"], model["vpnb"], model["vk"], model["prs_node"],
                  model["prs_sp"], model["prs_cap"], model["demand"])
    if model["prs_sp"]:
        p_init = np.full(model["n"], max(model["prs_sp"]))
    elif model["vpnb"]:
        p_init = np.full(model["n"], max(model["vpnb"]))
    else:
        p_init = np.full(model["n"], 5.0 + PATM)
    traj, stats = solve_design_day(net, p_init)
    log("stats", stats)
    return traj


def write_results(pkg, traj, out_csv):
    pmin = traj.min(axis=0)
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["governor", "min_pressure_barg"])
        for gname, node in pkg.governors:
            if node in pkg.node_index:
                w.writerow([gname, "%.4f" % (pmin[pkg.node_index[node]] - PATM)])
            else:
                w.writerow([gname, ""])


def main(argv):
    if len(argv) != 3:
        print("usage: designday.py PACKAGE_DIR OUT_CSV", file=sys.stderr)
        return 2
    pkg_dir, out_csv = argv[1], argv[2]
    pkg, model = build_model(pkg_dir)
    traj = run_model(model)
    write_results(pkg, traj, out_csv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
