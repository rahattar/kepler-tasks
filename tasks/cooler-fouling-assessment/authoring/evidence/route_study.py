"""Shortcuts and plans that spend the three clean-and-test slots differently, against the reference, on the shipped
bank. Figures: worst unit's |estimated - true| as-found fouling resistance on the test day, m2K/kW.

    python3 route_study.py > route_study.txt
"""
import itertools
import methods as M

P = M.REF_PLAN


def show(name, est):
    e, w, fails, _ = M.grade(est[0])
    print("  %-84s worst %.3f (%s)  fails %2d  %s" % (name, e, w, len(fails), " ".join(fails)))


def wilson(u, film):
    """No slot spent on u: its unknown film coefficient and its fouling fitted together from the trend
    (1/U - other film - wall = a * (design flow / flow)^n + R_f(0) + rate * day), the Wilson-plot route."""
    import numpy as np
    t = M.TR[u]
    r = t[t.state == "run"]
    b = M.bias(u)
    b = float(np.median([x for x in (M.bias(v) for v in M.hx.UNITS) if x is not None])) if b is None else b
    d = M.DESIGN[M.MODEL_OF[u]]
    tho = r.glycol_out_c.values - b
    q = r.glycol_flow_m3h.values / 3600 * M.hx.RHO_G * M.hx.CP_G * (r.glycol_in_c.values - tho)
    tco = r.cw_in_c.values + q / (r.cw_flow_m3h.values / 3600 * M.hx.RHO_CW * M.hx.CP_CW)
    y = 1000 / M.u_obs(r.glycol_flow_m3h.values, r.cw_in_c.values, tco, r.glycol_in_c.values, tho, d["A"])
    xt, xs = (d["ft"] / r.cw_flow_m3h.values) ** 0.8, (d["fs"] / r.glycol_flow_m3h.values) ** 0.6
    x, other = (xt, 1000 / d["hs"] * xs) if film == "tube" else (xs, 1000 / d["ht"] * xt)
    X = np.c_[x, np.ones(len(r)), r.day.values]
    yy = y - other - 1000 * d["rw"]
    c = np.linalg.lstsq(X, yy, rcond=None)[0]
    sd = float(np.std(yy - X @ c))
    g = np.array([0.0, 1.0, M.hx.T_TEST])           # the fit's own standard error of R_f on the test day
    se = sd * float(np.sqrt(g @ np.linalg.inv(X.T @ X) @ g))
    return c[1] + c[2] * M.hx.T_TEST - M.hx.rf(M.FLEET[u], M.hx.T_TEST), se


def main():
    print("tolerance %.3f m2K/kW\n" % M.TOL)
    show("reference: test E8, E9, E10", M.estimate(P))
    print("\nshortcuts on the reference plan")
    show("glycol-outlet transmitter bias not removed", M.estimate(P, use_bias=False))
    show("fouling taken as the four-week median (growth not carried to the test day)", M.estimate(P, growth="median"))
    show("fouling taken from the last two days of the trend", M.estimate(P, growth="last"))
    show("one straight line through the four weeks (shock-chlorination step ignored)", M.estimate(P, growth="line"))
    show("one straight line through the last two weeks (step ignored)", M.estimate(P, growth="line", window_days=14))
    show("E2 plugging ignored (nominal area and tube velocity)", M.estimate(P, plug="none"))
    show("ribbed-tube gain not applied to E3, E7", M.estimate(P, liner="none"))
    show("E8's measured ribbed-tube gain carried over unchanged to E3, E7", M.estimate(P, liner="same"))
    show("2025 split: all of the difference on the shell film", M.estimate(P, scale_how="shell"))
    show("2025 split: all of the difference on the tube film", M.estimate(P, scale_how="tube"))
    show("transmitter bias from the standby mean", M.estimate(P, bias_stat="mean"))
    show("E5 from its 2025 test as it stands (the wider baffle spacing ignored)", M.estimate(P, e5="2025"))
    print("\nplans that spend the slots differently (E9 untested: its 2025 sheet, whose heat balance is 5 % open)")
    for d, name in (("glycol", "glycol-side duty as recorded"), ("water", "water-side duty as recorded"),
                    ("fix_tho", "glycol outlet rebuilt from the water side"), ("fix_tco", "water outlet rebuilt from the glycol side"),
                    ("mean", "mean of the two duties"), ("fix_thi", "glycol inlet rebuilt from the water side"),
                    ("fix_tci", "water inlet rebuilt from the glycol side"), ("design", "sheet set aside, design split"),
                    ("fleet", "sheet set aside, the sister units' median factor")):
        show("test E8, E5, E10; E9: " + name, M.estimate(["E8", "E5", "E10"], e9=d))
    for plan in (["E8", "E9", "E5"], ["E3", "E9", "E10"], ["E7", "E9", "E10"], ["E8", "E7", "E10"], ["E8", "E2", "E10"],
                 ["E8", "E6", "E10"], ["E9", "E10", "E5"], ["E8", "E3", "E9"]):
        show("test " + ", ".join(plan), M.estimate(plan))
    print("\nno slot: the unknown film fitted from the trend's own flow variation (Wilson plot); the bank runs at\n"
          "nearly fixed flows, so the fit cannot separate the film from the fouling (error on that unit)")
    for u, film in (("E10", "tube"), ("E10", "shell"), ("E9", "tube"), ("E9", "shell"), ("E8", "tube"), ("E8", "shell"),
                    ("E3", "tube"), ("E7", "tube")):
        e, se = wilson(u, film)
        print("  %-70s error %+.3f, the fit's own standard error +-%.3f" % ("%s, %s film fitted" % (u, film), e, se))
    print("  (with flows this steady the fit's own standard error is 0.04 to 0.11, comparable to or above the 0.04\n"
          "   requirement: an error near zero, as on E8's tube fit, is chance inside that band)")


if __name__ == "__main__":
    main()
