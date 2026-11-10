"""Reference solution for shrink-fit-hubs.

    python3 solve.py DATA_DIR OUT_JSON

Uses only the documents in DATA_DIR and the laboratory's `slip` and `cte` commands (8 tests).

1. The joints as they are now: the records with the maintenance log applied (J10's shaft hollow, 40 mm bore; J11's
   peak torque scaled by 75/55 for the motor upgrade; J07 refitted with MoS2 paste).
2. The model: Lame contact pressure for the hub on its solid or hollow shaft; the acting interference is the geometric
   one less the smoothing 0.8 (Rz bore + Rz shaft) that ST-9 states, and in steady running it changes by the free
   thermal growth of bore and shaft at the thermography temperatures (positive or negative) and by the centrifugal
   growth of hub and shaft; the spinning hub adds hoop stress at the bore.
3. The top of each joint's range is exact once the oven expansion is known: the hub stress at the greatest
   interference (at rest and running), and the clearance at the heating limit. The 20-100 C expansion of the table
   understates steel's mean expansion to the 270-280 C limits of J04, J06 and J09, and with it J06 has no feasible
   interference at all, so test 1 is `cte steel 275`; steel's mean expansion is then taken linear in T between the
   table's 20-100 C value and the measurement. Other hubs are far enough from their limits that the table value,
   which errs low, is enough.
4. Each mean interference is placed at the top of its range, less 1 um (stress-limited) or less 2 % of the oven
   expansion (clearance-limited, for the scatter of the one reading), since there the friction torque is greatest and the friction is the one uncertain
   quantity. The oven temperature is the lowest that gives the clearance with the expansion used, plus 20 C, and at
   most the heating limit.
5. Tests 2-8 measure the friction of each of the seven hub material / preparation pairs in use, shrink-fitted (the
   plant shrink-fits; a pressed specimen slips lower), at the contact pressure of the pair's joint that runs at the
   lowest pressure. They confirm the torque: friction in a shrink fit falls with contact pressure, so for the pair's
   other joints the measured value is an upper bound and the confirmation for them is approximate; the joints at
   the tested pressure are confirmed exactly.
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

IT = [(50, 11, 16), (80, 13, 19), (120, 15, 22), (180, 18, 25), (250, 20, 29)]
LABMAT = {"steel": "steel", "ductile iron": "ductile-iron", "tin bronze CuSn12": "bronze", "aluminium AlSi10Mg": "aluminium"}
GRADE_MAT = {"C45+N": "steel", "42CrMo4+QT": "steel", "S355J2": "steel", "EN-GJS-600-3": "ductile iron",
             "EN-GJS-400-15": "ductile iron", "CuSn12-C": "tin bronze CuSn12", "AlSi10Mg-T6": "aluminium AlSi10Mg"}
PREP = {"degreased, dry": "dry", "light machine oil": "oiled", "MoS2 assembly paste": "paste"}
CTE_T = 275


def rows(data, name):
    with open(os.path.join(data, name), newline="") as f:
        return list(csv.DictReader(f))


def span_mm(d):
    for b, i5, i6 in IT:
        if d <= b:
            return (i5 + i6) * 1e-3
    raise ValueError(d)


def load(data):
    mats = {r["material"]: dict(E=float(r["E_GPa"]) * 1e3, nu=float(r["poisson"]), rho=float(r["density_kg_m3"]),
                                a100=float(r["expansion_20_100C_um_per_m_K"]) * 1e-6) for r in rows(data, "materials.csv")}
    J = {}
    for r in rows(data, "joint_register.csv"):
        J[r["joint"]] = dict(part=r["part"], d=float(r["shaft_diameter_mm"]), di=float(r["shaft_bore_mm"]),
                             D=float(r["hub_outside_diameter_mm"]), L=float(r["hub_length_mm"]),
                             mat=GRADE_MAT[r["hub_material"]], rpm=float(r["speed_rpm"]))
    for r in rows(data, "hub_certificates.csv"):
        J[r["joint"]].update(Re=float(r["yield_strength_MPa"]), Tlim=float(r["heating_limit_C"]))
    for r in rows(data, "assembly_sheets.csv"):
        J[r["joint"]].update(Rz_h=float(r["bore_Rz_um"]), Rz_s=float(r["shaft_Rz_um"]), prep=PREP[r["surface_preparation"]])
    for r in rows(data, "duty.csv"):
        J[r["joint"]]["T"] = float(r["peak_torque_Nm"])
    for r in rows(data, "thermography.csv"):
        J[r["joint"]].update(Th=float(r["hub_C"]), Ts=float(r["shaft_C"]))
    # the maintenance log: the joints as they are now
    for r in rows(data, "maintenance_log.csv"):
        k, e = r["joint"], r["entry"]
        m = re.search(r"hollow shaft, bore (\d+) mm", e)
        if k and m:
            J[k]["di"] = float(m.group(1))
        m = re.search(r"from (\d+) kW to (\d+) kW", e)
        if k and m:
            J[k]["T"] *= float(m.group(2)) / float(m.group(1))
        if k and "MoS2 assembly paste" in e:
            J[k]["prep"] = "paste"
    return mats, J


class Model:
    def __init__(self, mats, J, steel_cte_meas=None):
        self.m, self.J, self.meas = mats, J, steel_cte_meas

    def cte(self, mat, T):
        a100 = self.m[mat]["a100"]
        if mat == "steel" and self.meas is not None and T > 100:
            return a100 + (self.meas - a100) * (T - 100.0) / (CTE_T - 100.0)
        return a100

    def K(self, j):
        h, s = self.m[j["mat"]], self.m["steel"]
        d, D, di = j["d"], j["D"], j["di"]
        Ch = (D * D + d * d) / (D * D - d * d)
        Cs = (d * d + di * di) / (d * d - di * di) if di > 0 else 1.0
        return (Ch + h["nu"]) / h["E"] + (Cs - s["nu"]) / s["E"]

    def p(self, j, de):
        return max(de, 0.0) / (j["d"] * self.K(j))

    def smooth(self, j):
        return 0.8 * (j["Rz_h"] + j["Rz_s"]) * 1e-3

    def running(self, j):
        """change of acting interference in running (mm) and hoop stress of the spinning hub at the bore (MPa)"""
        h, s = self.m[j["mat"]], self.m["steel"]
        th = j["d"] * (self.cte(j["mat"], j["Th"]) * (j["Th"] - 20) - self.cte("steel", j["Ts"]) * (j["Ts"] - 20))
        w = j["rpm"] * 2 * math.pi / 60
        b, c, a = j["d"] / 2e3, j["D"] / 2e3, j["di"] / 2e3
        uh = h["rho"] * w * w * b / (4 * h["E"] * 1e6) * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b)
        us = s["rho"] * w * w * b / (4 * s["E"] * 1e6) * ((3 + s["nu"]) * a * a + (1 - s["nu"]) * b * b)
        hoop = h["rho"] * w * w / 4 * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b) / 1e6
        return -(th + 2e3 * (uh - us)), hoop

    def states(self, j):
        dd, hoop = self.running(j)
        return [(0.0, 0.0), (dd, hoop)]

    def vm(self, j, p, rot):
        Ch = (j["D"] ** 2 + j["d"] ** 2) / (j["D"] ** 2 - j["d"] ** 2)
        st, sr = p * Ch + rot, -p
        return math.sqrt(st * st - st * sr + sr * sr)

    def stress_ok(self, j, m):
        dmax = m * 1e-3 + span_mm(j["d"]) / 2 - self.smooth(j)
        return all(self.vm(j, self.p(j, dmax + dd), rot) <= j["Re"] / 1.2 for dd, rot in self.states(j))

    def clear_ok(self, j, m, T):
        return j["d"] * self.cte(j["mat"], T) * (T - 20) >= m * 1e-3 + span_mm(j["d"]) / 2 + 0.001 * j["d"]

    def least_p(self, j, m):
        """lowest contact pressure at the least interference, at rest and in running"""
        dmin = m * 1e-3 - span_mm(j["d"]) / 2 - self.smooth(j)
        return min(self.p(j, dmin + dd) for dd, _ in self.states(j))

    def torque_margin(self, j, m, mu):
        dmin = m * 1e-3 - span_mm(j["d"]) / 2 - self.smooth(j)
        cap = min(mu * self.p(j, dmin + dd) * math.pi * j["d"] ** 2 * j["L"] / 2e3 for dd, _ in self.states(j))
        return cap / (1.5 * j["T"]) - 1.0

    def top(self, j):
        tops = [m for m in range(1, 2000) if self.stress_ok(j, m) and self.clear_ok(j, m, j["Tlim"])]
        m = max(tops)
        heat_limited = not self.clear_ok(j, m + 1, j["Tlim"])
        return m, heat_limited

    def oven(self, j, m):
        for T in range(20, int(j["Tlim"]) + 1):
            if self.clear_ok(j, m, T):
                return min(T + 20, int(j["Tlim"]))
        return int(j["Tlim"])


def lab(*args):
    out = subprocess.run(list(args), capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line and not line.startswith("#"):
            return float(line.split(",")[1])
    raise RuntimeError(out)


def main(data, out):
    mats, J = load(data)
    meas = lab("cte", "steel", str(CTE_T)) * 1e-6
    M = Model(mats, J, meas)
    pick = {}
    for k, j in J.items():
        m, heat = M.top(j)
        if heat:
            m -= int(math.ceil(0.02 * j["d"] * M.cte(j["mat"], j["Tlim"]) * (j["Tlim"] - 20) * 1e3))
        else:
            m -= 1
        pick[k] = (m, M.oven(j, m))
    # friction of each pair in use, at the pressure of its lowest-pressure joint
    pairs = {}
    for k, j in J.items():
        pairs.setdefault((j["mat"], j["prep"]), []).append(k)
    mu, report = {}, {}
    for (mat, prep), ks in pairs.items():
        p = max(10, min(200, int(round(min(M.least_p(J[k], pick[k][0]) for k in ks)))))
        mu[(mat, prep)] = lab("slip", LABMAT[mat], prep, str(p), "shrink")
        for k in ks:
            report[k] = (p, mu[(mat, prep)], M.torque_margin(J[k], pick[k][0], mu[(mat, prep)]),
                         M.least_p(J[k], pick[k][0]))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"fits": {k: {"interference_um": pick[k][0], "heating_C": pick[k][1]} for k in sorted(J)}}, f, indent=1)
    print("steel mean expansion 20-%d C measured %.2f um/m K" % (CTE_T, meas * 1e6))
    for k in sorted(J):
        p, m_, tm, pj = report[k]
        print("%s %4d um %3d C | friction %.3f tested at %d MPa, joint at %.0f MPa, torque margin %+.3f with it" % (
            k, pick[k][0], pick[k][1], m_, p, pj, tm))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/app/data", sys.argv[2] if len(sys.argv) > 2 else "/app/output/fits.json")
