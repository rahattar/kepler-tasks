"""Reference assessment of the glycol cooler bank: as-found fouling resistance of E1-E10 on 2026-10-26 from the
records and three clean-and-test slots.

    python3 solve.py DATA_DIR HXTEST_URL OUT_CSV

Uses only the shipped records (/app/data) and the clean-and-test service. Never reads the service's code, the
sealed definition or the verifier.

1. Transmitter bias: in standby (cooling water shut, glycol circulating) the glycol leaves at its inlet
   temperature, so the median of outlet minus inlet over the standby hours is the outlet RTD's bias.
2. Clean performance: each unit's March 2025 acceptance test (just after hydroblasting) gives its clean U at the
   test flows; one common factor on the design-sheet split of film coefficients reproduces it, and the design-sheet
   exponents (0.8 on tube velocity, 0.6 on glycol crossflow velocity) carry it to any flows. E5's replacement
   bundle has the same geometry and baffle cut with the baffle spacing widened from 300 to 400 mm, so the glycol
   crossflow velocity at a given flow falls to 0.75 and its shell film to 0.75^0.6 of the 2025 one.
3. Fouling in the trend: for every running hour, U from the glycol-side duty (bias removed) over the counterflow
   LMTD (the water outlet from the same duty: the units share one return header), then R_f = 1/U - 1/U_clean at
   that hour's flows; a least-squares line in time, with a step at the shock chlorination in the maintenance log
   (biofilm stripped; the dose day left out), carries it to the test day.
4. What the records cannot settle gets a slot: the new unit (E10: only the vendor's datasheet, rated, not
   measured), a unit whose 2025 test sheet does not close its heat balance (E9: water-side duty 5 percent below the
   glycol side, where every other sheet closes within about 1 percent; which reading is wrong cannot be told from
   the sheet), and a ribbed unit that never stands by (E8: neither its bias nor its clean coefficient is known). A
   tested unit's as-found R_f is 1/U_as_found - 1/U_clean from the reference instruments.
5. Plugged tubes (E2): tube-side dp at a given water flow rises as (1/open fraction)^1.8, so the dp ratio to the
   unit's 2025 test gives the open fraction, the actual area and the tube velocity.
6. Ribbed tubes: dp ratio to the unit's 2025 test is the friction-factor gain. The tested ribbed unit's clean test
   gives its tube-film gain (clean U minus the shell film and wall, over its 2025 tube film); the ratio of
   (film gain - 1) to (friction gain - 1) carries to the other ribbed units through their own friction gain.
"""
import csv, json, os, re, sys, time, urllib.request
import numpy as np
import pandas as pd

DATA, URL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
RHO_G, CP_G = 1050.0, 3.60
DESIGN = {"C-200": dict(A=90.0, ht=3000.0, hs=2500.0, rw=5e-5, ft=180.0, fs=60.0),
          "C-310": dict(A=110.0, ht=3570.0, hs=2900.0, rw=5e-5, ft=220.0, fs=75.0)}     # C-310: vendor datasheet
T0 = pd.Timestamp("2026-09-14 00:00")
T_TEST = (pd.Timestamp("2026-10-26 08:00") - T0).total_seconds() / 86400.0
BUDGET = 3


def lmtd(tci, tco, thi, tho):
    a, b = thi - tco, tho - tci
    return np.where(np.abs(a - b) < 1e-6, a, (a - b) / np.log(a / b))


def u_obs(fs, tci, tco, thi, tho, A):
    q = np.asarray(fs) / 3600 * RHO_G * CP_G * (np.asarray(thi) - np.asarray(tho))
    return q * 1000.0 / (A * lmtd(tci, tco, thi, tho))


def films(model, ft, fs, s=(1.0, 1.0), open_=1.0, eh=1.0):
    d = DESIGN[model]
    return (d["ht"] * s[0] * eh * (np.asarray(ft) / open_ / d["ft"]) ** 0.8, d["hs"] * s[1] * (np.asarray(fs) / d["fs"]) ** 0.6,
            d["rw"])


def http(method, path):
    req = urllib.request.Request(URL + path, method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    reg = pd.read_csv(os.path.join(DATA, "unit_register.csv")).set_index("unit")
    acc = pd.read_csv(os.path.join(DATA, "acceptance_tests_2025.csv")).set_index("unit")
    log = pd.read_csv(os.path.join(DATA, "maintenance_log.csv"))
    tr = {}
    for u in reg.index:
        t = pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % u.lower()))
        t["day"] = (pd.to_datetime(t.timestamp) - T0).dt.total_seconds() / 86400.0
        tr[u] = t
    units = list(reg.index)
    ribbed = [u for u in units if str(reg.loc[u, "tubes"]).startswith("ribbed")]

    # E5's replacement bundle: same geometry and baffle cut, wider baffle spacing (bundle shop note); the shell-side
    # crossflow velocity scales as 1/spacing, and the shell film with velocity^0.6
    note = open(os.path.join(DATA, "docs", "bundle_e5_2026.md")).read()
    sp_old, sp_new = [float(x) for x in re.search(r"from (\d+) mm to (\d+) mm", note).groups()]
    hs_factor = {"E5": (sp_old / sp_new) ** 0.6}

    def scale(u):
        """(tube, shell) factors on the design split from the unit's 2025 clean test."""
        m = reg.loc[u, "model"]
        r = acc.loc[u]
        U = float(u_obs(r.glycol_flow_m3h, r.cw_in_c, r.cw_out_c, r.glycol_in_c, r.glycol_out_c, DESIGN[m]["A"]))
        ht, hs, rw = films(m, r.cw_flow_m3h, r.glycol_flow_m3h)
        f = (1 / ht + 1 / hs) / (1 / U - rw)
        return f, f * hs_factor.get(u, 1.0)

    def gap(u):
        """Heat-balance gap of a 2025 test sheet: water-side over glycol-side duty, minus one."""
        r = acc.loc[u]
        qw = r.cw_flow_m3h * 995.0 * 4.18 * (r.cw_out_c - r.cw_in_c)
        qg = r.glycol_flow_m3h * RHO_G * CP_G * (r.glycol_in_c - r.glycol_out_c)
        return qw / qg - 1

    def dp_ratio(u):
        r = tr[u][tr[u].state == "run"]
        return float(np.median(r.dp_tube_kpa / r.cw_flow_m3h ** 1.8) / (acc.loc[u].dp_tube_kpa / acc.loc[u].cw_flow_m3h ** 1.8))

    def bias(u):
        sb = tr[u][tr[u].state == "standby"]
        return float(np.median(sb.glycol_out_c - sb.glycol_in_c)) if len(sb) >= 3 else None

    # shock chlorination of the cooling water strips biofilm: a step in the fouling trend on that day
    shocks = [(pd.Timestamp(r.date) - T0).total_seconds() / 86400.0 for _, r in log.iterrows()
              if "shock chlorination" in str(r.work_done).lower() and pd.Timestamp(r.date) > T0]

    # what the records cannot settle
    plan = [u for u in units if u not in acc.index]                       # no site clean test (vendor datasheet only)
    plan += [u for u in acc.index if abs(gap(u)) > 0.02 and u not in plan]  # 2025 sheet whose heat balance does not close
    plan += [u for u in ribbed if bias(u) is None and u not in plan]      # ribbed, never stands by
    if not any(u in ribbed for u in plan):
        plan.append(ribbed[0])
    assert len(plan) == BUDGET, plan

    os.system("start-hxtest >/dev/null 2>&1")
    for _ in range(50):
        try:
            http("GET", "/status")
            break
        except Exception:
            time.sleep(0.2)
    tests = {u: http("POST", "/test?unit=%s" % u) for u in plan}

    def test_u(u, lab):
        r = tests[u][lab]["reference_instruments"]
        return float(u_obs(r["glycol_flow_m3h"], r["cw_in_c"], r["cw_out_c"], r["glycol_in_c"], r["glycol_out_c"],
                           DESIGN[reg.loc[u, "model"]]["A"])), r["cw_flow_m3h"], r["glycol_flow_m3h"]

    est = {}
    gains = []
    for u in plan:
        ua, _, _ = test_u(u, "as_found")
        uc, ft, fs = test_u(u, "after_cleaning")
        est[u] = 1000 * (1 / ua - 1 / uc)
        if u in ribbed:
            ht_old, hs, rw = films(reg.loc[u, "model"], ft, fs, scale(u))
            ht_now = 1 / (1 / uc - 1 / hs - rw)
            gains.append((ht_now / ht_old - 1) / (dp_ratio(u) - 1))
    k_rib = float(np.mean(gains))
    for u in units:
        if u in est:
            continue
        m = reg.loc[u, "model"]
        open_ = 1.0
        if any(("plugged" in str(r.work_done).lower()) and u in str(r.units).split(",") for _, r in log.iterrows()):
            open_ = dp_ratio(u) ** (-1 / 1.8)
        eh = 1 + k_rib * (dp_ratio(u) - 1) if u in ribbed else 1.0
        b = bias(u)
        r = tr[u][tr[u].state == "run"]
        tho = r.glycol_out_c.values - b
        q = r.glycol_flow_m3h.values / 3600 * RHO_G * CP_G * (r.glycol_in_c.values - tho)
        tco = r.cw_in_c.values + q / (r.cw_flow_m3h.values / 3600 * 995.0 * 4.18)      # no water-outlet RTD
        U = u_obs(r.glycol_flow_m3h.values, r.cw_in_c.values, tco, r.glycol_in_c.values, tho, DESIGN[m]["A"] * open_)
        ht, hs, rw = films(m, r.cw_flow_m3h.values, r.glycol_flow_m3h.values, scale(u), open_, eh)
        rf = 1000 * (1 / U - (1 / ht + 1 / hs + rw))
        day = r.day.values
        keep = np.ones(len(day), bool)
        cols = [np.ones(len(day)), day]
        for s0 in shocks:                       # a step at each shock dose; the dose day itself is left out
            keep &= (day < s0) | (day >= s0 + 1)
            cols.append((day >= s0 + 1).astype(float))
        X = np.column_stack(cols)
        c = np.linalg.lstsq(X[keep], rf[keep], rcond=None)[0]
        est[u] = float(c[0] + c[1] * T_TEST + sum(c[2:]))
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["unit", "fouling_m2k_per_kw"])
        for u in units:
            w.writerow([u, round(est[u], 4)])
    print("tested:", plan, "| ribbed film/friction ratio %.3f" % k_rib)
    print({u: round(v, 3) for u, v in est.items()})


if __name__ == "__main__":
    main()
