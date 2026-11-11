"""Writes the shop's documents from the sealed constants, so no table in a document can drift from the physics.

    docs()  ->  {relative path: text}

Four documents go to the agent:
- ms_bp_audit.md     the shop standard MS-BP: the reference condition, the gas budget, the speed, the gauges, the
                     cause and what the audit reports;
- vacuum_data.md     the shop's vacuum data: pump curves, the outgassing table, the seal table, the gas factors;
- records_format.md  what each record file holds;
- audit_note.md      the vacuum engineer's note from the previous quarter's audit.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpphys as P                                                      # noqa: E402
import fleet as F                                                       # noqa: E402


def _tbl(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def ms_bp():
    gas = ", ".join("%s %.2f" % (k, v) for k, v in sorted(P.GAS_FACTOR.items()))
    return """# MS-BP: base-pressure audit of the shop's vacuum chambers

## 1. Scope

MS-BP is the method by which this shop audits a vacuum chamber that does not reach its specified base pressure. It
fixes the condition the audit refers to, the gas budget and the pumping speed that make up the chamber's base
pressure, and the way the chamber's limiting cause is named. It applies to a chamber pumped by a turbomolecular pump
through a high-vacuum port, with its gas load measured or inferred from the chamber's own records.

## 2. The reference condition

Every chamber is referred to the same condition, whatever its records were taken at:

- **%(ref).1f hours** from the start of roughing, following a vent to atmospheric air;
- the chamber wall at the reference temperature **%(t0).2f C**;
- **no load** in the chamber (no fixtures, carriers, racks or work).

All three quantities the audit reports are the quantities at that condition.

## 3. The gas budget

The chamber is a lumped volume. Its total gas load is the sum of four mechanisms, each in mbar L/s, with t the hours
from the start of roughing and T the chamber wall temperature in kelvin:

    Q_total(t, T) = Q_wall + Q_leak + Q_virtual + Q_perm

### 3.1 Wall and internals outgassing

The water the chamber's surfaces took up during the vent leaves them as

    Q_wall = C_w * theta_w(T) * f_vent * sum_i [ A_i * q1_i * t^(-alpha_i) ]

over the chamber's internal surfaces i, with A_i the area in cm2 and q1_i and alpha_i the surface's entries in the
outgassing table of the shop's vacuum data. q1 is the specific gas load at t = 1 h and %(t0).2f C.

C_w is the chamber's own wall gas load coefficient. The table's q1 is a nominal figure for a surface of that kind,
good enough to size a pump; the gas load of a particular chamber departs from it by a factor that depends on the
history of its surfaces - how long they stood open, what has been baked out of them, what has been deposited on
them - so **C_w is identified from the chamber's own records** and is not assumed to be one. The exponent alpha is
set by the desorption of water from that kind of surface and is taken from the table.

    f_vent = 1.00 after a vent to atmospheric air
    f_vent = %(nf).2f after a vent to dry nitrogen

    theta_w(T) = exp( (E_W / R) * (1 / T_0 - 1 / T) ),   E_W = %(ew).1f kJ/mol,  T_0 = %(tk).2f K

Below t = %(hold).2f h the law is held at its value at %(hold).2f h.

### 3.2 Real air leak

A leak admits atmospheric air through a passage in a wall, weld, seal or feedthrough. Its gas load Q_leak is
constant: it does not change with pumping time and, over the shop's range of temperatures, not with temperature
either.

### 3.3 Virtual leak

A trapped volume - a blind hole, an unvented interspace, a pocket behind a clamped part - empties into the chamber
through a small conductance. Its gas load falls as a single exponential in the time since the vent:

    Q_virtual = Q_v0 * exp( -t / tau )

with Q_v0 its gas load at the vent and tau its time constant in hours. A trapped volume holds air, so its gas is of
atmospheric composition.

A trapped volume of this shop's chambers has a time constant of **%(taumax).0f hours or less**. A source that does not
fall measurably over a pumpdown is a leak and is reported as one: fitting it as a trapped volume of some hundreds
of hours describes the same constant and names the wrong mechanism.

### 3.4 Permeation

Atmospheric gas passes through the chamber's elastomer seals. Its gas load is proportional to the length of seal
exposed and rises steeply with temperature:

    Q_perm = K20 * L_seal * theta_p(T)

    theta_p(T) = exp( (E_P / R) * (1 / T_0 - 1 / T) ),   E_P = %(ep).1f kJ/mol

with L_seal the seal length in cm and K20 the seal material's entry in the seal table, in mbar L/(s cm) for
atmospheric air at %(t0).2f C. Permeation does not change with pumping time.

## 4. Pumping speed

The chamber's effective pumping speed is the pump in series with the high-vacuum port:

    S_eff = S_t * C / (S_t + C)

with S_t the turbomolecular pump's speed at the chamber's pressure, from its curve in the shop's vacuum data, and C
the conductance of the high-vacuum port **as fitted on the audit date**: the register's value, changed by any trap,
baffle or screen the maintenance log records as fitted or removed. The pump's speed is taken from its nitrogen curve
for every species.

The chamber's **rated** effective speed is the same expression with the pump in as-new condition. A pump that has
lost speed - through bearing drag, blade damage or a failing drive - delivers less than its curve; what it delivers
is its **actual** speed, and it is the actual speed the audit reports.

At the pressures of this audit the pump curves are flat, so the chamber's steady base pressure follows from

    p = Q_total / S_eff

## 5. Gauges

Chamber gauges are calibrated against nitrogen. A certificate's factor converts a reading to the nitrogen-equivalent
pressure:

    p_N2 = factor * reading

The true total pressure follows from the composition of the chamber's gas:

    p = p_N2 / sum_i ( x_i / K_i )

with x_i the fraction of species i in the chamber's gas and K_i its relative sensitivity from the shop's vacuum data
(%(gas)s). The composition is that of the gas the chamber's mechanisms admit, in the proportions of their gas loads;
the vacuum data give the composition of each mechanism's gas.

Where a chamber carries both a cold cathode gauge and a hot-filament ionization gauge, the ionization gauge is the
chamber's reference instrument and the cold cathode gauge is a working instrument.

## 6. The limiting cause

A chamber's limiting cause is named as follows, and only as follows:

1. If the chamber's actual effective speed at the reference condition is below **%(gate).2f** of its rated effective
   speed, the cause is `pump-speed`.
2. Otherwise the cause is the mechanism of clause 3 with the largest gas load at the reference condition:
   `wall-outgassing`, `air-leak`, `virtual-leak` or `permeation`.

## 7. The audit result

For each chamber the audit reports three things, all at the reference condition of clause 2:

- its limiting cause, as clause 6 names it;
- its total gas load Q_total, in mbar L/s;
- its actual effective pumping speed S_eff, in L/s.
""" % dict(ref=F.REF_H, t0=P.T_REF - 273.15, tk=P.T_REF, nf=P.N2_FACTOR, ew=P.E_W / 1e3, ep=P.E_P / 1e3,
           hold=P.T_HOLD, gate=P.PUMP_GATE, gas=gas, taumax=P.TAU_MAX)


def vacuum_data():
    turbo = []
    for name in sorted(P.TURBO):
        pts = "; ".join("%.0e: %.0f" % (p, s) for p, s in P.TURBO[name])
        turbo.append([name, pts])
    rows = []
    for name, pts in turbo:
        hz, pw, tb = P.PUMP_CONTROLLER[name]
        rows.append("| %s | %s | %.0f | %.0f | %.0f |" % (name, pts, hz, pw, tb))
    turbo_tbl = "\n".join(
        ["| pump | speed curve, mbar: L/s | rotor, Hz | drive power, W | bearing, C |",
         "|---|---|---|---|---|"] + rows)

    og = _tbl(["surface", "q1, mbar L/(s cm2) at 1 h", "alpha"],
              [[k, "%.1e" % v[0], "%.2f" % v[1]] for k, v in sorted(P.OUTGAS.items())])

    seal_rows = []
    for k, v in sorted(P.SEALS.items()):
        rel = ", ".join("%s %.2f" % (s, v["rel"][s]) for s in ("n2", "o2", "ar", "co2"))
        seal_rows.append([k, "%.2e" % v["K20"], rel])
    seals = _tbl(["seal material", "K20, mbar L/(s cm)", "relative permeability"], seal_rows)

    air = _tbl(["species", "fraction of dry air"], [[k, "%.5f" % v] for k, v in sorted(P.AIR.items())])
    gasf = _tbl(["species", "relative sensitivity K"], [[k, "%.2f" % v] for k, v in sorted(P.GAS_FACTOR.items())])

    mech_rows = []
    for mech in ("wall-outgassing", "air-leak", "virtual-leak"):
        w = P.SPECIES[mech]
        tot = sum(w.values())
        mech_rows.append([mech, ", ".join("%s %.3f" % (k, v / tot) for k, v in sorted(w.items()))])
    mech_rows.append(["permeation",
                      "dry air, each species weighted by the seal's relative permeability, renormalised"])
    mech = _tbl(["mechanism", "composition of the gas it admits"], mech_rows)

    fx = _tbl(["item", "area, m2", "surface"],
              [[k, "%.2f" % v[0], v[1]] for k, v in sorted(F.FIXTURES.items())])

    return """# Shop vacuum data

The tables MS-BP refers to. All values are for the shop reference temperature of %(t0).2f C unless stated.

## Turbomolecular pumps

Speed against inlet pressure for nitrogen, as the maker publishes it. Between table points the speed is linear in
log10 p; beyond the ends it is held at the end value. The last three columns are what a pump of that model in good
order reports to its controller at its rated speed, which is how a controller record is read.

%(turbo)s

## Outgassing of internal surfaces after an air vent

Specific gas load at 1 h and %(t0).2f C, and the decay exponent alpha of MS-BP clause 3.1.

%(og)s

## Elastomer seals

K20 is the permeation gas load per cm of seal length for atmospheric air at %(t0).2f C. The relative permeabilities
are referred to nitrogen and set the composition of permeated gas.

%(seals)s

## Dry air

%(air)s

## Gauge sensitivities

Relative sensitivity of a nitrogen-calibrated ionization or cold cathode gauge to each species, for MS-BP clause 5.

%(gasf)s

## Composition of the gas each mechanism admits

%(mech)s

## Shop fixtures

The areas and surfaces of the fixtures, carriers and racks the shop puts in its chambers. A load in the chamber adds
its area to the outgassing sum of MS-BP clause 3.1.

%(fx)s
""" % dict(t0=P.T_REF - 273.15, turbo=turbo_tbl, og=og, seals=seals, air=air, gasf=gasf, mech=mech, fx=fx)


def records_format():
    return """# The audit records

Every file below is in `/app/data`. All of them were written before the audit date, %(audit)s.

## chamber_register.csv

One row per chamber, as the register was issued: `chamber`, `volume_l`, `turbo`, `c_port_l_s` (the high-vacuum port
conductance as built), `seal_material`, `seal_length_cm`, `surface_area_m2` and `surface` (the chamber's internal
surfaces; a chamber with more than one surface has more than one row), and `p_spec_mbar`, its specified base
pressure.

## base_pressure_log.csv

The pressure reached at the end of each of the chamber's recent pumpdowns. One row per gauge read, so a pumpdown on
which two gauges were read has two rows with the same `pumpdown`: `date`, `chamber`, `pumpdown`, `vent_gas`,
`pumpdown_h` (hours from the start of roughing to the reading), `wall_temp_c`, `gauge`, `reading_mbar`, `load` (the
fixture in the chamber during that pumpdown, blank if none) and `note`.

## speed_tests.csv

The throughput tests by which the shop measures a chamber's effective pumping speed: a known flow of dry nitrogen is
admitted through a calibrated leak and the pressure rise is read. `date`, `chamber`, `flow_mbarl_s`,
`p_with_flow_mbar`, `p_without_flow_mbar`, `gauge`, `s_eff_l_s` (the speed the contractor reported, the flow divided
by the pressure rise).

## turbo_controller.csv

What each chamber's turbo controller reported at the weekly check: `date`, `chamber`, `rotor_hz`,
`drive_power_w`, `bearing_temp_c`.

## maintenance_log.csv

The chamber maintenance log: `date`, `chamber`, `entry`.

## shop_climate.csv

The shop's daily air temperature and relative humidity: `date`, `air_temp_c`, `relative_humidity_pct`.

## docs/

`ms_bp_audit.md` is the standard, `vacuum_data.md` the shop's vacuum data, `audit_note.md` the engineer's note from
the previous audit, `vacwork.md` the audit test order, and this file.

## example/

The records of chamber %(ex)s, a chamber of the same shop audited in an earlier quarter, in the same format, so
that the format and the units are plain, with `about_this_chamber.md` describing them. MS-BP defines what the
audit reports, so no audited result is given for it.
""" % dict(audit=F.AUDIT, ex=F.EXAMPLE)


def audit_note():
    return """# Vacuum engineering: note on the base-pressure audit

Ten chambers are on this quarter's list. All ten have failed to reach their specified base pressure on at least one
recent job, and process engineering wants each one's cause named and its gas load and pumping speed quantified
before the winter shutdown is planned.

A few things worth knowing before you start on the records.

**Pumpdown lengths vary.** Chambers are pumped overnight and the length depends on what time the crew vented them,
so the base-pressure log holds pumpdowns of anything from twelve to twenty-four hours. The shop's own jobs do not
care, but the audit does: MS-BP refers everything to one condition.

**The shop is not temperature controlled.** The south bay runs several degrees warmer than the north bay in summer
and colder in winter. The daily climate record goes back further than the log.

**Gauges.** The gauge on each chamber is the one the log names. Certificates are in `gauge_certificates.md`. Two
chambers carry an ionization gauge alongside the cold cathode; where both were read, both readings are in the log.
Cold cathode heads foul in coating service and we have had them read progressively low between calibrations, which
is why the ionization gauge is the reference instrument where there is one.

**Loads.** Where a pumpdown was run with fixtures in the chamber, the log names them. Their areas are in the vacuum
data.

**Speed tests.** Every chamber was speed-tested when it came into service and most have had one since. A test tells
you the speed on the day it was run and no more: if the controller records show the turbo has changed since, the
test no longer describes the pump.

**Last quarter.** Two of the chambers on the list were worked on in the autumn and their records are thin as a
result. There was not time to repeat the pumpdowns.
"""


def vacwork_doc():
    return """# The audit test order

The audit has a budget of **%(budget)s across the whole fleet**, ordered once, with the contractor who does
the shop's vacuum work.

    vacwork status
    vacwork submit < plan.json

`vacwork status` reports whether the order has been placed, what was ordered and how many tests remain.
`vacwork submit` reads the plan on standard input and places the order. **The order can be placed only once.** It
cannot be changed, extended or replaced afterwards, and the results of no test are known until the whole order has
been placed.

The plan names a chamber and a test for each of its entries, and may hold no more entries than the budget:

    {"tests": [{"chamber": "VC03", "test": "rga", "pumping_time_h": 20}]}

%(entries)s `pumping_time_h` is optional: the time from the start of roughing
at which the measurement is taken, from %(tmin)g to %(tmax)g hours. A plan that names none is tested at %(tdef)g h,
the contractor's standing practice. The reports are written to `/app/vacwork/`, with an index of what each file is.

## The tests

Every test of this order is run on the chamber's next pumpdown after an air vent. The chamber wall is at whatever
temperature the shop is on the day, and each report gives it, with the pumping time of the measurement.

**`rate-of-rise`** - the chamber is pumped to its base pressure, the high-vacuum valve is closed, and the pressure
is logged for 60 minutes at 10 s intervals with a spinning rotor gauge, which needs no gas correction. The record
holds the time from valve closure, the pressure, the pumping time and wall temperature at which the test was run,
and the chamber's base pressure over the ten minutes before the valve was closed.

**`speed-test`** - a throughput test as the shop's own speed tests are run: a known flow of dry nitrogen through a
calibrated leak, the pressure read with and without the flow on the contractor's own gauge. The record holds the
flow, both pressures, the speed they give, and the gauge's calibration factor.

**`rga`** - a quadrupole residual gas analyser on the chamber at its base pressure. The record holds the partial
pressure of each species it resolves, with the pumping time and wall temperature of the measurement.

**`helium`** - a helium leak test with the chamber under vacuum: the suspect seals and welds are hooded in turn and
the leak detector's signal is logged against time. The record holds the signal against time for each hooded region.
It does not depend on the pumping time.
""" % dict(budget="%d test%s" % (F.BUDGET, "" if F.BUDGET == 1 else "s"), n=F.BUDGET,
           tmin=F.TEST_H_MIN, tmax=F.TEST_H_MAX, tdef=F.DEFAULT_TEST_H,
           entries=("The plan holds one entry." if F.BUDGET == 1
                    else "Between 1 and %d entries, no entry repeated." % F.BUDGET))


def gauge_certificates():
    """One section per gauge, from the sealed certificates. The certificates are correct; where the log's serial
    column disagrees with a chamber's own series, it is the log that is wrong."""
    owner = {}
    for ch in F.FLEET + [F.EX]:
        for serial in ch["certs"]:
            owner[serial] = ch["id"]
    out = ["# Gauge calibration certificates",
           "",
           "Each gauge of the fleet, the chamber it is installed on and the calibration factors the laboratory has",
           "issued for it. A factor converts a reading to the nitrogen-equivalent pressure, as MS-BP clause 5 sets",
           "out, and holds from its issue date until the next certificate for that gauge.",
           ""]
    for serial in sorted(owner):
        ch = F.BY[owner[serial]]
        kind = "hot-filament ionization gauge" if serial.startswith("IG") else "cold cathode gauge"
        out.append("## %s" % serial)
        out.append("")
        out.append("%s, installed on chamber %s." % (kind[0].upper() + kind[1:], owner[serial]))
        out.append("")
        out.append(_tbl(["issued", "factor"], [[d, "%.2f" % v] for d, v in ch["certs"][serial]]))
        out.append("")
    return "\n".join(out)


def docs():
    return {
        "gauge_certificates.md": gauge_certificates(),
        "docs/ms_bp_audit.md": ms_bp(),
        "docs/vacuum_data.md": vacuum_data(),
        "docs/records_format.md": records_format(),
        "docs/audit_note.md": audit_note(),
        "docs/vacwork.md": vacwork_doc(),
    }


if __name__ == "__main__":
    for k, v in docs().items():
        print("=" * 100)
        print("# " + k)
        print(v)
