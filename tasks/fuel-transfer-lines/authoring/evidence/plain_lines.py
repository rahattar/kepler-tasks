#!/usr/bin/env python3
"""plain_lines.py PACKAGE_DIR OUT_CSV: the second solution as it is first written, one case at a time.

The formulation of second_lines.py (the pipe in y = ln(Tb - Ta) and s = x^(1/3), the same choice of pipes to
survey, a pair taken through its hours by TS-2 4.2) with library routines and nothing done for speed: the
pipe by scipy's solve_ivp to a relative tolerance of 1e-7, the wall temperature and every other root by
scipy's brentq, one pipe at a time, and for every record of a pair the whole ladder of divisions worked out
afresh. It is right, and on a full site it is far too slow for the limit.
"""
import csv
import json
import math
import os
import subprocess
import sys

from scipy.integrate import solve_ivp
from scipy.optimize import brentq



def ladder():
    low = [3e-4 * (0.24 / 3e-4) ** (i / 21.0) for i in range(22)]
    return low + [0.26 + 0.02 * i for i in range(25)] + [1.0 - v for v in reversed(low)]


class Oil:
    def __init__(self, row):
        self.rho, self.cp, self.k = float(row["density_kg_m3"]), float(row["cp_J_kgK"]), float(row["k_W_mK"])
        y50, y100 = (math.log10(math.log10(float(row[key]) + 0.7)) for key in ("nu50_cSt", "nu100_cSt"))
        self.B = (y50 - y100) / (math.log10(373.15) - math.log10(323.15))
        self.A = y50 + self.B * math.log10(323.15)

    def nu(self, kelvin):
        return (10.0 ** (10.0 ** (self.A - self.B * math.log10(kelvin))) - 0.7) * 1e-6


def pipe(flow, bore, length, uo, t_in, t_amb, oil):
    """(pressure drop in Pa, outlet temperature in C) of one pipe; flow in kg/s."""
    speed = flow / (oil.rho * math.pi * bore * bore / 4.0)
    graetz_x = speed * bore * bore * oil.rho * oil.cp / oil.k
    amb_k = t_amb + 273.15

    def slopes(s, state):
        if s <= 0.0:
            return [0.0, 0.0]
        bulk_k = amb_k + math.exp(state[0])
        nu_b = oil.nu(bulk_k)
        h0 = (3.66 ** 3 + 0.7 ** 3 + (1.077 * (graetz_x / s ** 3) ** (1.0 / 3.0) - 0.7) ** 3) ** (1.0 / 3.0) * oil.k / bore
        balance = lambda wall: h0 * (nu_b / oil.nu(wall)) ** 0.14 * (bulk_k - wall) - uo * (wall - amb_k)
        wall = brentq(balance, amb_k, bulk_k, xtol=1e-11) if bulk_k - amb_k > 1e-9 else bulk_k
        ratio = nu_b / oil.nu(wall)
        h = h0 * ratio ** 0.14
        jac = 3.0 * s * s
        return [-math.pi * bore * (h * uo / (h + uo)) / (flow * oil.cp) * jac, 32.0 * nu_b * oil.rho * speed / (bore * bore) / math.sqrt(ratio) * jac]

    end = solve_ivp(slopes, (0.0, length ** (1.0 / 3.0)), [math.log(max(t_in - t_amb, 1e-9)), 0.0], method="RK45", rtol=1e-7, atol=1e-10)
    return end.y[1][-1], t_amb + math.exp(end.y[0][-1])


def read(package, name):
    with open(os.path.join(package, name), newline="") as handle:
        return list(csv.DictReader(handle))


def main(package, out_csv):
    oils = {r["oil"]: Oil(r) for r in read(package, "oils.csv")}
    register = {r["line"]: r for r in read(package, "lines.csv")}
    surveys, jobs, records = read(package, "surveys.csv"), read(package, "work_log.csv"), read(package, "records.csv")
    with open(os.path.join(package, "site.json")) as handle:
        allowance = int(json.load(handle)["survey_allowance"])
    line_of = lambda p: p[:p.rindex("-")]
    oil_of = lambda p: oils[register[line_of(p)]["oil"]]
    laid = lambda p: float(register[line_of(p)]["bore_mm"]) * 1e-3
    run_len = lambda p: float(register[line_of(p)]["length_m"])

    def uo_from(row, bore):
        p = row["pipe"]
        miss = lambda ln_u: pipe(float(row["flow_t_h"]) / 3.6, bore, run_len(p), math.exp(ln_u), float(row["t_in_C"]),
                                 float(row["t_amb_C"]), oil_of(p))[1] - float(row["t_out_C"])
        return math.exp(brentq(miss, math.log(0.02), math.log(400.0), xtol=1e-12))

    def drop_of(row, flow_t_h, bore, uo):
        p = row["pipe"]
        return pipe(float(flow_t_h) / 3.6, bore, run_len(p), uo, float(row["t_in_C"]), float(row["t_amb_C"]), oil_of(p))[0]

    dates = sorted({r["date"] for r in surveys})
    at = {(r["pipe"], r["date"]): r for r in surveys}
    pipes = sorted({r["pipe"] for r in surveys})
    uo_file = {(r["pipe"], r["date"]): uo_from(r, laid(r["pipe"])) for r in surveys}
    covering = [(j["pipe"], j["date"]) for j in jobs if "covering" in j["job"].lower()]
    since_last = sorted({p for p, d in covering if d > dates[-1]})
    narrow = {}
    for name, reg in register.items():
        if reg["pipes"] != "2":
            continue
        a, b = name + "-A", name + "-B"
        short = [drop_of(at[(a, d)], at[(a, d)]["flow_t_h"], laid(a), uo_file[(a, d)])
                 / drop_of(at[(b, d)], at[(b, d)]["flow_t_h"], laid(b), uo_file[(b, d)]) - 1.0 for d in dates]
        if all(v < -0.04 for v in short):
            narrow[a] = b
        elif all(v > 0.04 for v in short):
            narrow[b] = a
    drifting = []
    for p in pipes:
        job_between = any(q == p and dates[-2] < when <= dates[-1] for q, when in covering)
        if p not in since_last and p not in narrow and not job_between and abs(uo_file[(p, dates[-1])] / uo_file[(p, dates[-2])] - 1.0) > 0.04:
            drifting.append(p)
    order = (since_last + sorted(narrow) + drifting)[:allowance]
    fresh = {}
    if order:
        try:
            said = subprocess.run(["heatsurvey", package] + order, capture_output=True, text=True)
            if said.returncode == 0:
                fresh = {r["pipe"]: r for r in csv.DictReader(said.stdout.splitlines())}
        except OSError:
            pass
    bore_now = {p: laid(p) for p in pipes}
    uo_now = {p: uo_file[(p, dates[-1])] for p in pipes}
    for p, row in fresh.items():
        if p not in narrow:
            uo_now[p] = uo_from(row, laid(p))
    for p, mate in narrow.items():
        if p in fresh:
            row = fresh[p]
            mate_flow = float(row["line_flow_t_h"]) - float(row["flow_t_h"])
        else:
            row = at[(p, dates[-1])]
            mate_flow = float(at[(mate, dates[-1])]["flow_t_h"])
        target = drop_of(row, mate_flow, bore_now[mate], uo_now[mate])
        miss = lambda bore: drop_of(row, row["flow_t_h"], bore, uo_from(row, bore)) - target
        bore_now[p] = brentq(miss, 0.5 * laid(p), 1.3 * laid(p), xtol=1e-9)
        uo_now[p] = uo_from(row, bore_now[p])

    rungs = ladder()
    held = {}
    result = {}
    by_line = {}
    for r in records:
        by_line.setdefault(r["line"], []).append(r)
    for name, rows in by_line.items():
        rows.sort(key=lambda r: float(r["hour"]))
        a, b = name + "-A", name + "-B"
        oil = oil_of(a)
        for r in rows:
            flow, t_in, t_amb = float(r["flow_t_h"]) / 3.6, float(r["t_in_C"]), float(r["t_amb_C"])
            if register[name]["pipes"] == "1":
                d, t = pipe(flow, bore_now[a], run_len(a), uo_now[a], t_in, t_amb, oil)
                result[r["record"]] = (d, t)
                continue
            both = lambda share: (pipe(share * flow, bore_now[a], run_len(a), uo_now[a], t_in, t_amb, oil),
                                  pipe((1.0 - share) * flow, bore_now[b], run_len(b), uo_now[b], t_in, t_amb, oil))
            apart = lambda share: (lambda two: two[0][0] - two[1][0])(both(share))
            on = [apart(v) for v in rungs]
            if name not in held:
                turns = [j for j in range(len(rungs) - 1) if (on[j] < 0) != (on[j + 1] < 0)]
                j = min(turns, key=lambda j: abs(rungs[j] - 0.5))
                lo, hi = rungs[j], rungs[j + 1]
            else:
                start = held[name]
                f0 = apart(start)
                lo = hi = start
                if f0 > 0:
                    below = [j for j in range(len(rungs)) if rungs[j] < start and on[j] <= 0]
                    if below:
                        hi = rungs[max(below)]
                        if max(below) + 1 < len(rungs) and rungs[max(below) + 1] < start:
                            lo = rungs[max(below) + 1]
                elif f0 < 0:
                    above = [j for j in range(len(rungs)) if rungs[j] > start and on[j] >= 0]
                    if above:
                        hi = rungs[min(above)]
                        if min(above) >= 1 and rungs[min(above) - 1] > start:
                            lo = rungs[min(above) - 1]
            if lo == hi:
                share = lo
            elif apart(hi) == 0:
                share = hi
            else:
                share = brentq(apart, min(lo, hi), max(lo, hi), xtol=1e-12)
            held[name] = share
            (da, ta), (db, tb) = both(share)
            result[r["record"]] = (0.5 * (da + db), share * ta + (1.0 - share) * tb)

    with open(out_csv, "w", newline="") as handle:
        sheet = csv.writer(handle, lineterminator="\n")
        sheet.writerow(["record", "dp_kPa", "t_out_C"])
        for r in records:
            sheet.writerow([r["record"], "%.7g" % (result[r["record"]][0] * 1e-3), "%.5f" % result[r["record"]][1]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
