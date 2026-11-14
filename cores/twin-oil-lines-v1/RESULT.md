# twin-oil-lines bare core v1 (Nov 13): low 0 of 3, xhigh 0 of 3, and the xhigh misses are a sentence of the standard

v0's physics (heated fuel oil in single pipes and pairs, a pair's division with its stability and history) with
the stall moved into the examples with results, where v0 showed every solver finds it. What decides a hidden
site is now a record that is wrong with no physical reason to doubt it, curable by a survey the program has
to order while it runs. Small: 30 lines, 50 pipes, about 1,280 records a site; 60 s of CPU a run.

## The core

- Outside coefficients are not given. They come from heat-loss surveys on file, three campaigns of every pipe
  (flow through the pipe, oil temperature in and out, surroundings), inverted through TS-2 section 3. A pair's
  two pipes have their own coverings, so pairs divide unevenly as a rule (shares 0.33 to 0.58 on file).
- The program places one order with the survey crew while it runs, `heatsurvey PACKAGE_DIR PIPE ...`, of at
  most `survey_allowance` pipes, each read as it stands after the last record.
- Legible need: the 3 or 4 pipes whose covering was renewed or repaired after the last campaign. In both
  examples the allowance is exactly that number, and a run without the order is out on those lines (126 and
  134 records, up to 37 bands). Three more covering jobs a site lie before the last campaign and need nothing.
- **Narrowed pipe** (pending, 3 of the 6 hidden sites planned): one pipe of a pair has 6.5 to 10 per cent
  less bore than the register's. No file says so. With the bores as laid, the two pipes' pressure drops at
  their surveyed flows differ by 20 to 50 per cent in every campaign. Allowance: one more.
- **Declining covering** (pending, 4 of 6 planned): a pipe's coefficient rises 15 to 22 per cent a campaign
  with no work logged and stands 45 to 70 per cent above its last survey now. Allowance: one more.
- The crew answers for the two example sites only where the program is written; the pending site has no
  results. TS-2 says what a survey measures and what the register records. Nothing says a record can be wrong.

## What was measured (grade.py, the crew answering from sealed books)

| program | examples | pending west_jetty | south_wharf (both) | canal_basin (both) | upper_yard (narrowed) |
|---|---|---|---|---|---|
| reference: re-covered pipes, the narrowed pipe, the declining pipe | 0 out, 0.26 of a band | 0 out | 0 out, 0.24 | 0 out, 0.37 | 0 out, 0.27 |
| `ladder/noorder.py` | 126 and 134 out | 238 | | | |
| `ladder/legible.py`: re-covered pipes only | 0 out | 82 of 1277 on 2 lines | 88 on 2 lines | 81 on 2 lines | 48 on 1 line |
| `ladder/decline.py`: no bore check | 0 out | 40 on 1 line | | | |
| `ladder/narrow.py`: no trend check | 0 out | 42 on 1 line | | | |

A missed condition puts every record of its line out, by up to 23 bands. Only three of the six hidden sites
were generated: the generator stalled on lines whose flows leave the laminar scope (see defects).

## Probes (opus, sandboxes from tools/mkprobe.sh with the crew's command)

| probe | effort | time | examples | pending, crew answering | three hidden sites | order |
|---|---|---|---|---|---|---|
| L1 | low | 7.4 min | accepted | 82 out, 2 lines | 3 of 3 out, as `legible` | the re-covered pipes |
| L2 | low | 5.9 min | accepted | 82 out, 2 lines | 3 of 3 out, as `legible` | the same |
| L3 | low | 10.3 min | accepted | 82 out, 2 lines | 3 of 3 out, as `legible` | the same |
| X1 | xhigh | 29 min | accepted | 40 out, the narrowed line | 3 of 3 out, the narrowed line only | re-covered, the declining pipe, a spare |
| X2 | xhigh | 29 min | accepted | 40 out, the narrowed line | 3 of 3 out, the narrowed line only | the same |
| X3 | xhigh | 84 min, program unchanged after 19 | accepted | 40 out, the narrowed line | 3 of 3 out, the narrowed line only | re-covered and the declining pipe |

- **Low effort: the designed miss, three times.** All three found the stall and its history from the examples'
  results, ordered exactly the re-covered pipes, ran the pending site and reported that it runs cleanly. L3
  noted that the pending allowance is 6 and did not ask why. L1 checked that Uo is steady across campaigns and
  that a pair's pipes have matching pressure drops at their surveyed flows, on the examples only.
- **xhigh: all three found the declining covering** from the spread of a pipe's surveys against the stated
  reading accuracy, and ordered it.
- **xhigh: X3 did not look at the division of a pair on file.** Its misses are the `decline` program's.
- **xhigh: X1 and X2 found the narrowed pipe and declined to act on it.** Both computed that FL-218 divides
  35 to 65 where TS-2 with the register bore gives 48 to 52, and both kept the register bore because 5.1 read
  "The bore and the length of a pipe are those of the lines register". X1: "TS-2 5.1 says to use the register
  bore, so I don't correct for it." That is the standard prescribing the wrong record, not difficulty.

## Lessons

- **Say what a register records, never that a quantity "is" the register's.** One prescriptive sentence turned
  two correct findings into two misses. v2's 5.1 reads "The lines register records the bore and the length
  each pipe was laid with."
- **Repeated measurements with a stated accuracy are a consistency check every careful run makes.** The
  declining covering was found 3 of 3 at xhigh and 0 of 3 at low. It separates the two efforts and does not
  hold at xhigh by itself.
- **A model check against measurements the model never needed is made at xhigh, not at low.** The surveyed
  flows of a pair are only inputs to each pipe's coefficient; two xhigh runs still compared the model's
  division with them. One low run made the same check and stopped at the examples.
- **Stall and history as feedback cost minutes**: every probe had them right before its first report.
- The time limit did not bind: probe programs run a site in 3 to 9 s, the reference in 24 to 30 s.

## Defects found in the core

- Some lines are outside the standard's laminar scope: 30 survey runs on 10 pipes over the five sites exceed
  Re 2000 (up to 3545), and the generator could not draw laminar records for a few lines and stalled on
  kiln_road. v2 draws every line so that its survey rating and its records are laminar.
- The reference's largest error is 0.37 of a band, from the reading accuracy of the surveys.

## Files
- `line.py`, `pair.py` sealed definition (unlike pipes, every division, the basin rule); `gen.py`
- `core/` the agent's data and the crew (`environment/rig/lab.py`, books for the examples); `hidden/` three
  sites with truth; `hidden_lab/` the crew's books for every site, the pending truth, what is true of each pipe
- `ref_lines.py`, `ladder/`, `grade.py`, `brief.txt`, `mk.sh`; `probes/` the six programs as delivered
