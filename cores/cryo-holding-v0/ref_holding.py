"""Reference: python3 holding.py PACKAGE_DIR OUT_CSV. MODE env (ladder): full | noorder | legible | nogauge | noinsul | keepf"""
import csv, json, math, os, subprocess, sys
import numpy as np
MODE = os.environ.get("MODE", "full")
TABLE = """__TABLE__"""
rows = [[float(x) for x in l.split(",")] for l in TABLE.strip().splitlines()[1:]]
T, P, RL, RV, HL, HV = np.array(rows).T
ATM = 1.01325; T_NBP = 77.355
def sat(t): return (np.interp(t, T, P), np.interp(t, T, RL), np.interp(t, T, RV), np.interp(t, T, HL), np.interp(t, T, HV))
def t_of_p(p): return float(np.interp(p, P, T))
def vent_per_J(t):
    p, rl, rv, hl, hv = sat(t); return (1 - rv / rl) / ((hv - hl) * 1e3)
def ua_from_ner(ner, cap, tt):
    rl = sat(T_NBP)[1]; return ner / 100 * cap * rl / 86400.0 / vent_per_J(T_NBP) / (tt + 273.15 - T_NBP)
def u_mix(t, v):
    p, rl, rv, hl, hv = sat(t); vl, vv = 1 / rl, 1 / rv
    x = (v - vl) / (vv - vl); ul, uv = hl - p * 100 * vl, hv - p * 100 * vv
    return ul + x * (uv - ul), x
def state(v, u):
    lo, hi = 77.0, 115.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if u_mix(mid, v)[0] < u: lo = mid
        else: hi = mid
    t = 0.5 * (lo + hi); return t, u_mix(t, v)[1]
def t_full(m, cap):
    """the temperature at which the liquid alone would fill the tank, or None above the table"""
    rho = m / cap
    if rho > RL[0] or rho < RL[-1]: return None
    return float(np.interp(-rho, -RL, T))
def hold(cap, m0, p0, relief, ua, tamb, days):
    t = t_of_p(p0 + ATM); v = cap / m0; u = u_mix(t, v)[0]; m = m0
    tset = t_of_p(relief + ATM); vented = 0.0; st = "closed"; out = []
    for d in range(1, days + 1):
        if st == "full": out.append((d,) + out[-1][1:]); continue
        q = ua * (tamb[d - 1] + 273.15 - t) * 86400.0
        if st == "closed":
            un = u + q / (m * 1e3); tf = t_full(m, cap)
            if tf is not None and tf < tset and un >= u_mix(tf, v)[0]:
                t = tf; st = "full"
            elif un <= u_mix(tset, v)[0]:
                t, x = state(v, un); u = un
            else:
                qr = (un - u_mix(tset, v)[0]) * m * 1e3; t = tset; st = "venting"
                dm = qr * vent_per_J(tset); vented += dm; m -= dm; v = cap / m; u = u_mix(t, v)[0]
        else:
            dm = q * vent_per_J(tset); vented += dm; m -= dm; v = cap / m; u = u_mix(t, v)[0]
        out.append((d, float(sat(t)[0]) - ATM, vented, st))
    return out


def rd(pkg, f): return list(csv.DictReader(open(os.path.join(pkg, f))))
def main(pkg, out):
    site = json.load(open(os.path.join(pkg, "site.json")))
    tanks = {r["tank"]: r for r in rd(pkg, "tanks.csv")}; names = list(tanks)
    for k, r in tanks.items(): r["ua_reg"] = ua_from_ner(float(r["ner_pct_day"]), float(r["capacity_m3"]), float(r["ner_t_amb_C"]))
    depot = rd(pkg, "depot_log.csv"); tl = rd(pkg, "tank_log.csv"); work = rd(pkg, "work_log.csv")
    last = depot[-1]["date"]
    legible = sorted({w["tank"] for w in work if w["date"] > last and ("vacu" in w["job"] or "perlite" in w["job"] or "evacuat" in w["job"])})
    ins = {(r["date"], r["tank"]): int(r["in_service"]) for r in tl}
    # unit boil-off of each tank each day, with its rated UA
    X = []; y = []
    for d in depot:
        ts = t_of_p(float(d["header_barg"]) + ATM); per = (float(d["t_amb_C"]) + 273.15 - ts) * 86400 * vent_per_J(ts)
        X.append([ins[(d["date"], n)] * tanks[n]["ua_reg"] * per for n in names]); y.append(float(d["meter_kg"]))
    X = np.array(X); y = np.array(y)
    f_all = y.sum() / X.sum()
    mult = {n: f_all for n in names}
    if MODE not in ("noinsul", "legible", "noorder", "nogauge_noinsul"):
        tog = [i for i, n in enumerate(names) if X[:, i].min() == 0]
        A = np.column_stack([X.sum(axis=1)] + [X[:, i] for i in tog])
        c, *_ = np.linalg.lstsq(A, y, rcond=None)
        sus = [names[i] for j, i in enumerate(tog) if c[j + 1] > 0.25 * c[0]]
        if MODE != "keepf":
            cols = [names.index(s) for s in sus]
            A2 = np.column_stack([X.sum(axis=1)] + [X[:, i] for i in cols]); c2, *_ = np.linalg.lstsq(A2, y, rcond=None)
            mult = {n: c2[0] for n in names}
            for j, i in enumerate(cols): mult[names[i]] = c2[0] + c2[j + 1]
    else:
        sus = []
    ua = {n: mult[n] * tanks[n]["ua_reg"] for n in names}
    order = [] if MODE == "noorder" else legible + [s for s in sus if s not in legible]
    order = order[:int(site["test_allowance"])]
    if order:
        p = subprocess.run(["nertest", pkg] + order, capture_output=True, text=True)
        lines = p.stdout.strip().splitlines()
        if p.returncode == 0 and lines and lines[0].startswith("tank"):
            for l in lines[1:]:
                tk, ner, tt = l.split(","); ua[tk] = ua_from_ner(float(ner), float(tanks[tk]["capacity_m3"]), float(tt))
    # gauge check: rise on fill days against the ticket
    kfac = {n: 1.0 for n in names}
    if MODE not in ("nogauge", "legible", "noorder", "nogauge_noinsul"):
        by = {}
        for r in tl: by.setdefault(r["tank"], []).append(r)
        for n, rs in by.items():
            dg = []; fills = []
            for a, b in zip(rs, rs[1:]):
                if a["in_service"] == "1" and b["in_service"] == "1" and a["gauge_kg"] and b["gauge_kg"]:
                    g = float(b["gauge_kg"]) - float(a["gauge_kg"]); fk = float(a["filled_kg"])
                    (fills if fk > 0 else dg).append((g, fk))
            if fills and dg:
                base = np.median([g for g, _ in dg])
                ks = [(g - base) / fk for g, fk in fills]
                k = float(np.median(ks))
                if abs(k - 1) > 0.04: kfac[n] = k
    hamb = [float(r["t_amb_C"]) for r in rd(pkg, "holding.csv")]
    with open(out, "w", newline="") as fo:
        w = csv.writer(fo); w.writerow(["record", "tank", "day", "p_barg", "vented_kg", "state"])
        for r in rd(pkg, "plan.csv"):
            n = r["tank"]; m0 = float(r["close_gauge_kg"]) / kfac[n]
            for d, p, v, st in hold(float(tanks[n]["capacity_m3"]), m0, float(site["close_barg"]), float(tanks[n]["relief_barg"]), ua[n], hamb, int(site["holding_days"])):
                w.writerow(["%s/%d" % (n, d), n, d, "%.3f" % p, "%.1f" % v, st])
    sys.stderr.write("f_all %.4f order %s sus %s k %s\n" % (f_all, order, sus, {n: round(k, 3) for n, k in kfac.items() if k != 1.0}))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
