"""Method spread: recompute the as-built review under defensible variants (should stay inside the tolerances) and
under the known errors (should fall outside)."""
import copy, importlib, math, sys
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "provenance"))
import method as M, project as P

FIELDS = ["outdoor_air_l_s", "coil_entering_wb_c", "block_total_kw", "block_sensible_kw", "block_latent_kw",
          "net_capacity_total_kw", "net_capacity_sensible_kw", "net_capacity_latent_kw"]
BASE = P.truth()

def reload():
    M.W_ROOM = M.w_from_rh(M.T_ROOM, M.RH_ROOM); M.W_OA = M.w_from_wb(M.T_OA_DESIGN, M.WB_OA_DESIGN)

def dev(T):
    out = {}
    for u in P.UNITS:
        if BASE[u]["verdict"] == "undetermined": continue
        for f in FIELDS:
            a, b = T[u][f], BASE[u][f]
            d = (a - b) if f == "coil_entering_wb_c" else (a - b) / b
            out.setdefault(f, []).append((abs(d), u))
        if T[u]["verdict"] != BASE[u]["verdict"]: out.setdefault("verdict", []).append((1, u))
    return {f: max(v) for f, v in out.items()}

def variant(name, patch, unpatch):
    patch(); reload()
    try:
        T = P.truth()
    finally:
        unpatch(); reload()
    d = dev(T)
    print("%-34s" % name, "  ".join("%s %s%.3f(%s)" % (f.replace("_kw","").replace("net_capacity","cap").replace("block","load").replace("coil_entering_wb_c","EWB").replace("outdoor_air_l_s","OA"),
                                                    "" if f=="coil_entering_wb_c" else "", v[0] if f=="coil_entering_wb_c" else 100*v[0], v[1]) for f, v in d.items() if f!="verdict"),
          "| VERDICT FLIP " + str(d["verdict"][1]) if "verdict" in d else "")

orig = dict(P=M.P_STATION, pws=M.pws, mix=M.mix, cp=M.CP_AIR, cl=M.CL_AIR, cap=M.capacity, vent=M.ventilation)
def restore():
    M.P_STATION = orig["P"]; M.pws = orig["pws"]; M.mix = orig["mix"]; M.CP_AIR = orig["cp"]; M.CL_AIR = orig["cl"]
    M.capacity = orig["cap"]; M.ventilation = orig["vent"]
    for fn in ("w_from_pw", "w_from_rh", "w_from_wb", "wb_from_w", "spec_volume"):
        f = getattr(M, fn); f.__defaults__ = tuple(M.P_STATION if isinstance(x, float) and abs(x - 98.9) < 3 else x for x in (f.__defaults__ or ()))

def set_p(p):
    def go():
        M.P_STATION = p
        for fn in ("w_from_pw", "w_from_rh", "w_from_wb", "wb_from_w", "spec_volume"):
            f = getattr(M, fn); f.__defaults__ = tuple(p if isinstance(x, float) and abs(x - 98.9) < 3 else x for x in (f.__defaults__ or ()))
    return go

def magnus():
    M.pws = lambda t: 0.61094 * math.exp(17.625 * t / (t + 243.04))

def vol_mix():
    def mix(v_oa, v_total):
        x = v_oa / v_total
        w = x * M.W_OA + (1 - x) * M.W_ROOM; t = x * M.T_OA_DESIGN + (1 - x) * M.T_ROOM
        return t, w, M.wb_from_w(t, w)
    M.mix = mix

def consts(cp, cl):
    def go(): M.CP_AIR = cp; M.CL_AIR = cl
    return go

def cap_variant(kind):
    def go():
        base = orig["cap"]
        def cap(model, airflow, ewb, edb, odb=M.T_OA_DESIGN):
            if kind == "rating_ewb": return base(model, airflow, 19.4, 26.7, odb)
            if kind == "rating_point":
                tc, sc, q = M.ahri_rating(model); return dict(net_total=tc, net_sensible=sc, net_latent=tc - sc)
            c = base(model, airflow, ewb, 26.7 if kind == "no_edb" else edb, odb)
            if kind == "gross": c = dict(c, net_total=c["gross_total"], net_sensible=c["gross_sensible"])
            return c
        M.capacity = cap
    return go

def no_ev():
    def vent(zones, vps):
        vou = sum(z["rp"] * z["pz"] + z["ra"] * z["az"] for z in zones); return vou, vou, 1.0, 0
    M.ventilation = vent

def ev_simplified():
    def vent(zones, vps):
        vou = sum(z["rp"] * z["pz"] + z["ra"] * z["az"] for z in zones); return vou / 0.75, vou, 0.75, 0
    M.ventilation = vent

print("defensible variants (must stay inside tolerances):")
variant("station pressure 101.325 kPa", set_p(101.325), lambda: (set_p(98.9)(), restore()))
variant("Magnus saturation pressure", magnus, restore)
variant("mixing by volume, linear DB", vol_mix, restore)
variant("air constants 1.20 / 3000", consts(1.20, 3000.0), restore)
variant("altitude-corrected constants", consts(1.23 * 98.9 / 101.325, 3010.0 * 98.9 / 101.325), restore)
print("known errors (must fall outside):")
variant("capacity at AHRI rating point", cap_variant("rating_point"), restore)
variant("capacity at 19.4 C EWB, 26.7 EDB", cap_variant("rating_ewb"), restore)
variant("no entering-dry-bulb correction", cap_variant("no_edb"), restore)
variant("gross (no fan heat)", cap_variant("gross"), restore)
variant("Ev = 1 (sum of zone rates)", no_ev, restore)
variant("Ev simplified procedure 0.75", ev_simplified, restore)
