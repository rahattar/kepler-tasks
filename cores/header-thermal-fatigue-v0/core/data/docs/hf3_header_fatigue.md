# HF-3: Low-cycle fatigue of boiler headers from transient records

Works standard, revision 2. It gives the fatigue damage done at the nozzle bore of a thick-walled steam header
by the start-ups, shut-downs and upsets in its plant record.

## 1. Scope

A header is a straight cylinder of inner radius r_i and wall thickness s (mm), its outer surface insulated, with
a nozzle bore through the wall. The material's properties are taken as constant: thermal diffusivity a (mm^2/s),
elastic modulus E (MPa), thermal expansion coefficient alpha (1/K) and Poisson's ratio nu.

## 2. Temperatures in the wall

The inner surface is at the temperature of the fluid. Through the wall the temperature T(r, t) follows radial
conduction,

    dT/dt = a (1/r) d/dr ( r dT/dr ),      r_i < r < r_o = r_i + s,

with the outer surface insulated (dT/dr = 0 at r_o). Each event of the record begins from steady running: at its
start the wall is uniform, at the temperature the outer-surface thermocouple reads.

T_m(t) is the mean temperature of the wall, weighted by area: T_m = 2 / (r_o^2 - r_i^2) times the integral of
T r dr from r_i to r_o. T_i(t) is the temperature of the inner surface.

## 3. Stress at the nozzle bore

    sigma(t) = k_p p(t) r_m / s  +  k_t E alpha / (1 - nu) ( T_m(t) - T_i(t) )

with p the gauge pressure (MPa), r_m = r_i + s/2, and k_p and k_t the nozzle's stress concentration factors for
pressure and for the through-wall temperature difference.

## 4. Cycles

The stress history of each event is counted by rainflow (ASTM E1049, the range-pair counting of the history's
peaks and valleys). What remains uncounted at the end of the event is counted as half cycles.

## 5. Damage

A cycle of stress range D_sigma above the cut-off does damage 1/N, with

    N = N_ref ( D_sigma_ref / D_sigma )^m ;

a half cycle does half that. Ranges at or below the cut-off do none. The damage of an event is the sum over its
cycles.

## 6. Results

For each event: its largest rainflow range (MPa) and its damage. The results are those of the continuous
problem; a calculation on nodes through the wall and steps in time is fine enough when halving both moves no
result by more than 0.2 per cent.
