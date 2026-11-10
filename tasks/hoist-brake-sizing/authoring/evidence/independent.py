"""Independent solution: a second selection, written separately from solution/solve.py, with its own test plan, its
own fits and its own numerics, graded by the sealed definition.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt

- Records: read from the CSV files with pandas; the log's changes applied by hand from its text.
- Tests (8): O1 at 20, 70 and 155 C; O2 at 20, 150, 205 and 265 C; engagement of S16 at 67 % with AC switching.
- Friction: a monotone cubic (PCHIP) through the ratios to 20 C, no use outside 10 C of the tested range.
  Engagement: t100 (1 + kappa ln(100 / setting)), kappa from the test, the same kappa for DC switching.
- Duty temperature: the hoist's working cycle marched stop by stop (hoisting and lowering stops alternating, each
  stop's heat, at the torque of the temperature it starts at, added at once, exponential cooling between stops) until
  the peak repeats, instead of the closed form.
- Emergency stops: integrated with scipy's solve_ivp (speed, angle, lining temperature), the brake's torque following
  the lining temperature.
- Setting: the middle of the window (the feasible settings) on the size with the widest window.
"""
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator

import common as C

G = 9.81
PLAN = [C.F(20), C.F(70), C.F(155), C.F(20, "O2"), C.F(150, "O2"), C.F(205, "O2"), C.F(265, "O2"),
        C.E("S16", 67, "AC")]
REACH = 10.0


def records(data):
    reg = pd.read_csv(os.path.join(data, "hoist_register.csv")).set_index("hoist")
    wir = pd.read_csv(os.path.join(data, "brake_wiring.csv")).set_index("hoist")
    duty = pd.read_csv(os.path.join(data, "duty_survey.csv")).set_index("hoist")
    cat = pd.read_csv(os.path.join(data, "brake_catalogue.csv")).set_index("size")
    hs = {}
    for hid, r in reg.iterrows():
        falls_reg = r.falls
        hs[hid] = dict(
            mass=r.rated_load_t * 1000, hook=r.hook_block_kg, falls=r.falls, drum=r.drum_pitch_diameter_mm / 1000,
            i=r.gearbox_ratio, eta=r.gearbox_efficiency, gb=r.gearbox_peak_input_torque_Nm,
            omega=r.motor_rpm * math.pi / 30, Jmot=r.motor_rotor_inertia_kgm2 + r.gearbox_inertia_at_input_kgm2,
            air=r.bay_air_temperature_C, smax=r.emergency_stop_travel_limit_mm / 1000,
            amax=r.emergency_stop_deceleration_limit_m_per_s2,
            # the register's lowering speed at the motor (above synchronous on contactor control)
            omega_down=r.lowering_speed_rated_load_m_per_min / 60 / (r.drum_pitch_diameter_mm / 1000 / (2 * falls_reg * r.gearbox_ratio)),
            slow=(4 / 24 if "4/24" in r.control else 4 / 16 if "4/16" in r.control else 1.0),
            ac=wir.loc[hid, "brake_switching"].startswith("AC"),
            per_hour=(duty.loc[hid, "brake_applications_hoisting"] + duty.loc[hid, "brake_applications_lowering"])
            / duty.loc[hid, "operating_hours"],
            mean_load=duty.loc[hid, "mean_load_percent_of_rated"] / 100, vfd=False, fast=None)
    # the maintenance log, read entry by entry
    hs["H05"].update(falls=2, mass=10000.0, hook=300.0)
    for hid in ("H04", "H08", "H12"):
        hs[hid]["vfd"] = True
        hs[hid]["omega_down"] = hs[hid]["omega"]
    hs["H04"]["fast"] = (1.5, 0.5)
    hs["H08"]["fast"] = (1.6, 0.4)
    for h in hs.values():
        h["r"] = h["drum"] / (2 * h["falls"] * h["i"])
    return hs, cat


class Lab:
    def __init__(self, tests, cat):
        pts = {"O1": {}, "O2": {}}
        self.kappa = None
        for test, vals in tests:
            if test[0] == "friction":
                pts[test[2]][float(test[1])] = float(np.mean(vals))
            else:
                t100 = cat.loc[test[1], "engagement_time_AC_switching_ms"] / 1000
                self.kappa = (np.mean(vals) / 1000 / t100 - 1) / math.log(100 / float(test[2]))
        self.f = {}
        self.span = {}
        for lin, p in pts.items():
            T = np.array(sorted(p))
            y = np.array([p[t] / p[20.0] for t in T])
            self.f[lin] = PchipInterpolator(T, y, extrapolate=False)
            self.span[lin] = (T[0], T[-1])

    def ratio(self, T, lin):
        lo, hi = self.span[lin]
        return float(self.f[lin](min(max(T, lo), hi)))


def check(h, size, setting, lab, cat):
    """the five MS-14 margins of one size and setting; None if the linings leave the tested range"""
    c = cat.loc[size]
    lin = c.friction_lining
    Cth, Hd, Jb = c.heat_capacity_J_per_K, c.heat_dissipation_W_per_K, c.rotor_inertia_kgm2
    t100 = (c.engagement_time_AC_switching_ms if h["ac"] else c.engagement_time_DC_switching_ms) / 1000
    te = t100 * (1 + lab.kappa * math.log(100 / setting))
    Mb = lambda T: setting / 100 * c.rated_torque_Nm * lab.ratio(T, lin)
    back = 2 - 1 / h["eta"]
    r = h["r"]

    def J(m):
        return h["Jmot"] + Jb + (m + h["hook"]) * r * r

    def grav(m):
        return (m + h["hook"]) * G * r

    def stop(m, w0, T0, lowering):
        """speed w (rad/s at the motor), angle and lining temperature through a stop; returns (angle, T end, heat)"""
        Jm = J(m)
        load = grav(m) * back if lowering else -grav(m) / h["eta"]
        # engagement delay: no brake
        w = w0 + load / Jm * te
        if not lowering and w <= 0:
            return 0.0, T0, 0.0
        ang0 = w0 * te + 0.5 * load / Jm * te * te

        def rhs(t, y):
            ww, th, T = y
            mb = Mb(T)
            return [(load - mb) / Jm, ww, mb * max(ww, 0) / Cth]

        def halt(t, y):
            return y[0]
        halt.terminal, halt.direction = True, -1
        if Mb(T0) <= load:
            return math.inf, T0, math.inf
        sol = solve_ivp(rhs, (0, 60), [w, 0.0, T0], events=halt, max_step=0.02, rtol=1e-7, atol=1e-9)
        if not sol.t_events[0].size:
            return math.inf, sol.y[2, -1], math.inf
        _, th, T = sol.y_events[0][0]
        return ang0 + th, T, (T - T0) * Cth

    def work_heat(m, w0, T0, lowering):
        """heat of a working stop: a few kelvin, so the brake's torque is taken at the lining temperature it starts at"""
        Jm, mb = J(m), Mb(T0)
        if lowering:
            L = grav(m) * back
            if mb <= L:
                return math.inf
            w = w0 + L / Jm * te
            return mb * Jm * w * w / (2 * (mb - L))
        L = grav(m) / h["eta"]
        w = max(w0 - L / Jm * te, 0.0)
        return mb * Jm * w * w / (2 * (mb + L))

    # working cycle: march alternating stops at the mean load until the peak repeats
    T = h["air"]
    peak = h["air"]
    if not h["vfd"]:
        m = h["mean_load"] * h["mass"]
        gap = 3600 / h["per_hour"]
        decay = math.exp(-gap * Hd / Cth)
        prev = None
        T_h = T
        for k in range(20000):
            lowering = k % 2 == 1
            w0 = (h["omega_down"] if lowering else h["omega"]) * h["slow"]
            q = work_heat(m, w0, T, lowering)
            if not math.isfinite(q):
                return None
            T += q / Cth
            if T > 1500:
                return None
            if lowering:
                if prev is not None and abs(T - prev) < 1e-5:
                    peak = max(T, T_h)
                    break
                prev = T
            else:
                T_h = T
            T = h["air"] + (T - h["air"]) * decay
        else:
            return None
    hold = Mb(peak) / (1.6 * grav(h["mass"])) - 1
    cases = [(h["mass"], h["omega_down"])] + ([(h["fast"][1] * h["mass"], h["fast"][0] * h["omega"])] if h["fast"] else [])
    travel, Tmax = math.inf, peak
    for m, w0 in cases:
        ang, Tend, q = stop(m, w0, peak, True)
        if not math.isfinite(ang):
            return None
        travel = min(travel, h["smax"] / (ang * r) - 1)
        Tmax = max(Tmax, Tend)
    lo, hi = lab.span[lin]
    if Tmax > hi + REACH:
        return None
    temp = 300 / Tmax - 1
    top = max(Mb(t) for t in np.linspace(h["air"], Tmax, 200))
    gearbox = h["gb"] / top - 1
    decel = h["amax"] / ((top + grav(h["mass"]) / h["eta"]) * r / J(h["mass"])) - 1
    return min(hold, travel, temp, gearbox, decel)


def solve(tests, data=C.DATA):
    hs, cat = records(data)
    lab = Lab(tests, cat)
    picks = {}
    for hid, h in hs.items():
        best = None
        for size in cat.index:
            # quick screen: holding at 100 % with the coldest friction ratio of the lining
            if cat.loc[size, "rated_torque_Nm"] * 1.35 < 1.6 * (h["mass"] + h["hook"]) * G * h["r"]:
                continue
            ok = []
            for s in range(50, 101):
                m = check(h, size, s, lab, cat)
                if m is not None and m >= 0:
                    ok.append(s)
            if ok and (best is None or len(ok) > len(best[1])):
                best = (size, ok)
        if best is None:
            raise SystemExit("no brake found for %s" % hid)
        size, ok = best
        picks[hid] = (size, ok[len(ok) // 2])
    return picks


def main():
    print(__doc__.split("\n\n")[0].strip())
    print("Shipped scenario, laboratory seed %d.\n" % C.SEED)
    tests = C.lab(PLAN)
    for test, vals in tests:
        print("test %-24s mean %.4f" % (" ".join(test), float(np.mean(vals))))
    picks = solve(tests)
    n, fails = C.grade(picks)
    print()
    for hid, (size, s) in picks.items():
        print("%s %s/%d  true smallest margin %+.3f" % (hid, size, s, C.truth_margin(hid, size, s)))
    print("\nindependent solution: %d of 12 meet every requirement %s" % (n, " ".join(fails)))


if __name__ == "__main__":
    main()
