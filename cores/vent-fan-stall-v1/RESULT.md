# vent-fan-stall bare core v1 (Nov 13): low 0 of 3, every failure the designed miss

v1 keeps v0's district (two axial fans in parallel, a stall dip, the log deciding which of two states holds) and
puts stall in the examples with results, where it is physics everybody finds. What decides a hidden district
is now two things the records do not say and a program has to spend a survey on, in one order placed before
any result is known. Built at a tenth of v0's size (121 to 165 branches, 79 to 98 log rows, 560 or 686
points), because v0 showed that size decides the timing and not who sees the condition.

## The core

- Airway resistances are not given. They come from pressure-quantity surveys on file, three campaigns of every
  airway, R = dp / (q |q|), each reading within 0.3 per cent. An airway re-supported or enlarged since its
  latest survey has none on file. Stoppings are not surveyed: the register carries what each was built to.
- The program places one order with the survey crew while it runs, `pqsurvey PACKAGE_DIR BRANCH ...`, of at
  most `survey_allowance` branches, surveyed in the district as it stands after the log's last entry.
- Legible need: the three or four airways worked on since the last campaign. In both examples the allowance
  is exactly that number.
- **Breach** (pending, 2 of 4 hidden): one stopping booked at 1 900 to 3 400 N s2/m8 is in fact at 7.7 to 7.9
  and passes 10 to 13 m3/s. No file says so. In every campaign the quantities of the two gate roads at its
  intake end differ by that much (10.08, 10.04, 9.87 at deep_south) where a stopping as built leaks half a
  m3/s and the readings are good to 0.3 m3/s. Allowance: one more.
- **Open outcome** (pending, 2 of 4 hidden): the record's last bulkhead closure takes the district to the stall
  point within what the surveys can resolve. The return's first entry is built between the value at which the
  healthy state ceases for the district as it is and for the district as its records have it (0.55 to 0.77 per
  cent apart), so the two go opposite ways and every round after it differs. A survey of a fan branch reads
  which limb the fan is on now. Allowance: one more.
- The fourth hidden district has neither and its allowance is the legible count.
- VS-4 and the package format state the physical thing (a resistance is the pressure difference over the
  square of the air passing) and what is on record (surveys of airways, the resistance a stopping was built
  to, the accuracy of a reading). Nothing says a record can be wrong or what the allowance is for.

## What was measured (grade.py, the program run with the crew answering from sealed books)

| program | examples | pending west_reef | deep_south (both) | old_shaft (breach) | far_east (open) | new_incline |
|---|---|---|---|---|---|---|
| reference: altered airways, the breached stopping, a fan with what is left | 0 out, 0.21 of the band | 0 out, 0.28 | 0 out, 0.26 | 0 out, 0.18 | 0 out, 0.23 | 0 out, 0.18 |
| `ladder/derive.py`: the breach's resistance worked out from the campaigns, not surveyed | 0 out | 0 out | 0 out | 0 out | 0 out | 0 out |
| `ladder/legible.py`: altered airways only | 0 out | 493 of 560 | 576 of 686 | 468 of 560 | 160 of 560 | 0 out |
| `ladder/stopping.py`: no fan read | 0 out | 160 | 196 | 0 out | 160 | 0 out |
| `ladder/fan.py`: stoppings as booked | 0 out | 493 | 576 | 468 | 0 out | 0 out |

A missed breach puts every round of the district out, by up to 33 times the band; a missed open outcome the
four rounds after the closure, by up to 36 times. The survey of the breached stopping is not needed to pass:
its resistance follows from the campaigns to well inside the band.

## Probes (opus, sandboxes from tools/mkprobe.sh with the crew's command)

| probe | effort | time | tool calls | examples | hidden | order on west_reef |
|---|---|---|---|---|---|---|
| A | low | 2.6 min | 8 | accepted | 3 of 4 out: 584, 468, 160 points | the 3 altered airways, 2 unused |
| B | low | 10.7 min | 27 | accepted | 3 of 4 out: 576, 468, 160 | the same |
| C | low | 2.6 min | 10 | accepted | 3 of 4 out: 576, 468, 160 | the same |

- All three found stall and its history from the examples' results, in their first or second program, and
  carried the state through the log. That part is now feedback and costs minutes.
- All three ordered exactly the altered airways. C: west_reef "needed 3 of its 5 allowed survey branches".
  None balanced a campaign at a node, none asked what the other two were for, none read a fan.
- All three ran the pending package and reported that it runs cleanly.
- Their misses are the `legible` program's, district for district.

## xhigh (opus, the same sandboxes): at least 2 of 3 accepted everywhere, too easy

| probe | time | tool calls | examples | pending | hidden | what the crew's log shows |
|---|---|---|---|---|---|---|
| D | over 65 min, not finished when v2 started | - | accepted (12:30 copy) | out | 3 of 4 out | the altered airways only, as the low probes |
| E | 41 min | 79 | accepted | accepted | 4 of 4 accepted | main intake and the panel entries surveyed on west_reef, then the stopping |
| F | 41 min | 89 | accepted | accepted | 4 of 4 accepted | spare branches spent on the fans first, then P2-X-02 |

- E and F did not start from the campaigns. Both built the legible program, ran it on the pending district
  and compared what it calculates with what the crew reads there now. The crew answers for the pending
  district in the sandbox, so a program that is wrong about it can see that it is wrong, and where: the
  panel-entry quantity off by 10 m3/s, a fan on the other limb. From there the node balance and the fan
  reading are an hour's work.
- So the pending district was not a place where the conditions merely show. It was a place where a wrong
  program is told so, the same fault as v0's examples with results, one step removed.
- v2 takes that away: where the program is written the crew answers only for the two example districts, which
  have neither condition. The pending district's campaigns still carry the imbalance and its log still ends
  at the close call; nothing answers back.
