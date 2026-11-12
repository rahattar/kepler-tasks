"""Write the agent's files and the sealed truth for the bare alignment core."""
import csv, json, os, random, sys
import model as M

def wcsv(path, head, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(head); w.writerows(rows)

SERVICE = {"comp": "process gas compressor, motor and speed-increasing gearbox", "gear": "cooling tower fan drive, motor and reduction gearbox",
           "turb": "boiler feed pump, steam turbine drive", "pump": "process pump, motor drive", "fan": "fan, motor drive"}
MOV = {"comp": "motor", "gear": "motor", "turb": "steam turbine", "pump": "motor", "fan": "motor"}
STAT = {"comp": "gearbox GR-800", "gear": "gearbox GR-450", "turb": "pump", "pump": "pump", "fan": "fan"}

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
it before use, by subtracting the mandrel reading from the bottom reading and half of it from each side.

- Sag belongs to the bar set. It does not depend on the machine the brackets are clamped to.
- The mandrel reading of a set is on its sag card. A card describes the set as it was carded: a set that has
  been altered, repaired or replaced has no card until it is carded again.
- The sag of one set says nothing about another set, of the same kit or any other.
- A reading taken with a set whose sag is not known is not an alignment measurement.

Which bar set a kit uses at a given span is in the kit leaflets. Which kit a fitter had is in the tool crib log.

## 4. Feet
The register gives, for each train, the distance from the movable hub's reading plane to the movable machine's
front feet and from its front feet to its rear feet. A shim change raises (+) or lowers (-) a pair of feet; a
lateral move takes them right (+) or left (-), in the sense of section 2.

## 5. Running position
A machine's shaft does not run where it sits cold. The alignment is set cold so that the shafts are in line
running. Each machine's shaft moves from cold to running by a rise and a lateral shift, the same along its length:

- motors, pumps, fans: rise = 11.5e-6 per K x the shaft height above the base x (support temperature running
  minus ambient at the time of the readings); no lateral shift;
- gearboxes: the maker's running position figure for the model, which describes the gear set as supplied.
  Gearboxes of one model with the same gear set, in the same service, move alike;
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
| C | August 2026 | set 1 (magnetic posts) for spans up to 160 mm, set 2 above 160 and up to 320 mm, set 3 above 320 mm |

A sheet's span is the distance between the two hubs' reading planes. A fitter takes the set for the span and no other.
"""

LASER = """# Laser alignment service

The contractor measures one train a visit, with the coupling made up and the machine cold, and leaves the heads
on through the start-up.

Order a visit with

    laservisit <tag>

A visit is charged when it is ordered. The contractor has time for {budget} trains at this turnaround and does not
return to a train. Each report is written to `/app/laser_reports/<tag>.csv` and gives, in mm:

- `y_stationary_plane`, `y_movable_plane`, `z_stationary_plane`, `z_movable_plane`: the cold position of the
  movable shaft's centreline relative to the stationary shaft's, at the two hubs' reading planes, in the sense
  of AP-12 section 2;
- `stationary_rise`, `stationary_lateral`, `movable_rise`, `movable_lateral`: how far each machine's shaft moved
  from cold to running.

The laser carries no bracket and has no sag.
"""

def main(out, rig, seed_note=""):
    T = M.build()
    rng = random.Random(M.SEED + 1)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True); os.makedirs(rig, exist_ok=True)
    open(os.path.join(out, "docs", "alignment_procedure.md"), "w").write(
        PROC.format(budget=M.BUDGET, tol=M.TOL))
    open(os.path.join(out, "docs", "kit_leaflets.md"), "w").write(LEAF)
    open(os.path.join(out, "docs", "laser_service.md"), "w").write(LASER.format(budget=M.BUDGET))

    reg = []
    for t in T.values():
        k = t["kind"]
        reg.append([t["tag"], SERVICE[k], t["crit"], MOV[k], STAT[k], t["speed"], "%.0f" % t["a"], "%.0f" % t["b"],
                    "%.0f" % t["h_mov"], "%.0f" % t["h_stat"]])
    reg.sort()
    wcsv(os.path.join(out, "train_register.csv"),
         ["tag", "service", "criticality", "movable_machine", "stationary_machine", "speed_rpm",
          "hub_plane_to_front_feet_mm", "front_to_rear_feet_mm", "movable_shaft_height_mm",
          "stationary_shaft_height_mm"], reg)

    sheets = []
    for t in T.values():
        sm, ms = M.readings(t, t["kit"], t["date"], rng)
        sheets.append([t["date"], t["tag"], t["fitter"], "%.0f" % t["span"], "%.0f" % t["amb"]]
                      + ["%.2f" % v for v in sm] + ["%.2f" % v for v in ms] + [""])
    tag, kit, date, fitter = M.REPEAT
    assert M.kit_for(fitter, date) == kit
    sm, ms = M.readings(T[tag], kit, date, rng)
    sheets.append([date, tag, fitter, "%.0f" % T[tag]["span"], "%.0f" % T[tag]["amb"]]
                  + ["%.2f" % v for v in sm] + ["%.2f" % v for v in ms]
                  + ["repeat asked for by the rotating equipment engineer; machine not touched since the first sheet"])
    sheets.sort()
    sheets = [["DS-%03d" % (i + 1)] + r for i, r in enumerate(sheets)]
    wcsv(os.path.join(out, "dial_sheets.csv"),
         ["sheet", "date", "tag", "fitter", "span_mm", "ambient_C", "SM_top", "SM_right", "SM_bottom", "SM_left",
          "MS_top", "MS_right", "MS_bottom", "MS_left", "remarks"], sheets)

    wcsv(os.path.join(out, "tool_crib_log.csv"), ["kit", "issued_to", "out", "returned"],
         sorted([[k, f, a, b] for k, f, a, b in M.CRIB], key=lambda r: (r[2], r[0])))
    wcsv(os.path.join(out, "sag_cards.csv"), ["kit", "bar_set", "carded", "mandrel_bottom_reading_mm"],
         [[k, b, d, "%.2f" % (-2 * s)] for k, b, d, s in M.CARDS])
    wcsv(os.path.join(out, "support_temperatures.csv"), ["tag", "movable_support_running_C", "stationary_support_running_C"],
         sorted([[t["tag"], "%.0f" % t["t_mov"], "%.0f" % t["t_stat"]] for t in T.values()]))
    wcsv(os.path.join(out, "gearbox_running_position.csv"), ["model", "gear_set", "rise_mm", "lateral_mm", "source"],
         [["GR-800", "as supplied, ratio 1:3.15", "0.26", "0.14", "maker's data book 2017"],
          ["GR-450", "as supplied, ratio 4.52:1", "0.15", "-0.09", "maker's data book 2014"]])
    wcsv(os.path.join(out, "hot_checks.csv"), ["tag", "date", "machine", "rise_mm", "lateral_mm", "by"],
         [[k, "2023-05-%02d" % (9 + i), "steam turbine", "%.2f" % v[0], "%.2f" % v[1], "laser contractor"]
          for i, (k, v) in enumerate(sorted(M.TURB_2023.items()))])

    wo = [
     ("2026-08-21", "stores", "Dial bracket kit C received and put in the tool crib. Kits A and B stay in service."),
     ("2026-09-30", "K-201A", "Operations report high 1x vibration at the coupling end since the April restart. Alignment to be looked at in the turnaround."),
     ("2026-10-02", "K-201B", "Coupling guard rubbing; guard re-set. Operations ask for alignment check, same complaint as K-201A."),
     ("2026-10-05", "K-201C", "Vibration trending up at motor drive end. Alignment and soft foot to be checked at turnaround."),
     ("2026-10-12", "GF-401", "Gearbox opened; gear set changed for the re-rated set, ratio 4.10:1, for the new fan pitch."),
     ("2026-10-12", "GF-402", "Gearbox opened; gear set changed for the re-rated set, ratio 4.10:1."),
     ("2026-10-13", "GF-403", "Gear set changed for the re-rated set, ratio 4.10:1. Oil flushed."),
     ("2026-10-13", "GF-404", "Gear set changed for the re-rated set, ratio 4.10:1."),
     ("2026-10-13", "P-105", "Mechanical seal replaced like for like."),
     ("2026-10-14", "P-131", "Motor sent for rewind and returned; same frame."),
     ("2026-10-15", "tool crib", "Kit B was dropped from the pipe rack on its way back to the crib on 14 October. Bar sets 2 and 3 found bent on inspection this morning; both replaced with tube from stores. Set 1 not damaged."),
     ("2026-10-16", "TP-301A", "Exhaust expansion joint replaced; exhaust line spring supports re-set."),
     ("2026-10-16", "FN-520", "Bearings replaced, both ends."),
     ("2026-10-19", "TP-301B", "Exhaust expansion joint replaced; exhaust line spring supports re-set."),
     ("2026-10-20", "P-118A", "Impeller wear rings renewed."),
     ("2026-10-21", "TP-301C", "Casing support keys freed and re-greased; exhaust line spring supports re-set."),
     ("2026-10-22", "P-140B", "Coupling element replaced."),
     ("2026-10-23", "K-201A", "Motor bearings inspected, satisfactory."),
     ("2026-10-27", "P-109", "Baseplate grout repaired at one corner."),
     ("2026-10-28", "P-141", "Suction strainer cleaned."),
    ]
    wcsv(os.path.join(out, "work_orders.csv"), ["date", "item", "work"], wo)

    truth = {t["tag"]: dict(t, moves=M.true_moves(t), change=M.running_change(t)) for t in T.values()}
    json.dump(dict(budget=M.BUDGET, trains=truth), open(os.path.join(rig, "truth.json"), "w"))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
