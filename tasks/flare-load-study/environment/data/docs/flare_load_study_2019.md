# Unit 400 flare load study

Document 400-SA-0012, revision 2, issued 14 March 2019. Prepared for the original plant.

## Basis

- Unit feed rate 310 t/d, the design basis of the unit as built.
- Feed analysis of 11 January 2019.
- Reboiler duties from the exchanger data sheets at the design feed rate.
- Control valve coefficients from the valve data sheets.
- P-401 performance from the pump data sheet curve.
- Vessel dimensions and elevations from the vessel data book, issue 2.
- Stack tip loss coefficient 1.55, the original vendor's figure for the tip then installed, referred to
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
| `power_failure` | PSV-403 | 47096 | 0.36 |
| `cooling_water_failure` | PSV-403 | 47096 | 0.36 |
| `instrument_air_failure` | PSV-401 PSV-405 PSV-407 PSV-409 | 75015 | 0.69 |
| `fire_zone_a` | PSV-401 PSV-402 PSV-409 | 20080 | 0.05 |
| `fire_zone_b` | PSV-403 PSV-404 | 18128 | 0.05 |
| `fire_zone_c` | PSV-406 PSV-407 PSV-408 | 41238 | 0.12 |

## Notes

1. The fire cases for V-403 and T-401 were taken with no insulation credit, neither item having been insulated to
   a fire-resistant specification at the time of issue.
2. Loss of power is governed by the two columns losing their overhead cooling. Any change to the supply the
   instrument air compressor stands on would bring the air failure cases into it as well, and should be referred
   back to this study.
3. The header as then installed passes the governing load with the inlet pressure below 1.0 barg. There is no
   margin for a further increase in reboil duty.
