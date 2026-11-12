# shaft-alignment bare core, v0: solved 3 of 3 in 80 seconds (Nov 11)

A kind-A core (docs/trap-analysis-2026-11-11.md, section 5) built bare: generator, rig, grader, a reference
route and a fallback study. No evidence set, no second solution, no bundle. `mk.sh <n>` builds a sandbox.

**The task.** 36 coupled trains, reverse-indicator dial sheets, moves at the driver's feet so the shafts are in
line running; a train passes when both hub planes are within 0.05 mm. Five laser visits, charged on order.

**What a pass needs.** Nine things the records cannot settle (bar sets B2, B3, C1, C2, C3 without a valid sag
card; a re-rated gear set on four gearboxes; three turbines whose hot checks were ended by pipework), and five
visits. The only passing bookings are the three turbines (two of which were read with B3 and C3), the one
re-geared train that was read with B2, and one of four C1 pumps; C2 has to be worked out from a train read
twice. 4 of 376,992 bookings pass. Three critical compressors with vibration complaints are settled by the
records and are there to draw a visit.

**Checks before probing.** The reference route gets 36 of 36 from the agent's files, worst residual 0.006 mm
against 0.05. Every natural fallback for an uncovered class fails every train in it (study.py). Six wrong
bookings leave 2 to 13 trains out.

**Probes.** Three, `model: "opus"`, effort low, the brief in brief.txt.

| probe | booking | trains | time | tool calls |
|---|---|---|---|---|
| 1 | TP-301A, TP-301B, TP-301C, GF-401, P-102A | 36 of 36 | 79 s | 5 |
| 2 | the same | 36 of 36 | 83 s | 7 |
| 3 | the same | 36 of 36 | 79 s | 6 |

Each report names all nine open items, the two sag sets that come free with the turbine visits, GF-401 as the
one train that settles both the gear set and B2, and the twice-read train for C2. None spent a visit on a
compressor.

**Why, against the list in section 6.2.** Five of the six conditions were met: many units, a budget with no
slack (tighter than a count, since it needed the overlaps), per-unit quantities no sibling predicts, salient
duplicates, wide fallbacks, charged before the result. The one that was not: "classes the solver must infer".
Here the procedure states them, because fairness seemed to need it: sag belongs to the bar set, a card dies
with an altered set, gearboxes of one model move alike, a turbine's figure is its own, work on supports ends a
hot check. Given those sentences the open items are a list and the booking is a small set cover, and the model
does both in one pass. Overlaps and a free derivation do not make an allocation hard; they make it a slightly
longer count.

So the hvac result is not reproduced by a zero-slack budget alone. What hvac had and this does not is that no
document said which rooms were open or that classes existed at all; the solver had to suspect it.
