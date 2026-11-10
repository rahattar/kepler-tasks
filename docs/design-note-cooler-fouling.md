# Design note: cooler-fouling-assessment (reworked Nov 9-10 2026)

**Status:** zip cooler-fouling-assessment-20261109c.zip (md5 1722e7d26560855cf9123479c01d8dba) sent to Alex. Two
earlier zips the same day: 20261109 (the instruction-quality fix) and 20261109b (the same at the 8 h agent budget).
Needs a fresh easiness screen before delivery.

**Task:** `/app/output/fouling.csv` (unit, fouling_m2k_per_kw), the as-found fouling resistance of ten glycol
coolers E1-E10 on 2026-10-26. Band 0.04 m2K/kW on every unit, stated in no file the agent can read. Three
clean-and-test slots from a contractor service that charges a slot before the test and cannot be reset.

## Why 20261023c was rejected (instruction quality)
The band was printed in instruction.md and in assessment_requirement.md, and nothing in the files said how the
ribbed tubes' film gain follows their friction gain. Runs took the midpoint of the laws that fitted the one tested
ribbed unit and argued it sat inside the band. Fixed by deleting the band from every agent-visible file and putting
the relation in the retube note: `h_ribbed/h_plain - 1 = K (f_ribbed/f_plain - 1)`, one K for the rib form, same
for all three tube lots, K not given. The design sheet also gained the crossflow-velocity / baffle-spacing
relation, which was the other quantity a run had hedged on.

## Why 20261109b failed the easiness screen, and what 20261109c changes
2 of 3 low-effort runs solved it, median 3 minutes. The log named each unit's mechanism on its own line, the units
the records could not settle were flagged plainly and there were exactly three of them for three slots, and the
fouling history was one line plus a step on one unit. Three changes, all in the sealed definition:
- **Budget below the symptoms.** E1 is now a second new C-310 commissioned with E10 in June 2026, so four units
  need a test and there are three slots. The escape is a fact in the datasheet, not the inference: one rating from
  one program for two coolers built to one drawing in one batch, works certificates agreeing to a per cent. A
  clean test on either twin gives the factor that rating is out by. Left on the datasheet the untested twin misses
  by 0.07. Of 120 allocations, 2 pass (E8, E9 and either twin); best failing 0.073.
- **A fouling history that needs its own model.** The window is seven weeks (2026-08-24 to 10-11, assessment 14
  days later) and holds the two cooling-water events the log dates: ten days with the chlorine dosing pump down
  (DOSE_FAST = 8) and the shock chlorination of 09-28, which strips 0.6 of the biofilm grown over those days. One
  rate, a level shift across the chlorine-free days, a step at the dose. One line through the record misses three
  units by up to 0.33; the wrong one of the two events misses five by up to 0.50.
- **A load-bearing clean reference.** C-200 film scatter 2.5 % -> 10 %, so the design split used flat for every
  unit now fails two units instead of passing on its own. The two C-310s keep 1 %, which is what makes the twin
  transfer tight (0.007 of error).

## Layers
- **Data-only:** the open 2025 heat balance (-6.4 % against +-1 % on the eight others); the plugged-tube count,
  from the tube-side dp; each unit's own film split; the chlorine-free acceleration, visible only as a steeper ramp
  between two logged dates; the shock step; the ribbed friction gain per unit, from dp against its 2025 test.
- **Documented:** the RTD offsets from standby hours (E8 never stands by); the common return header, so the duty
  comes from the glycol side; the ribbed film/friction relation; the baffle-spacing relation; the shared C-310
  rating; the exponents 0.8, 0.6, 1.8; the area on open tubes only.
- **Allocation:** four units unsettled, three slots, one chain.

## Calibration
Reference worst 0.011 (E9). 216 sound variants all pass, worst 0.026 (tube-only split on E7). Nearest unsound
0.063. Every unit is failed by at least three routes; E4, the plainest, by exactly three. Watch the sound spread
when hardening: it reached 0.031 before the shock dose was moved a week earlier, which lengthened every
post-event segment without shortening the extrapolation.
