# conveyor-drive bare core v0 (Nov 13): low effort 3 of 3 accepted, in about two minutes each

Idea 1 of the second ideation round, picked by Alex. A timed program on shifted hidden data, built at a tenth
of shipping size (lines of three or four flights, one day of feed log at 5 s). The program reads a line
package (flights, profiles, a drive register, five survey campaigns, a feed log) and gives the mean, greatest
and least motor power and the peak traction ratio of every drive in every 15 minute interval, to a standard,
BC-3, that states the physics: motion resistance, the load carried along the belt at the belt's own speed,
slip drives that share the load through their slip, belt stretch on the pulleys, a gravity take-up.

**What was meant to decide a hidden case.** A drive's no-slip belt speed is pi D n0 / (60 i), with D the pulley
diameter over its lagging. The register holds D as measured when the pulley was lagged. On eight drives of five
of the six hidden lines, and one of the pending line, the lagging has worn 0.9 to 1.9 per cent. Rated slip is
about 3 per cent, so the shares of every drive on such a flight move 9 to 40 per cent of rated power. Nothing
says so. In the surveys the worn drive's shaft speed and the belt speed from the weigher's wheel disagree by
the wear, at every campaign.

## What was measured

| program | hidden rows out, of 4,128 | examples | time a line |
|---|---|---|---|
| reference (`ref_drives.py`, diameters from the surveys) | 0; worst 0.18 of a band | accepted | 0.2 s |
| pulley diameters as registered (`as_registered.py`) | 1,728: every drive of the eight flights, 2 to 10 bands | accepted | 0.2 s |
| low 1 (opus) | **0: accepted**; worst 0.06 | 0.19 per cent of rated | 3 to 5 s |
| low 2 (opus) | **0: accepted**; worst 0.04 | 0.18 | 3 to 4 s |
| low 3 (opus) | **0: accepted**; worst 0.06 | 0.16 | 6 to 9 s |

| probe | minutes | tool calls | the lagging | in its own words |
|---|---|---|---|---|
| low 1 | 2.2 | 6 | found, PI-3 head2 named at 985 mm against 1,002.1 | "The lagging can wear after it was measured, so the register's diameter isn't always right." |
| low 2 | 2.1 | 8 | found, PI-3 head2 named, 1.7 per cent | "I also let the fit adjust each pulley's diameter, because the register records it as measured when the pulley was lagged and lagging wears." |
| low 3 | 2.2 | 6 | covered without naming a drive | "Because the pulley speed is fitted, worn lagging is covered rather than trusting the register diameter." |

No xhigh probes were run.

## Why it fell

- **The record came with a physical reason to doubt it.** The package format has to say what the diameter is
  ("over its lagging, measured when the pulley was lagged"); all three read that as a quantity that drifts.
- **The surveys measure more than the calibration needs, and the standard's own equations tie the surplus
  together.** A campaign gives belt speed, shaft speed and power; rated slip and the friction factor use up two
  of the three. BC-3 section 4 links the third to the other two through D. Two probes wrote one least-squares
  fit of the standard's equations to the campaigns with D free; the third worked D back directly. The audit
  before the probes had shown the hand-formula route quiet (rated slip spread 0.2 to 0.4 per cent, friction
  factor unmoved) and the re-solved survey state loud (28 per cent of rated on PI-3 against 0.3 elsewhere); the
  probes went straight to the loud route because a survey state is itself a full instance of the model.
- **The law I counted on nobody forming was an equation in the standard.** In ventilation-district-airflow the
  node balance is not needed to turn a survey into a resistance. Here the kinematic relation is how a survey
  turns into a slip.

## Reading

Not at the bar. With rod-pump v0 this makes two cores in one day lost to the same thing from two sides:
a contradicted record holds only if (1) nothing in the documents gives it a physical reason to drift, and
(2) the evidence against it is not joined to anything the program calibrates or computes by an equation the
standard states. Lube oil analyses pooled under a register's grouping meet both. A dimension that wears,
measured twice over in every survey, meets neither.

Built small on purpose (vent-fan-stall's lesson): about an hour to build, two minutes to probe.

## Files

`convsim.py` sealed physics; `gen.py` nine lines (`LINES`, `worn` the flights with worn lagging);
`core/environment/data` what a probe sees, `core/hidden`, `core/truth`, `core/sealed`; `ref_drives.py`,
`as_registered.py`, `grade.py`; `brief.txt`, `mk.sh`; `probes/` the three programs as graded; `logs/`.
