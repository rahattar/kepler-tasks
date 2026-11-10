"""Sealed definition of the project and the owner's review method: spaces, units, the design standard's
tables, the catalogue, the contractor's zoning and selections, and the record review. Everything the shipped files say
is generated from here (write_files.py); the grader recomputes the truth from here, never from the files."""
import json

# ---------------------------------------------------------------- owner's design standard (method)
HOURS = [10, 13, 15, 17]
T_OUT = {10: 28.0, 13: 31.5, 15: 33.0, 17: 32.0}          # C
T_IN, W_IN, W_OUT = 24.0, 0.0093, 0.0160                 # C, kg/kg
CLTD_ROOF = {10: 9.0, 13: 22.0, 15: 29.0, 17: 28.0}       # K
CLTD_WALL = {"N": {10: 3.0, 13: 6.0, 15: 8.0, 17: 9.0},
             "E": {10: 12.0, 13: 15.0, 15: 14.0, 17: 12.0},
             "S": {10: 5.0, 13: 12.0, 15: 14.0, 17: 13.0},
             "W": {10: 4.0, 13: 7.0, 15: 12.0, 17: 17.0}}
SCL = {"N": {10: 40.0, 13: 45.0, 15: 42.0, 17: 36.0},    # W/m2 through single clear, times SHGC
       "E": {10: 420.0, 13: 150.0, 15: 70.0, 17: 40.0},
       "S": {10: 180.0, 13: 300.0, 15: 220.0, 17: 90.0},
       "W": {10: 45.0, 13: 110.0, 15: 330.0, 17: 460.0}}
U_WALL, U_ROOF, U_GLASS = 0.45, 0.25, 2.8                 # W/m2 K
SHGC = {"standard": 0.40, "low-e": 0.27}
INFIL = 0.15                                              # L/s per m2 of exterior wall and glass
PEOPLE = {"office": (75.0, 55.0), "conference": (75.0, 55.0), "training": (75.0, 55.0),
          "corridor": (75.0, 55.0), "storage": (75.0, 55.0), "break": (75.0, 55.0), "lab": (75.0, 55.0),
          "assembly": (70.0, 45.0)}
LIGHTS = {"office": 9.0, "conference": 11.0, "training": 11.0, "corridor": 6.0, "storage": 5.0,
          "break": 9.0, "lab": 14.0, "assembly": 11.0}
OA = {"office": (2.5, 0.3), "conference": (2.5, 0.3), "training": (5.0, 0.6), "corridor": (0.0, 0.3),
      "storage": (0.0, 0.6), "break": (2.5, 0.6), "lab": (5.0, 0.9), "assembly": (3.8, 0.3)}   # L/s per person, per m2
BAND = (1.00, 1.25)                                       # net total capacity / block total load
DESIGN_DB = 33.0                                          # catalogue column for the review
EWB = 19.4

# ---------------------------------------------------------------- catalogue (gross, kW, at EWB 19.4 C, rated airflow)
# model: nominal tons, airflow L/s, fan motor heat kW, {outdoor DB: (gross total, gross sensible)}
CATALOG = {
    "RTX-04": (4, 750, 0.75, {30: (14.9, 11.1), 33: (14.3, 10.8), 35: (13.9, 10.6), 38: (13.3, 10.3)}),
    "RTX-05": (5, 940, 0.95, {30: (18.6, 13.8), 33: (17.9, 13.5), 35: (17.4, 13.2), 38: (16.6, 12.8)}),
    "RTX-06": (6, 1130, 1.15, {30: (22.3, 16.5), 33: (21.4, 16.1), 35: (20.8, 15.8), 38: (19.9, 15.3)}),
    "RTX-07": (7.5, 1410, 1.50, {30: (27.8, 21.3), 33: (26.7, 20.8), 35: (26.0, 20.4), 38: (24.8, 19.8)}),
    "RTX-08": (8.5, 1600, 1.70, {30: (31.6, 24.1), 33: (30.4, 23.6), 35: (29.6, 23.1), 38: (28.3, 22.4)}),
    "RTX-10": (10, 1880, 2.10, {30: (37.2, 27.5), 33: (35.8, 26.9), 35: (34.8, 26.4), 38: (33.3, 25.6)}),
    "RTX-12": (12.5, 2350, 2.70, {30: (46.5, 34.4), 33: (44.7, 33.6), 35: (43.5, 33.0), 38: (41.6, 32.0)}),
    "RTX-15": (15, 2820, 3.30, {30: (55.8, 41.3), 33: (53.7, 40.4), 35: (52.2, 39.6), 38: (49.9, 38.4)}),
    "RTX-17": (17.5, 3290, 3.90, {30: (65.1, 48.2), 33: (62.6, 47.1), 35: (60.9, 46.2), 38: (58.2, 44.8)}),
    "RTX-20": (20, 3760, 4.50, {30: (74.4, 55.1), 33: (71.6, 53.8), 35: (69.6, 52.8), 38: (66.5, 51.2)}),
    "RTX-25": (25, 4700, 5.70, {30: (93.0, 68.8), 33: (89.5, 67.3), 35: (87.0, 66.0), 38: (83.1, 64.0)}),
}

# ---------------------------------------------------------------- spaces
# fields: no, name, level, area m2, people, category, equipment W, walls {orient: m2}, glass {orient: m2},
# roof m2, glazing type, unit, flags
SPACES = [
    # RTU-1: level 1 east wing (trap: 118 served by existing AC-1 split system, to remain)
    dict(no="110", name="Open office", level=1, area=180.0, people=16, cat="office", equip=2400,
         walls={"E": 30.0, "N": 24.0}, glass={"E": 18.0, "N": 8.0}, roof=0.0, glz="standard", unit="RTU-1"),
    dict(no="112", name="Office", level=1, area=14.0, people=1, cat="office", equip=250,
         walls={"E": 9.0}, glass={"E": 4.0}, roof=0.0, glz="standard", unit="RTU-1"),
    dict(no="114", name="Office", level=1, area=14.0, people=1, cat="office", equip=250,
         walls={"E": 9.0}, glass={"E": 4.0}, roof=0.0, glz="standard", unit="RTU-1"),
    dict(no="116", name="Conference", level=1, area=36.0, people=12, cat="conference", equip=600,
         walls={"N": 18.0}, glass={"N": 6.0}, roof=0.0, glz="standard", unit="RTU-1"),
    dict(no="118", name="Server room", level=1, area=22.0, people=0, cat="office", equip=8000,
         walls={}, glass={}, roof=0.0, glz="standard", unit="RTU-1", existing="AC-1"),
    dict(no="119", name="Corridor", level=1, area=48.0, people=0, cat="corridor", equip=0,
         walls={}, glass={}, roof=0.0, glz="standard", unit="RTU-1"),
    # RTU-2: level 2 north wing (trap: 212 occupancy 48 per Addendum 2, schedule body says 24)
    dict(no="210", name="Open office", level=2, area=150.0, people=14, cat="office", equip=2100,
         walls={"N": 36.0}, glass={"N": 14.0}, roof=150.0, glz="standard", unit="RTU-2"),
    dict(no="212", name="Training room", level=2, area=96.0, people=20, cat="training", equip=1500,
         walls={"N": 30.0, "W": 24.0}, glass={"N": 10.0, "W": 10.0}, roof=96.0, glz="standard", unit="RTU-2",
         people_addendum=48),
    dict(no="214", name="Break room", level=2, area=30.0, people=8, cat="break", equip=1800,
         walls={"W": 15.0}, glass={"W": 5.0}, roof=30.0, glz="standard", unit="RTU-2"),
    dict(no="215", name="Corridor", level=2, area=40.0, people=0, cat="corridor", equip=0,
         walls={}, glass={}, roof=40.0, glz="standard", unit="RTU-2"),
    # RTU-3: level 2 east and west perimeter offices (trap: block at the coincident hour, not sum of peaks)
    dict(no="220", name="Office", level=2, area=16.0, people=1, cat="office", equip=300,
         walls={"E": 10.0}, glass={"E": 6.0}, roof=16.0, glz="standard", unit="RTU-3"),
    dict(no="221", name="Office", level=2, area=16.0, people=1, cat="office", equip=300,
         walls={"E": 10.0}, glass={"E": 6.0}, roof=16.0, glz="standard", unit="RTU-3"),
    dict(no="222", name="Office", level=2, area=16.0, people=1, cat="office", equip=300,
         walls={"E": 10.0}, glass={"E": 6.0}, roof=16.0, glz="standard", unit="RTU-3"),
    dict(no="223", name="Shared office", level=2, area=42.0, people=4, cat="office", equip=900,
         walls={"E": 20.0}, glass={"E": 15.0}, roof=42.0, glz="standard", unit="RTU-3"),
    dict(no="230", name="Office", level=2, area=16.0, people=1, cat="office", equip=300,
         walls={"W": 10.0}, glass={"W": 6.0}, roof=16.0, glz="standard", unit="RTU-3"),
    dict(no="231", name="Office", level=2, area=16.0, people=1, cat="office", equip=300,
         walls={"W": 10.0}, glass={"W": 6.0}, roof=16.0, glz="standard", unit="RTU-3"),
    dict(no="232", name="Office", level=2, area=16.0, people=1, cat="office", equip=300,
         walls={"W": 10.0}, glass={"W": 6.0}, roof=16.0, glz="standard", unit="RTU-3"),
    dict(no="233", name="Shared office", level=2, area=42.0, people=4, cat="office", equip=900,
         walls={"W": 20.0}, glass={"W": 15.0}, roof=42.0, glz="standard", unit="RTU-3"),
    dict(no="225", name="Corridor", level=2, area=60.0, people=0, cat="corridor", equip=0,
         walls={}, glass={}, roof=60.0, glz="standard", unit="RTU-3"),
    # RTU-4: addition, open office (trap: net capacity, not gross)
    dict(no="150", name="Open office (addition)", level=1, area=240.0, people=32, cat="office", equip=4700,
         walls={"S": 36.0, "W": 30.0}, glass={"S": 20.0, "W": 12.0}, roof=240.0, glz="low-e", unit="RTU-4"),
    dict(no="152", name="Huddle", level=1, area=18.0, people=4, cat="conference", equip=400,
         walls={"W": 12.0}, glass={"W": 4.0}, roof=18.0, glz="low-e", unit="RTU-4"),
    dict(no="153", name="Huddle", level=1, area=18.0, people=4, cat="conference", equip=400,
         walls={"W": 12.0}, glass={"W": 4.0}, roof=18.0, glz="low-e", unit="RTU-4"),
    # RTU-5: shell tenant space (trap: undetermined; fit-out by others)
    dict(no="130", name="Tenant space (shell)", level=1, area=210.0, people=None, cat=None, equip=None,
         walls={"S": 40.0, "E": 24.0}, glass={"S": 16.0, "E": 10.0}, roof=210.0, glz="low-e", unit="RTU-5", shell=True),
    # RTU-6: lab wing, level 1 (clean)
    dict(no="160", name="Teaching lab", level=1, area=110.0, people=20, cat="lab", equip=1800,
         walls={"N": 30.0}, glass={"N": 12.0}, roof=110.0, glz="standard", unit="RTU-6"),
    dict(no="161", name="Lab prep", level=1, area=28.0, people=2, cat="lab", equip=1200,
         walls={"N": 12.0}, glass={"N": 3.0}, roof=28.0, glz="standard", unit="RTU-6"),
    dict(no="162", name="Storage", level=1, area=20.0, people=0, cat="storage", equip=0,
         walls={}, glass={}, roof=20.0, glz="standard", unit="RTU-6"),
    dict(no="163", name="Office", level=1, area=14.0, people=1, cat="office", equip=250,
         walls={"N": 9.0}, glass={"N": 3.0}, roof=14.0, glz="standard", unit="RTU-6"),
    # RTU-7: south wing, level 1 (trap: 140 deleted by Addendum 1, struck through in the room schedule)
    dict(no="140", name="Multipurpose room", level=1, area=140.0, people=70, cat="assembly", equip=1500,
         walls={"S": 36.0}, glass={"S": 20.0}, roof=140.0, glz="standard", unit="RTU-7", deleted=True),
    dict(no="142", name="Office", level=1, area=14.0, people=1, cat="office", equip=250,
         walls={"S": 9.0}, glass={"S": 4.0}, roof=14.0, glz="standard", unit="RTU-7"),
    dict(no="143", name="Office", level=1, area=14.0, people=1, cat="office", equip=250,
         walls={"S": 9.0}, glass={"S": 4.0}, roof=14.0, glz="standard", unit="RTU-7"),
    dict(no="144", name="Conference", level=1, area=40.0, people=14, cat="conference", equip=600,
         walls={"S": 18.0}, glass={"S": 8.0}, roof=40.0, glz="standard", unit="RTU-7"),
    dict(no="145", name="Workroom", level=1, area=36.0, people=3, cat="office", equip=1800,
         walls={"S": 12.0}, glass={"S": 4.0}, roof=36.0, glz="standard", unit="RTU-7"),
    dict(no="146", name="Corridor", level=1, area=44.0, people=0, cat="corridor", equip=0,
         walls={}, glass={}, roof=44.0, glz="standard", unit="RTU-7"),
]
UNITS = ["RTU-1", "RTU-2", "RTU-3", "RTU-4", "RTU-5", "RTU-6", "RTU-7"]
# contractor's selections
SELECTED = {"RTU-1": "RTX-08", "RTU-2": "RTX-10", "RTU-3": "RTX-08", "RTU-4": "RTX-07", "RTU-5": "RTX-05",
            "RTU-6": "RTX-06", "RTU-7": "RTX-12"}
# contractor's assumed values for the shell space
SHELL_ASSUMED = dict(people=26, cat="office", equip=3000)


def space_loads(s, h, people=None):
    """Sensible and latent load (W) of one space at hour h per the standard."""
    n = s["people"] if people is None else people
    sens = U_ROOF * s["roof"] * CLTD_ROOF[h]
    for o, a in s["walls"].items():
        sens += U_WALL * a * CLTD_WALL[o][h]
    ag = sum(s["glass"].values())
    sens += U_GLASS * ag * (T_OUT[h] - T_IN)
    for o, a in s["glass"].items():
        sens += a * SHGC[s["glz"]] * SCL[o][h]
    ps, pl = PEOPLE[s["cat"]]
    sens += n * ps + LIGHTS[s["cat"]] * s["area"] + s["equip"]
    lat = n * pl
    v = INFIL * (sum(s["walls"].values()) + ag)
    sens += 1.2 * v * (T_OUT[h] - T_IN)
    lat += 3000.0 * v * (W_OUT - W_IN)
    return sens, lat


def outdoor_air(s, people=None):
    n = s["people"] if people is None else people
    rp, ra = OA[s["cat"]]
    return rp * n + ra * s["area"]


def block(spaces, people_override=None):
    """Block load of a set of spaces: max over hours of total (space + ventilation), kW; returns
    (total, sensible, hour, oa L/s)."""
    po = people_override or {}
    oa = sum(outdoor_air(s, po.get(s["no"])) for s in spaces)
    best = None
    for h in HOURS:
        S = L = 0.0
        for s in spaces:
            a, b = space_loads(s, h, po.get(s["no"])); S += a; L += b
        S += 1.2 * oa * (T_OUT[h] - T_IN); L += 3000.0 * oa * (W_OUT - W_IN)
        if best is None or S + L > best[0]:
            best = (S + L, S, h)
    return best[0] / 1000.0, best[1] / 1000.0, best[2], oa


def capacity(model, net=True, db=DESIGN_DB):
    tons, air, fan, tab = CATALOG[model]
    gt, gs = tab[db]
    return (gt - fan, gs - fan) if net else (gt, gs)


def verdict(total, sens, cap_t, cap_s):
    r = cap_t / total
    if r < BAND[0] or cap_s < sens: return "reject_undersized"
    if r > BAND[1]: return "reject_oversized"
    return "accept"


def truth():
    out = {}
    for u in UNITS:
        sp = [s for s in SPACES if s["unit"] == u and not s.get("existing") and not s.get("deleted")]
        if any(s.get("shell") for s in sp):
            out[u] = dict(verdict="undetermined", missing="tenant_fitout_loads"); continue
        po = {s["no"]: s["people_addendum"] for s in sp if "people_addendum" in s}
        t, se, h, oa = block(sp, po)
        ct, cs = capacity(SELECTED[u])
        out[u] = dict(block_total_kw=round(t, 2), block_sensible_kw=round(se, 2), net_capacity_total_kw=round(ct, 2),
                      net_capacity_sensible_kw=round(cs, 2), verdict=verdict(t, se, ct, cs), peak_hour=h, oa_l_s=round(oa, 1),
                      ratio=round(ct / t, 3))
    out["submittal"] = "approve" if all(v.get("verdict") == "accept" for v in out.values()) else "return_for_revision"
    return out


def contractor():
    """What the contractor's sheet shows: every space as listed (existing and deleted included), shell space
    with assumed loads, 212 at 24 people, each space at its own peak hour summed, gross capacity."""
    out = {}
    for u in UNITS:
        sp = [dict(s) for s in SPACES if s["unit"] == u]
        for s in sp:
            if s.get("shell"): s.update(SHELL_ASSUMED)
        rows = []
        for s in sp:
            best = max(((sum(space_loads(s, h)), h) for h in HOURS))
            S, L = space_loads(s, best[1])
            rows.append(dict(no=s["no"], peak=best[1], sens=S, lat=L, oa=outdoor_air(s)))
        oa = sum(r["oa"] for r in rows)
        S = sum(r["sens"] for r in rows) + 1.2 * oa * (T_OUT[15] - T_IN)
        L = sum(r["lat"] for r in rows) + 3000.0 * oa * (W_OUT - W_IN)
        gt, gs = capacity(SELECTED[u], net=False)
        out[u] = dict(rows=rows, total=(S + L) / 1000, sens=S / 1000, oa=oa, gross_total=gt, gross_sens=gs,
                      ratio=gt / ((S + L) / 1000))
    return out


if __name__ == "__main__":
    t = truth(); c = contractor()
    for u in UNITS:
        print(u, SELECTED[u], "truth", {k: v for k, v in t[u].items()}, "| contractor total %.1f ratio %.3f" % (c[u]["total"], c[u]["ratio"]))
    print(t["submittal"])
