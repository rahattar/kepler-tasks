# Fact sheet for the instruction of base-pressure-diagnosis

For Alex's rewrite of `instruction.md`. Everything below is what the instruction has to carry; the wording is
yours. This file is **not** part of the bundle. After the rewrite, run
`python3 -I authoring/evidence/preflight.py` from the bundle: it checks every item marked (P).

## The scenario, in one line

The shop audits the ten vacuum chambers that are not reaching their specified base pressure, under its own
standard MS-BP. For each chamber: what limits it, and two numbers.

## The reference condition

Everything the audit reports is at one condition, and the instruction should state it so there is nothing to infer
(P: the instruction or the standard fixes it): **16 h from the start of roughing after an air vent, the chamber
wall at 20 C, nothing in the chamber.** It is MS-BP clause 2.

## Input paths, all absolute (P: every one of these appears in full)

- `/app/data/docs/ms_bp_audit.md` - the standard
- `/app/data/docs/vacuum_data.md` - the shop's vacuum data (pump curves, outgassing, seals, gauge sensitivities)
- `/app/data/docs/records_format.md` - what each record file holds
- `/app/data/docs/audit_note.md` - the vacuum engineer's note on this quarter's list
- `/app/data/docs/vacwork.md` - the test order and what each test buys
- `/app/data/chamber_register.csv`
- `/app/data/base_pressure_log.csv`
- `/app/data/speed_tests.csv`
- `/app/data/turbo_controller.csv`
- `/app/data/maintenance_log.csv`
- `/app/data/shop_climate.csv`
- `/app/data/gauge_certificates.md`
- `/app/data/example/` - one chamber's records with the audit result MS-BP gives for it

## The command and the booking (P: the budget figure 1 and the word vacwork appear)

- `vacwork status` reports the order; `vacwork submit < plan.json` places it.
- Up to **1 test** across the whole fleet.
- Placed **once**: no result is known until the order has been placed, and it cannot be changed, extended or
  replaced afterwards.
- Reports are written to `/app/vacwork/`.
- The plan format is in `vacwork.md`, and `vacwork submit` prints it on a bad plan.

## The output (P: the header appears exactly)

- Path: `/app/output/diagnosis.csv`
- Header, exactly: `chamber,cause,q_total_mbarl_s,s_eff_l_s`
- One row for each of VC01 to VC10, none repeated, missing or unknown.
- `cause` is one of `air-leak`, `virtual-leak`, `wall-outgassing`, `permeation`, `pump-speed`, spelled as the
  standard spells it (P: all five names appear).
- `q_total_mbarl_s`: the chamber's total gas load at the reference condition, mbar L/s, within **4.0 percent**
  of its true value (P).
- `s_eff_l_s`: the chamber's actual effective pumping speed at the reference condition, L/s, within **3.0 percent**
  of its true value (P).
- A regular file of at most **100000 bytes** of ASCII text (P). Blank lines, surrounding spaces and any row order
  are accepted; nothing else is.

## Also worth saying

- Python 3, numpy, scipy and pandas are available.
- `/app/data` is read-only.

## What the instruction must not say (P: all checked)

- No heading of any kind.
- None of these words: grader, verifier, reward, score, pass, fail, tested, graded, partial credit. Watch
  "speed-tested" and "fails its specification" - use "speed test" and "is not reaching".
- No hint at any trap or mechanism. Preflight rejects the words drift, crossed, swapped, misfiled, trap, baffle,
  degraded, contaminated, thin, beware, careful, "note that", "do not forget", "remember to", as whole words.
- Nothing about how many chambers must be right. The two tolerances are stated; that every chamber must be right
  is not.
- The last paragraph must be exactly, and only (P):

  You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this
  task.

## My draft

`instruction.md` in the bundle is a draft that passes preflight. Replace it and re-run preflight.
