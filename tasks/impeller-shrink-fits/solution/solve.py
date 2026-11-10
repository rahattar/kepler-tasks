"""Reference solution for impeller-shrink-fits.

    python3 solve.py DATA_DIR OUT_CSV

Uses only the documents in DATA_DIR and the laboratory's `cte` command (3 tests).

1. The rotor as it is now: the certificates give each part's material (the 5th-stage impeller is the titanium
   replacement the maintenance log records; the parts register predates it) and heating limit, except S2's, which
   the log gives as 240 C after the spare was recoated; the overspeed trip is 110 % of MCS (the log; the OEM data
   sheet still says 105 %). The OEM spin-test values are scaled to MCS from the speed each impeller was spun at
   (S4's at 10500 rpm).
2. The seats were measured on the rotor in the overhaul bay at 28.5 C (the inspection report); the bore sheet is at
   20 C. Each reading is first corrected by its micrometer's calibration error (the 100-125 mm instrument reads 4 um
   low), then taken back to 20 C with the rotor steel's expansion; the assembly clearance is checked against the
   corrected seat in the bay, since the rotor stands there when the parts go on.
3. The model: Lame contact pressure for the part's hub ring on the solid rotor; the acting interference is the
   geometric one less RS-3's smoothing 0.8 (Rz bore + Rz seat); at trip speed in running it changes by the free thermal
   growth of bore and seat at the survey temperatures (either sign) and by the centrifugal growth of the bore (the
   OEM's spin-test value at MCS times (trip / MCS)^2 for an impeller, the free-ring value for the drum and the collar)
   less that of the seat; the hoop stress of rotation at the bore is the OEM value times (trip / MCS)^2, or the free
   ring's. Retention at the least interference and stress at the greatest, at rest and at trip.
4. The tests. The materials table gives each material's mean expansion from 20 C to 100 C only, and every material
   is needed above 100 C somewhere: a clearance-limited part's material at its heating limit (found with the table's
   values), a hub at its running temperature, and the rotor steel at its seats, which run at up to 190 C (S3). The
   mean expansion of a steel rises with temperature, so the 20-100 C value understates all of them. That makes four
   materials for three tests; the balance drum's certificate gives the 42CrMo4 forging's mill value to 250 C, above
   every 42CrMo4 temperature, so 42CrMo4 needs no test. Each other material is measured once, at the highest
   temperature it is needed at, and every other temperature is reached by the straight line through the table's
   value at 100 C and the measurement (or the mill value). Between them this is interpolation, never extrapolation
   beyond a measurement: FV520B's mean expansion rises more slowly as the temperature rises, so a line through a
   lower point overstates it above that point. The three tests: the rotor steel to 190 C, FV520B to 375 C (S6) and
   Ti-6Al-4V to 285 C (S5).
5. Each bore gives the top of the range less 2 um (stress-limited; the seat reading is to 1 um) or less 0.6 % of the
   oven expansion (clearance-limited: twice the laboratory's stated repeatability of the one reading); the oven is the
   lowest temperature giving the clearance, plus 20 C, and at most the heating limit.
"""
import csv
import math
import os
import re
import subprocess
import sys

IT5 = [(80, 13), (120, 15), (180, 18)]
LABNAME = {"FV520B": "FV520B", "Ti-6Al-4V": "Ti-6Al-4V", "42CrMo4": "42CrMo4", "26NiCrMoV14-5": "26NiCrMoV14-5"}
ROTOR = "26NiCrMoV14-5"


def rows(data, name):
    with open(os.path.join(data, name), newline="") as f:
        return list(csv.DictReader(f))


def band(d):
    for b, v in IT5:
        if d <= b:
            return v * 1e-3
    raise ValueError(d)


def seats(text):
    """'S1-S6, BD' -> ['S1', ..., 'S6', 'BD']"""
    out = []
    for item in text.split(","):
        item = item.strip()
        m = re.match(r"S(\d)-S(\d)$", item)
        out += ["S%d" % i for i in range(int(m.group(1)), int(m.group(2)) + 1)] if m else [item]
    return out


def load(data, use_log=True, mic=True, spin=True, recoat=True):
    mats = {r["material"]: dict(E=float(r["E_GPa"]) * 1e3, nu=float(r["poisson"]), rho=float(r["density_kg_m3"]),
                                a100=float(r["expansion_20_100C_um_per_m_K"]) * 1e-6) for r in rows(data, "materials.csv")}
    P = {}
    for r in rows(data, "parts_register.csv"):
        P[r["part"]] = dict(d=float(r["seat_nominal_mm"]), D=float(r["hub_outside_diameter_mm"]),
                            L=float(r["hub_length_mm"]), mat=r["material"], g=None, h=None, kW=0.0)
    mill = {}
    for r in rows(data, "material_certificates.csv"):
        P[r["part"]].update(Re=float(r["yield_strength_MPa"]), Tlim=float(r["heating_limit_C"]))
        m = re.search(r"mean expansion 20-(\d+) C ([\d.]+) um/m K", r["note"])
        if m:
            mill[r["material"]] = (float(m.group(1)), float(m.group(2)) * 1e-6)
        if use_log:
            P[r["part"]]["mat"] = r["material"]
    for r in rows(data, "rotor_inspection.csv"):
        P[r["part"]].update(seat_meas=float(r["seat_diameter_mm"]), Rz_s=float(r["seat_Rz_um"]))
    insp = open(os.path.join(data, "docs", "inspection_report.md")).read()
    t_bay = float(re.search(r"inspection: ([\d.]+) C", insp).group(1))
    for j in P.values():
        j["T_meas"] = t_bay
    for m in re.finditer(r"^\| (M-\d+) \| [\d-]+ \| ([^|]+) \| ([+-][\d.]+) mm \|$", insp, re.M):
        for part in seats(m.group(2)):
            if mic:
                P[part]["seat_meas"] -= float(m.group(3))     # indication less true value
    for r in rows(data, "thermal_survey.csv"):
        P[r["part"]].update(Th=float(r["hub_C"]), Ts=float(r["seat_C"]))
    oem = open(os.path.join(data, "docs", "oem_rotor_data.md")).read()
    mcs = float(re.search(r"MCS\): (\d+) rpm", oem).group(1))
    trip = float(re.search(r"Overspeed trip: (\d+) %", oem).group(1)) / 100.0
    for m in re.finditer(r"^\| (S\d) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", oem, re.M):
        k = (mcs / float(m.group(2))) ** 2 if spin else 1.0       # spin-test values scaled to MCS
        P[m.group(1)].update(g=float(m.group(3)) * 1e-3 * k, h=float(m.group(4)) * k, kW=float(m.group(5)))
    if use_log:
        for r in rows(data, "maintenance_log.csv"):
            m = re.search(r"trip reset to (\d+) % of MCS", r["entry"])
            if m:
                trip = float(m.group(1)) / 100.0
            m = re.search(r"do not exceed (\d+) C", r["entry"])
            if m and r["part"] and recoat:
                P[r["part"]]["Tlim"] = float(m.group(1))
    std = open(os.path.join(data, "docs", "standard.md")).read()
    pmin = float(re.search(r"at\s+least (\d+) MPa", std).group(1))
    rz_bore = float(re.search(r"Rz ([\d.]+) um", std).group(1))
    mu = {k: float(v) for k, v in re.findall(r"(FV520B|42CrMo4|Ti-6Al-4V) (\d\.\d+)", std)}
    return mats, P, dict(mcs=mcs, trip=trip, pmin=pmin, rz_bore=rz_bore, mu=mu, mill=mill)


class Model:
    def __init__(self, mats, P, C, measured=None, bay=True, use_mill=True):
        self.m, self.P, self.C = mats, P, C
        self.meas = dict(C.get("mill", {})) if use_mill else {}   # material -> (T, mean expansion to T)
        self.meas.update(measured or {})
        self.bay = bay

    def cte(self, mat, T):
        a100 = self.m[mat]["a100"]
        if mat in self.meas:
            Tm, am = self.meas[mat]
            return a100 + (am - a100) * (T - 100.0) / (Tm - 100.0)
        return a100

    def seat20(self, j):
        if not self.bay:
            return j["seat_meas"]
        return j["seat_meas"] / (1.0 + self.cte(ROTOR, j["T_meas"]) * (j["T_meas"] - 20.0))

    def seat_bay(self, j):
        return j["seat_meas"]

    def Ch(self, j):
        return (j["D"] ** 2 + j["d"] ** 2) / (j["D"] ** 2 - j["d"] ** 2)

    def p(self, j, de):
        h, s = self.m[j["mat"]], self.m[ROTOR]
        K = (self.Ch(j) + h["nu"]) / h["E"] + (1 - s["nu"]) / s["E"]
        return max(de, 0.0) / (j["d"] * K)

    def smooth(self, j):
        return 0.8 * (self.C["rz_bore"] + j["Rz_s"]) * 1e-3

    def omega(self, f):
        return self.C["mcs"] * f * 2 * math.pi / 60.0

    def running(self, j):
        f = self.C["trip"]
        w = self.omega(f)
        h, s = self.m[j["mat"]], self.m[ROTOR]
        b, c = j["d"] / 2e3, j["D"] / 2e3
        if j["g"] is not None:
            gb, hoop = j["g"] * f * f, j["h"] * f * f
        else:
            gb = 2e3 * h["rho"] * w * w * b / (4 * h["E"] * 1e6) * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b)
            hoop = h["rho"] * w * w / 4.0 * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b) / 1e6
        gs = 2e3 * s["rho"] * w * w * b ** 3 * (1 - s["nu"]) / (4 * s["E"] * 1e6)
        th = j["d"] * (self.cte(j["mat"], j["Th"]) * (j["Th"] - 20) - self.cte(ROTOR, j["Ts"]) * (j["Ts"] - 20))
        return -th - (gb - gs), hoop

    def states(self, j):
        dd, hoop = self.running(j)
        return [(0.0, 0.0), (dd, hoop)]

    def vm(self, j, p, rot):
        st, sr = p * self.Ch(j) + rot, -p
        return math.sqrt(st * st - st * sr + sr * sr)

    def ret_ok(self, j, um):
        dmin = um * 1e-3 - band(j["d"]) / 2 - self.smooth(j)
        for dd, _ in self.states(j):
            p = self.p(j, dmin + dd)
            if p < self.C["pmin"]:
                return False
            if j["kW"] > 0:
                tq = j["kW"] * 1e3 / self.omega(1.0)
                if self.C["mu"][j["mat"]] * p * math.pi * j["d"] ** 2 * j["L"] / 2e3 < 2.0 * tq:
                    return False
        return True

    def stress_ok(self, j, um):
        dmax = um * 1e-3 + band(j["d"]) / 2 - self.smooth(j)
        return all(self.vm(j, self.p(j, dmax + dd), rot) <= j["Re"] / 1.2 for dd, rot in self.states(j))

    def clear_ok(self, j, um, T):
        bmin = self.seat20(j) - um * 1e-3 - band(j["d"]) / 2
        return bmin * (1 + self.cte(j["mat"], T) * (T - 20)) - self.seat_bay(j) >= 0.001 * j["d"]

    def top(self, j):
        tops = [um for um in range(1, 700) if self.stress_ok(j, um) and self.clear_ok(j, um, j["Tlim"])]
        um = max(tops)
        return um, not self.clear_ok(j, um + 1, j["Tlim"])

    def oven(self, j, um):
        for T in range(20, int(j["Tlim"]) + 1):
            if self.clear_ok(j, um, T):
                return min(T + 20, int(j["Tlim"]))
        return int(j["Tlim"])


def lab(*args):
    out = subprocess.run(list(args), capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line and not line.startswith("#"):
            return float(line.split(",")[1])
    raise RuntimeError(out)


def plan(M):
    """materials to measure: each material whose mean expansion is needed above 100 C (the 20-100 C table's range),
    to the highest temperature it is needed at: a clearance-limited part's material at its heating limit, a hub
    material at its running temperature and the rotor steel at its hottest seat; less those the certificates already
    give to that temperature"""
    need = {}
    for k, j in M.P.items():
        if M.top(j)[1]:
            need[j["mat"]] = max(need.get(j["mat"], 0), int(j["Tlim"]))
        if j["Th"] > 100:
            need[j["mat"]] = max(need.get(j["mat"], 0), int(j["Th"]))
        if j["Ts"] > 100:
            need[ROTOR] = max(need.get(ROTOR, 0), int(j["Ts"]))
    return {m: T for m, T in need.items() if not (m in M.C["mill"] and M.C["mill"][m][0] >= T)}


def pick(M, j, allowance=0.006):
    um, heat = M.top(j)
    if heat:
        um -= int(math.ceil(allowance * j["d"] * M.cte(j["mat"], j["Tlim"]) * (j["Tlim"] - 20) * 1e3))
    else:
        um -= 2
    return um


def main(data, out):
    mats, P, C = load(data)
    M = Model(mats, P, C)
    need = plan(M)
    for mat, T in sorted(need.items()):
        M.meas[mat] = (T, lab("cte", LABNAME[mat], str(T)) * 1e-6)
    sheet = []
    for k, j in P.items():
        um = pick(M, j)
        sheet.append((k, round(M.seat20(j) - um * 1e-3, 3), M.oven(j, um), um))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        f.write("part,bore_mm,oven_C\n")
        for k, b, T, _ in sheet:
            f.write("%s,%.3f,%d\n" % (k, b, T))
    print("trip %.2f x MCS; mean expansion (um/m K, from 20 C): %s" % (C["trip"], ", ".join(
        "%s %.2f to %.0f C%s" % (k, v[1] * 1e6, v[0], " (certificate)" if k in C["mill"] and k not in need else "")
        for k, v in M.meas.items())))
    for k, b, T, um in sheet:
        print("%s bore %.3f mm (seat at 20 C %.3f, interference %d um), oven %d C" % (k, b, M.seat20(P[k]), um, T))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/app/data", sys.argv[2] if len(sys.argv) > 2 else "/app/output/bore_sheet.csv")
