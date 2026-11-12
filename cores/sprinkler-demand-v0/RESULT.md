# sprinkler-demand bare core v0 (Nov 12): probes cut off after 9 minutes; the low drafts already had the test design

v0 is a timed program with one decision made during the run. `demand.py` reads a wet-pipe system's package,
spends the system's one field flow test (it chooses the outlet, the flow and the two gauges), settles the pipe
condition the records leave open, and reports the riser-base pressure and flow of the most demanding design
area. Eight hidden systems, 60 s of CPU a run, pressure and flow each within 3 per cent.

## What was measured

| check | result |
|---|---|
| reference, seeds 1 to 4 | accepted on all four; worst pressure error 1.94 per cent (DC-6, seed 1); slowest run 24 s (DC-4) |
| naive version (bisection, cold starts) | DC-4 stopped at the 60 s CPU limit; DC-5 finishes in 25 s |
| convenient test instead of a designed one | fails most hidden systems by wide margins (FC-A with R1 and the far end of main A) |

## Probes (opus): all six stopped by the weekly usage limit about 9 minutes in

None finished, so there is no solve count. The drafts they left were graded as they stood (seed 1):

| probe | draft at cut-off | accuracy on the systems it finished | what failed |
|---|---|---|---|
| low S1 | 7 of 8 | all within 1.0 per cent | DC-4 over the limit (62 s) |
| low S2 | 7 of 8 | all within 1.4 per cent | DC-7: singular information matrix, a crash |
| low S3 | 3 of 8 | all within 0.5 per cent | five systems over the limit |
| xhigh T1, T3 | no result yet | | program not runnable yet |
| xhigh T2 | no program yet | | |

- **All three low drafts design the test by Fisher information** over outlets, flows and gauge pairs, and fit
  the unknowns by least squares. They open the same outlet as the reference on most systems. Nine minutes was
  enough to find this.
- **What is left for them is speed and one crash**, which is the kind of gap journal-bearing v3 showed closes at
  either effort.
- The screen allows 0 low-effort solves. Two drafts at 7 of 8 after nine minutes make 0 of 3 very unlikely.

## Reading

Unfinished, but the direction is clear: choosing the test is not a source of difficulty. A parameter the
package names as unknown, a documented model, and a test to choose reduce to a small design search plus a fit,
and low effort does both at once. This agrees with the calibration notes (a test budget is planned correctly at
low effort) and with the journal-bearing cores (a time limit changes the programs, not who passes).

The saved low probes can be resumed after the limit resets (Nov 14, 3 am Central) to turn this into a count.

## Files

- `hyd.py` truth physics and the field test; `gen.py` examples and hidden systems with their shift
- `ref_demand.py` reference; `naive_demand.py` the unoptimised version (imports the reference)
- `harness.py` runs a program on one package and answers its test; `grade.py` grades the hidden set at 60 s CPU
- `brief.txt`, `mk.sh` probe brief and sandbox builder
