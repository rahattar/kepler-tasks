"""Write the agent's records from the sealed definition and the seed.

    python3 gen.py <data directory> [seed]

With no seed it takes the one in seed.json beside it. The documents are fixed text; the tables come from
unit3.build(seed), and the dial readings from a second stream seeded one above it.
"""
import csv, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import unit3 as M

def wcsv(path, head, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows)

PROC = """# AP-12 Shaft alignment at turnaround

## 1. Scope
Every coupled train is left so that, at its running condition, the movable machine's shaft lies on the
stationary machine's shaft within section 7. The movable machine is the driver. Moves are made at the
movable machine's feet only.

## 2. Reading a dial sheet
The fitters use the reverse indicator method. Two rim readings are taken with both shafts turned together:

- SM: bracket clamped to the stationary shaft, indicator on the rim of the movable machine's hub;
- MS: bracket clamped to the movable shaft, indicator on the rim of the stationary machine's hub.

Indicators are zeroed at top and read at right, bottom and left, stem in positive. Right and left are as seen
standing at the movable machine and looking at the stationary machine. The two hubs' reading planes are the
sheet's span apart. Both brackets of a kit carry the same bar set.

With y the height and z the rightward position of the movable shaft's centreline relative to the stationary
shaft's centreline, a sag-free SM reading gives at the movable hub's plane y = -B/2 and z = (R - L)/2, and a
sag-free MS reading gives at the stationary hub's plane y = +B/2 and z = (L - R)/2. Between and beyond the two
planes the centreline is straight.

## 3. Bracket sag
A bracket droops under its own weight, and the droop is in every rim reading: the bottom reading carries the
whole of the set's mandrel bottom reading and each side reading half of it. Every rim reading is corrected for
it before use, by subtracting the mandrel reading from the bottom reading and half of it from each side. The
mandrel reading of each bar set is on its sag card. Which bar set a kit uses at a given span is in the kit
leaflets. Which kit a fitter had is in the tool crib log.

## 4. Feet
The register gives, for each train, the distance from the movable hub's reading plane to the movable machine's
front feet and from its front feet to its rear feet. A shim change raises (+) or lowers (-) a pair of feet; a
lateral move takes them right (+) or left (-), in the sense of section 2.

## 5. Running position
A machine's shaft does not run where it sits cold. The alignment is set cold so that the shafts are in line
running. Each machine's shaft moves from cold to running by a rise and a lateral shift, the same along its length:

- motors, pumps, fans: rise = 11.5e-6 per K x the shaft height above the base x (the temperature of the
  machine's supports with the machine running as it now runs, minus ambient at the time of the readings); no
  lateral shift;
- gearboxes: the maker's running position figure for the model, a rise and a lateral shift to the right in
  the sense of section 2;
- steam turbines: the figure from a hot check on that machine. A hot check describes the machine as it then
  stood; work on its casing supports or on the piping connected to it ends it. One turbine's figure is not
  another's.

## 6. Laser alignment visits
The laser contractor is on site for this turnaround with time for {budget} trains. `/app/data/docs/laser_service.md`
says what a visit gives and how one is ordered.

## 7. Acceptance
A train is aligned when, running, the movable shaft's centreline is within {tol:.2f} mm of the stationary shaft's
at both hubs' reading planes, in height and sideways.
"""

LEAF = """# Dial bracket kits

| kit | bought | bar sets |
|---|---|---|
| A | 2019 | set 1 for spans up to 160 mm, set 2 above 160 and up to 320 mm, set 3 above 320 mm |
| B | 2021 | set 1 for spans up to 160 mm, set 2 above 160 and up to 320 mm, set 3 above 320 mm |
| C | August 2026 | set 1 for spans up to 160 mm, set 2 above 160 and up to 320 mm, set 3 above 320 mm |

A sheet's span is the distance between the two hubs' reading planes. A fitter takes the set for the span and no other.
"""

LASER = """# Laser alignment service

The contractor measures one train a visit, with the coupling made up and the machine cold, and leaves the heads
on through the start-up and until the train is at its running condition.

The contractor has time for {budget} trains at this turnaround and plans the whole programme before coming to site.
Place it in one order, naming every train to be visited:

    laservisit <tag> <tag> <tag> <tag> <tag> <tag>

The order is taken once. No train is added or changed afterwards, and the contractor does not return to a train.
Each report is written to `/app/laser_reports/<tag>.csv` and gives, in mm:

- `y_stationary_plane`, `y_movable_plane`, `z_stationary_plane`, `z_movable_plane`: the cold position of the
  movable shaft's centreline relative to the stationary shaft's, at the two hubs' reading planes, in the sense
  of AP-12 section 2;
- `stationary_rise`, `stationary_lateral`, `movable_rise`, `movable_lateral`: how far each machine's shaft moved
  from cold to running.

The laser carries no bracket and has no sag.
"""

CLOSE = """# Unit 3 revamp: mechanical close-out, September 2026

1. **Process.** The revamp raised the fired heater's outlet and re-arranged the pumparound and product rundown
   heat exchange. Pumped temperatures at the new operating case are in `process_conditions.csv`. The boiler feed
   water, cooling water and condensate systems were outside the revamp.
2. **Personnel protection.** The casings and bearing pedestals of the pumps on the programme were lagged to
   specification PP-2. The pumps done are in the work orders.
3. **Water saving.** Cooling water to pump pedestal jackets was withdrawn: supply and return blanked, jackets
   drained. The pumps done are in the work orders.
4. **Drivers.** No motor was changed or re-rated. The gas compressors and their gearboxes were not in the revamp.
"""

def main(out, seed=None):
    if seed is None:
        seed = json.load(open(os.path.join(HERE, "seed.json")))["seed"]
    T = M.build(seed); rng = random.Random(seed + 1)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    open(os.path.join(out, "docs", "alignment_procedure.md"), "w").write(PROC.format(budget=M.BUDGET, tol=M.TOL))
    open(os.path.join(out, "docs", "kit_leaflets.md"), "w").write(LEAF)
    open(os.path.join(out, "docs", "laser_service.md"), "w").write(LASER.format(budget=M.BUDGET))
    open(os.path.join(out, "docs", "revamp_closeout.md"), "w").write(CLOSE)

    def service(t):
        if t["kind"] == "comp": return "process gas compressor"
        if t["kind"] == "turb": return "boiler feed water pump"
        if t["kind"] == "fan": return "air cooler fan"
        if t["model"] == "WP-100": return "cooling water pump" if t["tpnow"] < 40 else "condensate pump"
        names = ["pumparound pump", "heater charge pump", "bottoms pump", "product rundown pump", "hot oil pump", "side stripper pump"]
        if t["tag"].startswith("P-32"): return "pumparound pump"
        return names[sum(ord(ch) for ch in t["tag"].rstrip("AB")) % len(names)]
    def stat(t):
        return {"comp": "gearbox GR-800", "fan": "fan"}.get(t["kind"], "pump %s" % t["model"])
    reg = sorted([[t["tag"], service(t), t["crit"], "steam turbine" if t["kind"] == "turb" else "motor", stat(t), t["speed"],
                   "%.0f" % t["a"], "%.0f" % t["b"], "%.0f" % t["h_mov"], "%.0f" % t["h_stat"]] for t in T.values()])
    wcsv(os.path.join(out, "train_register.csv"),
         ["tag", "service", "criticality", "movable_machine", "stationary_machine", "speed_rpm",
          "hub_plane_to_front_feet_mm", "front_to_rear_feet_mm", "movable_shaft_height_mm", "stationary_shaft_height_mm"], reg)
    wcsv(os.path.join(out, "pump_data.csv"), ["model", "casing_support", "bearing_pedestal", "maker"],
         [[m, M.BUILD[c][0], M.BUILD[c][1], "as built"] for m, c in sorted(M.MODELS.items())])

    sheets = []
    for t in T.values():
        sm, ms = M.readings(t, rng)
        sheets.append([t["date"], t["tag"], t["fitter"], "%.0f" % t["span"], "%.0f" % t["amb"]]
                      + ["%.2f" % v for v in sm] + ["%.2f" % v for v in ms])
    sheets.sort(); sheets = [["DS-%03d" % (i + 1)] + r for i, r in enumerate(sheets)]
    wcsv(os.path.join(out, "dial_sheets.csv"),
         ["sheet", "date", "tag", "fitter", "span_mm", "ambient_C", "SM_top", "SM_right", "SM_bottom", "SM_left",
          "MS_top", "MS_right", "MS_bottom", "MS_left"], sheets)
    wcsv(os.path.join(out, "tool_crib_log.csv"), ["kit", "issued_to", "out", "returned"],
         sorted([[k, f, a, b] for k, f, a, b in M.CRIB], key=lambda r: (r[2], r[0])))
    wcsv(os.path.join(out, "sag_cards.csv"), ["kit", "bar_set", "carded", "mandrel_bottom_reading_mm"],
         [[k, b, M.CARD_DATE[k], "%.2f" % (-2 * s)] for (k, b), s in sorted(M.SAG.items())])
    wcsv(os.path.join(out, "support_temperature_survey.csv"),
         ["tag", "surveyed", "movable_support_C", "stationary_support_C", "pumped_temperature_C", "method"],
         sorted([[t["tag"], "2019-06-%02d" % rng.randrange(3, 28), "%.0f" % t["t_mov"], "%.0f" % t["t_stat19"],
                  "" if t["tp19"] is None else "%.0f" % t["tp19"], "contact thermometer, unit at normal rates, referred to 25 C ambient"]
                 for t in T.values()]))
    wcsv(os.path.join(out, "process_conditions.csv"), ["tag", "pumped_temperature_C", "case"],
         sorted([[t["tag"], "%.0f" % t["tpnow"], "post-revamp operating case, heat and material balance rev 4"]
                 for t in T.values() if t["tpnow"] is not None]))
    wcsv(os.path.join(out, "gearbox_running_position.csv"), ["model", "rise_mm", "lateral_to_right_mm", "source"],
         [["GR-800", "0.26", "0.14", "maker's data book 2017"]])
    wcsv(os.path.join(out, "hot_checks.csv"), ["tag", "date", "machine", "rise_mm", "lateral_mm", "by"],
         [[k, "2023-05-%02d" % (9 + i), "steam turbine", "%.2f" % v[0], "%.2f" % v[1], "laser contractor"]
          for i, (k, v) in enumerate(sorted(M.TURB_2023.items()))])
    wo = [("2026-09-30", "K-201A", "Operations report high 1x vibration at the coupling end since the April restart. Alignment to be looked at in the turnaround."),
          ("2026-10-02", "K-201B", "Coupling guard rubbing; guard re-set. Operations ask for alignment check, same complaint as K-201A."),
          ("2026-10-05", "K-201C", "Vibration trending up at motor drive end. Alignment and soft foot to be checked at turnaround."),
          ("2026-10-16", "TP-301A", "Exhaust expansion joint replaced; exhaust line spring supports re-set."),
          ("2026-10-19", "TP-301B", "Exhaust expansion joint replaced; exhaust line spring supports re-set."),
          ("2026-10-13", "P-302", "Mechanical seal replaced like for like."), ("2026-10-14", "P-306A", "Motor sent for rewind and returned; same frame."),
          ("2026-10-16", "FN-371", "Bearings replaced, both ends."), ("2026-10-20", "P-338A", "Impeller wear rings renewed."),
          ("2026-10-22", "P-312", "Coupling element replaced."), ("2026-10-27", "P-331", "Baseplate grout repaired at one corner."),
          ("2026-10-28", "P-360B", "Suction strainer cleaned.")]
    day = {"lag": ["2026-08-%02d" % d for d in (11, 11, 12, 13, 13, 18, 18, 19, 20)], "dry": ["2026-09-%02d" % d for d in (1, 1, 2, 2, 3, 3, 4, 7, 7, 8)]}
    i = {"lag": 0, "dry": 0}
    for t in T.values():
        if t["change"] == "lag":
            wo.append((day["lag"][i["lag"]], t["tag"], "Pump casing and bearing pedestals lagged to PP-2 (personnel protection programme).")); i["lag"] += 1
        if t["change"] == "dry":
            wo.append((day["dry"][i["dry"]], t["tag"], "Pedestal cooling water supply and return blanked; jackets drained (water saving programme).")); i["dry"] += 1
    wcsv(os.path.join(out, "work_orders.csv"), ["date", "item", "work"], sorted(wo))

if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
