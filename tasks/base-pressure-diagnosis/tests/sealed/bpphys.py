"""MS-BP physics: the steady gas budget of a vacuum chamber at the audit reference condition.

The chamber is a lumped volume pumped by a turbomolecular pump through a high-vacuum port:

    p = Q_total(t, T, vent) / S_eff(p)

with Q_total the sum of four mechanisms and S_eff the pump speed in series with the port conductance.

Mechanisms, all in mbar L/s, with t in hours from the start of roughing after a vent and T the chamber wall
temperature in K:

- Wall and internals outgassing (water):  Q_w = sum_i A_i q1_i t^-alpha_i  x f_vent x theta_w(T)
  q1 at 1 h and 20 C from the shop's outgassing table; f_vent 1 for an air vent, N2_FACTOR for dry nitrogen.
- Real air leak:                          Q_L, constant in t and T.
- Virtual leak (a trapped volume):        Q_v = Q_v0 exp(-t / tau).
- Permeation through elastomer seals:     Q_p = K20 L_seal theta_p(T), K20 per elastomer per cm of seal.

theta_w and theta_p are Arrhenius factors referred to 20 C with activation energies E_W and E_P.

S_eff = S_turbo(p) f_pump C_port / (S_turbo(p) f_pump + C_port), with f_pump the pump's condition factor (1 for a
pump in order). The turbo curves are flat below 1e-3 mbar, so S_eff is effectively constant over the base-pressure
range and p = Q / S_eff is a well-conditioned fixed point.

Species: each mechanism admits gas of its own composition (SPECIES), which the chamber's residual gas analysis
shows as partial pressures. Permeated air is enriched in oxygen and depleted in argon by the elastomer's relative
permeabilities.
"""
import math

R_GAS = 8.3145                      # J/(mol K)
T_REF = 293.15                      # K, the shop's reference temperature (20 C)
E_W = 30.0e3                        # J/mol, wall water outgassing
E_P = 42.0e3                        # J/mol, permeation through elastomer
N2_FACTOR = 0.25                    # wall gas load after a dry nitrogen vent, relative to an air vent
T_HOLD = 0.05                       # h, the outgassing law is held at this value below it

# turbo pumps: (pressure mbar, speed L/s), for nitrogen
TURBO = {
    "TMP-400": [(1e-9, 360.0), (1e-3, 360.0), (1e-2, 250.0), (5e-2, 100.0), (2e-1, 28.0)],
    "TMP-700": [(1e-9, 640.0), (1e-3, 640.0), (1e-2, 420.0), (5e-2, 160.0), (2e-1, 40.0)],
    "TMP-1100": [(1e-9, 1010.0), (1e-3, 1010.0), (1e-2, 640.0), (5e-2, 230.0), (2e-1, 55.0)],
    "TMP-1600": [(1e-9, 1480.0), (1e-3, 1480.0), (1e-2, 900.0), (5e-2, 310.0), (2e-1, 70.0)],
}

# what a pump in order reports to its controller: rated rotor frequency Hz, drive power W, bearing temperature C
PUMP_CONTROLLER = {
    "TMP-400": (1000.0, 60.0, 38.0),
    "TMP-700": (820.0, 95.0, 42.0),
    "TMP-1100": (700.0, 130.0, 45.0),
    "TMP-1600": (600.0, 170.0, 48.0),
}

# the shop's outgassing table after an air vent, at 1 h and 20 C: q1 mbar L/(s cm2), decay exponent alpha
OUTGAS = {
    "stainless steel, electropolished": (7.0e-9, 1.00),
    "stainless steel, as machined": (2.6e-8, 1.00),
    "stainless steel, bead blasted": (6.5e-8, 0.95),
    "aluminum, bare": (1.4e-8, 1.00),
    "aluminum, anodized": (5.5e-7, 0.85),
    "copper, bare": (2.2e-8, 1.00),
    "PEEK": (3.5e-7, 0.60),
    "graphite felt": (9.0e-7, 0.70),
}

# elastomer seals: K20 mbar L/(s cm) of seal length for air at 1013 mbar, and the relative permeabilities of the
# species of air referred to nitrogen
SEALS = {
    "fluoroelastomer": dict(K20=1.15e-7, rel=dict(n2=1.00, o2=3.00, ar=0.35, co2=12.0)),
    "nitrile": dict(K20=3.40e-7, rel=dict(n2=1.00, o2=2.60, ar=0.40, co2=10.0)),
    "perfluoroelastomer": dict(K20=4.20e-8, rel=dict(n2=1.00, o2=2.80, ar=0.30, co2=11.0)),
}

# dry air by volume fraction
AIR = dict(n2=0.7808, o2=0.2095, ar=0.00934, co2=0.00042)

# the species each mechanism admits, as fractions of its gas load
SPECIES = {
    "wall-outgassing": dict(h2o=0.960, h2=0.015, n2=0.025),
    "air-leak": dict(n2=AIR["n2"], o2=AIR["o2"], ar=AIR["ar"], co2=AIR["co2"]),
    "virtual-leak": dict(n2=AIR["n2"], o2=AIR["o2"], ar=AIR["ar"], co2=AIR["co2"]),
}

# each gauge type's sensitivity to each species relative to nitrogen, keyed by the serial's prefix: hot-filament
# ionization gauges (IG) and cold cathode gauges (CC). The two differ most for water, which a cold cathode's
# discharge reads well below nitrogen, so on a pumpdown read with both the ratio of their readings depends on how
# much of the gas is water.
GAS_FACTOR = {
    "IG": dict(h2o=1.12, h2=0.42, n2=1.00, o2=1.01, ar=1.29, co2=1.42),
    "CC": dict(h2o=0.80, h2=0.46, n2=1.00, o2=0.94, ar=1.12, co2=1.30),
}
GAUGE_TYPES = {"IG": "hot-filament ionization gauge", "CC": "cold cathode gauge"}

CAUSES = ("air-leak", "virtual-leak", "wall-outgassing", "permeation", "pump-speed")
TAU_MAX = 48.0                      # h, the longest time constant a trapped volume of this shop has; a source
                                    # constant over a pumpdown is a leak, not a trapped volume of some hundreds
                                    # of hours, and MS-BP clause 3.3 says so
PUMP_GATE = 0.75                    # S_eff below this fraction of the rated S_eff makes the pump the cause


def curve(table, p):
    """Pump speed at pressure p, linear in log10 p between the table points and held beyond the ends."""
    lp = math.log10(max(p, 1e-12))
    xs = [math.log10(a) for a, _ in table]
    ys = [b for _, b in table]
    if lp <= xs[0]:
        return float(ys[0])
    if lp >= xs[-1]:
        return float(ys[-1])
    for i in range(1, len(xs)):
        if lp <= xs[i]:
            f = (lp - xs[i - 1]) / (xs[i] - xs[i - 1])
            return float(ys[i - 1] + f * (ys[i] - ys[i - 1]))
    return float(ys[-1])


def series(s, c):
    return s * c / (s + c)


def theta_w(T_K):
    return math.exp(E_W / R_GAS * (1.0 / T_REF - 1.0 / T_K))


def theta_p(T_K):
    return math.exp(E_P / R_GAS * (1.0 / T_REF - 1.0 / T_K))


def q_wall_nominal(surfaces, t_h, vent="air", T_K=T_REF):
    """The wall and internals water load the outgassing table's nominal q1 would give for these surfaces."""
    t = max(t_h, T_HOLD)
    f = 1.0 if vent == "air" else N2_FACTOR
    tot = 0.0
    for area, mat in surfaces:
        q1, alpha = OUTGAS[mat]
        tot += area * q1 * t ** -alpha
    return tot * f * theta_w(T_K)


def q_wall(surfaces, t_h, vent="air", T_K=T_REF, factor=1.0):
    """The chamber's actual wall and internals water load: its own magnitude times the nominal shape. The table's
    q1 is a planning figure; a chamber's real specific gas load depends on the history of its surfaces, so the
    audit identifies `factor` from the chamber's own records."""
    return factor * q_wall_nominal(surfaces, t_h, vent, T_K)


def q_virtual(qv0, tau_h, t_h):
    if not qv0:
        return 0.0
    return qv0 * math.exp(-max(t_h, 0.0) / tau_h)


def q_perm(seal, l_seal_cm, T_K=T_REF):
    if not l_seal_cm:
        return 0.0
    return SEALS[seal]["K20"] * l_seal_cm * theta_p(T_K)


def components(cfg, t_h, vent="air", T_K=T_REF):
    """The four gas loads of a chamber configuration at (t, vent, T), in mbar L/s."""
    return {
        "wall-outgassing": q_wall(cfg["surfaces"], t_h, vent, T_K, cfg.get("wall_factor", 1.0)),
        "air-leak": cfg["leak"],
        "virtual-leak": q_virtual(cfg["qv0"], cfg["tau"], t_h),
        "permeation": q_perm(cfg["seal"], cfg["seal_cm"], T_K),
    }


def q_total(cfg, t_h, vent="air", T_K=T_REF):
    return sum(components(cfg, t_h, vent, T_K).values())


def s_eff(cfg, p, rated=False):
    """Effective speed for nitrogen at pressure p. With rated=True the pump is taken in as-new condition."""
    f = 1.0 if rated else cfg["f_pump"]
    return series(curve(TURBO[cfg["turbo"]], p) * f, cfg["c_port"])


def s_rated(cfg, p):
    return s_eff(cfg, p, rated=True)


def p_base(cfg, q, p0=1e-6):
    """Solves p = q / S_eff(p) for the chamber's indicated-gas-independent total pressure."""
    p = p0
    for _ in range(200):
        pn = q / s_eff(cfg, p)
        if abs(pn - p) <= 1e-12 * max(pn, 1e-12) + 1e-18:
            return pn
        p = 0.5 * (p + pn) if _ < 5 else pn
    return p


def partials(cfg, t_h, vent="air", T_K=T_REF):
    """Partial pressures by species at the steady state, mbar. Each mechanism's gas is pumped at the speed its
    own species sees; for the base-pressure range the turbo curve is flat, so one S_eff serves for all."""
    comp = components(cfg, t_h, vent, T_K)
    q = sum(comp.values())
    s = s_eff(cfg, p_base(cfg, q))
    out = dict(h2o=0.0, h2=0.0, n2=0.0, o2=0.0, ar=0.0, co2=0.0)
    for mech, qm in comp.items():
        if qm <= 0:
            continue
        if mech == "permeation":
            rel = SEALS[cfg["seal"]]["rel"]
            w = {k: AIR[k] * rel[k] for k in AIR}
        else:
            w = SPECIES[mech]
        tot = sum(w.values())
        for k, v in w.items():
            out[k] += qm * (v / tot) / s
    return out


def indicated(cfg, t_h, vent="air", T_K=T_REF, gauge="IG"):
    """What a nitrogen-calibrated gauge indicates: the sum of the partial pressures, each weighted by the gauge's
    relative sensitivity to that species (a species with K above 1 reads high). `gauge` is the gauge's serial or its
    type prefix; the sensitivities are its type's."""
    pp = partials(cfg, t_h, vent, T_K)
    k = GAS_FACTOR[gauge[:2]]
    return sum(v * k[s] for s, v in pp.items())


def cause(cfg, t_h, T_K=T_REF):
    """MS-BP clause 6: the pump when S_eff falls below PUMP_GATE of the rated speed, otherwise the mechanism with
    the largest share of the total gas load at the reference condition."""
    q = q_total(cfg, t_h, "air", T_K)
    p = p_base(cfg, q)
    if s_eff(cfg, p) < PUMP_GATE * s_rated(cfg, p):
        return "pump-speed"
    comp = components(cfg, t_h, "air", T_K)
    return max(comp, key=lambda k: comp[k])


def margins(cfg, t_h, T_K=T_REF):
    """How clearly the cause is decided: the ratio of the largest gas load to the next, and S_eff / S_rated."""
    comp = components(cfg, t_h, "air", T_K)
    order = sorted(comp.values(), reverse=True)
    q = sum(comp.values())
    p = p_base(cfg, q)
    return dict(share=order[0] / q, ratio=order[0] / order[1] if order[1] > 0 else float("inf"),
                pump=s_eff(cfg, p) / s_rated(cfg, p))


def rate_of_rise(cfg, t0_h, minutes, step_s, T_K=T_REF, vent="air"):
    """The pressure rise with the pump valved off from t0_h, at step_s intervals: V dp/dt = Q(t). Returns
    [(seconds from valve closure, pressure mbar)], the true total pressure, started from the steady base pressure."""
    out = []
    p = p_base(cfg, q_total(cfg, t0_h, vent, T_K))
    n = int(minutes * 60 // step_s)
    for i in range(n + 1):
        sec = i * step_s
        if i:
            # trapezoidal integration of Q over the step, in mbar L/s, into a volume of cfg["volume"] L
            ta = t0_h + (sec - step_s) / 3600.0
            tb = t0_h + sec / 3600.0
            qa = q_total(cfg, ta, vent, T_K)
            qb = q_total(cfg, tb, vent, T_K)
            p += 0.5 * (qa + qb) * step_s / cfg["volume"]
        out.append((sec, p))
    return out
