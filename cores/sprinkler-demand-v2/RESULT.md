# sprinkler-demand bare core v2 (Nov 13): low effort reads the tests on file; 3 of 3 accepted in 8 to 11 minutes

v2 is v0 (the program designs its one field flow test: outlet, flow, two gauges) with flow tests on file in
every package. In the pending package without results and in six of eight hidden systems, one group the
register carries a C for has aged since; the tests on file show it and nothing lists it. The three examples
with results have no such group. 20 s of CPU a run, pressure and flow each within 3 per cent, hidden systems
no larger than the largest example.

## Probes (opus, low effort)

| probe | time | hidden | what it did |
|---|---|---|---|
| S3 | 8 min | **accepted, 8 of 8**, within 0.21% | compared the tests on file with the register, found PN-1's feed main at about C 94 against 120, treats such a group as open and designs the test for it |
| S1 | 11 min | **accepted, 8 of 8**, within 0.28%, slowest run 12.5 s | the same: "a test on file decides it, not the register alone" |
| S2 | 9 min | **accepted, 8 of 8**, within 1.05% | the same; starts each open C from 0.9 of its 2019 value |

The screen allows 0 low-effort solves, so no xhigh probes were run.

## Reading

- The device that held on lube-oil-survey and ventilation-district-airflow (a need the records show and do
  not list, one order placed during the run, the instance in a package without results) did not hold here.
- The difference: here the record that shows the condition is of the same kind as the program's own
  measurement (a flow test in the protocol's format), and the package format names it. A program that fits
  flow tests anyway fits the ones on file, and a drop 3.6 psi beyond the registered C in a 10 psi reading is
  the first thing the fit shows. In the two tasks that held, the tell was a difference between quantities
  the program had no reason to compare.
- With v0 and v1 this closes the subject: a decision made during the run, inference nobody prompts, and a
  record the register contradicts are all found at low effort on a documented hydraulic network.

## Checks before the probes

| program | hidden |
|---|---|
| reference (`ref_demand.py`), seeds 1 to 5 | accepted on all five, every pressure within 0.75%, slowest run 7.5 s |
| the register followed (`register_demand.py`, v0's reference) | fails 5 of 8 by 4.4 to 12.9% (DC-3 has an aged group and stays within 1.1%) |
| unoptimised second solution (`naive_demand.py`) | right answers; 22 s on DC-7, 130 s on DC-1 |

- A tree with one unknown on a main and one on the branch lines cannot be settled within 3% by one test at
  0.1 psi gauge scatter (the first build failed its own reference there on some seeds), so every pair of
  unknowns sits where one high-flow test separates them.

## Files

`gen.py` (specs, the shift of each hidden system, `core/manifest.json`), `hyd.py`, `harness.py`, `grade.py`
(20 s CPU), `ref_demand.py`, `register_demand.py`, `naive_demand.py`, `brief.txt`, `mk.sh`.
