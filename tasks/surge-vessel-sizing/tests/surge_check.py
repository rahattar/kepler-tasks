"""MS-SV clause 3 check of a vessel design on a main as installed (the sealed definitions in hidden/truth.json),
with the method of characteristics in moc.py (MS-SV clause 2): all running sets trip at the bottom, middle and top
water levels of the reservoir; the crown pressure, the largest pressure and the vessel's gas volume over 120 s."""
import math
import moc

LIM = dict(pmin=-3.0, pmax=160.0, gas=0.85, economy=1.15)


def colebrook(k, D, v, nu=1.0e-6):
    Re = v * D / nu; f = 0.02
    for _ in range(60):
        f = (-2 * math.log10(k / (3.7 * D) + 2.51 / (Re * math.sqrt(f)))) ** -2
    return f


def case(m, Ht, vessel=None):
    """The main at reservoir level Ht, with the Colebrook friction factor of the steady flow it carries."""
    A = math.pi * m["D"] ** 2 / 4
    f = colebrook(m["k"], m["D"], 1.5)
    for _ in range(8):
        P = dict(dt=0.02, sections=[dict(L=m["L"], D=m["D"], a=m["a"], f=f)], profile=(m["ch"], m["z"]), Hs=m["ww"],
                 Ht=Ht, pump=dict(m["pump"]))
        f = colebrook(m["k"], m["D"], max(moc.steady(P)[4] / A, 0.05))
    P = dict(dt=0.02, sections=[dict(L=m["L"], D=m["D"], a=m["a"], f=f)], profile=(m["ch"], m["z"]), Hs=m["ww"], Ht=Ht,
             pump=dict(m["pump"]), vessel=vessel)
    return P


def check(m, V, Vg):
    worst = dict(pmin=1e9, pmax=-1e9, gas=0.0)
    for Ht in (m["BWL"], 0.5 * (m["BWL"] + m["TWL"]), m["TWL"]):
        r = moc.run(case(m, Ht, dict(m["vessel"], V=V, Vg0=Vg, zw=m["header"] + 1.0)), T=120.0)
        worst["pmin"] = min(worst["pmin"], float((r["pmin"] - m["D"] / 2).min()))
        worst["pmax"] = max(worst["pmax"], float(r["pmax"].max()))
        worst["gas"] = max(worst["gas"], float(r["Vgmax"] / V))
    ok = worst["pmin"] >= LIM["pmin"] and worst["pmax"] <= LIM["pmax"] and worst["gas"] <= LIM["gas"]
    return ok, worst
