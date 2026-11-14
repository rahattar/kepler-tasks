# pipe-ratchet-v0: low 3 of 3 accepted (Nov 14)

A timed program for the ratchet strain of pressurised pipe walls to a stated standard, PW-5: a 24-layer wall
in the hoop direction held by equilibrium, Chaboche kinematic hardening (three back stresses) with Voce
isotropic hardening, straight ramps between load states, ratchet strain at checkpoints. Every condition that
decides a hidden case is stated: the model, the history, and that hidden works may use other materials and
loads (three materials never seen, loads nearer the ratchet limit, more trips and hydrotests). Built after the
design gate of Nov 13 and chosen in a pre-mortem for a difficulty that survives being stated: the exact
integration of the hardening laws, which the usual return mapping does not give at any affordable step.

Six works of six lines, 6,800 to 9,400 states a line. Limit 15 s of CPU; band 3 per cent of the line's
greatest ratchet strain.

| program | hidden | visible |
|---|---|---|
| reference (`ref_ratchet.py`: lines together, one step a ramp, two on pressure ramps, exact laws) | accepted, 4.9 to 5.7 s, widest 0.48 band | accepted |
| backward Euler, one step a ramp (`wrong/be_one.py`) | out on 16 of 18 lines, up to 9.6 bands | out, up to 8.2 bands |
| backward Euler, 8 substeps | over the limit | over or out |
| exact laws, one line after another | accepted, 9 to 11 s | accepted |
| low 1 (49 min) | accepted, widest 0.26 band, 7.5 to 8 s | |
| low 2 (20 min) | accepted, widest 0.11 band, 9 to 10 s | |
| low 3 (16 min) | accepted, widest 0.15 band, 9 s | |

All three wrote the exact exponential update of the back stresses for a fixed flow direction,
carried the lines together, skipped elastic ramps, substepped the plastic part of a ramp, and budgeted their
substeps against their own CPU time. All three built harsher works of their own at the stated maximum to test
it. Their programs are more accurate than the reference.

Not at the bar. The pre-mortem was right that a low run that knows the exponential update passes; it did not
expect every low run to know it.
