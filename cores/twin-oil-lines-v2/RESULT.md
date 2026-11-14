# twin-oil-lines bare core v2 (Nov 13): low 0 of 3, xhigh 1 of 3. At the bar

v1 with its two defects removed: TS-2 5.1 now says what the register records ("the bore and the length each
pipe was laid with. Pipes are not gauged in service") where v1 said the bore "is" the register's, and every
line is drawn so that its survey rating and its records are laminar. Nine sites instead of six, so the six
hidden ones cover every combination. Small: 30 lines, 50 pipes, 1,240 to 1,285 records a site; 60 s of CPU.

## The core (as v1, in short)

- Outside coefficients come from heat-loss surveys on file (three campaigns of every pipe), inverted through
  TS-2 section 3. One order a run, `heatsurvey PACKAGE_DIR PIPE ...`, of at most `survey_allowance` pipes.
- Legible need: 3 or 4 pipes a site whose covering was renewed or repaired after the last campaign. The
  examples' allowance is exactly that, and a run with no order is out on those lines.
- **Narrowing pipe**: one pipe of a pair has lost bore to deposit, 3.5 to 4.5, 5.5 to 6.5, 7.5 to 8.5 per cent
  at the three campaigns and 11 to 12.5 per cent now. No file says so. With the bores as laid the two pipes'
  pressure drops at their surveyed flows disagree in every campaign. Allowance: one more.
- **Declining covering**: a coefficient that rises campaign by campaign with no work logged and stands 45 to
  70 per cent above its last survey now. Allowance: one more.
- west_jetty (pending, no results, crew not answering) has both. Hidden: south_wharf and canal_basin both;
  upper_yard narrowing; kiln_road and tank_row declining; boiler_lane neither.

## What was measured (grade.py, the crew answering from sealed books)

Records out of band, of about 1,250 a site; every record of a missed line is out.

| program | examples | west_jetty | south_wharf | canal_basin | upper_yard | kiln_road | tank_row | boiler_lane |
|---|---|---|---|---|---|---|---|---|
| reference (21 to 27 s) | 0, 0.30 of a band | 0, 0.21 | 0, 0.22 | 0, 0.66 | 0, 0.33 | 0, 0.39 | 0, 0.17 | 0, 0.39 |
| `ladder/noorder.py` | 165 and 176 | | 255 | 254 | 160 | 210 | 206 | 163 |
| `ladder/legible.py` | 0 | 89 | 84 | 90 | 39 | 44 | 38 | 0 |
| `ladder/decline.py`: no bore check | 0 | 47 | 44 | 47 | 39 | 0 | 0 | 0 |
| `ladder/narrow.py`: no trend check | 0 | 42 | 40 | 43 | 0 | 44 | 38 | 0 |
| `ladder/stalebore.py`: finds the pipe, does not survey it | 0 | 47, to 5.8 bands | | | | | | |
| `ladder/keepu.py`: bore fitted, coefficient not re-derived | 0 | 35, to 2.5 bands | | | | | | |

The reference at 50 marching steps instead of 100 runs a site in 11 to 14 s with the same errors: what is left
is the reading accuracy of the surveys, not the integration.

## Probes (opus, sandboxes from tools/mkprobe.sh with the crew's command)

| probe | effort | time | examples | six hidden sites | what it did |
|---|---|---|---|---|---|
| L1 | low | 19.7 min | accepted | 5 of 6 out, as `legible` | ordered the re-covered pipes |
| L2 | low | 7.5 min | accepted | 5 of 6 out, as `legible` | the same |
| L3 | low | 11 min | accepted | 5 of 6 out, as `legible` | the same; reported a drift check its program does not act on |
| X1 | xhigh | 32 min | accepted | 3 of 6 out, as `decline` | ordered both conditioned pipes; called the narrowing pipe "a growing deposit" and kept the bore as laid |
| X2 | xhigh | 25 min | accepted | 3 of 6 out, as `decline` | ordered both as "drifting coverings" |
| X3 | xhigh | 56 min | accepted | **accepted**, worst 0.44 of a band | compared each pair's surveyed division with equal pressure drop, fitted bore and coefficient together (62.5, 61.0, 59.6 mm of 65 laid), ordered both pipes |

- **Low: the designed miss, three times.** Stall, history and the re-covered pipes in 7 to 20 minutes; none
  looked at a campaign trend or a pair's surveyed division.
- **xhigh: 3 of 3 order the declining covering and the narrowing pipe.** In v2 the narrowing pipe's apparent
  coefficient drifts as well (the heat balance is read with the wrong bore), so the trend check alone puts it
  in the order. What separates the runs is what the fresh reading is used for: X3 solves the bore, X1 and X2
  re-derive a coefficient with the register bore and fail every record of that line by 15 to 26 bands.
- **The reworded 5.1 is enough for a run that asks what D is.** X3 cites "pipes are not gauged in service" as
  the reason the register's bore need not be the pipe's. X1 saw the deposit and chose the register anyway,
  which is a judgement the documents no longer make for it.
- **The limit does not bind**: probe programs run a site in 1.4 to 9.6 s. X3's runs in 1.5 s.

## Files
- `line.py`, `pair.py` sealed definition; `gen.py` (every line redrawn until its survey rating and its records
  are laminar and every pair stalls somewhere in its records)
- `core/` the agent's data and the crew; `hidden/` six sites with truth; `hidden_lab/` the crew's books for
  all nine, the pending truth, what is true of each pipe
- `ref_lines.py`, `ladder/`, `grade.py`, `brief.txt`, `mk.sh`; `probes/` the six programs as delivered
