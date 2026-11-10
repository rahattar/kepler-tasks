"""A second solution, written separately from solution/solve.py, with its own tests, model code and pick rule.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt

Tests (3): the mean expansion of FV520B to 400 C and Ti-6Al-4V to 290 C, each a little above the highest heating
limit among its parts, and of the rotor steel to 200 C, above its hottest seat, so that every temperature above 100 C
lies between the table's 20-100 C value and a measurement. 42CrMo4 is not tested: the balance drum's certificate
gives its mill value to 250 C, above every 42CrMo4 temperature. The rotor as now: certificates for the material, the log's 110 % trip, the inspection report's 28.5 C.
Each bore is the middle of the whole-micrometre window this model computes; the oven is the heating limit for a part
whose top is set by the clearance there, and the needed temperature plus 25 C (within the limit) for the others. It
is graded on the shipped seed and on the laboratory seeds 5301-5320 with the in-process laboratory.
"""
import re

import numpy as np
import pandas as pd

import common as C

D = C.DATA
PLAN = {"FV520B": 400, "Ti-6Al-4V": 290, "26NiCrMoV14-5": 200}


def records():
    cert = pd.read_csv(D + "/material_certificates.csv").set_index("part")
    reg = pd.read_csv(D + "/parts_register.csv").set_index("part")
    ins = pd.read_csv(D + "/rotor_inspection.csv").set_index("part")
    th = pd.read_csv(D + "/thermal_survey.csv").set_index("part")
    mat = pd.read_csv(D + "/materials.csv").set_index("material")
    t = reg.drop(columns=["material"]).join(cert).join(ins).join(th)
    oem = open(D + "/docs/oem_rotor_data.md").read()
    mcs = float(re.search(r"\(MCS\): (\d+)", oem).group(1))
    spin = {m[0]: (float(m[2]) * (mcs / float(m[1])) ** 2, float(m[3]) * (mcs / float(m[1])) ** 2, float(m[4]))
            for m in re.findall(r"\| (S\d) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|", oem)}
    insp = open(D + "/docs/inspection_report.md").read()
    t_bay = float(re.search(r"inspection: ([\d.]+) C", insp).group(1))
    # micrometer errors by range: a seat read with an instrument is corrected by its error (indication less true)
    for lo, hi, err in re.findall(r"\| M-\d+ \| (\d+)-(\d+) \| [^|]+ \| ([+-][\d.]+) mm \|", insp):
        sel = (t.seat_nominal_mm > float(lo)) & (t.seat_nominal_mm <= float(hi))
        t.loc[sel, "seat_diameter_mm"] -= float(err)
    log = pd.read_csv(D + "/maintenance_log.csv")
    for _, e in log.dropna(subset=["part"]).iterrows():
        lim = re.search(r"do not exceed (\d+) C", e.entry)
        if lim:
            t.loc[e.part, "heating_limit_C"] = float(lim.group(1))
    trip = 1.10          # maintenance log 2025-06-11 (the OEM sheet still says 105 %)
    return t, mat, spin, mcs, trip, t_bay


def run(seed):
    t, mat, spin, mcs, trip, t_bay = records()
    lab = C.Lab(seed)
    meas = {m: (T, lab.cte(m, T) * 1e-6) for m, T in PLAN.items()}
    mill = t.note.fillna("").str.extract(r"mean expansion 20-(\d+) C ([\d.]+) um/m K").dropna()
    for k, (Tm, am) in mill.iterrows():
        meas.setdefault(t.loc[k, "material"], (float(Tm), float(am) * 1e-6))
    a100 = {m: r.expansion_20_100C_um_per_m_K * 1e-6 for m, r in mat.iterrows()}

    def alpha(m, T):
        if m in meas and T > 100:
            Tm, am = meas[m]
            return a100[m] + (am - a100[m]) * (T - 100) / (Tm - 100)
        return a100[m]

    rot = mat.loc["26NiCrMoV14-5"]
    w = mcs * trip * np.pi / 30
    sheet = {}
    for k, r in t.iterrows():
        h = mat.loc[r.material]
        d, Dh = r.seat_nominal_mm, r.hub_outside_diameter_mm
        seat20 = r.seat_diameter_mm / (1 + a100["26NiCrMoV14-5"] * (t_bay - 20))
        span = (13 if d <= 80 else 15 if d <= 120 else 18) * 1e-3
        sm = 0.8 * (3.2 + r.seat_Rz_um) * 1e-3
        q = (Dh ** 2 + d ** 2) / (Dh ** 2 - d ** 2)
        kl = (q + h.poisson) / (h.E_GPa * 1e3) + (1 - rot.poisson) / (rot.E_GPa * 1e3)
        b, c = d / 2e3, Dh / 2e3
        if k in spin:
            grow, hoop = spin[k][0] * 1e-3 * trip ** 2, spin[k][1] * trip ** 2
            torque = spin[k][2] * 1e3 / (mcs * np.pi / 30)
        else:
            grow = 2e3 * h.density_kg_m3 * w * w * b / (4 * h.E_GPa * 1e9) * ((3 + h.poisson) * c * c + (1 - h.poisson) * b * b)
            hoop = h.density_kg_m3 * w * w / 4 * ((3 + h.poisson) * c * c + (1 - h.poisson) * b * b) / 1e6
            torque = 0.0
        grow -= 2e3 * rot.density_kg_m3 * w * w * b ** 3 * (1 - rot.poisson) / (4 * rot.E_GPa * 1e9)
        dth = d * (alpha(r.material, r.hub_C) * (r.hub_C - 20) - alpha("26NiCrMoV14-5", r.seat_C) * (r.seat_C - 20))
        run_change = -dth - grow
        mu = 0.12 if r.material == "Ti-6Al-4V" else 0.15
        um = np.arange(1, 700)
        lo_i = um * 1e-3 - span / 2 - sm
        hi_i = um * 1e-3 + span / 2 - sm
        ok = np.ones(len(um), bool)
        for dd, rr in ((0.0, 0.0), (run_change, hoop)):
            p_lo = np.maximum(lo_i + dd, 0) / (d * kl)
            ok &= p_lo >= 15.0
            if torque:
                ok &= mu * p_lo * np.pi * d * d * r.hub_length_mm / 2e3 >= 2 * torque
            p_hi = np.maximum(hi_i + dd, 0) / (d * kl)
            st = p_hi * q + rr
            ok &= np.sqrt(st * st + st * p_hi + p_hi * p_hi) <= r.yield_strength_MPa / 1.2
        Tl = r.heating_limit_C
        bmin = seat20 - um * 1e-3 - span / 2
        clear = bmin * (1 + alpha(r.material, Tl) * (Tl - 20)) - r.seat_diameter_mm >= 0.001 * d
        W = um[ok & clear]
        m = int(W[len(W) // 2])
        nxt = W[-1]          # index of the micrometre above the window's top (um starts at 1)
        heat_limited = bool(ok[nxt] and not clear[nxt])
        bore = round(seat20 - m * 1e-3, 3)
        need = next(T for T in range(20, int(Tl) + 1)
                    if (bore - span / 2) * (1 + alpha(r.material, T) * (T - 20)) - r.seat_diameter_mm >= 0.001 * d)
        T = int(Tl) if heat_limited else min(need + 25, int(Tl))
        sheet[k] = (bore, T)
    return sheet, lab.log


def main():
    sheet, log = run(C.SEED)
    n, res, _ = C.grade(sheet)
    print("shipped seed %d: tests %s" % (C.SEED, log))
    for k in C.IDS:
        m = res[k][1]
        print("%s %.3f mm %3d C  %s  retention %+.3f stress %+.3f clearance %+.3f" % (
            k, sheet[k][0], sheet[k][1], "ok " if res[k][0] else "BAD", m["ret"], m["stress"], m["clear"]))
    print("right %d of 8; smallest margin retention %+.4f stress %+.4f clearance %+.4f" % (
        n, C.least(res, "ret"), C.least(res, "stress"), C.least(res, "clear")))
    ns = [C.grade(run(s)[0])[0] for s in C.SEEDS]
    print("seeds 5301-5320: 8 of 8 on %d of 20 (right counts %s)" % (sum(x == 8 for x in ns), ns))


if __name__ == "__main__":
    main()
