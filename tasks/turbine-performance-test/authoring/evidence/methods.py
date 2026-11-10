"""The reference reduction (solution/solve.py) with one step changed at a time, for route_study.py (traps) and
method_spread.py (other sound choices). reduce(opts) returns {condition: (output MW, heat rate kJ/kWh)}.

  wrong side (traps): no_pt_fix, dcs_mw, net_mw, qnh_kept, pt102_zero_kept, pt102_per_day, cit_bias_kept, fuel_zero_kept,
      gc_air_kept, hhv_volumetric, whole_run, l3_kept, filter_dp, te301
  not a trap: no_pf (power factor correction left out)
  sound alternatives: window='last' | 'all', cit_from='spot', zero_stat='mean', gc_air='removed', per_minute=True,
      lhv_pooled=True
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import solve as S        # noqa: E402
import gt1_truth as T    # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")
_C = {}


def data():
    if not _C:
        _C["v"] = S.load(DATA)
    return _C["v"]


def factors(Tb, c, pa, w, di, de):
    tc, ti, te, th = (Tb["compressor inlet temperature"], Tb["inlet loss"], Tb["exhaust loss"],
                      Tb["ambient specific humidity"])
    fo = (np.interp(c, tc[:, 0], tc[:, 1]) * pa / 101.325 * np.interp(w, th[:, 0], th[:, 1])
          * np.interp(di, ti[:, 0], ti[:, 1]) * np.interp(de, te[:, 0], te[:, 1]))
    fh = (np.interp(c, tc[:, 0], tc[:, 2]) * np.interp(w, th[:, 0], th[:, 2])
          * np.interp(di, ti[:, 0], ti[:, 2]) * np.interp(de, te[:, 0], te[:, 2]))
    return fo, fh


def reduce(o=None):
    o = o or {}
    d, gc, log, Tb = data()
    day = d.index.normalize()
    days = sorted(set(day))
    still = d.index.strftime("%H:%M") < S.STILL_END
    baro = d.met_baro_hpa / 10.0
    conv = (1.0 - 2.25577e-5 * S.ELEV_M) ** 5.25588
    p_amb = baro.where(day == days[0], baro * conv)
    if o.get("qnh_kept"):
        p_amb = baro.copy()
    gap = (d.pt102_inlet_total_kpa_abs - baro)[still].groupby(day[still]).mean()
    pt102 = d.pt102_inlet_total_kpa_abs.copy()
    if o.get("pt102_per_day"):
        pt102 = pt102 - gap.reindex(day).values          # PT-102 forced onto the met reading each day
        p_amb = baro.copy()
    elif not o.get("pt102_zero_kept"):
        pt102 = pt102 - float(gap[days[0]])
    cit = d[["cit_%d_c" % i for i in range(1, 9)]].mean(axis=1)
    if not o.get("cit_bias_kept"):
        if o.get("cit_from") == "spot":
            spots = log[log.entry.str.startswith("Inlet plenum air temperature spot check")]
            bias = {}
            for _, r in spots.iterrows():
                ref = float(r.entry.split(":")[-1].replace("degC", "").strip())
                bias[r.time.normalize()] = float(cit[r.time]) - ref
            cit = cit - pd.Series(bias).reindex(day).values
        else:
            b = (cit - d.met_dry_bulb_c)[still].groupby(day[still]).mean()
            cit = cit - b.reindex(day).values
    k = 1.0 if o.get("no_pt_fix") else S.PT_ACTUAL / S.PT_SET
    P = d.gen_mw_jt001 * 1000.0 * k
    Q = d.gen_mvar_jt001 * 1000.0 * k
    if o.get("dcs_mw"):
        P = d.gen_mw_dcs * 1000.0
    if o.get("net_mw"):
        P = d.unit_net_mw * 1000.0
    dp_in = d.pdt101_filter_dp_kpa if o.get("filter_dp") else p_amb - pt102
    pv = d.met_rh_pct / 100.0 * S.psat_kpa(d.met_dry_bulb_c)
    w = 0.621945 * pv / (p_amb - pv)
    fz = d.fuel_coriolis_kg_s[still].groupby(day[still])
    zero = fz.mean() if o.get("zero_stat") == "mean" else fz.median()
    if o.get("fuel_zero_kept"):
        zero = zero * 0.0
    tf = d.te301_fuel_meter_c if o.get("te301") else d.te305_fuel_skid_c
    lhv, allv = {}, []
    for kd in days:
        vals = []
        for _, r in gc[gc.sample_time.dt.normalize() == kd].iterrows():
            x = {c: r[c] / 100.0 for c in S.COMP}
            if o.get("hhv_volumetric"):
                vals.append(r["gross_cv_mj_m3_15_15"] * 1000.0)
                continue
            if x["O2"] > 0.001 and not o.get("gc_air_kept"):
                if o.get("gc_air") == "removed":
                    a = x["O2"] / 0.2095
                    x["N2"] -= a * 0.7905
                    x["O2"] = 0.0
                    s = sum(x.values())
                    x = {c: v / s for c, v in x.items()}
                else:
                    continue
            vals.append(S.lhv_kj_kg(x))
        lhv[kd] = float(np.mean(vals))
        allv += vals
    if o.get("lhv_pooled"):
        lhv = {kd: float(np.mean(allv)) for kd in days}
    res = {}
    for name, se in S.runs(log).items():
        x = d[(d.index > se["start"]) & (d.index <= se["end"])]
        base = ((x.igv_deg >= 85.5) & ((x.texh_avg_c - x.ttrf_c).abs() <= 3.0)).values
        if o.get("whole_run"):
            win = x.index
        else:
            starts = [i for i in range(len(x) - 29) if base[i:i + 30].all()]
            if not starts:
                if not o.get("l3_kept"):
                    continue
                win = x.index[:30]
            elif o.get("window") == "last":
                win = x.index[starts[-1]:starts[-1] + 30]
            elif o.get("window") == "all":
                win = x.index[base]
            else:
                win = x.index[starts[0]:starts[0] + 30]
        kd = win[0].normalize()
        if o.get("per_minute"):
            Pm, Qm = P[win], Q[win]
            pf = Pm / np.hypot(Pm, Qm)
            Ppf = Pm if o.get("no_pf") else Pm + S.gen_loss_kw(Pm, pf) - S.gen_loss_kw(Pm, S.REF_PF)
            heat = (d.fuel_coriolis_kg_s[win] - zero[kd]) * (lhv[kd] + S.CP_FUEL * (tf[win] - 15.0))
            fo, fh = factors(Tb, cit[win], p_amb[win], w[win], dp_in[win], d.pdt201_exhaust_kpa_g[win])
            out_mw = float(np.mean(Ppf / fo)) / 1000.0
            hr = float(np.mean(3600.0 * heat / Ppf / fh))
        else:
            Pm, Qm = P[win].mean(), Q[win].mean()
            pf = Pm / np.hypot(Pm, Qm)
            Ppf = Pm if o.get("no_pf") else Pm + S.gen_loss_kw(Pm, pf) - S.gen_loss_kw(Pm, S.REF_PF)
            heat = (d.fuel_coriolis_kg_s[win].mean() - zero[kd]) * (lhv[kd] + S.CP_FUEL * (tf[win].mean() - 15.0))
            fo, fh = factors(Tb, cit[win].mean(), p_amb[win].mean(), w[win].mean(), dp_in[win].mean(),
                             d.pdt201_exhaust_kpa_g[win].mean())
            out_mw, hr = Ppf / fo / 1000.0, 3600.0 * heat / Ppf / fh
        res[name] = (out_mw, hr)
    out = {}
    for cond, letter in (("as_found", "A"), ("as_left", "L")):
        r = [v for n, v in res.items() if n.startswith(letter)]
        out[cond] = (float(np.mean([v[0] for v in r])), float(np.mean([v[1] for v in r])))
    return out


def misses(o=None):
    """Percent misses: {condition: (output, heat rate)}."""
    r = reduce(o)
    return {c: (round(100 * (r[c][0] / T.OUTPUT_MW[c] - 1), 2), round(100 * (r[c][1] / T.HEAT_RATE[c] - 1), 2))
            for c in T.CONDITIONS}


if __name__ == "__main__":
    print(misses())
