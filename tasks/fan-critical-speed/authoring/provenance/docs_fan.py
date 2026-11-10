"""Documents of each fan's package, and the standard and the package format the fans share."""
import csv, os, random
import fans as Fm

STANDARD = """# MS-RD Lateral critical speeds of overhung fans (owner's standard, revision 1)

1. A critical speed is a running speed at which the rotor and its supports are in resonance with the unbalance
   excitation: the undamped synchronous response of the rotor to unbalance is unbounded there.
2. Model:
   - the shaft from its drawing, as Euler-Bernoulli beam sections (steel, E = 207 GPa, density 7850 kg/m3), with no
     added stiffness from parts fitted on it;
   - the impeller and the fan half of the coupling as rigid bodies at their centers of gravity, with their mass and
     their transverse and polar moments of inertia;
   - each bearing as a radial spring of the bearing stiffness between the shaft and its pedestal;
   - each pedestal as a lumped mass on a horizontal and a vertical spring to the foundation; the two pedestals of a
     fan are of one design and have the same mass and the same stiffnesses;
   - the motor and the coupling's flexible element not included; damping neglected.
3. The pedestal springs are identified from a standstill impact test of the fan: the lowest natural frequencies
   measured at the fan-end bearing housing, horizontal and vertical.
4. A fan modification is assessed by the two lowest critical speeds of the fan as it will run after it.
"""

FORMAT = """# Fan package format

Each fan's package holds:
- `fan_datasheet.md`: the OEM datasheet of the fan as built: shaft drawing (sections from the coupling end of the
  shaft), bearings and their stiffness, pedestals, coupling hub, impeller, speed range;
- `rotor_changes.csv`: the asset register's record of changes to the rotor since it was built, one row per changed
  property: `entered` (the date the register entry was made), `work_order`, `part` (`impeller`, `coupling hub`, or
  `shaft section FROM-TO mm` with the positions of the shaft drawing), `property` (`mass_kg`,
  `transverse_inertia_kg_m2`, `polar_inertia_kg_m2` or `diameter_mm`) and `value`, the new value;
- `maintenance_log.csv`: work on the fan since it was built: `date` (of the work), `work_order`, `description`;
- `impact_tests/`: the standstill impact test reports, one file per test;
- `new_impeller.md`: the impeller to be fitted.
"""

TITLE = lambda n: n.replace("-", " ").title().replace("Id ", "ID ").replace("Fd ", "FD ")


def mm(x):
    return int(round(x * 1000))


def datasheet(f):
    rows = "\n".join("| %d | %d | %d |" % (mm(a), mm(b), mm(d)) for a, b, d in f["shaft0"])
    m, Id, Ip = f["imp0"]
    hm, hId, hIp = f["hub"]
    poles = 4 if f["rpm"] > 1200 else 6
    return ("# %s - OEM datasheet (as built)\n\n"
            "- Single inlet centrifugal fan, overhung impeller, direct drive from a %d-pole motor through a flexible disc "
            "coupling; variable speed drive, maximum continuous speed %d rpm.\n"
            "- Shaft drawing FS-%d rev A; sections from the coupling end of the shaft:\n\n"
            "| from (mm) | to (mm) | diameter (mm) |\n|---|---|---|\n%s\n\n"
            "- Bearings: spherical roller bearings, drive end at %d mm and fan end at %d mm (bearing centerlines); radial "
            "stiffness %.2f GN/m each.\n"
            "- Pedestals: two cast pedestals of one design, effective mass %d kg each at the bearing centerline.\n"
            "- Coupling hub (fan half): center of gravity at %d mm; mass %.1f kg; transverse moment of inertia %.2f kg m2; "
            "polar moment of inertia %.2f kg m2.\n"
            "- Impeller: center of gravity at the shaft end, %d mm; mass %d kg; transverse moment of inertia about the "
            "center of gravity %.1f kg m2; polar moment of inertia (WR2) %.1f kg m2.\n"
            % (TITLE(f["name"]), poles, f["rpm"], 4100 + f["seed"], rows, mm(f["bearings"][0]), mm(f["bearings"][1]),
               f["kb"] / 1e9, f["mp"], 60, hm, hId, hIp, mm(f["L"]), m, Id, Ip))


def new_impeller(f):
    m, Id, Ip = f["new"]
    return ("# %s - replacement impeller (OEM datasheet)\n\n- Uprated impeller for the existing shaft and hub fit; center "
            "of gravity at the shaft end, as the impeller it replaces.\n- Mass %d kg; transverse moment of inertia about the "
            "center of gravity %.1f kg m2; polar moment of inertia (WR2) %.1f kg m2.\n" % (TITLE(f["name"]), m, Id, Ip))


def test_report(f, t, rnd):
    cond = ("as installed" if t["cond"] == "" else
            "fan-end pedestal horizontal stay removed for access to the bearing (refitted after the bearing change)")
    return ("# Impact test report - %s, %s\n\n- Fan stopped, isolated and uncoupled; impeller at rest.\n- Condition: %s.\n"
            "- Excitation: instrumented hammer on the fan-end bearing housing; response: accelerometer on the fan-end "
            "bearing housing; %d averages, coherence above 0.95 at the peaks.\n\n| direction | lowest natural frequency (Hz) |\n"
            "|---|---|\n| horizontal | %.2f |\n| vertical | %.2f |\n"
            % (TITLE(f["name"]), t["date"], cond, rnd.choice([5, 6, 8]), t["fH"], t["fV"]))


NOISE = ["Bearings regreased", "Coupling disc pack inspected, no defects", "Inlet damper actuator serviced",
         "Motor bearings regreased", "Impeller cleaned of build-up", "Vibration route: levels normal",
         "Trim balance, 85 g at the impeller back plate", "Shaft seal packing replaced", "Housing drain cleared",
         "Inlet cone gap checked and adjusted"]


def write(f, out):
    os.makedirs(os.path.join(out, "impact_tests"), exist_ok=True)
    rnd = random.Random(f["seed"])
    open(os.path.join(out, "fan_datasheet.md"), "w").write(datasheet(f))
    open(os.path.join(out, "new_impeller.md"), "w").write(new_impeller(f))
    for t in Fm.test_freqs(f):
        open(os.path.join(out, "impact_tests", "impact_test_%s.md" % t["date"]), "w").write(test_report(f, t, rnd))
    ch = []
    log = []
    for e in f["events"]:
        wo = "WO-%s-%04d" % (e["date"][:4], rnd.randint(100, 9999))
        if e["kind"] == "impeller":
            m, Id, Ip = e["imp"]
            ch += [[e["entered"], wo, "impeller", "mass_kg", m], [e["entered"], wo, "impeller", "transverse_inertia_kg_m2", Id],
                   [e["entered"], wo, "impeller", "polar_inertia_kg_m2", Ip]]
            log.append([e["date"], wo, "Impeller re-bladed (OEM blade set rev C) and balanced in situ." if e["text"] == "re-bladed"
                        else "Impeller replaced by the OEM spare impeller and balanced in situ."])
        if e["kind"] == "hub":
            m, Id, Ip = e["hub"]
            ch += [[e["entered"], wo, "coupling hub", "mass_kg", m], [e["entered"], wo, "coupling hub", "transverse_inertia_kg_m2", Id],
                   [e["entered"], wo, "coupling hub", "polar_inertia_kg_m2", Ip]]
            log.append([e["date"], wo, "Coupling replaced by a disc coupling of the next size up; fan half hub fitted."])
        if e["kind"] == "shaft":
            a, b, d = f["shaft0"][e["seg"]]
            ch.append([e["entered"], wo, "shaft section %d-%d mm" % (mm(a), mm(b)), "diameter_mm", mm(e["d"])])
            log.append([e["date"], wo, "Shaft replaced to drawing FS-%d rev B." % (4100 + f["seed"])])
        if e["kind"] == "support":
            log.append([e["date"], wo, "Pedestal soleplates regrouted with epoxy grout; anchor bolts replaced."])
    for t in f["tests"]:
        if t["cond"]:
            log.append([t["date"], "WO-%s-%04d" % (t["date"][:4], rnd.randint(100, 9999)),
                        "Fan-end bearing replaced in kind; pedestal horizontal stay removed for access and "
                        "refitted after the bearing change. Impact test before the bearing change."])
    for k in range(10):
        y = rnd.choice(range(2017, 2026))
        d = "%d-%02d-%02d" % (y, rnd.randint(1, 12), rnd.randint(1, 28))
        log.append([d, "WO-%s-%04d" % (d[:4], rnd.randint(100, 9999)), rnd.choice(NOISE) + "."])
    log.sort()
    with open(os.path.join(out, "maintenance_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "work_order", "description"]); w.writerows(log)
    with open(os.path.join(out, "rotor_changes.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["entered", "work_order", "part", "property", "value"]); w.writerows(sorted(ch))
