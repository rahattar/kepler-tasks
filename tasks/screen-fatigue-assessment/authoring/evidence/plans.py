"""Estimation engine for the evidence studies: records plus one outage programme of field tests. Per-screen components
are computed once for a set of record choices; any programme (and proxy choice) is then assembled from them, so
every allocation can be scored. Field results come from the contractor's own generator (fieldwork.make_records), as
the service would hand them back."""
import os
import sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "provenance"))
import methods as M
import screens as S
import fieldwork as FW

BANK = S.load_bank(os.path.join(HERE, "..", "..", "environment", "fieldwork", "bank.json"))
REF = [("S5", "strain-survey"), ("S6", "coast-down"), ("S8", "coast-down")]
DEFAULT = dict(gf=True, pos=True, swap=True, debond="rescale", debond_from="2026-08-20", fs8=True, thick=True,
               fat5=True, s9debond=True, s8starts=True, s9gap=True, s6=True, s2tau=True, coast="twomode",
               events=True, n_phase=8)


def table_tau():
    """Commissioning coast-down times from the screen description (as exponential time constants)."""
    import re
    txt = open(os.path.join(M.DATA, "docs", "screen_description.md")).read()
    return {u: float(v) / np.log(2.0) for u, v in re.findall(r"\| (S\d+) \| ([\d.]+) \|", txt)}


TABLE = table_tau()
FRAME_A = [u for u in S.UNITS if u not in S.FRAME_B]
TAU_A_MED = float(np.median([TABLE[u] for u in FRAME_A if u in TABLE]))


def opts(**kw):
    o = dict(DEFAULT)
    o.update(kw)
    if o["debond"] != "none":
        rp, rq = M.ratio_s1(o)
        o["r_pre"], o["r_fix"] = rp, rp / rq
    rp9, rq9 = M.ratio_s1(dict(debond_from="2026-07-20"), "S9")
    o["r9_fix"] = rq9 / rp9
    return o


def hs(e1, e2):
    return (1.0 * e1 - 0.4 * e2) / 0.6 * M.E * 1e-6


def log_for(u, o):
    L = M.LOG[M.LOG.screen == u].copy()
    if u == "S8" and o["s8starts"]:
        m = L.date >= "2024-07-01"
        L.loc[m, "starts"] = L.loc[m, "starts"] / 2.0
    if u == "S9" and o["s9gap"]:
        L = pd.concat([L, M.s9_fill(L)], ignore_index=True)
    if u == "S6" and o["s6"]:
        L = L[L.date >= "2025-11-14"]
    return L


def steady_damage(u, a, b, L, fa):
    cph = M.REG.loc[u, "motor_rpm"] * 60.0
    tot = 0.0
    for (lo, hi), col in zip(S.BANDS, S.BAND_COLS):
        if hi == lo:
            r = cph / float(S.cycles_to_failure(a + b * lo, fa))
        else:
            F = np.linspace(lo, hi, 201)
            r = float(np.trapezoid(cph / S.cycles_to_failure(a + b * F, fa), F) / (hi - lo))
        tot += float(L[col].sum()) * r
    return tot


def components(o):
    comp = {}
    for u in S.UNITS:
        fa = M.fat(u, o)
        rows = M.IDX[M.IDX.screen == u]
        fs = 200.0 if (u == "S8" and o["fs8"]) else 500.0
        c = dict(fa=fa, L=log_for(u, o))
        F, R, ev = [], [], {"start": [], "stop": []}
        for rid, kind, feed in zip(rows.record, rows.kind, rows.feed_tph):
            s = M.hotspot(u, rid, o)
            r, cc = S.rainflow(s)
            if kind in ("loaded", "empty"):
                F.append(feed); R.append(float(np.median(r[cc == 1.0])))
            else:
                ev[kind].append(S.miner(r, cc, fa))
        c["ab"] = np.polyfit(F, R, 1)[::-1] if F else None
        for k in ("start", "stop"):
            c[k] = float(np.mean(ev[k])) if ev[k] else None
        if c["stop"] is not None:
            recs = [(M.hotspot(u, rid, o), M.REC[rid].speed_rpm.values) for rid in rows.record[rows.kind == "stop"]]
            if o["coast"] == "twomode":
                p, cc, _ = M.forced_fit(recs, fs, M.ringdown2(*recs[0], fs))
                c["modes"] = (p, cc)
            elif o["coast"] in ("sdof", "quasi"):
                ids = [M.ringdown(s, fs) for s, _ in recs]
                c["sdof"] = (float(np.mean([i[0] for i in ids])), float(np.mean([i[1] for i in ids])))
        sv = FW.make_records(u, "strain-survey", BANK)
        Rs = []
        for kind, f, cols in sv:
            r, cc = S.rainflow(hs(cols["ch1_ue"], cols["ch2_ue"]))
            Rs.append(float(np.median(r[cc == 1.0])))
        c["ab_survey"] = np.polyfit([f for _, f, _ in sv], Rs, 1)[::-1]
        (_, _, cols), = FW.make_records(u, "coast-down", BANK)
        r, cc = S.rainflow(hs(cols["ch1_ue"], cols["ch2_ue"]))
        c["coast_test"] = S.miner(r, cc, fa)
        sp = cols["speed_rpm"]
        t = np.arange(sp.size) / FW.FS
        m = (sp < 0.95 * sp[0]) & (sp > 0.05 * sp[0])
        c["tau_test"] = -1.0 / np.polyfit(t[m], np.log(sp[m]), 1)[0]
        comp[u] = c
    return comp


_CACHE = {}


def coast_model(u, c, tau, o):
    key = (u, o["coast"], round(float(tau), 6), o["n_phase"], id(c))
    if key not in _CACHE:
        f_op = M.REG.loc[u, "motor_rpm"] / 60.0
        if o["coast"] == "twomode":
            p, cc = c["modes"]
            _CACHE[key] = M.coast2(p, cc, tau, f_op, c["fa"], n=o["n_phase"])
        else:
            fr, z = c["sdof"]
            _CACHE[key] = M.coast_damage(fr, z, tau, f_op, c["ab"][0], c["fa"], method=o["coast"])
    return _CACHE[key]


def assemble(comp, plan, o, proxy="median"):
    plan = set(plan)
    tau_b = None
    for u in S.FRAME_B:
        if (u, "coast-down") in plan:
            tau_b = comp[u]["tau_test"]
    ab = {}
    for u in S.UNITS:
        c = comp[u]
        ab[u] = c["ab"] if c["ab"] is not None else (c["ab_survey"] if (u, "strain-survey") in plan else None)
    med = np.median([v for v in ab.values() if v is not None], axis=0)
    ab = {u: (v if v is not None else med) for u, v in ab.items()}
    Ae = {u: ab[u][0] for u in S.UNITS}

    def tauf(u):
        return tau_b if (u in S.FRAME_B and tau_b) else TABLE.get(u, TAU_A_MED)
    coast = {}
    for u in S.UNITS:
        c = comp[u]
        if (u, "coast-down") in plan:
            coast[u] = c["coast_test"]
        elif o["coast"] in ("twomode", "sdof", "quasi") and ("modes" in c or "sdof" in c):
            if u == "S2" and o["s2tau"]:
                L = c["L"]; pre = L.date < S.BRAKE_DATE; late = L.date >= S.TAU_CHANGE[1]
                n1, n2 = float(L.starts[pre & ~late].sum()), float(L.starts[pre & late].sum())
                coast[u] = (n1 * coast_model(u, c, tauf(u), o) +
                            n2 * coast_model(u, c, S.TAU_CHANGE[2] / np.log(2.0), o)) / max(n1 + n2, 1)
            else:
                coast[u] = coast_model(u, c, tauf(u), o)
        elif o["coast"] == "braked" and c["stop"] is not None:
            coast[u] = c["stop"]
        elif o["coast"] == "none":
            coast[u] = 0.0
        else:
            coast[u] = None
    norm = {"start": [], "stop": [], "coast": []}
    for u in S.UNITS:
        for k in ("start", "stop"):
            if comp[u][k] is not None:
                norm[k].append(comp[u][k] / Ae[u] ** 3)
        if coast[u] is not None and u not in S.FRAME_B:
            norm["coast"].append(coast[u] / Ae[u] ** 3)
    agg = {"median": np.median, "max": np.max, "min": np.min}[proxy]
    est = {}
    for u in S.UNITS:
        c = comp[u]; L = c["L"]
        a, b = ab[u]
        D = steady_damage(u, a, b, L, c["fa"])
        if o["events"]:
            pre = (L.date < S.BRAKE_DATE).values
            n_all, n_pre = float(L.starts.sum()), float(L.starts[pre].sum())
            st = c["start"] if c["start"] is not None else float(agg(norm["start"])) * Ae[u] ** 3
            sp = c["stop"] if c["stop"] is not None else float(agg(norm["stop"])) * Ae[u] ** 3
            co = coast[u] if coast[u] is not None else float(agg(norm["coast"])) * Ae[u] ** 3
            D += n_all * st + (n_all - n_pre) * sp + n_pre * co
        est[u] = D
    return est


def grade(est):
    return M.grade(est)
