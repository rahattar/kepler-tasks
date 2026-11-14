# Hot piping nozzle loads from a hanger survey: pre-mortem, not built (Nov 14)

A prototype main steam line was built: 71 nodes, 3D beams with B31.1 bend flexibility, weight, thermal growth,
anchor movements, nine variable springs set by the usual rule, a rod, and two guides with gaps. The
deliverable would be the turbine nozzle loads in each state, to a band of 5 per cent of the resultant (about
5 kN and 20 kNm). The evidence would be a survey of 10 targets placed away from the supports, read to 2 mm.
Run with `python3 exp.py`.

| mechanism | survey residual | nozzle load change |
|---|---|---|
| spring hanger locked (travel stop left in), 7 of 9 hangers | 40 to 350 mm | 11 to 260 kNm (0.5 to 13 bands) |
| spring of twice or half its rate | 1 to 26 mm | 1 to 22 kNm (at most about 1 band) |
| cold load set 15 per cent high | 1 to 20 mm | 1 to 19 kNm (at most about 1 band) |
| rod settled 10 mm | 13 mm | 55 kNm (2.7 bands) |
| guide lug shifted so it never engages | 45 mm | 245 kNm (12 bands) |
| springs on the riser next to the anchor, any change | 0 | 0 (the riser's axial stiffness takes it) |

- **The mechanisms that move the loads are the ones the survey shows at 20 to 170 times its accuracy.** The
  mechanisms the survey shows weakly move the loads by a band or less. No pair of mechanisms fits the survey
  alike yet moves the loads differently, so there is no confound to identify.
- **A generic route skips identification.** For a locked H3, a least-squares fit of unknown vertical forces
  at the nine hangers to the hot survey (10 targets, 3 components) recovers the nozzle loads to 3 kN and
  6 kNm, inside the band, without naming any mechanism.
- **Ten-minute route:** build the frame (textbook), compare it with the survey, and sweep "lock each hanger"
  and "change each gap". It passes.
- **Rule.** In a linear structure the deliverable and the evidence are both linear in the same support forces,
  so a condition big enough to matter is big in the evidence. Look for a deliverable that is more sensitive to
  the condition than the evidence is: an extrapolation past a nonlinearity, or damage that compounds a small
  error.
