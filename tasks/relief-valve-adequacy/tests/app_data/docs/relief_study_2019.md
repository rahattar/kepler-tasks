# Unit 400 relief study

Document 400-SA-0012, revision 2, issued 14 March 2019. Prepared for the original plant.

## Basis

- Unit feed rate 310 t/d, the design basis of the unit as built.
- Feed analysis of 11 January 2019.
- Reboiler duties from the exchanger data sheets at the design feed rate.
- Control valve coefficients from the valve data sheets.
- P-401 performance from the pump data sheet curve.
- Vessel dimensions and elevations from the vessel data book, issue 2.
- Sized to RP-7 issue 4, whose sizing expressions, correction factors, orifice areas and conditions for
  instrumented protection credit are those of the current issue.
- PSV-404 carried a G orifice at the time of issue.
- Issue 4 carried no limit on the pressure loss of the inlet line; that requirement was introduced at issue 5.

## Findings

| valve | governing contingency | required area, mm2 | orifice | finding |
|---|---|---|---|---|
| PSV-401 | `control_valve_failure` | 559 | J | adequate |
| PSV-402 | `tube_rupture` | 517 | G | inadequate |
| PSV-403 | `cooling_failure` | 1167 | K | adequate |
| PSV-404 | `fire` | 215 | G | adequate |
| PSV-405 | `blocked_outlet` | 133 | F | adequate |
| PSV-406 | `fire` | 738 | J | adequate |
| PSV-407 | `fire` | 607 | J | adequate |
| PSV-408 | `fire` | 391 | H | adequate |
| PSV-409 | `fire` | 271 | G | adequate |

## Notes

1. The fire case for V-403 and T-401 was taken with no insulation credit, neither item having been insulated to a
   fire-resistant specification at the time of issue.
2. The relieving capacity required of PSV-403 is close to the capacity of the K orifice fitted. Any increase in
   reboil duty should be referred back to this study.
3. PSV-402 does not provide the capacity the E-402 tube rupture case requires. Action 400-A-0071 is raised to
   replace the valve with one of the next larger orifice.
4. This revision supersedes revision 1 of 2 February 2019 in the treatment of the PSV-402 tube rupture case
   only.
