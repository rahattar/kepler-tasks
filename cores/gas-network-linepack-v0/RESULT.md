# gas-network-linepack v0 (Nov 14)

The redesign of `cores/gas-network-premortem/RESULT.md`, on the ventilation recipe: a timed program on shifted
hidden data, two independent conditions that show only as a residual of records the program reads anyway, an
in-run order with an allowance above the work log.

## The task

A gas company's intermediate-pressure networks (2 to 7 bar gauge) are checked before winter to GD-3
(`core/data/docs/gd3_design_day.md`): the lowest pressure at every district governor over the design day.
`designday.py PACKAGE_DIR OUT_CSV`, within 0.02 bar of the result at every governor, 10 s CPU a run, one order
with the field team (`gdsurvey`) a run.

What the program must do, all of it stated:
- each main's K from its latest survey (`p_from^2 - p_to^2 = K Q|Q|^0.82`), and for mains renewed, relined or
  laid since their latest survey a survey from the field team (the allowance covers them);
- linepack at the nodes, implicit steps of 0.1 h, a periodic design day from 06:00;
- PRS at set point between nothing and capacity: on the design day every network's PRSs run at capacity for
  hours, so there is no steady state at the peak and the transient carries the result;
- governors' demand from the package, customers' from the weekday hourly means of their meter record.

What is not stated (public evidence only, the documents never say a record can be wrong):
- **a boundary valve booked closed that passes gas**: at its node (a junction) the campaigns' mains do not
  balance, by 3.6 to 100 times the bound the stated accuracies put on the misclosure; GD-3 section 6 takes a
  passing valve as a main whose K comes from a survey across it, which the field team makes;
- **a customer meter registering 80 to 86 per cent**: at the customer's node the campaigns' mains bring in more
  than the meter registers in the same hour of `customer_meters.csv`, 7 to 10 times the bound; the field team
  proves the meter.

The allowance is the number of mains worked on since their latest survey, plus one for each condition. The
examples have neither condition; the pending package both; the field team answers for the examples only.

| network | where | nodes | worked on | allowance | passing valve (flow now, m3/h) | low meter |
|---|---|---|---|---|---|---|
| kestrel | examples | 240 | 5 | 5 | | |
| heron | examples | 265 | 6 | 6 | | |
| plover | pending | 233 | 5 | 7 | in, about 1200 | 82 % |
| curlew | hidden | 414 | 8 | 10 | in, 1422 | 80 % |
| dunlin | hidden | 312 | 6 | 7 | | 86 % |
| merlin | hidden | 368 | 6 | 7 | out, 1381 | |
| osprey | hidden | 337 | 9 | 9 | | |
| siskin | hidden | 445 | 7 | 9 | out, 1438 | 84 % |
| teal | hidden | 324 | 6 | 7 | in, 745 | |

Shift: hidden networks are 1.2 to 1.9 times the examples' size, three of six have three PRSs (examples two),
with staggered set points, more mains worked on, one with customers shut at weekends.

## Checks before probing (first hidden set)

| program | examples | six hidden | CPU a run |
|---|---|---|---|
| `ref_design.py` (order: worked on + suspects from the balances) | accepted | accepted | 2.9 to 3.9 s |
| `stale_design.py` (no order) | out, worst 0.033 and 0.046 bar | 6 of 6 out | |
| `worked_on_design.py` | accepted | 5 of 6 out, worst 0.12 to 1.74 bar | |
| `valve_only_design.py` | accepted | 3 of 6 out (the meters) | |
| `meter_only_design.py` | accepted | 4 of 6 out (the valves) | |
| `balance_design.py` (valve and meter quantified from the campaigns, not ordered) | accepted | merlin out, 0.028 | |
| `dense_design.py` (the reference with dense algebra) | accepted, 2.7 to 3.3 s | curlew 12.3 s, siskin 15.0 s over the limit | 5.3 to 15.0 s |
| one day from a steady state, not periodic | accepted | accepted | 1.4 to 2.0 s |
| PRS allowed to take gas back | accepted | accepted | |

- At sound nodes the misclosure reaches 0.71 to 0.90 of its bound, and up to 680 m3/h in absolute terms at the
  big junctions; the low meters miss by 444 to 603 m3/h. A check by absolute size would not single them out;
  by the stated accuracy it does.
- A capacity-limited network turns every m3/h of demand into lost linepack: 100 m3/h moves every governor's
  minimum by about 0.03 bar, which is why the conditions put whole networks out and why quantifying the valve
  from the campaigns (1 per cent flows on a large node) misses by 1.4 times the band at merlin.
- Periodicity and the PRS's one-way delivery are stated but decide nothing here: the networks recover overnight.
- The limit is 2.6 times the reference's largest run; dense linear algebra, about 3 s on an example, is over it
  on the two largest hidden networks.
- After the first low probes started, the passing valve and the low meter were found to be the first valve and
  the first customer in every package; both are now drawn at random and the pending and hidden networks were
  regenerated (the examples, which have neither, are unchanged). On the regenerated set every variant keeps its
  verdict except `balance_design`, now accepted (merlin's passing valve is on a small node), and all six probe
  programs keep theirs: low 5 of 6 out each, xhigh accepted.

## Low effort: 0 of 3 (first hidden set)

Three probes on `model: "opus"`, effort low, brief `brief.txt`, 10 s limit.

| probe | time | tool calls | examples | six hidden | order |
|---|---|---|---|---|---|
| A | 8.3 min | 27 | accepted | 5 of 6 out | the mains worked on, then meters by largest flow |
| B | 2.3 min | 8 | accepted | 5 of 6 out | the same |
| C | 9.4 min | 26 | accepted | 5 of 6 out | the same |

- **All three wrote the stated method correctly** (examples exact to 4 decimals, 1.5 to 5.0 s on the hidden
  networks) and **none balanced a campaign**. Each read the spare places as room to prove meters, largest flow
  first, and each would have ordered a boundary valve only if the register had it open.
- The spare places proved the low meter at curlew and siskin by its size, but those networks also have a
  passing valve; at dunlin the low meter is not the largest and the proving went to another. Only osprey, with
  neither condition, passed.
- A and C tested a run without the field team (0.023 bar out on kestrel); C timed a 505-node network built from
  the two examples at 2.4 s. The limit does not bind on a sparse program.

## xhigh: 3 of 3 (regenerated pending, graded on the first hidden set)

Three probes on `model: "opus"`, effort xhigh, sandboxes built after the pending package was regenerated (its
passing valve now BV-2, missing its node's balance by about 1,150 m3/h against a bound of 12; its low meter
MT-5200 at 82 per cent).

| probe | time | tool calls | examples | six hidden | CPU a run | order |
|---|---|---|---|---|---|---|
| A | 30 min | 89 | exact | accepted, worst 0.000 | 1.0 to 1.7 s | worked-on mains, then the valves and meters the balances flag |
| B | 26 min | 67 | exact | accepted, worst 0.000 | 1.5 to 2.0 s | the same |
| C | 28 min | 66 | exact | accepted, worst 0.000 | 1.2 to 1.8 s | flagged valves and meters first, then the mains |

- **Every xhigh run balanced the campaigns at the valve and customer nodes, unprompted, and named both of
  plover's conditions** with their sizes (BV-2 passing 1,150 to 1,190 m3/h, MT-5200 registering about 81 per
  cent). Each ordered the flagged items and applied the readings as GD-3 says; each also kept an estimate from
  the campaigns as a fallback.
- **Two conditions with one signature are one trap.** Both show as a node misclosure in the same campaigns,
  and the check that finds one finds the other: the outcome is binary (low: neither, xhigh: both). The review
  of Nov 13 warned of single traps; this is the same failure with two names. Ventilation held because its
  second condition was of another kind (a fan state the records leave open), not a second residual.
- **A misclosure of 4 to 100 times a stated bound is a contradiction, not a judgement.** Once computed it
  needs no interpretation: the bound comes from the accuracies the package states. The only thing between a
  run and the answer is deciding to compute it, which xhigh always does here.
- **The limit did not bind.** The probes' programs ran in 1.0 to 2.0 s (xhigh) and 1.5 to 5.0 s (low) against
  10 s; my reference (2.9 to 3.9 s) was the slowest program in the room. Two built 500-node packages to check.
- Judgement calls the runs made and stated: a meter proved within 1 per cent is left as registered (all three
  xhigh, inferred from the examples); a survey on the day of the work is not "after" it (A, B).

## Verdict

Not a candidate as it stands: low 0 of 3 meets the easiness bar, xhigh 3 of 3 is above the 0 to 5 of 8 band.
What would be needed is a second condition that the balance check does not settle: one that shares the
misclosure but has another cause and consequence, so that the first explanation fits and is wrong (the hoist
rope v1 pattern), or one whose evidence only a transient calculation shows. Neither is designed here.
