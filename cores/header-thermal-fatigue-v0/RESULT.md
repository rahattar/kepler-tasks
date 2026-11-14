# header-thermal-fatigue bare core v0 (Nov 13): the fluid thermocouple's lag is read off the outer thermocouple at once; low 3 of 3

A timed program: for every start-up, shut-down and upset in a steam header's 1 s record, the largest stress
range at the nozzle bore and the fatigue damage (HF-3 in `core/data/docs`: radial conduction, nozzle stress,
rainflow, S-N). On the pending header and four of six hidden headers the fluid thermocouple sits in a heavy
thermowell (28 to 110 s); nothing lists it. The evidence is the outer-surface thermocouple, which HF-3 uses
only for the wall's starting temperature. 6 s of CPU a run; each range of 120 MPa or more within 3 per cent,
the total damage within 8 per cent. The brief said from the start that the results go into the register
unreviewed.

## Probes (opus, low effort)

| probe | time | hidden | what it did |
|---|---|---|---|
| H1 | 6 min | **accepted, 6 of 6**, worst 0.53 of the band | the model's outer surface 10 K off on HD-P; a 44 s lag fits to 0.04 K; ruled out wall thickness and diffusivity |
| H2 | 4 min | **accepted, 6 of 6**, worst 0.65 of the band | a "sensor check" comparing the predicted and measured outer surface; ruled out thickness and a plain delay |
| H3 | 10 min | **accepted, 6 of 6**, worst 0.56 of the band | the same check; the same lag from every event independently |

Low effort: 3 of 3. No xhigh round.

## Reading

- **A record that measures something the program's own model predicts is compared as a matter of course.**
  The model computes the outer surface anyway; checking it against the outer thermocouple is the obvious
  validation, and all three runs did it within minutes. This is the sprinkler v2 lesson (a flow test on file
  in the format of the program's own test) and I should have caught it at design time.
- **The estimate itself was no barrier.** A one-parameter fit with a physically clear signature (one lag
  fits all 24 events to the noise; thickness and diffusivity do not) is easy once the residual is seen.
- The time limit separated nothing: all three ran in 1.3 to 1.7 s; the unoptimised Crank-Nicolson loop would
  take about 48 s.

## Checks before the probes

| program | hidden |
|---|---|
| reference (`ref_fatigue.py`) | accepted, 1.2 to 2.0 s, worst 0.51 of the band; lags found 43, 68, 108 s for 45, 70, 110 |
| the record taken as the fluid (`recorded_fatigue.py`) | fails all four lagged headers by 4 to 12 bands |
| unoptimised (`naive_fatigue.py`, Crank-Nicolson stepped in a loop) | about 48 s with the lag fit |

## Files

`hf.py`, `gen.py` (specs, shift, `core/manifest.json`; the data is rebuilt by `mk.sh` and kept out of git),
`ref_fatigue.py`, `recorded_fatigue.py`, `naive_fatigue.py`, `grade.py`, `brief.txt`, `mk.sh`.
