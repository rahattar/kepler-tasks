# heat-network bare core v2 (Nov 14): low 2 of 3, and all three found both conditions

v1 with its conditions moved into the campaigns that give the resistances (the ventilation kind v1 said holds):
- pipe resistances only from three hydraulic campaigns (every pipe's flow and drop, every substation's metered
  flow, the plant's flow and pressure difference), by the largest-drop rule;
- a substation registered at the wrong node: an equal-and-opposite pair in the campaign node balance, the size of
  its metered flow;
- a substation bypass leaking open: one unpaired node surplus of 1.5 to 3 kg/s; R_b from dp_node / m_b^2.
Examples neither, pending both, hidden 5 of 6 one or both. Bands 0.5 K, 2 per cent or 1 kW; limit 15 s against a
reference of 3.6 to 6.0 s. Points whose answer moves by more than 0.4 of the band under other campaign noise are
dropped (0 to 4 per network); reference worst 0.38 of the band. Ladder: records alone 5 of 6 out (9 to 69 bands),
moved only 3 out, bypass only 3 out.

| probe | effort | time | hidden | conditions found |
|---|---|---|---|---|
| A | low | 5 min | accepted, worst 0.38 of the band, 6.2 to 8.8 s | both, S122 at T12_132 and S080 at about 1.2e4 |
| B | low | 6 min | not accepted: west_hill 17.1 s; every network in band | both |
| C | low | 9 min | accepted, worst 0.40 of the band, 7.8 to 11.0 s | both |

- **A node balance of logged flows is a direct comparison when the package lists every term.** Every run summed
  the campaign flows at each node before writing the solver, in the first minutes. The documents named both
  mechanisms (a bypass law in the scope, a `bypass_resistance` column "closed, as fitted", the register's node),
  and the pending network carried both.
- **One check found both conditions**, as gas-network-linepack v0 says: two residuals of one balance are one.
- The only miss was speed (B, 16 to 18 s on two networks); the limit sorts solvers, not readings.
- Build fixes worth keeping: a line search that asks for a real decrease (a pipe near no flow sends full Newton
  steps back and forth), best-fit matching of moved substations, and the noise screen on points.
