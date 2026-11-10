"""Sealed definition: the octave-band sound power of three compressor packages in a plant hall, determined to plant
standard NS-7 (an ISO 3744 style engineering method over a reflecting floor).

The deliverable for each machine is its sound power level in the eight octave bands from 63 Hz to 8 kHz and its
A-weighted sound power level, in dB, for the machine as it stands now. A value is right when it is within TOL of this
definition.

The hall holds C1 and C2 in the open and C3 against the east wall. A contractor surveyed all three in September: the
sound pressure level in each band at the positions of each machine's array, with that machine running alone, plus the
background at every position with all three off. Those records are the agent's. They are not the answer:

- the hall's reverberation time is no longer the one in the acoustic report, because the absorptive ceiling panels
  were removed in the roof repair and not refitted (maintenance log), so the environmental correction has to be
  computed from the reverberation time as the hall is now, band by band;
- C2 ran at 2508 rpm during the survey (the survey's own speed column; the VFD limit of the plant trial, since
  lifted), so its levels are referred to its rated 2950 rpm by the standard's speed rule;
- C1 was surveyed with an enclosure access panel open (it was closed on 2026-09-20) and C3 was surveyed before its
  intake silencer was fitted, so each of those two needs the standard's configuration difference: the per-band level
  difference now against the survey at one position of its own array, the hall being unchanged;
- C3 stands 0.6 m from the east wall and radiates into a quarter space, and its array is at 2.0 m, not the nominal
  3.0 m of the register;
- the contractor's sheet enters four rows under the wrong machine: the two ends of C1's array under C2 and two of
  C2's under C1. Both arrays are at the same radius, so only the position table gives it away;
- the first day's pass, C4's array, was read with M-5, which carried no windscreen, and the second day's with M-2,
  which did, so the certificate correction belongs to most of the rows but not to C4's;
- the drive-end position of C1's array (P4) was set at 0.65 m to clear a pipe rack, so it is not on the measurement
  surface and is not a valid position;
- the ventilation blower of the adjacent bay runs continuously behind the louvred east wall and raises the 250 Hz and
  500 Hz background at P15 and P16 above the level with C2 running, so those two positions are not valid either;
- the maintenance log says what was done and when, in work orders, and nothing about what any of it does to a level.

More things look as though they need a reading than the booking of 2 allows: the hall's absorption area, the
configuration difference of each of the three machines changed after the survey, and the speed of the three surveyed
under a drive limit. The standard's speed rule settles the last three without a reading, the survey's own room check
settles the absorption area, and the note against C7 in the register carries the certified insertion loss of the
lagging that was refitted, which leaves exactly the two differences the booking can pay for.

The blower spectrum at P15 and P16, the ceiling panels' effect on the reverberation time and P4's distance were set by
authoring/provenance/tune.py from the design rules it states; it checks them.
"""
import math

import numpy as np

BANDS = [63, 125, 250, 500, 1000, 2000, 4000, 8000]
LABEL = {63: "63", 125: "125", 250: "250", 500: "500", 1000: "1k", 2000: "2k", 4000: "4k", 8000: "8k"}
AW = {63: -26.2, 125: -16.1, 250: -8.6, 500: -3.2, 1000: 0.0, 2000: 1.2, 4000: 1.0, 8000: -1.1}

TOL = 1.0                  # dB, on every band level and on the A-weighted level
SURVEY_SEED = 91           # the survey's own scatter; fixed, so the records do not move with the laboratory seed
NOISE_SLM = 0.15           # dB, one standard deviation of a meter reading (the standard states it)
NOISE_RT = 0.02            # relative, one standard deviation of a reverberation time reading
BUDGET = 2                 # readings of the booked meter, in all
SOUND_C = 0.161            # Sabine's constant, m
MIN_POSITIONS = 6          # the standard's least number of valid positions
WALL_CLEAR = 1.5           # m, the standard's clearance for a half space
BG_MARGIN = 6.0            # dB, the standard's background rule

ROOM = dict(L=30.0, W=16.0, H=6.5, V=3120.0)
# reverberation time of the hall as it is now (the ceiling lining is gone) and in the acoustic report (with it)
T60 = {63: 3.40, 125: 3.60, 250: 3.90, 500: 4.00, 1000: 4.00, 2000: 3.50, 4000: 2.60, 8000: 1.50}
T60_REPORT = {63: 2.60, 125: 2.30, 250: 1.60, 500: 1.10, 1000: 0.90, 2000: 0.90, 4000: 0.90, 8000: 0.80}
# the hall's general background with every machine off, away from the louvred wall
BG = {63: 64.0, 125: 62.0, 250: 58.0, 500: 55.0, 1000: 52.0, 2000: 49.0, 4000: 45.0, 8000: 41.0}
# the adjacent bay's ventilation blower, as it contributes at a position by the louvred wall and elsewhere
BLOWER_NEAR = {63: 68.0, 125: 74.0, 250: 87.2, 500: 89.3, 1000: 78.0, 2000: 70.0, 4000: 62.0, 8000: 55.0}
BLOWER_FAR = {b: v - 22.0 for b, v in BLOWER_NEAR.items()}

# The three instruments of the survey, which ran over three days. M-2 and M-9 carried windscreens, whose certificate
# corrections are added to their indications; M-5, which took the first day's pass, carried none. The survey's own
# pass order decides which instrument read a position, and the levels with everything off at a position were read
# with the same instrument as the levels with a machine running.
METER = {"M-5": {63: 0.0, 125: 0.0, 250: 0.0, 500: 0.0, 1000: 0.0, 2000: 0.0, 4000: 0.0, 8000: 0.0},
         "M-2": {63: 0.0, 125: 0.0, 250: 0.0, 500: 0.0, 1000: 0.0, 2000: 0.1, 4000: 0.7, 8000: 2.4},
         "M-9": {63: 0.0, 125: 0.0, 250: 0.0, 500: 0.1, 1000: 0.1, 2000: 0.2, 4000: 1.1, 8000: 3.1}}
METER["M-7"] = {b: 0.0 for b in BANDS}          # the booked instrument, which needs no correction
METER_DAY = {"M-5": ("C4", "C5"), "M-2": ("C1", "C2", "C3"), "M-9": ("C6", "C7", "C8")}

# C7's lagging system came with a certified insertion loss, which is its configuration difference. It stands in the
# note column of the register, so the booking does not have to be spent on that machine.
CERTIFIED = "C7"

# The room check of the survey: a reference sound source of certified sound power, stood in the open part of the
# hall and measured on a hemisphere of RSS_R at the positions RSS_POS. It fixes the hall's equivalent absorption
# area band by band, so the booking does not have to be spent on a reverberation measurement.
RSS_LW = {63: 91.2, 125: 93.6, 250: 95.1, 500: 96.0, 1000: 96.3, 2000: 95.4, 4000: 93.7, 8000: 90.2}
RSS_R = 3.0
RSS_POS = ("R1", "R2", "R3", "R4", "R5", "R6")
RSS_DEV = (0.2, -0.3, 0.3, -0.2, 0.1, -0.1)
RSS_METER = "M-2"

NOMINAL_R = 3.0                                          # the register's nominal survey radius for every package
GUARANTEE = {"C1": 105.0, "C2": 102.0, "C3": 96.0, "C4": 98.0, "C5": 101.0, "C6": 93.0, "C7": 101.0,
             "C8": 98.0}                                 # the supplier's guaranteed A-weighted level


def _m(desc, r, space, wall, rated, survey_rpm, lw, sdelta):
    return dict(desc=desc, r=r, space=space, wall=wall, rated=rated, survey_rpm=survey_rpm, lw=lw, sdelta=sdelta,
                positions=[])


def _s(v):
    return dict(zip(BANDS, v))


# the eight packages as they stand now, and the configuration each was surveyed in. sdelta is the amount by which a
# band was higher when the survey measured it, for the two machines that were changed afterwards; for the rest the
# survey caught the machine as it stands, except for the speed its own pass ran at.
MACHINES = {
    "C1": _m("1250 kW centrifugal air compressor package", 3.0, "half", 4.2, 3600.0, 3600.0,
             _s([96.0, 98.0, 100.0, 102.0, 103.0, 101.0, 98.0, 93.0]),
             _s([2.5, 3.0, 4.0, 5.0, 5.5, 6.0, 5.5, 4.5])),      # the drive-end access cover stood open
    "C2": _m("900 kW screw compressor package", 3.0, "half", 3.8, 2950.0, 2508.0,
             _s([93.0, 95.0, 97.0, 99.0, 100.0, 98.0, 95.0, 90.0]), None),
    "C3": _m("600 kW blower package, against the east wall", 1.5, "quarter", 0.6, 3000.0, 3000.0,
             _s([92.0, 94.0, 95.0, 94.0, 93.0, 91.0, 88.0, 84.0]),
             _s([2.5, 4.0, 7.0, 8.0, 7.0, 5.0, 3.0, 2.5])),      # the intake silencer was not yet installed
    "C4": _m("450 kW screw compressor package", 3.0, "half", 5.0, 2970.0, 2970.0,
             _s([90.0, 92.0, 93.0, 94.0, 94.0, 92.0, 89.0, 85.0]), None),
    "C5": _m("710 kW centrifugal air compressor package", 3.0, "half", 4.6, 1800.0, 1500.0,
             _s([94.0, 96.0, 97.0, 98.0, 97.0, 95.0, 92.0, 87.0]), None),
    "C6": _m("300 kW blower package, against the north wall", 1.0, "quarter", 0.9, 3550.0, 3000.0,
             _s([88.0, 90.0, 91.0, 90.0, 89.0, 87.0, 84.0, 80.0]), None),
    "C7": _m("800 kW screw compressor package", 3.0, "half", 3.4, 2960.0, 2960.0,
             _s([92.0, 94.0, 96.0, 98.0, 99.0, 97.0, 94.0, 89.0]),
             _s([2.5, 3.5, 5.0, 6.0, 6.5, 6.0, 4.5, 3.0])),      # the discharge lagging was off
    "C8": _m("520 kW centrifugal air compressor package", 3.0, "half", 4.0, 2400.0, 2400.0,
             _s([91.0, 93.0, 94.0, 95.0, 95.0, 93.0, 90.0, 86.0]), None),
}

# each machine's array: the height in m, the bearing in degrees and the directivity deviation of the direct field in
# dB at each position, in the order the positions are numbered
ARRAY = {
    "C1": [(1.5, 0, 0.3), (1.5, 45, -0.2), (1.5, 90, 0.4), (1.5, 135, 0.0), (1.5, 180, -0.3), (1.5, 225, 0.2),
           (3.0, 270, -0.4), (3.0, 315, 0.1), (3.0, 20, 0.2), (3.0, 200, -0.3)],
    "C2": [(1.5, 0, 0.2), (1.5, 45, -0.3), (1.5, 90, 0.4), (1.5, 135, -0.1), (1.5, 180, 0.3), (1.5, 225, -0.4),
           (3.0, 270, 0.1), (3.0, 20, -0.2), (3.0, 315, 0.1), (3.0, 340, -0.2)],
    "C3": [(1.5, 0, 0.3), (1.5, 30, -0.4), (1.5, 60, 0.2), (1.5, 90, 0.0), (1.5, 120, -0.2), (1.5, 150, 0.4),
           (3.0, 180, -0.3), (3.0, 45, 0.2), (3.0, 135, -0.2)],
    "C4": [(1.5, 0, 0.2), (1.5, 45, -0.3), (1.5, 90, 0.3), (1.5, 135, -0.2), (1.5, 180, 0.4), (1.5, 225, -0.4),
           (3.0, 270, 0.1), (3.0, 315, -0.1), (3.0, 20, 0.2), (3.0, 200, -0.2)],
    "C5": [(1.5, 0, -0.2), (1.5, 45, 0.3), (1.5, 90, -0.3), (1.5, 135, 0.2), (1.5, 180, -0.4), (1.5, 225, 0.4),
           (3.0, 270, -0.1), (3.0, 315, 0.1), (3.0, 20, -0.2), (3.0, 200, 0.2)],
    "C6": [(1.5, 0, 0.2), (1.5, 30, -0.3), (1.5, 60, 0.4), (1.5, 90, -0.2), (1.5, 120, 0.1), (1.5, 150, -0.4),
           (3.0, 180, 0.3), (3.0, 45, -0.1), (3.0, 135, 0.0)],
    "C7": [(1.5, 0, 0.3), (1.5, 45, -0.2), (1.5, 90, 0.2), (1.5, 135, -0.3), (1.5, 180, 0.4), (1.5, 225, -0.4),
           (1.5, 270, 0.1), (3.0, 315, -0.1), (3.0, 20, 0.2), (3.0, 90, -0.2), (3.0, 340, 0.0)],
    "C8": [(1.5, 0, -0.3), (1.5, 45, 0.2), (1.5, 90, -0.2), (1.5, 135, 0.3), (1.5, 180, -0.4), (1.5, 225, 0.4),
           (3.0, 270, -0.1), (3.0, 315, 0.1), (3.0, 20, 0.2), (3.0, 200, -0.2)],
}
# positions the surveyor had to set at another radius, so that they are not on the measurement surface
OFF_SURFACE = {"P4": 0.60, "P65": 0.65}
# positions by the louvred east wall, where the adjacent bay's blower dominates two bands
NEAR_WALL = ("P19", "P20", "P68", "P69")
# the contractor's sheet enters four rows under the wrong machine: two of C1's array under C2 and two of C2's under
# C1. Both arrays were set at the same radius, so only the position table and the speed column give it away.
MISLABEL = {"P9": "C2", "P10": "C2", "P11": "C1", "P12": "C1"}


def _p(machine, r, height, arc, dev, valid, note):
    return dict(machine=machine, r=r, height=height, arc=arc, dev=dev, valid=valid, note=note)


def _build():
    """numbers the positions P1 upward, machine by machine, from ARRAY"""
    pos, n = {}, 0
    for m, j in MACHINES.items():
        for height, arc, dev in ARRAY[m]:
            n += 1
            pid = "P%d" % n
            r = OFF_SURFACE.get(pid, j["r"])
            note = ("set at %.2f m, not on the measurement surface" % r) if pid in OFF_SURFACE else (
                "by the louvred east wall" if pid in NEAR_WALL else "")
            pos[pid] = _p(m, r, height, arc, dev, pid not in OFF_SURFACE and pid not in NEAR_WALL, note)
            j["positions"].append(pid)
    return pos


POS = _build()
WALL = {m: j["wall"] for m, j in MACHINES.items()}
DAY_ONE = tuple(p for p, j in POS.items() if j["machine"] in METER_DAY["M-5"])
STATES = ("off",) + tuple(m.lower() for m in MACHINES) + ("all",)


def area(band, t60=None):
    """the hall's equivalent absorption area, m2"""
    return SOUND_C * ROOM["V"] / (t60 or T60)[band]


def surface(space, r):
    """the area of the measurement surface of radius r, m2"""
    return (2.0 * math.pi if space == "half" else math.pi) * r * r


def k2(m, band, t60=None):
    """the standard's environmental correction, dB"""
    j = MACHINES[m]
    return 10.0 * math.log10(1.0 + 4.0 * surface(j["space"], j["r"]) / area(band, t60))


def speed_referral(m):
    """the standard's referral of the survey's levels to the rated speed, dB"""
    j = MACHINES[m]
    return 50.0 * math.log10(j["rated"] / j["survey_rpm"])


def lw(m, band, config="now"):
    """the machine's sound power level in the band, as it is now or as it was surveyed"""
    j = MACHINES[m]
    v = j["lw"][band]
    if config == "survey":
        v += j["sdelta"][band] if j["sdelta"] else -speed_referral(m)
    return v


def lwa(m, config="now"):
    return 10.0 * math.log10(sum(10.0 ** (0.1 * (lw(m, b, config) + AW[b])) for b in BANDS))


def dev(pid):
    """the directivity factor of the direct field at the position, normalised to 1 over the machine's valid positions"""
    j = MACHINES[POS[pid]["machine"]]
    v = [10.0 ** (0.1 * POS[q]["dev"]) for q in j["positions"] if POS[q]["valid"]]
    return 10.0 ** (0.1 * POS[pid]["dev"]) / (sum(v) / len(v))


def lp_machine(m, pid, band, config="now"):
    """the sound pressure level at the position with that machine running alone, dB"""
    j = MACHINES[m]
    direct = dev(pid) / surface(j["space"], POS[pid]["r"])
    return lw(m, band, config) + 10.0 * math.log10(direct + 4.0 / area(band))


def rss_dev(pid):
    """the directivity factor at a room-check position, normalised to 1 over the six of them"""
    v = [10.0 ** (0.1 * d) for d in RSS_DEV]
    return 10.0 ** (0.1 * RSS_DEV[RSS_POS.index(pid)]) / (sum(v) / len(v))


def lp_rss(pid, band):
    """the sound pressure level at a room-check position with the reference source running"""
    direct = rss_dev(pid) / surface("half", RSS_R)
    return RSS_LW[band] + 10.0 * math.log10(direct + 4.0 / area(band))


def lp_rss_total(pid, band):
    """the level a room-check position read: the reference source and the hall's background"""
    return 10.0 * math.log10(10.0 ** (0.1 * lp_rss(pid, band)) + 10.0 ** (0.1 * (BG[band] + 0.0)))


def lab_rss(pid, rng):
    """the room check as the survey recorded it, as indicated by the instrument that read it"""
    return [round(lp_rss_total(pid, b) - METER[RSS_METER][b] + float(rng.normal(0.0, NOISE_SLM)), 1)
            for b in BANDS]


def lp_background(pid, band):
    """the level at the position with all three machines off: the hall's background and the adjacent bay's blower"""
    bl = BLOWER_NEAR if pid in NEAR_WALL else BLOWER_FAR
    return 10.0 * math.log10(10.0 ** (0.1 * BG[band]) + 10.0 ** (0.1 * bl[band]))


def lp_total(pids_state, pid, band, config="now"):
    """the level at the position with the machines of the state running, background included"""
    e = 10.0 ** (0.1 * lp_background(pid, band))
    for m in pids_state:
        e += 10.0 ** (0.1 * lp_machine(m, pid, band, config))
    return 10.0 * math.log10(e)


def state_machines(state):
    if state == "off":
        return ()
    return tuple(MACHINES) if state == "all" else (state.upper(),)


def meter_of(pid):
    """the instrument that read the position during the survey, from the pass the position belongs to"""
    m = POS[pid]["machine"]
    return next(name for name, machines in METER_DAY.items() if m in machines)


def lab_slm(pid, state, rng, config="now", survey=False):
    """one reading at the position: the eight band levels, dB to 0.1. With survey=True the reading is the survey's
    own, indicated by the instrument that read that position, so its certificate correction is still to be added."""
    out = []
    for b in BANDS:
        v = lp_total(state_machines(state), pid, b, config)
        if survey:
            v -= METER[meter_of(pid)][b]
        out.append(round(v + float(rng.normal(0.0, NOISE_SLM)), 1))
    return out


def lab_rt(pid, rng):
    """one reverberation time measurement at the position: the eight band values, s to 0.01"""
    return [round(T60[b] * float(np.exp(rng.normal(0.0, NOISE_RT))), 2) for b in BANDS]


def truth():
    """{machine: {band label: Lw}} with "A" for the A-weighted level"""
    out = {}
    for m in MACHINES:
        out[m] = {LABEL[b]: lw(m, b) for b in BANDS}
        out[m]["A"] = lwa(m)
    return out


def margins(m, values):
    """how far each submitted value is from the definition, dB (abs <= TOL passes)"""
    t = truth()[m]
    return {k: values[k] - t[k] for k in t}


def item_ok(m, k, value):
    return abs(value - truth()[m][k]) <= TOL
