# twin-oil-lines v3 (Nov 14): both conditions stated, low 2 of 3 accepted. Do not state them

The fuel-transfer-lines bundle (core v2's data, TS-2 4.2 and 4.3 stated, 2.5 per cent band, 40 s) with the two
deciding conditions stated, as the design gate first read on Nov 13 seemed to require (`docs/playbook.md`, after
the engine-indicating rejection):

- 5.5 a bore in service can be less than laid, where deposit has built up; D in section 3 is the bore in service;
  the pair's surveyed division settles it (4.1);
- 5.6 a covering can change with no work on it; campaigns that differ by more than 5.4's accuracies say so.

The method is left open: nothing says to survey these pipes, how to solve the bore, or what the spare places
of the allowance are for.

| probe | effort | time | six sites |
|---|---|---|---|
| L1 | low | 12 min | out on 8 records of canal_basin's narrowed line, 9.1 bands |
| L2 | low | 10 min | accepted, 0.40 of the band |
| L3 | low | 20 min | accepted, 0.36 of the band |

All three ordered exactly the reference's pipes at every site: the re-covered ones, the failing covering and
the narrowed pipe. All three solved the bore from the pair's division. Unstated, the same data was low 0 of 6
(core v2 and bundle) and xhigh 2 of 6.

- **This is engine-indicating v6 and rope-bending again, on a third physics.** Once the condition and its
  criterion are written down, a careful program meets it at low effort in ten to twenty minutes. The pair's
  history, the coefficient inversion and the bore solve are no barrier when the standard says what to solve.
- **The pre-mortem written before probing said so.** At 1 of 3 already the bar is missed.
- **The gate was corrected the same night** (ventilation 20261113b approved, official 3 of 8): a physical
  condition may stay unstated where public evidence identifies it unambiguously, a residual well outside the
  stated accuracy. Both conditions here are of that kind (the pair's two pressure drops 0.142 to 0.185 apart
  in ln against 0.010 at 176 sound pairs; the failing covering 0.163 to 0.210 against 0.022 at 427 pipes), and
  the one rule no evidence settles, the pair's carry-over, is stated in 4.2 and 4.3. So fuel-transfer-lines
  ships unstated, and this result is the reason not to add 5.5 and 5.6.

Files: `core/` the environment with 5.5 and 5.6, `brief.txt`, `mk.sh` (sandboxes /tmp/ol3_<label>),
`probes/low_L1.py` to `low_L3.py`. Graded with the bundle's own checker (`tasks/fuel-transfer-lines/tests/rerun.py`).
