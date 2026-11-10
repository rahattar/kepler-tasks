"""Sealed definition: twelve hubs shrink-fitted on steel shafts (plant standard ST-9).

The deliverable for each joint is the specified mean diametral interference (whole um) and the hub's oven temperature
(whole C). The shaft is ground to IT5 and the bore to IT6 about the mean, so the interference lies within
mean -/+ (IT5 + IT6) / 2. A joint is right when, as it is now:

1. torque: at the least interference, at rest (20 C, standing) and in steady running (the thermography temperatures,
   the running speed), the friction torque mu(p) p pi d^2 L / 2 is at least 1.5 x the peak torque;
2. hub stress: at the greatest interference, at rest and in steady running (with the hoop stress of the spinning
   hub), the von Mises stress at the hub bore is at most the yield strength / 1.2;
3. assembly: at the oven temperature the bore clears the shaft (at 20 C) by at least 0.001 d at the greatest
   interference, and the oven temperature is at most the hub's heating limit.

Contact pressure is Lame's for a hub on a solid or hollow shaft; the interference that acts is the geometric one less
the smoothing 0.8 (Rz_bore + Rz_shaft), and in running it changes by the free thermal growth of the hub bore and the
shaft (the mean expansion coefficient rises linearly with temperature) and by the centrifugal growth of hub and shaft.
Friction depends on the hub material and the surface preparation, falls with contact pressure as (p / 50 MPa)^-0.25,
and is lower in a pressed-in specimen than in a shrink-fitted one.

The joints as they are now differ from the records the agent is given in three places that the maintenance log
states: J07 is fitted with MoS2 paste (the assembly sheet still says oil), J10's shaft is hollow with a 40 mm bore (the
register still shows it solid), and J11's motor went from 55 to 75 kW (the duty list predates it). Tpeak and Re below
were set by authoring/provenance/tune.py from the design rules it states; it checks them against these values.
"""
import numpy as np

MAT = {  # E GPa, nu, density kg/m3, mean expansion coefficient from 20 C to T = a0 + a1 (T - 20), 1/K
    "steel": dict(E=210.0, nu=0.30, rho=7850.0, a0=11.64e-6, a1=0.00325e-6),
    "GJS": dict(E=174.0, nu=0.28, rho=7200.0, a0=10.8e-6, a1=0.0050e-6),
    "CuSn12": dict(E=95.0, nu=0.34, rho=8700.0, a0=17.6e-6, a1=0.0060e-6),
    "AlSi10Mg": dict(E=72.0, nu=0.33, rho=2680.0, a0=20.5e-6, a1=0.0080e-6),
}
KF = 0.25                  # friction falls with contact pressure as (p / 50 MPa)^-KF
MU50 = {("steel", "dry"): 0.165, ("steel", "oiled"): 0.105, ("steel", "paste"): 0.070,
        ("GJS", "dry"): 0.135, ("GJS", "oiled"): 0.092, ("GJS", "paste"): 0.062,
        ("CuSn12", "dry"): 0.125, ("CuSn12", "oiled"): 0.088, ("CuSn12", "paste"): 0.060,
        ("AlSi10Mg", "dry"): 0.120, ("AlSi10Mg", "oiled"): 0.085, ("AlSi10Mg", "paste"): 0.058}
PRESS_FACTOR = 0.72        # a pressed-in specimen slips at this fraction of the shrink-fitted value
BANDS = [50, 80, 120, 180, 250]          # IT grades (um) by diameter band (upper limit, mm)
IT5 = [11, 13, 15, 18, 20]
IT6 = [16, 19, 22, 25, 29]


def span(d):
    """total spread of the interference, mm"""
    for i, b in enumerate(BANDS):
        if d <= b:
            return (IT5[i] + IT6[i]) * 1e-3
    raise ValueError(d)


def cte(mat, T):
    m = MAT[mat]
    return m["a0"] + m["a1"] * (T - 20.0)


def lame_K(j):
    d, D, di = j["d"], j["D"], j["di"]
    h, s = MAT[j["hub"]], MAT["steel"]
    Ch = (D * D + d * d) / (D * D - d * d)
    Cs = (d * d + di * di) / (d * d - di * di) if di > 0 else 1.0
    return (Ch + h["nu"]) / (h["E"] * 1e3) + (Cs - s["nu"]) / (s["E"] * 1e3)     # 1/MPa


def pressure(j, de):
    """contact pressure (MPa) for an acting diametral interference de (mm)"""
    return max(de, 0.0) / (j["d"] * lame_K(j))


def smoothing(j):
    return 0.8 * (j["Rz_h"] + j["Rz_s"]) * 1e-3


def thermal_loss(j):
    """interference lost in steady running by the thermal growth of the bore over the shaft (negative: gained), mm"""
    return j["d"] * (cte(j["hub"], j["Th"]) * (j["Th"] - 20.0) - cte("steel", j["Ts"]) * (j["Ts"] - 20.0))


def centrifugal_loss(j):
    w = j["rpm"] * 2 * np.pi / 60.0
    b, c, a = j["d"] / 2e3, j["D"] / 2e3, j["di"] / 2e3
    h, s = MAT[j["hub"]], MAT["steel"]
    uh = h["rho"] * w * w * b / (4 * h["E"] * 1e9) * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b)
    us = s["rho"] * w * w * b / (4 * s["E"] * 1e9) * ((3 + s["nu"]) * a * a + (1 - s["nu"]) * b * b)
    return 2e3 * (uh - us)


def hoop_rot(j):
    """hoop stress at the bore of the hub spinning as a free disc, MPa"""
    w = j["rpm"] * 2 * np.pi / 60.0
    b, c = j["d"] / 2e3, j["D"] / 2e3
    h = MAT[j["hub"]]
    return h["rho"] * w * w / 4.0 * ((3 + h["nu"]) * c * c + (1 - h["nu"]) * b * b) / 1e6


def vm_bore(j, p, rot=0.0):
    Ch = (j["D"] ** 2 + j["d"] ** 2) / (j["D"] ** 2 - j["d"] ** 2)
    st, sr = p * Ch + rot, -p
    return float(np.sqrt(st * st - st * sr + sr * sr))


def mu(j, p, method="shrink", cond=None):
    return MU50[(j["hub"], cond or j["cond"])] * (max(p, 1.0) / 50.0) ** (-KF) * (PRESS_FACTOR if method == "press" else 1.0)


def states(j):
    """(name, change of acting interference in mm, hoop stress from rotation in MPa)"""
    return [("rest", 0.0, 0.0), ("running", -(thermal_loss(j) + centrifugal_loss(j)), hoop_rot(j))]


def tcap(j, de):
    p = pressure(j, de)
    return mu(j, p) * p * np.pi * j["d"] ** 2 * j["L"] / 2e3, p          # N m, MPa


def margins(jid, mean_um, T_heat, J=None):
    """relative margins of the three requirements (>= 0 passes) for a mean interference (um) and oven temperature"""
    j = (J or JOINTS)[jid]
    dmin = mean_um * 1e-3 - span(j["d"]) / 2
    dmax = mean_um * 1e-3 + span(j["d"]) / 2
    slip, stress, pp = float("inf"), float("inf"), None
    for _, dd, rot in states(j):
        Tc, p = tcap(j, dmin - smoothing(j) + dd)
        sl = Tc / (1.5 * max(j["Tpeak"], 1e-9)) - 1.0
        if sl < slip:
            slip, pp = sl, p
        pm = pressure(j, dmax - smoothing(j) + dd)
        stress = min(stress, (j["Re"] / 1.2) / max(vm_bore(j, pm, rot), 1e-9) - 1.0)
    clear = j["d"] * cte(j["hub"], T_heat) * (T_heat - 20.0) / (dmax + 0.001 * j["d"]) - 1.0
    limit = (j["Tlim"] - T_heat) / 20.0
    return dict(slip=slip, stress=stress, clear=clear, limit=limit, p=pp, mu=mu(j, pp))


def joint_ok(jid, mean_um, T_heat, J=None):
    m = margins(jid, mean_um, T_heat, J)
    return min(m["slip"], m["stress"], m["clear"], m["limit"]) >= 0, m


def fit_window(jid, J=None):
    """the whole-micrometre mean interferences that pass with the hub at its heating limit"""
    jj = (J or JOINTS)[jid]
    return [m for m in range(5, 900) if joint_ok(jid, m, jj["Tlim"], J)[0]]


def t_need(jid, mean_um, J=None):
    """lowest whole-degree oven temperature giving the clearance"""
    for T in range(20, 701):
        if margins(jid, mean_um, T, J)["clear"] >= 0:
            return T
    return None


def _j(desc, d, D, L, hub, cond, rpm, Th, Ts, Tpeak, Re, Tlim, di=0.0, Rz_h=4.0, Rz_s=2.5):
    return dict(desc=desc, d=d, D=D, L=L, hub=hub, cond=cond, rpm=rpm, Th=Th, Ts=Ts, Tpeak=Tpeak, Re=Re, Tlim=Tlim,
                di=di, Rz_h=Rz_h, Rz_s=Rz_s)


# d, D, L mm; hub; surface preparation as now; rpm; hub and shaft C in steady running; peak torque N m as now;
# yield strength MPa; heating limit C; shaft bore mm as now
JOINTS = {
    "J01": _j("pump coupling hub", 55, 85, 70, "steel", "dry", 2970, 60, 95, 1440.0, 390.0, 350),
    "J02": _j("fan hub", 90, 140, 110, "AlSi10Mg", "dry", 1480, 65, 55, 3780.0, 200.0, 190),
    "J03": _j("worm wheel", 110, 175, 90, "CuSn12", "oiled", 60, 55, 45, 2690.0, 160.0, 230),
    "J04": _j("gear hub", 150, 270, 160, "steel", "paste", 300, 70, 65, 24690.0, 490.0, 270),
    "J05": _j("brake drum hub", 75, 120, 90, "GJS", "dry", 980, 110, 60, 3390.0, 370.0, 300),
    "J06": _j("compressor impeller", 65, 150, 75, "steel", "dry", 5900, 90, 80, 4800.0, 480.0, 270),
    "J07": _j("crane wheel", 120, 190, 130, "GJS", "paste", 25, 40, 35, 5830.0, 250.0, 300),
    "J08": _j("flywheel", 180, 400, 200, "GJS", "dry", 740, 50, 45, 58170.0, 250.0, 300),
    "J09": _j("rolling-mill coupling", 220, 400, 240, "steel", "paste", 150, 55, 50, 87450.0, 530.0, 280),
    "J10": _j("conveyor pulley hub", 100, 150, 100, "steel", "oiled", 120, 35, 35, 6650.0, 345.0, 350, di=40.0),
    "J11": _j("gear on hollow shaft", 130, 200, 120, "steel", "dry", 600, 60, 55, 24700.0, 390.0, 350, di=70.0),
    "J12": _j("timing pulley", 45, 70, 50, "steel", "paste", 1480, 55, 85, 220.0, 345.0, 350),
}

# the laboratory
BUDGET = 8
NOISE_MU = 0.012           # relative scatter of a slip test (log-normal)
NOISE_CTE = 0.008          # relative scatter of a dilatometer reading (log-normal)
LABMAT = {"steel": "steel", "ductile-iron": "GJS", "bronze": "CuSn12", "aluminium": "AlSi10Mg"}
LAB_P = (10, 200)
LAB_T = (100, 400)


def lab_slip(mat, cond, p, shrink, rng):
    m = MU50[(mat, cond)] * (p / 50.0) ** (-KF) * (1.0 if shrink else PRESS_FACTOR)
    return round(m * float(np.exp(rng.normal(0, NOISE_MU))), 3)


def lab_cte(mat, T, rng):
    return round(cte(mat, T) * 1e6 * float(np.exp(rng.normal(0, NOISE_CTE))), 2)
