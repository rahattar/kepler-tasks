"""Documents of each main's package, and the shared standard MS-SV and package format."""
import csv, os, random
import numpy as np
import mains as M

NUM = {1: "one", 2: "two", 3: "three", 4: "four"}

STANDARD = """# MS-SV Surge protection of pumping mains (owner's standard, revision 2)

1. Design case: simultaneous power failure of all running pumps from the normal operating point, at every operating
   condition of the main (receiving reservoir between its bottom and top water levels, wet well as held).
2. Analysis: method of characteristics for the main, with its friction, profile and wave speed as installed (Darcy-
   Weisbach, the friction factor of the initial steady flow held through the transient); pump
   rundown from the sets' inertia and homologous characteristics; ideal non-return valve closure at flow reversal;
   air vessel gas with polytropic exponent 1.2; 120 s after the trip.
3. Limits, over the whole main and the whole 120 s:
   - pressure at the pipe crown not below -3 m (gauge);
   - pressure not above 160 m (PN16);
   - the vessel's gas volume not above 85 percent of the vessel volume.
4. Air vessel on the pump station header, connected through a DN300 branch with a differential orifice: head loss
   10 m per (m3/s)^2 times flow squared for outflow to the main, 25 m per (m3/s)^2 for inflow. The vessel's level
   control keeps the gas volume at its set value in steady operation. Water surface in the vessel 1.0 m above the
   header centreline.
5. Size: the smallest total vessel volume that meets clause 3, with its gas volume set to suit. A volume more than
   15 percent above that smallest volume is not accepted.
"""

FORMAT = """# Main package format

Each main's package holds:
- `system_description.md`: the pump station, the rising main (pipe, wave speed, design friction, longitudinal
  profile from the drawings), its chambers and transmitters, and the receiving reservoir;
- `pump_datasheets.md`: the new pump sets;
- `scada.csv`: 15-minute SCADA values for a month with the existing pumps: number of pumps running, FT201 flow
  (L/s), PT201 (pump station header) and the chamber transmitter's gauge pressures (bar), LT501 reservoir level
  (m AOD);
- `records/maintenance_log.csv`: work on the pump station and the main during the month.
"""


def system_description(m):
    prof = "\n".join("| %s | %.1f |" % ("{:,}".format(int(round(c))), z) for c, z in zip(m["ch"], m["z_drawing"]))
    L = ["# %s rising main - system description" % m["name"].replace("-", " ").title(), "",
         "Pump station PS-2 lifts treated water from its wet well to the service reservoir through a single rising main.",
         "", "## Pump station PS-2",
         "- Wet well water level %.1f m AOD (held by the inlet control)." % m["ww"],
         "- Duty pumps discharge through individual non-return valves into a common header. Header centreline %.1f m AOD." % m["header"],
         "- Pressure transmitter PT201 on the header, %.1f m AOD. Electromagnetic flowmeter FT201 on the rising main." % (m["header"] + 0.6),
         "- The existing pumps are to be replaced by %s Halvorsen sets (pump_datasheets.md), %s sets running together at "
         "all times, and a surge vessel is to be added on the header." % (NUM[m["new"]["n"]], NUM[m["new"]["n"]]),
         "", "## Rising main",
         "- Ductile iron, cement-mortar lined, internal diameter %d mm, PN16; %s m from PS-2 to the reservoir inlet. "
         "Wave speed %s m/s (manufacturer's value for the pipe class and lining)." % (round(m["D"] * 1000), "{:,}".format(int(m["L"])), "{:,}".format(int(m["a"]))),
         "- Design friction: Colebrook-White with roughness %.2f mm." % (m["k_design"] * 1000),
         "- Longitudinal profile (pipe centreline, design drawings):", "",
         "| chainage (m) | centreline (m AOD) |", "|---|---|", prof, ""]
    if m["diversion"]:
        c0, c1 = m["knee_x"] - 150, m["knee_x"] + 150
        L.append("  Chainage %s to %s m was diverted during construction (variation order VO-7); the as-laid levels of "
                 "the diversion were not recorded, and the table gives the original design levels there." % ("{:,}".format(int(c0)), "{:,}".format(int(c1))))
    tap = ("on the crown tapping of the main" if not m["datum"] else
           "in the chamber, %.1f m below the crown tapping of the main to which it is connected" % m["datum"])
    L += ["- Air valve chamber %s at chainage %s m, at the high point of the main. Pressure transmitter %s (installed 2024) %s." % (
          m["chamber"], "{:,}".format(int(m["knee_x"])), m["tag"], tap), "",
          "## Service reservoir",
          "- Inlet at chainage %s m, discharging below the water surface. Operating levels: bottom water level %.1f m "
          "AOD, top water level %.1f m AOD. Level transmitter LT501 (m AOD)." % ("{:,}".format(int(m["L"])), m["BWL"], m["TWL"])]
    return "\n".join(L) + "\n"


def datasheet(m):
    p = m["new"]
    pts = "\n".join("| %d | %.1f |" % (q, p["HR"] * (1.30 - 0.30 * (q / (1000 * p["QR"])) ** 2))
                    for q in np.linspace(0, 1000 * p["QR"] * 4 / 3, 9))
    return ("# Halvorsen pump set - datasheet extract\n\n- Rated point at 1480 rpm: %.0f L/s at %.1f m; efficiency %d "
            "percent at the rated point.\n- Head-flow curve at rated speed:\n\n| flow (L/s) | head (m) |\n|---|---|\n%s\n\n"
            "- Homologous characteristics for transient analysis, normal zone (speed and flow positive), with alpha = "
            "speed / rated speed and v = flow / rated flow: head / rated head = 1.30 alpha^2 - 0.30 v^2; torque / rated "
            "torque = 0.45 alpha^2 + 0.55 alpha v. Rated torque = rho g Q H / (efficiency x rated angular speed).\n"
            "- Moment of inertia: impeller and shaft %.1f kg m2. Motor (4 pole): rotor %.1f kg m2. No flywheel.\n"
            "- Non-return valve: tilting disc with dashpot, closes at flow reversal without slam.\n"
            % (1000 * p["QR"], p["HR"], round(100 * p["eta"]), pts, p["I_pump"], p["I_motor"]))


def write(m, out):
    os.makedirs(os.path.join(out, "records"), exist_ok=True)
    open(os.path.join(out, "system_description.md"), "w").write(system_description(m))
    open(os.path.join(out, "pump_datasheets.md"), "w").write(datasheet(m))
    M.write_scada(m, out)
    rnd = random.Random(m["seed"])
    rows = []
    if m["throttle"]:
        d0, d1 = m["throttle"]["t0"], m["throttle"]["t1"]
        rows.append([d0, "PS-2", "Outlet isolating valve throttled to limit flow while the reservoir inlet works are "
                     "carried out; valve to stay throttled until %s." % d1, "closed"])
    noise = ["Pump set 1 bearing temperature check", "Wet well level sensor cleaned", "Flowmeter FT201 zero check, "
             "within tolerance", "Air valve AV-2 serviced", "Header drain valve exercised", "Motor insulation test, set 2",
             "Kiosk heater replaced", "Pump set 2 gland adjusted", "Washout WO-3 flushed"]
    for k in range(14):
        rows.append(["2026-09-%02d %02d:%02d" % (rnd.randint(1, 30), rnd.randint(7, 15), rnd.randint(0, 59)),
                     rnd.choice(["PS-2", "main"]), rnd.choice(noise) + ".", "closed"])
    rows.sort()
    with open(os.path.join(out, "records", "maintenance_log.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date_local", "asset", "description", "status"]); w.writerows(rows)
