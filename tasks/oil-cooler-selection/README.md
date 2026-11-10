# oil-cooler-selection

A plant replaces its lube oil coolers in kind with standard shell-and-tube designs from a vendor catalogue and wants
a program that makes the selection. The solver gets the selection procedure, the plant rating standard (Bell-Delaware),
the catalogue, the case package format and one example cooler with the plant engineer's selection, and delivers
`/app/output/design.py`, which is run on eight hidden coolers' case packages and must select a compliant design within
6 % of the cheapest one for at least seven of them.

## Difficulty

A plant's mechanical or process engineer does this when the plant replaces its lube oil coolers in kind and wants every selection made the same way: set the design case from last summer's operation, rate the vendor's standard designs with the plant rating standard, and buy the cheapest one that meets the requirements. The program is reused for every cooler, so it has to be right for coolers nobody has looked at. The coolers, records and catalogue are synthetic, written by authoring/provenance from a sealed definition.

The core difficulty is that the design case comes from historian records, and the program must recognise, without seeing the data first, what a plant engineer recognises in them:
- Calibration: readings before an adjusting calibration carry the as-found error, so a flowmeter that read 9-12 percent low hides the real summer peak.
- Transmitter faults that nobody flagged: a transmitter frozen at a value from before the heat wave, and one left out of its thermowell during insulation work, reading the air in the pipe rack. Neither is marked bad in the historian. Both are shown up only by the second cooling water measurement at the tower basin outlet, which the cooler inlet should track within a steady offset, and the second only by a quiet log line about putting the transmitter back in its thermowell.
- Instrument glitches: a single 10-minute value far outside what the process can do (cooling water at 60 degC, oil flow nearly tripled) inflates a one-hour design value and buys a cooler 14-26 percent too dear, while real short process upsets of the oil inlet temperature are part of the design case and must stay.
- The oil in service: a grade change after the latest analysis means the new grade's typical properties, not the analysed oil.

The selection itself is real engineering work: Bell-Delaware shell-side rating with leakage, bypass and laminar corrections and the wall viscosity correction for a viscous oil, temperature-dependent fouling on the water side, P-NTU for shells in series, tube support spans, and a price-ordered search in which the cheapest compliant design typically sits within a fraction of a kelvin and a few kPa of the limits.

The example cooler shows only a flowmeter calibration correction. Leaving out any one of these steps gets 2 to 7 of the 8 hidden coolers wrong (authoring/evidence/route_study.txt) against an allowance of 1.

## Reference solution

solution/design.py is the reference program; solution/solve.sh installs it as /app/output/design.py and runs it on the example. For one case package it does the following.

Design case:
- The trend is cut to the period in case.json.
- Each adjusting calibration's as-found error is removed from the readings before it (percent of reading for the flowmeter, K for a temperature).
- A single value that departs from both neighbours, which agree with each other, by more than a quarter of the median flow, 20 K (oil inlet) or 5 K (water) is a glitch and is replaced by the neighbours' mean. Two-sample oil upsets are kept.
- The water inlet transmitter is compared with the basin outlet transmitter. Their usual offset is the median difference where neither is frozen (identical values for an hour). Where the inlet transmitter is frozen, or where the 13-sample median of its deviation from basin outlet plus offset exceeds 0.8 K, the basin outlet plus offset is used.
- Design values are the highest one-hour means on the time axis.
- Oil: the latest analysis, or the typical properties of a grade the log says was put in after it.

Selection:
- Catalogue configurations (shell, tube, length, passes, layout, shells in series) in order of installed price.
- For each, the water side is checked once (it does not depend on the baffles). A configuration that cannot reach the oil outlet limit with its closest baffles is skipped.
- Otherwise every cut and every spacing in 5 mm steps is rated by RS-12 as written in rating_standard.md, and the first design meeting every limit is written.

On the 8 hidden coolers it selects the cheapest compliant design every time (price ratio 1.000), in about 2 s per cooler.

`solution/solve.sh` installs `design.py` and runs it on the example case (a few seconds).

## Verification

tests/grade_cases.py runs the submitted /app/output/design.py on each of eight hidden cooler case packages (tests/hidden; the agent's image does not contain them).

The verifier image has the agent's /app/data at the same path and read-only (tests/app_data, a copy that authoring/provenance/build.py writes). A program that reads the documents at run time behaves as it did in development.

How each case is run and judged:
- design.py alone and the case package are copied to a scratch directory. It runs as the unprivileged user nobody, with only PATH and HOME set, as `python3 -I design.py CASE OUT.json`, within 300 seconds; the eight runs are sequential, so the worst case (2400 s) fits the 3600 s verifier timeout. The instruction states these run conditions, including that design.py must be self-contained.
- The design written is checked against the catalogue (sizes, cut, spacing in whole mm between 0.2 shell ID and the TEMA support limit).
- It is then rated by tests/rate.py, the rating standard RS-12 (a copy of authoring/provenance/rate.py), at the cooler's sealed design case (tests/hidden/truth.json, built from the true process values, which stays in /tests, root-only).
- A case is right when the oil outlet is within its limit plus 0.3 K, both pressure drops within their limits plus 3 percent, the tube velocity in range, and the installed price at most 1.06 times the cheapest design meeting the limits exactly (found by authoring/provenance/gen3.py with every cut and a 5 mm spacing step).

The 0.3 K and 3 percent allow for round-off between sound implementations of RS-12. The single pytest test passes when at most 1 of the 8 cases is wrong. Per-case results go to /logs/verifier/metrics.json and do not affect the reward.

The hidden coolers carry, by design:
- flowmeter calibrations with as-found errors of -8 to -11 percent (four coolers) and a water transmitter calibration error (two);
- a frozen water inlet transmitter through the heat wave, logged as restarted on the day it recovered (two);
- a water inlet transmitter out of its thermowell (two);
- single-value glitches on water temperature (two), oil inlet temperature (one) and oil flow (one);
- an oil grade change after the latest analysis (two);
- oils from ISO VG 32 to 100, limits and cooling water allotments that differ per cooler.

Why at most 1 wrong:
- Correct side: authoring/evidence/independent_design.py, a second program sharing no code with the reference (pandas time windows, Hampel filter, rolling-median tracking check, brentq on the heat balance, tube counts from the catalogue rule, a 10 mm spacing grid), gets all 8 right (independent.txt). Other sound settings (spacing step 1 or 25 mm, offset by mean, tracking limit 0.5 or 1.5 K, other glitch and frozen limits) also leave the reference at 0 wrong (method_spread.txt).
- Wrong side: leaving out any one step gets 2 to 7 coolers wrong (route_study.txt).

A program that always writes the example's selection gets 6 of 8 wrong, and one that always writes the largest design 8 of 8 (constant_null.txt).

The agent works as a separate user that can only write to /app/output; /app/data is read-only. The verifier runs separately without network, and /logs/verifier is root-only.

Files in `authoring/evidence/`: `common.py` (grades a program text with the verifier's own grade_cases),
`route_study.py` (each check or step left out), `method_spread.py` (other sound settings), `independent_design.py`
and `independent.py` (a second program sharing no code with the reference), `constant_null.py`, their `.txt`
outputs, and `preflight.py` (structure, names, ASCII, sealed design cases against the definition, byte-exact
regeneration by `authoring/provenance/build.py`). `authoring/provenance/` holds the rating standard (`rate.py`), the
catalogue (`catalog.py`), the case generator (`gen3.py`), the public documents (`docs/`) and `build.py`.
