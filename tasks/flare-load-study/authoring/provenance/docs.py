"""The agent-visible documents for relief-valve-adequacy. gen.py fills in the computed tables."""

STANDARD = """# RP-7  Flare system relieving load

Issue 6, January 2026. Supersedes issue 5. Applies to the flare system of any process unit and to the load study
that establishes what each unit-wide contingency puts into it.

## 1 Scope and basis of study

A study under this standard establishes, for each contingency the unit admits, which relief devices discharge at
the same time, the total mass flow that arrives at the flare header, and the pressure that flow raises at the
header's inlet.

The study is made on the plant as it now stands, not as it was designed. The set pressure of a device is the one
it now carries. The flows, pressures, temperatures and duties are those the unit now runs at.

Where a quantity is established from a record of the plant running, only the part of that record which describes
the item in its present condition may be used. The maintenance log says what has been done to each item and
when; a reading taken before the last work on an item does not describe the item that is there now, and a record
read across such work describes nothing that has ever been in service.

## 2 Contingencies to be studied

- `power_failure`: the loss of the normal electrical supply across the unit.
- `cooling_water_failure`: the loss of the cooling water supply.
- `instrument_air_failure`: the loss of instrument air across the unit.
- `fire_zone_a`, `fire_zone_b`, `fire_zone_c`: a pool fire in one fire zone. A fire is credible in one zone at a
  time and reaches only the items that stand in that zone.

## 3 Which devices discharge

A relief device discharges under a contingency when that contingency puts upon its item a cause the item's
service admits, and when nothing in section 7 or section 8 prevents it. The causes are those of section 4 and
the register lists which of them each item admits.

The chain from a contingency to a cause is to be followed through the unit's own records, not assumed:

- A loss of the normal electrical supply stops every driven machine the drive schedule puts on that supply, and
  nothing on the essential supply. Where the instrument air compressor is on the normal supply, a loss of power
  carries a loss of instrument air with it.
- A loss of cooling water stops the machines and exchangers the drive schedule shows to be cooled by water.
- A loss of instrument air puts every control valve in the failure position its data sheet gives. A valve that
  fails open admits its source to the item it feeds; a valve that fails closed isolates what it passes.
- The overhead cooling of a column is lost when the condenser serving it stops.
- A pump whose discharge is isolated delivers against a closed valve.

## 4 Causes and their relieving rates

### 4.1 Relieving pressure

    P1 = (Pset + Pb) * (1 + a) + 1.013      bar absolute

with Pset the set pressure in bar gauge, Pb the pressure standing at the device's own outlet in bar gauge, and
the accumulation a

- a = 0.21 for `fire`;
- a = 0.10 for every other cause.

A conventional spring-loaded device is referenced to atmosphere, so whatever pressure stands at its outlet is
added to the pressure at which it opens: for such a device Pb is the pressure in the header at its own tie-in,
built up by the very flow the contingency is putting into the header. A device with a balanced bellows is
isolated from its outlet and opens at its set pressure whatever the header is doing: for those Pb is zero. The
relief valve register says which devices carry a bellows.

Fluid properties are taken at the relieving pressure, and at the saturation temperature there where the
relieving fluid is a saturated vapour. Where the relieving fluid does not condense, the relieving temperature is
the item's normal operating temperature, the mean of the operating record, and its molar mass is that of the most
recent analysis of the stream. Property tables are interpolated linearly and held flat beyond their ends.

### 4.2 `fire`

The heat absorbed by a vessel in a pool fire is

    Q = 43.2 * F * Aw^0.82      kW

where the item stands in an area with drainage or impounding and prompt firefighting is available, and

    Q = 70.9 * F * Aw^0.82      kW

where it does not. Aw is the wetted area in m2.

The environment factor F is 1.0 for a bare or ordinarily lagged item. Where the item carries insulation certified
to remain in place in a fire,

    F = (k / t) * (904 - Tf) / 21000

with k the thermal conductivity of the insulation in W/m K, t its thickness in m, and Tf the relieving
temperature in C. Insulation without such a certificate earns no credit.

The wetted area is the outside surface of the item in contact with liquid at its highest normal operating level,
counted only up to 7.6 m above grade. Surface above that height is not included.

- Each 2:1 ellipsoidal head has an area of 1.084 * D^2, D the diameter in m.
- For a horizontal vessel with a liquid level h above the bottom of the shell, the wetted fraction of the shell
  and of each head is acos((R - h) / R) / pi, with R the shell radius.
- For a fractionating column, the wetted area is the shell in contact with the bottoms liquid, plus the bottom
  head, plus at each tray at or below 7.6 m above grade a band of shell equal in height to the tray liquid depth
  given in the column's data.

The relieving rate is

    W = 3600 * Q / L      kg/h

where L is the latent heat, at the relieving pressure, of the liquid the item holds, which the vessel data book
names. What relieves in a fire is the vapour boiled off that liquid, whatever the item passes in normal service,
so its latent heat, molar mass, ratio of specific heats and compressibility are all those of that liquid's vapour
at the relieving pressure, and the relieving temperature is the saturation temperature there.

### 4.3 `control_valve_failure`

The valve passes into the protected item, at the item's relieving pressure, the flow its full travel admits. The
upstream pressure is the set pressure of the relief device that protects the source of the stream.

    W = 3.16 * Kv * Fp * Y * sqrt(x * P1u * rho1)      kg/h

with

- Kv = Cv / 1.156, the valve coefficient at the travel in question;
- P1u the upstream pressure, kPa absolute, and rho1 the upstream density, kg/m3;
- x = min((P1u - P2) / P1u, Fk * xT), with P2 the downstream pressure, xT the valve's pressure drop ratio factor
  and Fk = k / 1.40;
- Y = 1 - x / (3 * Fk * xT).

The trim follows an equal percentage characteristic,

    Cv(h) = Cv_rated * R^(h - 1)

with h the fractional travel and R the rangeability on the valve's data sheet. The coefficient at full travel
shall be verified against the valve's own operating record; where the record and the data sheet disagree, the
record governs.

### 4.4 `cooling_failure`

With the overhead condenser of a column stopped and heat input continuing, the relieving rate is the vapour the
reboiler generates at the relieving temperature:

    Q = UA * (Ts - Tb)      kW
    W = 3600 * Q / L        kg/h

where the liquid the column holds is the one the vessel data book names for it, and

- Ts is the saturation temperature of the steam at the pressure of the header that supplies the reboiler, which
  the exchanger data gives, the steam valve being taken as fully open;
- Tb is the saturation temperature of that liquid at the relieving pressure;
- L is the latent heat of that same liquid at the relieving pressure, the mass the reboiler makes being its duty
  over the latent heat of what it is boiling;
- UA shall be established from the record of the exchanger in its present condition, at the throughput the unit
  runs, as the mean over that record of the value each day's duty and temperature difference give.

What then leaves the top of the column and enters the header is the relieving fluid the register names, so it is
that fluid's molar mass, ratio of specific heats, compressibility and temperature at the relieving pressure that
the mixture of section 5 is made from.

### 4.5 `blocked_outlet`

A pump delivering against a closed discharge relieves the flow it passes at the relieving pressure, carried on
its own mass. The flow the pump delivers there is read from its performance as last tested, and section 7
settles whether it can reach the relieving pressure at all.

## 5 The load on the header

The load a contingency puts on the header is the sum of the rates of the devices that discharge under it. What
arrives is their mixture, whose properties are

- molar mass: the total mass divided by the total moles, the moles of each contribution being its mass over its
  own molar mass;
- ratio of specific heats, compressibility and temperature: the mass-weighted means of the contributions.

A device discharging liquid contributes its mass like any other, and enters the mixture with the molar mass of
the liquid it passes, a ratio of specific heats of 1.05, a compressibility of 1, and the temperature at which
that liquid is pumped.

## 6 The pressure at the header's inlet

The header runs from a blinded end at the unit limit to the stack base. Relief devices tie into it at the
distances the as-built isometrics give, and those tie-ins divide the header into lengths, whether or not the
device at a tie-in discharges under the contingency in hand. Flow runs towards the stack, so each length carries
the devices that tie in beyond it, and carries their mixture, taken as section 5 gives it. A length that carries
nothing adds nothing, the purge flow being neglected.

The loss along a length of header, and through the tip, follows

    dP = (f * L / D + sum K) * rho * v^2 / 2      Pa

with f = 0.018, L the length and D the bore in m, v the velocity of what that length carries, and the fitting
losses

| fitting | K |
|---|---|
| 90 degree elbow | 0.30 |
| tee, flow through run | 0.20 |

each fitting counted in the length its position falls in.

For a given set of rates the pressures are worked out from the tip outwards:

1. the tip, carrying the whole load, with the mixture's density at atmospheric pressure and the tip's own loss
   coefficient and bore, gives the pressure at the stack base;
2. then each length of header in turn, from the stack base outwards, with the density of what that length
   carries taken at the pressure already reached at its downstream end. The pressure reached at a tie-in is the
   pressure the devices tying in there stand against at their outlets.

The rates are not known before those pressures, because section 4.1 lifts the relieving pressure of every
conventional device by the pressure at its own tie-in, and a higher relieving pressure passes less. The load,
the relieving pressures and the header pressures are therefore one system and are to be brought out together:
begin with no built-up pressure anywhere, work out the rates and then the pressures, take those pressures back
into section 4.1, and repeat until no pressure at any tie-in moves by more than 0.0001 bar between one pass and
the next. Passing less as the back pressure rises, the sweeps close on one answer from below.

Which devices discharge is settled on the same converged pressures, section 7 included.

The pressure at the header's inlet is the pressure reached at the blinded end, reported in bar gauge. A flare
header carries no isolation valve.

Where the loss coefficient of the tip or of a fitting is not on record for the item as installed, it is to be
established by test on that item, and not taken from the item it replaced.

## 7 Causes that need not be considered

A cause need not be considered where it cannot raise the pressure of the protected item to its relieving
pressure. For a pump delivering against a closed discharge this is settled by the pump's shutoff pressure in its
present condition, which is the condition it is in after the last work the maintenance log records on it.

## 8 Credit for instrumented protection

A cause may be set aside where a safety instrumented function prevents it and all of the following hold:

- the function is rated SIL 2 or better in the safety instrumented system register;
- it is proof tested at intervals of not more than 18 months;
- its initiating element is not a measurement that any control function on the protected item uses;
- the system that carries the function still has the supply the drive schedule shows it on.

Where any of these does not hold, the cause stands.

## 9 The re-rating of the stack tip

A conventional device is not to be left standing against a built-up back pressure of more than 5 per cent of
its own set pressure under any contingency. Where the tip as installed leaves one above that, the tip is to be
re-rated: the duty is the smallest bore the vendor supplies at which no conventional device is left above the
limit under any contingency, the loss coefficient of the tip being unchanged by its bore. The bores available
are in the flare system note.

Report that bore, the conventional device left with the largest share of its set pressure at it, and that share
as a percentage of set pressure. The load study itself is reported for the tip as installed, not for the
re-rated one.

## 10 The record of the study

For each contingency: the relief devices that discharge, the total load in kg/h, and the pressure at the header's
inlet in bar gauge.
"""

UNIT = """# Unit 400, natural gas liquids recovery

Unit 400 takes rich pipeline gas, knocks out the liquid, and splits the liquid into ethane, propane, butane and a
stabilised bottoms product.

## Flow of the unit

Pipeline gas enters at the unit limit through the feed pressure control valve PV-4001 and the feed meter FE-4011,
and passes to the inlet separator V-401. The pipeline operator's agreement caps the delivery pressure at the unit
limit at 72 barg.

Gas leaves V-401 to the sales gas header. A small stream is let down through PV-4021 to the fuel gas knock-out
drum V-402, which supplies the plant fuel gas header; FE-4021 meters it.

Liquid from V-401 is pumped through the feed/bottoms exchanger E-402, whose tube side carries the high pressure
feed liquid and whose shell side carries the hot bottoms product, and enters the deethaniser T-401. T-401 is
reboiled by E-403 on 13 barg steam and condensed overhead into the reflux drum V-403; PV-4031 controls the column
pressure by bypassing the condenser. FE-4033 meters the reflux and FE-4034 the ethane product.

The deethaniser bottoms, metered by FE-4035, feed the debutaniser T-402, reboiled by E-406 on 13 barg steam.
T-402 overhead is condensed into the receiver V-404; FE-4036 meters the reflux and FE-4037 the overhead product.
PV-4061 controls the column pressure. The T-402 bottoms are the stabilised product; pump P-401 sends them through
E-402 and the product cooler to storage, metered by FE-4051.

The T-402 overhead product goes on to the depropaniser T-403, outside the scope of this assessment, which makes
the propane and butane products. Propane vapour from T-403 is admitted to the propane product drum V-405 through
PV-4071; FE-4071 meters it. FE-4072 meters the propane product and FE-4038 the butane product.

## Cooling and air

T-401 is condensed overhead by E-404, which is cooled by the plant's cooling water through two circulating
pumps. T-402 is condensed overhead by E-407, an air cooler with four fans. Instrument air comes from K-901 in
unit 900, through a receiver at the unit limit. The drive schedule gives what drives each of these and which
electrical supply that driver is on.

## Relief disposal

Every relief device on the unit discharges to the one main flare header, which runs to the stack. The header and
the stack tip are described in the flare system note.

## Control and protection

The regulatory controls that bear on the contingencies in this assessment are

| control | measurement | final element | what it does |
|---|---|---|---|
| PIC-4011 | PT-4012 | PV-4001 | holds V-401 pressure by throttling the feed |
| PIC-4021 | PT-4021 | PV-4021 | holds V-402 pressure by throttling the fuel gas let-down |
| PIC-4031 | PT-4031 | PV-4031 | holds T-401 pressure by bypassing the overhead condenser |
| PIC-4061 | PT-4061 | PV-4061 | holds T-402 pressure by bypassing the overhead condenser |
| PIC-4071 | PT-4071 | PV-4071 | holds V-405 pressure by admitting propane vapour |

## Relief devices outside this assessment

| device | protects | set, barg |
|---|---|---|
| PSV-410 | sales gas header | 66 |
| PSV-411 | T-403 and its overhead system | 26 |
| PSV-412 | fuel gas header | 10 |
| PSV-413 | 13 barg steam header | 15 |

## Fire zones

The unit is divided into three fire zones for the purposes of the flare load study. The zones and the items that
stand in each are in the fire zone schedule.
"""

VESSELS = """# Unit 400 vessel data book

Issue 2, March 2019. Dimensions in metres. Elevations are of the bottom tangent line above grade. The highest
normal operating liquid level is given above the bottom tangent line. All heads are 2:1 ellipsoidal.

| item | service | shape | diameter | T-T length | bottom tangent | highest normal level | liquid held | specific gravity | insulation |
|---|---|---|---|---|---|---|---|---|---|
| V-401 | inlet separator | vertical | 2.40 | 7.00 | 1.50 | 1.10 | sep_liquid | 0.504 | mineral wool, metal jacket, 60 mm |
| V-402 | fuel gas knock-out drum | horizontal | 1.60 | 4.20 | 1.00 | 0.70 | c3_product | 0.480 | none |
| V-403 | T-401 reflux drum | horizontal | 2.00 | 5.50 | 6.60 | 0.85 | c2_overhead | 0.389 | fire-resistant, 75 mm |
| V-404 | T-402 overhead receiver | horizontal | 2.20 | 6.50 | 2.00 | 0.95 | c4_product | 0.496 | none |
| V-405 | propane product drum | horizontal | 2.40 | 10.00 | 1.20 | 1.45 | c3_product | 0.447 | none |
| T-401 | deethaniser | column | 1.80 | 24.00 | 1.80 | 2.60 | c3_product | 0.387 | fire-resistant, 75 mm |
| T-402 | debutaniser | column | 3.20 | 21.00 | 3.60 | 3.60 | c4_product | 0.497 | none |
| E-402 | feed/bottoms exchanger shell | horizontal | 0.90 | 6.00 | 1.00 | 0.90 | bottoms_product | 0.622 | none |

The liquid held is the stream in the fluid properties table whose properties apply to the item's
liquid inventory. For a column it is the liquid in the bottom of the column. The specific gravity is
that of the liquid held at the item's normal operating condition. The highest normal level is as the
item's level transmitter indicates it, at the setting the level control system holds; the transmitters
are in the instrument schedule. E-402 has no level transmitter and its figure is the design datum. The
relieving fluid of each item is in the relief valve register.

## Insulation

| item | system | conductivity, W/m K | thickness, m | fire resistance certificate |
|---|---|---|---|---|
| V-401 | removable mineral wool with metal jacket | 0.062 | 0.060 | none |
| V-403 | fire-resistant insulation to specification S-1140 | 0.055 | 0.075 | FRC-2251 |
| T-401 | fire-resistant insulation to specification S-1140 | 0.055 | 0.075 | FRC-1987 |

## Columns

| column | trays | spacing | lowest tray above grade | tray liquid depth |
|---|---|---|---|---|
| T-401 | 28 | 0.60 | 5.60 | 0.090 |
| T-402 | 24 | 0.65 | 8.30 | 0.105 |

## Fire protection of the unit

The whole of unit 400 stands on a paved, kerbed and graded area draining to the unit's own sump, and is within
reach of the main firewater ring with two monitors and a hydrant at the unit limit. The fire protection survey of
May 2026 confirmed drainage and firewater coverage over the whole unit.
"""

FLARE_SYSTEM = """# Unit 400 flare system

Issue 3, July 2026. The header was re-rated in 2026 when the low pressure header was taken out of service and
its devices tied into the main header; what follows is as built after that work.

## The header

| item | value |
|---|---|
| bore | 457.2 mm |
| developed length, blinded end to the stack base | 380 m |
| isolation valves | none |

The header terminates at the unit limit in a blinded end carrying the purge gas connection, and runs without an
isolation valve of any kind, as the standard requires. Distances along it are measured from the stack base.

## Fittings

| fitting | distance from the stack base, m |
|---|---|
| 90 degree elbow | 22 |
| tee, flow through the run | 47 |
| tee, flow through the run | 73 |
| 90 degree elbow | 119 |
| 90 degree elbow | 160 |
| 90 degree elbow | 240 |
| tee, flow through the run | 251 |
| 90 degree elbow | 302 |

## Tip bores the vendor supplies

254.0, 304.8, 355.6, 406.4 and 457.2 mm, all to the same design and so to the same loss coefficient.

## Tie-ins

Where each device ties into the header is held in the as-built isometrics, issue 4 of July 2026, which list
every tie-in on it. The tie-in schedule is in the unit's records.

## The stack tip

| item | value |
|---|---|
| bore | 304.8 mm |

The tip discharges to atmosphere. The original tip was replaced in 2025 with a unit of the same bore from
another vendor, who supplied no performance data with it, so the loss coefficient of the tip now installed is
not on record here or anywhere else in the unit's files. The figure the 2019 study worked to is the original
vendor's, measured on the tip that unit replaced, and covers that tip's burner and wind shield together.

## Friction

The header and the tip are both to be worked out with the Darcy friction factor and the fitting losses that
RP-7 gives.
"""

STUDY = """# Unit 400 flare load study

Document 400-SA-0012, revision 2, issued 14 March 2019. Prepared for the original plant.

## Basis

- Unit feed rate 310 t/d, the design basis of the unit as built.
- Feed analysis of 11 January 2019.
- Reboiler duties from the exchanger data sheets at the design feed rate.
- Control valve coefficients from the valve data sheets.
- P-401 performance from the pump data sheet curve.
- Vessel dimensions and elevations from the vessel data book, issue 2.
- Stack tip loss coefficient {tip_k_old}, the original vendor's figure for the tip then installed, referred to
  the velocity in the tip bore.
- The instrument air compressor stood on the essential supply at the time of issue, so a loss of the normal
  supply was taken not to carry a loss of air with it.
- Worked to RP-7 issue 4, whose relieving rates, accumulations, credit conditions and header expressions are
  those of the current issue.
- The low pressure header was then in service; the loads below are the two headers added together, which is what
  the one header now carries.

## Findings

| contingency | devices discharging | load, kg/h | header inlet, barg |
|---|---|---|---|
{rows}

## Notes

1. The fire cases for V-403 and T-401 were taken with no insulation credit, neither item having been insulated to
   a fire-resistant specification at the time of issue.
2. Loss of power is governed by the two columns losing their overhead cooling. Any change to the supply the
   instrument air compressor stands on would bring the air failure cases into it as well, and should be referred
   back to this study.
3. The header as then installed passes the governing load with the inlet pressure below 1.0 barg. There is no
   margin for a further increase in reboil duty.
"""


FIELD = """# Unit 400 field testing

Issue 2, October 2026. What the unit's test crew will run during an assessment, and how it is ordered.

## Ordering

The crew takes its orders through the `fieldtest` command, one test to an order:

    fieldtest <test>

The booking for an assessment is {budget} tests. A test is charged to the booking when it is ordered, whatever
its result, and the same test will not be run twice. The crew reports to `/app/field_reports`, one file an
order, and prints where it has written. Orders are taken in any sequence, but the crew is on the unit for one
shift only, so all of them have to be placed on what is already known rather than on the result of an earlier
test in the same booking.

## What the crew will run

| test | what it does | what it reports |
|---|---|---|
| `tip-backpressure` | runs nitrogen through the stack tip from a temporary compressor | the flow, its temperature and the gauge pressure at the stack base |
| `pump-shutoff` | a four point performance test on P-401 as it now stands | flow against head at the running speed |
| `reboiler-E406` | a performance test on E-406 at three reboil rates | the steam pressure and flow, and the temperatures either side |
| `valve-PV4031` | strokes PV-4031 against measured flow at five travels | the travel, the pressures either side, the upstream temperature and the flow |
| `condenser-E404` | a performance test on E-404 over three cooling water temperatures | the water temperatures, the duty and the condensing temperature |
| `popcheck-PSV404` | lifts PSV-404 on the test stand, three pops | the pressure at which it lifted, as found |

## Reading the reports

Each report is a CSV with a commented first line naming the test and the day it was run. The crew measures and
records; it draws no conclusions, and it does not say whether a test was worth ordering.
"""
