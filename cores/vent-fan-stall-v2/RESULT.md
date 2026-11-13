# vent-fan-stall bare core v2 (Nov 13): low 0 of 3, xhigh 1 of 3

v2 is v1 with one thing taken away. In v1 the survey crew answered for the pending district while the
program was being written, and two of three xhigh probes used that: they ran the program that follows the
records, compared it with what the crew reads in the district now, and were shown the 10 m3/s at a panel entry
and the fan on the other limb (`../vent-fan-stall-v1/RESULT.md`). In v2 the crew answers for the two example
districts only, which have neither condition. The package document says so in one sentence: "Where a program
is written the crew answers for the two districts in `examples`; it has not been to the district in
`pending`." Everything else is v1's small core: the same districts, documents, brief and grader.

What is left to see in the pending district is in its files and nowhere else: the two gate-road quantities
at the ends of one stopping differ by 10 to 13 m3/s in all three campaigns, the allowance is two more than the
airways worked on, and the log's last bulkhead closure brings the district to the stall point.

## Probes (opus, sandboxes from tools/mkprobe.sh, graded with ../vent-fan-stall-v1/grade.py)

| probe | effort | time | tool calls | examples | pending | hidden | order |
|---|---|---|---|---|---|---|---|
| A | low | 4.6 min | 13 | accepted | 493 of 560 out | 3 of 4 out | the altered airways |
| B | low | 5.2 min | 12 | accepted | 493 out | 3 of 4 out | the altered airways |
| C | low | 4.3 min | 15 | accepted | 493 out | 3 of 4 out | the altered airways |
| G | xhigh | 28 min | 82 | accepted | 493 out | 3 of 4 out | the altered airways, and DS with a spare place as a check |
| H | xhigh | 30 min | 65 | accepted | accepted | 4 of 4 accepted | altered airways, the stopping the campaigns do not balance at, a fan |
| I | xhigh | 15 min | 47 | accepted | 493 out | 3 of 4 out | the altered airways, and both fans with the spare places as a check |

- Low: all three wrote the program that follows the records, saw that the pending district has two places
  more than it has altered airways, and went no further. The misses are `ladder/legible.py`'s to the point.
- H checked every stopping against the campaigns ("the flow drop along the panel and the pressure across it"),
  found P2-X-02 passing 12 m3/s against 0.77 booked, and used the fan reading to settle which fans are
  stalled at the end of the record. That is the reference's method, reached from the records.
- G and I spent the spare places on a reading of the present state and used it as a check only: both report
  that their end state agrees with the crew in the examples. In the hidden districts the reading disagrees
  with their calculation and nothing in the program acts on it. Neither balanced a campaign at a node.
- 1 of 3 at xhigh is inside the band (0 to 5 of 8 is met 98 per cent of the time at that rate).

## What v2 adds to the lessons

- A place where a wrong program can ask how the district is now is a results table by another name. With the
  crew answering for the pending district, the conditions were found by comparison; without it, by one probe
  in three, from the conservation of air at a node.
- B and C report that the examples still pass with no order placed (worst point at 0.71 of the band). The
  legible need has to cost something in the examples or it is decoration; fixed in the bundle's districts.
