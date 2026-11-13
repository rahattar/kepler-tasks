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

### First cut (Nov 12 evening): low effort 2 of 3, in three minutes each

Records only, twelve layers, every one of which shows in a residual or is stated in a record. Reference within
1.8 per cent; 17 of 19 defective routes refused.

| probe | time | result |
|---|---|---|
| L1 | 2.8 min | 9 of 10 rows; SR06 9 per cent low (fitted its C on the last year only, after the drain change) |
| L2 | 3.0 min | **accepted** |
| L3 | 2.5 min | **accepted** |

All three found, unprompted: the held statics (each used the main's highest pressure since the previous drain was
shut), the overhaul's two eras, the sticking check, SR03's valve after the gland repack, the fast-ageing lead-in,
the crossed serials (kept the register's gauges), the replaced gauge and the replaced drain valve.

This repeats what the base-pressure rounds already established (`docs/design-note-base-pressure.md` on that
branch, "What the probe rounds establish"): **a layer that perturbs a residual is found by every probe at any
effort, because they fit until the residuals reach the reading noise.** What caught probes there was a unit the
plain budget fits quietly and wrongly, found only by asking which admissible structures the records cannot tell
apart, with one test to spend on it and decoys around it.

### The quiet core (next)

The sprinkler analogue of base-pressure's mechanism A:

- A main drain test gives a riser's own loss at one flow. Lead-in friction goes as q^1.85 and a partly shut
  control valve as q^2, so one flow cannot split them, and at 2.5 times the flow the two differ by 15 per cent.
- FP-12 clause 3.4 says which valves can stand partly shut: a supervised valve cannot (its switch reports it); an
  unsupervised one stands as it was left by the last work on its riser, or as it stood when the records begin.
- What closes a riser: lined ductile iron (C fixed, so the valve follows from one flow); a wall hydrant on the
  lead-in, flowed every year at about 900 gpm with the riser's own gauge read (C from that, the valve from the
  drain tests); supervision.
- **SR10 is the target**: cast iron, unsupervised, no hydrant, its valve partly shut since before the records
  begin. All friction fits it with C about 59, inside the site's range, and puts its limit on the lead-in and its
  pressure about 9 per cent high. Nothing steps and nothing in the log points at it.
- Decoys: SR03 (ductile, loud step after a gland repack: settled by its own records), SR06 (cast iron,
  unsupervised, work on the riser in 2024 with a change of drain pattern at the same visit: settled by its wall
  hydrant).
- One contractor's flow test, ordered once: a riser and a flow up to 1 000 gpm. It only splits the two laws at a
  high flow.
