# Design note: fuel-transfer-lines (Nov 13)

A timed program on shifted hidden data, to the Nov 11 ask. Built from bare cores v0 to v2
(`docs/difficulty-calibration.md`, the twin oil lines sections; `cores/twin-oil-lines-v0`, `-v1`, `-v2`). The
bundle's data is byte for byte core v2's; what the bundle adds is TS-2 4.2 and 4.3, the checker and the evidence.

**Subject.** A fuel terminal's heated heavy-oil transfer lines: 30 lines a site, 20 of them pairs of pipes
between common manifolds and 10 single pipes, 50 pipes, 1240 to 1285 hourly records. Standard TS-2 gives the
pipe (heat balance, Graetz-type film with wall-viscosity correction, laminar friction with its own, ASTM D341),
the pair (one pressure drop, and how the division carries from record to record) and where each quantity comes
from (register, heat-loss surveys).

**Mechanism.** The ventilation district's, on another physics: a record wrong with no physical reason to doubt
it, curable only by a survey the program orders before it sees any result.

- The pair's collapse and its history are in the examples with results and are now stated in TS-2 4.2 and 4.3
  (after the ventilation-district-airflow quality rejection). v0 showed low effort finds them anyway.
- Outside coefficients come from three heat-loss campaigns on file. Pipes whose covering was renewed or
  repaired after the last campaign have to be ordered: one order a run, at most `survey_allowance` pipes. That
  is the legible need, and it bites in the examples.
- **Narrowed pipe** (pending, 3 of 6 hidden). One pipe of a pair has lost 11.2 to 12.3 per cent of its bore
  today. The register gives the bore as laid; TS-2 5.1 says pipes are not gauged in service. The pair's
  surveyed division does not fit one pressure drop with the bores as laid: 0.142 to 0.185 apart in ln in every
  campaign, against 0.010 at the worst of 176 sound pairs. Two steps cure it: survey the pipe, and solve its
  bore from the new reading's division. Allowance: one more.
- **Failing covering** (pending, 4 of 6 hidden). A coefficient that rises 0.163 to 0.210 in ln between the
  last two campaigns with no work logged, against 0.022 at the worst of 427 pipes. Allowance: one more.

**What must not be changed without re-probing.**
- TS-2 5.1 says what the register records ("the bore and the length each pipe was laid with. Pipes are not
  gauged in service."). The v1 wording, that a pipe's bore "is" the register's, turned two correct findings at
  xhigh into misses.
- D in TS-2 section 3 is "the bore", not "the bore open to the oil". One v2 xhigh run saw the deposit and kept
  the register's bore. The physical definition is the ready fix if a reviewer reads that as unclear, and it
  would likely raise the xhigh rate.
- The crew answers for the two examples only; the pending package has no results.
- The examples' allowance equals the covering jobs. A spare place in an example is a visible test.
- Nothing says a record can be wrong or what a spare place is for.
- The two conditions stay unstated: they are physical, and public evidence identifies them (the corrected design
  gate, Nov 13). Stated as TS-2 5.5 and 5.6 (core v3), low effort solved the task 2 of 3. What no evidence
  settles, the pair's carry-over and its opening, is stated in 4.2 and 4.3 and must stay so.

**What the generator has to hold to** (`authoring/provenance/sites.py`).
- Every line laminar in every pipe at its survey rating, at the crew's reading today and at every record
  (largest Re 1550). v1 had 30 survey runs over Re 2000; lines are drawn again until they are in scope.
- A pair's division at every record the same with the flows 4 per cent either way and with each hour in six
  steps; every pair's first record with one division.
- Readings fine enough that a correct program is inside the band: flows to 0.05 per cent, oil temperatures to
  0.004 K before rounding. At v1's coarser readings the reference was at 0.62 of the band on a sound line.
- Checksums by hashlib.

**The band.** Pressure drop 2.5 per cent, outlet temperature 0.5 K. The core used 1.5 per cent; the bundle's
evidence showed both independent solutions at about 1 per cent on canal_basin's narrowed line (FL-216), where the
bore is solved from one reading and dp goes as D^-4. At 1.5 per cent that is 0.66 of the band, under the
playbook's factor of two; at 2.5 per cent it is 0.40. Every wrong route was out by 8 to 26 bands at 1.5 per
cent and stays out.

**The timed half.** 40 s a run on one CPU; the reference 11.6 to 14.8 s of CPU. The second solution as first
written (scipy solve_ivp and brentq, one case at a time) takes 100 s for a small site of 250 records and is
stopped at the limit; made fast it runs a site in 15.8 to 17.9 s. The limit does not separate probes: their
programs run a site in 2.6 to 14.6 s.

**Verifier.** The program runs as nobody (subprocess user=, group=, extra_groups=[]). The crew is a desk
directory the checker serves between looks at the clock: the verifier's `heatsurvey` leaves the order under
`/run/heat-desk/asks` and reads the answer from `answers`, so there is no socket and no thread. CPU time is the
larger of /proc read every 0.05 s and the kernel's wait4 count, over the program and every process it starts.
No CPU affinity.

**Local rates** (`model: "opus"`).

| | low | xhigh |
|---|---|---|
| core v1, TS-2 5.1 prescriptive | 0 of 3 | 0 of 3 |
| core v2, 5.1 descriptive | 0 of 3 | 1 of 3 |
| the bundle | 0 of 3 (10 min each) | 1 of 3 |

The bundle's xhigh probes (programs in `cores/twin-oil-lines-v2/probes/bundle_*.py`): BX2 accepted on all six
and on the three visible sites, largest error 0.28 of the band (65 min; it solved FL-212-A's bore as 62.5,
61.0 and 59.6 mm at the three campaigns and fitted each pair's two coefficients together with the surveyed
division). BX1 (39 min) and BX3 (76 min) ordered both conditioned pipes, read the narrowed one as a drifting
covering, re-derived its coefficient with the register's bore, and are out on the narrowed line at the three
sites that have one, by 15 to 28 bands. BX2 wrote that it took TS-2's bore to be the bore in service because
5.1 says the register holds the bore as laid.

Over the v2 data, core and bundle, xhigh is 2 of 6 and low 0 of 6. Every xhigh run ordered both conditioned
pipes; the four misses are one miss, the step from finding the pipe to changing a quantity the register states.
One low run (BL2) ordered the failing covering and the narrowed pipe as two drifting coverings, the first low
run on this data to look at the campaigns at all.

**The small set and identifiability.** The first small south_wharf had a failing covering in a 125 mm pair of
FO-700 at 3 t/h, where the inside film carries nearly all the resistance: its coefficient today (23.8) moved
the outlet temperature by 0.007 K for a factor of 1.21, and the reference's inversion ran to its bracket (200).
sites.py now draws a site again when any reading moves its outlet temperature by less than 0.15 K for that
factor (SEEN_K); every full site met it at its first draw (least 0.206 K), so their files are unchanged.
