# Boiler efficiency v0: low effort 3 of 3 (Nov 14)

The losses method (BE-3, written in full in `be3_boiler_efficiency.md`) applied to a year of hourly records
for each pulverised-coal boiler. The output is a row a day: efficiency on HHV, with a band of 0.15 points,
and coal fired, with a band of 1 per cent. BE-3 takes excess air from the CO2 reading. It says the fuel, gas
and air are "those of the boiler as it ran", and the package holds "the plant's readings and logs of them".

Two physical conditions are left unstated and show only as a model residual: the CO2 reading against the CO2
that the O2 probes and the logged delivery's stoichiometry imply.
- **drift:** the CO2 analyser's zero ramps from an onset to a cap of 1.2 to 1.8 per cent CO2 (16 times its
  stated accuracy). It is additive and smooth.
- **mislabel:** a run of 3 to 5 bunker fillings, 2.5 to 5 days, is logged as a delivery of the boiler's other
  coal. The residual steps by 0.7 to 0.85 per cent CO2 at fillings and matches the delivery actually fired.
  Coal is 11 to 109 per cent off on those days.

`boilers.py OUT_ROOT` regenerates the packages: two sound examples, harrow_3 (drift) and harrow_4 (mislabel)
pending, and six hidden boilers (drift; mislabel twice; both overlapping; both apart; none; lignite with a
mislabel).

## Routes (`compare.py`, `check_program.py`)
| route | hidden boilers out |
|---|---|
| reference `efficiency.py` (E from O2; fillings matched against a 3-week running median of the residual) | 0 (worst 0.18 of band) |
| `co2_driftcorr` (E from the CO2 reading less the running median) | 0 |
| `literal` (E from CO2, log as it stands) | 5 of 6 |
| `o2_logged` (E from O2, log as it stands) | 4 of 6 |
| `naive_id` (fillings matched to the nearest delivery, drift ignored) | 3 of 6 |
| `co2_identified` (fuel right, CO2 as read) | 3 of 6 |

## Probes, model opus, low effort
| probe | time | result | what it did |
|---|---|---|---|
| BL1 | 3.2 min | accepted, 0.18 of band | E from CO2 unless it disagrees with the O2 probes; fillings matched with drift allowed for |
| BL2 | 2.9 min | accepted, 0.18 | E from O2; fillings reassigned where the gas fits another delivery |
| BL3 | 4.0 min | accepted, 0.17 | E from O2; 15-day rolling median for the analyser's offset; fillings reassigned |

All three said BE-3's "as it ran" sentence was why they looked. All three found both conditions on the pending
boilers, and each built copies of an example with the faults injected (drift, steps, a drifting probe,
mislabelled fillings, all together) to test its detector. The bar is low 0 of 3, so xhigh was not run.

## Lesson
- **A residual between redundant instruments of one gas is a direct comparison.** Two O2 probes and a CO2
  analyser on the same duct invite a cross-check that this model makes as routine validation, and the
  O2-against-CO2 line (Ostwald) is ordinary boiler testing. The stoichiometry needed to see the residual is
  the task's own formula, so computing it is no barrier. Drift past CO2max (18.9 per cent read at 4 per cent O2)
  is impossible on its face.
- **The "as it ran" sentence was read as an invitation.** It is the honest statement of the requirement,
  and stating the requirement this way was enough at low effort.
- **Low effort tests its own detectors on injected faults.** A condition the examples do not show still gets
  tested, from a copy of an example that the run seeds with it.
