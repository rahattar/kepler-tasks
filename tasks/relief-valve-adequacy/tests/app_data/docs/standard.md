# RP-7  Pressure relief adequacy

Issue 6, January 2026. Supersedes issue 5. Applies to every pressure relief valve on a process item in the
refinery, and to the assessment of an existing installation as well as to a new design.

## 1 Scope and basis of assessment

An assessment under this standard establishes, for each relief valve, which contingency requires the largest
relieving capacity, the effective orifice area that contingency requires, and whether the valve as it now stands
provides it.

The assessment is made on the plant and the valve as they now stand, not as they were designed. The set pressure
and the orifice are those the valve now carries. The flows, pressures, temperatures and duties are those the unit
now runs at.

## 2 Contingencies

The following contingencies are recognised. For each protected item, those its service and connections admit are
listed in the relief valve register.

- `fire`: an external pool fire around the item.
- `blocked_outlet`: every outlet from the item isolated while the inlets continue.
- `control_valve_failure`: a control valve admitting fluid to the item fails fully open.
- `cooling_failure`: total loss of the overhead cooling of a fractionating column while heat input continues.
- `tube_rupture`: one tube of a shell and tube exchanger severed, so that the high pressure side discharges into
  the low pressure side.
- `thermal_expansion`: liquid blocked in and taking heat, with no vapour space.

## 3 Relieving pressure

The relieving pressure is

    P1 = Pset * (1 + a) + 1.013      bar absolute

with Pset the set pressure in bar gauge and the accumulation a

- a = 0.21 for `fire`;
- a = 0.10 for every other contingency.

Fluid properties are taken at the relieving pressure, and at the saturation temperature there where the relieving
fluid is a saturated vapour. Where the relieving fluid does not condense, the relieving temperature is the item's
normal operating temperature, the mean of the operating record, and its molar mass is that of the most recent
analysis of the stream. Property tables are interpolated linearly and held flat beyond their ends.

## 4 Required area, vapour relief

Critical flow is assumed. The required effective orifice area is

    A = W / (C * Kd * Kb * Kc * P1) * sqrt(T * Z / M)      mm2

with

- W the relieving rate, kg/h;
- P1 the relieving pressure, kPa absolute;
- T the relieving temperature, K;
- Z the compressibility and M the molar mass, kg/kmol, of the relieving vapour;
- C = 0.03948 * sqrt(k * (2/(k+1))^((k+1)/(k-1))), k the ratio of specific heats;
- Kd = 0.975;
- Kb and Kc from section 11.

The capacity of an installed orifice follows from the same expression:

    W = A * C * Kd * Kb * Kc * P1 / sqrt(T * Z / M)        kg/h

## 5 Required area, liquid relief

    A = 11.78 * Q * sqrt(G / (P1 - Pb)) / (Kd * Kw * Kc * Kv)      mm2

with Q the relieving rate in L/min, G the relative density of the liquid, P1 the relieving pressure and Pb the
back pressure both in kPa gauge, and Kd = 0.65.

Kv corrects for viscosity. With the Reynolds number at the required area

    Re = 2800 * Q * G / (u * sqrt(A))

where u is the dynamic viscosity in cP and A the required area in mm2,

    Kv = 1                                                            for Re >= 1e5
    Kv = (0.9935 + 2.878 / Re^0.5 + 342.75 / Re^1.5)^(-1/1.5)         otherwise

A appears on both sides, so the area is obtained by iteration from Kv = 1.

## 6 Fire

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
at the relieving pressure, and the relieving temperature is the saturation temperature there. The relieving fluid
named in the relief valve register applies to the other contingencies.

## 7 Blocked outlet

With every outlet isolated, the relieving rate is the total normal inlet flow to the item, relieved as vapour at
relieving conditions. The normal flow of a stream is the mean of the operating record over its whole span, read as
the instrument schedule requires. The relief valve register gives the measurements that make up each item's inlet
flow.

## 8 Control valve failure

The valve is taken to fail fully open, and the relieving rate is the flow it then passes into the protected item
at the relieving pressure. The upstream pressure is the set pressure of the relief device that protects the source
of the stream.

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

## 9 Loss of overhead cooling

With the overhead condenser lost and heat input continuing, the relieving rate is the vapour the reboiler
generates at the relieving temperature:

    Q = UA * (Ts - Tb)      kW
    W = 3600 * Q / L        kg/h

with Ts the saturation temperature of the steam at the supply header pressure, its control valve taken as
fully open, Tb the saturation temperature of the column bottoms at the
relieving pressure, and L the latent heat of the relieving vapour at relieving conditions. UA shall be established
from the unit's operating record at the throughput the unit runs, as the mean over the record of the value each
day's duty and temperature difference give.

## 10 Tube rupture

One tube is taken to be severed, both ends discharging. The contingency need not be considered where the design
pressure of the low pressure side is at least 0.70 of the design pressure of the high pressure side.

Otherwise, for a liquid on the high pressure side,

    W = 3600 * 2 * 0.62 * At * sqrt(2 * rho * dP)      kg/h

with At the bore area of one tube in m2, rho the density of the high pressure fluid at its inlet temperature
to the exchanger in kg/m3, and dP the design pressure of the high pressure side less the relieving pressure,
in Pa. The relief is sized as a liquid.

## 11 Thermal expansion

For liquid blocked in and taking heat Q in kW,

    q = 3600 * alpha * Q / (rho * cp)      m3/h

with alpha the cubical expansion coefficient of the liquid at its temperature in 1/C, rho its density in kg/m3 and
cp its specific heat in kJ/kg K. Solar gain is taken as 0.80 kW/m2 of projected area.

## 12 Contingencies that need not be considered

A contingency need not be considered where it cannot raise the pressure of the protected item to its relieving
pressure. For a blocked pump discharge this is settled by the pump's shutoff pressure in its present condition;
the flow the pump delivers at the relieving pressure is read from its performance as last tested.

## 13 Credit for instrumented protection

A contingency may be set aside where a safety instrumented function prevents it and all of the following hold:

- the function is rated SIL 2 or better in the safety instrumented system register;
- it is proof tested at intervals of not more than 18 months;
- its initiating element is not the measurement used by the control function whose failure causes the
  contingency.

Where any of these does not hold, the contingency stands.

## 14 Correction factors

Kc is 0.90 where a rupture disc is installed upstream of the valve, and 1.00 where none is.

A conventional valve takes Kb = 1 and Kw = 1, but may not be used where the superimposed back pressure exceeds
10 per cent of the set pressure.

For a balanced bellows valve, Kb corrects vapour capacity against the ratio of back pressure to relieving
pressure, and Kw corrects liquid capacity against the ratio of back pressure to set pressure. Both are 1.00 at or
below the first ratio tabulated, and are interpolated linearly between entries.

| back pressure / relieving pressure | Kb |
|---|---|
| 0.30 | 1.00 |
| 0.35 | 0.99 |
| 0.40 | 0.97 |
| 0.45 | 0.95 |
| 0.50 | 0.93 |

| back pressure / set pressure | Kw |
|---|---|
| 0.10 | 1.00 |
| 0.15 | 0.99 |
| 0.20 | 0.97 |
| 0.25 | 0.95 |
| 0.30 | 0.93 |
| 0.40 | 0.88 |

## 15 Effective orifice areas

| letter | area, mm2 |
|---|---|
| D | 71 |
| E | 126 |
| F | 198 |
| G | 325 |
| H | 506 |
| J | 830 |
| K | 1186 |
| L | 1841 |
| M | 2323 |
| N | 2800 |
| P | 4116 |

## 16 Inlet line

For a valve in vapour service, the non-recoverable pressure loss in the inlet line, at the capacity of the
installed orifice under the valve's governing contingency, shall not exceed 3 per cent of the set pressure. A
valve whose governing contingency relieves liquid is not subject to this section. The loss is

    dP = (f * L / D + sum K) * rho * v^2 / 2      Pa

with f = 0.018, L the developed length and D the bore of the inlet line in m, rho the density and v the velocity
of the relieving fluid at relieving conditions, and the fitting losses

| fitting | K |
|---|---|
| 90 degree elbow | 0.30 |
| tee, flow through run | 0.20 |
| full bore ball or gate valve | 0.10 |
| entrance from the vessel | 0.50 |

## 17 The finding

A valve is adequate when all of the following hold, and inadequate when any does not:

- the effective area of the orifice it carries is at least the area required by its governing contingency;
- its type is permitted at its superimposed back pressure under section 14;
- its inlet line meets section 16.
