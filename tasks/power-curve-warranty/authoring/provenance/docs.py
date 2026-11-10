"""Documents of each package and the owner's procedure PP-12 (shared)."""
import csv, math, os, random
import model as M

PROCEDURE = """# PP-12 Power performance verification (warranty)

Owner's procedure PP-12, revision 3 (2025-11-20), for the power curve warranty of the supply agreement covering the
Halden turbines at the owner's wind farms. It is applied to one farm-period package at a time.

## 1. Basis

Power performance is verified with nacelle anemometry after IEC 61400-12-2:2022, against the warranted power curve of
each turbine's model (supply agreement appendix C, the package's `warranted_power_curves.csv`). The verification period
is the package's period, in the farm's local standard time.

## 2. Data

- Turbine data: the 10-minute SCADA records of each turbine (`scada/turbine_<turbine>.csv`).
- Site meteorology: the farm's met mast M1 (`mast/m1_10min.csv`).
- Air density for each 10-minute period: from M1's hub-height temperature and relative humidity and its barometer,
  the pressure reduced to hub height with the barometric formula at the measured temperature, by IEC 61400-12-1:2022
  formula (12): rho = (1/T) (B/R0 - phi Pw (1/R0 - 1/Rw)), R0 = 287.05 J/(kg K), Rw = 461.5 J/(kg K),
  Pw = 0.0000205 exp(0.0631846 T) Pa, T in K, B in Pa, phi the relative humidity (0 to 1).
- Power: the turbine's SCADA active power. The revenue meters at the turbines' step-up transformers
  (`records/monthly_meter_energy.csv`) are the farm's reference for turbine energy.
- Record checks: every record is checked against the farm's other records and against the physics before it is
  used. A record found in error is corrected where the other records fix the right value; otherwise the periods it
  affects are left out.

## 3. Free-stream wind speed

The free-stream wind speed of a period is the turbine's nacelle wind speed through the farm's nacelle transfer
function (NTF), given in the site description, established from the calibration turbine and M1 in the calibration
sector (M1 wind direction). An NTF applies only to the configuration it was established for (IEC 61400-12-2); where it
no longer applies, it is re-established from the calibration turbine and M1 in the calibration sector, with M1's wind
speed from its anemometer calibration.

## 4. Data selection

A 10-minute period of a turbine is used only when all of the following hold:
- the turbine's status is 0 (running, unrestricted);
- no power limitation applies: neither a grid operator curtailment (`records/curtailment_log.csv`) nor an operating
  mode of the farm's noise permit (`noise_permit.md`, where the farm has one);
- no icing: M1 temperature at or above 2 C or relative humidity at or below 85 percent, and no ice alarm where the
  turbine has an ice detector;
- the turbine's wind direction is outside every disturbed sector (IEC 61400-12-1:2022 Annex A) of the neighbouring
  turbines within 20 of their rotor diameters, whether or not they were running. The disturbed sector of a neighbour
  at distance L with rotor diameter Dn is centred on the bearing from the turbine to the neighbour and is
  1.3 arctan(2.5 Dn/L + 0.15) + 10 degrees wide. The turbine's wind direction is its yaw position corrected by its
  north offset (site description).

## 5. Measured power curve

Normalise each period's free-stream wind speed to the reference density 1.225 kg/m3: V_n = V (rho/1.225)^(1/3).
Bin the periods in 0.5 m/s bins centred on 3.0, 3.5, ... 25.0 m/s; a bin's point is the mean normalised wind speed
and the mean power of its periods, and bins with fewer than 3 periods are left out. The measured power curve is the
bin points joined by straight lines and held constant beyond the first and last points.

## 6. Annual energy ratio and claim

Evaluate the measured and the warranted curve at 3.0, 3.5, ... 25.0 m/s and compute each one's annual energy for a
Rayleigh distribution of mean 7.5 m/s: AEP = 8760 h x sum over intervals of [F(V_i) - F(V_i-1)] (P_i-1 + P_i)/2,
F(V) = 1 - exp(-(pi/4)(V/7.5)^2). The annual energy ratio is measured AEP over warranted AEP. A turbine whose ratio is
below 0.97 is claimed under the power curve warranty.
"""

PACKAGE_FORMAT = """# Farm-period package format

Each package holds one farm's records for one verification period (about six months):

- `site_description.md`: farm, period, local standard time, elevation, turbines (position relative to M1, model,
  rotor diameter, hub height, north offset), the calibration turbine and sector, the farm's NTF table, M1's
  instruments and the anemometer calibration certificate in force at the start of the period;
- `warranted_power_curves.csv`: the warranted curve of each turbine model of the supply agreement (kW against wind speed at
  1.225 kg/m3);
- `noise_permit.md`: the farm's noise permit conditions, where it has one;
- `scada/turbine_<turbine>.csv`: 10-minute SCADA records of each turbine, stamped at the start of the period in the farm's
  local standard time as configured at commissioning: `power_kw` (mean active power), `nacelle_ws_ms` (mean nacelle
  wind speed reported by the controller), `yaw_position_deg` (mean yaw position, degrees from north as the controller
  reports it), `status` (0 running unrestricted, 1 ready below cut-in, 2 fault, 3 maintenance, 5 curtailed by the grid
  operator, 7 manual stop; the status that held for most of the period), `ambient_temp_c` (nacelle air temperature),
  `ambient_pressure_hpa` (air pressure from the controllers' weather feed), and `ice_alarm` on turbines with an ice
  detector;
- `mast/m1_10min.csv`: M1's 10-minute records in local standard time: `ws_hub_hz` (hub-height cup anemometer output
  frequency, Hz), `wd_hub_deg` (hub-height vane, degrees from true north), `temp_hub_c`, `rh_hub_pct`, and
  `pressure_2m_hpa` (barometer 2 m above ground);
- `records/maintenance_log.csv`, `records/mast_service_log.csv`, `records/curtailment_log.csv` and
  `records/monthly_meter_energy.csv` (kWh at each turbine's revenue meter).
"""


def site_description(pk):
    tz = "UTC%+d" % pk["utc"]
    hub = M.MODELS[pk["models"]["T01"]]["hub"]
    end = M.np.datetime64(pk["start"]) + M.np.timedelta64(pk["days"], "D") - M.np.timedelta64(10, "m")
    L = ["# %s - site description" % pk["farm"], "",
         "Verification period %s 00:00 to %s local standard time (%s; the farm's controllers and loggers do not "
         "change for daylight saving)." % (pk["start"], M._fmt(end).replace("T", " "), tz), "",
         "Ground elevation at M1 %.0f m above sea level; the site is flat to within 15 m. Hub height %.0f m." % (pk["elev"], hub), "",
         "## Turbines", "",
         "| turbine | east of M1 (m) | north of M1 (m) | model | rotor diameter (m) | north offset (deg) |",
         "|---|---|---|---|---|---|"]
    for t in pk["turbines"]:
        x, y = pk["xy"][t]; m = pk["models"][t]
        L.append("| %s | %.0f | %.0f | %s | %.0f | 0.0 |" % (t, x, y, m, M.MODELS[m]["D"]))
    fw = pk["faults"].get("fw")
    if fw and max(fw["dates"].values()) < pk["start"]:
        L += ["", "Controller software 4.2.1 has run on all turbines since %s (OEM service bulletin SB-2026-03)."
              % max(fw["dates"].values())[:10]]
    L += ["", "North offsets are added to the yaw position to give the wind direction; they were checked against M1 at "
          "the last annual service and all set to zero.", "",
          "Ice detectors: %s." % (", ".join(pk["ice"]) if pk["ice"] else "none"), "",
          "## Met mast M1", "",
          "Lattice mast 2.5 rotor diameters upwind of T01 in the prevailing direction. Hub-height cup anemometer (Thies "
          "First Class), calibration certificate DWG-25-1187 (MEASNET): wind speed = %.5f m/s per Hz x frequency + "
          "%.4f m/s. Hub-height vane, temperature and humidity; barometer 2 m above ground." % M.CERT, "",
          "## Nacelle transfer function", "",
          "Calibration turbine T01, calibration sector %d to %d degrees (M1 wind direction). NTF from the commissioning "
          "campaign (controller software 3.x):" % pk["cal_sector"], "",
          "| nacelle wind speed (m/s) | free-stream wind speed (m/s) |", "|---|---|"]
    a, b = pk["ntf_old"]
    for v in range(2, 23):
        L.append("| %.1f | %.2f |" % (v, a * v + b))
    L += ["", "Linear interpolation between rows."]
    return "\n".join(L) + "\n"


def write(pk, out):
    F = pk["faults"]
    open(os.path.join(out, "site_description.md"), "w").write(site_description(pk))
    models = sorted(M.MODELS)   # appendix C covers every model of the supply agreement
    with open(os.path.join(out, "warranted_power_curves.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["wind_speed_ms"] + ["%s_kw" % m for m in models])
        curves = [M.warranted(m)[1] for m in models]
        for i, v in enumerate(M.GRID):
            w.writerow(["%.1f" % v] + ["%.1f" % c[i] for c in curves])
    if pk["sound"]:
        tl = sorted(pk["sound"]); lim = pk["sound"][tl[0]]
        open(os.path.join(out, "noise_permit.md"), "w").write(
            "# Noise permit, excerpt (conditions 6 and 7)\n\n6. Turbines %s operate in sound mode S2 from 22:00 to 06:00 "
            "local standard time every night: active power is limited to %.0f kW.\n\n7. The operator keeps the sound-mode schedule "
            "in the turbine controllers. Sound-mode operation is not a fault and is not reported as a separate status.\n"
            % (", ".join(tl[:-1]) + " and " + tl[-1] if len(tl) > 1 else tl[0], lim))
    rnd = random.Random(pk["seed"])
    rows = []
    if "fw" in F and F["fw"]["logged"]:
        for t, d in F["fw"]["dates"].items():
            rows.append([d, t, "controller", "Controller software update 4.2.1 installed per OEM service bulletin SB-2026-03 (grid code and yaw control improvements). Turbine returned to service.", "closed"])
    if "scale" in F and F["scale"]["logged"]:
        rows.append([F["scale"]["at"], F["scale"]["turbine"], "electrical", "Power transducer (CT/VT module) in the converter cabinet replaced after a failed self-test; SCADA power checked live, turbine returned to service.", "closed"])
    for r in F.get("rotor", []):
        rows.append([r["at"], r["turbine"], "rotor", "Rotor upgraded to the %s blade set (rotor diameter %.0f m) under supply agreement amendment 4; %s controller parameter set loaded. Warranted power curve per appendix C for %s from completion." % (r["model"], M.MODELS[r["model"]]["D"], r["model"], r["model"]), "closed"])
    if "yaw" in F and F["yaw"]["logged"]:
        rows.append([F["yaw"]["at"], F["yaw"]["turbine"], "yaw", "Yaw encoder replaced after an encoder fault; yaw system tested in both directions, turbine returned to service.", "closed"])
    noise = ["Gearbox oil sample taken", "Annual service completed", "Converter cooling fan replaced", "Tower ladder inspection",
             "Aviation light replaced", "Yaw brake pads inspected", "Pitch battery test", "Grease system refilled",
             "Nacelle filter mats replaced", "Main bearing temperature sensor checked", "Blade inspection by drone, no findings"]
    t0 = M.np.datetime64(pk["start"])
    for k in range(60):
        d = t0 + M.np.timedelta64(rnd.randint(0, pk["days"] - 1), "D")
        rows.append(["%s %02d:%02d" % (d, rnd.randint(7, 16), rnd.randint(0, 59)), rnd.choice(pk["turbines"]), "general", rnd.choice(noise) + ".", "closed"])
    rows.sort()
    with open(os.path.join(out, "records", "maintenance_log.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date_local", "turbine", "system", "description", "status"]); w.writerows(rows)
    mrows = [["%s 10:00" % (t0 + M.np.timedelta64(20, "D")), "M1", "Quarterly mast inspection; guy tensions checked; all sensors in service.", "closed"]]
    if "qnh" in F:
        mrows.append([F["qnh"]["start"], "M1", "Barometer reads zero; replacement ordered.", "open"])
    if "cup" in F:
        mrows.append([F["cup"]["at"], "M1", "Hub-height cup anemometer replaced with the site spare (Vaisala WAA151) after bearing noise; spare's calibration certificate DWG-26-0412 (MEASNET): wind speed = %.5f m/s per Hz x frequency + %.4f m/s. Logger channel unchanged." % (F["cup"]["slope"], F["cup"]["offset"]), "closed"])
    if "vane" in F:
        mrows.append([F["vane"]["at"], "M1", "Hub-height wind vane replaced after bearing noise; vane boom checked.", "closed"])
    if "mclock" in F:
        mrows.append([F["mclock"]["at"], "M1", "Data logger replaced after a power supply failure; channel configuration and scaling restored from the site backup.", "closed"])
    mrows.sort()
    with open(os.path.join(out, "records", "mast_service_log.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date_local", "asset", "description", "status"]); w.writerows(mrows)
