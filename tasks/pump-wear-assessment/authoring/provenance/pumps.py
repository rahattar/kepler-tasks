"""Sealed definition: the cooling-water pump bank, P1-P10, ten pumps of one model (CW-250) on a common discharge
header. Units: m3/h, m, kPa, days.

Head curve of pump i as new, at 1480 rpm and its installed impeller:  H_new(Q) = h0 - h1 q - h2 q^2,  q = Q / 900.
As found:  H(Q, t) = k(t) H_new(Q),  k(t) = k_T - r (T_TEST - t)   (worn wear rings recirculate; head falls).
Graded:  deficit D = H_new(900) - H(900, T_TEST) = (1 - k_T) H_new(900), m, per pump.

- P4: impeller trimmed 330 -> 315 mm (2025).
  H_new4(Q) = t^2 H_cert(Q / t), t = 315/330.
- P9: VFD; at speed ratio s: H = s^2 k H_new(Q / s). Graded at 1480 rpm.
- P3: its factory certificate was run at 1450 rpm (motor of the test stand); at 1480 rpm the affinity laws apply.
- P10: replacement impeller (2026, other supplier); the supplier's typical curve is optimistic. The rig test made
  after fitting it (as new, at 1490 rpm, the shop motor) is in the records.
- P7, P8: started and stopped together (one breaker group), never apart; nothing in the records says so. A
  clamp-on survey of P7's discharge flow on 2026-10-08 is the one measurement that splits them.
- Header flowmeter read 3.0 % high until its recalibration on 2026-10-01 12:00.
- P2: discharge transmitter replaced 2026-10-04 with a 0-1600 kPa unit; the DCS kept the 0-1000 kPa span until
  2026-10-11 06:00, so in between it read 1000/1600 of the true gauge pressure.
- P2, P5: discharge tappings moved in 2024; the installation sheet was updated for P2 only (P5 still shows 0.80 m;
  its stopped-pump readings show 1.55 m).
- P6: impeller replaced in 2018 with an OEM spare of a later pattern (rev C), turned to 330 mm; no certificate of the
  spare. The OEM's type test of the pattern was run at 340 mm; the trim law brings it to P6's impeller.
- P1: tripped on 2026-10-09 at 02:10 after running starved (suction strainer blinded by debris). The cavitating,
  vibrating run rubbed the wear rings open: its head ratio steps down at the trip, from a 0.55 m deficit to its
  test-day value. Restarted 05:00. A constant ratio fitted over the four weeks lands near the average and misses.
- P6: discharge transmitter PT-606 read 10 kPa high until its loop check and zero trim on 2026-10-06 10:00 (pump out
  of service that week). Its stopped hours fall mostly after the trim, so one median of the stopped-hour offset
  over the window looks like the sheet's 0.80 m and hides the earlier 1.02 m error.
- The clamp-on survey of P7: the meter reports its measured velocity times the bore keyed into it. The surveyor keyed
  in the steel pipe (273.0 mm OD, 9.27 mm wall, no lining: 254.46 mm), but the discharge lines are cement-mortar
  lined to a 250 mm bore (installation sheet), so the survey reads (254.46/250)^2 = 3.6 % high.
"""
import numpy as np

UNITS = ["P%d" % i for i in range(1, 11)]
QR = 900.0                        # rated flow, m3/h
RHO, G = 998.0, 9.81
T_TEST = 42.0                     # 2026-11-02 08:00, from the trend start 2026-09-21 08:00
TEST_DATE = "2026-11-02"
TRIM = {"P4": 315.0 / 330.0}
P3_RPM = 1450.0
CAL_DAY, CAL_ERR = 10.1667, 0.030             # header meter recalibrated 2026-10-01 12:00 (day 10.17)
SPAN_FROM, SPAN_TO = 12.6667, 19.9167         # P2 wrong span 2026-10-04 00:00 .. 10-11 06:00
DZ = {u: 0.80 for u in UNITS}
DZ.update({"P2": 2.10, "P5": 1.55})           # discharge gauge above suction gauge, m
D_NOZ_S, D_NOZ_D = 0.35, 0.25                 # suction / discharge pipe ID at the gauges, m
P6_OEM_MM, P10_RIG_RPM = 340.0, 1490.0
DRY_PUMP, DRY_DAY, DRY_PRE = "P1", 17.75, 0.55          # trip 2026-10-09 02:00 (hour 426); deficit before it, m
ZERO_PUMP, ZERO_DAY, ZERO_KPA = "P6", 15.0833, 10.0     # PT-606 zero trimmed 2026-10-06 10:00 (hour 362)
SURVEY_KEYED_MM = 273.0 - 2 * 9.27                       # bore the clamp-on meter was told, mm
SURVEY_SCALE = (SURVEY_KEYED_MM / 250.0) ** 2            # survey reading / true flow
DEFICIT = {"P8": 0.45, "P2": 1.70, "P1": 2.36, "P10": 3.05, "P3": 4.45, "P4": 5.12, "P6": 5.80, "P5": 7.25,
           "P9": 7.93, "P7": 9.30}          # m at 900 m3/h on the test day: irregular, at least 0.66 m apart


def make_bank(seed=7):
    rng = np.random.default_rng(seed)
    bank = {}
    for u in UNITS:
        b = dict(unit=u)
        b["h0"] = 58.0 * (1 + rng.normal(0, 0.012))
        b["h1"] = 2.0 * (1 + rng.normal(0, 0.10))
        b["h2"] = 11.0 * (1 + rng.normal(0, 0.03))
        b["r"] = float(rng.uniform(0.00001, 0.00003))       # k lost per day (rings wear over years)
        bank[u] = b
    # the pair is two sister pumps from one casting lot: near-identical certificates
    for k in ("h0", "h1", "h2"):
        bank["P8"][k] = bank["P7"][k] * (1 + 0.002 * (1 if k == "h0" else -1))
    for u in UNITS:
        b = bank[u]
        b["cert"] = (b["h0"], b["h1"], b["h2"])             # factory certificate curve (full impeller)
        h0, h1, h2 = b["cert"]
        if u == "P6":                                        # later impeller pattern (rev C), no certificate
            h0, h1, h2 = 61.2, 1.4, 12.6
        if u == "P3":                                        # certificate at 1450 rpm; true curve at 1480
            r = 1480.0 / P3_RPM
            h0, h1, h2 = h0 * r * r, h1 * r, h2
        if u == "P10":                                       # other supplier: different curve, typical sheet optimistic
            h0, h1, h2 = 55.0, 1.0, 12.5
            b["cert"] = (h0 * 1.07, h1, h2 * 0.97)
        t = TRIM.get(u, 1.0)                                  # trim law: H(Q) = t^2 H(Q / t)
        b["new"] = (h0 * t * t, h1 * t, h2)
        hn = h_new(b, QR)
        b["kT"] = 1.0 - DEFICIT[u] / hn
        b["dk"] = (DEFICIT[u] - DRY_PRE) / hn if u == DRY_PUMP else 0.0   # head ratio lost at the trip
    return bank


def h_new(b, Q):
    h0, h1, h2 = b["new"]
    q = np.asarray(Q) / QR
    return h0 - h1 * q - h2 * q * q


def k_at(b, t):
    t = np.asarray(t, float)
    return b["kT"] - b["r"] * (T_TEST - t) + b.get("dk", 0.0) * (t < DRY_DAY)


def head(b, Q, t, s=1.0):
    """As-found head at flow Q, day t, speed ratio s."""
    return s * s * k_at(b, t) * h_new(b, np.asarray(Q) / s)


def flow_at_head(b, H, t, s=1.0):
    """Flow delivering head H (inverse of head), m3/h; 0 if H above shutoff."""
    h0, h1, h2 = b["new"]
    k = k_at(b, t)
    # s^2 k (h0 - h1 q/s - h2 q^2/s^2) = H, q = Q/QR
    a, bb, c = k * h2, k * h1 * s, H - k * h0 * s * s
    disc = bb * bb - 4 * a * c
    q = (-bb + np.sqrt(np.maximum(disc, 0))) / (2 * a)
    return np.maximum(q, 0) * QR


def deficit(b):
    return h_new(b, QR) * (1 - b["kT"])


def grade(est, bank, tol):
    res = {}
    for u in UNITS:
        e = est[u] - deficit(bank[u])
        res[u] = (float(e), abs(e) <= tol)
    return res
