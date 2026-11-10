# chill-bench-commissioning

Sixteen newly installed vacuum wafer chill stations, inspection metrology for all of
them, no thermal data for any of them, and a commissioning bench that will run only
eight test wafers. The agent must set backside helium pressure and dwell time for every
station so that a wafer reaches the temperature target without exceeding a transient
zone-uniformity limit or that station's own throughput budget. A station that meets all
three is commissioned; the recipe is accepted when at least fifteen of the sixteen are.

Every number quoted here comes from a script or a run record in `authoring/evidence/`.

## Difficulty

This is tool commissioning as it is actually done. When a fab installs new vacuum chill
stations, the equipment engineer and the process engineer qualifying them get a handful
of instrumented monitor wafers and a production schedule, not a characterisation
campaign per station. They have to decide which stations to spend those wafers on, infer
the rest from incoming-inspection metrology, and sign a recipe for every station in the
set. Overcooling wastes throughput on a tool that has not yet earned it; undercooling
hands off a wafer with a hot region.

The heat transfer itself is standard. Helium at these pressures has a mean free path
comparable to the plate standoff, so a temperature jump forms at each surface and the
gap conductance is `k/(d + 2g)` rather than `k/d`, with the jump distance `g` scaling as
`(2 - α)/(α P)` in the thermal accommodation coefficient α and the pressure P. Any
practitioner in this area knows that, and the task does not rest on it.

The difficulty is that **the evidence has to be bought, and the budget is half the
fleet.** Eight runs, sixteen stations. Eight stations can never be measured and can
only be reached through a model fitted across the ones that were. The campaign is
irreversible: a run spent at the wrong station is gone.

### What the unmeasured stations depend on

Each station's accommodation coefficient depends on two things printed in its
inspection report: plate surface roughness, and the passivation bath temperature of the
lot its plate came from. Neither the dependence nor its shape is stated. Three features
of the fleet make it hard to get right from eight runs:

- **Twelve lots, eight runs.** A per-lot offset — the natural first model when a lot
  field is present — cannot be fitted: at least four lots are never measured, and
  their stations have no prediction.
- **The bath effect saturates.** Below a knee the coefficient falls steeply with bath
  temperature; above it the passivation layer is saturated and bath temperature
  changes nothing. A short steep ramp and a long flat plateau is precisely the shape a
  straight line or a low-order polynomial cannot follow and a hinge can.
- **There is scatter the inspection report cannot explain**, about 3% of the
  coefficient per station. In the shipped draw thirteen of the sixteen stations sit
  below the structure, and the lowest-roughness plate, S05, sits 2.9 standard
  deviations below it. S05 is also half of the only same-lot pair with a large
  roughness contrast, and so the natural anchor for a roughness slope.

### Why the throughput limit makes that bind

Because the jump distance scales as `(2 - α)/(α P)`, every station's gap conductance
depends on pressure and accommodation coefficient only through the effective pressure
`P·α/(2 - α)`. The whole cooldown, and with it each station's optimum dwell, is
therefore the same whatever the coefficient; the coefficient only decides *which
pressure* realises it, and an error in the coefficient is exactly an error in pressure.
The dwell allowance acts purely as a tolerance on the coefficient: once the pressure is
centred in the band the allowance opens, a recipe survives any coefficient error inside
that band.

`authoring/evidence/station_windows.py` measures the band for all sixteen stations at
the shipped allowance, and `allowance_window.py` sweeps the allowance on the three
stations that span the fleet's coefficients:

| allowance | coefficient estimate may sit low by | or high by |
|---|---|---|
| 20% | 12.6–17.4% | 13.7–20.5% |
| 12% | 7.8–11.1% | 8.2–12.3% |
| **8% (shipped, all sixteen stations)** | **5.1–7.3%** | **5.3–7.8%** |
| 6% | 3.6–5.3% | 3.7–5.5% |

A station's tolerance is set by its geometry and, through `d ln f / d ln α = 2/(2 - α)`
for `f = α/(2 - α)`, shrinks as its coefficient rises. At a 20% allowance any model
that gets the shape roughly right lands inside the band. At the shipped 8% the station
coefficient has to be known to about six percent, which is the scale on which an
eight-run campaign's prediction errors actually lie. At that scale, *where the
campaign spent its runs* decides the outcome.

### Where the runs have to go

Seven stations — S04, S05, S06, S07, S09, S11 and S15 — are vertices of the fleet's
convex hull in (roughness, bath temperature). No model can interpolate to a hull
vertex: a campaign that leaves one unmeasured extrapolates to it, however well it
samples the rest, and staying inside each covariate's *range* separately does not
prevent it. With eight runs that leaves one free choice, and only 9 of the 12,870
possible eight-station campaigns leave no station outside the hull of what they
measured.

On this fleet the vertex that matters is S09, the low-roughness corner of the plateau.
A campaign that skips it reaches that corner by extrapolating from S05, which is low,
and loses S09 together with S12, the one low-roughness plateau station whose scatter
runs the other way. `authoring/evidence/design_mc.py` runs each strategy through 1000
identification-noise draws on the shipped fleet and through 300 fleets with freshly
drawn scatter, judging every station against its own window:

| campaign | measures every hull vertex | lot offsets, line or quadratic: shipped | hinge: shipped | hinge: redrawn fleets |
|---|---|---|---|---|
| the same-lot roughness pair, both bath extremes, the roughness extreme, three on the cold ramp | no, misses S09 | 0% | 19.5% | 82.7% |
| eight distinct lots, dense on the cold ramp | no, misses S09 | 0% | 47.6% | 83.3% |
| the same, with S09 in place of the roughness extreme | no, misses S04 | 0% | 99.2% | 84.7% |
| **the seven hull vertices plus one (the reference)** | **yes** | **0%** | **99.5%** | **86.3%** |

The wrong models fail on every campaign and essentially every fleet (at most 7% of
redrawn fleets): the hinge has to be found. With the hinge, the campaign decides
whether this fleet is commissioned. The seed, 20260919, has not changed since the first
version of this task, and S05 has held that draw in every version; it only matters once
the throughput limit is tight enough for a few percent to count.

The data are synthetic, from a disclosed seeded generator in `authoring/provenance/`.

## Ablation ladder

`authoring/evidence/baselines.py` builds each rung from what an agent can see — the
public inspection report and the traces the bench returns — never importing the
reference, and grades the recipe it produces with the shipped verifier. Every rung uses
the reference's own recipe policy (optimum dwell less a 1.5% margin, pressure centred in
the band), so the comparison isolates campaign and model. A measured station is
modelled as its true coefficient plus identification error of 0.006, about what the
reference's own identification achieves.

| strategy | one draw, graded by the verifier | clears the gate over 400 noise draws | stations lost on that draw |
|---|---|---|---|
| no bench runs, literature coefficient 0.40 | 2/16 | — | 14 |
| same-lot pair and bath extremes, lot offsets | 8/16 | 0% | 8 |
| hull + 1, lot offsets | 9/16 | 0% | 7 |
| same-lot pair and bath extremes, straight line in bath temperature | 10/16 | 0% | 6 |
| hull + 1, straight line in bath temperature | 12/16 | 0% | S03, S08, S10, S13 |
| same-lot pair and bath extremes, quadratic in bath temperature | 10/16 | 0% | 6 |
| hull + 1, quadratic in bath temperature | 13/16 | 0% | S08, S12, S14 |
| first eight stations in the file, hinge | 14/16 | 38% | S09, S12 |
| same-lot pair and bath extremes, hinge in the lumped coefficient | 14/16 | 4% | S09, S12 |
| same-lot pair and bath extremes, hinge | 15/16 | 19% | S12 |
| eight distinct lots (the previous reference's campaign), hinge | 14/16 | 49% | S09, S12 |
| same-lot pair with S09, hinge in the lumped coefficient | 16/16 | 97% | — |
| same-lot pair with S09, hinge | 16/16 | 99% | — |
| hull + 1, hinge in the lumped coefficient | 15/16 | 100% | S12 |
| **hull + 1 (the reference's plan), hinge** | **16/16** | **100%** | — |

Three things the ladder shows. First, the model has to be found: lot offsets, a
straight line and a quadratic in bath temperature lose three to eight stations on their
draws and clear the gate on none of 400 noise draws, whatever the campaign. Second, with
the hinge, the campaign decides. Every campaign that leaves S09 unmeasured loses it
together with S12 on most draws; the one such rung whose single draw cleared the gate,
at 15 of 16, landed in the 19% of draws that do, and the noise column, not the single
draw, is the rate. Third, regressing the lumped conductance coefficient `α/(2 − α)`
instead of α costs a poor campaign most of what it had and a good one almost nothing.

The 'clears the gate' column comes from the exact per-station windows that
`design_mc.py` relies on, and the ladder checks them against the verifier: on every
rung, the windows predicted exactly the stations the verifier failed.

## Reference solution

`solution/solve.py` buys its data through the same bench client and the same budget the
agent has, and never reads the sealed fleet parameters.

**Campaign.** Planned from the inspection report alone. It measures every vertex of the
fleet's convex hull in (roughness, bath temperature), so that each station it cannot
reach is an interpolation in both covariates at once. The one run left goes to the
station that minimises the worst prediction variance over the stations still
unmeasured, taken over every knee position the covariate model could find; that is
S16. All eight runs are made at 12 Torr for 22 s.

**Identification**, in three stages so the plate is never assumed isothermal: a first
pass with the plate pinned at setpoint, one plate heat capacity and chiller conductance
fitted across the fleet from the RTD traces, then a refit of every coefficient with
that plate model in place. It recovers 1940 J/K and 551 W/K against sealed values of
2000 and 550, and the eight measured coefficients to within 0.010.

**Covariate model.** It does not assume the shape. It fits the accommodation
coefficient — the surface property, not a lumped conductance — against roughness and
bath temperature twice: as a straight line, and as a hinge whose knee is chosen on a
grid. It keeps whichever has the smaller residual per degree of freedom, charging the
hinge for its extra parameter. On the shipped instance the line's residual is 0.069 and
the hinge's 0.011, with the knee at 48.0 C.

**Recipe.** Every station's dwell is set from its own optimum, which does not depend on
the coefficient, times `(1 + 0.08 − 0.015)`. The pressure is placed at the geometric
centre of the band that dwell opens at the estimated coefficient, with the top of the
band held 0.35 K under the zone limit, so the recipe absorbs the largest coefficient
error the allowance can pay for, in both directions at once.

It is independent of the verifier in four ways rather than one. It does not import the
grading module. It discretises the wafer into equal-**area** annuli where the grader
uses equal radial width. It integrates with scipy's adaptive LSODA where the grader
uses fixed-step RK4. And it identifies each coefficient by matching the times at which
the mass mean crosses four temperature thresholds, rather than by least squares over
the curve.

It commissions all sixteen stations on the shipped instance:

| criterion | worst station | limit |
|---|---|---|
| mass-mean temperature at end of dwell | 49.07 C (S07) | 50.0 C |
| peak zone difference during dwell | 24.75 K (S12) | 25.0 K |
| dwell against that station's own optimum | 1.069x | 1.080x |

The margins are thin by design: the allowance is 8%, and the reference spends it on
tolerance to coefficient error rather than on headroom it does not need. The tightest
station is S12, predicted 5.8% low against a window that, with the reference's guard,
reaches 6.7%; it is the station whose scatter runs opposite to its neighbours'.

### The reference against redrawn instances

`authoring/evidence/reference_reseeds.py` runs the actual reference end to end on twelve
instances — the shipped seed and eleven with the per-station scatter redrawn — each with
its own bench service, budget and grading. The fleet's geometry, roughness, lots and
bath temperatures stay fixed, so this measures the policy against the residual no
covariate model can explain.

| instances | cleared the gate | at 16 of 16 | at 15 of 16 | failed at 14 of 16 |
|---|---|---|---|---|
| 12 | 9 | 7 | 2 | 3 |

No dwell ratio on any instance exceeds 1.069, so no instance is lost on throughput,
and every station lost on any instance is one the campaign did not measure. Each
failure is two unmeasured stations whose scatter alone carries them outside a window of
about six percent. Nine of twelve is consistent, within the sampling error of twelve
draws, with design_mc's 86% for the same campaign and model, and it is the price of an
8% allowance with eight runs: with scatter of three percent of the coefficient and
eight stations unmeasured, two of them sometimes land outside the window whatever the
campaign. That is why the shipped instance's robustness is measured directly rather
than inferred from redraws: across 1000 identification-noise draws on the shipped
fleet, the reference's campaign clears the gate on 99.5% (`design_mc.txt`).

## Verification

`tests/test_recipe.py` replays the submitted recipe through the sealed physics in
`tests/physics.py`. Three criteria are evaluated per station:

1. mass-mean wafer temperature at the end of dwell at or below 50.0 C
2. maximum inner-to-outer zone difference during the dwell at or below 25.0 K
3. that station's dwell within 8% of that station's own shortest feasible dwell

**A station is commissioned when it meets all three, and the reward is gated on the
count: at least fifteen of the sixteen.** The threshold ships in the machine-readable
spec, `min_stations_commissioned` in `/data/spec.json`, as well as in the instruction.

Criterion 3 is **per station, not summed.** A summed budget pools slack across the
fleet; measured on an earlier version of this task it let a single station run 2.7x
its own optimum while the total still passed.

The fleet-level rule is a count rather than a conjunction, and fifteen is the count
that separates sound campaigns from poor ones. Moving only the gate, with the hinge model
and 1000 identification-noise draws on the shipped fleet (`design_mc.txt`):

| campaign | 16 of 16 | **15 of 16** | 14 of 16 |
|---|---|---|---|
| same-lot roughness pair and bath extremes (misses S09) | 8.5% | **22.2%** | 90.2% |
| eight distinct lots, dense on the cold ramp (misses S09) | 13.6% | **47.0%** | 99.7% |
| the same-lot pair with S09 in place of the roughness extreme | 74.6% | **99.4%** | 100% |
| the seven hull vertices plus one (the reference) | 32.3% | **99.3%** | 99.9% |

Requiring all sixteen would make even the reference's campaign mostly luck, because
S12's scatter runs against its neighbours'; allowing two would pass a campaign that
never reaches the plateau corner. The count forgives one station, not several: the
ablation ladder's wrong models lose three to eight stations each and clear the gate on
none of 400 noise draws, the cheat suite's measure-eight-guess-eight shortcut
commissions eight, and the best constant dwell commissions five. On an earlier fleet,
a conjunction over every condition had turned the verdict on a 0.08 K excess at one
station while every other margin was healthy.

### Ground truth

Nothing is compared against a stored answer. `tests/truth.json` carries the station
definitions and their coefficients; each station's constrained optimum is re-derived at
grade time, so the grader cannot drift away from the model that produced the traces the
agent bought. Ground truth is the simulator's evaluation of whatever recipe is
submitted and is never produced by running the reference. The generator and its fixed
seed in `authoring/provenance/` reproduce every data file byte for byte.

The graded quantities are defined on area means — mass mean over the wafer, area mean
over `r < 75 mm`, area mean over `r >= 75 mm` — so any adequately resolved model of the
same physics computes the same numbers. The physics module contains no randomness;
measurement noise exists only in the bench service, seeded at a fixed value.

That convergence is measured rather than asserted, and at an 8% allowance it has to be:
the reference's margins are thin, so the grader's own discretisation error must be an
order of magnitude below them. `authoring/evidence/method_study.py` sweeps the grader's
ring count and time step independently across three stations spanning the fleet, and
compares the shipped setting against the finest in each sweep:

| quantity | shipped (80 rings, 0.01 s) against 160 rings, 0.005 s | against the extrapolated limit | the reference's margin |
|---|---|---|---|
| end temperature | 0.0006 C | 0.0008 C | 0.93 C |
| peak zone difference | 0.014 K | 0.019 K | 0.25 K |
| optimum dwell | 0.001% | — | 1.1% of the optimum |

The time step is converged to the printed precision at twice the shipped step, and the
ring sweep converges at second order. The verifier searches for each optimum on a
0.05 Torr step, which can only place it at or after the continuous optimum, so any error
from that search is in the solver's favour. The grader ran 40 rings until the allowance
tightened to 8%; at 40 rings it read the zone difference 0.07 K high, a third of the
reference's thinnest margin, so the resolution was doubled at 1.6 times the grading
time.

`tests/test.sh` writes 0 to the reward file before doing anything and overwrites it
with 1 only on a clean pytest exit, so any crash leaves reward 0. It emits the CTRF
report at `/logs/verifier/ctrf.json` and the per-station breakdown at
`/logs/verifier/metrics.json`. Only the station count gates; the per-criterion
diagnostics are recorded and never fail a run on their own.

### Adversarial shortcuts

Twenty-two adversarial shortcuts are recorded in
`authoring/evidence/cheat_attempts.txt` and all twenty-two score 0: the empty and
malformed submissions, missing, duplicated and invented stations, negative dwell,
out-of-range pressure, go-slow, maximum pressure, zero dwell, one recipe copied to all
sixteen, and five ways of gaming the reference itself — every dwell padded 15% loses
the dwell budget on all sixteen stations, every dwell shaved 10% loses the temperature
limit on all sixteen, every pressure raised 15% loses the zone limit on all sixteen,
and replacing either the dwells or the pressures with their fleet mean commissions one
and three.

Two exist because the gate is a count. **The reference applied only to the eight
stations its campaign measures, with a plausible mid recipe on the other eight,
commissions eight.** And the constant-dwell impossibility is re-derived under the count
rule: a station is commissionable at a constant dwell `D` only if `D` falls between its
own optimum and 1.08 times it, because at that station's best pressure the time to
target *is* the optimum. Those windows run from `[6.36, 6.87]` s at one end of the fleet
to `[9.67, 10.44]` s at the other, and the best single dwell — 7.84 s — commissions 5
of 16. The gate needs fifteen.

### The bench

The commissioning bench runs as a compose sidecar. It holds the sealed coefficients and
the physics; neither is present in the agent's container, which reaches the service only
over the compose network. **The budget is decremented inside the service**, so it cannot
be edited, reset or bypassed from the agent side, and a request the bench refuses — an
unknown station, a pressure outside the supply range, an impossible run length — costs
no budget. Each test wafer carries its own small calibration offset on every
temperature channel, as real instrumented wafers do; a solver that fits those out
recovers the gap physics more cleanly than one that does not.

## Calibration

`authoring/evidence/probe_runs.txt` records thirteen clean-context probe runs on the
sixteen-station fleet: agents given only the brief, the data and the bench client, in
an isolated directory with no sealed physics and no grader, graded afterwards with the
shipped verifier. Screen-effort probes are matched to the platform's own easiness
screen — about 60 tool calls and 30 minutes, free to check and revise. Full-effort
probes get about 200 tool calls and two hours.

| allowance | screen effort | full effort |
|---|---|---|
| 20% | 4 of 6 | 2 of 2 |
| 8% (shipped) | 2 of 3 | 0 of 2 |

Three findings from those runs shaped the shipped design:

- **The physics is found reliably.** Every agent that built a sound forward model found
  the pressure-accommodation degeneracy unprompted, and every one found the hinge. None
  of those is a source of difficulty on its own.
- **At 20% the structure was invisible.** A centred recipe tolerated a coefficient
  error of about 13–20%; only gross forward-model errors failed anyone. That
  measurement is why the allowance is 8%.
- **At 8% the campaign decides.** Most agents converged on the first campaign in the
  Difficulty table, built around the same-lot roughness pair. Every failure lost the
  same two stations, S09 and S12, on the zone limit — low-roughness plateau stations
  predicted low — and none of the failing campaigns measured S09 or its lot-mate.
  Both passes reached that corner directly: one by spending its last two runs where
  its candidate models disagreed most, one by measuring S09's lot-mate. One
  full-effort run named S09 as its riskiest station after its budget was already
  spent.

Five runs at the shipped setting are too few to claim an effort gradient in either
direction, and none is claimed. What they do show is a pass rate well away from both 0
and 1, decided by a recognisable experimental-design choice rather than by trivia or
volume: spend the irreversible budget where the prediction is weakest, not where the
structure is most obvious.
