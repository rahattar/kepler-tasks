# Pre-mortem: gas distribution network with linepack (Nov 14, before any build)

The ventilation recipe (approved at 3 of 8) put on a medium-pressure town gas network: a timed transient
simulation over a month, two physical conditions left unstated but shown by public evidence, an in-run survey
order with an allowance above the work log. `gn.py` (Renouard medium-pressure law, linepack at the nodes,
implicit Euler, Newton each step) on a test town of 96 nodes and 152 mains, two feeds, three large metered
customers, five telemetry points (`test.py`).

| change | effect at the five telemetry points | stated accuracy it would be read against |
|---|---|---|
| feed B's regulator 0.15 bar below its register setting | 99 to 122 mbar lower everywhere; feed A's share 0.54 to 0.64 | 5 mbar |
| a large customer's meter registering 20 per cent low | 6 to 8 mbar lower; 280 m3/h unaccounted, 2.3 per cent of the total | 5 mbar; profiled demand a few per cent |
| transient (linepack) against steady | up to 4.7 mbar | |

## Reading

- **As first sketched, the drift is a routine tell.** Telemetry pressures are what the network model computes;
  every careful program compares them (the header core's lesson), and 100 mbar against 5 is read at once.
  Ventilation's evidence was different in kind: node imbalances in survey campaigns the program uses as inputs
  for another purpose (resistances), never compared with its own output.
- **The meter fault is too weak** against any honest statement of profile accuracy, unless it is much larger or
  a reading sits near it.
- **Linepack moves pressures by a few mbar**: the transient matters only if the band is tighter than that.
- **A design that holds would put the evidence where the program has no reason to compare it**: survey
  campaigns on file used to calibrate the mains, whose inconsistency at a node (an obstruction, a drifted
  regulator recorded in a campaign's outlet reading) shows only to a conservation check; no live telemetry the
  model predicts. Not built.
