"""Writes the agent-visible records from the sealed definition (puller.py): minute logs and caliper profiles of the
eight HZ-B bodies (seeds 101-108) grown on the fast-pull recipe under the fab's loops (pull rate PI on the camera
diameter, heater PI on the 30 min filtered pull rate), one with an approved heater response test (heater loop in
manual, +2.5 kW for 150 min from 700 mm), and both recipe tables. The documents in environment/data/docs are
written by hand and copied as they are.

    python3 gen.py OUT_DIR
"""
import os, sys, csv
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import puller as P2

HIST_SEEDS = list(P2.RECORD_SEEDS)
STEP_BODY = 105


class FabLoops:
    """The fab's fast-pull loops. Pull rate PI on camera diameter; heater PI on the 30 min filtered pull rate."""
    def __init__(self, recipe, d_set=304.0, kd=0.06, ti_d=30.0, kp_h=40.0, ti_h=80.0, tf=30.0, test=None):
        self.rc, self.d_set = recipe, d_set
        self.kd, self.ti_d, self.kp_h, self.ti_h, self.tf = kd, ti_d, kp_h, ti_h, tf
        self.test = test
        self.init = False
        self.manual = False

    def step(self, m):
        e = m["camera_diameter_mm"] - self.d_set
        if not self.init:
            self.init = True
            self.i_d = m["pull_rate_mm_min"]
            self.vf = m["pull_rate_mm_min"]
            self.p0 = m["heater_power_kw"]
            self.i_h = 0.0
        self.i_d += self.kd / self.ti_d * e
        vp = self.i_d + self.kd * e
        self.vf += (m["pull_rate_mm_min"] - self.vf) / self.tf
        ev = self.vf - float(self.rc["v"](m["length_mm"]))
        p_auto = self.p0 + self.i_h + self.kp_h * ev
        if self.test is not None:
            L0, dp, dur = self.test
            if not self.manual and m["length_mm"] >= L0 and not hasattr(self, "t_test"):
                self.manual, self.t_test, self.p_hold = True, m["t"], m["heater_power_kw"]
            if self.manual:
                if m["t"] - self.t_test < dur:
                    return vp, self.p_hold + dp
                # bumpless return to auto
                self.manual = False
                self.i_h = m["heater_power_kw"] - self.p0 - self.kp_h * ev
                return vp, m["heater_power_kw"]
        self.i_h += self.kp_h / self.ti_h * ev
        return vp, p_auto


def run_logged(b, recipe, ctl):
    pl = P2.Puller(b, recipe)
    rows = []
    while pl.L < P2.L_BODY and pl.t < 4000:
        m = pl.measure()
        vp, p = ctl.step(m)
        rows.append(m)
        pl.apply(vp, p, 1.0)
    return rows, np.array(pl.log)


def write_recipes(out):
    os.makedirs(os.path.join(out, "recipes"), exist_ok=True)
    for name, key in (("fast_pull_r31.csv", "fast_pull"), ("perfect_si_r07.csv", "perfect_si")):
        rc = P2.RECIPES[key]
        with open(os.path.join(out, "recipes", name), "w") as f:
            f.write("length_mm,growth_rate_program_mm_min,crucible_rpm\n")
            for L in np.arange(0, 1501, 10.0):
                f.write("%.0f,%.4f,%.1f\n" % (L, float(rc["v"](L)), P2.w_cmd(L, rc)))


def main(OUT):
    write_recipes(OUT)
    os.makedirs(os.path.join(OUT, "logs"), exist_ok=True)
    rc = P2.RECIPES["fast_pull"]
    for s in HIST_SEEDS:
        b = P2.make_body(s)
        ctl = FabLoops(rc, test=(700.0, 2.5, 150.0) if s == STEP_BODY else None)
        rows, log = run_logged(b, rc, ctl)
        name = "B%d" % (s - 100 + 2410)
        with open(os.path.join(OUT, "logs", name + "_minute.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time_min", "length_mm", "camera_diameter_mm", "pull_rate_mm_min", "heater_power_kw",
                        "pyrometer_c", "crucible_rpm_set"])
            for r in rows:
                w.writerow(["%.0f" % r["t"], "%.2f" % r["length_mm"], "%.2f" % r["camera_diameter_mm"],
                            "%.4f" % r["pull_rate_mm_min"], "%.2f" % r["heater_power_kw"],
                            "%.2f" % (1428.0 + r["pyrometer_k"]), "%.1f" % r["crucible_rpm_set"]])
        rng = np.random.default_rng(s + 7)
        Lc = np.arange(20.0, log[-1, 1], 10.0)
        Dc = np.interp(Lc, log[:, 1], log[:, 2]) + rng.normal(0, 0.05, len(Lc))
        with open(os.path.join(OUT, "logs", name + "_caliper.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["length_mm", "diameter_mm"])
            for a, d in zip(Lc, Dc):
                w.writerow(["%.0f" % a, "%.2f" % d])
        sc = P2.score(log)
        print(name, "minutes %.0f d_min %.2f d_mean %.2f" % (sc["minutes"], sc["d_min"], sc["d_mean"]))


if __name__ == "__main__":
    main(sys.argv[1])
