"""The Wilson-plot route on the reactor-jacket unit E8 (tube film fitted from the trend's own flow variation, the
bank's median RTD offset for the unit that never stands by): its error on the shipped records against re-drawn
measurement noise. The bank is the same sealed bank; only the generator's noise seed changes.

    python3 wilson_noise.py > wilson_noise.txt
"""
import os, sys, tempfile
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "provenance"))
import hx, gen

FLEET = hx.make_fleet(gen.SEED)
_make = hx.make_fleet
hx.make_fleet = lambda seed=11: _make(11)          # same bank, new noise


def wilson_error(d, u):
    tr = {v: pd.read_csv(os.path.join(d, "trends", v.lower() + ".csv")) for v in hx.UNITS}
    offs = [np.median(t[t.state == "standby"].glycol_out_c - t[t.state == "standby"].glycol_in_c)
            for t in tr.values() if (t.state == "standby").sum() >= 3]
    t = tr[u]
    t["day"] = np.arange(len(t)) / 24.0
    r = t[t.state == "run"]
    tho = r.glycol_out_c.values - float(np.median(offs))
    q = r.glycol_flow_m3h.values / 3600 * hx.RHO_G * hx.CP_G * (r.glycol_in_c.values - tho)
    tco = r.cw_in_c.values + q / (r.cw_flow_m3h.values / 3600 * hx.RHO_CW * hx.CP_CW)
    a, b = r.glycol_in_c.values - tco, tho - r.cw_in_c.values
    A, ft0, fs0, hs0 = (110.0, 220.0, 75.0, 2900.0) if u in hx.NEW else (90.0, 180.0, 60.0, 2500.0)
    y = 1000.0 / (q * 1000 / (A * (a - b) / np.log(a / b)))
    xt, xs = (ft0 / r.cw_flow_m3h.values) ** 0.8, (fs0 / r.glycol_flow_m3h.values) ** 0.6
    X = np.c_[xt, np.ones(len(r)), r.day.values]
    c = np.linalg.lstsq(X, y - 1000.0 / hs0 * xs - 0.05, rcond=None)[0]
    return c[1] + c[2] * hx.T_TEST - hx.rf(FLEET[u], hx.T_TEST)


print("tube film fitted from the trend instead of spending a slot (requirement 0.04 m2K/kW); the bank's median")
print("offset for E8, which never stands by. Same sealed bank, only the generator's noise re-drawn.")
print("  %-18s %18s %18s" % ("", "E8 error", "E1 error"))
for seed in (11, 12, 13, 14, 15, 16, 17, 18):
    gen.SEED = seed
    d = tempfile.mkdtemp()
    gen.main(d)
    print("  noise seed %-11s %+18.3f %+18.3f" % ("%d%s" % (seed, " (shipped)" if seed == 11 else ""),
                                                  wilson_error(d, "E8"), wilson_error(d, "E1")))
