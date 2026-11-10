"""Documents of each chamber's package, and the standard, the vacuum data and the package format the chambers share."""
import csv, math, os
import numpy as np
import jobs as Jm
import vac as V

STANDARD = """# MS-VP Pump-down time of vacuum chambers (owner's standard, revision 3)

1. The pump-down time of a job is the time from the start of roughing, with the chamber at 1013 mbar after the job's
   air vent, to the first time the chamber pressure reaches the job's process pressure. It is computed for the
   chamber as it is on the job's date.
2. The chamber pressure p (mbar) follows V dp/dt = -S_eff p + Q(t), where:
   - V (L) is the volume pumped: the chamber and everything open to it on the chamber side of the gate valve;
   - roughing runs until p reaches the crossover pressure of the chamber's controller; from then the turbo pump pumps
     the chamber through the high-vacuum port and the roughing pump no longer does;
   - S_eff = S C / (S + C): in roughing, S is the roughing pump's speed at p and C the roughing line's conductance;
     in high vacuum, S is the turbo pump's speed at p and C the conductance of the high-vacuum port;
   - pump speeds come from the pump curves of `vacuum_data.md`, linear in log10 p between the points and held beyond
     them;
   - the roughing line's conductance is Knudsen's for air at 20 C, C = 135 D^4 p / L + 12.1 D^3 / L
     (1 + 192 D p) / (1 + 237 D p) L/s, with D the bore and L the length in cm and p the chamber pressure in mbar.
3. The gas load is Q(t) = Q_L + Q_w(t) + sum A q1 (t / 1 h)^-alpha (mbar L/s), with t in hours from the start of
   roughing, held at its 3-minute value before 3 minutes:
   - Q_L is the chamber's air leak, constant;
   - Q_w(t) = Q_w1 (t / 1 h)^-alpha_w is the gas load of the chamber's walls and internals after an air vent;
   - the sum runs over the surfaces in the chamber that its walls' gas load does not include: a load, and any spool
     piece, with q1 and alpha of their material from the outgassing table of `vacuum_data.md` and A their area (cm2).
4. Q_L, Q_w1 and alpha_w are fitted to the chamber's pump-down records after an air vent. In high vacuum, the gas
   load during a record is S_eff p + V dp/dt.
5. Pressures: a gauge's indicated pressure times its calibration factor (its certificate) is the pressure for air.
   Below the crossover the residual gas is water vapor, and a cold cathode gauge's pressure for water vapor is 1.12
   times its pressure for air.
"""


def curve_table(name, pts, gas):
    return ("| %s (%s) | " % (name, gas)) + " | ".join("%g mbar: %g L/s" % (p, s) for p, s in pts) + " |"


DATA = ("# Vacuum data (shop tables)\n\n## Roughing pumps (air)\n\n| pump | speed curve |\n|---|---|\n" +
        "\n".join("| %s | %s |" % (k, "; ".join("%g mbar %g L/s" % (p, s) for p, s in v)) for k, v in Jm.V.ROUGH.items()) +
        "\n\n## Turbo pumps (water vapor)\n\n| pump | speed curve |\n|---|---|\n" +
        "\n".join("| %s | %s |" % (k, "; ".join("%g mbar %g L/s" % (p, s) for p, s in v)) for k, v in Jm.V.TURBO.items()) +
        "\n\n## Outgassing after an air vent, 20 C\n\n| material | q1 at 1 h (mbar L/(s cm2)) | alpha |\n|---|---|---|\n" +
        "\n".join("| %s | %.2g | %.2f |" % (k, q, a) for k, (q, a) in Jm.OUTGAS.items()) + "\n")

FORMAT = """# Chamber package format

Each chamber's package holds:
- `chamber_sheet.md`: the chamber as issued: its volume, roughing pump, roughing line (bore and length), turbo pump,
  high-vacuum port conductance, the controller's crossover pressure and the chamber's gauges.
- `job_sheet.md`: the job: its date, its load (items, material and area) and its process pressure.
- `equipment_log.csv`: the chamber's equipment log: `date`, `entry`. Besides routine entries, entries use the shop's
  standard texts:
  - `Turbo pump sent for service; exchange unit fitted.`
  - `Roughing line rerouted: <bore> mm bore, <length> m long.`
  - `Spool piece fitted between the chamber and the gate valve: <bore> mm bore, <length> mm long, stainless steel,
    as machined.`
  - `Internals rebuilt: <what>; chamber volume now <volume> L.`
  - `Door seal replaced.`
  - `Load lock merged into the chamber: inner door removed.`
- `gauge_certificates.md`: the calibration certificates of the shop's gauges: serial number, date and calibration
  factor.
- `pumpdown_records/`: the chamber's past pump-down records, one file each. The header lines (`#`) give the date, the
  vent (gas and time open), the load in the chamber (or `empty`), the gauges by serial number, and the pumps and the
  crossover pressure. The columns are `time_s` from the start of roughing, `stage` (`rough` or `high`), and
  the indicated pressures `pirani_mbar` and `cold_cathode_mbar` (blank when the gauge is off or out of range).
"""


def chamber_sheet(ch):
    s = ch["sheet"]
    return ("# Chamber sheet - %s\n\n- Volume: %d L.\n- Roughing pump: %s.\n- Roughing line: %d mm bore, %.1f m long.\n"
            "- Turbo pump: %s.\n- High-vacuum port conductance: %d L/s.\n- Crossover pressure: %g mbar.\n"
            "- Gauges: Pirani %s, cold cathode %s.\n" % (ch["name"], s["V"], s["rough"], s["line"][0], s["line"][1],
                                                         s["turbo"], s["C_hv"], s["p_x"], s["pirani"], s["cc"]))


def load_text(load):
    if not load:
        return "empty"
    return "; ".join("%s (%s, %.2f m2)" % (it, mat, a) for it, mat, a in load)


def job_sheet(ch):
    j = ch["job"]
    return ("# Job sheet - %s\n\n- Date: %s.\n- Vent: air, door open for loading.\n- Load: %s.\n"
            "- Process pressure: %g mbar.\n" % (ch["name"], j["date"], load_text(j["load"]), j["p_target"]))


def log_text(kind, args):
    if kind == "turbo":
        return "Turbo pump sent for service; exchange unit fitted."
    if kind == "line":
        return "Roughing line rerouted: %d mm bore, %.1f m long." % args
    if kind == "spool":
        return ("Spool piece fitted between the chamber and the gate valve: %d mm bore, %d mm long, stainless steel, "
                "as machined." % args)
    if kind == "internals":
        return "Internals rebuilt: %s; chamber volume now %d L." % (args[2], args[0])
    if kind == "seal":
        return "Door seal replaced."
    if kind == "merge":
        return "Load lock merged into the chamber: inner door removed."
    if kind == "note":
        return args
    return None                                    # crossover, cc, pirani changes are not logged


def factor_at(certs, serial, date):
    f = certs[serial]
    if isinstance(f, float):
        return f
    return [v for d, v in sorted(f) if d <= date][-1]


def record(ch, date, vent, load, hours, rng, src=None):
    """A pump-down record of the chamber (or, misfiled into its folder, of the chamber src)."""
    if src:
        ch = Jm.BY[src]
    c = Jm.config(ch, date)
    surf = Jm.gas_surfaces(c, load, vent)
    r1, r2, tx = V.pumpdown(c["V"], c["rough"], c["D"], c["L"], c["turbo"], c["C_hv"], c["p_x"], c["leak"], surf,
                            record=True, t_end_h=hours)
    ts = list(np.arange(0, min(tx, 900), 5.0)) + list(np.arange(900, tx, 15.0)) if tx > 900 else list(np.arange(0, tx, 5.0))
    ts += list(np.arange(math.ceil(tx / 30) * 30, hours * 3600 + 1, 30.0))
    fp, fc = factor_at(ch["certs"], c["pirani"], date), factor_at(ch["certs"], c["cc"], date)
    rows = []
    for t in ts:
        if t < tx:
            p = math.exp(r1.sol(t)[0]); stage = "rough"
        else:
            p = math.exp(r2.sol(t)[0]); stage = "high"
        noise = math.exp(0.012 * rng.standard_normal())
        pir = "%.3e" % (p / fp * noise) if p >= Jm.PIRANI_MIN else ""
        cc = "%.3e" % (p / (fc * Jm.CC_WATER) * math.exp(0.01 * rng.standard_normal())) if (stage == "high" and p < Jm.CC_ON) else ""
        rows.append(("%d" % t, stage, pir, cc))
    vent_txt = "air, door open %d min" % (25 + int(30 * rng.random())) if vent == "air" else "dry nitrogen, door closed"
    head = ["# Pump-down record - %s, %s" % (ch["name"], date), "# Vent: %s" % vent_txt, "# Load: %s" % load_text(load),
            "# Gauges: Pirani %s, cold cathode %s" % (c["pirani"], c["cc"]),
            "# Pumps: roughing %s, turbo %s" % (c["rough"], c["turbo"]),
            "# Controller: crossover at %g mbar" % c["p_x"]]
    return head, rows


def write(ch, d):
    os.makedirs(os.path.join(d, "pumpdown_records"), exist_ok=True)
    rng = np.random.default_rng(500 + ch["seed"])
    open(os.path.join(d, "chamber_sheet.md"), "w").write(chamber_sheet(ch))
    open(os.path.join(d, "job_sheet.md"), "w").write(job_sheet(ch))
    certs = ["# Gauge calibration certificates", "",
             "Pressure for air = indicated pressure x calibration factor, from the gauge's calibration on that date.", ""]
    allc = dict(ch["certs"])
    for rec in ch["records"]:
        if len(rec) > 4:
            allc.update(Jm.BY[rec[4]]["certs"])
    for s, f in sorted(allc.items()):
        kind = "Pirani" if s.startswith("PG") else "cold cathode"
        for cd, cv in ([("2025-10-%02d" % (1 + int(s[-2:]) % 27), f)] if isinstance(f, float) else sorted(f)):
            certs.append("- %s gauge %s: calibrated %s, calibration factor %.3f." % (kind, s, cd, cv))
    open(os.path.join(d, "gauge_certificates.md"), "w").write("\n".join(certs) + "\n")
    with open(os.path.join(d, "equipment_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "entry"])
        for date, kind, args in ch["events"]:
            t = log_text(kind, args)
            if t:
                w.writerow([date, t])
    for rec in ch["records"]:
        date, vent, load, hours = rec[:4]
        head, rows = record(ch, date, vent, load, hours, rng, rec[4] if len(rec) > 4 else None)
        with open(os.path.join(d, "pumpdown_records", date + ".csv"), "w", newline="") as fh:
            fh.write("\n".join(head) + "\n")
            w = csv.writer(fh); w.writerow(["time_s", "stage", "pirani_mbar", "cold_cathode_mbar"])
            w.writerows(rows)
