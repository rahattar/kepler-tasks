"""Reference: each cooling-water pump's head deficit at 900 m3/h and 1480 rpm, from the plant records alone.

    python3 solve.py DATA_DIR OUT_JSON

1. Pump head per running hour: (discharge - suction) / (rho g) + tapping height + velocity-head difference.
   Tapping heights are read off the stopped hours (check valve shut, casing at suction pressure, so discharge minus
   suction is minus the height): 0.80 m on most pumps, 2.10 m on P2 and 1.55 m on P5. The installation sheet still
   gives P5 its pre-2024 0.80 m although the log records the relocation. P6's transmitter was calibrated on
   2026-10-06 (log), and its stopped hours before that read about 1 m lower: the offset is taken separately on each
   side of the calibration, which removes the transmitter's earlier zero error. Velocity heads use the 250 mm
   discharge and 350 mm suction bores.
2. Corrections from the documents: FT-100 read 3.0 % high until 2026-10-01 12:00 (calibration certificate);
   PT-206 on P2 was a 0-1600 kPa transmitter ranged 0-1000 kPa from its replacement until 2026-10-11 06:00 (log),
   so those readings are multiplied by 1.6.
3. As-new curves (quadratic in flow): factory certificates, with the affinity laws for P3 (certificate at 1450 rpm)
   and the trim law for P4 (315 of 330 mm); P6 from the OEM's type test of its rev C pattern, run at 340 mm and
   trimmed to its 330 mm impeller; P10 from its 2026 rig test after the impeller change, run at 1490 rpm and brought
   to 1480 rpm (the supplier's catalogue curve is not used). P9's logged VFD speed enters through the affinity laws.
4. Wear: as found, head is a constant fraction k of as-new head at every flow (datasheet); rings wear over years,
   so k is constant over the four weeks, except on P1: it tripped on 2026-10-09 after running starved and vibrating
   (log), which rubs wear rings open, so P1 gets one ratio before the trip and another after it; the one after is
   its state on the test day. All the k are fitted together by least squares so that, every running
   hour, the pumps' flows at their measured heads add up to the corrected header flow. P7 and P8 always run
   together, so the balance fixes only their sum; the clamp-on survey of P7's discharge flow (2026-10-08) is
   added to the fit and splits them. The survey meter reports velocity times the bore keyed into it (instrument
   notes); its setup sheet keyed the bare steel pipe (273.0 mm OD, 9.27 mm wall, no lining: 254.46 mm), but the
   discharge lines are cement-mortar lined to 250 mm (installation sheet), so the survey flows are divided by
   (254.46/250)^2.
5. Deficit = (1 - k) x as-new head at 900 m3/h, with P1's ratio from after its trip.
"""
import json
import os
import re
import sys
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

DATA, OUT = sys.argv[1], sys.argv[2]
RHO, G, QR = 998.0, 9.81, 900.0
T0 = pd.Timestamp("2026-09-21 08:00")


def doc(name):
    return open(os.path.join(DATA, "docs", name)).read()


def days(ts):
    return (pd.to_datetime(ts) - T0) / pd.Timedelta(days=1)


def quad(Q, H):
    q = np.asarray(Q, float) / QR
    return tuple(np.linalg.lstsq(np.c_[np.ones_like(q), -q, -q * q], np.asarray(H, float), rcond=None)[0])


def scaled(c, r):
    """Affinity or trim law with ratio r: H(Q) = r^2 H0(Q / r)."""
    return c[0] * r * r, c[1] * r, c[2]


def hnew(c, Q):
    q = np.asarray(Q) / QR
    return c[0] - c[1] * q - c[2] * q * q


def flow_at(c, k, H, s):
    a, b, cc = k * c[2], k * c[1] * s, H - k * c[0] * s * s
    return np.maximum((-b + np.sqrt(np.maximum(b * b - 4 * a * cc, 0))) / (2 * a), 0) * QR


def main():
    reg = pd.read_csv(os.path.join(DATA, "pump_register.csv")).set_index("pump")
    cert = pd.read_csv(os.path.join(DATA, "factory_tests.csv"))
    oem = pd.read_csv(os.path.join(DATA, "oem_type_test_rev_c.csv"))
    rig10 = pd.read_csv(os.path.join(DATA, "p10_rig_test_2026.csv"))
    survey = pd.read_csv(os.path.join(DATA, "flow_survey.csv"))
    units = list(reg.index)
    tr = {u: pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % u.lower())) for u in units}
    hdr = pd.read_csv(os.path.join(DATA, "trends", "header.csv"))
    day = days(hdr.timestamp).values

    inst = doc("installation_sheet.md")
    d_s = float(re.search(r"suction pipe .*? \| (\d+) mm", inst).group(1)) / 1000
    d_d = float(re.search(r"discharge pipe .*? \| (\d+) mm", inst).group(1)) / 1000
    a_s, a_d = np.pi * d_s ** 2 / 4, np.pi * d_d ** 2 / 4

    def vel(Q):
        return ((Q / 3600 / a_d) ** 2 - (Q / 3600 / a_s) ** 2) / (2 * G)

    err = float(re.search(r"read high by ([\d.]+) %", doc("ft100_calibration_2026-10-01.md")).group(1)) / 100
    F = hdr.header_flow_m3h.values.astype(float)
    F = np.where(day < days("2026-10-01 12:00"), F / (1 + err), F)
    t_a, t_b = days("2026-10-04 00:00"), days("2026-10-11 06:00")
    log = pd.read_csv(os.path.join(DATA, "maintenance_log.csv"))
    ev = log[(log.pumps == "P6") & log.work_done.str.contains("PT-606")].iloc[0]
    t_cal = days("%s %s" % (ev.date, re.search(r"(\d\d:\d\d)", ev.work_done).group(1)))
    ev = log[(log.pumps == "P1") & log.work_done.str.contains("Tripped")].iloc[0]
    t_trip = days("%s %s" % (ev.date, re.search(r"(\d\d:\d\d)", ev.work_done).group(1)))

    head, run, spd = {}, {}, {}
    for u in units:
        t = tr[u]
        off = (t.suction_kpa - t.discharge_kpa).values * 1000.0 / (RHO * G)
        st = (t.state != "run").values
        if u == "P6":                     # one offset on each side of PT-606's calibration
            pre = day < t_cal
            dz = np.where(pre, np.median(off[st & pre]), np.median(off[st & ~pre]))
        else:
            dz = float(np.median(off[st]))
        pdis = t.discharge_kpa.values.astype(float)
        if u == "P2":
            m = (day >= t_a) & (day < t_b)
            pdis[m] *= 1.6
        head[u] = (pdis - t.suction_kpa.values) * 1000.0 / (RHO * G) + dz
        run[u] = (t.state == "run").values
        spd[u] = np.where(run[u], t.speed_rpm.values / 1480.0, 1.0)

    curves = {}
    for u in units:
        c = cert[cert.pump == u]
        if not c.empty:
            base = scaled(quad(c.flow_m3h, c.head_m), 1480.0 / c.speed_rpm.iloc[0])
            curves[u] = scaled(base, reg.loc[u, "impeller_mm"] / c.impeller_mm.iloc[0])
    curves["P6"] = scaled(quad(oem.flow_m3h, oem.head_m), reg.loc["P6", "impeller_mm"] / oem.impeller_mm.iloc[0])
    curves["P10"] = scaled(quad(rig10.flow_m3h, rig10.head_m), 1480.0 / rig10.speed_rpm.iloc[0])

    sv = doc("clamp_on_survey_2026-10-08.md")
    od = float(re.search(r"outside diameter \| ([\d.]+) mm", sv).group(1))
    wall = float(re.search(r"wall thickness \| ([\d.]+) mm", sv).group(1))
    keyed = (od - 2 * wall) / 1000.0              # no lining keyed in
    sv_q = survey.flow_m3h.values * (d_d / keyed) ** 2
    sv_idx = np.rint(days(survey.timestamp).values * 24).astype(int)
    sv_pump = survey.pump.iloc[0]

    i1 = units.index("P1")

    def kvec(k, u):
        if u == "P1":                     # P1's ratio before its trip is the extra parameter
            return np.where(day < t_trip, k[-1], k[i1])
        return k[units.index(u)]

    def pump_flow(u, k):
        k = kvec(k, u)
        Q = flow_at(curves[u], k, head[u], spd[u])
        for _ in range(3):
            Q = flow_at(curves[u], k, head[u] + vel(Q), spd[u])
        return Q

    def resid(k):
        tot = np.zeros(len(F))
        for i, u in enumerate(units):
            tot += np.where(run[u], pump_flow(u, k), 0.0)
        surv = pump_flow(sv_pump, k)[sv_idx] - sv_q
        return np.r_[(tot - F) / 30.0, surv / 5.0]

    k = least_squares(resid, np.full(len(units) + 1, 0.9), x_scale=0.01, xtol=1e-12, ftol=1e-12, gtol=1e-12).x
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump({u: round((1 - k[i]) * float(hnew(curves[u], QR)), 3) for i, u in enumerate(units)}, fh, indent=1)
    print({u: round(float(v), 4) for u, v in zip(units + ["P1 before trip"], k)})


if __name__ == "__main__":
    main()
