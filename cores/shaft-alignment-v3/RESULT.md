# shaft-alignment bare core, v3: the split inside one pump model. Low 0 of 6, xhigh 0 of 3 (Nov 11)

v2 with one change: every listed class is a single pump model, and the five blanked foot-mounted pumps are all
HSC-400. Two of them ran at 0.38 of the pumped rise in the 2019 survey and three at 0.47; no column separates
them. Reference route 36 of 36. Every probe on `model: "opus"`.

| probe | effort | visits | trains |
|---|---|---|---|
| 1 | low | TP-301A, TP-301B, P-301A, P-320A, P-340A, **K-201A** | 33 of 36 |
| 2 | low | TP-301A, TP-301B, P-301A, P-325B, P-342, **K-201A** | 34 of 36 |
| 3 | low | P-301A, P-320A, P-340A, TP-301A, TP-301B, **P-331** | 33 of 36 |
| 4 | low | P-301A, TP-301A, TP-301B, P-340A, P-325A, **K-201A** | 34 of 36 |
| 5 | low | **K-201A**, TP-301A, TP-301B, P-310A, P-325B, P-342 | 34 of 36 |
| 6 | low | TP-301A, TP-301B, **K-201A**, P-301A, P-320A, P-340A | 33 of 36 |
| 7 | xhigh | TP-301A, TP-301B, P-301A, P-342, P-325B, **K-201A** | fails (visits fixed) |
| 8 | xhigh | TP-301A, TP-301B, P-310B, P-320A, P-342, **K-201B** | 33 of 36 |
| 9 | xhigh | TP-301A, TP-301B, P-301A, P-325A, P-345A, **K-201A** | 34 of 36 |

- Every run found five needs and spent the sixth visit as a spare: eight times on a compressor, once on a pump
  whose baseplate grout was repaired after its sheet was taken. Three low-effort runs bought the spare last,
  after counting, which is the mechanism working as designed.
- Three low-effort runs saw the 0.38 and 0.47 once they were carrying the measured figure across, and wrote it
  up as an unresolved judgement. No xhigh run saw it at all: with one model there was nothing to make a planner
  ask whether the class was uniform, and a changed pump's old fraction has no use on the solver's route.
- So this is too well hidden. v2's two model names were what made the xhigh runs put the question.
- A defect found by an xhigh report and fixed from v4 on: the maker's lateral figure had no stated direction,
  which gave a careful run a legitimate reason to spend a visit on a compressor.
