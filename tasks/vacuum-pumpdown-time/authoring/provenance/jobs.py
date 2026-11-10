"""Sealed definitions of the chambers and their jobs.

A chamber: its chamber sheet as issued (volume, roughing pump, roughing line, turbo pump, high-vacuum port conductance,
crossover pressure, gauges), its true wall gas load after an air vent (Q_w1 at 1 h and its decay exponent), its true
air leak, the dated changes of its equipment log, its past pump-down records (date, vent gas, load, length), its gauges'
calibration factors, and the job to be run in it (load and process pressure).

The truth of a chamber (truth()) is MS-VP's pump-down time for the job in the chamber as it is on the job's date: the
equipment after every change, the true wall gas load (of the chamber's current internals), the true air leak (since
the last door seal), the spool pieces' and the job load's outgassing from the shop's table, all integrated by vac.py."""
import math
import vac as V

# the shop's outgassing table after an air vent at 20 C: q1 mbar L/(s cm2) at 1 h, decay exponent alpha
OUTGAS = {
    "stainless steel, as machined": (2.6e-8, 1.0),
    "stainless steel, electropolished": (7.0e-9, 1.0),
    "stainless steel, bead blasted": (6.5e-8, 0.95),
    "aluminum, bare": (1.4e-8, 1.0),
    "aluminum, anodized": (5.5e-7, 0.85),
    "copper, bare": (2.2e-8, 1.0),
    "PEEK": (3.5e-7, 0.6),
    "graphite felt": (9.0e-7, 0.7),
}
N2_FACTOR = 0.25          # wall gas load after a dry nitrogen vent, relative to an air vent (true, not in the docs)
CC_WATER = 1.12           # cold cathode gauges: true / indicated for water vapor (documented)
CC_ON = 1e-2              # the cold cathode gauge is switched on below this, after the crossover
PIRANI_MIN = 5e-4


def load_surfaces(load):
    return [(a_m2 * 1e4,) + OUTGAS[mat] for _, mat, a_m2 in load]


def Ch(name, seed, sheet, wall, leak, events, records, job, certs):
    """sheet: dict(V L, rough, line (D mm, L m), turbo, C_hv L/s, p_x mbar, pirani, cc); wall: (Q_w1 mbar L/s at 1 h,
    alpha); leak: Q_L mbar L/s; events: [(date, kind, args)] with kinds turbo (model), rough (model), line (D mm, L m),
    crossover (p), spool (D mm, L mm), internals (new volume, new wall), seal (new leak), leak (new leak, not logged),
    merge (added volume, added wall gas load at 1 h), cc (new serial), pirani (new serial), note (routine text); records: [(date, vent gas, load, hours)]; job: dict(date, load, p_target);
    load: [(item, material, area m2)]."""
    return dict(name=name, seed=seed, sheet=sheet, wall=wall, leak=leak, events=sorted(events), records=records,
                job=job, certs=certs)


def config(ch, date, route=()):
    """The chamber's true equipment, volume, wall gas load and leak on a date (after the changes logged before it)."""
    s = ch["sheet"]
    c = dict(V=s["V"], rough=s["rough"], D=s["line"][0] / 10, L=s["line"][1] * 100, turbo=s["turbo"], C_hv=s["C_hv"],
             p_x=s["p_x"], pirani=s["pirani"], cc=s["cc"], wall=ch["wall"], leak=ch["leak"], spools=[])
    for d, kind, args in ch["events"]:
        if d > date:
            continue
        if kind == "turbo":
            c["turbo"] = args
        elif kind == "rough":
            c["rough"] = args
        elif kind == "line":
            c["D"], c["L"] = args[0] / 10, args[1] * 100
        elif kind == "crossover":
            c["p_x"] = args
        elif kind == "spool":
            Dm, Lm = args[0] / 1000, args[1] / 1000
            c["V"] += math.pi / 4 * Dm ** 2 * Lm * 1000
            c["spools"].append(math.pi * Dm * Lm * 1e4)
        elif kind == "internals":
            c["V"], c["wall"] = args[0], args[1]
        elif kind == "seal":
            c["leak"] = args
        elif kind == "leak":                                     # a leak that grew, not logged
            c["leak"] = args
        elif kind == "merge":                                    # a load lock merged into the chamber
            c["V"] += args[0]
            c["wall"] = (c["wall"][0] + args[1], c["wall"][1])
        elif kind == "cc":
            c["cc"] = args
        elif kind == "pirani":
            c["pirani"] = args
    return c


def gas_surfaces(c, load, vent="air"):
    Q1, a = c["wall"]
    f = 1.0 if vent == "air" else N2_FACTOR
    surf = [(1.0, Q1 * f, a)]                                     # the wall gas load as one "surface" of unit area
    surf += [(A,) + OUTGAS["stainless steel, as machined"] for A in c["spools"]]
    surf += load_surfaces(load)
    return surf


def truth(ch):
    j = ch["job"]
    c = config(ch, j["date"])
    return V.pumpdown(c["V"], c["rough"], c["D"], c["L"], c["turbo"], c["C_hv"], c["p_x"], c["leak"],
                      gas_surfaces(c, j["load"]), p_target=j["p_target"], t_end_h=12.0)


RACK = ("fixture rack", "stainless steel, as machined")
EXAMPLE = "chamber-ex"
CHAMBERS = [
    Ch("chamber-ex", 1,
       dict(V=1600, rough="DS-250", line=(63, 4.0), turbo="TMP-1100", C_hv=1400, p_x=0.05, pirani="PG-1101", cc="CC-2101"),
       wall=(4.0e-3, 1.0), leak=3e-6, events=[("2026-01-20", "note", "Door seal inspected: no damage.")],
       records=[("2026-02-03", "air", [], 3.0), ("2026-02-17", "air", [], 3.0), ("2026-03-03", "air", [], 3.0),
                ("2026-03-17", "air", [], 3.0)],
       job=dict(date="2026-04-07", load=[RACK + (2.0,), ("lens holders", "aluminum, anodized", 0.35)], p_target=1e-5),
       certs={"PG-1101": 1.00, "CC-2101": 1.00}),
    # cold cathode gauge changed (records name it); internals rebuilt; some records after a nitrogen vent
    Ch("optics-coater", 11,
       dict(V=2400, rough="DS-250", line=(63, 5.0), turbo="TMP-1600", C_hv=2200, p_x=0.05, pirani="PG-1131", cc="CC-2131"),
       wall=(1.6e-2, 0.75), leak=5e-6,
       events=[("2026-01-12", "internals", (2150, (6.0e-3, 1.0), "planetary drive and heat shields replaced")),
               ("2026-02-20", "cc", "CC-2190"), ("2026-03-02", "note", "Quartz crystal monitor head cleaned.")],
       records=[("2025-12-10", "air", [], 3.0), ("2026-01-27", "air", [], 3.0), ("2026-02-09", "nitrogen", [], 3.0),
                ("2026-03-04", "air", [], 3.0), ("2026-03-18", "nitrogen", [], 3.0), ("2026-03-31", "air", [], 3.0)],
       job=dict(date="2026-04-14", load=[("lens rack", "aluminum, anodized", 0.6), RACK + (1.5,)], p_target=4e-6),
       certs={"PG-1131": 1.00, "CC-2131": 1.00, "CC-2190": 0.74}),
    # the controller's crossover changed (records report it); records with a load; internals rebuilt
    Ch("braze-furnace", 12,
       dict(V=900, rough="RV-65", line=(40, 6.0), turbo="TMP-700", C_hv=900, p_x=0.05, pirani="PG-1142", cc="CC-2142"),
       wall=(2.4e-2, 0.6), leak=2e-5, events=[("2026-01-25", "internals", (1020, (6.0e-3, 0.9), "graphite felt heat shields replaced by molybdenum shields")),
                                            ("2026-03-01", "note", "Thermocouple TC3 replaced.")],
       records=[("2026-01-08", "air", [], 3.0), ("2026-02-05", "air", [("brazing fixture", "stainless steel, bead blasted", 2.2)], 3.0),
                ("2026-02-26", "air", [("brazing fixture", "stainless steel, bead blasted", 2.2)], 3.0),
                ("2026-03-12", "air", [], 3.0), ("2026-03-26", "air", [("brazing fixture", "stainless steel, bead blasted", 2.2)], 3.0)],
       job=dict(date="2026-04-09", load=[("brazing fixture", "stainless steel, bead blasted", 1.2), ("heat exchanger cores", "aluminum, bare", 2.5)], p_target=2.5e-5),
       certs={"PG-1142": 1.00, "CC-2142": [("2025-10-06", 1.00), ("2026-03-20", 0.80)]}),
    # turbo exchanged for another model (records name it); roughing line rerouted
    Ch("sputter-bay", 13,
       dict(V=3200, rough="DS-400", line=(80, 3.0), turbo="TMP-1600", C_hv=2600, p_x=0.05, pirani="PG-1153", cc="CC-2153"),
       wall=(7.5e-3, 1.0), leak=4e-6,
       events=[("2026-01-20", "crossover", 0.2), ("2026-02-03", "merge", (900, 1.2e-3)), ("2026-02-23", "line", (63, 9.5)),
               ("2026-03-05", "note", "Target 2 replaced.")],
       records=[("2026-01-14", "air", [], 3.0), ("2026-01-28", "air", [], 3.0), ("2026-02-11", "air", [], 3.0),
                ("2026-03-11", "air", [], 3.0), ("2026-03-25", "air", [], 3.0)],
       job=dict(date="2026-04-08", load=[("substrate carriers", "aluminum, bare", 4.0)], p_target=1e-4),
       certs={"PG-1153": 1.00, "CC-2153": 1.00}),
    # gauge changed; door seal replaced (the old records carry a leak)
    Ch("thermal-vac", 14,
       dict(V=5200, rough="DS-400", line=(100, 6.0), turbo="TMP-1600", C_hv=2400, p_x=0.05, pirani="PG-1164", cc="CC-2164"),
       wall=(1.1e-2, 1.0), leak=1.2e-3,
       events=[("2026-02-16", "seal", 6e-6), ("2026-02-16", "cc", "CC-2177"), ("2026-03-24", "turbo", "TMP-1100"),
               ("2026-03-12", "note", "Shroud LN2 valve serviced.")],
       records=[("2026-01-13", "air", [], 4.0), ("2026-01-27", "air", [], 4.0), ("2026-02-10", "air", [], 4.0),
                ("2026-02-24", "air", [], 4.0), ("2026-03-17", "air", [], 4.0), ("2026-03-31", "air", [], 4.0)],
       job=dict(date="2026-04-15", load=[("test article", "aluminum, bare", 6.0), ("harness", "PEEK", 0.4)], p_target=6e-6),
       certs={"PG-1164": 1.00, "CC-2164": 1.00, "CC-2177": 1.21}),
    # crossover changed; spool piece; roughing line rerouted
    Ch("tool-coater", 15,
       dict(V=1400, rough="DS-160", line=(80, 3.0), turbo="TMP-1100", C_hv=1500, p_x=0.05, pirani="PG-1175", cc="CC-2175"),
       wall=(4.5e-3, 1.0), leak=3e-6,
       events=[("2026-02-09", "crossover", 0.01), ("2026-02-02", "merge", (420, 6e-4)), ("2026-03-30", "spool", (400, 1500)),
               ("2026-03-30", "line", (63, 9.0)),
               ("2026-03-10", "note", "Heater H2 contactor replaced.")],
       records=[("2026-01-21", "air", [], 3.0), ("2026-02-18", "air", [], 3.0), ("2026-03-04", "air", [], 3.0),
                ("2026-03-18", "air", [], 3.0)],
       job=dict(date="2026-04-13", load=[("tool fixtures", "stainless steel, as machined", 1.2)], p_target=1e-4),
       certs={"PG-1175": 1.00, "CC-2175": 1.00}),
    # turbo exchanged for another model; spool piece
    Ch("space-sim", 16,
       dict(V=6500, rough="DS-400", line=(100, 5.0), turbo="TMP-1100", C_hv=1800, p_x=0.05, pirani="PG-1186", cc="CC-2186"),
       wall=(6.0e-3, 0.95), leak=8e-6,
       events=[("2026-02-12", "turbo", "TMP-700"), ("2026-03-28", "spool", (500, 2000)), ("2026-03-02", "note", "Viewport 3 cleaned.")],
       records=[("2026-01-07", "air", [], 4.0), ("2026-01-21", "air", [], 4.0), ("2026-02-04", "air", [], 4.0),
                ("2026-03-04", "air", [], 4.0, "thermal-vac"), ("2026-03-18", "air", [], 4.0)],
       job=dict(date="2026-04-16", load=[("test article", "aluminum, bare", 4.5)], p_target=1e-5),
       certs={"PG-1186": 1.00, "CC-2186": [("2025-10-09", 1.00), ("2026-03-01", 0.82)]}),
    # records with a load; door seal replaced; some records after a nitrogen vent
    Ch("lens-coater", 17,
       dict(V=1900, rough="DS-250", line=(63, 4.5), turbo="TMP-1100", C_hv=1600, p_x=0.05, pirani="PG-1197", cc="CC-2197"),
       wall=(5.0e-3, 1.0), leak=9e-4,
       events=[("2026-02-23", "seal", 4e-6), ("2026-03-04", "note", "Electron gun filament replaced.")],
       records=[("2026-01-19", "air", [("lens rack", "aluminum, anodized", 0.5)], 3.0), ("2026-02-02", "nitrogen", [], 3.0),
                ("2026-02-16", "air", [], 3.0), ("2026-03-02", "air", [("lens rack", "aluminum, anodized", 0.5)], 3.0),
                ("2026-03-09", "air", [], 3.0, "braze-furnace"), ("2026-03-16", "nitrogen", [], 3.0),
                ("2026-03-30", "air", [("lens rack", "aluminum, anodized", 0.5)], 3.0)],
       job=dict(date="2026-04-13", load=[("lens rack", "aluminum, anodized", 0.5), ("lens rack", "aluminum, anodized", 0.5)], p_target=6e-6),
       certs={"PG-1197": 1.00, "CC-2197": 1.00}),
]
BY = {c["name"]: c for c in CHAMBERS}
HIDDEN = [c["name"] for c in CHAMBERS if c["name"] != EXAMPLE]
