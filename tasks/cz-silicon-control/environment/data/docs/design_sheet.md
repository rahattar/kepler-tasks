# Puller 11 hot zone - process design sheet

Puller 11 grows 300 mm crystals (body grown over 304 mm nominal, ground to 300 mm; the grinder needs at least
301.0 mm of as-grown diameter everywhere). Hot zone HZ-B (new heat shield, new graphite side heater, new crucible
support) replaced HZ-A in August 2026.

## Steady state (HZ-B thermal model, vendor report TM-2026-14)

- Growth rate at zero melt superheat, crucible at 8 rpm, as a function of body length L (mm):
  v0(L) = 0.98 - 0.10 (1 - exp(-L / 400)) - 0.04 L / 1500  mm/min.
- Superheat sensitivity of the growth rate: 0.050 mm/min per K (interface heat balance; growth rate falls as the
  melt under the interface gets hotter).
- Heater power for zero superheat: p0(L) = 100 - 14 L / 1500 kW, plus a run-to-run offset (meltdown, charge,
  hot-zone aging) of a few kW.
- Steady superheat per kW above p0: kh(L) = kh0 (1 + 0.6 L / 1500) K/kW; the rise with L follows the falling melt
  level. The model does not give kh0.
- Run-to-run growth offsets of a few hundredths of mm/min, drifting slowly over the body, are normal.

## Dynamics (HZ-A commissioning, March 2024)

These were measured on HZ-A and have not been re-measured on HZ-B. They are listed for reference only.

| item | HZ-A value |
|---|---|
| heater to melt: transport delay | 15 min |
| melt bulk lag, then interface lag | 25 min, 12 min |
| kh0 | 0.45 K/kW |
| crucible rotation effect on growth rate | -0.006 mm/min per rpm above 8 rpm |
| convection settling after a rotation change | 5 min (first order) |

Superheat follows the heater power through the delay and the two lags in series. A crucible rotation change alters
melt convection and the heat reaching the interface; the growth rate shifts within minutes.

## Diameter camera

The bright-ring camera reads the meniscus ring, not the crystal: it reads the true diameter plus an offset, plus
-1.2 mm per mm of meniscus height above its equilibrium (see growth_physics.md). The offset was set to zero against
the post-growth caliper on HZ-A. It has not been checked on HZ-B.

## Limits

Pull rate 0.2-1.6 mm/min, slew 0.05 mm/min per min. Heater 60-140 kW, slew 0.6 kW/min.
