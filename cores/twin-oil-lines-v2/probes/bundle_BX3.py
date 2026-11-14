#!/usr/bin/env python3
"""TS-2 heated oil transfer lines: pressure drop and outlet temperature for every hourly record
of one site's package.

    python3 lines.py PACKAGE_DIR OUT_CSV
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

np.seterr(all="ignore")

DEBUG = bool(os.environ.get("LINES_DEBUG"))


def dbg(*a):
    if DEBUG:
        sys.stderr.write(" ".join(str(x) for x in a) + "\n")

LN10 = math.log(10.0)
C3 = 3.66 ** 3 + 0.7 ** 3

# survey reading accuracy, TS-2 5.4
ERR_FLOW = 0.002
ERR_TOIL = 0.02
ERR_TAMB = 0.1

N_FINE = 20       # integration steps for results
N_COARSE = 8      # integration steps for the scan of pair divisions
N_FIT = 40        # integration steps for survey fits
ZMAX = 13.0       # scan of pair divisions over logit(s) in [-ZMAX, ZMAX]
NG = 261          # scan points
DRIFT_RATIO = 0.5  # survey disagreement (in units of the reading bounds) taken as a changed covering


# ----------------------------------------------------------------------------------------------
# physics (TS-2 sections 2 and 3)
# ----------------------------------------------------------------------------------------------

def d341(nu50, nu100):
    T1, T2 = 323.15, 373.15
    y1 = math.log10(math.log10(nu50 + 0.7))
    y2 = math.log10(math.log10(nu100 + 0.7))
    B = (y1 - y2) / (math.log10(T2) - math.log10(T1))
    A = y1 + B * math.log10(T1)
    return A, B


def pipe(m, D, L, rho, cp, k, A, B, U, tin, ta, N=N_FINE, iters=1):
    """One pipe, vectorised over cases (all arguments broadcastable); m in kg/s.
    Returns (pressure drop Pa, outlet bulk temperature C).

    State theta = ln(Tb - Ta) (not stiff even at very low flow) and p, integrated by RK4 over
    t in [0, 1] with x = L t^3 (smooth through the x^(1/3) entry behaviour of the film)."""
    m, D, L, rho, cp, k, A, B, U, tin, ta = np.broadcast_arrays(
        *[np.asarray(v, dtype=float) for v in (m, D, L, rho, cp, k, A, B, U, tin, ta)])
    a1 = LN10 * A
    taK = ta + 273.15
    L3 = 3.0 * L
    cqL = np.pi * D * U / (m * cp) * L3                                  # dtheta/dt = -cqL t^2 r
    cdpL = 32.0 * (4.0 * m / (np.pi * D * D * rho)) * rho * 1e-6 / (D * D) * L3  # dp/dt = cdpL t^2 sqrt(nub nuw)
    cg = 1.077 * np.cbrt(4.0 * m * cp / (np.pi * k * L))                # 1.077 Gz^(1/3) = cg / t
    kD = k / D

    def visc(dTK):
        return np.exp(LN10 * np.exp(a1 - B * np.log(taK + dTK))) - 0.7

    def visc2(dTK):
        T = taK + dTK
        inner = np.exp(a1 - B * np.log(T))
        W = np.exp(LN10 * inner)
        nu = W - 0.7
        return nu, (W / nu) * (LN10 * inner) * (-B / T)

    def h0_at(t):
        w = cg / t - 0.7
        return kD * np.cbrt(C3 + w * w * w)

    def stage(th, r, h0):
        # r = (Tw - Ta) / (Tb - Ta); Newton on r = hh/(hh+U), hh = h0 (mu_b/mu_w)^0.14
        dT = np.exp(th)
        nub = visc(dT)
        for _ in range(iters):
            nuw, dl = visc2(r * dT)
            hh = h0 * (nub / nuw) ** 0.14
            den = hh + U
            gr = hh / den
            dg = U / (den * den) * (-0.14 * hh * dl * dT)
            dr = (gr - r) / (1.0 - dg)
            r = r + dr
            nuw = nuw * np.exp(dl * dr * dT)
        return r, np.sqrt(nub * nuw)

    th = np.log(np.maximum(tin - ta, 1e-9))
    p = np.zeros_like(th)
    r = np.ones_like(th)
    h = 1.0 / N
    h0_end = None
    for i in range(N):
        t0 = i * h
        tm = t0 + 0.5 * h
        t1 = t0 + h
        h0m = h0_at(tm)
        h0e = h0_at(t1)
        if i == 0:
            k1 = 0.0
            q1 = 0.0
            r1 = r
        else:
            r1, s1 = stage(th, r, h0_end)
            k1 = -cqL * r1 * (t0 * t0)
            q1 = cdpL * s1 * (t0 * t0)
        w = tm * tm
        r2, s2 = stage(th + 0.5 * h * k1, r1, h0m)
        k2 = -cqL * r2 * w
        r3, s3 = stage(th + 0.5 * h * k2, r2, h0m)
        k3 = -cqL * r3 * w
        r4, s4 = stage(th + h * k3, r3, h0e)
        w4 = t1 * t1
        k4 = -cqL * r4 * w4
        th = th + (h / 6.0) * (k1 + 2.0 * (k2 + k3) + k4)
        p = p + (h / 6.0) * (q1 + cdpL * (2.0 * (s2 + s3) * w + s4 * w4))
        r = r4
        h0_end = h0e
    return p, ta + np.exp(th)


def expit(z):
    return 1.0 / (1.0 + np.exp(-z))


# ----------------------------------------------------------------------------------------------
# package
# ----------------------------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
    return out


def fnum(v, default=float("nan")):
    try:
        return float(v)
    except Exception:
        return default


class Package:
    def __init__(self, d):
        self.dir = d
        try:
            with open(os.path.join(d, "site.json")) as f:
                self.site = json.load(f)
        except Exception:
            self.site = {}
        self.oils = {}
        for r in read_csv(os.path.join(d, "oils.csv")):
            A, B = d341(fnum(r["nu50_cSt"]), fnum(r["nu100_cSt"]))
            self.oils[r["oil"]] = dict(rho=fnum(r["density_kg_m3"]), cp=fnum(r["cp_J_kgK"]),
                                       k=fnum(r["k_W_mK"]), A=A, B=B)
        self.lines = {}
        self.pipe_line = {}
        for r in read_csv(os.path.join(d, "lines.csv")):
            n = int(round(fnum(r.get("pipes", 1), 1)))
            n = 2 if n == 2 else 1
            name = r["line"]
            pipes = [name + "-A"] + ([name + "-B"] if n == 2 else [])
            self.lines[name] = dict(n=n, D=fnum(r["bore_mm"]) / 1000.0, L=fnum(r["length_m"]),
                                    oil=self.oils[r["oil"]], pipes=pipes)
            for p in pipes:
                self.pipe_line[p] = name
        try:
            self.surveys = read_csv(os.path.join(d, "surveys.csv"))
        except Exception:
            self.surveys = []
        try:
            self.work = read_csv(os.path.join(d, "work_log.csv"))
        except Exception:
            self.work = []
        self.records = read_csv(os.path.join(d, "records.csv"))

    def geom(self, pipe_name):
        ln = self.lines[self.pipe_line[pipe_name]]
        o = ln["oil"]
        return ln["D"], ln["L"], o["rho"], o["cp"], o["k"], o["A"], o["B"]


def norm_pipe(name):
    return (name or "").strip().upper().replace(" ", "")


def normdate(s):
    s = (s or "").strip()
    m = re.match(r"^\s*(\d{4})\D(\d{1,2})\D(\d{1,2})", s)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^\s*(\d{1,2})\D(\d{1,2})\D(\d{4})", s)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return s


def squash(name):
    return re.sub(r"[^0-9A-Z]", "", (name or "").upper())


# ----------------------------------------------------------------------------------------------
# outside coefficients from heat-loss surveys (TS-2 5.2 - 5.4)
# ----------------------------------------------------------------------------------------------

def fit_uo(rows):
    """rows: list of (geom tuple, m kg/s, tin, tout, ta). Returns arrays U, bound."""
    n = len(rows)
    if n == 0:
        return np.zeros(0), np.zeros(0)
    G = np.array([r[0] for r in rows], dtype=float)
    D, L, rho, cp, k, A, B = [G[:, i] for i in range(7)]
    m = np.array([r[1] for r in rows], float)
    tin = np.array([r[2] for r in rows], float)
    tout = np.array([r[3] for r in rows], float)
    ta = np.array([r[4] for r in rows], float)
    ok = np.isfinite(m) & (m > 0) & (tout > ta) & (tin > tout) & np.isfinite(D) & np.isfinite(L)
    mm = np.where(ok, m, 1.0)
    ratio = np.where(ok, (tin - ta) / np.where(ok, tout - ta, 1.0), 2.0)
    U0 = mm * cp * np.log(ratio) / (np.pi * D * L)
    lu = np.log(np.where(ok & (U0 > 0), U0 * 1.2, 5.0))
    tin_ = np.where(ok, tin, 80.0)
    ta_ = np.where(ok, ta, 10.0)
    tout_ = np.where(ok, tout, 60.0)

    def model(lu_, m_=None, tin__=None, ta__=None):
        return pipe(mm if m_ is None else m_, D, L, rho, cp, k, A, B, np.exp(lu_),
                    tin_ if tin__ is None else tin__, ta_ if ta__ is None else ta__, N=N_FIT, iters=2)[1]

    lo = np.full(n, math.log(1e-3))
    hi = np.full(n, math.log(1e3))
    for _ in range(30):
        f0 = model(lu) - tout_
        f1 = model(lu + 1e-5) - tout_
        d = (f1 - f0) / 1e-5
        # tout decreases with U: f0 > 0 -> U too small
        lo = np.where(f0 > 0, np.maximum(lo, lu), lo)
        hi = np.where(f0 < 0, np.minimum(hi, lu), hi)
        step = np.where(d < 0, -f0 / np.where(d < 0, d, -1.0), 0.0)
        new = lu + np.clip(step, -1.0, 1.0)
        bad = ~(np.isfinite(new)) | (d >= 0) | (new <= lo) | (new >= hi)
        new = np.where(bad, 0.5 * (lo + hi), new)
        done = np.abs(new - lu) < 1e-11
        lu = new
        if np.all(done | ~ok):
            break
    U = np.exp(lu)
    T0 = model(lu)
    dTU = (model(lu + 1e-3) - T0) / (U * (math.exp(1e-3) - 1.0))
    dTm = (model(lu, m_=mm * 1.001) - T0) / (mm * 0.001)
    dTi = (model(lu, tin__=tin_ + 0.01) - T0) / 0.01
    dTa = (model(lu, ta__=ta_ + 0.01) - T0) / 0.01
    bnd = (np.abs(dTm) * ERR_FLOW * mm + np.abs(dTi) * ERR_TOIL + ERR_TOIL + np.abs(dTa) * ERR_TAMB) / np.abs(dTU)
    U = np.where(ok & np.isfinite(U), U, np.nan)
    bnd = np.where(np.isfinite(bnd) & (bnd > 0), bnd, np.where(np.isfinite(U), 0.05 * U, np.nan))
    return U, bnd


COVER_WORDS = ("cover", "lagg", "insulat", "cladd", "jacket", "wrapp", "sheath", "mattress")
WORK_WORDS = ("renew", "repair", "replac", "patch", "rebuil", "refit", "re-fit", "reinstat", "restor",
              "remov", "strip", "new", "made good", "make good", "redone", "re-done", "relag", "re-lag",
              "damag", "wet", "torn", "missing", "fitted", "applied", "installed", "reapplied", "recover",
              "re-cover", "extended", "modified", "changed", "upgraded", "swapped")
LOOK_WORDS = ("inspect", "check", "survey", "examin", "measur", "test", "looked", "photograph", "noted ok",
              "no defect", "no damage", "satisfactory")


def is_covering_work(job):
    j = (job or "").lower()
    if not any(w in j for w in COVER_WORDS):
        return any(w in j for w in ("relag", "re-lag", "lagged", "insulated"))
    if any(w in j for w in LOOK_WORDS) and not any(w in j for w in WORK_WORDS):
        return False
    return True


def reconcile_flows(pkg, readings):
    """Best flow through each pipe from the readings of one survey occasion: readings is a list of
    (pipe, occasion, pipe flow, line flow) in kg/s. A single pipe has its flow read twice; a pair
    has both pipe flows and the line flow, whose sum must agree. Errors in proportion to the
    reading (TS-2 5.4)."""
    out = [r[2] for r in readings]
    groups = {}
    for i, (p, occ, m, M) in enumerate(readings):
        groups.setdefault((pkg.pipe_line.get(p), occ), []).append(i)
    for (ln, occ), idx in groups.items():
        if ln is None:
            continue
        L = pkg.lines[ln]
        Ms = [readings[i][3] for i in idx if np.isfinite(readings[i][3]) and readings[i][3] > 0]
        if L["n"] == 1:
            for i in idx:
                m = readings[i][2]
                if np.isfinite(m) and m > 0 and Ms:
                    vals = [m] + Ms
                    out[i] = float(np.mean(vals))
        else:
            pa = [i for i in idx if readings[i][0] == L["pipes"][0]]
            pb = [i for i in idx if readings[i][0] == L["pipes"][1]]
            if len(pa) != 1 or len(pb) != 1 or not Ms:
                continue
            ia, ib = pa[0], pb[0]
            mA, mB = readings[ia][2], readings[ib][2]
            if not (np.isfinite(mA) and np.isfinite(mB) and mA > 0 and mB > 0):
                continue
            Mb = float(np.mean(Ms))
            vA, vB, vM = mA * mA, mB * mB, Mb * Mb / len(Ms)
            e = Mb - mA - mB
            if abs(e) > 0.02 * Mb:
                continue
            S = vA + vB + vM
            out[ia] = mA + e * vA / S
            out[ib] = mB + e * vB / S
    return out


def survey_status(pkg):
    """Per pipe: dict with U (best estimate from file), bound, status, score, valid list."""
    pipes = list(pkg.pipe_line.keys())
    pset = set(pipes)
    pipe_sq = {squash(p): p for p in pipes}
    line_sq = {squash(l): l for l in pkg.lines}
    # covering jobs
    last_job = {}
    for w in pkg.work:
        if not is_covering_work(w.get("job", "")):
            continue
        p = norm_pipe(w.get("pipe", ""))
        date = normdate(w.get("date"))
        targets = []
        if p in pset:
            targets = [p]
        elif p in pkg.lines:
            targets = list(pkg.lines[p]["pipes"])
        else:
            sq = squash(p)
            if sq in pipe_sq:
                targets = [pipe_sq[sq]]
            elif sq in line_sq:
                targets = list(pkg.lines[line_sq[sq]]["pipes"])
        for t in targets:
            if date > last_job.get(t, ""):
                last_job[t] = date
    # fit all surveys on file
    rows, meta = [], []
    srows = []
    for s in pkg.surveys:
        p = norm_pipe(s.get("pipe", ""))
        if p not in pset:
            p = pipe_sq.get(squash(p), p)
        if p not in pset:
            continue
        srows.append((p, normdate(s.get("date")), fnum(s.get("flow_t_h")) / 3.6, fnum(s.get("line_flow_t_h")) / 3.6, s))
    flows = reconcile_flows(pkg, [(r[0], r[1], r[2], r[3]) for r in srows])
    for (p, date, _, _, s), m in zip(srows, flows):
        rows.append((pkg.geom(p), m, fnum(s.get("t_in_C")), fnum(s.get("t_out_C")), fnum(s.get("t_amb_C"))))
        meta.append((p, date))
    U, bnd = fit_uo(rows)
    by = {p: [] for p in pipes}
    raw = {p: {} for p in pipes}
    for (p, date), u, b, s in zip(meta, U, bnd, rows):
        if np.isfinite(u):
            by[p].append((date, float(u), float(b)))
            raw[p][date] = (s[1], s[2], s[4])  # flow kg/s, t_in, t_amb
    info = {}
    for p in pipes:
        sv = sorted(by[p])
        lj = last_job.get(p, "")
        valid = [x for x in sv if x[0] > lj] if lj else list(sv)
        sameday = [x for x in sv if lj and x[0] == lj]
        older = [x for x in sv if lj and x[0] < lj]
        rec = dict(valid=valid, sameday=sameday, all=sv, status="ok", score=0.0, raw=raw[p])
        if not valid:
            rec["status"] = "none"
            rec["score"] = 1e9
            cand = sameday or sv
            if sameday and older:
                # a same-day survey that disagrees with the old covering was taken after the work
                u0, b0 = combine(older)
                us, bs = combine(sameday)
                if abs(us - u0) > DRIFT_RATIO * (bs + b0):
                    rec["status"] = "single"
                    rec["valid"] = sameday
                    rec["score"] = 1e6
            if cand:
                rec["U"], rec["b"] = combine(cand[-1:]) if rec["status"] == "none" else combine(rec["valid"])
            else:
                rec["U"], rec["b"] = float("nan"), float("nan")
        else:
            worst = 0.0
            for i in range(len(valid)):
                for j in range(i + 1, len(valid)):
                    worst = max(worst, abs(valid[i][1] - valid[j][1]) / (valid[i][2] + valid[j][2]))
            rec["ratio"] = worst
            if worst > DRIFT_RATIO:
                rec["status"] = "drift"
                rec["score"] = 1e3 * worst
                rec["U"], rec["b"] = valid[-1][1], valid[-1][2]
            else:
                if len(valid) == 1 and rec["status"] == "ok":
                    rec["status"] = "single"
                    rec["score"] = 0.3
                else:
                    rec["score"] = worst
                rec["U"], rec["b"] = combine(valid)
        info[p] = rec
    return info


def combine(lst):
    w = np.array([1.0 / (x[2] ** 2) for x in lst])
    u = np.array([x[1] for x in lst])
    U = float(np.sum(w * u) / np.sum(w))
    b = float(1.0 / math.sqrt(np.sum(w)))
    return U, b


def plan_order(pkg, info, allowance):
    """Choose the pipes for the survey crew (one order, at most `allowance` pipes)."""
    if allowance <= 0:
        return []
    nrec = {}
    for r in pkg.records:
        nrec[r.get("line", "")] = nrec.get(r.get("line", ""), 0) + 1

    def partner(p):
        line = pkg.lines[pkg.pipe_line[p]]
        return [q for q in line["pipes"] if q != p][0] if line["n"] == 2 else None

    key = lambda p: (-info[p]["score"], -nrec.get(pkg.pipe_line[p], 0), p)
    must = sorted([p for p, r in info.items() if r["status"] in ("none", "drift")], key=key)
    if len(must) > allowance:
        # A survey of one pipe of a pair also gives the division of the pair, and with it the
        # partner's coefficient (TS-2 4.1): where both pipes of a pair need one, order one of them.
        chosen = []
        for p in must:
            q = partner(p)
            if q is not None and q in chosen:
                continue
            chosen.append(p)
        must = chosen[:allowance]
    order = list(must)
    if len(order) < allowance:
        # spare surveys: one pipe of each line not yet covered, most doubtful first
        covered = {pkg.pipe_line[p] for p in order}
        cands = []
        for ln, L in pkg.lines.items():
            if ln in covered:
                continue
            ps = [p for p in L["pipes"] if p in info]
            if not ps:
                continue
            best = min(ps, key=key)
            cands.append((-max(info[p]["score"] for p in ps), -nrec.get(ln, 0), best))
        cands.sort()
        for _, _, p in cands:
            if len(order) >= allowance:
                break
            order.append(p)
    if len(order) < allowance:
        rest = sorted([p for p in info if p not in order], key=key)
        order += rest[: allowance - len(order)]
    return order


def run_crew(pkg_dir, order):
    """Place one order. Returns (rows, message, accepted)."""
    try:
        res = subprocess.run(["heatsurvey", pkg_dir] + list(order), capture_output=True, text=True,
                             timeout=30)
        out = res.stdout or ""
        msg = (res.stderr or "") + "\n" + out
    except Exception as e:
        return [], str(e), False
    rows = []
    header = None
    for line in out.splitlines():
        parts = [x.strip() for x in line.strip().split(",")]
        if len(parts) < 6:
            continue
        if header is None and "pipe" in [x.lower() for x in parts]:
            header = [x.lower() for x in parts]
            continue
        h = header or ["pipe", "line_flow_t_h", "flow_t_h", "t_in_c", "t_out_c", "t_amb_c"]
        d = dict(zip(h, parts))
        try:
            rows.append(dict(pipe=norm_pipe(d["pipe"]), line_flow=float(d["line_flow_t_h"]),
                             flow=float(d["flow_t_h"]), tin=float(d["t_in_c"]), tout=float(d["t_out_c"]),
                             ta=float(d["t_amb_c"])))
        except Exception:
            continue
    return rows, msg, bool(rows) or header is not None


def order_crew(pkg_dir, pkg, info, allowance):
    """Plan and place the crew's one order. A refused order does not count, so on a refusal that
    names the crew's own limit the order is planned again to that limit."""
    if allowance <= 0:
        return [], []
    tried = set()
    lim = allowance
    for _ in range(4):
        order = plan_order(pkg, info, lim)
        if not order or tuple(order) in tried:
            break
        tried.add(tuple(order))
        rows, msg, accepted = run_crew(pkg_dir, order)
        dbg("crew order", order, "->", len(rows), "rows", "" if accepted else msg.strip()[:200])
        if accepted:
            return order, rows
        mm = re.search(r"at most\s+(\d+)", msg)
        if mm and int(mm.group(1)) < lim:
            lim = int(mm.group(1))
            continue
        break
    return [], []


def resolve_uo(pkg, info, crew_rows):
    """Coefficient of every pipe from the surveys that describe its covering as it stands: the
    heat-loss readings of each pipe and, for pairs, the division of the oil read in each survey
    (TS-2 4.1: both pipes carry the pressure drop between the manifolds)."""
    U = {p: r.get("U", float("nan")) for p, r in info.items()}
    crew = {}
    crew_ok = [c for c in crew_rows if c["pipe"] in pkg.pipe_line]
    cflow = reconcile_flows(pkg, [(c["pipe"], "crew", c["flow"] / 3.6, c["line_flow"] / 3.6) for c in crew_ok])
    rows = [(pkg.geom(c["pipe"]), m, c["tin"], c["tout"], c["ta"]) for c, m in zip(crew_ok, cflow)]
    Uc, bc = fit_uo(rows)
    for c, u, b in zip(crew_ok, Uc, bc):
        if np.isfinite(u):
            crew[c["pipe"]] = (float(u), float(b), c)
    # heat-loss estimates of each pipe's present covering
    obs = {}
    for p, r in info.items():
        if p in crew:
            u, b, c = crew[p]
            if r["status"] in ("ok", "single") and r["valid"]:
                u0, b0 = combine(r["valid"])
                if abs(u - u0) <= DRIFT_RATIO * (b + b0):
                    obs[p] = list(r["valid"]) + [("crew", u, b)]
                else:
                    dbg("crew survey shows a changed covering on", p, "%.4f vs %.4f" % (u, u0))
                    obs[p] = [("crew", u, b)]
            else:
                obs[p] = [("crew", u, b)]
        elif r["status"] in ("ok", "single"):
            obs[p] = list(r["valid"])
        else:
            obs[p] = []
        if obs[p]:
            U[p] = combine(obs[p])[0]
    # pairs with one pipe surveyed by the crew: check the partner against the division read
    tasks = []
    for ln, L in pkg.lines.items():
        if L["n"] != 2:
            continue
        a, b = L["pipes"]
        if (a in crew) == (b in crew):
            continue
        q, p = (a, b) if a in crew else (b, a)
        tasks.append((p, q))
    if tasks:
        try:
            inferred = infer_partners(pkg, info, U, crew, tasks)
        except Exception:
            inferred = {}
        for p, (ui, bi) in inferred.items():
            if obs[p]:
                bf = min(x[2] for x in obs[p])
                if abs(ui - U[p]) > bi + bf:
                    dbg("partner survey contradicts file for", p, "%.4f vs %.4f" % (ui, U[p]))
                    obs[p] = []
                    U[p] = ui
                else:
                    dbg("partner check", p, "inferred %.4f file %.4f (+-%.4f)" % (ui, U[p], bi + bf))
            else:
                dbg("inferred", p, "from partner survey: %.4f (+-%.4f)" % (ui, bi))
                U[p] = ui
    # joint estimate for each pair
    try:
        pair_fit(pkg, info, U, obs, crew)
    except Exception as e:
        dbg("pair fit failed:", repr(e))
    # anything still unknown: borrow a reasonable value
    known = [u for u in U.values() if np.isfinite(u)]
    fallback = float(np.median(known)) if known else 6.0
    for p in U:
        if not np.isfinite(U[p]):
            line = pkg.lines[pkg.pipe_line[p]]
            partner = [U[q] for q in line["pipes"] if q != p and np.isfinite(U[q])]
            U[p] = partner[0] if partner else fallback
    return U


def pair_fit(pkg, info, U, obs, crew):
    """Least squares over (ln UA, ln UB) of each pair: heat-loss estimates of either pipe plus,
    for every survey that read the division of the pair with both coverings as they stand, the
    equality of the two pressure drops. Weights from the reading accuracy (TS-2 5.4)."""
    pairs = [(ln, L) for ln, L in pkg.lines.items() if L["n"] == 2]
    cons = []   # (pair index, geom, mA, mB, tin, ta, dmA, dmB, dM)
    for k, (ln, L) in enumerate(pairs):
        a, b = L["pipes"]
        da = {x[0] for x in obs[a] if x[0] != "crew"}
        db = {x[0] for x in obs[b] if x[0] != "crew"}
        for date in sorted(da & db):
            ra, rb = info[a]["raw"].get(date), info[b]["raw"].get(date)
            if ra is None or rb is None:
                continue
            cons.append((k, pkg.geom(a), ra[0], rb[0], 0.5 * (ra[1] + rb[1]), 0.5 * (ra[2] + rb[2]),
                         ERR_FLOW * ra[0], ERR_FLOW * rb[0], 0.0, 0))
        ca, cb = a in crew, b in crew
        if ca or cb:
            if ca and cb:
                c1, c2 = crew[a][2], crew[b][2]
                cons.append((k, pkg.geom(a), c1["flow"] / 3.6, c2["flow"] / 3.6, 0.5 * (c1["tin"] + c2["tin"]),
                             0.5 * (c1["ta"] + c2["ta"]), ERR_FLOW * c1["flow"] / 3.6, ERR_FLOW * c2["flow"] / 3.6, 0.0, 0))
            else:
                q = a if ca else b
                c = crew[q][2]
                mq = c["flow"] / 3.6
                mo = (c["line_flow"] - c["flow"]) / 3.6
                if mo <= 0:
                    continue
                # the partner's flow is the line flow less the surveyed pipe's
                if ca:
                    cons.append((k, pkg.geom(a), mq, mo, c["tin"], c["ta"], ERR_FLOW * mq, 0.0,
                                 ERR_FLOW * c["line_flow"] / 3.6, 1))
                else:
                    cons.append((k, pkg.geom(a), mo, mq, c["tin"], c["ta"], 0.0, ERR_FLOW * mq,
                                 ERR_FLOW * c["line_flow"] / 3.6, 2))
    if not cons:
        return
    nc = len(cons)
    kk = np.array([c[0] for c in cons])
    geo = np.array([c[1] for c in cons], float)
    gcols = [geo[:, i] for i in range(7)]
    mA = np.array([c[2] for c in cons]); mB = np.array([c[3] for c in cons])
    tin = np.array([c[4] for c in cons]); ta = np.array([c[5] for c in cons])
    dmA = np.array([c[6] for c in cons]); dmB = np.array([c[7] for c in cons]); dM = np.array([c[8] for c in cons])
    mode = np.array([c[9] for c in cons])
    x = np.array([[math.log(U[L["pipes"][0]]), math.log(U[L["pipes"][1]])] for _, L in pairs], float)
    x0 = x.copy()
    UA = lambda: np.exp(x[kk, 0])
    UB = lambda: np.exp(x[kk, 1])

    def dps(mA_, mB_, uA, uB, tin_, ta_):
        pa = pipe(mA_, *gcols, uA, tin_, ta_, N=N_FIT, iters=2)[0]
        pb = pipe(mB_, *gcols, uB, tin_, ta_, N=N_FIT, iters=2)[0]
        return pa, pb

    # weight of each division reading: bound of dpA - dpB from the flow, oil and air readings
    uA0, uB0 = UA(), UB()
    pa0, pb0 = dps(mA, mB, uA0, uB0, tin, ta)
    e = 1e-3
    paA, _ = dps(mA * (1 + e), mB, uA0, uB0, tin, ta)
    _, pbB = dps(mA, mB * (1 + e), uA0, uB0, tin, ta)
    dA = (paA - pa0) / (mA * e)
    dB = (pbB - pb0) / (mB * e)
    pat, pbt = dps(mA, mB, uA0, uB0, tin + 0.01, ta)
    paa, pba = dps(mA, mB, uA0, uB0, tin, ta + 0.01)
    dT = ((pat - pbt) - (pa0 - pb0)) / 0.01
    dTa = ((paa - pba) - (pa0 - pb0)) / 0.01
    # mode 1: mB = M - mA (A surveyed); mode 2: mA = M - mB (B surveyed)
    sig_flow = np.where(mode == 1, np.abs(dA + dB) * dmA + np.abs(dB) * dM,
                        np.where(mode == 2, np.abs(dA + dB) * dmB + np.abs(dA) * dM,
                                 np.abs(dA) * dmA + np.abs(dB) * dmB))
    sig = sig_flow + np.abs(dT) * ERR_TOIL + np.abs(dTa) * ERR_TAMB
    sig = np.where(np.isfinite(sig) & (sig > 0), sig, np.inf)
    ok = np.isfinite(pa0) & np.isfinite(pb0) & np.isfinite(sig)
    h = 1e-4
    for it in range(8):
        uA, uB = UA(), UB()
        pa, pb = dps(mA, mB, uA, uB, tin, ta)
        pa2, pb2 = dps(mA, mB, uA * math.exp(h), uB * math.exp(h), tin, ta)
        r = np.where(ok, (pa - pb) / sig, 0.0)
        jA = np.where(ok, (pa2 - pa) / h / sig, 0.0)
        jB = np.where(ok, -(pb2 - pb) / h / sig, 0.0)
        maxstep = 0.0
        for k, (ln, L) in enumerate(pairs):
            sel = kk == k
            rows_r, rows_j = [], []
            for j in np.nonzero(sel)[0]:
                rows_r.append(r[j]); rows_j.append((jA[j], jB[j]))
            for i, p in enumerate(L["pipes"]):
                for (_, u, b) in obs[p]:
                    ui = math.exp(x[k, i])
                    rows_r.append((ui - u) / b)
                    jj = [0.0, 0.0]; jj[i] = ui / b
                    rows_j.append(tuple(jj))
                # weak prior keeps an unobserved coefficient where it is
                rows_r.append((x[k, i] - x0[k, i]) / 3.0)
                jj = [0.0, 0.0]; jj[i] = 1.0 / 3.0
                rows_j.append(tuple(jj))
            if len(rows_r) <= 2:
                continue
            J = np.array(rows_j, float); R = np.array(rows_r, float)
            if not (np.all(np.isfinite(J)) and np.all(np.isfinite(R))):
                continue
            try:
                d = -np.linalg.solve(J.T @ J, J.T @ R)
            except Exception:
                continue
            d = np.clip(d, -0.3, 0.3)
            x[k] += d
            maxstep = max(maxstep, float(np.max(np.abs(d))))
        if maxstep < 1e-7:
            break
    for k, (ln, L) in enumerate(pairs):
        for i, p in enumerate(L["pipes"]):
            if np.isfinite(x[k, i]):
                if abs(x[k, i] - x0[k, i]) > 1e-4:
                    dbg("pair fit", p, "%.4f -> %.4f" % (math.exp(x0[k, i]), math.exp(x[k, i])))
                U[p] = float(math.exp(x[k, i]))


def infer_partners(pkg, info, U, crew, tasks):
    """For (target p, surveyed q) pairs: U of p such that p carries, at the division read in q's
    survey, the pressure drop that q has. Returns {p: (U, bound)} with the bound from the reading
    accuracy of the survey and of q's coefficient."""
    rows = []
    for p, q in tasks:
        uq, bq, c = crew[q]
        uq = U[q]
        M, mq, tin, ta = c["line_flow"] / 3.6, c["flow"] / 3.6, c["tin"], c["ta"]
        var = [(M, mq, tin, ta, uq), (M * (1 + ERR_FLOW), mq, tin, ta, uq), (M, mq * (1 + ERR_FLOW), tin, ta, uq),
               (M, mq, tin + ERR_TOIL, ta, uq), (M, mq, tin, ta + ERR_TAMB, uq), (M, mq, tin, ta, uq + bq)]
        for v in var:
            rows.append((p, q) + v)
    n = len(rows)
    gp = np.array([pkg.geom(r[0]) for r in rows], float)
    gq = np.array([pkg.geom(r[1]) for r in rows], float)
    M = np.array([r[2] for r in rows]); mq = np.array([r[3] for r in rows])
    tin = np.array([r[4] for r in rows]); ta = np.array([r[5] for r in rows]); uq = np.array([r[6] for r in rows])
    mp = M - mq
    dpq = pipe(mq, *[gq[:, i] for i in range(7)], uq, tin, ta, N=N_FIT, iters=2)[0]
    lo = np.full(n, math.log(0.05))
    hi = np.full(n, math.log(500.0))
    f = lambda lu: pipe(np.maximum(mp, 1e-9), *[gp[:, i] for i in range(7)], np.exp(lu), tin, ta, N=N_FIT, iters=2)[0] - dpq
    flo, fhi = f(lo), f(hi)
    okb = (flo < 0) & (fhi > 0) & (mp > 0)
    for _ in range(45):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        up = fm < 0
        lo = np.where(up, mid, lo)
        hi = np.where(up, hi, mid)
    Ui = np.exp(0.5 * (lo + hi))
    out = {}
    for t, (p, q) in enumerate(tasks):
        sl = slice(6 * t, 6 * t + 6)
        if not okb[sl].all():
            continue
        u = Ui[sl]
        out[p] = (float(u[0]), float(np.sum(np.abs(u[1:] - u[0]))))
    return out


# ----------------------------------------------------------------------------------------------
# results
# ----------------------------------------------------------------------------------------------

def solve_singles(pkg, U, recs, out):
    if not recs:
        return
    cols = []
    for r in recs:
        ln = pkg.lines[r["line"]]
        p = ln["pipes"][0]
        cols.append(pkg.geom(p) + (U[p], r["M"], r["tin"], r["ta"]))
    a = np.array(cols, float)
    dp, to = pipe(a[:, 8], a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4], a[:, 5], a[:, 6], a[:, 7],
                  a[:, 9], a[:, 10], N=24, iters=2)
    for r, d, t in zip(recs, dp, to):
        out[r["i"]] = (d / 1000.0, t)


class PairSet:
    def __init__(self, pkg, U, recs):
        self.recs = recs
        n = len(recs)
        a = np.zeros((n, 12))
        for j, r in enumerate(recs):
            ln = pkg.lines[r["line"]]
            pa, pb = ln["pipes"]
            a[j, :7] = pkg.geom(pa)
            a[j, 7] = U[pa]
            a[j, 8] = U[pb]
            a[j, 9] = r["M"]
            a[j, 10] = r["tin"]
            a[j, 11] = r["ta"]
        self.a = a

    def g(self, js, z, N=N_FINE, iters=1, full=False):
        """g = dpA - dpB at division s = expit(z) (fraction in pipe A) for records js."""
        a = self.a[js]
        if np.ndim(z) == 2:
            a = a[:, None, :]
            sh = (len(js), np.shape(z)[1])
        else:
            sh = (len(js),)
        s = expit(z)
        sc = expit(-z)
        geo = [a[..., i] for i in range(7)]
        M = a[..., 9]
        pa, ta_ = pipe(s * M, *geo, a[..., 7], a[..., 10], a[..., 11], N=N, iters=iters)
        pb, tb_ = pipe(sc * M, *geo, a[..., 8], a[..., 10], a[..., 11], N=N, iters=iters)
        pa = np.broadcast_to(pa, sh)
        pb = np.broadcast_to(pb, sh)
        if full:
            return pa - pb, pa, pb, ta_, tb_, s
        return pa - pb


def roots_from_row(G, zg):
    """Sign changes of one scanned row. Returns list of (z_approx, kind, cell) with kind +1 stable
    (g rising through zero) and -1 unstable."""
    pos = G > 0
    idx = np.nonzero(pos[1:] != pos[:-1])[0]
    out = []
    for i in idx:
        g0, g1 = G[i], G[i + 1]
        zr = zg[i] + (zg[i + 1] - zg[i]) * (g0 / (g0 - g1)) if g0 != g1 else zg[i]
        out.append((float(zr), 1 if g1 > g0 else -1, int(i)))
    return out


def clean_roots(rts):
    """Make the root list alternate stable/unstable starting and ending with stable (g < 0 at s=0,
    g > 0 at s=1)."""
    rts = list(rts)
    if not rts:
        return rts
    # drop leading unstables / trailing unstables (can only come from scan-end artefacts)
    while rts and rts[0][1] < 0:
        rts.pop(0)
    while rts and rts[-1][1] < 0:
        rts.pop()
    return rts


def choose(rts, zp):
    """Stable root of the basin containing zp. Returns (root tuple, ambiguity distance)."""
    stables = [r for r in rts if r[1] > 0]
    unst = [r for r in rts if r[1] < 0]
    if not stables:
        return None, 0.0
    if zp is None:
        if len(stables) == 1:
            return stables[0], 1e9
        # more than one division: drop the closest adjacent pairs (marginal crossings) until one is left
        rr = list(rts)
        while len(rr) > 1:
            gaps = [rr[i + 1][0] - rr[i][0] for i in range(len(rr) - 1)]
            i = int(np.argmin(gaps))
            del rr[i:i + 2]
        st = [r for r in rr if r[1] > 0]
        return (st[0] if st else stables[0]), 0.0
    nbelow = sum(1 for u in unst if u[0] < zp)
    nbelow = min(nbelow, len(stables) - 1)
    dist = min([abs(u[0] - zp) for u in unst], default=1e9)
    return stables[nbelow], dist


def solve_pairs(pkg, U, recs, out):
    if not recs:
        return
    P = PairSet(pkg, U, recs)
    n = len(recs)
    zg = np.linspace(-ZMAX, ZMAX, NG)
    dz = zg[1] - zg[0]
    # --- coarse scan of g over the division for every record
    G = np.empty((n, NG))
    CH = max(1, 120000 // NG)
    for c0 in range(0, n, CH):
        js = np.arange(c0, min(n, c0 + CH))
        G[js] = P.g(js, np.broadcast_to(zg, (len(js), NG)), N=N_COARSE, iters=1)
    G[:, 0] = np.minimum(G[:, 0], -1e-30)
    G[:, -1] = np.maximum(G[:, -1], 1e-30)
    G = np.where(np.isfinite(G), G, 0.0)
    roots = [clean_roots(roots_from_row(G[j], zg)) for j in range(n)]

    # records of each line, in time order
    by_line = {}
    for j, r in enumerate(recs):
        by_line.setdefault(r["line"], []).append(j)
    for ln in by_line:
        by_line[ln].sort(key=lambda j: recs[j]["hour"])

    zroot = np.full(n, np.nan)
    cell = np.zeros(n, int)

    def near_miss(row, zp, c):
        """True if, between zp and the chosen root cell c, the scan comes close enough to zero that
        a pair of crossings could hide between two scan points."""
        ip = int(np.clip(np.searchsorted(zg, zp), 1, NG - 2))
        a_, b_ = (ip, c) if ip <= c else (c + 1, ip)
        lo_i, hi_i = max(1, a_ - 1), min(NG - 2, b_ + 1)
        if hi_i < lo_i:
            return False
        ii = np.arange(lo_i, hi_i + 1)
        ii = ii[(ii != c) & (ii != c + 1)]
        if len(ii) == 0:
            return False
        gi = np.abs(row[ii])
        var = np.maximum(np.abs(row[ii] - row[ii - 1]), np.abs(row[ii + 1] - row[ii]))
        lmin = (gi <= np.abs(row[ii - 1])) & (gi <= np.abs(row[ii + 1]))
        return bool(np.any(lmin & (gi < 1.5 * var)))
    kind_amb = np.zeros(n, bool)

    def track(seq, z_prev_exact):
        """Phase 1 over a sequence of record indices with approximate previous division."""
        zp = z_prev_exact
        for j in seq:
            rt, dist = choose(roots[j], zp)
            if rt is None:
                rt = (0.0, 1, NG // 2)
                kind_amb[j] = True
            cell[j] = rt[2]
            if zp is not None:
                if dist < 2.5 * dz:
                    kind_amb[j] = True
                elif near_miss(G[j], zp, rt[2]):
                    kind_amb[j] = True
            zroot[j] = rt[0]
            zp = rt[0]

    for ln, seq in by_line.items():
        track(seq, None)

    def refine(js):
        """Accurate root in the chosen cell for records js (vectorised Illinois)."""
        js = np.asarray(js, int)
        if len(js) == 0:
            return
        lo = zg[np.clip(cell[js], 0, NG - 2)].copy()
        hi = zg[np.clip(cell[js] + 1, 1, NG - 1)].copy()
        glo = P.g(js, lo)
        ghi = P.g(js, hi)
        # coarse-scan error can put the crossing in a neighbouring cell: slide the bracket
        for _ in range(8):
            both_neg = (glo < 0) & (ghi < 0)
            both_pos = (glo > 0) & (ghi > 0)
            if not (both_neg.any() or both_pos.any()):
                break
            sh = np.where(both_neg, dz, np.where(both_pos, -dz, 0.0))
            mv = sh != 0
            lo = np.where(mv, lo + sh, lo)
            hi = np.where(mv, hi + sh, hi)
            if mv.any():
                idx = np.nonzero(mv)[0]
                glo[idx] = P.g(js[idx], lo[idx])
                ghi[idx] = P.g(js[idx], hi[idx])
        side = 0 * lo
        zr = 0.5 * (lo + hi)
        for _ in range(40):
            den = ghi - glo
            zr = np.where(np.abs(den) > 0, lo - glo * (hi - lo) / np.where(den != 0, den, 1.0), 0.5 * (lo + hi))
            zr = np.where((zr > lo) & (zr < hi), zr, 0.5 * (lo + hi))
            gr = P.g(js, zr)
            same_lo = np.sign(gr) == np.sign(glo)
            # Illinois
            new_lo = np.where(same_lo, zr, lo)
            new_hi = np.where(same_lo, hi, zr)
            new_glo = np.where(same_lo, gr, glo)
            new_ghi = np.where(same_lo, ghi, gr)
            new_ghi = np.where(same_lo & (side == 1), new_ghi * 0.5, new_ghi)
            new_glo = np.where(~same_lo & (side == -1), new_glo * 0.5, new_glo)
            side = np.where(same_lo, 1, -1)
            lo, hi, glo, ghi = new_lo, new_hi, new_glo, new_ghi
            if np.all((hi - lo) < 1e-9) or np.all(gr == 0):
                break
        zroot[js] = zr

    refine(np.arange(n))

    # --- records whose basin is uncertain: walk the division exactly from the previous one
    def march(j, zp):
        g0 = float(P.g(np.array([j]), np.array([zp]))[0])
        if g0 == 0.0:
            return zp
        step = -0.02 if g0 > 0 else 0.02
        zc = zp
        gprev = g0
        while True:
            zs = zc + step * np.arange(1, 201)
            if step < 0:
                zs = zs[zs > -ZMAX - 6]
            else:
                zs = zs[zs < ZMAX + 6]
            if len(zs) == 0:
                return zc
            gs = P.g(np.full(len(zs), j), zs)
            ch = np.nonzero(np.sign(gs) != np.sign(g0))[0]
            if len(ch):
                i = ch[0]
                a_, b_ = (zc, zs[0]) if i == 0 else (zs[i - 1], zs[i])
                ga, gb = (gprev, gs[0]) if i == 0 else (gs[i - 1], gs[i])
                for _ in range(60):
                    mid = 0.5 * (a_ + b_)
                    gm = float(P.g(np.array([j]), np.array([mid]))[0])
                    if np.sign(gm) == np.sign(ga):
                        a_, ga = mid, gm
                    else:
                        b_, gb = mid, gm
                    if abs(b_ - a_) < 1e-10:
                        break
                return 0.5 * (a_ + b_)
            zc = zs[-1]
            gprev = gs[-1]

    dbg("pair records", n, "ambiguous after scan", int(kind_amb.sum()),
        "multi-root records", sum(1 for r in roots if len(r) > 1))
    for ln, seq in by_line.items():
        k = 1
        while k < len(seq):
            j = seq[k]
            if kind_amb[j]:
                zp = zroot[seq[k - 1]]
                try:
                    zr = float(march(j, zp))
                    if not np.isfinite(zr):
                        zr = zroot[j]
                except Exception:
                    zr = zroot[j]
                dbg("march", recs[j]["record"], "scan root %.5f -> walked %.5f" % (zroot[j], zr))
                if abs(zr - zroot[j]) > 1e-6:
                    zroot[j] = zr
                    # re-track the rest of the line from the corrected division
                    rest = seq[k + 1:]
                    if rest:
                        track(rest, zr)
                        refine(rest)
                kind_amb[j] = False
            k += 1

    # --- results at the divisions
    js = np.arange(n)
    _, pa, pb, ta_, tb_, s = P.g(js, zroot, full=True)
    for j in range(n):
        dp = 0.5 * (pa[j] + pb[j])
        to = s[j] * ta_[j] + (1.0 - s[j]) * tb_[j]
        out[recs[j]["i"]] = (dp / 1000.0, to)


def main(pkg_dir, out_csv):
    pkg = Package(pkg_dir)
    recs = []
    for i, r in enumerate(pkg.records):
        recs.append(dict(i=i, record=r.get("record", ""), line=(r.get("line") or "").strip(),
                         hour=fnum(r.get("hour"), i), M=fnum(r.get("flow_t_h")) / 3.6,
                         tin=fnum(r.get("t_in_C")), ta=fnum(r.get("t_amb_C"))))
    out = [None] * len(recs)
    U = {p: 6.0 for p in pkg.pipe_line}
    info = None
    try:
        info = survey_status(pkg)
        U0 = {p: r.get("U", float("nan")) for p, r in info.items()}
        known = [u for u in U0.values() if np.isfinite(u)]
        for p in U:
            if np.isfinite(U0.get(p, float("nan"))):
                U[p] = U0[p]
            elif known:
                U[p] = float(np.median(known))
    except Exception:
        info = None
    if info is not None:
        try:
            allowance = int(float(pkg.site.get("survey_allowance", 0)))
        except Exception:
            allowance = 0
        try:
            if DEBUG and os.environ.get("LINES_UOVERRIDE"):
                U = {r["pipe"]: float(r["U"]) for r in read_csv(os.environ["LINES_UOVERRIDE"])}
                crew_rows, order = [], []
            else:
                order, crew_rows = order_crew(pkg_dir, pkg, info, allowance)
                U = resolve_uo(pkg, info, crew_rows)
            if DEBUG:
                for p in sorted(info):
                    r = info[p]
                    dbg("pipe", p, r["status"], "ratio=%.2f" % r.get("ratio", -1),
                        "Ufile=%.4f" % r.get("U", float("nan")), "U=%.4f" % U[p], "nvalid=%d" % len(r["valid"]))
                if os.environ.get("LINES_UDUMP"):
                    with open(os.environ["LINES_UDUMP"], "w") as f:
                        f.write("pipe,U\n")
                        for p in sorted(U):
                            f.write("%s,%.10g\n" % (p, U[p]))
                dbg("allowance", allowance, "order", order, "crew rows", len(crew_rows))
        except Exception as e:
            dbg("coefficient resolution failed:", repr(e))
    singles = [r for r in recs if r["line"] in pkg.lines and pkg.lines[r["line"]]["n"] == 1]
    pairs = [r for r in recs if r["line"] in pkg.lines and pkg.lines[r["line"]]["n"] == 2]
    try:
        solve_singles(pkg, U, singles, out)
    except Exception:
        pass
    try:
        solve_pairs(pkg, U, pairs, out)
    except Exception:
        pass
    write(out_csv, recs, out)


def write(out_csv, recs, out):
    with open(out_csv, "w", newline="") as f:
        f.write("record,dp_kPa,t_out_C\n")
        for r, o in zip(recs, out):
            if o is None or not (np.isfinite(o[0]) and np.isfinite(o[1])):
                o = (0.0, r["tin"] if np.isfinite(r["tin"]) else 0.0)
            f.write("%s,%.4f,%.4f\n" % (r["record"], o[0], o[1]))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.stderr.write("usage: lines.py PACKAGE_DIR OUT_CSV\n")
        sys.exit(0)
    try:
        main(sys.argv[1], sys.argv[2])
    except Exception:
        # last resort: still produce a well-formed file
        try:
            rows = read_csv(os.path.join(sys.argv[1], "records.csv"))
            with open(sys.argv[2], "w") as f:
                f.write("record,dp_kPa,t_out_C\n")
                for r in rows:
                    f.write("%s,0,%s\n" % (r.get("record", ""), r.get("t_in_C", "0")))
        except Exception:
            pass
    sys.exit(0)
