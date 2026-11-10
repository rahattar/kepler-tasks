"""Sealed definitions of the grinding jobs.

A job: the machine and its records (wheel and coolant history, idle power history, the true power model of each
wheel and coolant), the wheel now on the machine (specification, diameter), the part (material, lot, ground width),
the operation (work speed, coolant temperature) and the lots' heat treatment certificates.

The truth of a job (limit()) is the burn-limited depth of MS-GB for the operation as it will run: the true power model
of the current wheel and coolant at the end of the dressing interval, the current wheel diameter, the work speed the
table will run at (the programmed speed, or the table's speed limit when the machine log sets a lower one), the
coolant temperature it will run at (the job sheet's, or the coolant temperature the log gives while the chiller is out
of service), the contact width (two lands where the face has a relief groove), and the burn limit from the highest
tempering temperature of the part's lot."""
import numpy as np
import heat as B

BETA = {"100Cr6": np.sqrt(40 * 7810 * 460), "42CrMo4": np.sqrt(42 * 7850 * 470), "16MnCr5": np.sqrt(44 * 7850 * 465),
        "X40CrMoV5-1": np.sqrt(25 * 7800 * 460)}
PROPS = {"100Cr6": (40, 7810, 460), "42CrMo4": (42, 7850, 470), "16MnCr5": (44, 7850, 465), "X40CrMoV5-1": (25, 7800, 460)}
RW = {("A80K5V", "emulsion"): 0.75, ("A80K5V", "oil"): 0.62, ("A60J6V", "emulsion"): 0.78, ("A60J6V", "oil"): 0.65,
      ("B126V", "emulsion"): 0.30, ("B126V", "oil"): 0.22}
# true power model per (wheel, coolant): p0 (W/mm), p1 (W/mm per mm3/mm since dressing), u (J/mm3)
PM = {("A80K5V", "emulsion"): (6.0, 0.012, 42.0), ("A80K5V", "oil"): (3.6, 0.008, 31.0),
      ("A60J6V", "emulsion"): (7.5, 0.016, 36.0), ("A60J6V", "oil"): (4.5, 0.011, 27.0),
      ("B126V", "emulsion"): (9.0, 0.004, 55.0), ("B126V", "oil"): (5.5, 0.003, 44.0)}


def J(name, seed, machine, material, b, v_m_min, interval, lot, certs, T0, history, d_now, wheel_width=40, lands=None,
      table_limit=None, parts=None, chiller=None):
    """history: list of (from_date, wheel, coolant, idle_W) periods of the machine, the last one current; the idle
    power (wheel running out of contact, coolant on) rises with straight oil, which the wheel drags more of, and after
    spindle work.
    lands: (land width, gap) for a face ground as two lands (contact width 2 x land); table_limit: (date, m/min) of a
    table speed limit in the machine log; parts: (parts per dressing, stock mm, face length mm) when the job sheet
    gives the dressing interval in parts."""
    if parts:
        interval = parts[0] * parts[1] * parts[2]
    if lands:
        b = 2 * lands[0]
    v_run = min(v_m_min, table_limit[1]) if table_limit else v_m_min
    T_job = T0
    if chiller:                       # (date, coolant temperature) while the chiller is out of service
        T0 = chiller[1]
    return dict(name=name, seed=seed, machine=machine, material=material, b=b, v=v_run * 1000 / 60, v_m_min=v_m_min,
                interval=interval, lot=lot, certs=certs, T0=T0, history=history, d_now=d_now, wheel_width=wheel_width,
                lands=lands, table_limit=table_limit, parts=parts, chiller=chiller, T_job=T_job)


EXAMPLE = "job-ex"
JOBS = [
    J("job-ex", 1, "SG-2", "100Cr6", 18, 15, 900, "L2214", {"L2214": [180]}, 25,
      [("2026-01-05", "A80K5V", "emulsion", 980)], 384),
    # coolant changed to oil mid-records
    J("race-face", 11, "SG-1", "100Cr6", 22, 12, 1200, "L3107", {"L3107": [170], "L3044": [190]}, 24,
      [("2025-12-01", "A80K5V", "emulsion", 1050), ("2026-02-16", "A80K5V", "oil", 1550)], 371,
      table_limit=("2026-03-23", 10)),
    # wheel changed from A80 to A60 mid-records; idle up after spindle service
    J("die-insert", 12, "SG-3", "X40CrMoV5-1", 14, 9, 700, "H0921", {"H0921": [560, 580]}, 26,
      [("2025-11-10", "A80K5V", "emulsion", 860), ("2026-01-19", "A60J6V", "emulsion", 1520)], 392, parts=(25, 0.15, 180)),
    # lot re-tempered at a higher temperature
    J("shaft-seat", 13, "SG-2", "42CrMo4", 30, 14, 1000, "Q5512", {"Q5512": [200, 240], "Q5530": [200]}, 25,
      [("2025-12-15", "A80K5V", "emulsion", 1010)], 377, lands=(11, 8), chiller=("2026-04-06", 46)),
    # CBN wheel after an alumina wheel; coolant oil
    J("cam-flank", 14, "SG-4", "16MnCr5", 12, 20, 2500, "C7718", {"C7718": [160]}, 28,
      [("2025-12-01", "A60J6V", "oil", 1180), ("2026-02-02", "B126V", "oil", 1190)], 398, parts=(120, 0.08, 240)),
    # coolant changed from oil to emulsion; lot certificate among several
    J("gauge-block", 15, "SG-1", "100Cr6", 16, 7, 800, "L3166", {"L3107": [170], "L3166": [150], "L3044": [190]}, 23,
      [("2025-12-01", "A80K5V", "oil", 1550), ("2026-03-02", "A80K5V", "emulsion", 1100)], 365, lands=(5, 6),
      chiller=("2026-04-13", 44)),
    # idle power rose after a spindle bearing change; re-tempered lot
    J("punch-land", 16, "SG-3", "X40CrMoV5-1", 10, 8, 600, "H0977", {"H0977": [540, 600]}, 26,
      [("2025-11-10", "A60J6V", "emulsion", 820), ("2026-02-09", "A60J6V", "emulsion", 1640)], 388, parts=(20, 0.1, 300)),
    # wheel changed from A60 to A80; long dressing interval
    J("bushing-od", 17, "SG-4", "16MnCr5", 20, 16, 1600, "C7790", {"C7790": [210], "C7718": [160]}, 27,
      [("2025-12-01", "A60J6V", "emulsion", 1150), ("2026-02-23", "A80K5V", "emulsion", 1160)], 381,
      table_limit=("2026-03-30", 12)),
]
BY = {j["name"]: j for j in JOBS}
HIDDEN = [j["name"] for j in JOBS if j["name"] != EXAMPLE]


def current(j):
    return j["history"][-1]


def limit(j, wheel=None, coolant=None, V=None, Tt=None, d=None, b=None, pm=None, rw=None):
    _, w, c, _ = current(j)
    wheel = wheel or w; coolant = coolant or c
    p0, p1, u = pm or PM[(wheel, coolant)]
    V = j["interval"] if V is None else V
    Tt = max(j["certs"][j["lot"]]) if Tt is None else Tt
    dT = Tt + 200 - j["T0"]
    return B.a_max(j["v"], b or j["b"], d or j["d_now"], p0 + p1 * V, u, rw or RW[(wheel, coolant)], BETA[j["material"]], dT)
