"""Sealed definitions of the welded joints.

A joint: two plates (mark, grade, heat, thickness, and the plate's own product analysis when its certificate gives
one), the runs as welded (process, consumable batch, true current and voltage or the true pulse waveform, travel speed,
start time), the consumables (batch certificates, the true moisture pick-up of each electrode type), the electrodes'
handling (issue to a heated or unheated quiver, rebaking), the shop climate over the day, and the shop's work log
(a plate replaced, an arc monitor recalibrated, a wire spool changed).

The truth of a joint (truth()) is MS-PH's minimum preheat for the joint as it was welded: the plates in the joint
(after any replacement), each plate's composition (its product analysis, or its heat's cast analysis), every run's true
heat input (true arc power, travel speed and process efficiency) and true diffusible hydrogen (the batch actually used,
its certificate value and the true moisture pick-up of its exposure), and the capping runs for the HAZ hardness."""
import math
import numpy as np
import weld as W

# covered electrodes' true moisture pick-up, ml/100 g per kPa h of exposure (water vapor pressure x hours)
PICKUP = {"E 42 4 B 42 H5": 0.42, "E 46 5 1Ni B 32 H5": 0.31}
DESIG = {"E": ("111", "E 42 4 B 42 H5"), "N": ("111", "E 46 5 1Ni B 32 H5"), "F": ("136", "T 46 4 P M21 1 H10"),
         "B": ("136", "T 42 4 B M21 3 H5"), "G": ("135", "G 42 4 M21 3Si1"), "T": ("141", "W 46 5 W3Si1")}

E0 = ("C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "V", "Nb", "Ti")


def comp(C, Si, Mn, Cr, Mo, Ni, Cu, V, Nb=0.02, P=0.012, S=0.004, Ti=0.002):
    return dict(C=C, Si=Si, Mn=Mn, P=P, S=S, Cr=Cr, Mo=Mo, Ni=Ni, Cu=Cu, V=V, Nb=Nb, Ti=Ti)


# the heats on the shop's certificates: grade and cast analysis
HEATS = {
    "84213": ("S355J2+N", comp(0.150, 0.30, 1.42, 0.06, 0.02, 0.05, 0.10, 0.004)),
    "84390": ("S355J2+N", comp(0.162, 0.28, 1.48, 0.10, 0.03, 0.10, 0.18, 0.005)),
    "84477": ("S355J2+N", comp(0.178, 0.35, 1.52, 0.14, 0.04, 0.16, 0.24, 0.006)),
    "84520": ("S355J2+N", comp(0.135, 0.25, 1.40, 0.05, 0.02, 0.04, 0.10, 0.003)),
    "71502": ("S355ML", comp(0.085, 0.30, 1.45, 0.04, 0.01, 0.22, 0.12, 0.040, Nb=0.03)),
    "71588": ("S355ML", comp(0.105, 0.38, 1.50, 0.06, 0.02, 0.25, 0.15, 0.050, Nb=0.03)),
    "65110": ("S460ML", comp(0.085, 0.40, 1.62, 0.10, 0.10, 0.45, 0.20, 0.060, Nb=0.04)),
    "65174": ("S460ML", comp(0.100, 0.42, 1.65, 0.20, 0.12, 0.55, 0.25, 0.070, Nb=0.04)),
    "92031": ("S420NL", comp(0.140, 0.35, 1.58, 0.10, 0.05, 0.30, 0.15, 0.060, Nb=0.03)),
    "92077": ("S420NL", comp(0.148, 0.40, 1.62, 0.10, 0.06, 0.30, 0.18, 0.060, Nb=0.03)),
    "84601": ("S355J2+N", comp(0.185, 0.30, 1.55, 0.10, 0.03, 0.10, 0.22, 0.005)),
    "84655": ("S355J2+N", comp(0.156, 0.30, 1.46, 0.08, 0.02, 0.08, 0.15, 0.005)),
}

# consumable batches: (kind letter, certificate diffusible hydrogen ml/100 g)
BATCHES = {
    "E-7781": ("E", 3.6), "E-7802": ("E", 4.2), "E-7655": ("E", 2.6), "E-7840": ("E", 2.7),
    "N-2210": ("N", 3.1), "N-2234": ("N", 3.4),
    "F-1980": ("F", 5.8), "F-2207": ("F", 8.6), "F-2015": ("F", 6.2), "F-2240": ("F", 9.1),
    "B-3312": ("B", 3.5), "B-3340": ("B", 4.0),
    "G-1190": ("G", 1.8), "G-1215": ("G", 2.2),
    "T-0412": ("T", 1.5), "T-0430": ("T", 1.7),
}


def plate(mark, heat, d, product=None):
    """product: the plate's product analysis as changes to its heat's cast analysis (absolute values)."""
    grade, cast = HEATS[heat]
    p = dict(cast)
    if product:
        p.update(product)
    return dict(mark=mark, heat=heat, grade=grade, d=d, product=p if product else None, comp=p)


def run(kind, batch, I, U, v_mm_min, n=1, pulse=None, at=None):
    """pulse: (Ip, Ib, Up, Ub, duty) of a waveform-controlled run; I and U are then ignored. at: start time (HH:MM)
    of the first of these runs, after a break."""
    return dict(kind=kind, batch=batch, I=I, U=U, v=v_mm_min, n=n, pulse=pulse, at=at)


def J(name, seed, date, station, monitor, length, plates, runs, nominal, start="07:40", gap=6.0, issue=None,
      rebake=None, replaced=None, calib=None, spool=None, climate=(14.0, 25.0, 82.0, 50.0), speed_scatter=0.04,
      issued=None, foreign=None, sister=None, others=None, heat_fix=None):
    """issue: {batch: (time, heated)} electrode issue to the welder's quiver; rebake: (batch, time returned to the oven,
    time reissued); replaced: (plate index, new plate, time) a plate rejected and replaced after the joint sheet was
    issued; calib: (time, factor) the monitor's current reading was factor x true before its recalibration at time;
    spool: (time, new batch) a wire spool of another batch fitted on the station; climate: (T at 06:00, T at 15:00,
    RH at 06:00, RH at 15:00) of the station's bay; issued: {joint sheet's batch: batch the oven issued instead};
    foreign: runs of another joint at the station that day, (joint number, kind, process, I, U, v mm/min, length,
    start, n); sister: (heat, plate mark, product analysis) of another plate of a joint plate's heat; others: other
    stations' electrode events, (station, batch, issue time, heated, return time); heat_fix: {plate index: heat} a
    plate the joint sheet gives the wrong heat for (its certificate and the fit-up check give the heat)."""
    rng = np.random.default_rng(seed)
    t = hm(start)
    runs_out = []
    k = 0
    for r in runs:
        if r["at"]:
            t = hm(r["at"])
        for _ in range(r["n"]):
            k += 1
            batch = (issued or {}).get(r["batch"], r["batch"])
            if spool and t >= hm(spool[0]) and DESIG[BATCHES[batch][0]][0] == DESIG[BATCHES[spool[1]][0]][0]:
                batch = spool[1]
            v = r["v"] * (1 + speed_scatter * rng.standard_normal())
            arc = length / (v / 60)                               # s
            runs_out.append(dict(no=k, kind=r["kind"], batch=batch, sheet_batch=r["batch"],
                                 process=DESIG[BATCHES[batch][0]][0], I=r["I"], U=r["U"], v=v, arc=arc,
                                 start=t, pulse=r["pulse"]))
            t += arc / 60 + gap * (0.7 + 0.6 * rng.random())
    fruns, count = [], {}
    for jno, kind, proc, I, U, v0, L, t0, n in (foreign or []):
        tf = hm(t0)
        for k2 in range(n):
            v = v0 * (1 + speed_scatter * rng.standard_normal())
            arc = L / (v / 60)
            count[jno] = count.get(jno, 0) + 1
            fruns.append(dict(joint=jno, no=count[jno], kind=kind, process=proc, I=I, U=U, v=v, arc=arc, start=tf, L=L))
            tf += arc / 60 + gap * (0.7 + 0.6 * rng.random())
    pl = list(plates)
    for i, h in (heat_fix or {}).items():
        pl[i] = plate(plates[i]["mark"], h, plates[i]["d"])
    if replaced:
        pl[replaced[0]] = replaced[1]
    return dict(name=name, seed=seed, date=date, station=station, monitor=monitor, length=length, plates=pl,
                sheet_plates=list(plates), runs=runs_out, nominal=nominal, issue=issue or {}, rebake=rebake,
                replaced=replaced, calib=calib, spool=spool, climate=climate, foreign=fruns, sister=sister,
                others=others, issued=issued or {}, heat_fix=heat_fix or {})


BAY = {"WS-1": "B1", "WS-2": "B1", "WS-3": "B2", "WS-4": "B2"}
# loop resistance (ohm) of the welding and return cables of the monitors that sense voltage at the power source
LOOP = {"M3": 0.015, "M4": 0.018}


def other_bay(j):
    """The climate of the other bay: bay 1 is drier (its doors stay shut), bay 2 more humid (next to the wash bay)."""
    T6, T15, R6, R15 = j["climate"]
    if BAY[j["station"]] == "B2":
        return (T6 - 1.0, T15 - 1.5, 0.48 * R6, 0.48 * R15)
    return (T6 - 0.5, T15 - 1.0, min(R6 + 10, 95), R15 + 14)


def hm(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def climate_at(j, minutes, clim=None):
    """The true shop air temperature and relative humidity at a time of day (minutes) in the joint's bay (or for the
    climate clim): a smooth rise from 06:00 to 15:00 and a slow fall after it."""
    T6, T15, R6, R15 = clim or j["climate"]
    if minutes <= 360:
        x = 0.0
    elif minutes <= 900:
        x = 0.5 * (1 - math.cos(math.pi * (minutes - 360) / 540))
    else:
        x = max(1 - 0.35 * (minutes - 900) / 540, 0.0)
    return T6 + (T15 - T6) * x, R6 + (R15 - R6) * x


def exposure(j, t0, t1):
    """True exposure (kPa h) between two times of day (minutes)."""
    if t1 <= t0:
        return 0.0
    ts = np.linspace(t0, t1, 400)
    p = [W.vapor_kpa(*climate_at(j, x)) for x in ts]
    return float(np.trapezoid(p, ts) / 60)


def pulse_power(p):
    """True mean instantaneous power and mean current and voltage of a pulse waveform: rectangular pulses with linear
    ramps of 8 percent of the period on each side."""
    Ip, Ib, Up, Ub, duty = p
    s = np.linspace(0, 1, 20001)[:-1]
    I, U = pulse_shape(s, p)
    return float(np.mean(I * U)), float(np.mean(I)), float(np.mean(U))


def pulse_shape(s, p):
    Ip, Ib, Up, Ub, duty = p
    r = 0.08
    f = np.clip(np.minimum(s / r, (duty + r - s) / r), 0, 1)       # 0 at base, 1 at peak
    f = np.where(s < duty + r, f, 0.0)
    return Ib + (Ip - Ib) * f, Ub + (Up - Ub) * f


def run_truth(j, r, route=()):
    """(heat input kJ/mm, diffusible hydrogen ml/100 g) of a run as welded. route: defects to apply, for the route
    study: "pulse" (mean current x mean voltage of a pulsed run), "calib" (the uncorrected monitor current), "spool"
    (the joint sheet's batch), "exposure" (no moisture pick-up), "rebake" (exposure from the first issue), "nominal"
    (the WPS's nominal current, voltage and travel speed)."""
    if "nominal" in route:
        proc, I, U, v = j["nominal"][r["kind"]]
        P, v = I * U, v
    elif r["pulse"]:
        P, Im, Um = pulse_power(r["pulse"])
        if "pulse" in route:
            P = Im * Um
        v = r["v"]
    else:
        P, v = r["I"] * r["U"], r["v"]
    if "calib" in route and j["calib"] and r["start"] < hm(j["calib"][0]):
        P *= j["calib"][1]
    smaw = DESIG[BATCHES[r["batch"]][0]][0] == "111"
    batch = r["sheet_batch"] if (("spool" in route and not smaw) or ("issued" in route and smaw)) else r["batch"]
    Q = W.heat_input(r["process"], P, v / 60)
    kind, HD0 = BATCHES[batch]
    HD = HD0
    desig = DESIG[kind][1]
    if desig in PICKUP and "exposure" not in route and not ("issued" in route and batch != r["batch"]):
        HD += PICKUP[desig] * exposure(j, *exposure_window(j, r, first="rebake" in route))
    return Q, HD


def exposure_window(j, r, first=False):
    """The run's electrodes' time in an unheated quiver, up to the start of the run (minutes)."""
    t_issue, heated = j["issue"][r["batch"]]
    t0 = hm(t_issue)
    if j["rebake"] and j["rebake"][0] == r["batch"] and not first:
        if r["start"] >= hm(j["rebake"][2]):
            t0 = hm(j["rebake"][2])
    if heated:
        return (0, 0)
    return (t0, r["start"])


def truth(j, **kw):
    return assess_true(j, **kw)[0]


def assess_true(j, hard_runs=("cap",), mode="max", route=(), plates=None, cast=False, hydrogen=True, hardness=True):
    out = []
    QH = [run_truth(j, r, route) + (r["kind"],) for r in j["runs"]]
    for p in (plates or j["plates"]):
        c = HEATS[p["heat"]][1] if cast else p["comp"]
        CET, CE = W.cet(c), W.ceb(c)
        th = max(W.tp_hydrogen(CET, p["d"], HD, Q) for Q, HD, _ in QH) if hydrogen else -273
        caps = [Q for Q, _, k in QH if k in hard_runs]
        tk = W.tp_hardness(c["C"], CE, p["d"], caps, mode=mode) if hardness else -273
        out.append((th, tk))
    return max(max(a, b) for a, b in out), out, QH


EXAMPLE = "joint-ex"
NOM = dict(E=dict(root=("111", 110, 22, 95), fill=("111", 165, 23, 165), cap=("111", 160, 23, 170)),
           TGG=dict(root=("141", 115, 11.5, 70), fill=("135", 240, 27, 330), cap=("135", 175, 25, 340)),
           EFE=dict(root=("111", 110, 22, 95), fill=("136", 220, 26, 300), cap=("111", 160, 23, 170)),
           TFF=dict(root=("141", 115, 11.5, 70), fill=("136", 220, 26, 300), cap=("136", 200, 25, 300)),
           EGG=dict(root=("111", 110, 22, 95), fill=("135", 240, 27, 330), cap=("135", 175, 25, 340)),
           EBE=dict(root=("111", 110, 22, 95), fill=("136", 230, 26, 320), cap=("111", 160, 23, 170)))
PULSE = (440, 70, 34.0, 20.0, 0.32)
JOINTS = [
    # clean: S355 40 mm, SMAW throughout, electrodes in heated quivers, one heat per plate, cast analyses only
    J("joint-ex", 1, "2026-03-11", "WS-1", "M1", 1200,
      [plate("P-4410", "84213", 40), plate("P-4415", "84520", 40)],
      [run("root", "E-7781", 110, 22, 92), run("fill", "E-7781", 168, 23, 160, n=7), run("cap", "E-7781", 160, 23, 150, n=4)],
      NOM["E"], issue={"E-7781": ("07:20", True)}),
    # FCAW spool changed to a higher-hydrogen batch; product analysis on a plate; heated quivers
    J("girder-flange", 11, "2026-04-14", "WS-2", "M2", 1500,
      [plate("P-5521", "84390", 32, product=dict(C=0.172, Mn=1.57, Cu=0.22)), plate("P-5526", "84213", 32)],
      [run("root", "E-7802", 112, 22, 96), run("fill", "F-1980", 222, 26, 305, n=6), run("cap", "E-7802", 162, 23, 122, n=4)],
      NOM["EFE"], issue={"E-7802": ("06:50", True)}, spool=("08:30", "F-2207"),
      foreign=[("J-2115", "root", "136", 205, 25, 280, 600, "10:55", 1), ("J-2115", "cap", "136", 200, 25, 360, 600, "11:10", 2)]),
    # a plate replaced by a thicker plate of a richer heat; TIG root, MAG fill, pulsed MAG cap
    J("tank-course", 12, "2026-04-21", "WS-3", "M3", 1300,
      [plate("P-6102", "84213", 14), plate("P-6107", "84520", 14)],
      [run("root", "T-0412", 118, 11.5, 66), run("fill", "G-1190", 245, 27, 320, n=5), run("cap", "G-1190", 0, 0, 238, n=3, pulse=PULSE)],
      NOM["TGG"], replaced=(1, plate("P-6190", "84477", 16), "06:55"),
      foreign=[("J-2171", "fill", "135", 240, 27, 330, 500, "06:40", 1), ("J-2171", "cap", "135", 180, 24, 380, 500, "06:50", 2)]),
    # S460ML; product analysis; the monitor's current read 8 percent high until its recalibration
    J("boom-chord", 13, "2026-05-05", "WS-1", "M1", 1400,
      [plate("P-7301", "65110", 16), plate("P-7304", "65174", 16, product=dict(C=0.116, Mn=1.70))],
      [run("root", "N-2210", 110, 22, 94), run("fill", "B-3312", 230, 26, 318, n=7), run("cap", "N-2210", 158, 23, 150, n=4)],
      NOM["EBE"], issue={"N-2210": ("07:05", True)}, calib=("15:30", 1.08)),
    # SMAW throughout, unheated quiver, rebaked mid-joint
    J("column-splice", 14, "2026-05-19", "WS-4", "M4", 1100,
      [plate("P-8020", "92031", 32), plate("P-8026", "92077", 32)],
      [run("root", "E-7655", 108, 22, 94), run("fill", "E-7655", 166, 23, 162, n=8), run("cap", "E-7655", 160, 23, 115, n=4)],
      NOM["E"], start="10:10", issue={"E-7802": ("06:20", False)}, rebake=("E-7802", "09:20", "10:00"), issued={"E-7655": "E-7802"},
      others=[("WS-2", "E-7802", "10:35", True, "15:10")],
      climate=(22.0, 32.0, 90.0, 72.0)),
    # thin S355ML: a plate replaced by one of a richer heat; FCAW spool changed
    J("hopper-wall", 15, "2026-06-02", "WS-2", "M2", 1600,
      [plate("P-9105", "71502", 15), plate("P-9111", "71502", 15)],
      [run("root", "T-0430", 116, 11.5, 68), run("fill", "F-2015", 218, 26, 300, n=3), run("cap", "F-2015", 205, 25, 290, n=3)],
      NOM["TFF"], replaced=(1, plate("P-9190", "71588", 20), "07:05"), spool=("08:40", "F-2240"),
      sister=("71588", "P-9191", dict(C=0.128, Mn=1.63, Cu=0.24, Ni=0.34))),
    # pulsed MAG cap; the monitor's current read 7 percent high until its recalibration
    J("frame-web", 16, "2026-06-16", "WS-3", "M3", 1250,
      [plate("P-9402", "84390", 22), plate("P-9406", "84213", 22)],
      [run("root", "E-7840", 110, 22, 95), run("fill", "G-1215", 242, 27, 330, n=5), run("cap", "G-1215", 0, 0, 310, n=3, pulse=PULSE)],
      NOM["EGG"], issue={"E-7840": ("07:00", True)}, calib=("13:00", 1.07),
      sister=("84213", "P-9407", dict(C=0.184, Mn=1.53, Cr=0.12)), heat_fix={0: "84655"}),
    # unheated quiver with a rebake; product analysis; basic FCAW fill
    J("deck-plate", 17, "2026-06-30", "WS-4", "M4", 1350,
      [plate("P-9710", "84520", 40), plate("P-9715", "92031", 40, product=dict(C=0.147, Mn=1.73))],
      [run("root", "E-7840", 110, 22, 96), run("fill", "E-7840", 166, 23, 160, n=6), run("cap", "E-7840", 158, 23, 125, n=3, at="13:20")],
      NOM["E"], start="07:00", gap=9.0, issue={"E-7781": ("06:10", False)}, rebake=("E-7781", "12:05", "12:50"), issued={"E-7840": "E-7781"},
      others=[("WS-1", "E-7781", "08:40", True, "14:30")],
      climate=(21.0, 31.0, 92.0, 76.0), heat_fix={0: "84601"}),
]
BY = {j["name"]: j for j in JOINTS}
HIDDEN = [j["name"] for j in JOINTS if j["name"] != EXAMPLE]
