"""Engine for the evidence studies (authoring/evidence): estimates every unit's as-found fouling resistance on the test day from the records and
a set of clean-and-test results, with switches for the shortcuts and the sound variations."""
import os, sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "provenance"))
import hx

DATA = os.path.join(HERE, "..", "..", "environment", "data")
FLEET = hx.make_fleet(11)
TR = {u: pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % u.lower())) for u in hx.UNITS}
for _t in TR.values():
    _t["day"] = np.arange(len(_t)) / 24.0
ACC = pd.read_csv(os.path.join(DATA, "acceptance_tests_2025.csv")).set_index("unit")
DESIGN = {"C-200": dict(A=90.0, ht=3000.0, hs=2500.0, rw=5e-5, ft=180.0, fs=60.0),
          "C-310": dict(A=110.0, ht=3200.0, hs=2600.0, rw=5e-5, ft=220.0, fs=75.0)}
MODEL_OF = {u: FLEET[u]["model"] for u in hx.UNITS}
TOL = 0.04


def lmtd(tci, tco, thi, tho):
    a, b = thi - tco, tho - tci
    return np.where(np.abs(a - b) < 1e-6, a, (a - b) / np.log(a / b))


def u_obs(fs, tci, tco, thi, tho, A, side="glycol"):
    if side == "glycol":
        q = fs / 3600 * hx.RHO_G * hx.CP_G * (thi - tho)          # kW
    else:
        raise ValueError
    return q * 1000.0 / (A * lmtd(tci, tco, thi, tho))


def design_split(model, ft, fs, scale_t=1.0, scale_s=1.0, open_=1.0, eh=1.0):
    d = DESIGN[model]
    ht = d["ht"] * scale_t * eh * (ft / open_ / d["ft"]) ** 0.8
    hs = d["hs"] * scale_s * (fs / d["fs"]) ** 0.6
    return ht, hs, d["rw"]


def sheet_u(r, A, duty="glycol"):
    """Clean U from a 2025 test sheet. duty: "glycol" or "water" (as recorded), "mean" (mean of the two duties), or
    "fix_<reading>" (that one reading rebuilt from the other side's duty: tho, tco, thi, tci)."""
    tci, tco, thi, tho = r.cw_in_c, r.cw_out_c, r.glycol_in_c, r.glycol_out_c
    cw = r.cw_flow_m3h / 3600 * hx.RHO_CW * hx.CP_CW
    cg = r.glycol_flow_m3h / 3600 * hx.RHO_G * hx.CP_G
    qw, qg = cw * (tco - tci), cg * (thi - tho)
    q = qg
    if duty == "water":
        q = qw
    elif duty == "mean":
        q = (qw + qg) / 2
    elif duty == "fix_tho":
        tho, q = thi - qw / cg, qw
    elif duty == "fix_thi":
        thi, q = tho + qw / cg, qw
    elif duty == "fix_tco":
        tco = tci + qg / cw
    elif duty == "fix_tci":
        tci = tco - qg / cw
    return float(q * 1000.0 / (A * lmtd(tci, tco, thi, tho)))


def unit_scale(u, how="common", duty="glycol"):
    """Per-unit scale on the design split from the unit's 2025 clean acceptance test."""
    r = ACC.loc[u]
    m = MODEL_OF[u]
    U = sheet_u(r, DESIGN[m]["A"], duty)
    ht, hs, rw = design_split(m, r.cw_flow_m3h, r.glycol_flow_m3h)
    target = 1 / U - rw
    if how == "common":       # one factor on both films
        s = (1 / ht + 1 / hs) / target
        return s, s
    if how == "shell":        # all of the difference on the shell film
        return 1.0, 1 / (hs * (target - 1 / ht))
    if how == "tube":
        return 1 / (ht * (target - 1 / hs)), 1.0


def bias(u, stat="median"):
    t = TR[u]
    sb = t[t.state == "standby"]
    if len(sb) < 3:
        return None
    d = (sb.glycol_out_c - sb.glycol_in_c).values
    return float(np.median(d) if stat == "median" else np.mean(d))


def dp_ratio(u):
    """Tube-side dp now over the 2025 acceptance dp, both referred to the same CW flow (dp ~ flow^1.8)."""
    t = TR[u]
    r = t[t.state == "run"]
    now = np.median(r.dp_tube_kpa / r.cw_flow_m3h ** 1.8)
    old = ACC.loc[u].dp_tube_kpa / ACC.loc[u].cw_flow_m3h ** 1.8
    return float(now / old)


def test_result(u, k):
    rec = hx.clean_and_test(FLEET[u], k)
    out = {}
    for lab in ("as_found", "after_cleaning"):
        r = rec[lab]["reference_instruments"]
        open_ = dp_ratio(u) ** (-1 / 1.8) if u == "E2" else 1.0      # plugged tubes: area from the dp rise
        out[lab] = float(u_obs(r["glycol_flow_m3h"], r["cw_in_c"], r["cw_out_c"], r["glycol_in_c"], r["glycol_out_c"],
                               DESIGN[MODEL_OF[u]]["A"] * open_))
        out[lab + "_flows"] = (r["cw_flow_m3h"], r["glycol_flow_m3h"])
        out[lab + "_dcs_bias"] = rec[lab]["dcs"]["glycol_out_c"] - r["glycol_out_c"]
        out[lab + "_dp"] = rec[lab]["dcs"]["dp_tube_kpa"]
    return out


SHOCK = 21.0      # 2026-10-05, the shock-chlorination day (maintenance log); its hours are left out of the fit


def estimate(plan, scale_how="common", bias_stat="median", use_bias=True, growth="step", plug="dp", liner="proxy",
             e5="baffle", e10="vendor", e9="glycol", e8_bias="bay_median", k_override=None, window_days=28, duty="glycol"):
    """plan: units given a clean-and-test, in order. Returns {unit: rf m2K/kW at the test day}."""
    tests = {u: test_result(u, k) for k, u in enumerate(plan, 1)}
    est, eh_meas = {}, {}
    # enhancement measured on a tested ribbed unit: tube film from the clean test vs its 2025 film
    for u in plan:
        if u in hx.ENH:
            ft, fs = tests[u]["after_cleaning_flows"]
            st, ss = unit_scale(u, scale_how)
            ht_old, hs, rw = design_split(MODEL_OF[u], ft, fs, st, ss)
            ht_now = 1 / (1 / tests[u]["after_cleaning"] - 1 / hs - rw)
            ef = dp_ratio(u)
            eh_meas[u] = (ht_now / ht_old, ef)
    if k_override is not None:
        K = k_override
    elif eh_meas:
        K = float(np.mean([(eh - 1) / (ef - 1) for eh, ef in eh_meas.values()]))
    else:
        K = None
    biases = {u: bias(u, bias_stat) for u in hx.UNITS}
    known = [b for b in biases.values() if b is not None]
    for u in hx.UNITS:
        if u in tests:
            est[u] = 1000 * (1 / tests[u]["as_found"] - 1 / tests[u]["after_cleaning"])
            continue
        m = MODEL_OF[u]
        A = DESIGN[m]["A"]
        open_, eh = 1.0, 1.0
        if u == "E2" and plug == "dp":
            open_ = dp_ratio(u) ** (-1 / 1.8)
        if u in hx.ENH:
            if liner == "proxy" and K is not None:
                eh = 1 + K * (dp_ratio(u) - 1)
            elif liner == "same" and eh_meas:
                eh = list(eh_meas.values())[0][0]
            elif liner == "none":
                eh = 1.0
        if u == "E10":
            if e10 == "vendor":
                # vendor datasheet clean U at design, split like the design sheet
                d = DESIGN[m]                 # vendor datasheet films 3570 / 2900 W/m2K (clean U 1490)
                st, ss = 3570.0 / d["ht"], 2900.0 / d["hs"]
            else:
                st = ss = 1.0
        elif u == "E5" and e5 == "baffle":        # 2025 shell film x (300/400)^0.6: crossflow velocity x 0.75
            st, ss = unit_scale(u, scale_how)
            ss = ss * (300.0 / 400.0) ** 0.6
        elif u == "E5" and e5 == "2025":
            st, ss = unit_scale(u, scale_how)
        elif u == "E9" and e9 == "design":            # the design split as it stands
            st, ss = 1.0, 1.0
        elif u == "E9" and e9 == "fleet":             # the median factor of the other plain units' 2025 tests
            f = float(np.median([unit_scale(v, "common")[0] for v in ("E1", "E2", "E4", "E5", "E6")]))
            st, ss = f, f
        elif u == "E9":
            st, ss = unit_scale(u, scale_how, e9)
        else:
            st, ss = unit_scale(u, scale_how)
        b = biases[u]
        if b is None:
            b = float(np.median(known)) if e8_bias == "bay_median" else 0.0
        if not use_bias:
            b = 0.0
        t = TR[u]
        r = t[(t.state == "run") & (t.day >= 28 - window_days)]
        tho = (r.glycol_out_c - b).values
        q = r.glycol_flow_m3h.values / 3600 * hx.RHO_G * hx.CP_G * (r.glycol_in_c.values - tho)
        tco = r.cw_in_c.values + q / (r.cw_flow_m3h.values / 3600 * hx.RHO_CW * hx.CP_CW)   # no water-outlet RTD
        U = u_obs(r.glycol_flow_m3h.values, r.cw_in_c.values, tco, r.glycol_in_c.values, tho, A * open_)
        ht, hs, rw = design_split(m, r.cw_flow_m3h.values, r.glycol_flow_m3h.values, st, ss, open_, eh)
        Rf = 1000 * (1 / U - (1 / ht + 1 / hs + rw))
        day = r.day.values
        keep = (day < SHOCK) | (day >= SHOCK + 1)
        if growth == "step":       # line in time plus a step at the shock dose
            X = np.c_[np.ones(keep.sum()), day[keep], day[keep] >= SHOCK + 1]
            c = np.linalg.lstsq(X, Rf[keep], rcond=None)[0]
            est[u] = float(c[0] + c[1] * hx.T_TEST + c[2])
        elif growth == "after":    # line through the hours after the shock dose only
            a = day >= SHOCK + 1
            est[u] = float(np.polyval(np.polyfit(day[a], Rf[a], 1), hx.T_TEST))
        elif growth == "line":     # one straight line through the window, shock ignored
            est[u] = float(np.polyval(np.polyfit(day, Rf, 1), hx.T_TEST))
        elif growth == "last":
            est[u] = float(np.median(Rf[r.day.values >= r.day.values.max() - 2]))
        else:
            est[u] = float(np.median(Rf))
    return est, K


def grade(est, tol=None):
    res = hx.grade(est, FLEET, tol or TOL)
    worst = max(res, key=lambda u: abs(res[u][0]))
    return abs(res[worst][0]), worst, sorted(u for u in res if not res[u][1]), res


REF_PLAN = ["E8", "E9", "E10"]
