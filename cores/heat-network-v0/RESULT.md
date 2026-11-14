# heat-network bare core v0 (Nov 14): low 3 of 3, dead at the gate

District heating to a standard stated in full (HN-3): mirrored supply and return networks with loops, valve
limits at the substations (m = min(Q / c dT, K sqrt(dp))), plug flow with heat loss by residence time, complete
mixing at nodes, a 120 s step in a stated order. Nothing decides a case but doing that correctly and fast:
examples 62 and 91 pipes over 48 h, pending 312 pipes over 72 h, six hidden of 553 to 970 pipes over 96 h,
colder, with more valves at their limit and more reversing pipes. Limit 12 s of CPU against a reference of
3.6 to 4.7 s (`ref_heat.py`) and a plain one-deque-a-pipe simulator of 17 to 28 s (`truth.py`, which makes the
sealed results).

| probe | effort | time | hidden | slowest run | what it wrote |
|---|---|---|---|---|---|
| A | low | 7 min | accepted, worst 0.0005 of the band | 6.1 s | numpy parcel arrays for every pipe at once, Newton from the last step; built a 936-pipe test package |
| B | low | 10 min | accepted | 5.0 s | active-set valve loop, parcels at either end; built a 936-pipe test package |
| C | low | 16 min | accepted (final program too) | 4.6 s | trees eliminated exactly, only the looped core to the solver; built a 936-pipe test, and one with 60 extra loops (8.5 s) |

- **A stated numerical scheme is implemented first time.** All three read HN-3, wrote the parcels with the heat
  loss kept exact, the mirrored pressures, the valve limit and the step order, and matched both examples to
  1e-6 at the first or second attempt.
- **Vectorised numpy is the low-effort default.** The limit was set against a plain per-pipe loop; none of the
  three wrote one. Each first program ran the largest hidden district in 4.6 to 6.1 s, at the reference's speed.
- **Two of three built a package at the stated maximum on their own**, by joining copies of the pending one at
  the plant, and timed it. The package document's limits were read as a test plan.
- So the review's point holds here too: a limit binds only against a method a competent first program does not
  reach. A constant factor (vectorising) is not such a method.
