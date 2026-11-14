#!/usr/bin/env python3
"""lines.py PACKAGE_DIR OUT_CSV: every hourly record of a site's heated oil lines to TS-2.

1. `coefficients_on_file`: the outside coefficient of every pipe at every campaign, the value for which TS-2
   3.1 to 3.3 give the outlet temperature that was read (5.2), with the bore of the register.
2. What the one survey order has to read (`pipes_to_survey`):
     - the pipes whose covering was renewed or repaired after the last campaign (5.3, the work log);
     - a pipe of a pair that is narrower than it was laid: with the register's bore for both pipes, the
       pressure drops of the two at the flows read in a survey differ, the same way in every campaign,
       where 4.1 says they are one pressure drop;
     - a pipe whose coefficient changes from one campaign to the next with no work on its covering between.
3. `as_they_stand`: the order is placed with `heatsurvey`. A surveyed pipe takes the coefficient of the new
   reading. For a narrower pipe the bore is found first: the bore at which the pipe, with the coefficient that
   bore gives from the new reading, has the pressure drop of its mate at the mate's flow in the same reading.
4. `calculate`: single pipes directly; a pair by finding every division of the delivered oil at which the two
   pipes have one pressure drop, and following the pair through its records in hour order by 4.2 and 4.3.

The pipe itself (`march`): the heat balance 3.1 taken along the pipe in steps crowded towards the inlet, each
step with the local decay of the oil's excess temperature at the step's middle, the wall temperature of 3.2
found by iteration, the pressure gradient 3.4 summed with it. Every argument is an array, one entry a case, so
that all cases of a kind are taken in one sweep.
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np

STEPS = 50                                     # along a pipe
_low = np.geomspace(2e-4, 0.30, 26)
SHARES = np.concatenate([_low, np.linspace(0.32, 0.68, 19), (1 - _low)[::-1]])     # of a pair's oil in pipe A
DROPS_APART = 0.06                             # ln of the ratio of two pressure drops that 4.1 says are one
COEFFICIENT_MOVED = 0.05                       # ln of the ratio of a pipe's coefficient at two campaigns


def walther(nu50, nu100):
    """A and B of TS-2 2.2 from the viscosities at 50 C and 100 C in cSt."""
    z = lambda nu: np.log10(np.log10(np.asarray(nu, float) + 0.7))
    t50, t100 = np.log10(323.15), np.log10(373.15)
    B = (z(nu50) - z(nu100)) / (t100 - t50)
    return z(nu50) + B * t50, B


def viscosity(A, B, t_C):
    """kinematic viscosity in m2/s"""
    return (10.0 ** (10.0 ** (A - B * np.log10(t_C + 273.15))) - 0.7) * 1e-6


def march(flow, bore, length, uo, t_in, t_amb, oil, steps=STEPS):
    """(pressure drop in Pa, outlet temperature in C) of pipes; flow in kg/s, bore and length in m."""
    flow, bore, length, uo, t_in, t_amb, rho, cp, k, A, B = np.broadcast_arrays(
        *[np.asarray(x, float) for x in (flow, bore, length, uo, t_in, t_amb, oil["rho"], oil["cp"], oil["k"], oil["A"], oil["B"])])
    station = np.linspace(0.0, 1.0, steps + 1) ** 3.0
    velocity = flow / (rho * np.pi * bore * bore / 4.0)
    developed = 3.66 ** 3 + 0.7 ** 3

    def local(tb, x):
        nu_b = viscosity(A, B, tb)
        graetz = (velocity * bore / nu_b) * (nu_b * rho * cp / k) * bore / x
        film0 = (developed + (1.077 * np.cbrt(graetz) - 0.7) ** 3) ** (1.0 / 3.0) * k / bore
        tw = (film0 * tb + uo * t_amb) / (film0 + uo)
        for _ in range(60):
            ratio = nu_b / viscosity(A, B, tw)
            film = film0 * ratio ** 0.14
            again = (film * tb + uo * t_amb) / (film + uo)
            settled = np.max(np.abs(again - tw)) < 1e-7
            tw = again
            if settled:
                break
        ratio = nu_b / viscosity(A, B, tw)
        film = film0 * ratio ** 0.14
        decay = np.pi * bore * film * uo / (film + uo) / (flow * cp)        # of (tb - t_amb), per metre
        gradient = 32.0 * nu_b * rho * velocity / (bore * bore) / np.sqrt(ratio)
        return decay, gradient

    tb = t_in.copy()
    drop = np.zeros(flow.shape)
    for i in range(steps):
        h = (station[i + 1] - station[i]) * length
        x = 0.5 * (station[i] + station[i + 1]) * length
        first, _ = local(tb, x)
        decay, gradient = local(t_amb + (tb - t_amb) * np.exp(-0.5 * h * first), x)
        tb = t_amb + (tb - t_amb) * np.exp(-h * decay)
        drop = drop + h * gradient
    return drop, tb


def illinois(g, lo, hi, g_lo, g_hi, tol, rounds=30):
    """A root of g between lo and hi (arrays, g of opposite sign at the two)."""
    for _ in range(rounds):
        x = (lo * g_hi - hi * g_lo) / (g_hi - g_lo)
        gx = g(x)
        same = gx * g_lo > 0
        g_hi = np.where(same, g_hi * 0.5, gx)
        hi = np.where(same, hi, x)
        g_lo, lo = np.where(same, gx, g_lo * 0.5), np.where(same, x, lo)
        if np.max(np.abs(hi - lo) / tol) < 1.0:
            break
    return (lo * g_hi - hi * g_lo) / (g_hi - g_lo)


def coefficient(flow, bore, length, t_in, t_out, t_amb, oil):
    """TS-2 5.2: the outside coefficient for which the pipe gives the outlet temperature that was read."""
    miss = lambda ln_u: march(flow, bore, length, np.exp(ln_u), t_in, t_amb, oil)[1] - t_out
    lo, hi = np.full(len(flow), np.log(0.05)), np.full(len(flow), np.log(200.0))
    return np.exp(illinois(miss, lo, hi, miss(lo), miss(hi), 1e-7))


def divisions(delivered, case):
    """Every division of every case of a pair at which its two pipes have one pressure drop (TS-2 4.1).

    Returns arrays over the divisions found, in order of case and of share: the case, the share of pipe A,
    the pressure drop and the mixed outlet temperature.
    """
    n, m = len(delivered), len(SHARES)
    in_a = SHARES[None, :] * delivered[:, None]
    wide = {key: np.repeat(value, m) for key, value in case.items()}
    apart = (march(in_a.ravel(), wide["bore_a"], wide["length"], wide["uo_a"], wide["t_in"], wide["t_amb"], wide)[0]
             - march((delivered[:, None] - in_a).ravel(), wide["bore_b"], wide["length"], wide["uo_b"], wide["t_in"], wide["t_amb"], wide)[0]).reshape(n, m)
    sign = np.where(apart >= 0, 1.0, -1.0)
    row, col = np.nonzero(sign[:, :-1] * sign[:, 1:] < 0)
    at = {key: value[row] for key, value in case.items()}
    total = delivered[row]
    miss = lambda a: (march(a, at["bore_a"], at["length"], at["uo_a"], at["t_in"], at["t_amb"], at)[0]
                      - march(total - a, at["bore_b"], at["length"], at["uo_b"], at["t_in"], at["t_amb"], at)[0])
    g_lo = np.where(apart[row, col] == 0, -1e-30, apart[row, col])
    g_hi = np.where(apart[row, col + 1] == 0, 1e-30, apart[row, col + 1])
    a = illinois(miss, in_a[row, col].copy(), in_a[row, col + 1].copy(), g_lo, g_hi, 1e-8 * total)
    drop_a, out_a = march(a, at["bore_a"], at["length"], at["uo_a"], at["t_in"], at["t_amb"], at)
    drop_b, out_b = march(total - a, at["bore_b"], at["length"], at["uo_b"], at["t_in"], at["t_amb"], at)
    return row, a / total, 0.5 * (drop_a + drop_b), (a * out_a + (total - a) * out_b) / total


class Site:
    """A package as read, and what is worked out from it."""

    def __init__(self, package):
        table = lambda name: list(csv.DictReader(open(os.path.join(package, name), newline="")))
        self.package = package
        self.oils = {row["oil"]: row for row in table("oils.csv")}
        self.lines = {row["line"]: row for row in table("lines.csv")}
        self.surveys, self.jobs, self.records = table("surveys.csv"), table("work_log.csv"), table("records.csv")
        with open(os.path.join(package, "site.json")) as handle:
            self.allowance = int(json.load(handle)["survey_allowance"])
        self.pipes = sorted({row["pipe"] for row in self.surveys})
        self.bore = {pipe: float(self.lines[self.line(pipe)]["bore_mm"]) / 1e3 for pipe in self.pipes}      # as laid
        self.length = {pipe: float(self.lines[self.line(pipe)]["length_m"]) for pipe in self.pipes}
        self.campaigns = sorted({row["date"] for row in self.surveys})
        self.reading = {(row["pipe"], row["date"]): row for row in self.surveys}

    @staticmethod
    def line(pipe):
        return pipe.rsplit("-", 1)[0]

    def oil(self, lines):
        rows = [self.oils[self.lines[name]["oil"]] for name in lines]
        A, B = walther(np.array([float(r["nu50_cSt"]) for r in rows]), np.array([float(r["nu100_cSt"]) for r in rows]))
        return dict(rho=np.array([float(r["density_kg_m3"]) for r in rows]), cp=np.array([float(r["cp_J_kgK"]) for r in rows]),
                    k=np.array([float(r["k_W_mK"]) for r in rows]), A=A, B=B)

    def coefficients(self, readings, bore=None):
        """The outside coefficient each heat-loss reading gives (rows as in surveys.csv)."""
        bore = bore or self.bore
        column = lambda key: np.array([float(row[key]) for row in readings])
        return coefficient(column("flow_t_h") / 3.6, np.array([bore[row["pipe"]] for row in readings]),
                           np.array([self.length[row["pipe"]] for row in readings]), column("t_in_C"), column("t_out_C"),
                           column("t_amb_C"), self.oil([self.line(row["pipe"]) for row in readings]))

    def drop_at(self, pipe, flow_kg_s, reading, uo, bore=None):
        """Pressure drop of a pipe at a flow, under the inlet and surroundings of a reading."""
        return march(np.array([flow_kg_s]), bore or self.bore[pipe], self.length[pipe], uo, float(reading["t_in_C"]),
                     float(reading["t_amb_C"]), self.oil([self.line(pipe)]))[0][0]


def coefficients_on_file(site):
    return {(row["pipe"], row["date"]): uo for row, uo in zip(site.surveys, site.coefficients(site.surveys))}


def pipes_to_survey(site, on_file):
    """(covering worked on since the last campaign, {narrower pipe: its mate}, coefficient moving unexplained)"""
    last, before = site.campaigns[-1], site.campaigns[-2]
    covering = {}
    for job in site.jobs:
        if "covering" in job["job"]:
            covering.setdefault(job["pipe"], []).append(job["date"])
    worked_on = sorted(pipe for pipe, dates in covering.items() if max(dates) > last)
    narrower = {}
    for name, row in site.lines.items():
        if row["pipes"] != "2":
            continue
        a, b = name + "-A", name + "-B"
        apart = []
        for date in site.campaigns:
            drop = [site.drop_at(p, float(site.reading[(p, date)]["flow_t_h"]) / 3.6, site.reading[(p, date)], on_file[(p, date)]) for p in (a, b)]
            apart.append(np.log(drop[0] / drop[1]))
        if min(apart) > DROPS_APART:                        # B carries its flow on too little drop for its bore
            narrower[b] = a
        elif max(apart) < -DROPS_APART:
            narrower[a] = b
    moving = []
    for pipe in site.pipes:
        between = [date for date in covering.get(pipe, []) if date > before]
        if not between and pipe not in worked_on and abs(np.log(on_file[(pipe, last)] / on_file[(pipe, before)])) > COEFFICIENT_MOVED:
            moving.append(pipe)
    return worked_on, narrower, moving


def survey(site, pipes):
    """The crew's readings of the pipes named, {pipe: row}; nothing if the order is not taken."""
    if not pipes:
        return {}
    try:
        said = subprocess.run(["heatsurvey", site.package] + pipes, capture_output=True, text=True)
    except OSError:
        return {}
    if said.returncode != 0:
        return {}
    return {row["pipe"]: row for row in csv.DictReader(said.stdout.splitlines())}


def as_they_stand(site, on_file, narrower, fresh):
    """(bore, outside coefficient) of every pipe as it stands after the last record."""
    last = site.campaigns[-1]
    uo = {pipe: on_file[(pipe, last)] for pipe in site.pipes}
    bore = dict(site.bore)
    plain = [pipe for pipe in fresh if pipe not in narrower]
    if plain:
        for pipe, value in zip(plain, site.coefficients([fresh[pipe] for pipe in plain])):
            uo[pipe] = value
    for pipe, mate in narrower.items():
        reading = fresh.get(pipe) or site.reading[(pipe, last)]
        oil = site.oil([site.line(pipe)])
        if pipe in fresh:
            mate_flow = (float(reading["line_flow_t_h"]) - float(reading["flow_t_h"])) / 3.6
        else:
            mate_flow = float(site.reading[(mate, last)]["flow_t_h"]) / 3.6
        target = site.drop_at(mate, mate_flow, reading, uo[mate])
        flow = np.array([float(reading["flow_t_h"]) / 3.6])
        t_in, t_out, t_amb = (float(reading[key]) for key in ("t_in_C", "t_out_C", "t_amb_C"))
        lo, hi = 0.6 * site.bore[pipe], site.bore[pipe]
        for _ in range(3):                                  # three passes over 24 bores at once
            trial = np.linspace(lo, hi, 24)
            many = {key: np.repeat(value, 24) for key, value in oil.items()}
            with_bore = coefficient(np.repeat(flow, 24), trial, site.length[pipe], t_in, t_out, t_amb, many)
            drop = march(np.repeat(flow, 24), trial, site.length[pipe], with_bore, t_in, t_amb, many)[0]
            k = int(np.argmax(drop < target))               # the first bore wide enough
            lo, hi = trial[max(k - 1, 0)], trial[k]
        part = (drop[max(k - 1, 0)] - target) / (drop[max(k - 1, 0)] - drop[k]) if k > 0 else 0.0
        bore[pipe] = lo + part * (hi - lo)
        uo[pipe] = site.coefficients([reading], {pipe: bore[pipe]})[0]
    return bore, uo


def calculate(site, bore, uo):
    """(pressure drop in Pa, outlet temperature in C) of every record, in the order of records.csv."""
    rec = site.records
    n = len(rec)
    drop, out = np.zeros(n), np.zeros(n)
    column = lambda key: np.array([float(row[key]) for row in rec])
    delivered, t_in, t_amb = column("flow_t_h") / 3.6, column("t_in_C"), column("t_amb_C")
    paired = np.array([site.lines[row["line"]]["pipes"] == "2" for row in rec])
    oil = site.oil([row["line"] for row in rec])
    length = np.array([float(site.lines[row["line"]]["length_m"]) for row in rec])
    bore_a = np.array([bore[row["line"] + "-A"] for row in rec])
    uo_a = np.array([uo[row["line"] + "-A"] for row in rec])
    single = ~paired
    if single.any():
        drop[single], out[single] = march(delivered[single], bore_a[single], length[single], uo_a[single], t_in[single], t_amb[single],
                                          {key: value[single] for key, value in oil.items()})
    where = np.nonzero(paired)[0]
    if len(where):
        case = {key: value[where] for key, value in oil.items()}
        case.update(bore_a=bore_a[where], uo_a=uo_a[where], bore_b=np.array([bore[rec[i]["line"] + "-B"] for i in where]),
                    uo_b=np.array([uo[rec[i]["line"] + "-B"] for i in where]), length=length[where], t_in=t_in[where], t_amb=t_amb[where])
        row, share, d, t = divisions(delivered[where], case)
        of_case = {}
        for i in range(len(row)):
            of_case.setdefault(int(row[i]), []).append(i)
        runs = {}
        for q, i in enumerate(where):
            runs.setdefault(rec[i]["line"], []).append((float(rec[i]["hour"]), q))
        for hours in runs.values():
            held = None
            for _, q in sorted(hours):
                found = of_case.get(q, [])
                if not found:
                    continue
                if held is None:                            # 4.3: the run opens where there is one division
                    k = found[int(np.argmin(np.abs(share[found] - 0.5)))] if len(found) > 1 else found[0]
                else:
                    # 4.2: the drops of A and B at the held division differ in sign alternately between
                    # successive divisions, A's being the lower below the first. Oil leaves the pipe with
                    # the higher drop, so the pair goes down to the next division when an odd number lie
                    # below the held one and up to the next otherwise.
                    below = int(np.sum(share[found] < held))
                    k = found[below - 1] if below % 2 == 1 else found[min(below, len(found) - 1)]
                drop[where[q]], out[where[q]] = d[k], t[k]
                held = share[k]
    return drop, out


def main(package, out_csv):
    site = Site(package)
    on_file = coefficients_on_file(site)
    worked_on, narrower, moving = pipes_to_survey(site, on_file)
    order = list(dict.fromkeys(worked_on + sorted(narrower) + sorted(moving)))[:site.allowance]
    fresh = survey(site, order)
    bore, uo = as_they_stand(site, on_file, narrower, fresh)
    drop, out = calculate(site, bore, uo)
    with open(out_csv, "w", newline="") as handle:
        sheet = csv.writer(handle)
        sheet.writerow(["record", "dp_kPa", "t_out_C"])
        for row, d, t in zip(site.records, drop, out):
            sheet.writerow([row["record"], "%.6g" % (d / 1e3), "%.4f" % t])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
