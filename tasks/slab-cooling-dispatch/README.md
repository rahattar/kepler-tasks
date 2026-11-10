# slab-cooling-dispatch

Supervisory control of a two-zone thermally activated slab (TABS) group on one chiller. The agent
receives a design sheet, eight weeks of BMS trend logs, an archive of the weather forecasts issued
over those weeks, the chiller's COP and capacity tables, a tariff and a maintenance log. It delivers
`/app/controller.py`, which the verifier runs in closed loop, every 15 minutes, over eight hidden
summer weeks, against a sealed simulation of the building.

## Difficulty

This is the work of a building controls engineer commissioning model-based supervisory control on
an existing radiant-slab building: replace a fixed BMS sequence with one that keeps the occupied
zones comfortable at lower cost, from the data the building already has. The building and its
occupants are synthetic, from a disclosed seeded generator; the weather is real (Chicago O'Hare
TMY3), resampled day by day with a seeded anomaly for the graded weeks.

The problem is hard for four reasons that compound:

1. **The graded quantity is not measured, and the as-built zones differ from the design sheet.**
   Comfort is judged on operative temperature (air, soffit, glazing and room surfaces), for which no
   sensor exists; it has to be carried by a model. Each zone's as-built water flow, envelope losses,
   effective solar gain behind occupant blinds and furnishing mass differ from the design sheet, and
   one of the eight logged weeks contains a valve that failed closed while the BMS kept commanding it
   open, recorded only in the maintenance log. Fitting the logs buys margin rather than feasibility:
   the reference's estimator and planner, run on a model written from the design sheet alone, cost
   1.166 at the reference's 0.2 K comfort margin and fail, and pass only with the margin cut to 0.1 K
   (1.139) or 0 (1.103, one zone-week over) (authoring/evidence/design_sheet_route.txt).
2. **The actuator acts across a lag of hours.** A step in supply temperature moves the operative
   temperature 10% of the way in about 3 h and halfway in about 12 h, so comfort on a hot
   afternoon is decided the night before, from a weather forecast. The forecast damps the diurnal
   swing (about 1.2 K too warm before dawn, 1.1 K too cool mid-afternoon), which is visible only by
   comparing the forecast archive with the logged outdoor temperature.
3. **The two zones share one chiller and one supply temperature.** The east zone peaks in the
   morning, the west in the afternoon. Colder water removes heat faster but costs more: at 25 C
   outdoors the COP rises from 5.2 at 15 C leaving water to 7.8 at 22 C. Capacity is finite and
   binds when both zones precool at night. The economic optimum therefore couples the zones through
   a nonlinear efficiency and a shared capacity, over a 48 h horizon.
4. **The calendar matters.** The building closes on federal holidays; Labor Day falls in the graded
   weeks.

What each piece is worth, with the exact models and states (authoring/evidence/ladder.txt, totals
relative to the benchmark): using the forecast as issued costs 4.5%, pricing every kWh at a fixed
COP costs 3.6%, ignoring the chiller capacity costs 8.2% and breaks the comfort limit in two
zone-weeks, missing the holiday costs 0.5%, and all four together cost 17%. Model-free sequences a
BMS would run either break comfort or cost 1.9 to 3.2 times the benchmark; none of the 24 tried
passes. With models fitted from the public data instead (the reference's own pipeline), the
reference passes at 1.117. The same controller using the forecast as issued scores 1.167 and
ignoring the capacity 1.152, and both fail; pricing every kWh at a fixed COP (1.138) or missing the
holiday (1.123) still passes on its own; with all four ignored it scores 1.257; and without a
comfort margin it is cheaper (1.071) but breaks comfort in three zone-weeks.

The allowance is 15% over the benchmark's total cost for the eight weeks, with at most one of the
16 zone-weeks allowed above 0.5 K h of occupied discomfort. It was fixed from the reference's
results on redrawn instances before any other controller was graded: the smallest 5% step at
least 3% above the reference's worst total (authoring/evidence/reference_reseeds.txt).

## Reference solution

`solution/fit.py` identifies both zones from `/app/data` and writes a self-contained controller
(`solution/controller_template.py` with its parameters embedded). It never reads the sealed plant,
the benchmark or the verifier.

- **Zone models.** Four states per zone (pipe-plane slab, soffit-side slab, air, room surfaces and
  furnishings), with the soffit's convective and radiative coefficients fixed from physics (5.0 and
  5.4 W/m2 K: a cooled ceiling and an emissivity of 0.92) because the logs cannot separate them;
  capacities, couplings, envelope, water-side conductance and solar fractions are fitted by
  multi-step simulation error over 2-day windows of the log, with the east valve treated as closed
  while the maintenance log says it was. The glazing inner surface comes from a steady-state window
  balance, and operative temperature from the stated view factors.
- **Estimation.** A Kalman filter per zone on the air and slab sensors, with an unmeasured-heat
  state that absorbs occupancy and model error.
- **Forecast.** The damping factor is estimated from the archive by regressing the logged outdoor
  temperature on the forecast's departure from its own 24 h mean (0.222; the generator uses 0.25),
  and undone on every issue.
- **Plan.** Every hour, a joint linear program over 48 h for both zones' heat extraction and the
  common supply temperature, with the zone dynamics condensed, the chiller capacity as a constraint
  and the cost per kWh (tariff over COP) linearised about the previous plan's supply temperatures
  inside a trust region. Comfort is a soft constraint 0.2 K inside the band during occupied hours.
  Valve duty is the planned heat over the available driving difference.

On the shipped instance it costs 1.117 times the benchmark with no zone-week above 0.5 K h (worst
0.09 K h). End to end on three redrawn instances (new graded weather, occupancy, forecast errors and
sensor noise, data regenerated and refitted) it scores 1.075, 1.059 and 1.059, with at most one
zone-week over. With its margins widened to 0.3 K it costs 1.144; with no margin it is cheaper
(1.071) but breaks comfort in three zone-weeks.

## Verification

The verifier rebuilds the sealed world from fixed seeds (`tests/world.py`): a warm-up and the logged
eight weeks under the building's old sequence, then the eight graded weeks, 2017-07-15 to
2017-09-08. `/app/controller.py` runs as the unprivileged user `nobody` in one sandboxed process for
the whole run (it keeps its state across all 5376 steps), from a scratch directory holding only the
controller and the protocol shim, over private pipes, with limits on CPU time, memory, file size and
process count; `/tests` is mode 700 and the verifier has no network. Each step it receives the
observation (sensors, the previous commands, the latest forecast issue) and returns a supply
setpoint and a valve duty per zone; the plant integrates each 15 min in 1 min sub-steps with the
valves open for whole minutes and the chiller's leaving temperature floating up when demand exceeds
capacity. Occupied operative temperature is evaluated every minute in each zone. The constructor has
600 s, each step 10 s, the whole run 7200 s of controller time.

The reward is 1 when the run completes, at most one of the 16 zone-weeks has more than 0.5 K h of
occupied operative temperature outside 21-26 C, and the total cooling cost (heat removed divided by
the COP at the actual leaving temperature and outdoor temperature, times the tariff, summed over
minutes) is at most 1.15 times the benchmark's. One test gates it; the weekly breakdown goes to
`/logs/verifier/metrics.json` and never gates.

Ground truth never comes from the reference. The benchmark is a controller that knows both zones'
exact models and states, receives the same forecasts with the generator's damping undone, assumes
design internal gains, keeps predicted operative temperature 0.3 K inside the band, and plans 48 h
with the chiller's efficiency and capacity, re-planned hourly. Its weekly costs are computed from the
generator by `authoring/provenance/run_bench.py` and shipped as `tests/bench.json`;
`authoring/provenance/regenerate.py` reproduces every data file byte for byte and, with `--bench`,
the benchmark costs. The plant as shipped is 12 slab cells and 1 min sub-steps; doubling the cells
and halving the sub-step moves the benchmark total by -0.4% and the reference's ratio from 1.117 to
1.124 (authoring/evidence/convergence.txt).

Twenty-three adversarial controllers ship as a runnable script
(authoring/evidence/cheat_attempts.py, run with the verifier image's interpreter and pins; output in
cheat_attempts.txt) and all score 0: ones that hunt for the sealed files, write the reward file,
forge replies on the protocol pipe, signal the verifier, fork-bomb, exhaust memory, hang, return
non-finite, wrong-typed or missing commands, never cool, or cool flat out. A probe controller
confirms that the sealed files, the verifier's memory, environment and file descriptors, and the log
files are out of its reach, and that nothing it leaves behind survives the run. The reference with
every valve held open 40% longer than planned, or with the supply 1 K colder than planned, still
passes (1.114 both): the estimator absorbs actuator errors, so these are robustness controls, not
loopholes.
