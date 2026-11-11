# MS-BP: base-pressure audit of the shop's vacuum chambers

## 1. Scope

MS-BP is the method by which this shop audits a vacuum chamber that does not reach its specified base pressure. It
fixes the condition the audit refers to, the gas budget and the pumping speed that make up the chamber's base
pressure, and the way the chamber's limiting cause is named. It applies to a chamber pumped by a turbomolecular pump
through a high-vacuum port, with its gas load measured or inferred from the chamber's own records.

## 2. The reference condition

Every chamber is referred to the same condition, whatever its records were taken at:

- **36.0 hours** from the start of roughing, following a vent to atmospheric air;
- the chamber wall at the reference temperature **20.00 C**;
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
outgassing table of the shop's vacuum data. q1 is the specific gas load at t = 1 h and 20.00 C.

C_w is the chamber's own wall gas load coefficient. The table's q1 is a nominal figure for a surface of that kind,
good enough to size a pump; the gas load of a particular chamber departs from it by a factor that depends on the
history of its surfaces - how long they stood open, what has been baked out of them, what has been deposited on
them - so **C_w is identified from the chamber's own records** and is not assumed to be one. The exponent alpha is
set by the desorption of water from that kind of surface and is taken from the table.

    f_vent = 1.00 after a vent to atmospheric air
    f_vent = 0.25 after a vent to dry nitrogen

    theta_w(T) = exp( (E_W / R) * (1 / T_0 - 1 / T) ),   E_W = 30.0 kJ/mol,  T_0 = 293.15 K

Below t = 0.05 h the law is held at its value at 0.05 h.

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

A trapped volume of this shop's chambers has a time constant of **48 hours or less**. A source that does not
fall measurably over a pumpdown is a leak and is reported as one: fitting it as a trapped volume of some hundreds
of hours describes the same constant and names the wrong mechanism.

### 3.4 Permeation

Atmospheric gas passes through the chamber's elastomer seals. Its gas load is proportional to the length of seal
exposed and rises steeply with temperature:

    Q_perm = K20 * L_seal * theta_p(T)

    theta_p(T) = exp( (E_P / R) * (1 / T_0 - 1 / T) ),   E_P = 42.0 kJ/mol

with L_seal the seal length in cm and K20 the seal material's entry in the seal table, in mbar L/(s cm) for
atmospheric air at 20.00 C. Permeation does not change with pumping time.

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

    p = p_N2 / sum_i ( x_i K_i )

with x_i the fraction of species i in the chamber's gas and K_i its relative sensitivity from the shop's vacuum data
(ar 1.29, co2 1.42, h2 0.42, h2o 1.12, n2 1.00, o2 1.01). The composition is that of the gas the chamber's mechanisms admit, in the proportions of their gas loads;
the vacuum data give the composition of each mechanism's gas.

Where a chamber carries both a cold cathode gauge and a hot-filament ionization gauge, the ionization gauge is the
chamber's reference instrument and the cold cathode gauge is a working instrument.

## 6. The limiting cause

A chamber's limiting cause is named as follows, and only as follows:

1. If the chamber's actual effective speed at the reference condition is below **0.75** of its rated effective
   speed, the cause is `pump-speed`.
2. Otherwise the cause is the mechanism of clause 3 with the largest gas load at the reference condition:
   `wall-outgassing`, `air-leak`, `virtual-leak` or `permeation`.

## 7. The audit result

For each chamber the audit reports three things, all at the reference condition of clause 2:

- its limiting cause, as clause 6 names it;
- its total gas load Q_total, in mbar L/s;
- its actual effective pumping speed S_eff, in L/s.
