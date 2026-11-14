# quench-oil v1 (Nov 14): two conditions, laboratory silent on the pending package. Low 1 of 3, xhigh 3 of 3.

Built on Alex's go after quench-oil-survey 20261113b went 3 of 3 at the official easiness probe. Not
submitted. `bundle/` holds the changed documents, generator, reference, second solution and studies;
`probes/` the six probe programs. The bundle folder in `tasks/` was put back to 20261113b.

What changed from v0:
- **A second condition.** At five of six hidden sites one kept system's charge is changing (water getting
  in): its cooling rates climb 3.8 to 5.3 per cent a round on file, where the package format says ageing is
  under 0.5 per cent a round. HT-5 section 5 now states that a kept charge runs linear in time from its latest
  analysis to an analysis on the date the laboratory draws its samples, so the changing one needs a sample
  the oil log gives no reason to take. Allowance one or two above the log's count.
- **Mixed hidden sites:** four with both conditions, one with only the divided system, one with only the
  changing charge; every changing site has a second kept system.
- **The agent's laboratory answers for the two examples only**, as the package format says.

Probes on `model: "opus"`, graded by the bundle's checker at the 50 s limit:

| run | time | result | what decided it |
|---|---|---|---|
| low 1 | 19 min | 5 of 6 sites out | found both; took the divided system's second reservoir as never renewed |
| low 2 | 8 min | 2 of 6 out, by 1.02 and 1.46 bands | found both; solver not converged on the cooling rate through 700 C |
| low 3 | 14 min | accepted, largest 1.00 of a band | found both; checked the second reservoir's new figure against its old trend |
| xhigh 4 | 72 min | accepted, 0.61 | found both, synthetic test bench, 64 random sites |
| xhigh 5 | 54 min | accepted, 0.29 | found both |
| xhigh 6 | 41 min | accepted, 0.19 | found both |

- **Every run found both conditions on the pending package**, low runs within 8 to 19 minutes. A condition
  that shows as a direct comparison of numbers in one file (tanks against each other, rounds against each
  other) against an accuracy the documents state is found at any effort. Ventilation and fuel-transfer-lines
  held because their conditions show only as a residual of a physical model.
- **A silent laboratory did not slow anyone.** Every run reasoned from the analyses on file alone.
- **What failed the low runs was a reading and a resolution**, not the conditions: whether the renewal reached
  the second reservoir (a sample answers it; one run asked and one did not), and cr700's sensitivity (about
  3 per cent per K of T_CRmax and up to 2.3 per cent per per cent of cooling rate for small bars).
- **An unsampled ageing charge must not move its T_CRmax by a degree**, or cr700 for small bars leaves the band
  (xhigh 6 and 4 both found the sensitivity). The shipped data held it; no design rule checked it.
