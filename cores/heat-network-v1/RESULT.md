# heat-network bare core v1 (Nov 14): low 1 of 3, and all three found both conditions

v0 (HN-3 stated in full) plus two conditions the records show only against a computation:
- a substation fouled, giving its water back 9 to 14 K above its commissioned return temperature; its heat meter
  over the record's first day passes 18 per cent more water for the same heat than the model with the
  commissioned value gives;
- a pipe throttled, its resistance 10 to 40 times as laid; the pressure survey's logged differences below it are
  about 44 kPa under what the laid resistances give for the survey's flows.
Examples neither, pending both, hidden 5 of 6 one or both. Bands 0.5 K, 2 per cent or 1 kW; limit 15 s against a
reference of 5.3 to 7.5 s. Ladder: records alone 5 of 6 out, survey only 3 out, meters only 3 out; every substation
from its own meter accepted (a second sound route).

| probe | effort | time | hidden | conditions found |
|---|---|---|---|---|
| A | low | 27 min | not accepted: 1 to 7 points out on 5 of 6, up to 5 bands | both; refits too eagerly (a valve capacity as well) |
| B | low | 17 min | accepted, worst 0.24 of the band | both, 44 kPa below P081 and 18 per cent at S045 |
| C | low | 10 min | not accepted: 1 point out on river_side, 2.3 bands | both |

- **Every run recomputed the survey morning and the meter day with its own model**, saw the mismatch and refit.
  That is what the model is for; a record the program's own calculation predicts is a record it checks.
- **The ventilation residual held because it was a conservation law applied to inputs**: the campaign surveys
  were consumed as resistances, and nothing in the method compared them with anything. Here the survey and the
  meters were comparisons waiting to be made, the program's own output against a measurement on file.
