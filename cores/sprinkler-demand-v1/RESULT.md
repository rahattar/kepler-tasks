# sprinkler-demand bare core v1 (Nov 12): low effort solves it, 1 of 3 accepted in eight minutes

The premise failed. Low effort looks at how well its fit explains the visible readings without being asked,
finds every kind of fault in five to eight minutes, and one of three runs was accepted on all eight hidden
systems. The screen allows 0 low solves, so no xhigh probes were run.

## Probes (opus, low effort)

| probe | time | hidden | what it built | what it missed |
|---|---|---|---|---|
| S1 | 8 min | **accepted, 8 of 8**, within 1.3% | static offsets; a robust fit of every C and every valve; port tags reassigned within each run by optimal assignment; misfit runs dropped | nothing |
| S2 | 5 min | 4 of 8 | the same, but readings that do not fit are dropped, not reassigned | DC-1, DC-4, DC-6 over the 20 s limit; DC-5 20% low |
| S3 | 14 min (program as it stood; the run had not reported) | 7 of 8 | static offsets; a soft-L1 fit; swaps undone for the whole campaign or run by run; a run's flow corrected from the common factor of its drops | DC-3 3.6% high |

- **All three found all five kinds of fault from the examples alone**, including the four that move no
  visible result. S1's and S2's reports name WH-B's gauge, WH-C's register, WH-E's swapped ports and WH-E's
  flow, and S3's program handles the same four.
- **They test the shift themselves.** S1 built packages from the examples with lower C, valves at factors of
  20 to 300, swapped tags and a wrong flow; S2 made nine damaged sheets. Once an agent has a forward model,
  "the same fault, larger, where it decides" is something it tries before it submits.
- **S2's three timeouts are a fault of the core, not difficulty.** The hidden grids are three to four times the
  size of any example. By the Nov 12 tips a size that decides the result belongs in the visible data.
- **DC-5 is the one miss on substance.** The swapped ports there are the only ones that carry the information
  on the branch lines, so discarding them leaves the lines at the register's figure. S1 and S3 undo the swap
  and pass.
- S3's miss is DC-3, the mis-entered flow on a drain run: 3.6% against a 3% tolerance.

## Reading

Unlabelled faults in a redundant record of a documented physical model are not a source of difficulty, whether
or not they move a visible result. The method is generic (robust regression, assignment, dropping what does not
fit), and low effort reaches for it at once. Together with v0 this closes the two ideas tried on this subject:
a decision made during the run, and inference nobody prompts.

What is left on this subject would have to be a fault that discarding cannot handle and that a generic fit
cannot absorb, in every hidden system and not in one. DC-5 is the only instance here.

The sections below are the author's side as built before the probes.

## What changed from v0

v0 named its unknowns and let the program choose a test; low effort designed the test in nine minutes. v1 keeps
the hydraulics and the timed re-run and moves the difficulty to inference nobody prompts:

- A package is the system as the records describe it (`system.json`) and the sheet of its re-rating campaign
  (`campaign.csv`): two static runs and six flowing runs, every gauge port read on each.
- The system is rated as it stands. The truth is the physical system, which the records need not match.
- Five things can be wrong, and nothing in the package says which:

  | kind | what it is | visible instance | hidden |
  |---|---|---|---|
  | register | a registered C the pipe has aged below | WH-C, decides its result | DC-4, DC-5, DC-8 |
  | valve | a valve off its seat | WH-D, factor 6 | DC-1 and DC-7 (sectional, 250 and 200), DC-6 (feed gate) |
  | ports | two ports entered against each other | WH-E, on one main | DC-2, DC-5, DC-8 |
  | flow | a run's flow written down wrong | WH-E, a tenth low | DC-3 (a third low), DC-6 (a quarter low) |
  | zero | a gauge with a zero error | WH-B, 0.8 psi | DC-4, 4 psi |

- Only WH-C's fault moves a visible result outside the tolerance. The others show plainly in the readings and
  move their example's result by under 1 per cent once every C is fitted: WH-D and WH-E fit with a reduced
  chi-square of 12 and about 1 000 against about 1 for a sound fit, and WH-B's gauge stands 0.8 psi off the
  others in both static runs. The hidden systems carry the same kinds where they decide the result.
- The examples give results only, not the condition found.

## Checks (seed 1 unless said)

| program | examples | hidden |
|---|---|---|
| reference (`ref_rerate.py`) | 5 of 5, within 0.3% | 8 of 8, within 0.7%; slowest run about 8 s of the 20 s limit |
| `ladder.py absolute` (records at their word, gauges as written) | fails WH-C | fails 7 of 8 |
| `ladder.py as_recorded` (the same, gauge zeros fitted) | fails WH-C | fails 6 of 8 |
| `ladder.py all_C` (every C fitted) | 5 of 5 | fails 6 of 8 (DC-1, 2, 3, 5, 6, 8), smallest miss 10.7% |
| `ladder.py all_C_valves` (every C and valve fitted) | 5 of 5 | fails 5 of 8 (DC-2, 3, 5, 6, 8), smallest miss 10.7% |
| naive (`naive_rerate.py`, every candidate refitted in full, cold starts) | | right answers; 41 s on DC-2 and 45 s on DC-1 against the 20 s limit |

- Reference on fresh scatter, seeds 2 to 9: every package within 0.85% (`seed_study.py`, `seeds_2_9.txt`).
- The reference names the right fault on every package. The runner-up explanation fits at least 30 times
  worse, except where two explanations are the same pipe (the feed main's C and its gate valve), and those
  give the same demand.
- Full table of the programs that stop short: `ladder_seed1.txt`.

## Files

- `hyd.py` truth physics and the campaign; `gen.py` builder; `specs.py` the thirteen systems and their shift
- `ref_rerate.py` reference; `ladder.py` programs that stop short; `naive_rerate.py`, `time_naive.py`
- `grade.py` grades at 20 s CPU; `seed_study.py` and `seeds_2_9.txt`; `ladder_study.sh` and `ladder_seed1.txt`
- `explore.py`, `isolate.py` the truth-side prototypes used to size the faults
- `brief.txt`, `mk.sh` probe brief and sandbox builder
