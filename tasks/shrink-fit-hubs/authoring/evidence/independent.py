"""A second solution, written separately from solution/solve.py, with its own tests, friction law and pick rule.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt

Tests (8): steel's mean expansion to 270 C; steel/dry at two pressures (those of J01 and J06 at a first estimate) to
fit a power law of friction in pressure; one shrink test of each other pair in use except ductile iron with paste
(J07), which is taken as steel/paste times the ductile-iron/steel ratio of the dry tests at the same pressure. Every
pair's friction then follows its test with the fitted exponent. The joints as now: the maintenance log applied. Each
mean interference is the middle of the whole-micrometre window this model computes (the top of the range if it finds none); the oven is the heating limit for
the clearance-limited joints and the needed temperature plus 25 C (within the limit) for the others. It is graded on
the shipped seed and on the laboratory seeds 7101-7120 with the in-process laboratory.
"""
import numpy as np
import pandas as pd

import common as C

D = C.DATA
SPAN = [(50, 27), (80, 32), (120, 37), (180, 43), (250, 49)]
MATKEY = {"C45+N": "steel", "42CrMo4+QT": "steel", "S355J2": "steel", "EN-GJS-600-3": "ductile-iron",
          "EN-GJS-400-15": "ductile-iron", "CuSn12-C": "bronze", "AlSi10Mg-T6": "aluminium"}
MATROW = {"steel": "steel", "ductile-iron": "ductile iron", "bronze": "tin bronze CuSn12", "aluminium": "aluminium AlSi10Mg"}


def records():
    reg = pd.read_csv(D + "/joint_register.csv").set_index("joint")
    cert = pd.read_csv(D + "/hub_certificates.csv").set_index("joint")
    sheet = pd.read_csv(D + "/assembly_sheets.csv").set_index("joint")
    duty = pd.read_csv(D + "/duty.csv").set_index("joint")
    therm = pd.read_csv(D + "/thermography.csv").set_index("joint")
    mat = pd.read_csv(D + "/materials.csv").set_index("material")
    log = pd.read_csv(D + "/maintenance_log.csv", keep_default_na=False)
    t = reg.join(cert[["yield_strength_MPa", "heating_limit_C"]]).join(sheet).join(duty[["peak_torque_Nm"]]).join(therm)
    t["peak_torque_Nm"] = t["peak_torque_Nm"].astype(float)
    t["shaft_bore_mm"] = t["shaft_bore_mm"].astype(float)
    t["mat"] = [MATKEY[g] for g in t["hub_material"]]
    t["prep"] = t["surface_preparation"].map({"degreased, dry": "dry", "light machine oil": "oiled", "MoS2 assembly paste": "paste"})
    for _, r in log.iterrows():                      # read by hand: the three entries that change a joint
        if r["joint"] == "J10":
            t.loc["J10", "shaft_bore_mm"] = 40.0
        if r["joint"] == "J11":
            t.loc["J11", "peak_torque_Nm"] *= 75.0 / 55.0
        if r["joint"] == "J07":
            t.loc["J07", "prep"] = "paste"
    return t, mat


class Joint:
    def __init__(self, r, mat, a_steel):
        self.r, self.mat = r, mat
        self.d, self.D, self.di, self.L = r.shaft_diameter_mm, r.hub_outside_diameter_mm, r.shaft_bore_mm, r.hub_length_mm
        h, s = mat.loc[MATROW[r.mat]], mat.loc["steel"]
        self.Eh, self.nh, self.rh = h.E_GPa * 1e3, h.poisson, h.density_kg_m3
        self.Es, self.ns, self.rs = s.E_GPa * 1e3, s.poisson, s.density_kg_m3
        self.ah100, self.as100 = h.expansion_20_100C_um_per_m_K * 1e-6, s.expansion_20_100C_um_per_m_K * 1e-6
        self.a_steel = a_steel
        self.span = next(v for b, v in SPAN if self.d <= b) * 1e-3
        self.sm = 0.8 * (r.bore_Rz_um + r.shaft_Rz_um) * 1e-3
        q, qi = self.d / self.D, self.di / self.d
        self.k_lame = ((1 + q * q) / (1 - q * q) + self.nh) / self.Eh + ((1 + qi * qi) / (1 - qi * qi) - self.ns) / self.Es
        self.Ch = (1 + q * q) / (1 - q * q)
        w = r.speed_rpm * np.pi / 30
        b, c, a = self.d / 2e3, self.D / 2e3, self.di / 2e3
        grow_h = self.rh * w * w * b / (4 * self.Eh * 1e6) * ((3 + self.nh) * c * c + (1 - self.nh) * b * b)
        grow_s = self.rs * w * w * b / (4 * self.Es * 1e6) * ((3 + self.ns) * a * a + (1 - self.ns) * b * b)
        thermal = self.d * (self.ah100 * (r.hub_C - 20) - self.as100 * (r.shaft_C - 20))
        self.run_change = -(thermal + 2e3 * (grow_h - grow_s))
        self.hoop = self.rh * w * w / 4 * ((3 + self.nh) * c * c + (1 - self.nh) * b * b) / 1e6

    def alpha(self, T):
        if self.r.mat == "steel":
            return self.a_steel(T)
        return self.ah100

    def p(self, de):
        return np.maximum(de, 0) / (self.d * self.k_lame)

    def least_p(self, m):
        e = m * 1e-3 - self.span / 2 - self.sm
        return np.minimum(self.p(e), self.p(e + self.run_change))

    def ok(self, m, mu):
        e_lo = m * 1e-3 - self.span / 2 - self.sm
        e_hi = m * 1e-3 + self.span / 2 - self.sm
        torque = min(mu(self.p(e)) * self.p(e) * np.pi * self.d ** 2 * self.L / 2e3 for e in (e_lo, e_lo + self.run_change))
        def vm(p, rot):
            st = p * self.Ch + rot
            return np.sqrt(st * st + st * p + p * p)
        stress = max(vm(self.p(e_hi), 0.0), vm(self.p(e_hi + self.run_change), self.hoop))
        T = self.r.heating_limit_C
        clear = self.d * self.alpha(T) * (T - 20) - (m * 1e-3 + self.span / 2 + 0.001 * self.d)
        return torque >= 1.5 * self.r.peak_torque_Nm and stress <= self.r.yield_strength_MPa / 1.2 and clear >= 0

    def heat_limited(self, m):
        T = self.r.heating_limit_C
        return self.d * self.alpha(T) * (T - 20) < (m + 1) * 1e-3 + self.span / 2 + 0.001 * self.d


def run(seed):
    lab = C.Lab(seed)
    t, mat = records()
    a100 = mat.loc["steel"].expansion_20_100C_um_per_m_K * 1e-6
    a270 = lab.cte("steel", 270) * 1e-6
    a_steel = lambda T: a100 + (a270 - a100) * (T - 100) / 170.0
    J = {k: Joint(r, mat, a_steel) for k, r in t.iterrows()}
    # first estimate of the pressures: the middle of the stress / clearance-limited range with handbook friction 0.15
    guess = {}
    for k, j in J.items():
        ms = [m for m in range(1, 1500) if j.ok(m, lambda p: 0.15)]
        guess[k] = j.least_p(ms[len(ms) // 2]) if ms else 50.0
    p1, p2 = round(float(guess["J01"])), round(float(guess["J06"]))
    m1, m2 = lab.slip("steel", "dry", p1), lab.slip("steel", "dry", p2)
    kexp = -np.log(m2 / m1) / np.log(p2 / p1)
    tests = {("steel", "dry"): (p1, m1)}
    groups = {}
    for k, j in J.items():
        groups.setdefault((j.r.mat, j.r.prep), []).append(k)
    for key in (("steel", "paste"), ("aluminium", "dry"), ("bronze", "oiled"), ("ductile-iron", "dry"), ("steel", "oiled")):
        p = round(float(np.median([guess[k] for k in groups[key]])))
        tests[key] = (p, lab.slip(key[0], key[1], p))
    # ductile iron with paste, by the dry ratio at the paste test's pressure
    pp, mp = tests[("steel", "paste")]
    pg, mg = tests[("ductile-iron", "dry")]
    ratio = (mg * (pp / pg) ** (-kexp)) / (m1 * (pp / p1) ** (-kexp))
    tests[("ductile-iron", "paste")] = (pp, mp * ratio)
    fits = {}
    for k, j in J.items():
        p0, m0 = tests[(j.r.mat, j.r.prep)]
        mu = lambda p, p0=p0, m0=m0: m0 * (np.maximum(p, 1.0) / p0) ** (-kexp)
        W = [m for m in range(1, 1500) if j.ok(m, mu)]
        if not W:                                   # no window with this friction: the top of the range
            W = [max(m for m in range(1, 1500) if j.ok(m, lambda p: 10.0))]
        m = W[len(W) // 2]
        T = int(j.r.heating_limit_C)
        if not j.heat_limited(W[-1]):
            need = next(T_ for T_ in range(20, T + 1)
                        if j.d * j.alpha(T_) * (T_ - 20) >= m * 1e-3 + j.span / 2 + 0.001 * j.d)
            T = min(need + 25, T)
        fits[k] = (m, T)
    return fits, kexp, lab.log


def main():
    fits, kexp, log = run(C.SEED)
    n, res, _ = C.grade(fits)
    print("shipped seed %d: tests %s" % (C.SEED, log))
    print("fitted friction exponent %.3f" % kexp)
    for k in C.IDS:
        m = res[k][1]
        print("%s %4d um %3d C  %s  torque %+.3f stress %+.3f clearance %+.3f" % (k, fits[k][0], fits[k][1],
              "ok " if res[k][0] else "BAD", m["slip"], m["stress"], m["clear"]))
    print("right %d of 12; smallest margin torque %+.4f stress %+.4f clearance %+.4f" % (
        n, C.least(res, "slip"), C.least(res, "stress"), C.least(res, "clear")))
    ns = [C.grade(run(s)[0])[0] for s in C.SEEDS]
    print("seeds 7101-7120: 12 of 12 on %d of 20 (right counts %s)" % (sum(x == 12 for x in ns), ns))


if __name__ == "__main__":
    main()
