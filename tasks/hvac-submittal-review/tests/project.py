"""Layered version. Layer 1 (record documents and the contractor's submittal) is internally consistent and
the submittal passes the standard on it. Layer 2 (work orders, minutes, asset inventory) hints
that the as-built differs. Layer 3 (field verification, budgeted) gives the as-built inputs. The review is
graded on the as-built condition."""
import copy, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_base as B

HOURS, T_OUT = B.HOURS, B.T_OUT
CLTD_ROOF, CLTD_WALL, SCL = B.CLTD_ROOF, B.CLTD_WALL, B.SCL
U_WALL, U_GLASS, SHGC, INFIL = B.U_WALL, B.U_GLASS, B.SHGC, B.INFIL
PEOPLE, LIGHTS, OA, BAND = B.PEOPLE, B.LIGHTS, B.OA, B.BAND
import method as M
ROOF_U = {"R-20 (2004 record)": 0.25, "R-30 (re-roofed)": 0.18}       # Table 3 of the standard
UNITS = B.UNITS

# record (layer 1) spaces: start from the base and make the record consistent (no notes, no comments)
RECORD = []
for s in B.SPACES:
    s = copy.deepcopy(s)
    for k in ("existing", "deleted", "people_addendum", "shell"):
        s.pop(k, None)
    if s["no"] == "140": continue                      # deleted by Addendum 1, already out of the record schedule
    if s["no"] == "130": s["shell"] = True
    if s["no"] == "144": s["people"] = 18
    if s["no"] == "145": s["equip"] = 2400
    if s["no"] == "110": s["equip"] = 2000
    s["roof_assembly"] = "R-20 (2004 record)"
    RECORD.append(s)
RECORD_BY = {s["no"]: s for s in RECORD}
SHELL_ASSUMED = dict(people=26, cat="office", equip=3000)

# as-built (layer 3): deltas on the record; "hint" names the layer-2 document that points at it
# as-built (layer 3). The 2019 reorganisation refurnished the rooms in REFURNISHED (known only from the
# 2019 furniture work orders); the effect depends on room size: single offices became three-workstation
# rooms, mid-size rooms gained half again, open offices a quarter, conference rooms were reseated at 1.4 times. Untouched rooms drifted a little
# at random. The lab programme grew in 2022. 118 is served by AC-1 (records explicit).
import random as _rnd
REFURNISHED = ["110", "112", "114", "116", "210", "220", "221", "222", "223", "230", "231", "232", "233",
               "142", "143", "144", "145"]
LAB_GROWTH = {"160": 1.8, "161": 1.8}
BUDGET = 8
DRIFT_SEED = 0                      # the shipped instance; authoring/evidence varies it


def _drift(s):
    r = _rnd.Random(int(s["no"]) * 7919 + DRIFT_SEED)
    s = copy.deepcopy(s)
    if s["no"] in REFURNISHED:
        if s["cat"] == "conference":
            s["people"] = int(round(s["people"] * 1.4)); s["equip"] = s["equip"] + 400
        elif s["area"] <= 15.0:
            s["people"] = 2; s["equip"] = 500
        elif s["area"] <= 20.0:
            s["people"] = 3; s["equip"] = 750
        elif s["area"] <= 50.0:
            s["people"] = int(round(s["people"] * 1.5)); s["equip"] = int(round(s["equip"] * 1.5))
        else:
            s["people"] = int(round(s["people"] * 1.25)); s["equip"] = int(round(s["equip"] * 1.25))
    elif s["no"] in LAB_GROWTH:
        s["equip"] = int(round(s["equip"] * LAB_GROWTH[s["no"]]))
    elif not s.get("shell") and s["cat"] != "corridor" and s["unit"] != "RTU-4":
        r.choice([-1, 0, 0, 1])                      # (kept so the equipment draws stay as before)
        s["equip"] = int(round(s["equip"] * r.uniform(0.9, 1.1) / 10) * 10)
    return s


ASBUILT_DELTAS = {"118": dict(served_by="AC-1", hint="WO-2019-0412")}
ROOF_ASBUILT = {1: "R-20 (2004 record)", 2: "R-20 (2004 record)"}
EXISTING_UNITS = {
    "AC-1": dict(serves=["118"], nominal="5 ton ductless split system, installed 2019, remains in service"),
    "RTU-A": dict(serves=["101", "102", "103", "104", "105", "106", "107", "108", "109"], nominal="12.5 ton packaged rooftop, 2004, west wing level 1, remains in service"),
    "RTU-B": dict(serves=["201", "202", "203", "204", "205", "206", "207", "208", "209"], nominal="12.5 ton packaged rooftop, 2004, west wing level 2, remains in service"),
}


def asbuilt_space(no):
    s = _drift(RECORD_BY[no])
    d = ASBUILT_DELTAS.get(no, {})
    for k, v in d.items():
        if k == "hint": continue
        if k in ("glass", "walls"): s[k].update(v)
        else: s[k] = v
    s["roof_assembly"] = ROOF_ASBUILT[s["level"]]
    return s


def space_loads(s, h):
    """Space sensible and latent load, W, at hour h: CLTD/SCL/CLF method with the District's tabulated factors."""
    n = s["people"]
    u_roof = ROOF_U[s["roof_assembly"]]
    sens = u_roof * s["roof"] * CLTD_ROOF[h]
    for o, a in s["walls"].items(): sens += U_WALL * a * CLTD_WALL[o][h]
    ag = sum(s["glass"].values())
    sens += U_GLASS * ag * (T_OUT[h] - M.T_ROOM)
    for o, a in s["glass"].items(): sens += a * SHGC[s["glz"]] * SCL[o][h]
    ps, pl = PEOPLE[s["cat"]]
    sens += n * ps + LIGHTS[s["cat"]] * s["area"] + s["equip"]
    lat = n * pl
    v = INFIL * (sum(s["walls"].values()) + ag)
    sens += M.CP_AIR * v * (T_OUT[h] - M.T_ROOM); lat += M.CL_AIR * v * (M.W_OA - M.W_ROOM)
    return sens, lat


def zone_airflow(s):
    """Scheduled zone supply airflow, L/s: peak sensible over the design hours at 13 C supply, up to 5 L/s."""
    qs = max(space_loads(s, h)[0] for h in HOURS)
    q = max(qs / (M.CP_AIR * (M.T_ROOM - M.T_SUPPLY)), M.MIN_ZONE_AIR * s["area"])
    return int(math.ceil(q / 5.0) * 5)


def block(spaces, oa):
    best = None
    for h in HOURS:
        S = L = 0.0
        for s in spaces:
            a, b = space_loads(s, h); S += a; L += b
        S += M.CP_AIR * oa * (T_OUT[h] - M.T_ROOM); L += M.CL_AIR * oa * (M.W_OA - M.W_ROOM)
        if best is None or S + L > best[0]: best = (S + L, S, L, h)
    return best[0] / 1000.0, best[1] / 1000.0, best[2] / 1000.0, best[3]


def verdict(t, s, l, cap):
    r = cap["net_total"] / t
    if r < BAND[0] or cap["net_sensible"] < s or cap["net_latent"] < l: return "reject_undersized"
    if r > BAND[1]: return "reject_oversized"
    return "accept"


# ---------------------------------------------------------------- the contractor's submittal (layer 1)
def contractor_space(no):
    s = copy.deepcopy(RECORD_BY[no])
    if s.get("shell"): s.update(SHELL_ASSUMED)
    return s


def _select(total):
    for m in M.MODELS:
        gt, gs, q = M.ahri_rating(m)
        if 1.0 <= gt / total <= BAND[1]:
            return m
    raise ValueError("no model for %.1f kW" % total)


def contractor():
    """The contractor's sheet: record inputs, shell with assumed loads, every scheduled room in the unit's zoning
    (server room included), outdoor air as the sum of the zone rates (Ev = 1), capacity at the AHRI rating point,
    gross. Zone airflows from record peak sensible loads at 13 C supply, scaled pro rata so the unit airflow sits
    inside the selected model's catalogue range."""
    out = {}
    for u in UNITS:
        sp = [contractor_space(s["no"]) for s in RECORD if s["unit"] == u]
        zq0 = {s["no"]: zone_airflow(s) for s in sp}
        oa = sum(OA[s["cat"]][0] * s["people"] + OA[s["cat"]][1] * s["area"] for s in sp)
        t, se, la, h = block(sp, oa)
        m = SELECTED.get(u) or _select(t)
        qs = sorted(M.CATALOG[m])
        q0 = sum(zq0.values())
        q = min(max(int(math.ceil(q0 / 25.0) * 25), qs[0]), qs[-1])
        zq = {no: int(round(v * q / q0 / 5.0) * 5) for no, v in zq0.items()}
        q = sum(zq.values())
        q = min(max(q, qs[0]), qs[-1])
        gt, gs, qr = M.ahri_rating(m)
        out[u] = dict(spaces=[s["no"] for s in sp], zone_airflow=zq, zone_airflow_peak=zq0, airflow=q, oa=oa, total=t,
                      sens=se, lat=la, hour=h, model=m, rated_total=gt, rated_sens=gs, ratio=gt / t)
    return out


SELECTED = {"RTU-1": "RTX-090", "RTU-2": "RTX-100", "RTU-3": "RTX-070", "RTU-4": "RTX-080", "RTU-5": "RTX-050",
            "RTU-6": "RTX-060", "RTU-7": "RTX-050"}
if os.environ.get("HV_NO_SELECT") != "1":
    _C = contractor()
    AIRFLOW = {u: _C[u]["airflow"] for u in UNITS}
    ZONE_AIRFLOW = {no: q for u in UNITS for no, q in _C[u]["zone_airflow"].items()}


# ---------------------------------------------------------------- the review
def review(space_fn, exclude_served=True):
    out = {}
    for u in UNITS:
        nos = [s["no"] for s in RECORD if s["unit"] == u]
        sp = [space_fn(n) for n in nos]
        if any(s.get("shell") for s in sp):
            out[u] = dict(verdict="undetermined", missing="tenant_fitout_loads"); continue
        if exclude_served: sp = [s for s in sp if not s.get("served_by")]
        zones = [dict(rp=OA[s["cat"]][0], ra=OA[s["cat"]][1], pz=s["people"], az=s["area"], vpz=ZONE_AIRFLOW[s["no"]]) for s in sp]
        vot, vou, ev, crit = M.ventilation(zones, vps=AIRFLOW[u])
        t, se, la, h = block(sp, vot)
        tm, wm, wbm = M.mix(vot, AIRFLOW[u])
        cap = M.capacity(SELECTED[u], AIRFLOW[u], wbm, tm)
        out[u] = dict(verdict=verdict(t, se, la, cap), outdoor_air_l_s=round(vot, 1), coil_entering_db_c=round(tm, 2),
                      coil_entering_wb_c=round(wbm, 2), block_total_kw=round(t, 2), block_sensible_kw=round(se, 2),
                      block_latent_kw=round(la, 2), net_capacity_total_kw=round(cap["net_total"], 2),
                      net_capacity_sensible_kw=round(cap["net_sensible"], 2), net_capacity_latent_kw=round(cap["net_latent"], 2),
                      ev=round(ev, 3), critical_zone=sp[crit]["no"], peak_hour=h, ratio=round(cap["net_total"] / t, 3))
    out["submittal"] = "approve" if all(v.get("verdict") == "accept" for v in out.values()) else "return_for_revision"
    return out


def truth():
    return review(asbuilt_space)


def record_review():
    return review(lambda n: copy.deepcopy(RECORD_BY[n]))


def verification(item):
    """What the facilities technician reports for an item: as-built inputs in the standard's terms."""
    kind, _, key = item.partition(":")
    if kind == "room" and key in RECORD_BY:
        s = asbuilt_space(key)
        r = dict(item=item, name=s["name"], level=s["level"], area_m2=s["area"],
                 occupants_current_layout=s["people"], use_category=s["cat"],
                 equipment_nameplate_w=s["equip"], exterior_walls_m2=s["walls"], glazing_m2=s["glass"],
                 glazing_type=s["glz"], roof_m2=s["roof"], roof_assembly=s["roof_assembly"],
                 served_by=s.get("served_by", "new RTU per submittal"))
        if s.get("shell"): r.update(occupants_current_layout=None, use_category=None, equipment_nameplate_w=None,
                                    note="shell space, unfinished, no fit-out")
        return r
    if kind == "roof" and key in ("L1", "L2"):
        lv = int(key[1]); return dict(item=item, roof_assembly=ROOF_ASBUILT[lv], u_value_w_m2k=ROOF_U[ROOF_ASBUILT[lv]])
    if kind == "unit" and key in EXISTING_UNITS:
        return dict(item=item, **EXISTING_UNITS[key])
    return None


def items():
    return [f"room:{s['no']}" for s in RECORD] + ["roof:L1", "roof:L2"] + [f"unit:{k}" for k in EXISTING_UNITS]


if __name__ == "__main__":
    R = record_review(); T = truth()
    for u in UNITS:
        print(u, SELECTED[u], "record", R[u].get("ratio"), R[u]["verdict"], "| as-built", T[u].get("block_total_kw"), T[u].get("ratio"), T[u]["verdict"])
    print(R["submittal"], T["submittal"])
