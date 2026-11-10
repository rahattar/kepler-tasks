"""Reference solution for crack-growth-life. Uses only the documents in /app/data and the `fcgr` command.

    python3 solve.py [DATA_DIR] [OUT_FILE]

1. Tests (all 5 slots, all Paris tests). The stress-relieved cracks' larger ranges sit between R 0.2 and 0.5, which
   is where crack closure slows growth, and where closure ends is a property of the steel, not of BS 7910's R = 0.5
   split; so two tests on heat H1 inside that band, at R = 0.20 and 0.35, one at R = 0.45 to find the closure-free
   Paris curve, and one at R = 0.90, which the laboratory's Kmax limit holds to dK 2-7.5, so that it gives the
   near-threshold shape. A threshold test would take three slots, and the threshold matters little here: the cracks'
   larger ranges are well above it. The flanges come from four heats of two grades and the growth rate of a steel
   differs from heat to heat, so the fifth test is on S460NL plate (heat H4, R = 0.70, closure-free); it grows about
   1.3 times as fast as H1. Heat H3, also S460NL, is taken to grow like H4.
2. One fit to all five reports: da/dN = G C (U(R) dK)^m (1 - dKth(R)/dK)^p, with a closure law linear in R,
   U = min(1, U0 + k R) (Elber's form), a closure-free threshold fitted to the R = 0.90 data and BS 7910's recommended
   threshold line 5.38 - 6.77 R where that is higher, and G the S460NL factor (1 for H1).
   Heat H2 was not tested. Its rate comes from E02, the earlier crack on H2: read as FA-3 describes the repair (the
   groove is ground 1 mm past the crack), the fitted law reproduces E01, on H1, within 1 percent and needs about 1.24 times
   its rate to reproduce E02.
3. For each crack: the weld-toe stress intensity factor K = Mk Y S sqrt(pi a), with BS 7910's 2D Mk for a transverse
   attachment (L = attachment thickness + 2 fillet legs, held at L/T = 2 beyond 2, Mk >= 1); the BS 7910 residual
   stress (yield as welded, 0.2 yield after furnace PWHT, no credit for vibratory stress relief, and as welded where
   the log shows an attachment welded on site after the PWHT); the survey's stress ranges, raised for unloader 2 by the
   ratio of the loaded grab weights; R per range from the dead load and the residual stress; integration from the
   inspected depth to the critical depth.
4. Cycles per month: the survey's counts over the days each unloader actually operated during the survey (unloader 1
   was out of service for a week of it), times 25 operating days a month; for unloader 2, times old payload / new
   payload, because the berth conveyor fixes the throughput, so the heavier grab makes fewer cycles.
5. The interval is 0.447 (the geometric middle of 0.40 and 0.50) times the remaining life.
"""
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys

import numpy as np
from scipy.optimize import least_squares

DATA = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/app/output/intervals.json"
FCGR = os.environ.get("FCGR", "fcgr")
CAMPAIGN = [("paris", 0.20, "H1"), ("paris", 0.35, "H1"), ("paris", 0.45, "H1"), ("paris", 0.90, "H1"),
            ("paris", 0.70, "H4")]
REPAIR_MARGIN = 1.0e-3      # FA-3: a repair groove is ground 1 mm deeper than the last MPI indication
DAYS_PER_YEAR, FRACTION = 300.0, 0.447


def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def Y(aT):
    return 1.12 - 0.231 * aT + 10.55 * aT ** 2 - 21.72 * aT ** 3 + 30.39 * aT ** 4


def Mk(aT, LT):
    """BS 7910 (PD 6493:1991, IIW): 2D flaw at the toe of a transverse non-load-carrying attachment"""
    aT = np.asarray(aT, float)
    if LT <= 2.0:
        v = np.where(aT <= 0.05 * LT ** 0.55, 0.51 * LT ** 0.27 * aT ** -0.31, 0.83 * aT ** (-0.15 * LT ** 0.46))
    else:
        v = np.where(aT <= 0.073, 0.615 * aT ** -0.31, 0.83 * aT ** -0.2)
    return np.maximum(v, 1.0)


def run_lab(grade):
    data = []
    for kind, R, heat in CAMPAIGN:
        out = subprocess.run([FCGR, kind, "%.2f" % R, heat], capture_output=True, text=True, check=True).stdout
        pts = [l.split(",") for l in out.splitlines() if l and l[0].isdigit()]
        data.append((kind, R, np.array([float(a) for a, _ in pts]), np.array([float(b) for _, b in pts]),
                     grade[heat] != "S355J2"))
    return data


def fit(data):
    R = np.concatenate([np.full(len(d), r) for _, r, d, _, _ in data])
    dK = np.concatenate([d for _, _, d, _, _ in data])
    v = np.concatenate([x for _, _, _, x, _ in data])
    other = np.concatenate([np.full(len(d), g, float) for _, _, d, _, g in data])

    def U(Rv, q):
        return np.minimum(1.0, q[3] + q[4] * np.asarray(Rv, float))

    def th(Rv, q):
        return np.maximum(5.38 - 6.77 * np.asarray(Rv, float), q[5])

    def lnrate(q, Rv, dKv):
        return q[0] + q[1] * np.log(U(Rv, q) * dKv) + q[2] * np.log(np.clip(1 - th(Rv, q) / dKv, 1e-6, None))

    best = None
    for p0 in (0.3, 0.6, 1.0):
        sol = least_squares(lambda q: q[6] * other + lnrate(q, R, dK) - np.log(v), [-25.0, 3.0, p0, 0.6, 1.0, 2.0, 0.0],
                            bounds=([-60, 1.5, 0.05, 0.2, 0.0, 0.5, -2.0], [10, 6, 3, 1.0, 5.0, 0.999 * dK.min(), 2.0]))
        if best is None or sol.cost < best.cost:
            best = sol
    q = best.x

    def law(dKx, Rx):
        dKx = np.asarray(dKx, float)
        k = th(Rx, q)
        out = np.exp(q[0]) * (U(Rx, q) * dKx) ** q[1] * np.clip(1 - k / np.maximum(dKx, 1e-9), 0, None) ** q[2]
        return np.where(dKx > k, out, 0.0)
    law.q = q
    law.G = float(np.exp(q[6]))
    law.th = lambda Rv: th(Rv, q)
    law.U = lambda Rv: U(Rv, q)
    return law


def cycles_to(law, T, L, a0, a1, smin, sres, ds, n):
    """cycles for the model to grow a crack from a0 to a1 under a spectrum (the example records)"""
    g = lambda a: Mk(a / T, L / T) * Y(a / T) * np.sqrt(np.pi * a)  # noqa: E731
    Rb = np.minimum((smin + sres) / (smin + sres + ds), 0.95)
    a = np.linspace(a0, a1, 3000)
    rr = (law(ds[None, :] * g(a)[:, None], Rb[None, :]) * (n / n.sum())[None, :]).sum(1)
    return float(np.trapezoid(1 / rr, a))


def example_factor(law, rec, cert):
    """the rate factor that makes the model reproduce an earlier crack's record: its growth from the TOFD depth to the
    excavation depth less FA-3's 1 mm, in its operating days, under its own survey counts"""
    h = cert[rec["flange_plate_heat"]]
    sy = float(h["yield_strength_MPa"])
    sres = 0.2 * sy if rec["member_fabrication"].lower().startswith("pwht") else sy
    bins = [(float(k.split("_")[2]), float(v)) for k, v in rec.items() if k.startswith("survey_range")]
    ds, n = np.array([b for b, _ in bins]), np.array([c for _, c in bins])
    T = float(rec["flange_thickness_mm"]) * 1e-3
    L = (float(rec["attachment_thickness_mm"]) + 2 * float(rec["fillet_weld_leg_mm"])) * 1e-3
    a0 = float(rec["crack_depth_found_mm"]) * 1e-3
    a1 = float(rec["excavation_depth_mm"]) * 1e-3 - REPAIR_MARGIN
    N_obs = float(rec["operating_days_found_to_repair"]) / float(rec["survey_days"]) * n.sum()
    return cycles_to(law, T, L, a0, a1, float(rec["dead_load_stress_MPa"]), sres, ds, n) / N_obs


def life_months(law, T, L, a0, smin, sres, ds, n, kmat, days, kc, G=1.0):
    g = lambda a: Mk(a / T, L / T) * Y(a / T) * np.sqrt(np.pi * a)  # noqa: E731
    Rb = np.minimum((smin + sres) / (smin + sres + ds), 0.95)
    aa = np.linspace(a0, 0.5 * T, 20000)
    hit = np.nonzero((smin + ds.max()) * g(aa) >= kmat)[0]
    ac = aa[hit[0]] if len(hit) else 0.5 * T
    a = np.linspace(a0, ac, 3000)
    rr = (law(ds[None, :] * g(a)[:, None], Rb[None, :]) * (n / n.sum())[None, :]).sum(1)
    N = float(np.trapezoid(1 / (G * rr), a))
    return N / (kc * n.sum() / days * DAYS_PER_YEAR / 12.0)


def main():
    reg = {r["component"]: r for r in rows(os.path.join(DATA, "component_register.csv"))}
    cert = {r["heat"]: r for r in rows(os.path.join(DATA, "material_certificates.csv"))}
    insp = {r["component"]: float(r["crack_depth_mm"]) for r in rows(os.path.join(DATA, "inspection_2026.csv"))}
    spec = {}
    for r in rows(os.path.join(DATA, "strain_survey_rainflow.csv")):
        spec.setdefault(r["component"], []).append((float(r["stress_range_MPa"]), float(r["cycles"])))
    # the maintenance log: the survey's dates and any time an unloader was out of service during it; the heavier grab
    # on unloader 2 after the survey (the live-load ranges of every member of that unloader scale with the loaded
    # grab's weight, and at the conveyor's fixed throughput its cycles scale with 1 / payload); and attachments
    # welded on site after the members' PWHT
    log = rows(os.path.join(DATA, "maintenance_log.csv"))
    day = dt.date.fromisoformat
    s0 = [day(r["date"]) for r in log if "survey started" in r["entry"]][0]
    s1 = [day(r["date"]) for r in log if "survey ended" in r["entry"]][0]
    factor, cycles, site_welded, since, down = {}, {}, set(), {}, {}
    for r in log:
        m = re.search(r"Grab \S+ \(([\d.]+) t empty, ([\d.]+) t rated payload\) replaced by \S+ \(([\d.]+) t empty, "
                      r"([\d.]+) t rated\s+payload\)", r["entry"])
        if m:
            factor[r["location"]] = (float(m.group(3)) + float(m.group(4))) / (float(m.group(1)) + float(m.group(2)))
            cycles[r["location"]] = float(m.group(2)) / float(m.group(4))
        if "welded on site" in r["entry"]:
            site_welded.add(r["location"])
        if "out of service" in r["entry"]:
            since[r["location"]] = day(r["date"])
        if "back in service" in r["entry"]:
            a, b = max(since[r["location"]], s0), min(day(r["date"]), s1 + dt.timedelta(days=1))
            down[r["location"]] = down.get(r["location"], 0) + max(0, (b - a).days)
    survey_days = (s1 - s0).days + 1
    grade = {h: r["grade"] for h, r in cert.items()}
    law = fit(run_lab(grade))
    # each heat's rate factor: from the laboratory where the heat or its grade was tested, otherwise from the earlier
    # crack on that heat
    tested = {h for _, _, h in CAMPAIGN}
    hf = {h: (law.G if any(grade[t] == grade[h] and t != "H1" for t in tested) and grade[h] != grade["H1"] else 1.0)
          for h in cert}
    checks = {}
    for name in sorted(os.listdir(os.path.join(DATA, "examples"))):
        rec = {r["item"]: r["value"] for r in rows(os.path.join(DATA, "examples", name))}
        h = rec["flange_plate_heat"]
        f = example_factor(law, rec, cert) * hf[h]
        checks[rec["component"]] = (h, f)
        if h not in tested and not any(grade[t] == grade[h] and t != "H1" for t in tested):
            hf[h] = f
    res = {}
    for cid, r in reg.items():
        h = cert[r["flange_plate_heat"]]
        sy, kmat = float(h["yield_strength_MPa"]), float(h["fracture_toughness_Kmat_MPa_sqrt_m"])
        where = "%s, %s" % (r["member"], r["position"])
        pwht = r["member_fabrication"].lower().startswith("pwht") and where not in site_welded
        sres = 0.2 * sy if pwht else sy
        k = [v for unit, v in factor.items() if r["member"].startswith(unit)]
        kc = [v for unit, v in cycles.items() if r["member"].startswith(unit)]
        days = survey_days - sum(v for unit, v in down.items() if r["member"].startswith(unit))
        ds = np.array([d for d, _ in spec[cid]]) * (k[0] if k else 1.0)
        n = np.array([c for _, c in spec[cid]])
        T = float(r["flange_thickness_mm"]) * 1e-3
        L = (float(r["attachment_thickness_mm"]) + 2 * float(r["fillet_weld_leg_mm"])) * 1e-3
        res[cid] = round(FRACTION * life_months(law, T, L, insp[cid] * 1e-3, float(r["dead_load_stress_MPa"]), sres, ds,
                                                n, kmat, days, kc[0] if kc else 1.0,
                                                hf[r["flange_plate_heat"]]), 4)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"intervals_months": res}, f, indent=1)
    print("examples (rate factor the fitted law needs): %s; heat factors %s" % (
        ", ".join("%s on %s x%.3f" % (k, h, f) for k, (h, f) in sorted(checks.items())),
        ", ".join("%s %.3f" % kv for kv in sorted(hf.items()))))
    print("fit m %.3f p %.3f dKth %.2f U0 %.3f closure-free from R %.3f, S460NL x%.3f; survey %d days, out of service %s; unloader 2 ranges x%s, cycles x%s; "
          "site welded %s; wrote %s" % (law.q[1], law.q[2], float(law.th(0.85)), law.q[3],
                                        (1 - law.q[3]) / max(law.q[4], 1e-9), law.G, survey_days, down, factor, cycles,
                                        sorted(site_welded), OUT))


if __name__ == "__main__":
    main()
