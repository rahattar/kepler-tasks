# twin-oil-lines bare core v0 (Nov 13): low 3 of 3 solved, in 7 to 13 minutes

A timed program on shifted hidden data. `lines.py` reads a site's package (oils, lines, hourly records of flow,
inlet temperature and surroundings temperature) and writes the pressure drop and the outlet temperature of
every record, to a terminal standard TS-2 that gives the model of one pipe in full (bulk heat balance, a local
film for developing laminar flow with a wall-viscosity correction, corrected laminar friction, ASTM D341
viscosity) and says of a pair of like pipes between common manifolds only that the oil divides between them and
both have the pressure drop between the manifolds. 60 s of CPU a run; pressure drop within 1.5 per cent, outlet
temperature within 0.5 K.

**What was meant to carry it.** A wrong answer that passes the solver's own checks. With a viscous oil cooling
along the pipe, the pressure drop of one pipe is not monotonic in its flow, so a pair can satisfy every balance
in more than one way. The even division is always a solution and is exact on both examples with results (warm
season: it is the only stable one at every record). At cold sites on low throughput it is unstable: one pipe
stalls and cools while the other carries nearly all the flow (86 to 99 per cent at the pending site, by
the probes' own count), and once stalled the pair stays so
after the flow is raised again, until the uneven division ceases to exist. Nothing in the standard names
stability or history. The condition is in the visible data once, in the package without results (west_jetty,
736 of 2378 records stalled).

| what was run | examples | hidden sites | cpu a run |
|---|---|---|---|
| reference (`ref_lines.py`: every steady division, its stability, each pair followed hour by hour) | accepted | accepted, worst 0.01 of a band | 15 to 34 s |
| even-division program (`sym_lines.py`) | accepted, worst 0.01 of a band | 5 of 6 fail: every stalled record, 698 to 1003 a site; outlet temperature 1.8 to 18.4 K low, pressure drop -29 to +32 per cent, none of the 4373 inside both bands | 0.5 s |
| low L1 (opus), 13.5 min | within 0.005 per cent, 0.005 K | **accepted**, worst 0.00 | 6 to 14 s |
| low L2 (opus), 12 min | the same | **accepted**, worst 0.00 | 3 to 10 s |
| low L3 (opus), 7 min, 10 tool calls | the same | **accepted**, worst 0.01 | 4 to 11 s |

No xhigh probe was run: the screen allows no low-effort solve.

**Why it fell.** Each probe wrote the pair as the equation it is, dp(a) = dp(M - a), and looked at all its
roots on the pending package. From there each supplied, unprompted and in its own words, the three rules the
standard leaves out:
- an unstable division is discarded (L2: "a small shift in flow would grow");
- between two stable divisions the pair keeps the one it had the hour before, read off the format document's
  sentence that a line's records are an unbroken hourly run in service (L1 cites it);
- a survey starts on the even division where that is stable.
All three flagged these as their own reading, untested by the examples, and all three were right.

- **An equation that the standard states is a signpost to all of its solutions.** The even division was never
  taken on symmetry; the split was solved.
- **Physics the standard leaves out is supplied when it follows from the physics.** Stability and persistence
  were inferred three times in three. A rule is only hidden from this solver if it is arbitrary.
- **The pending package was again the place each probe looked first** for what the examples do not show.
- **The time limit decided nothing**: the probes' programs run in a third of the reference's time.

**Checks on the core.** The states do not hang on the model's last per cent: the generator keeps a line's
history only if the same sequence of even and uneven states comes out with the flow 4 per cent down and up and
with every hourly step walked in six parts, and at warm sites only if nothing but the even division is steady
and stable at any record. No record has two stable uneven divisions. The first record of every pair has one
stable state.

## Files
- `line.py` one pipe; `pair.py` every division of a pair, stability, following; `gen.py` the nine sites;
  `sites.txt` their record and stalled-record counts; `core/` the agent's data and the hidden sites with truth
- `ref_lines.py`, `sym_lines.py` single-file programs; `grade.py` (60 s of CPU a run)
- `brief.txt`, `mk.sh` probe brief and sandbox builder (through tools/mkprobe.sh)
- `L1.log`, `L2.log`, `L3.log` the graded runs; `probes/` the three programs as delivered
