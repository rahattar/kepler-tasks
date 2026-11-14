# quench-oil v2 (Nov 14): the evidence moved into test bars. Low 3 of 3. xhigh stopped.

v1 with the divided system dropped and the two conditions shown only through the physics: each tank has a
monthly test bar (centre thermocouple, measured t85 good to 1 per cent) at three diameters and that day's
bath and furnace temperature, so raw times cannot be compared and each bar has to be run through HT-5.

- **A stopped agitator.** The register records a propeller (HT-5 section 4: factor 1.35 running, 1.0 still);
  at five hidden sites one own-oil tank's propeller has not run. Its bars come out 39 per cent slower than
  HT-5 with the register's agitation and fit still oil. No analysis is needed; the register is overridden.
- **A changing charge** whose analyses on file look normal (ageing 0.1 per cent a round); only its bars drift,
  month by month, against the oil on file. It needs an analysis the oil log gives no reason to order.
- Hidden: three sites with both, two with the agitator only, one with the changing charge only; the pending
  package has both; the agent's laboratory answers for the examples only.

Reference accepted on the six sites (largest error 0.38 of a band, 16 to 22 s a site, limit 50 s).

| run | time | result |
|---|---|---|
| low 1 | 13 min | accepted, largest 0.40 of a band |
| low 2 | 17 min | accepted, 0.56 |
| low 3 | 19 min | accepted, 0.40 |
| xhigh 4 to 6 | | stopped once the low result decided the round |

- **Every low run fitted its model to every tank's test bars**, because test bars are the only measured results
  in a package that has none for the loads. Two of the three tried both agitation factors on every tank as a
  matter of course; all three fitted a drift per charge. The physics turned the evidence into a residual per
  tank, and a residual per tank is read as readily as a number in a column.
- **Ventilation and fuel-transfer-lines hold for a different reason**: their residual exists only after a
  coupled solve (a network balance, a pair's division), and acting on it means changing a quantity the
  register states in a way the solve does not suggest on its own. A per-item check against measurements, done
  item by item, is found at any effort.
- Files: `bundle/` (documents, generator, reference, second solution, checker, studies), `probes/` (the three
  low programs). `tasks/quench-oil-survey` is back at the submitted 20261113b.
