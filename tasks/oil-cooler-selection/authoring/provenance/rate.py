"""Shell-and-tube cooler rating: oil on the shell side (Bell-Delaware, Taborek), cooling water in the tubes
(Gnielinski), 1-N shells in series. Sealed copy of the plant rating standard, also used by the verifier.
"""
import math

import numpy as np

# Taborek ideal-bank coefficients: per layout, rows of (Re_min, a1, a2, b1, b2); and (a3, a4, b3, b4)
COEF = {
    30: ([(1e4, 0.321, -0.388, 0.372, -0.123), (1e3, 0.321, -0.388, 0.486, -0.152), (1e2, 0.593, -0.477, 4.570, -0.476),
          (10, 1.360, -0.657, 45.10, -0.973), (0, 1.400, -0.667, 48.00, -1.000)], (1.450, 0.519, 7.00, 0.500)),
    90: ([(1e4, 0.370, -0.396, 0.391, -0.148), (1e3, 0.107, -0.266, 0.0815, 0.022), (1e2, 0.408, -0.460, 6.0900, -0.602),
          (10, 0.900, -0.631, 32.10, -0.963), (0, 0.970, -0.667, 35.00, -1.000)], (1.187, 0.370, 6.30, 0.378)),
}
K_WALL = 45.0          # carbon steel tubes, W/m K


def walther_nu(T, nu40, nu100):
    """Kinematic viscosity (cSt) by ASTM D341 (Walther) through two points."""
    def z(nu):
        return math.log10(math.log10(nu + 0.7))
    t1, t2 = math.log10(313.15), math.log10(373.15)
    B = (z(nu40) - z(nu100)) / (t2 - t1)
    A = z(nu40) + B * t1
    zz = A - B * math.log10(T + 273.15)
    return 10 ** (10 ** zz) - 0.7


def oil_props(T, oil):
    rho = oil["rho15"] * (1 - 0.00065 * (T - 15.0))
    cp = 1000.0 * (1.80 + 0.0036 * T)
    k = 0.134 - 0.00007 * T
    mu = walther_nu(T, oil["nu40"], oil["nu100"]) * 1e-6 * rho
    return rho, cp, k, mu


def water_props(T):
    rho = 1000.6 - 0.0128 * T ** 1.76
    cp = 4180.0
    k = 0.569 + 0.00188 * T - 7.5e-6 * T * T
    mu = 2.414e-5 * 10 ** (247.8 / (T + 273.15 - 140.0))
    return rho, cp, k, mu


def geometry(d):
    do = d["tube_od_mm"] / 1000.0
    di = do - 2 * d["tube_wall_mm"] / 1000.0
    Ds = d["shell_id_mm"] / 1000.0
    Pt = d["pitch_mm"] / 1000.0
    Lbc = d["baffle_spacing_mm"] / 1000.0
    Bc = d["baffle_cut_pct"] / 100.0
    lay = d["layout_deg"]
    Nt = d["tubes"]
    Lsb = (3.1 + 0.004 * d["shell_id_mm"]) / 1000.0     # shell-to-baffle diametral clearance (TEMA)
    Ltb = 0.8 / 1000.0                                  # tube-to-baffle-hole diametral clearance
    Lbb = (12.0 + 0.005 * d["shell_id_mm"]) / 1000.0    # bundle-to-shell diametral clearance (fixed tubesheet)
    Dotl = Ds - Lbb
    Dctl = Dotl - do
    Pp = Pt * (math.cos(math.radians(30)) if lay == 30 else 1.0)
    Ppeff = Pt
    Sm = Lbc * (Lbb + Dctl / Ppeff * (Pt - do))
    tds = 2 * math.acos(1 - 2 * Bc)
    tctl = 2 * math.acos(Ds / Dctl * (1 - 2 * Bc))
    Fw = tctl / (2 * math.pi) - math.sin(tctl) / (2 * math.pi)
    Fc = 1 - 2 * Fw
    Swg = Ds * Ds / 4 * (tds / 2 - math.sin(tds) / 2)
    Swt = Nt * Fw * math.pi * do * do / 4
    Sw = Swg - Swt
    Ssb = math.pi * Ds * Lsb / 2 * (1 - tds / (2 * math.pi))
    Stb = math.pi / 4 * ((do + Ltb) ** 2 - do * do) * Nt * (1 - Fw)
    Sb = Lbc * (Ds - Dotl)
    Ntcc = Ds / Pp * (1 - 2 * Bc)
    Ntcw = 0.8 / Pp * (Ds * Bc - (Ds - Dctl) / 2)
    L = d["tube_length_m"]
    Nb = max(1, int(round(L / Lbc)) - 1)
    return dict(do=do, di=di, Ds=Ds, Pt=Pt, Lbc=Lbc, Nt=Nt, Sm=Sm, Sw=Sw, Fw=Fw, Fc=Fc, Ssb=Ssb, Stb=Stb, Sb=Sb, tds=tds,
                Ntcc=Ntcc, Ntcw=Ntcw, Nb=Nb, L=L, lay=lay)


def shell_side(g, m, T, Tw, oil):
    rho, cp, k, mu = oil_props(T, oil)
    muw = oil_props(Tw, oil)[3]
    Re = g["do"] * m / (mu * g["Sm"])
    rows, (a3, a4, b3, b4) = COEF[g["lay"]]
    for Rmin, a1, a2, b1, b2 in rows:
        if Re >= Rmin:
            break
    pr = g["Pt"] / g["do"]
    a = a3 / (1 + 0.14 * Re ** a4)
    b = b3 / (1 + 0.14 * Re ** b4)
    ji = a1 * (1.33 / pr) ** a * Re ** a2
    fi = b1 * (1.33 / pr) ** b * Re ** b2
    Pr = cp * mu / k
    Jc = 0.55 + 0.72 * g["Fc"]
    rs = g["Ssb"] / (g["Ssb"] + g["Stb"])
    rlm = (g["Ssb"] + g["Stb"]) / g["Sm"]
    Jl = 0.44 * (1 - rs) + (1 - 0.44 * (1 - rs)) * math.exp(-2.2 * rlm)
    Fsbp = g["Sb"] / g["Sm"]
    Jb = math.exp(-(1.25 if Re < 100 else 1.35) * Fsbp)
    Nc = (g["Ntcc"] + g["Ntcw"]) * (g["Nb"] + 1)
    if Re >= 100:
        Jr = 1.0
    else:
        Jr20 = (10.0 / Nc) ** 0.18
        Jr = Jr20 if Re <= 20 else Jr20 + (20 - Re) / 80.0 * (Jr20 - 1)
    G = m / g["Sm"]
    h = ji * cp * G * Pr ** (-2.0 / 3.0) * (mu / muw) ** 0.14 * Jc * Jl * Jb * Jr
    # pressure drop
    dPbi = 2 * fi * g["Ntcc"] * G * G / rho * (muw / mu) ** 0.14
    p = -0.15 * (1 + rs) + 0.8
    Rl = math.exp(-1.33 * (1 + rs) * rlm ** p)
    Rb = math.exp(-(4.5 if Re < 100 else 3.7) * Fsbp)
    mw = m / math.sqrt(g["Sm"] * g["Sw"])
    dPc = dPbi * (g["Nb"] - 1) * Rb * Rl
    if Re >= 100:
        dPw = g["Nb"] * (2 + 0.6 * g["Ntcw"]) * mw * mw / (2 * rho) * Rl
    else:
        Dw = 4 * g["Sw"] / (math.pi * g["do"] * g["Nt"] * g["Fw"] + g["Ds"] * g["tds"])
        dPw = g["Nb"] * (26 * mu * mw / rho * (g["Ntcw"] / (g["Pt"] - g["do"]) + g["Lbc"] / Dw ** 2) +
                         mw * mw / rho) * Rl
    dPe = 2 * dPbi * (1 + g["Ntcw"] / g["Ntcc"]) * Rb
    return h, dPc + dPw + dPe, Re


def tube_side(g, m, T, passes):
    rho, cp, k, mu = water_props(T)
    n_per_pass = g["Nt"] / passes
    A = n_per_pass * math.pi * g["di"] ** 2 / 4
    v = m / (rho * A)
    Re = rho * v * g["di"] / mu
    Pr = cp * mu / k
    f = (0.790 * math.log(Re) - 1.64) ** -2
    Nu = (f / 8) * (Re - 1000) * Pr / (1 + 12.7 * math.sqrt(f / 8) * (Pr ** (2 / 3) - 1)) if Re > 2300 else 3.66
    h = Nu * k / g["di"]
    dP = passes * (f * g["L"] / g["di"] + 2.5) * rho * v * v / 2
    return h, dP, v


def F_factor(R, P, N):
    """LMTD correction for N shells in series, each 1 shell pass / even tube passes (Bowman)."""
    if P <= 0:
        return 1.0
    if abs(R - 1) < 1e-6:
        Px = P / (N - (N - 1) * P)
        s = math.sqrt(2)
        num = s * Px / (1 - Px)
        den = math.log((2 - Px * (2 - s)) / (2 - Px * (2 + s)))
        return num / den
    X = ((1 - R * P) / (1 - P)) ** (1.0 / N)
    Px = (1 - X) / (R - X)
    S = math.sqrt(R * R + 1)
    a = (2 - Px * (R + 1 - S))
    b = (2 - Px * (R + 1 + S))
    if a <= 0 or b <= 0 or (1 - R * Px) <= 0 or (1 - Px) <= 0:
        return float("nan")
    return S * math.log((1 - Px) / (1 - R * Px)) / ((R - 1) * math.log(a / b))


def rate(d, basis):
    """Oil outlet temperature, shell and tube pressure drops and tube velocity for design d at basis."""
    g = geometry(d)
    oil = basis["oil"]
    mo, mc = basis["oil_kg_s"], basis["cw_kg_s"]
    Thi, Tci = basis["oil_in_c"], basis["cw_in_c"]
    Ns = d["shells_in_series"]
    Rfo = basis["fouling_oil"]
    Rfi = basis.get("fouling_cw")
    Aone = g["Nt"] * math.pi * g["do"] * g["L"]
    A = Aone * Ns
    Tho = Thi - 25.0
    for _ in range(60):
        Tco = Tci + mo * oil_props(0.5 * (Thi + Tho), oil)[1] * (Thi - Tho) / (mc * 4180.0)
        Tm_o, Tm_c = 0.5 * (Thi + Tho), 0.5 * (Tci + Tco)
        Tw = Tm_c + 0.35 * (Tm_o - Tm_c)
        for _ in range(4):
            hs, dPs, Res = shell_side(g, mo / 1.0, Tm_o, Tw, oil)
            ht, dPt, v = tube_side(g, mc / 1.0, Tm_c, d["tube_passes"])
            if basis.get("fouling_cw") is None:            # TEMA: treated tower water, by tube velocity
                Rfi = 0.000176 if v > 0.9 else 0.000352
            Uo = 1.0 / (1 / hs + Rfo + g["do"] * math.log(g["do"] / g["di"]) / (2 * K_WALL) + Rfi * g["do"] / g["di"]
                        + g["do"] / (g["di"] * ht))
            Tw = Tm_o - Uo * (Tm_o - Tm_c) / hs
        Ch = mo * oil_props(Tm_o, oil)[1]
        Cc = mc * 4180.0
        # effectiveness of N 1-2 shells in series
        Cmin, Cmax = min(Ch, Cc), max(Ch, Cc)
        Cr = Cmin / Cmax
        ntu1 = Uo * Aone / Cmin
        s = math.sqrt(1 + Cr * Cr)
        e1 = 2 / (1 + Cr + s * (1 + math.exp(-ntu1 * s)) / (1 - math.exp(-ntu1 * s)))
        if abs(Cr - 1) < 1e-9:
            e = Ns * e1 / (1 + (Ns - 1) * e1)
        else:
            q = ((1 - e1 * Cr) / (1 - e1)) ** Ns
            e = (q - 1) / (q - Cr)
        Q = e * Cmin * (Thi - Tci)
        new = Thi - Q / Ch
        if abs(new - Tho) < 1e-4:
            Tho = new
            break
        Tho = 0.5 * (Tho + new)
    return dict(oil_out_c=Tho, cw_out_c=Tci + Q / Cc, duty_kw=Q / 1000, dp_shell_kpa=dPs * Ns / 1000,
                dp_tube_kpa=dPt * Ns / 1000, tube_velocity=v, U=Uo, area_m2=A, Re_shell=Res, h_shell=hs, h_tube=ht)
