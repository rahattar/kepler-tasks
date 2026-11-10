"""MS-PH physics: the hydrogen-cracking preheat of EN 1011-2 (Annex C, method B), the HAZ hardness of the capping runs
(the Dueren relation with the EN 1011-2 Annex D cooling time t8/5), heat input and the diffusible hydrogen of covered
electrodes after moisture pick-up."""
import math
from scipy.optimize import brentq

K = {"111": 0.8, "121": 1.0, "135": 0.8, "136": 0.8, "141": 0.6}      # thermal efficiency by process number
F_CAP = (1.0, 0.9)                                                     # (F2, F3) of a capping run of a butt weld
HV_MAX = 380.0                                                         # HV10, as welded (EN ISO 15614-1, groups 1 and 2)


def cet(c):
    return c["C"] + (c["Mn"] + c["Mo"]) / 10 + (c["Cr"] + c["Cu"]) / 20 + c["Ni"] / 40


def ceb(c):
    return c["C"] + c["Si"] / 11 + c["Mn"] / 8 + c["Cu"] / 9 + c["Cr"] / 5 + c["Ni"] / 17 + c["Mo"] / 6 + c["V"] / 3


def tp_hydrogen(CET, d, HD, Q):
    return 697 * CET + 160 * math.tanh(d / 35) + 62 * HD ** 0.35 + (53 * CET - 32) * Q - 328


def t85(T0, Q, d, F2=F_CAP[0], F3=F_CAP[1]):
    t3 = (6700 - 5 * T0) * Q * (1 / (500 - T0) - 1 / (800 - T0)) * F3
    t2 = (4300 - 4.3 * T0) * 1e5 * (Q / d) ** 2 * (1 / (500 - T0) ** 2 - 1 / (800 - T0) ** 2) * F2
    return max(t2, t3)


def hv(C, CE, t):
    lt = math.log10(t)
    return 2019 * (C * (1 - 0.5 * lt) + 0.3 * (CE - C)) + 66 * (1 - 0.8 * lt)


def t_min(C, CE, hv_max=HV_MAX):
    """The shortest t8/5 at which the HAZ hardness is at most hv_max (HV linear in log t)."""
    A = 2019 * (C + 0.3 * (CE - C)) + 66
    B = 2019 * 0.5 * C + 66 * 0.8
    return 10 ** ((A - hv_max) / B)


def tp_hardness(C, CE, d, caps, hv_max=HV_MAX, mode="max"):
    """The lowest preheat at which every capping run's t8/5 reaches t_min. caps: heat inputs (kJ/mm) of the capping
    runs. mode: "max" (the larger of t2 and t3, MS-PH), "3d" or "2d" (one formula only, for the route study)."""
    tm = t_min(C, CE, hv_max)

    def t(T0, Q):
        if mode == "max":
            return t85(T0, Q, d)
        F2, F3 = F_CAP
        if mode == "3d":
            return (6700 - 5 * T0) * Q * (1 / (500 - T0) - 1 / (800 - T0)) * F3
        return (4300 - 4.3 * T0) * 1e5 * (Q / d) ** 2 * (1 / (500 - T0) ** 2 - 1 / (800 - T0) ** 2) * F2
    need = -273.0
    for Q in caps:
        if t(-100, Q) >= tm:
            need = max(need, -100.0)
            continue
        need = max(need, brentq(lambda T: t(T, Q) - tm, -100, 450, xtol=1e-9))
    return need


def vapor_kpa(T, RH):
    return RH / 100 * 0.61094 * math.exp(17.625 * T / (T + 243.04))


def heat_input(process, power_w, v_mm_s):
    return K[process] * power_w / v_mm_s / 1000
