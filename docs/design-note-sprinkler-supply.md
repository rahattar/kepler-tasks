# Design note: sprinkler-supply-rating

Started Nov 13 after Alex chose "sprinkler task in the accepted shape" (records, a diagnosis with quantities, no
answer key, mechanisms that need physical reasoning, as base-pressure-diagnosis). The two timed-program cores on
this subject were solved at low effort (`cores/sprinkler-demand-v0`, `-v1`); this is a different task on the
supply side, not a third version of them.

## The task in one paragraph

A distribution site has ten sprinkler risers, SR01 to SR10, fed from a private yard main that takes its water
from the city main through one connection with a double check backflow preventer. None of the risers gets its
placard pressure any more. For each riser the audit gives what limits it and two pressures at the standard's
reference condition: in the yard main and at the base of the riser. Deliverable: `/app/output/rating.csv`,
header `riser,limit,p_yard_psi,p_base_psi`.

## Physics (the standard's pressure budget)

    p_base = S - d_main(Q) - d_bfp(Q) - d_lead(q) - d_valve(q) - d_check(q)

- S: the city main's static at the connection, at the site datum. It moves through the day and the year.
- d_main = B (Q/1000)^1.85, the main's draw-down. B from the utility's hydrant flow tests.
- d_bfp = h_b + (Q/Cv_b)^2 for any forward flow. h_b is a constant, not a friction loss.
- d_lead = 4.52 L q^1.85 / (C^1.85 d^4.87). C is identified from the riser's own records.
- d_valve = (q/Cv)^2, negligible fully open. d_check = h_c + (q/Cv_c)^2 on risers with a lead-in check.
- q is the riser's own flow; Q is everything through the connection.

Reference condition: the riser at its placard flow q_d; 500 gpm of outside hose from the yard main (through the
connection, not through the lead-in); nothing else flowing; S at its reference level, the working-day
17:00-20:00 mean of the utility's record over the last full quarter.

`limit` is the element with the largest loss at the reference condition.

## Why no record reaches the reference condition

The routine test is the quarterly main drain test: about 350 to 450 gpm through the riser's 2 in. drain, against
placard flows of 850 to 1150 gpm plus 500 gpm of hose. The elements extrapolate differently: h_b and h_c not at
all, the lead-in as q^1.85, a throttled valve as q^2, the main and the backflow preventer at the larger flow Q.
Scaling the test's whole drop is wrong by tens of psi; so is forgetting the constants.

## Layers (first cut; target 12 to 15, several data-only)

1. Different flows and laws per element at the reference condition; constants are not scaled.
2. Trapped statics. With no flow the backflow preventer holds the highest pressure that has reached the yard
   since the last flow, so the static before the first test of a round sits several psi above the main's
   pressure at that hour. "Static minus residual" overstates the drop. Statics do not follow the hour; residuals
   do. The device data state that the assembly holds its outlet pressure; nothing says what that does to a log.
3. h_b is identified from the fleet's statics, differs from the data sheet, and stepped down at the 2025
   overhaul (the log says only "overhauled").
4. Lead-in checks on three risers: h_c from statics, one of them well above its data sheet.
5. Lead-in C: lined ductile holds its C; unlined cast iron ages, one riser fast, and the rating is at the audit
   date.
6. A control valve left partly shut after work on it: a step in one riser's drop at a maintenance date, to be
   carried as q^2 and named as the limit.
7. A supply gauge replaced part way, with a zero error on its certificate.
8. Two risers' gauge serials crossed in the log for three rounds.
9. B: pitot flow with the outlet coefficient from the hydrant list; one test on two outlets.
10. Cv_b from the yard hydrant tests; only the test after the overhaul describes the assembly as it stands.
11. One riser's drain valve replaced by a smaller pattern: its test flow changed.
12. Elevations: the utility's transmitter is in the pit below the datum; each supply gauge is above it.

## Open questions

- Whether to add one contractor's test ordered before its result is known (base-pressure had one). First cut is
  records only; decide after the first probes.
- Tolerances: aim 4 per cent on each pressure; check with the independent solution and the method spread.

## Probe log

(none yet)
