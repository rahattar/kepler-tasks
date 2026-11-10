"""A second solution, written separately from solution/solve.py and sharing no code with it: pandas for the
records, its own reading of the register, and a different algorithm. Instead of scanning the range and asking where
every requirement holds from, it finds for each requirement the highest pressure in the range at which that
requirement fails, and takes the answer as the highest of those plus one step of the standard's resolution. The
reversal is counted on a quarter-degree sweep and converted to degrees.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt

It uses the laboratory of common.py, which is the environment, not the method.
"""
import os
import re

import numpy as np
import pandas as pd

import common as C

S = C.S
DATA = C.DATA
DPS, DPD, TDMAX, DT_BOTTLE, REV, RES, TDTOL = 0.35, 0.70, 135.0, 6.0, 15.0, 0.01, 0.001
NAMES = ("gas_load", "rod_load_compression", "rod_load_tension", "discharge_temperature",
         "cylinder_power", "pin_reversal")


def md(name):
    return open(os.path.join(DATA, "docs", name)).read()


def build():
    """every record this solution needs, read its own way"""
    sch = pd.read_csv(os.path.join(DATA, "cylinder_schedule.csv")).set_index("cylinder")
    lin = pd.read_csv(os.path.join(DATA, "liner_records.csv")).sort_values("date")
    opr = pd.read_csv(os.path.join(DATA, "operating_record.csv")).set_index("stage")
    ins = pd.read_csv(os.path.join(DATA, "instrument_schedule.csv")).set_index("tag")
    drv = pd.read_csv(os.path.join(DATA, "drive_record.csv")).sort_values("date")
    prp = pd.read_csv(os.path.join(DATA, "component_properties.csv")).set_index("component")
    tcols = [c for c in prp.columns if c.startswith("cp_over_R_at_")]
    tvals = [float(c.replace("cp_over_R_at_", "").rstrip("C")) for c in tcols]
    feed = pd.read_csv(os.path.join(DATA, "gas_analysis_feed.csv")).set_index("component")
    sheet, reg, bul = md("machine_data_sheet.md"), md("overhaul_register.md"), md("service_bulletin.md")
    g = dict(
        sch=sch, lin=lin, opr=opr, ins=ins, prp=prp, tcols=tcols, tvals=tvals,
        cp_rows={c: [float(prp.loc[c, col]) for col in tcols] for c in prp.index},
        bore=dict(zip(lin["cylinder"], lin["mean_bore_mm"])),
        feed=feed["mol_per_cent"].to_dict(),
        stroke=float(re.findall(r"stroke \| ([\d.]+) mm", sheet)[0]),
        ell=float(re.findall(r"crank radius \| ([\d.]+)", sheet)[0]),
        rpm=float(drv["speed_held_rev_min"].iloc[-1]),
        rated=float(re.findall(r"to ([\d.]+) kN, in compression", bul)[0]),
        derate=float(re.findall(r"limited to ([\d.]+) kN", reg)[0]),
        spare=int(re.findall(r"throw (\d+) running assembly", reg)[0]),
        piston=int(re.findall(r"throw (\d+) liner and piston", reg)[0]),
        dpiston=(lambda t: float(t[0]) - float(t[1]))(
            re.findall(r"piston as fitted ([\d.]+) kg, piston removed ([\d.]+) kg", reg)[0]),
        pockets=[int(x) for x in re.findall(r"pockets, throws (\d+) and (\d+)", reg)[0]],
    )
    return g


def kappa(mol, g, t):
    """the exponent of a mixture at a temperature, interpolated in the property table by hand"""
    ts = g["tvals"]
    i = min(max(sum(1 for x in ts if x <= t) - 1, 0), len(ts) - 2)
    f = (t - ts[i]) / (ts[i + 1] - ts[i])
    cp = 0.0
    for comp, v in mol.items():
        row = g["cp_rows"][comp]
        cp += v * (row[i] + f * (row[i + 1] - row[i]))
    cp /= 100.0
    return cp / (cp - 1.0)


def td_and_k(g, j, p):
    """the discharge temperature and the exponent together, by repeated substitution"""
    rr = (j["pd"] + DPD) / (p - DPS)
    td = j["ts"]
    while True:
        k = kappa(g["gas"][j["stage"]], g, 0.5 * (j["ts"] + td))
        nxt = (j["ts"] + 273.15) * rr ** (1.0 - 1.0 / k) - 273.15
        if abs(nxt - td) < TDTOL:
            return nxt, k
        td = nxt


def cylinder(g, cid, gas, weights):
    r = g["sch"].loc[cid]
    st = int(r["stage"])
    throw = int(r["throw"])
    tag = g["opr"].loc[st, "temperature_element"]
    ts = float(g["opr"].loc[st, "suction_temperature_C"])
    if "bottle" in str(g["ins"].loc[tag, "mounting"]):
        ts += DT_BOTTLE
    a1 = np.pi * (float(g["bore"][cid]) / 1000.0) ** 2 / 4.0
    a2 = a1 - np.pi * (float(r["piston_rod_mm"]) / 1000.0) ** 2 / 4.0
    c_he = float(r["clearance_head_end_sheet"])
    if throw in g["pockets"]:
        c_he += float(r["clearance_pocket_cm3"]) / (a1 * (g["stroke"] / 1000.0) * 1e6)
    c_ce = float(r["clearance_crank_end_sheet"])
    w = weights.get(cid)
    if w is None:
        w = float(r["reciprocating_weight_kg_sheet"]) + (g["dpiston"] if throw == g["piston"] else 0.0)
    return dict(
        stage=st, throw=throw, ts=ts, c_he=c_he, c_ce=c_ce, mass=w,
        bore=float(g["bore"][cid]) / 1000.0,
        rodd=float(r["piston_rod_mm"]) / 1000.0,
        pd=float(g["opr"].loc[st, "discharge_pressure_bar_a"]),
        kw=float(r["rated_power_kW"]), glim=float(r["allowable_gas_load_kN"]),
        limit=min(g["rated"], g["derate"]) if throw == g["spare"] else g["rated"],
    )


_ANG = {}


def fails(g, j, p):
    """which requirements fail at that one pressure, by this solution's own arithmetic"""
    a1 = np.pi * j["bore"] ** 2 / 4.0
    a2 = a1 - np.pi * j["rodd"] ** 2 / 4.0
    n = 1440
    if n not in _ANG:
        a = np.arange(n) * 360.0 / n
        _ANG[n] = (a, a < 180.0, np.cos(np.radians(a)), np.cos(2.0 * np.radians(a)))
    ang, first, c1, c2 = _ANG[n]
    pg = np.where(first, j["pd"], p) * a1 - np.where(first, p, j["pd"]) * a2
    pg = pg * 100.0                                                        # bar m2 -> kN
    om = g["rpm"] * np.pi / 30.0
    acc = -j["mass"] * om ** 2 * (g["stroke"] / 2000.0) * (c1 + c2 / g["ell"]) / 1000.0
    tot = pg + acc
    rr = (j["pd"] + DPD) / (p - DPS)
    td, kk = td_and_k(g, j, p)
    expo = 1.0 - 1.0 / kk
    gg = rr ** (1.0 / kk) - 1.0
    disp = (a1 * (1.0 - j["c_he"] * gg) + a2 * (1.0 - j["c_ce"] * gg)) * (g["stroke"] / 1000.0) * (
        g["rpm"] / 60.0)
    pw = (p - DPS) * 1e2 * disp * (rr ** expo - 1.0) / expo                # bar m3/s -> kW
    rev = float((tot < 0.0).sum()) * 360.0 / n
    out = set()
    if np.abs(pg).max() > j["glim"]:
        out.add("gas_load")
    if tot.max() > j["limit"]:
        out.add("rod_load_compression")
    if -tot.min() > j["limit"]:
        out.add("rod_load_tension")
    if td > TDMAX:
        out.add("discharge_temperature")
    if pw > j["kw"]:
        out.add("cylinder_power")
    if rev < REV:
        out.add("pin_reversal")
    return out


def scan(g, j):
    """the set of failing requirements at every 0.05 bar of the range, coarsest first"""
    top, bot = round(j["pd"] - 0.20, 2), round(j["pd"] * 0.10, 2)
    out = {}
    for p in np.round(np.arange(bot, top + 0.025, 0.05), 2):
        out[float(p)] = fails(g, j, float(p))
    return out, top


def highest_failure(g, j, req, coarse, top):
    """the highest pressure in the range at which that requirement fails, or None"""
    bad = [p for p, f in coarse.items() if req in f]
    if not bad:
        return None
    hi = max(bad)
    fine = np.round(np.arange(hi - 0.05, min(hi + 0.10, top) + RES / 2.0, RES), 2)
    got = [p for p in fine if req in fails(g, j, float(p))]
    return max(got) if got else hi


def answer(g, j):
    coarse, top = scan(g, j)
    worst, who = None, None
    for req in NAMES:
        p = highest_failure(g, j, req, coarse, top)
        if p is not None and (worst is None or p > worst):
            worst, who = p, req
    if worst is None:
        return round(j["pd"] * 0.10, 2), None
    return round(worst + RES, 2), who


def solve(seed=C.SEED):
    g = build()
    lab = C.Lab(seed)
    gas = {1: g["feed"]}
    gas[2] = lab.gc(2)                       # the second stage's sample stream
    gas[3] = gas[2]                          # its separator is bypassed, so the third stage takes the same gas
    g["gas"] = gas
    g2 = g
    weights = {}
    for cid in g["sch"].index:
        if int(g["sch"].loc[cid, "throw"]) == g["spare"]:
            weights[cid] = lab.weigh(cid)
    out = {}
    for cid in g["sch"].index:
        j = cylinder(g2, cid, gas, weights)
        out[cid] = answer(g2, j)
    return out, lab.log


def main():
    sheet, log = solve()
    n, err, (wc, wv) = C.grade(sheet)
    truth = S.truth()
    print("A second solution, written separately. Readings: %s\n" % ", ".join(log))
    print("| cylinder | this solution | the definition | apart | requirement |")
    print("|---|---|---|---|---|")
    for cid in C.IDS:
        print("| %s | %.2f bar | %.2f bar | %+.3f %% | %s%s |" % (
            cid, sheet[cid][0], truth[cid][0], 100.0 * err[(cid, "pressure")], sheet[cid][1],
            "" if sheet[cid][1] == truth[cid][1] else " (DIFFERS: %s)" % truth[cid][1]))
    print()
    print("%d of %d right on the shipped seed, the worst value %.3f per cent from the definition against a\n"
          "tolerance of %.1f per cent." % (n, len(C.ITEMS), 100.0 * abs(wv), 100.0 * S.TOL))
    bad = 0
    worst = abs(wv)
    for s in C.SEEDS:
        sh, _ = solve(s)
        m, e, (_, v) = C.grade(sh)
        worst = max(worst, abs(v))
        bad += m < len(C.ITEMS)
    print("On the twenty laboratory seeds %d to %d it gets all twelve %s, the worst value over all of them %.3f\n"
          "per cent from the definition." % (C.SEEDS[0], C.SEEDS[-1],
                                             "every time" if not bad else "on %d of 20" % (len(C.SEEDS) - bad),
                                             100.0 * worst))
    return bad or n < len(C.ITEMS)


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
