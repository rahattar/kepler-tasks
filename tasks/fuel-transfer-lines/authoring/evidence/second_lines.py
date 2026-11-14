#!/usr/bin/env python3
"""second_lines.py PACKAGE_DIR OUT_CSV: a second solution, written apart from solution/lines.py, in its fast form.

It shares the documents with the reference and nothing else: not a function, not a method.

The pipe. The unknown is y = ln(Tb - Ta), for which TS-2 3.1 reads dy/dx = -pi D U / (m cp) with
U = h Uo / (h + Uo), and the coordinate is s = x^(1/3), in which the entrance of the pipe is smooth
(dx = 3 s^2 ds). y and the pressure are carried together by the classical fourth-order Runge-Kutta rule in
equal steps of s. The Graetz number is u D^2 rho cp / (k x), which needs no viscosity. The wall temperature of
3.2 is the root of h(Tw) (Tb - Tw) - Uo (Tw - Ta), found by Newton's method with the derivative of the D341
viscosity written out.

A coefficient from a heat-loss reading, a bore from a pair's division, and a pair's division itself are all
roots of one function of one unknown, found by Ridders' method on all cases at once.

Which pipes to survey: the covering jobs after the last campaign; in a pair, the pipe whose bore has to be
smaller than the register's for the pair to have one pressure drop at the flows read, campaign after campaign
(`bore_ratio` solves that bore at each campaign); and a pipe whose coefficient moves by more than the readings
can explain between two campaigns with no covering job between.

The records. For every record of a pair, the difference of the two pressure drops is evaluated on a ladder of
divisions once. Then each pair is taken through its hours in order, all pairs side by side, exactly as TS-2
4.2 puts it: the difference at the division held says which pipe the oil leaves, the ladder gives the first
change of sign on that side, and the division there is refined. The run opens on the one division 4.3
promises.
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

LN10 = np.log(10.0)
RK_STEPS = 16
NEWTON = 4                                     # steps for the wall temperature
LADDER = np.concatenate([np.geomspace(3e-4, 0.24, 22), np.linspace(0.26, 0.74, 25), 1.0 - np.geomspace(0.24, 3e-4, 22)])


class Oil:
    """Arrays of oil properties, one entry a case."""

    def __init__(self, rows):
        self.rho = np.array([float(r["density_kg_m3"]) for r in rows])
        self.cp = np.array([float(r["cp_J_kgK"]) for r in rows])
        self.k = np.array([float(r["k_W_mK"]) for r in rows])
        y50 = np.log10(np.log10(np.array([float(r["nu50_cSt"]) for r in rows]) + 0.7))
        y100 = np.log10(np.log10(np.array([float(r["nu100_cSt"]) for r in rows]) + 0.7))
        self.B = (y50 - y100) / (np.log10(373.15) - np.log10(323.15))
        self.A = y50 + self.B * np.log10(323.15)

    def pick(self, index):
        other = Oil.__new__(Oil)
        for name in ("rho", "cp", "k", "A", "B"):
            setattr(other, name, getattr(self, name)[index])
        return other

    def nu(self, kelvin):
        """(kinematic viscosity in m2/s, its relative slope 1/nu dnu/dT in 1/K)"""
        big = 10.0 ** (self.A - self.B * np.log10(kelvin))          # log10 of (cSt + 0.7)
        z = 10.0 ** big
        return (z - 0.7) * 1e-6, -z * LN10 * big * self.B / (kelvin * (z - 0.7))


def pipe(flow, bore, length, uo, t_in, t_amb, oil, steps=RK_STEPS):
    """(pressure drop in Pa, outlet temperature in C) for arrays of cases; flow in kg/s."""
    area = np.pi * bore * bore / 4.0
    speed = flow / (oil.rho * area)
    graetz_x = speed * bore * bore * oil.rho * oil.cp / oil.k           # Graetz number times x
    amb_k = t_amb + 273.15
    fourth = 3.66 ** 3 + 0.7 ** 3

    def slopes(s, y):
        """d/ds of (ln excess temperature, pressure lost) at s = x^(1/3) > 0"""
        bulk_k = amb_k + np.exp(y)
        nu_b, _ = oil.nu(bulk_k)
        h0 = (fourth + (1.077 * np.cbrt(graetz_x / s ** 3) - 0.7) ** 3) ** (1.0 / 3.0) * oil.k / bore
        wall = (h0 * bulk_k + uo * amb_k) / (h0 + uo)
        for _ in range(NEWTON):
            nu_w, slope = oil.nu(wall)
            lift = (nu_b / nu_w) ** 0.14
            miss = h0 * lift * (bulk_k - wall) - uo * (wall - amb_k)
            d_miss = h0 * lift * (-0.14 * slope * (bulk_k - wall) - 1.0) - uo
            wall = np.clip(wall - miss / d_miss, amb_k, bulk_k)
        nu_w, _ = oil.nu(wall)
        ratio = nu_b / nu_w
        h = h0 * ratio ** 0.14
        through = h * uo / (h + uo)
        jac = 3.0 * s * s
        return -np.pi * bore * through / (flow * oil.cp) * jac, 32.0 * nu_b * oil.rho * speed / (bore * bore) / np.sqrt(ratio) * jac

    y = np.log(np.maximum(t_in - t_amb, 1e-9)) + np.zeros_like(flow)
    lost = np.zeros_like(y)
    ds = length ** (1.0 / 3.0) / steps + np.zeros_like(flow)          # each case has its own step: its own length
    for i in range(steps):
        # at the inlet itself both slopes are zero: dx/ds is, and the film there is without limit
        k1 = (np.zeros_like(y), np.zeros_like(y)) if i == 0 else slopes(i * ds, y)
        k2 = slopes((i + 0.5) * ds, y + 0.5 * ds * k1[0])
        k3 = slopes((i + 0.5) * ds, y + 0.5 * ds * k2[0])
        k4 = slopes((i + 1.0) * ds, y + ds * k3[0])
        y = y + ds / 6.0 * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
        lost = lost + ds / 6.0 * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
    return lost, t_amb + np.exp(y)


def ridders(f, a, b, fa, fb, rounds=9):
    """Roots of f between a and b, arrays; f(a) and f(b) have opposite signs."""
    x = 0.5 * (a + b)
    for _ in range(rounds):
        m = 0.5 * (a + b)
        fm = f(m)
        x = m + (m - a) * np.sign(fa - fb) * fm / np.sqrt(np.maximum(fm * fm - fa * fb, 1e-300))
        fx = f(x)
        hit = fx == 0.0
        via_m = (~hit) & (fm * fx < 0)                      # the root is between m and x
        via_a = (~hit) & (~via_m) & (fa * fx < 0)           # between a and x
        via_b = (~hit) & (~via_m) & (~via_a)                # between x and b
        a, fa, b, fb = (np.where(hit | via_b, x, np.where(via_m, m, a)), np.where(hit | via_b, fx, np.where(via_m, fm, fa)),
                        np.where(via_b, b, x), np.where(via_b, fb, fx))
        if np.max(np.abs(b - a) / (1.0 + np.abs(x))) < 1e-11:
            break
    return x


def coefficient(flow, bore, length, t_in, t_out, t_amb, oil):
    """TS-2 5.2 for arrays of heat-loss readings."""
    miss = lambda ln_u: pipe(flow, bore, length, np.exp(ln_u), t_in, t_amb, oil)[1] - t_out
    lo, hi = np.full(flow.shape, np.log(0.02)), np.full(flow.shape, np.log(400.0))
    return np.exp(ridders(miss, lo, hi, miss(lo), miss(hi)))


def read(package, name):
    with open(os.path.join(package, name), newline="") as handle:
        return list(csv.DictReader(handle))


def main(package, out_csv):
    oils = {r["oil"]: r for r in read(package, "oils.csv")}
    register = {r["line"]: r for r in read(package, "lines.csv")}
    surveys, jobs, records = read(package, "surveys.csv"), read(package, "work_log.csv"), read(package, "records.csv")
    with open(os.path.join(package, "site.json")) as handle:
        allowance = int(json.load(handle)["survey_allowance"])
    line_of = lambda p: p[:p.rindex("-")]
    oil_for = lambda lines: Oil([oils[register[n]["oil"]] for n in lines])
    laid = lambda p: float(register[line_of(p)]["bore_mm"]) * 1e-3
    run_len = lambda p: float(register[line_of(p)]["length_m"])
    f = lambda rows, key: np.array([float(r[key]) for r in rows])

    def uo_from(rows, bores):
        return coefficient(f(rows, "flow_t_h") / 3.6, np.asarray(bores, float), np.array([run_len(r["pipe"]) for r in rows]),
                           f(rows, "t_in_C"), f(rows, "t_out_C"), f(rows, "t_amb_C"), oil_for([line_of(r["pipe"]) for r in rows]))

    def drop_of(row, flow_t_h, bore, uo):
        """the pressure drop of the pipe of a reading at a flow, under that reading's temperatures"""
        one = lambda v: np.array([float(v)])
        return pipe(one(flow_t_h) / 3.6, one(bore), one(run_len(row["pipe"])), one(uo), one(row["t_in_C"]), one(row["t_amb_C"]),
                    oil_for([line_of(row["pipe"])]))[0][0]

    def bore_and_uo(row, mate_flow_t_h, mate_bore, mate_uo):
        """the bore, and with it the coefficient, at which the pipe of a reading has its mate's pressure drop"""
        target = drop_of(row, mate_flow_t_h, mate_bore, mate_uo)
        full = laid(row["pipe"])

        def miss(bore):
            out = []
            for b in bore:
                u = uo_from([row], [b])[0]
                out.append(drop_of(row, row["flow_t_h"], b, u) - target)
            return np.array(out)
        lo, hi = np.array([0.5 * full]), np.array([1.3 * full])
        bore = float(ridders(miss, lo, hi, miss(lo), miss(hi), rounds=8)[0])
        return bore, float(uo_from([row], [bore])[0])

    dates = sorted({r["date"] for r in surveys})
    at = {(r["pipe"], r["date"]): r for r in surveys}
    pipes = sorted({r["pipe"] for r in surveys})
    uo_file = dict(zip([(r["pipe"], r["date"]) for r in surveys], uo_from(surveys, [laid(r["pipe"]) for r in surveys])))

    covering = [(j["pipe"], j["date"]) for j in jobs if "covering" in j["job"].lower()]
    since_last = sorted({p for p, d in covering if d > dates[-1]})

    # a pair has one pressure drop: the bore one pipe would need, as a share of the register's, at each campaign
    narrow = {}
    for name, reg in register.items():
        if reg["pipes"] != "2":
            continue
        a, b = name + "-A", name + "-B"
        shortfall = []
        for d in dates:
            da = drop_of(at[(a, d)], at[(a, d)]["flow_t_h"], laid(a), uo_file[(a, d)])
            db = drop_of(at[(b, d)], at[(b, d)]["flow_t_h"], laid(b), uo_file[(b, d)])
            shortfall.append(da / db - 1.0)
        if all(v < -0.04 for v in shortfall):
            narrow[a] = b
        elif all(v > 0.04 for v in shortfall):
            narrow[b] = a
    drifting = []
    for p in pipes:
        if p in since_last or p in narrow:
            continue
        for d0, d1 in zip(dates[:-1], dates[1:]):
            job_between = any(q == p and d0 < when <= d1 for q, when in covering)
            if d1 == dates[-1] and not job_between and abs(uo_file[(p, d1)] / uo_file[(p, d0)] - 1.0) > 0.04:
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
            uo_now[p] = float(uo_from([row], [laid(p)])[0])
    for p, mate in narrow.items():
        if p in fresh:
            row = fresh[p]
            mate_flow = float(row["line_flow_t_h"]) - float(row["flow_t_h"])
        else:
            row = at[(p, dates[-1])]
            mate_flow = float(at[(mate, dates[-1])]["flow_t_h"])
        bore_now[p], uo_now[p] = bore_and_uo(row, mate_flow, bore_now[mate], uo_now[mate])

    dp = {}
    t_out = {}
    singles = [r for r in records if register[r["line"]]["pipes"] == "1"]
    if singles:
        ps = [r["line"] + "-A" for r in singles]
        d, t = pipe(f(singles, "flow_t_h") / 3.6, np.array([bore_now[p] for p in ps]), np.array([run_len(p) for p in ps]),
                    np.array([uo_now[p] for p in ps]), f(singles, "t_in_C"), f(singles, "t_amb_C"), oil_for([r["line"] for r in singles]))
        for r, dd, tt in zip(singles, d, t):
            dp[r["record"]], t_out[r["record"]] = dd, tt

    twins = [r for r in records if register[r["line"]]["pipes"] == "2"]
    if twins:
        n, m = len(twins), len(LADDER)
        flow, t_in, t_amb = f(twins, "flow_t_h") / 3.6, f(twins, "t_in_C"), f(twins, "t_amb_C")
        length = np.array([run_len(r["line"] + "-A") for r in twins])
        ba, bb = (np.array([bore_now[r["line"] + s] for r in twins]) for s in ("-A", "-B"))
        ua, ub = (np.array([uo_now[r["line"] + s] for r in twins]) for s in ("-A", "-B"))
        oil = oil_for([r["line"] for r in twins])

        def apart(share, idx):
            """drop of A less drop of B for the records idx at the shares given; also both pipes' results"""
            o = oil.pick(idx)
            a = pipe(share * flow[idx], ba[idx], length[idx], ua[idx], t_in[idx], t_amb[idx], o)
            b = pipe((1.0 - share) * flow[idx], bb[idx], length[idx], ub[idx], t_in[idx], t_amb[idx], o)
            return a[0] - b[0], a, b

        every = np.repeat(np.arange(n), m)
        on_ladder = apart(np.tile(LADDER, n), every)[0].reshape(n, m)
        hours = {}
        for i, r in enumerate(twins):
            hours.setdefault(r["line"], []).append((float(r["hour"]), i))
        runs = [[i for _, i in sorted(v)] for v in hours.values()]
        held = np.full(n, np.nan)
        for step in range(max(len(v) for v in runs)):
            now = np.array([v[step] for v in runs if step < len(v)])
            before = np.array([v[step - 1] if step else -1 for v in runs if step < len(v)])
            lo, hi, f_lo, f_hi = (np.zeros(len(now)) for _ in range(4))
            if step == 0:
                for q, i in enumerate(now):
                    turns = np.nonzero(np.sign(on_ladder[i, :-1]) != np.sign(on_ladder[i, 1:]))[0]
                    j = turns[np.argmin(np.abs(LADDER[turns] - 0.5))]
                    lo[q], hi[q], f_lo[q], f_hi[q] = LADDER[j], LADDER[j + 1], on_ladder[i, j], on_ladder[i, j + 1]
            else:
                start = held[before]
                f_start = apart(start, now)[0]
                for q, i in enumerate(now):
                    lo[q] = hi[q] = start[q]
                    f_lo[q] = f_hi[q] = f_start[q]
                    if f_start[q] > 0:                       # A has the higher drop: oil leaves A, its share falls
                        rungs = np.nonzero((LADDER < start[q]) & (on_ladder[i] <= 0))[0]
                        if len(rungs):
                            j = rungs.max()
                            hi[q], f_hi[q] = LADDER[j], on_ladder[i, j]
                            if j + 1 < m and LADDER[j + 1] < start[q]:
                                lo[q], f_lo[q] = LADDER[j + 1], on_ladder[i, j + 1]
                    elif f_start[q] < 0:                     # oil leaves B
                        rungs = np.nonzero((LADDER > start[q]) & (on_ladder[i] >= 0))[0]
                        if len(rungs):
                            j = rungs.min()
                            hi[q], f_hi[q] = LADDER[j], on_ladder[i, j]
                            if j >= 1 and LADDER[j - 1] > start[q]:
                                lo[q], f_lo[q] = LADDER[j - 1], on_ladder[i, j - 1]
            between = f_lo * f_hi < 0
            share = np.where(f_hi == 0, hi, lo)
            if between.any():
                share[between] = ridders(lambda x: apart(x, now[between])[0], lo[between], hi[between], f_lo[between], f_hi[between])
            _, a, b = apart(share, now)
            held[now] = share
            for q, i in enumerate(now):
                dp[twins[i]["record"]] = 0.5 * (a[0][q] + b[0][q])
                t_out[twins[i]["record"]] = share[q] * a[1][q] + (1.0 - share[q]) * b[1][q]

    with open(out_csv, "w", newline="") as handle:
        sheet = csv.writer(handle, lineterminator="\n")
        sheet.writerow(["record", "dp_kPa", "t_out_C"])
        for r in records:
            sheet.writerow([r["record"], "%.7g" % (dp[r["record"]] * 1e-3), "%.5f" % t_out[r["record"]]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
