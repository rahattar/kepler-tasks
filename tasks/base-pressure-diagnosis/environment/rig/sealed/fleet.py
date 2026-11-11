"""Sealed definition of the shop's ten vacuum chambers and the quarterly base-pressure audit.

A chamber carries:
- `reg`: its register entry as issued (volume, turbo model, port conductance, seal material and length, the internal
  surfaces, the specified base pressure, the commissioning speed test);
- its true condition: the pump's speed factor, the real air leak, any trapped volume, and the surfaces, seal and port
  as they actually are;
- `events`: the dated rows of the maintenance log;
- `log`: the base-pressure log, one entry per gauge read at the end of a pumpdown;
- `certs`: its gauges' dated calibration factors;
- `speed`: the dated throughput (speed) tests the shop has run on it;
- `ctrl`: the turbo controller's monthly rows.

The truth of a chamber (`truth()`) is MS-BP's audit result for the chamber as it stands on the audit date: the total
gas load and the effective pumping speed at the reference condition (REF_H hours after the start of roughing
following an air vent, with the chamber at 20 C), and the cause by clause 6.

The audit date is 2026-11-02. Every record predates it.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpphys as P                                                      # noqa: E402

REF_H = 36.0                        # h from the start of roughing, the audit reference condition
AUDIT = "2026-11-02"
CHAMBER_IDS = ["VC%02d" % i for i in range(1, 11)]
BUDGET = 1                          # tests in the one audit order
DEFAULT_TEST_H = 16.0               # the contractor's standing pumping time, used when a plan names none
TEST_H_MIN = 4.0                    # the shortest and longest pumping times the contractor will test at
TEST_H_MAX = 48.0
EXAMPLE = "VC00"                    # the worked example chamber, outside the fleet

# How well the instruments repeat, each as the relative standard deviation of one reading. The records and the
# reports draw their noise from these, and records_format.md and vacwork.md state them, so the figures an agent
# weights its fit by are the figures the scatter was drawn from.
REPEAT = dict(
    reading=0.006,                  # a gauge reading in the base-pressure log
    speed_pressure=0.005,           # each pressure of a throughput speed test, the shop's or the contractor's
    ror_trace=0.0025,               # each point of a rate-of-rise trace
    ror_base=0.003,                 # a rate-of-rise report's base pressure before valve closure
    rga=0.010,                      # each partial pressure of a residual gas analysis
    helium=0.02,                    # each point of a helium leak detector's signal
)


def Ch(cid, reg, true, events, log, certs, speed, ctrl):
    return dict(id=cid, reg=reg, true=true, events=sorted(events), log=log, certs=certs, speed=speed, ctrl=ctrl)


def reg_entry(volume, turbo, c_port, seal, seal_cm, surfaces, p_spec):
    """surfaces: [(area m2, material)] as the register lists them."""
    return dict(volume=volume, turbo=turbo, c_port=c_port, seal=seal, seal_cm=seal_cm,
                surfaces=list(surfaces), p_spec=p_spec)


def config(ch, date=AUDIT):
    """The chamber's true physical configuration on a date, after every change logged on or before it."""
    r = ch["reg"]
    t = ch["true"]
    # `pump_actual` and `seal_actual`: the register names one part and another is fitted, with nothing in the
    # maintenance log to say so. Only the data can tell.
    c = dict(volume=r["volume"], turbo=t.get("pump_actual", r["turbo"]), c_port=r["c_port"],
             seal=t.get("seal_actual", r["seal"]), seal_cm=r["seal_cm"],
             surfaces=[(a * 1e4, m) for a, m in r["surfaces"]], leak=t.get("leak", 0.0),
             qv0=t.get("qv0", 0.0), tau=t.get("tau", 1.0), f_pump=1.0,
             wall_factor=t.get("wall_factor", 1.0))
    for d, kind, args in ch["events"]:
        if d > date:
            continue
        if kind == "internals":                      # the internal surfaces were replaced
            c["surfaces"] = [(a * 1e4, m) for a, m in args[0]]
        elif kind == "seal":                         # the door seal material was changed
            c["seal"] = args[0]
        elif kind == "seal_len":
            c["seal_cm"] = args[0]
        elif kind == "trap":                          # a cold trap or baffle in the high-vacuum port
            c["c_port"] = args[0]
        elif kind == "leak":                          # a real leak opened or was repaired
            c["leak"] = args
        elif kind == "trapped":                       # a trapped volume appeared (qv0 at the vent, tau in hours)
            c["qv0"], c["tau"] = args
        elif kind == "pump":                          # the turbo's condition changed
            c["f_pump"] = args
        elif kind == "note":
            pass
    return c


def load_surfaces(items, fixtures):
    return [(fixtures[k][0] * 1e4, fixtures[k][1]) for k in items]


def truth(ch, fixtures=None):
    """MS-BP's audit result for the chamber on the audit date."""
    c = config(ch, AUDIT)
    q = P.q_total(c, REF_H, "air", P.T_REF)
    p = P.p_base(c, q)
    return dict(cause=P.cause(c, REF_H), q_total=q, s_eff=P.s_eff(c, p), s_rated=P.s_rated(c, p),
                p_base=p, margins=P.margins(c, REF_H))


# ----------------------------------------------------------------------------------------------------------------
# fixtures the shop puts in its chambers: area m2 and material
FIXTURES = {
    "carrier set A": (2.4, "stainless steel, as machined"),
    "carrier set B": (1.6, "stainless steel, bead blasted"),
    "lens rack": (0.55, "aluminum, anodized"),
    "braze fixture": (2.1, "stainless steel, bead blasted"),
    "shield set": (1.8, "aluminum, bare"),
    "harness tray": (0.30, "PEEK"),
}

# ----------------------------------------------------------------------------------------------------------------
# The example chamber: sound records throughout, one mechanism plainly dominant, no change in the maintenance log,
# one gauge, a current speed test. No audited result is published for it: it is there to show the record formats
# and a chamber in sound condition, not to be a worked answer.
EX = Ch(
    EXAMPLE,
    reg_entry(2000, "TMP-1100", 1500, "fluoroelastomer", 170,
              [(6.0, "stainless steel, as machined")], 5e-7),
    true=dict(wall_factor=2.00, leak=1.0e-5),
    events=[("2026-06-15", "note", "Annual inspection: door seal sound, no work required.")],
    log=[("2026-08-04", "P1", "air", 16.0, 25.5, "CC-7000", None),
         ("2026-08-25", "P2", "air", 12.0, 24.2, "CC-7000", None),
         ("2026-09-15", "P3", "air", 20.0, 22.0, "CC-7000", None),
         ("2026-10-06", "P4", "air", 16.0, 19.1, "CC-7000", None),
         ("2026-10-20", "P5", "air", 24.0, 17.0, "CC-7000", None)],
    certs={"CC-7000": [("2026-01-12", 1.00)]},
    speed=[("2025-03-11", 16.0, 10.7), ("2026-07-07", 16.0, 25.4)],
    ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"],
)

# ----------------------------------------------------------------------------------------------------------------
FLEET = [
    # VC01 wall-outgassing: a large chamber relined mid-log, with a real leak beside the wall gas that a single
    # entry cannot separate from it. Nitrogen vents on two pumpdowns, a fixture set in on two, and a cold cathode
    # whose certificate the calibration laboratory issued 14 per cent out. That error
    # cancels in the gas load and shows only in the speed, which its throughput tests then report above what the
    # pump and port can deliver. Its reference instrument reads true, so which of the two gauges is out is
    # determinate rather than a choice between a wrong gauge and a wrong register.
    Ch("VC01",
       reg_entry(3200, "TMP-1600", 2400, "fluoroelastomer", 590,
                 [(9.0, "stainless steel, bead blasted")], 2.0e-7),
       true=dict(wall_factor=2.60, leak=1.0e-4, cert_wrong=("CC-7101", 1.14)),
       events=[("2026-07-21", "note", "Rotary feedthrough regreased."),
               ("2026-09-10", "internals", ([(9.0, "stainless steel, as machined")],
                                            "Chamber relined with machined panels.")),
               ("2026-09-08", "note", "Quartz monitor head replaced.")],
       log=[("2026-07-28", "P1", "air", 16.0, 25.6, "CC-7101", None),
            ("2026-08-18", "P2", "nitrogen", 16.0, 24.7, "CC-7101", None),
            ("2026-09-01", "P3", "air", 12.0, 23.5, "CC-7101", None),
            ("2026-09-22", "P4", "air", 20.0, 21.0, "CC-7101", "carrier set A"),
            ("2026-09-22", "P4", "air", 20.0, 21.0, "IG-7201", "carrier set A"),
            ("2026-10-13", "P5", "nitrogen", 24.0, 17.9, "CC-7101", None),
            ("2026-10-13", "P5", "nitrogen", 24.0, 17.9, "IG-7201", None),
            ("2026-10-27", "P6", "air", 16.0, 15.8, "CC-7101", "carrier set A"),
            ("2026-10-27", "P6", "air", 16.0, 15.8, "IG-7201", "carrier set A")],
       certs={"CC-7101": [("2026-02-03", 1.00)], "IG-7201": [("2026-02-03", 1.00)]},
       speed=[("2025-03-25", 16.0, 12.4), ("2026-06-23", 18.0, 24.5)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC02 wall-outgassing: internals replaced in September, so the earlier entries no longer apply. Its anodized
    # shields outgas at under half the table's figure, and a real leak sits beside them. Two gauges on the early
    # pumpdowns, and the cold cathode drifts from the July entry on: only the ratio of the two shows it.
    Ch("VC02",
       reg_entry(1900, "TMP-1100", 1600, "fluoroelastomer", 180,
                 [(5.5, "stainless steel, as machined"), (1.8, "aluminum, anodized")], 5.0e-7),
       true=dict(wall_factor=0.45, leak=1.95e-4, drift=("CC-7102", "2026-07-14", 0.00265)),
       events=[("2026-09-10", "internals", ([(5.5, "stainless steel, as machined"), (2.6, "aluminum, anodized")],
                                            "Heat shields and planetary drive replaced.")),
               ("2026-10-10", "note", "Ionization gauge IG-7202 filament open; head awaiting replacement.")],
       log=[("2026-07-14", "P1", "air", 16.0, 26.9, "CC-7102", None),
            ("2026-07-14", "P1", "air", 16.0, 26.9, "IG-7202", None),
            ("2026-08-11", "P2", "air", 20.0, 26.5, "CC-7102", None),
            ("2026-08-11", "P2", "air", 20.0, 26.5, "IG-7202", None),
            ("2026-09-29", "P3", "air", 16.0, 21.4, "CC-7102", None),
            ("2026-09-29", "P3", "air", 16.0, 21.4, "IG-7202", None),
            ("2026-10-20", "P4", "nitrogen", 12.0, 18.3, "CC-7102", None),
            ("2026-10-28", "P5", "air", 16.0, 17.0, "CC-7102", "lens rack")],
       certs={"CC-7102": [("2026-02-10", 1.00)], "IG-7202": [("2026-02-10", 1.00)]},
       speed=[("2025-04-08", 16.0, 15.9), ("2026-06-30", 16.0, 26.3)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC03 air-leak: an electropolished chamber with a real leak, and walls outgassing at two and a half times the
    # table's figure beside it. Its gauge serial is crossed with VC07's in the log from the late September entries
    # on; the certificates are right and the two factors differ.
    Ch("VC03",
       reg_entry(1200, "TMP-700", 900, "perfluoroelastomer", 150,
                 [(4.2, "stainless steel, electropolished")], 2.0e-7),
       true=dict(wall_factor=2.50, leak=3.7e-5),
       events=[("2026-06-10", "trap", (420, "Baffle fitted in the high-vacuum port.")),
               ("2026-08-19", "note", "Gate valve actuator serviced.")],
       log=[("2026-07-22", "P1", "air", 16.0, 24.0, "CC-7103", None),
            ("2026-08-12", "P2", "air", 24.0, 23.4, "CC-7103", None),
            ("2026-09-02", "P3", "air", 12.0, 21.8, "CC-7103", None),
            ("2026-09-23", "P4", "air", 16.0, 19.3, "CC-7107", None, "CC-7103"),
            ("2026-10-14", "P5", "air", 20.0, 16.2, "CC-7107", None, "CC-7103"),
            ("2026-10-28", "P6", "air", 16.0, 14.0, "CC-7107", None, "CC-7103")],
       certs={"CC-7103": [("2026-02-17", 1.00)]},
       speed=[("2025-04-22", 16.0, 15.0), ("2026-07-01", 20.0, 23.4)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC04 air-leak: a long nitrile seal makes permeation a credible reading, but the gas load does not follow the
    # shop temperature as permeation would. Bead-blasted internals add a wall load well above the table's. A
    # fixture set is in on two pumpdowns, and the last is vented with dry nitrogen.
    Ch("VC04",
       reg_entry(4200, "TMP-1600", 1600, "fluoroelastomer", 600,
                 [(4.5, "stainless steel, bead blasted")], 1.5e-7),
       true=dict(wall_factor=2.30, leak=4.0e-4),
       events=[("2026-06-18", "trap", (700, "Baffle fitted in the high-vacuum port.")),
               ("2026-08-05", "note", "Viewport 2 reseated."),
               ("2026-08-20", "seal", ("nitrile", "Door seal replaced; nitrile section fitted."))],
       log=[("2026-07-15", "P1", "air", 16.0, 26.0, "CC-7104", None),
            ("2026-08-05", "P2", "air", 20.0, 25.9, "CC-7104", "shield set"),
            ("2026-09-09", "P3", "air", 16.0, 23.1, "CC-7104", None),
            ("2026-09-30", "P4", "air", 12.0, 20.4, "CC-7104", "shield set"),
            ("2026-10-21", "P5", "air", 14.0, 17.2, "CC-7104", None),
            ("2026-10-29", "P6", "nitrogen", 16.0, 16.0, "CC-7104", None)],
       certs={"CC-7104": [("2026-02-24", 1.00)]},
       speed=[("2025-05-06", 16.0, 19.2), ("2026-07-08", 16.0, 25.8)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC05 permeation: the register gives a perfluoroelastomer door seal; a nitrile seal has been fitted from the
    # start, and nothing in the maintenance log says so. Taken from the register, the permeation is an eighth of
    # what it is and the rest reads as a leak. Only the records show it: across the season the constant part of the
    # gas load follows the wall temperature as permeation through nitrile does, which a leak cannot. A cold trap was
    # also fitted in the high-vacuum port, so the rated speed is not the register's; an agent that keeps the
    # register's port calls the pump the cause.
    Ch("VC05",
       reg_entry(2600, "TMP-1100", 1500, "perfluoroelastomer", 520,
                 [(6.0, "stainless steel, as machined")], 1.0e-7),
       true=dict(wall_factor=1.40, leak=3.5e-5, seal_actual="nitrile"),
       events=[("2026-08-24", "trap", (620, "Liquid nitrogen trap fitted in the high-vacuum port.")),
               ("2026-09-16", "note", "Door seal renewed, same material and section.")],
       log=[("2026-07-14", "P1", "air", 16.0, 24.9, "CC-7105", None),
            ("2026-08-04", "P2", "air", 20.0, 24.8, "CC-7105", None),
            ("2026-09-02", "P3", "air", 16.0, 22.3, "CC-7105", None),
            ("2026-09-23", "P4", "air", 24.0, 19.8, "CC-7105", None),
            ("2026-10-07", "P5", "air", 12.0, 17.7, "CC-7105", None),
            ("2026-10-21", "P6", "air", 16.0, 15.6, "CC-7105", None),
            ("2026-10-30", "P7", "air", 20.0, 14.2, "CC-7105", None)],
       certs={"CC-7105": [("2026-03-03", 1.00)]},
       speed=[("2025-05-20", 16.0, 19.7), ("2026-09-01", 18.0, 22.4)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC06 permeation: its shroud panels were replaced in September by electropolished ones, so the register's
    # bead-blasted surface no longer applies; an agent that keeps it calls the cause wall-outgassing. The new
    # panels are not yet conditioned and outgas at two and a half times the table's figure, beside a real leak.
    # Four pumpdowns since, spanning three pumping times and a nitrogen vent, so its split is determined by its own
    # records.
    Ch("VC06",
       reg_entry(5200, "TMP-1600", 2600, "perfluoroelastomer", 900,
                 [(11.0, "stainless steel, bead blasted")], 8.0e-8),
       true=dict(wall_factor=2.56, leak=4.5e-5),
       events=[("2026-09-28", "internals", ([(11.0, "stainless steel, electropolished")],
                                            "Shroud panels replaced with electropolished panels.")),
               ("2026-09-28", "seal", ("fluoroelastomer", "Shroud seals replaced with fluoroelastomer sections."))],
       log=[("2026-10-02", "P1", "air", 12.0, 19.0, "CC-7106", None),
            ("2026-10-09", "P2", "nitrogen", 20.0, 17.9, "CC-7106", None),
            ("2026-10-16", "P3", "air", 16.0, 16.9, "CC-7106", None),
            ("2026-10-26", "P4", "air", 12.0, 15.3, "CC-7106", None)],
       certs={"CC-7106": [("2026-03-10", 1.00)]},
       speed=[("2025-06-03", 16.0, 20.7), ("2026-10-05", 14.0, 17.2)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC07 virtual-leak: a trapped volume behind a fixture plate fitted in July, emptying with a time constant of a
    # day. Across the ordinary 12-24 h pumpdowns that is hard to tell from wall gas; the 44 h weekend pumpdown in
    # September settles it, so this chamber needs no test. Nitrogen vents on two pumpdowns, the pump fitted is not
    # the one the register names, and its gauge serial is crossed with VC03's from its October entries on.
    Ch("VC07",
       reg_entry(1600, "TMP-1600", 1100, "fluoroelastomer", 170,
                 [(4.8, "stainless steel, electropolished")], 1.5e-7),
       true=dict(wall_factor=1.40, leak=9.0e-6, pump_actual="TMP-700"),
       events=[("2026-07-20", "trapped", (4.5e-4, 24.0)),
               ("2026-07-20", "note", "Substrate fixture plate refitted with new clamping bars.")],
       log=[("2026-08-03", "P1", "air", 16.0, 25.5, "CC-7107", None),
            ("2026-08-24", "P2", "nitrogen", 20.0, 24.3, "CC-7107", None),
            ("2026-09-14", "P3", "air", 12.0, 22.1, "CC-7107", None),
            ("2026-09-28", "P4", "air", 44.0, 19.6, "CC-7107", None),
            ("2026-10-05", "P5", "air", 24.0, 19.2, "CC-7103", None, "CC-7107"),
            ("2026-10-19", "P6", "nitrogen", 16.0, 17.1, "CC-7103", None, "CC-7107"),
            ("2026-10-26", "P7", "air", 16.0, 16.0, "CC-7103", None, "CC-7107")],
       certs={"CC-7107": [("2026-03-17", 1.42)]},
       speed=[("2025-06-17", 16.0, 24.1), ("2026-07-15", 16.0, 25.6)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC08 virtual-leak: a trapped volume appeared when the cryopanel brackets were replaced in October. The four
    # pumpdowns before it settle the wall gas and the leak, and they still apply: the bracket work changed neither.
    # The two since are both at 16 h, so they give the trapped load at 16 h and nothing about how fast it empties.
    # Its gas load at the reference condition needs one measurement at a longer pumping time: the one chamber the
    # audit test must be spent on, and spent at a time other than the contractor's default. Its time constant, 14 h,
    # lies away from every round figure a solver might assume in place of measuring it (12 h misses by 21 per cent
    # of the trapped load, 16 h by 20), so that only a measurement gets it.
    Ch("VC08",
       reg_entry(2200, "TMP-1100", 1300, "fluoroelastomer", 200,
                 [(5.2, "stainless steel, electropolished")], 1.2e-7),
       true=dict(wall_factor=1.30, leak=7.0e-6),
       events=[("2026-10-06", "trapped", (1.57e-3, 14.0)),
               ("2026-10-06", "note", "Cryopanel brackets replaced.")],
       log=[("2026-07-21", "P1", "air", 20.0, 25.0, "CC-7108", None),
            ("2026-08-11", "P2", "air", 12.0, 24.5, "CC-7108", None),
            ("2026-09-01", "P3", "air", 24.0, 22.9, "CC-7108", None),
            ("2026-09-22", "P4", "nitrogen", 16.0, 20.4, "CC-7108", None),
            ("2026-10-13", "P5", "air", 16.0, 16.7, "CC-7108", None),
            ("2026-10-27", "P6", "air", 16.0, 14.6, "CC-7108", None)],
       certs={"CC-7108": [("2026-03-24", 1.00)]},
       speed=[("2025-07-01", 16.0, 23.8), ("2026-10-09", 18.0, 17.3)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC09 pump-speed: the turbo lost speed in September. The gas load is wall gas and a leak in comparable
    # measure, so an agent that skips clause 6 answers wall-outgassing. The controller rows date the change, which
    # voids the speed test.
    Ch("VC09",
       reg_entry(1400, "TMP-700", 1000, "fluoroelastomer", 400,
                 [(4.5, "stainless steel, as machined")], 2.0e-7),
       true=dict(wall_factor=2.40, leak=7.0e-5, drift=("CC-7109", "2026-07-29", 0.00215)),
       events=[("2026-09-12", "pump", 0.45),
               ("2026-09-12", "note", "Turbo reported a bearing alarm; reset and returned to service."),
               ("2026-10-05", "note", "Ionization gauge IG-7209 head contaminated; removed for cleaning.")],
       log=[("2026-07-29", "P1", "air", 16.0, 26.1, "CC-7109", None),
            ("2026-07-29", "P1", "air", 16.0, 26.1, "IG-7209", None),
            ("2026-08-19", "P2", "air", 20.0, 25.2, "CC-7109", None),
            ("2026-08-19", "P2", "air", 20.0, 25.2, "IG-7209", None),
            ("2026-09-30", "P3", "air", 16.0, 20.5, "CC-7109", None),
            ("2026-09-30", "P3", "air", 16.0, 20.5, "IG-7209", None),
            ("2026-10-14", "P4", "nitrogen", 16.0, 18.4, "CC-7109", None),
            ("2026-10-28", "P5", "air", 12.0, 16.2, "CC-7109", None)],
       certs={"CC-7109": [("2026-04-07", 1.00)], "IG-7209": [("2026-04-07", 1.00)]},
       speed=[("2025-07-15", 16.0, 26.1), ("2026-07-02", 16.0, 25.7)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),

    # VC10 pump-speed: a small chamber whose turbo has been falling away since August, with wall gas and a leak in
    # comparable measure. Its gauge was recalibrated in September, so the earlier certificate stops applying.
    Ch("VC10",
       reg_entry(900, "TMP-400", 700, "fluoroelastomer", 225,
                 [(2.6, "stainless steel, as machined")], 3.0e-7),
       true=dict(wall_factor=2.20, leak=3.6e-5),
       events=[("2026-08-17", "pump", 0.42),
               ("2026-08-17", "note", "Turbo drive reported over-temperature; fan filter cleaned.")],
       log=[("2026-07-02", "P0", "air", 20.0, 23.3, "CC-7110", None),
            ("2026-07-23", "P1", "air", 16.0, 23.8, "CC-7110", None),
            ("2026-08-27", "P2", "air", 16.0, 22.2, "CC-7110", None),
            ("2026-09-17", "P3", "nitrogen", 24.0, 19.8, "CC-7110", None),
            ("2026-10-08", "P4", "air", 12.0, 16.9, "CC-7110", None),
            ("2026-10-29", "P5", "air", 20.0, 13.7, "CC-7110", "carrier set A")],
       certs={"CC-7110": [("2026-04-14", 1.00), ("2026-09-22", 0.88)]},
       speed=[("2025-02-25", 16.0, 7.4), ("2026-07-09", 20.0, 23.6)],
       ctrl=["2026-07-01", "2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02", "2026-09-09", "2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07", "2026-10-14", "2026-10-21", "2026-10-28"]),
]

BY = {c["id"]: c for c in FLEET}
BY[EXAMPLE] = EX

# The regions the contractor hoods in turn during a helium leak test, and the region each chamber's real leak sits
# in. A chamber with no real leak worth finding still gets the full sweep.
REGIONS = ["door seal", "viewport flange", "feedthrough flange", "gate valve flange", "chamber weld seam"]
ELASTOMER_REGIONS = ["door seal", "viewport flange", "gate valve flange"]
LEAK_AT = {
    "VC01": "feedthrough flange", "VC02": "viewport flange", "VC03": "chamber weld seam",
    "VC04": "feedthrough flange", "VC05": "viewport flange", "VC06": "gate valve flange",
    "VC07": "door seal", "VC08": "viewport flange", "VC09": "feedthrough flange",
    "VC10": "chamber weld seam",
}

# The contractor's standing pumping time for each chamber and the chamber wall temperature on the day it runs
# this quarter's tests. The order may name another pumping time (TEST_H_MIN to TEST_H_MAX); the wall
# temperature is the day's either way, and is not the reference condition of MS-BP clause 2.
AUDIT_TESTS = {
    "VC01": (16.0, 14.9), "VC02": (16.0, 16.3), "VC03": (16.0, 13.3), "VC04": (16.0, 15.4),
    "VC05": (16.0, 13.8), "VC06": (16.0, 13.0), "VC07": (16.0, 15.0), "VC08": (16.0, 13.7),
    "VC09": (16.0, 15.5), "VC10": (16.0, 13.1),
}
HE_AIR_RATIO = 2.69                 # helium leak rate over air leak rate for a channel in molecular flow


def cert_factor(serial, date):
    """The calibration factor the certificates give for a gauge on a date. The certificates are correct; it is the
    log's serial column that is crossed on two chambers."""
    for ch in FLEET + [EX]:
        if serial in ch["certs"]:
            certs = ch["certs"][serial]
            f = certs[0][1]
            for d, v in certs:
                if d <= date:
                    f = v
            return f
    raise KeyError(serial)


def _days(a, b):
    """Whole days from date a to date b, both as YYYY-MM-DD."""
    import datetime
    fa = datetime.date(*map(int, a.split("-")))
    fb = datetime.date(*map(int, b.split("-")))
    return (fb - fa).days


def cert_wrong_factor(ch, serial):
    """A certificate the calibration laboratory issued wrong. The gauge's true factor is the certificate's figure
    times this, so every pressure the certificate yields is low by it and every speed the certificate yields is
    high by it. The two cancel in Q = p S_eff, and the fit of the gas budget is as good as ever; what gives it
    away is that the speed then comes out above what the pump and port can deliver, which MS-BP clause 4 says
    cannot happen."""
    w = ch["true"].get("cert_wrong")
    if not w or w[0] != serial:
        return 1.0
    return w[1]


def drift_factor(ch, serial, date):
    """A dirtying cold cathode gauge reads progressively low. The drift is a ramp, not a step: it shows only as a
    slow trend in the ratio to the chamber's second gauge, never as a clean step against it."""
    d = ch["true"].get("drift")
    if not d or d[0] != serial or date < d[1]:
        return 1.0
    return 1.0 + d[2] * _days(d[1], date)


def log_reading(ch, entry, fixtures=FIXTURES):
    """What the gauge indicated at the end of a pumpdown, before noise. The chamber is taken as it was on the
    entry's date, with the entry's vent gas, duration, wall temperature and any fixture load. The reading is the
    true indicated pressure divided by the gauge's own calibration factor and by its drift; `actual` names the gauge
    that was really read where the log's serial column is crossed."""
    date, _pid, vent, hours, temp_c, serial, load = entry[:7]
    actual = entry[7] if len(entry) > 7 else None
    real = actual or serial
    c = config(ch, date)
    if load:
        c = dict(c, surfaces=list(c["surfaces"]) + load_surfaces([load], fixtures))
    ind = P.indicated(c, hours, vent, temp_c + 273.15)
    return ind / (cert_factor(real, date) * drift_factor(ch, real, date) * cert_wrong_factor(ch, real))
