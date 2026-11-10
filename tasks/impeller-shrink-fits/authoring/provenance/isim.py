"""Sealed definition: six impellers, a balance drum and a thrust collar shrink-fitted on the rotor of a two-section
centrifugal compressor after an overhaul (plant standard RS-3).

The rotor's seats have been reground and measured; the spare parts come with undersized bores. The deliverable for
each part is the bore diameter to which it is finish-honed (mm, to 0.001, at 20 C) and its oven temperature (whole C).
The bore is honed to IT5 about the specified diameter, so the interference (true seat diameter at 20 C less the bore)
lies within the mean -/+ IT5 / 2. A part is right when, as the rotor is now:

1. retention: at the least interference, at rest (20 C, standing) and at trip speed in running (the thermal survey's
   temperatures), the contact pressure is at least 15 MPa and the fit carries twice the stage's torque at MCS with the
   standard's friction coefficient;
2. hub stress: at the greatest interference, at rest and at trip speed in running, the von Mises stress at the bore
   (contact pressure plus the hoop stress of rotation) is at most the yield strength / 1.2;
3. assembly: at the oven temperature the smallest bore clears the seat as the rotor stands in the overhaul bay
   (28.5 C) by at least 0.001 d, and the oven temperature is at most the part's heating limit.

Contact pressure is Lame's for a ring of the hub's outside diameter on the solid rotor; the interference that acts is
the geometric one less the smoothing 0.8 (Rz_bore + Rz_seat). In running it changes by the free thermal growth of
bore and seat (the mean expansion coefficient rises linearly with temperature) and by the centrifugal growth of the
bore less that of the seat. An impeller's bore growth and bore hoop stress are the OEM's spin-test values, scaled with
the square of speed from the spin-test speed (MCS, except S4's, at 10500 rpm); the drum and the collar are plain rings.
The rotor steel's mean expansion rises like the others', and its seats run at up to 190 C (S3).

The rotor as it is now differs from the agent's records in places the maintenance log states: the overspeed trip is
110 % of MCS (the OEM data sheet still gives 105 %), and the 5th-stage impeller is a titanium (Ti-6Al-4V) replacement
(the parts register still shows FV520B; its certificate and the OEM sheet's revision show the titanium part). The
seat diameters in the inspection report were measured in the overhaul bay at 28.5 C, with micrometers whose calibration
the report gives (the 100-125 mm instrument reads 4 um low). The S2 spare was recoated after it was certified: the log
gives its heating limit as 240 C (the certificate, 260 C). The balance drum's certificate gives the 42CrMo4 forging's
mill value of mean expansion to 250 C. Re, the heating limits and the OEM hoop stresses were set by
authoring/provenance/tune.py from the design rules it states; it checks them.
"""
import numpy as np

MAT = {  # E GPa, nu, density kg/m3, mean expansion coefficient from 20 C to T = a0 + a1 (T - 20) + a2 (T - 20)^2, 1/K
    "FV520B": dict(E=196.0, nu=0.29, rho=7800.0, a0=10.0801e-6, a1=0.0070770e-6, a2=-7.230e-12),
    "Ti64": dict(E=114.0, nu=0.34, rho=4430.0, a0=8.44e-6, a1=0.0020e-6),
    "42CrMo4": dict(E=210.0, nu=0.30, rho=7850.0, a0=11.64e-6, a1=0.0033e-6),
    "rotor": dict(E=206.0, nu=0.30, rho=7850.0, a0=10.76e-6, a1=0.0080e-6),
}
MU = {"FV520B": 0.15, "Ti64": 0.12, "42CrMo4": 0.15}      # the standard's design friction on rotor steel
P_MIN = 15.0               # MPa
T_BAY = 28.5               # C, the overhaul bay
MCS = 11200.0              # rpm
TRIP = 1.10                # x MCS, as set now
IT5 = [(80, 13), (120, 15), (180, 18)]
RZ_BORE = 3.2              # um, honed bores (standard)
MIC_ERR = -0.004           # mm, the 100-125 mm micrometer's calibration error (it reads low)


def band(d):
    for b, v in IT5:
        if d <= b:
            return v * 1e-3
    raise ValueError(d)


def cte(m, T):
    t = T - 20.0
    return MAT[m]["a0"] + MAT[m]["a1"] * t + MAT[m].get("a2", 0.0) * t * t


def seat_bay(j):
    return j["seat"] * (1.0 + cte("rotor", T_BAY) * (T_BAY - 20.0))


def micrometer(j):
    """the micrometer a seat was read with and its error (indication less true value, mm)"""
    return ("M-114", MIC_ERR) if j["d"] > 100 else ("M-113", 0.0)


def reading(j):
    """the seat diameter as read in the bay"""
    return seat_bay(j) + micrometer(j)[1]


def Ch(j):
    return (j["D"] ** 2 + j["d"] ** 2) / (j["D"] ** 2 - j["d"] ** 2)


def K(j):
    h, s = MAT[j["mat"]], MAT["rotor"]
    return (Ch(j) + h["nu"]) / (h["E"] * 1e3) + (1.0 - s["nu"]) / (s["E"] * 1e3)


def pressure(j, de):
    return max(de, 0.0) / (j["d"] * K(j))


def smoothing(j):
    return 0.8 * (RZ_BORE + j["Rz_s"]) * 1e-3


def omega(f):
    return MCS * f * 2 * np.pi / 60.0


def seat_growth(j, f):
    s = MAT["rotor"]
    w, b = omega(f), j["d"] / 2e3
    return 2e3 * s["rho"] * w * w * b ** 3 * (1 - s["nu"]) / (4 * s["E"] * 1e9)


def ring_growth(j, f):
    h = MAT[j["mat"]]
    w, b, c = omega(f), j["d"] / 2e3, j["D"] / 2e3
    return 2e3 * h["rho"] * w * w * b / (4 * h["E"] * 1e9) * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b)


def ring_hoop(j, f):
    h = MAT[j["mat"]]
    w, b, c = omega(f), j["d"] / 2e3, j["D"] / 2e3
    return h["rho"] * w * w / 4.0 * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b) / 1e6


def spin_scale(j):
    """(speed / spin-test speed)^2 at MCS"""
    return (MCS / j.get("spin", MCS)) ** 2


def bore_growth(j, f):
    return j["g_mcs"] * 1e-3 * f * f * spin_scale(j) if j["g_mcs"] else ring_growth(j, f)


def bore_hoop(j, f):
    return j["h_mcs"] * f * f * spin_scale(j) if j["h_mcs"] else ring_hoop(j, f)


def thermal_change(j):
    """change of interference in running from the temperatures, mm (positive: gained)"""
    return -j["d"] * (cte(j["mat"], j["Th"]) * (j["Th"] - 20.0) - cte("rotor", j["Ts"]) * (j["Ts"] - 20.0))


def states(j):
    """(name, change of acting interference in mm, hoop stress of rotation at the bore in MPa)"""
    run = thermal_change(j) - (bore_growth(j, TRIP) - seat_growth(j, TRIP))
    return [("rest", 0.0, 0.0), ("trip", run, bore_hoop(j, TRIP))]


def vm_bore(j, p, rot):
    st, sr = p * Ch(j) + rot, -p
    return float(np.sqrt(st * st - st * sr + sr * sr))


def stage_torque(j):
    return j["P_kW"] * 1e3 / omega(1.0)


def margins(pid, bore_mm, T_oven, J=None):
    """relative margins (>= 0 passes) for a specified bore (mm at 20 C) and oven temperature"""
    j = (J or PARTS)[pid]
    mean = j["seat"] - bore_mm
    dmin, dmax = mean - band(j["d"]) / 2, mean + band(j["d"]) / 2
    ret, stress = float("inf"), float("inf")
    for _, dd, rot in states(j):
        p = pressure(j, dmin - smoothing(j) + dd)
        r = p / P_MIN - 1.0
        if j["P_kW"] > 0:
            r = min(r, MU[j["mat"]] * p * np.pi * j["d"] ** 2 * j["L"] / 2e3 / (2.0 * stage_torque(j)) - 1.0)
        ret = min(ret, r)
        pm = pressure(j, dmax - smoothing(j) + dd)
        stress = min(stress, (j["Re"] / 1.2) / vm_bore(j, pm, rot) - 1.0)
    bmin = bore_mm - band(j["d"]) / 2
    clear = (bmin * (1.0 + cte(j["mat"], T_oven) * (T_oven - 20.0)) - seat_bay(j)) / (0.001 * j["d"]) - 1.0
    limit = (j["Tlim"] - T_oven) / 20.0
    return dict(ret=ret, stress=stress, clear=clear, limit=limit)


def part_ok(pid, bore_mm, T_oven, J=None):
    m = margins(pid, bore_mm, T_oven, J)
    return min(m.values()) >= 0, m


def window(pid, J=None):
    """the mean interferences (whole um below the seat at 20 C) that pass with the oven at the heating limit"""
    j = (J or PARTS)[pid]
    return [um for um in range(1, 700) if part_ok(pid, round(j["seat"] - um * 1e-3, 3), j["Tlim"], J)[0]]


def _p(desc, d, seat, D, L, mat, Th, Ts, Tlim, Re, g_mcs, h_mcs, P_kW, Rz_s):
    return dict(desc=desc, d=d, seat=seat, D=D, L=L, mat=mat, Th=Th, Ts=Ts, Tlim=Tlim, Re=Re, g_mcs=g_mcs,
                h_mcs=h_mcs, P_kW=P_kW, Rz_s=Rz_s)


# desc; nominal d; true seat diameter at 20 C (mm); hub outside diameter; hub length; material as now; hub and seat
# C in running; heating limit C; yield MPa; OEM bore growth at MCS (um, diametral) and bore hoop stress at MCS (MPa)
# for impellers (None: plain ring); stage power kW (0: no stage torque); seat Rz um
PARTS = {
    "S1": _p("1st stage impeller", 115, 115.212, 190, 80, "FV520B", 60, 50, 400, 890.0, 104, 550.0, 1650, 1.6),
    "S2": _p("2nd stage impeller", 120, 120.218, 195, 80, "FV520B", 95, 75, 240, 905.0, 77, 532.0, 1600, 1.6),
    "S3": _p("3rd stage impeller", 125, 125.224, 200, 78, "FV520B", 150, 190, 400, 880.0, 96, 538.0, 1550, 1.6),
    "S4": dict(_p("4th stage impeller", 125, 125.207, 200, 78, "FV520B", 60, 95, 400, 895.0, 84, 485.0, 1500, 1.6),
               spin=10500.0),
    "S5": _p("5th stage impeller", 120, 120.211, 195, 80, "Ti64", 140, 135, 285, 860.0, 101, 524.0, 1450, 1.6),
    "S6": _p("6th stage impeller", 115, 115.226, 190, 80, "FV520B", 175, 165, 375, 885.0, 252, 520.0, 1400, 1.6),
    "BD": _p("balance drum", 110, 110.205, 252, 150, "42CrMo4", 190, 180, 220, 650.0, None, None, 0, 1.6),
    "TC": _p("thrust collar", 95, 95.161, 208, 40, "42CrMo4", 70, 75, 190, 700.0, None, None, 0, 1.6),
}

# the laboratory: a dilatometer
BUDGET = 3
NOISE_CTE = 0.003
LABMAT = {"FV520B": "FV520B", "Ti-6Al-4V": "Ti64", "42CrMo4": "42CrMo4", "26NiCrMoV14-5": "rotor"}
LAB_T = (100, 450)


def lab_cte(mat, T, rng):
    return round(cte(mat, T) * 1e6 * float(np.exp(rng.normal(0, NOISE_CTE))), 2)
