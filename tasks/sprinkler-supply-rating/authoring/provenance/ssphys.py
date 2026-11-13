"""The pressure budget of FP-12 and the tests the site's records come from.

Sealed: this file and site.py are the definition the records and the expected rating are written from. Nothing
here is fitted to a solution's output.

    p_base = S - d_main(Q) - d_bfp(Q) - d_lead(q) - d_valve(q) - d_check(q)

S is the city main's static at the connection, referred to the site datum; Q is the flow through the connection
and q the flow through the riser's own lead-in, both in gpm; pressures in psi.
"""
import math

HW_N = 1.85
PSI_PER_FT = 0.433
PITOT = 29.84                     # Q = 29.84 c d^2 sqrt(p), d in inches, p in psi, per outlet

# internal diameters, inches
PIPE_ID = {
    ("DI-CL", "6"): 6.16, ("DI-CL", "8"): 8.27,       # ductile iron, cement lined
    ("CI", "6"): 6.00, ("CI", "8"): 8.00,             # cast iron, unlined
}
OUTLET_C = {"smooth": 0.90, "square": 0.80, "projecting": 0.70}
DRAIN_K = {"2 in. angle": 52.0, "1-1/2 in. globe": 36.0}
VALVE_OPEN_CV = {"6": 5200.0, "8": 9800.0}             # control valve fully open
CHECK_CV = {"6": 2100.0, "8": 3900.0}                  # lead-in check valve, flow term


def k_lead(length_ft, C, material, size):
    """Hazen-Williams coefficient of a lead-in, psi per gpm^1.85."""
    return 4.52 * length_ft / (C ** HW_N * PIPE_ID[(material, size)] ** 4.87)


def d_main(B, Q):
    return B * (Q / 1000.0) ** HW_N


def d_bfp(h_b, Cv_b, Q):
    return h_b + (Q / Cv_b) ** 2 if Q > 0 else 0.0


def own_losses(riser, q):
    """The riser's own losses at flow q, as a dict by element (riser: its state at the time)."""
    out = {"lead-in": k_lead(riser["length_ft"], riser["C"], riser["material"], riser["size"]) * q ** HW_N,
           "valve": (q / riser["valve_cv"]) ** 2,
           "check": 0.0}
    if riser.get("check"):
        out["check"] = riser["h_c"] + (q / CHECK_CV[riser["size"]]) ** 2
    return out


def budget(site, riser, S, q, Q):
    """Losses by element and the two pressures at (S, q, Q): site and riser are states at one time."""
    loss = {"city-main": d_main(site["B"], Q), "backflow": d_bfp(site["h_b"], site["Cv_b"], Q)}
    loss.update(own_losses(riser, q))
    p_yard = S - loss["city-main"] - loss["backflow"]
    p_base = p_yard - loss["lead-in"] - loss["valve"] - loss["check"]
    return loss, p_yard, p_base


def pitot_flow(c, d_in, pitot_psi, outlets=1):
    return outlets * PITOT * c * d_in ** 2 * math.sqrt(pitot_psi)


def drain_test(site, riser, S):
    """A main drain test: the residual on the supply gauge (true pressure at the gauge) and the drain's flow.
    The drain passes q = K sqrt(p) with p the residual on the supply gauge; only this riser flows."""
    K = DRAIN_K[riser["drain"]]
    lo, hi = 0.0, 2000.0
    for _ in range(80):
        q = 0.5 * (lo + hi)
        _l, _y, p_base = budget(site, riser, S, q, q)
        p_g = p_base - PSI_PER_FT * riser["gauge_ft"]
        if p_g > 0 and K * math.sqrt(p_g) > q:
            lo = q
        else:
            hi = q
    q = 0.5 * (lo + hi)
    _l, _y, p_base = budget(site, riser, S, q, q)
    return p_base - PSI_PER_FT * riser["gauge_ft"], q


def held_static(site, riser, S_held):
    """The supply gauge with nothing flowing: the yard holds S_held - h_b, the highest it has been brought to
    since the last flow, and a lead-in check holds its own opening differential below that."""
    p = S_held - site["h_b"] - (riser["h_c"] if riser.get("check") else 0.0)
    return p - PSI_PER_FT * riser["gauge_ft"]
