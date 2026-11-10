"""Writes the agent-visible records of the cooling-water pump bank from the sealed definition (pumps.py): the pump
register, the maintenance log, the factory test certificates, the supplier's typical curve for P10's impeller, and
four weeks of hourly DCS trends (one file per pump and one for the header). Documents are written by hand.

    python3 gen.py OUT_DIR
"""
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pumps as P

SEED = 7
NZ = 1.0                     # measurement-noise scale
HOURS = 28 * 24
T0 = pd.Timestamp("2026-09-21 08:00")
KB = 1.2                     # branch loss (check valve, discharge valve) at 900 m3/h, m
A_S, A_D = np.pi * P.D_NOZ_S ** 2 / 4, np.pi * P.D_NOZ_D ** 2 / 4


def vel_head(Q):
    vs, vd = Q / 3600 / A_S, Q / 3600 / A_D
    return (vd ** 2 - vs ** 2) / (2 * P.G)


def eff(q):
    return 0.84 - 0.50 * (q - 1.0) ** 2


def roster(rng):
    """Weekly standby lists and a daily priority order: who may run, in what order of starting."""
    weeks = []
    singles = ["P1", "P2", "P3", "P4", "P5", "P6", "P9", "P10"]
    for w in range(4):
        out = [singles[(2 * w + 1) % len(singles)]]
        pair_on = w % 2 == 0 or w == 3
        weeks.append((out, pair_on))
    return weeks


def operate(bank, rng):
    weeks = roster(rng)
    rows, hdr, q7 = {u: [] for u in P.UNITS}, [], []
    for k in range(HOURS):
        t = k / 24.0
        w = min(int(t // 7), 3)
        out, pair_on = weeks[w]
        avail = [u for u in P.UNITS if u not in out and (u not in ("P7", "P8") or pair_on)]
        kd = int(round(P.DRY_DAY * 24))
        if kd <= k < kd + 3:                                    # P1 tripped (starved suction), restarted 05:00
            avail.remove(P.DRY_PUMP)
        # demand: daily cycle and weather; number of pumps from demand
        dem = 5600 + 1300 * np.sin(2 * np.pi * (t - 0.3)) + 600 * np.sin(2 * np.pi * t / 5.3) + rng.normal(0, 60)
        n = int(np.clip(round(dem / 900.0), 4, len(avail)))
        order = [u for u in avail if u != "P8"]
        rng_d = np.random.default_rng(int(t) * 31 + 7)          # daily start order
        rng_d.shuffle(order)
        if k == kd - 1:                                         # P1 was on duty when its strainer blinded
            order.remove(P.DRY_PUMP)
            order.insert(0, P.DRY_PUMP)
        run = []
        for u in order:                                         # the pair (P7, P8) starts and stops as a block
            blk = ["P7", "P8"] if u == "P7" else [u]
            if len(run) + len(blk) <= n:
                run += blk
        s9 = float(np.clip(0.93 + 0.05 * np.sin(2 * np.pi * t / 3.7) + rng.normal(0, 0.005), 0.85, 1.0))
        hs0 = 33.0 + 3.0 * np.sin(2 * np.pi * t / 6.1) + rng.normal(0, 0.3)       # static lift, m
        ks = 9.0 / 5600.0 ** 2                                                      # m per (m3/h)^2
        basin = 38.0 + 6.0 * np.sin(2 * np.pi * (t - 0.1) / 0.517) + rng.normal(0, 0.3)   # suction gauge, kPa (tide)

        def flows(hreq):
            Q = {}
            for u in run:
                b = bank[u]
                s = s9 if u == "P9" else 1.0
                kk = P.k_at(b, t)
                h0, h1, h2 = b["new"]
                # s^2 k H_new(Q/s) = hreq + KB q^2 + velocity-free (pump total head between flanges)
                a, bb, c = kk * h2 + KB, kk * h1 * s, hreq - kk * h0 * s * s
                q = (-bb + np.sqrt(max(bb * bb - 4 * a * c, 0.0))) / (2 * a)
                Q[u] = max(q, 0.0) * P.QR
            return Q
        lo, hi = 20.0, 70.0
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            F = sum(flows(mid).values())
            if mid > hs0 + ks * F * F:
                hi = mid
            else:
                lo = mid
        hreq = 0.5 * (lo + hi)
        Q = flows(hreq)
        F = sum(Q.values())
        q7.append(Q.get("P7", 0.0))
        meter = F * (1 + (P.CAL_ERR if t < P.CAL_DAY else 0.0)) * (1 + NZ * rng.normal(0, 0.0015))
        hdr.append([(T0 + pd.Timedelta(hours=k)).strftime("%Y-%m-%d %H:%M"), round(meter, 0), len(run)])
        for u in P.UNITS:
            b = bank[u]
            ts = (T0 + pd.Timedelta(hours=k)).strftime("%Y-%m-%d %H:%M")
            spd = round(1480 * (s9 if u == "P9" else 1.0), 1) if u in run else 0.0
            ps = basin - 0.6 * (Q.get(u, 0.0) / P.QR) ** 2
            if u in run:
                H = (s9 if u == "P9" else 1.0) ** 2 * P.k_at(b, t) * P.h_new(b, Q[u] / (s9 if u == "P9" else 1.0))
                # pump total head = (pd - ps)/rho g + dz + velocity head difference
                pd_ = ps + (H - P.DZ[u] - vel_head(Q[u])) * P.RHO * P.G / 1000.0
            else:
                pd_ = ps - P.DZ[u] * P.RHO * P.G / 1000.0          # stopped: gauge sees the basin, lower by its height
            pd_meas = pd_ + NZ * rng.normal(0, 0.6)
            if u == P.ZERO_PUMP and t < P.ZERO_DAY:              # PT-606 zero error until its loop check
                pd_meas += P.ZERO_KPA
            if u == "P2" and P.SPAN_FROM <= t < P.SPAN_TO:
                pd_meas = pd_meas * 1000.0 / 1600.0
            rows[u].append([ts, "run" if u in run else "stopped", spd, round(ps + NZ * rng.normal(0, 0.15), 1), round(pd_meas, 1)])
    return rows, hdr, q7


def certificates(bank, rng):
    out = []
    for u in P.UNITS:
        if u in ("P10", "P6"):
            continue
        b = bank[u]
        h0, h1, h2 = b["cert"]
        true_new = (h0, h1, h2)                       # the curve the certificate test measured (as listed)
        for Q in (0.0, 450.0, 675.0, 900.0, 1035.0):
            q = Q / P.QR
            Hc = h0 - h1 * q - h2 * q * q                     # listed head (certificate)
            Ht = true_new[0] - true_new[1] * q - true_new[2] * q * q   # what the pump really delivered
            e = eff(q) if Q > 0 else 0.0
            pw = (P.RHO * P.G * Q / 3600 * Ht / max(e, 1e-9) / 1000.0) if Q > 0 else 95.0
            out.append(dict(pump=u, serial="CW250-%04d" % (2140 + P.UNITS.index(u)), test_date="2014-0%d-%02d" % (3 + P.UNITS.index(u) % 3, 10 + P.UNITS.index(u)),
                            impeller_mm=330, speed_rpm=1450 if u == "P3" else 1480, flow_m3h=Q, head_m=round(Hc + rng.normal(0, 0.03), 2),
                            efficiency_pct=round(100 * e + (rng.normal(0, 0.2) if Q > 0 else 0), 1),
                            shaft_power_kw=round(pw * (1 + rng.normal(0, 0.003)), 1)))
    return pd.DataFrame(out)


def main(out):
    rng = np.random.default_rng(SEED + 1000)
    bank = P.make_bank(SEED)
    os.makedirs(os.path.join(out, "trends"), exist_ok=True)
    reg = pd.DataFrame([dict(pump=u, serial="CW250-%04d" % (2140 + P.UNITS.index(u)),
                             model="CW-250" if u != "P10" else "CW-250 (impeller replaced 2026)",
                             impeller_mm=315 if u == "P4" else 330, drive="VFD" if u == "P9" else "fixed 1480 rpm",
                             in_service_since="2014") for u in P.UNITS])
    reg.to_csv(os.path.join(out, "pump_register.csv"), index=False)
    certificates(bank, rng).to_csv(os.path.join(out, "factory_tests.csv"), index=False)
    rows, hdr, q7 = operate(bank, rng)
    for u in P.UNITS:
        pd.DataFrame(rows[u], columns=["timestamp", "state", "speed_rpm", "suction_kpa", "discharge_kpa"]).to_csv(
            os.path.join(out, "trends", "%s.csv" % u.lower()), index=False)
    pd.DataFrame(hdr, columns=["timestamp", "header_flow_m3h", "pumps_running"]).to_csv(
        os.path.join(out, "trends", "header.csv"), index=False)
    # clamp-on survey of P7's discharge flow: three hours from 10:00 on the first day from 2026-10-08 that P7 runs
    k0 = next(k for k in range(17 * 24 + 2, HOURS - 3) if (k - 2) % 24 == 0 and all(q7[k + j] > 0 for j in range(3)))
    srng = np.random.default_rng(SEED + 3000)
    pd.DataFrame([dict(timestamp=(T0 + pd.Timedelta(hours=k0 + j)).strftime("%Y-%m-%d %H:%M"), pump="P7",
                       flow_m3h=round(q7[k0 + j] * P.SURVEY_SCALE * (1 + srng.normal(0, 0.004)), 1)) for j in range(3)]).to_csv(
        os.path.join(out, "flow_survey.csv"), index=False)
    # P10: rig test after fitting the new impeller (as new), shop motor at 1490 rpm
    r = P.P10_RIG_RPM / 1480.0
    b10 = bank["P10"]
    pd.DataFrame([dict(pump="P10", date="2026-02-27", speed_rpm=int(P.P10_RIG_RPM), flow_m3h=round(Qs * (1 + srng.normal(0, 0.001)), 1),
                       head_m=round(float(r * r * P.h_new(b10, Qs / r)) + srng.normal(0, 0.03), 2))
                  for Qs in (450.0, 600.0, 750.0, 900.0, 1050.0)]).to_csv(os.path.join(out, "p10_rig_test_2026.csv"), index=False)
    # P6: the OEM's type test of impeller pattern rev C at 340 mm, 1480 rpm
    t = P.P6_OEM_MM / 330.0
    h0, h1, h2 = bank["P6"]["new"]
    rows6 = []
    for Qs in (0.0, 450.0, 675.0, 900.0, 1035.0):
        q = Qs / P.QR
        rows6.append(dict(pattern="CW-250 rev C", impeller_mm=int(P.P6_OEM_MM), speed_rpm=1480, flow_m3h=Qs,
                          head_m=round(h0 * t * t - h1 * t * q - h2 * q * q + srng.normal(0, 0.03), 2)))
    pd.DataFrame(rows6).to_csv(os.path.join(out, "oem_type_test_rev_c.csv"), index=False)
    log = [("2014-05-20", "P1-P10", "Bank commissioned; factory test certificates filed (factory_tests.csv)"),
           ("2018-08-20", "P6", "Impeller replaced with OEM spare, pattern rev C, turned to 330 mm; certificate of the original impeller withdrawn; OEM type test of the pattern on file (oem_type_test_rev_c.csv)"),
           ("2024-06-11", "P2,P5", "Discharge piping modified; pressure gauge tappings relocated (see installation sheet)"),
           ("2025-04-07", "P4", "Impeller trimmed 330 -> 315 mm (shop job 25-118) to match the reduced duty of the east header"),
           ("2025-09-15", "P9", "VFD installed; speed setpoint from header pressure control"),
           ("2026-02-23", "P10", "Impeller replaced (cracked vane) with a supplier impeller; supplier's typical curve on file (p10_supplier_curve.md)"),
           ("2026-02-27", "P10", "Rig test in the pump shop after fitting the new impeller (p10_rig_test_2026.csv)"),
           ("2026-10-01", "header", "Header flowmeter FT-100 calibrated in place (certificate in docs); adjusted at 12:00"),
           ("2026-10-04", "P2", "Discharge pressure transmitter PT-206 replaced (failed); new transmitter 0-1600 kPa"),
           ("2026-10-11", "P2", "DCS range of PT-206 corrected at 06:00 after an operator query"),
           ("2026-10-06", "P6", "Instrument PM during the outage: discharge pressure transmitter PT-606 loop-checked and calibrated, returned to service 10:00"),
           ("2026-10-09", "P1", "Tripped 02:10 on low suction pressure, suction strainer blinded by debris; noisy and vibrating for about 20 min before the trip; strainer cleaned, restarted 05:00"),
           ("2026-10-08", "P7", "Clamp-on ultrasonic flow survey on the discharge pipe, three hours (flow_survey.csv; setup sheet in docs)"),
           ("2026-11-02", "P1-P10", "Overhaul ranking due")]
    log.sort(key=lambda r: r[0])
    pd.DataFrame(log, columns=["date", "pumps", "work_done"]).to_csv(os.path.join(out, "maintenance_log.csv"), index=False)
    return bank


if __name__ == "__main__":
    main(sys.argv[1])
