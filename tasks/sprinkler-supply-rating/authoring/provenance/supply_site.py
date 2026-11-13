"""The site as it is: the sealed definition of the city main, the connection, the ten risers and what was done to
them, and the tests that produced the records. build.py writes the records and the expected rating from it.

Everything a record does not say is here: the backflow preventer's opening differential and flow coefficient
before and after its overhaul, each lead-in's C and how fast it is falling, the control valve left partly shut,
the check that sticks, the gauges' zero errors, and which rows of the log carry the wrong serial.
"""
import datetime as dt
import math
import random

import numpy as np

import ssphys as P

SEED = 20261113
GRID_START = dt.datetime(2021, 12, 1)
GRID_END = dt.datetime(2026, 10, 1)
STEP_MIN = 30
LOG_START = dt.date(2023, 1, 1)
LOG_END = dt.date(2026, 9, 30)
AUDIT_DATE = dt.date(2026, 10, 5)
REF_FROM, REF_TO = dt.date(2026, 7, 1), dt.date(2026, 9, 30)      # the reference quarter
REF_HOURS = (17, 20)                                               # 17:00 up to, not including, 20:00
PIT_BELOW_FT = 8.0             # the utility's transmitter is in the pit, this far below the site datum
HOSE_OUTSIDE = 500.0           # gpm, taken from the yard main at the reference condition

# ---------------------------------------------------------------------------------------------- city and connection
B_MAIN = 5.60                  # psi at 1000 gpm
OVERHAUL = dt.datetime(2025, 3, 11, 9, 30)
BFP_BEFORE = {"h_b": 7.4, "Cv_b": 720.0}
BFP_AFTER = {"h_b": 5.1, "Cv_b": 640.0}       # springs renewed; No. 2 isolating valve not fully reopened
BFP_SHEET = {"h_b": 4.0, "Cv_b": 950.0}       # the maker's figures for the assembly as new


def site_state(t):
    s = dict(BFP_BEFORE if t < OVERHAUL else BFP_AFTER)
    s["B"] = B_MAIN
    return s


# ---------------------------------------------------------------------------------------------- the risers
# C_audit: the lead-in's C on the audit date; aging: how much higher it was per year before that.
RISERS = [
    dict(id="SR01", building="A", material="DI-CL", size="8", length_ft=310, laid=2004, C_audit=140.0, aging=0.0,
         check=None, gauge_ft=4.5, gauges=[("G-1407", None)], drain=[("2 in. angle", None)], q_d=1250,
         placard_psi=55),
    dict(id="SR02", building="A", material="CI", size="6", length_ft=220, laid=1978, C_audit=82.0, aging=0.6,
         check=None, gauge_ft=5.0, gauges=[("G-1411", None)], drain=[("2 in. angle", None)], q_d=900,
         placard_psi=51),
    dict(id="SR03", building="B", material="DI-CL", size="6", length_ft=280, laid=2001, C_audit=140.0, aging=0.0,
         check=None, gauge_ft=4.0, gauges=[("G-1420", None)], drain=[("2 in. angle", None)], q_d=950,
         placard_psi=53, valve=[(dt.datetime(2024, 11, 19, 11, 0), 250.0)]),
    dict(id="SR04", building="B", material="CI", size="6", length_ft=350, laid=1974, C_audit=74.0, aging=4.4,
         check="LC-6", h_c=1.6, gauge_ft=5.5, gauges=[("G-1423", None)], drain=[("2 in. angle", None)], q_d=850,
         placard_psi=50),
    dict(id="SR05", building="C", material="DI-CL", size="6", length_ft=300, laid=2009, C_audit=140.0, aging=0.0,
         check="LC-6", h_c=3.1, gauge_ft=4.5, gauges=[("G-1431", None)], drain=[("2 in. angle", None)], q_d=1080,
         placard_psi=47),
    dict(id="SR06", building="C", material="CI", size="8", length_ft=520, laid=1971, C_audit=66.0, aging=0.5,
         check=None, gauge_ft=6.0, gauges=[("G-1436", None)],
         drain=[("2 in. angle", dt.datetime(2024, 5, 14, 13, 0)), ("1-1/2 in. globe", None)], q_d=1100,
         placard_psi=42),
    dict(id="SR07", building="C", material="DI-CL", size="6", length_ft=150, laid=2012, C_audit=140.0, aging=0.0,
         check=None, gauge_ft=4.0, gauges=[("G-1440", None)], drain=[("2 in. angle", None)], q_d=520,
         placard_psi=61),
    dict(id="SR08", building="D", material="CI", size="6", length_ft=270, laid=1983, C_audit=90.0, aging=0.7,
         check=None, gauge_ft=5.0, gauges=[("G-1452", dt.datetime(2025, 6, 3, 10, 0)), ("G-2291", None)],
         drain=[("2 in. angle", None)], q_d=820, placard_psi=47),
    dict(id="SR09", building="D", material="DI-CL", size="8", length_ft=260, laid=2006, C_audit=140.0, aging=0.0,
         check="LC-8", h_c=1.4, gauge_ft=4.5, gauges=[("G-1458", None)], drain=[("2 in. angle", None)], q_d=1100,
         placard_psi=49),
    dict(id="SR10", building="D", material="CI", size="6", length_ft=215, laid=1980, C_audit=70.0, aging=0.8,
         check=None, gauge_ft=5.0, gauges=[("G-1463", None)], drain=[("2 in. angle", None)], q_d=880,
         placard_psi=52),
]
# the example riser: sound records throughout
EXAMPLE = dict(id="SR00", building="E", material="DI-CL", size="6", length_ft=220, laid=2010, C_audit=140.0,
               aging=0.0, check=None, gauge_ft=4.5, gauges=[("G-1399", None)], drain=[("2 in. angle", None)],
               q_d=800, placard_psi=60)

CHECK_SHEET = {"LC-6": 1.5, "LC-8": 1.5}                 # the maker's opening differential, psi
GAUGE_ZERO = {"G-1399": 0.0, "G-1407": -0.2, "G-1411": 0.9, "G-1420": 0.1, "G-1423": 0.3, "G-1431": -0.1,
              "G-1436": 0.2, "G-1440": 0.0, "G-1452": 0.1, "G-2291": 1.3, "G-1458": -0.3, "G-1463": -0.7}
# the log's serial column carries the other riser's serial on these rounds (year, month)
CROSSED = {"risers": ("SR02", "SR10"), "rounds": [(2026, 7), (2026, 8), (2026, 9)]}
READ_SD = 0.08                 # a supply gauge's repeatability, psi; read to 0.1

# work in the maintenance log that changed nothing
NO_EFFECT = [
    (dt.date(2023, 3, 22), "SR05", "Tamper switch on control valve tested."),
    (dt.date(2023, 8, 9), "SR10", "Leak at lead-in flange in valve room; clamp fitted, no pipe replaced."),
    (dt.date(2024, 2, 6), "SR01", "Control valve exercised and lubricated."),
    (dt.date(2024, 7, 30), "SR07", "Alarm gong bearing replaced."),
    (dt.date(2025, 9, 16), "SR04", "Fire department connection caps replaced."),
    (dt.date(2026, 1, 20), "SR09", "Control valve exercised and lubricated."),
    (dt.date(2026, 4, 14), "SR02", "Riser room heater replaced."),
]


def years_before_audit(t):
    d = t.date() if isinstance(t, dt.datetime) else t
    return (AUDIT_DATE - d).days / 365.25


def at(schedule, t):
    """The entry of a [(value, until), ...] schedule in force at t (until None: still in force)."""
    for value, until in schedule:
        if until is None or t < until:
            return value
    return schedule[-1][0]


def riser_state(r, t):
    s = dict(material=r["material"], size=r["size"], length_ft=r["length_ft"], gauge_ft=r["gauge_ft"],
             C=r["C_audit"] + r["aging"] * years_before_audit(t), drain=at(r["drain"], t),
             valve_cv=P.VALVE_OPEN_CV[r["size"]], check=bool(r["check"]), h_c=r.get("h_c", 0.0),
             gauge=at(r["gauges"], t))
    for when, cv in r.get("valve", []):
        if t >= when:
            s["valve_cv"] = cv
    return s


# ---------------------------------------------------------------------------------------------- the city main
def _bump(h, centre, width):
    d = (h - centre + 12.0) % 24.0 - 12.0
    return math.exp(-0.5 * (d / width) ** 2)


class Main:
    """The city main's static at the connection, at the site datum, on a 30 minute grid and linear between."""

    def __init__(self):
        rng = np.random.RandomState(SEED)
        n = int((GRID_END - GRID_START).total_seconds() // (60 * STEP_MIN)) + 1
        rho = math.exp(-(STEP_MIN / 60.0) / 8.0)
        slow = np.zeros(n)
        e = rng.normal(0.0, 0.7 * math.sqrt(1 - rho ** 2), n)
        for i in range(1, n):
            slow[i] = rho * slow[i - 1] + e[i]
        fast = rng.normal(0.0, 0.12, n)
        S = np.zeros(n)
        for i in range(n):
            t = GRID_START + dt.timedelta(minutes=STEP_MIN * i)
            h = t.hour + t.minute / 60.0
            doy = t.timetuple().tm_yday
            work = t.weekday() < 5
            S[i] = (79.5 - 0.45 * (t - dt.datetime(2023, 1, 1)).days / 365.25
                    - 2.2 * math.cos(2 * math.pi * (doy - 196) / 365.25)
                    + 5.5 * _bump(h, 3.0, 2.2) - (3.2 if work else 1.2) * _bump(h, 7.6, 1.3)
                    - (6.0 if work else 3.0) * _bump(h, 18.4, 1.8))
        self.S = S + slow + fast
        self.n = n
        self.record = np.round(self.S + P.PSI_PER_FT * PIT_BELOW_FT + rng.normal(0.0, 0.05, n), 2)

    def time(self, i):
        return GRID_START + dt.timedelta(minutes=STEP_MIN * i)

    def _x(self, t):
        return (t - GRID_START).total_seconds() / (60.0 * STEP_MIN)

    def at(self, t):
        x = self._x(t)
        i = int(math.floor(x))
        f = x - i
        return float(self.S[i] * (1 - f) + self.S[i + 1] * f)

    def held(self, t0, t1):
        """The highest the main has stood between t0 and t1."""
        i0, i1 = int(math.ceil(self._x(t0))), int(math.floor(self._x(t1)))
        m = max(self.at(t0), self.at(t1))
        if i1 >= i0:
            m = max(m, float(self.S[i0:i1 + 1].max()))
        return m

    def reference(self):
        """S at the reference condition: the working-day mean of 17:00 to 20:00 over the reference quarter."""
        v = []
        for i in range(self.n):
            t = self.time(i)
            if REF_FROM <= t.date() <= REF_TO and t.weekday() < 5 and REF_HOURS[0] <= t.hour < REF_HOURS[1]:
                v.append(self.S[i])
        return float(np.mean(v))


# ---------------------------------------------------------------------------------------------- the tests
START_TIMES = [(6, 40), (7, 30), (9, 10), (10, 20), (13, 10), (14, 40), (16, 20), (8, 20), (11, 30), (15, 30)]


def reading(true, serial, rng):
    return round(true + GAUGE_ZERO[serial] + rng.gauss(0.0, READ_SD), 1)


def simulate(risers=RISERS, tag="site", first=LOG_START, last=LOG_END, main=None):
    """Every round of main drain tests, the yard hydrant tests and the utility's flow tests.
    Returns dict(main, drain_log, yard_tests, utility_tests)."""
    main = main or Main()
    rng = random.Random("%s/%d" % (tag, SEED))
    last_flow = dt.datetime(first.year, first.month, 1) - dt.timedelta(days=17, hours=13)
    events = []                                   # (time, kind, payload) in time order
    y, m = first.year, first.month
    k = 0
    while dt.date(y, m, 1) <= last:
        day = rng.randint(6, 22)
        d = dt.date(y, m, day)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        hh, mm = START_TIMES[(k * 3 + rng.randint(0, 2)) % len(START_TIMES)]
        events.append((dt.datetime(d.year, d.month, d.day, hh, mm), "round", k))
        k += 1
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    for yr in range(first.year, last.year + 1):
        when = dt.datetime(yr, 9, 24, 10, 15)
        while when.weekday() >= 5:
            when += dt.timedelta(days=1)
        if first <= when.date() <= last:
            events.append((when, "yard", yr))
    if first <= OVERHAUL.date() <= last:
        events.append((OVERHAUL, "overhaul", None))
    events.sort(key=lambda e: e[0])

    drain_log, yard_tests = [], []
    for when, kind, payload in events:
        if kind == "overhaul":
            last_flow = when + dt.timedelta(hours=5)          # the yard was drawn on while the assembly was set up
        elif kind == "round":
            order = risers[(payload * 3) % len(risers):] + risers[:(payload * 3) % len(risers)]
            t = when
            for r in order:
                site, rs = site_state(t), riser_state(r, t)
                serial = rs["gauge"]
                held = main.held(last_flow, t - dt.timedelta(minutes=2))
                static = reading(P.held_static(site, rs, held), serial, rng)
                p_g, q = P.drain_test(site, rs, main.at(t))
                logged = serial
                if r["id"] in CROSSED["risers"] and (t.year, t.month) in CROSSED["rounds"]:
                    other = [x for x in risers if x["id"] in CROSSED["risers"] and x["id"] != r["id"]]
                    if other:
                        logged = riser_state(other[0], t)["gauge"]
                drain_log.append(dict(riser=r["id"], time=t, gauge_serial=logged, static_psi=static,
                                      residual_psi=reading(p_g, serial, rng), true_flow=q))
                last_flow = t + dt.timedelta(minutes=3)
                t = t + dt.timedelta(minutes=rng.randint(20, 34))
        elif kind == "yard":
            # one 2-1/2 in. outlet of yard hydrant YH-2, residual on the supply gauge of a riser that is not flowing
            t = when
            site = site_state(t)
            r = [x for x in risers if x["id"] in ("SR07", "SR00")][0]
            rs = riser_state(r, t)
            held = main.held(last_flow, t - dt.timedelta(minutes=5))
            static = reading(P.held_static(site, rs, held), rs["gauge"], rng)
            # the hydrant's outlet discharges to atmosphere from the yard main
            lo, hi = 0.0, 3000.0
            for _ in range(80):
                Q = 0.5 * (lo + hi)
                p_yard = main.at(t) - P.d_main(site["B"], Q) - P.d_bfp(site["h_b"], site["Cv_b"], Q)
                pit = (Q / (P.PITOT * P.OUTLET_C["smooth"] * 2.5 ** 2)) ** 2
                if p_yard - 3.0 > pit * 1.12:                    # the hydrant's own loss, about 12 per cent
                    lo = Q
                else:
                    hi = Q
            pit_true = (Q / (P.PITOT * P.OUTLET_C["smooth"] * 2.5 ** 2)) ** 2
            p_yard = main.at(t) - P.d_main(site["B"], Q) - P.d_bfp(site["h_b"], site["Cv_b"], Q)
            resid_true = p_yard - P.PSI_PER_FT * rs["gauge_ft"]
            yard_tests.append(dict(time=t, flow_hydrant="YH-2", outlets=1, residual_riser=r["id"],
                                   pitot_psi=round(pit_true + rng.gauss(0.0, 0.15), 1), static_psi=static,
                                   residual_psi=reading(resid_true, rs["gauge"], rng), true_flow=Q))
            last_flow = t + dt.timedelta(minutes=6)

    # the utility's own flow tests on the city main: residual at H-41 by the connection, flow at another hydrant
    utility_tests = []
    plan = [(2023, 5, 16, "H-42", 1), (2023, 11, 14, "H-42", 1), (2024, 5, 14, "H-42", 2), (2024, 11, 12, "H-42", 1),
            (2025, 5, 20, "H-43", 1), (2025, 11, 18, "H-43", 1), (2026, 5, 19, "H-42", 1)]
    hydrant_outlet = {"H-42": "smooth", "H-43": "square"}
    for yr, mo, dy, hyd, outlets in plan:
        t = dt.datetime(yr, mo, dy, 10, 30)
        if not first <= t.date() <= last:
            continue
        S = main.at(t)
        c = P.OUTLET_C[hydrant_outlet[hyd]]
        lo, hi = 0.0, 6000.0
        for _ in range(80):
            Q = 0.5 * (lo + hi)
            pit = (Q / (outlets * P.PITOT * c * 2.5 ** 2)) ** 2
            if S - P.d_main(B_MAIN, Q) * 1.25 - 2.0 > pit * 1.15:   # the flow hydrant is further along the main
                lo = Q
            else:
                hi = Q
        pit_true = (Q / (outlets * P.PITOT * c * 2.5 ** 2)) ** 2
        utility_tests.append(dict(time=t, residual_hydrant="H-41", flow_hydrant=hyd, outlets=outlets,
                                  static_psi=round(S + rng.gauss(0.0, 0.1), 1),
                                  residual_psi=round(S - P.d_main(B_MAIN, Q) + rng.gauss(0.0, 0.1), 1),
                                  pitot_psi=round(pit_true + rng.gauss(0.0, 0.15), 1), true_flow=Q))
    return dict(main=main, drain_log=drain_log, yard_tests=yard_tests, utility_tests=utility_tests)


# ---------------------------------------------------------------------------------------------- the rating
def expected(main=None, risers=RISERS):
    """The rating at the reference condition, from the definition alone."""
    main = main or Main()
    S_ref = main.reference()
    t = dt.datetime(AUDIT_DATE.year, AUDIT_DATE.month, AUDIT_DATE.day, 12, 0)
    site = site_state(t)
    out = {}
    for r in risers:
        rs = riser_state(r, t)
        loss, p_yard, p_base = P.budget(site, rs, S_ref, float(r["q_d"]), r["q_d"] + HOSE_OUTSIDE)
        ranked = sorted(loss.items(), key=lambda kv: -kv[1])
        lo, hi = 0.0, float(r["q_d"])
        for _ in range(80):
            q = 0.5 * (lo + hi)
            if P.budget(site, rs, S_ref, q, q + HOSE_OUTSIDE)[2] > r["placard_psi"]:
                lo = q
            else:
                hi = q
        out[r["id"]] = dict(limit=ranked[0][0], p_yard_psi=p_yard, p_base_psi=p_base, q_avail_gpm=0.5 * (lo + hi),
                            losses=loss, runner_up=ranked[1][0], gap_psi=ranked[0][1] - ranked[1][1], S_ref=S_ref)
    return out


if __name__ == "__main__":
    sim = simulate()
    exp = expected(sim["main"])
    print("S_ref %.2f" % list(exp.values())[0]["S_ref"])
    for rid, e in exp.items():
        print(rid, e["limit"], "p_base %.1f q_avail %.0f" % (e["p_base_psi"], e["q_avail_gpm"]),
              " ".join("%s %.1f" % (k, v) for k, v in e["losses"].items()),
              "| next %s by %.1f" % (e["runner_up"], e["gap_psi"]))
    for u in sim["utility_tests"]:
        print("utility", u["time"].date(), u["flow_hydrant"], u["outlets"], u["static_psi"], u["residual_psi"],
              u["pitot_psi"], "Q %.0f" % u["true_flow"])
    for yt in sim["yard_tests"]:
        print("yard", yt["time"].date(), yt["pitot_psi"], yt["static_psi"], yt["residual_psi"], "Q %.0f" % yt["true_flow"])

