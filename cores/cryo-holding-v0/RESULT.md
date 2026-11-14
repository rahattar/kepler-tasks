# cryo-holding bare core v0 (Nov 14): probes running

A depot's liquid nitrogen tanks (vacuum-insulated, perlite) are closed for a holding period while the recovery
compressor is overhauled. `holding.py PACKAGE_DIR OUT_CSV` gives each tank's pressure at the end of each day,
the nitrogen its relief valve vents and its state, to CS-4 (`docs_src/cs4_closed_holding.md`): homogeneous
saturated contents, daily heat UA (T_a - T), the standard's nitrogen table. One order a run, `nertest PACKAGE
TANK ...`, of at most `test_allowance` tanks.

- **Legible need**: 1 or 2 tanks with insulation work after the last campaign (CS-4 3.5). The examples'
  allowance is exactly that; a run with no order is out on those tanks.
- **Vacuum lost** (C1): one tank's heat leak is 1.6 to 2.4 times its sound value, no work logged. The only
  evidence: the recovery meter (one total for the depot) drops by that excess on the 9 to 13 days the tank was
  out of service. A depot multiple taken over all days spreads the excess over every tank. Allowance: one more.
- **Gauge chart** (C2): one gauge reads 0.87 to 0.91 or 1.09 to 1.13 of the contents; the only evidence is the
  gauge's rise on fill days against the weighbridge tickets. No order needed.
- west_quarry (pending) has both. Hidden: south_fen and mill_lane both; river_cut and high_wold C1; kiln_end C2;
  salt_marsh neither. Bands 0.15 bar, vented 5 per cent or 100 kg, `full` exact; limit 30 s against 0.3 s.

## Ladder (`ref_holding.py` with MODE)

| MODE | hidden out | what it does |
|---|---|---|
| full | 0 of 6, worst 0.15 of a band | finds the vacuum tank by its out-of-service days, tests it, refits the multiple without it; gauge factor from fills |
| noorder | 6 of 6 | no test |
| legible | 5 of 6 | tests the re-insulated tanks, one depot multiple for the rest |
| nogauge | 3 of 6 | everything but the gauge check |
| noinsul | 4 of 6 | everything but the vacuum tank |
| keepf | 4 of 6 | finds and tests the vacuum tank but keeps the multiple taken with it in |
