# sprinkler-demand bare core v1 (Nov 12): built and checked, not yet probed

Opus probes cannot run until the weekly limit resets (Nov 14, 3 am Central). Everything below is the author's
side: the reference, the programs that stop short of it, the naive version and the seed study.

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

## The premise to probe

A program that fits every group's C passes all five examples and fails six hidden systems. The question for the
probes is whether an agent looks at how well its fit explains the visible readings when the visible results
already agree, and then works out what the misfit is. Low effort is expected to stop at "every C fitted";
whether xhigh goes further is what the probe measures.

Things to watch in the probe reports:
- If every probe misses the sheet faults the same way, the visible instances are too quiet and WH-E or WH-D
  should be made to decide its own result.
- If low effort finds them, the instances are too loud; shrink them toward five times the scatter.

## Files

- `hyd.py` truth physics and the campaign; `gen.py` builder; `specs.py` the thirteen systems and their shift
- `ref_rerate.py` reference; `ladder.py` programs that stop short; `naive_rerate.py`, `time_naive.py`
- `grade.py` grades at 20 s CPU; `seed_study.py` and `seeds_2_9.txt`; `ladder_study.sh` and `ladder_seed1.txt`
- `explore.py`, `isolate.py` the truth-side prototypes used to size the faults
- `brief.txt`, `mk.sh` probe brief and sandbox builder
