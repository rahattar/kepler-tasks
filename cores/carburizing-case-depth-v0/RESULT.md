# carburizing-case-depth bare core v0 (Nov 13): oxygen probe drift read off the enrichment gas; low 1 of 3, 3 of 3 found it

A timed program: for every load in six months of a carburizing furnace's 1 min record (about 250 loads), the
surface carbon and the effective case depth (CD-2 in `core/data/docs`: Tibbetts diffusivity, mass transfer at
the surface). On the pending furnace and four of six hidden furnaces the oxygen probe reads high from an
unrecorded date, by up to 0.09 to 0.22 %C; the evidence is the enrichment gas, which CD-2 never uses. 15 s of
CPU a run; case depth within 2 per cent and surface carbon within 0.02 %C on every load.

## Probes (opus, low effort)

| probe | time | hidden | what it did |
|---|---|---|---|
| C1 | 5 min | not accepted: one load of 1500 out, by 1.06 bands | found the drift from the gas; balance fitted after `probe_calibrated_day`, refitted on the loads found true; per-load offsets |
| C2 | 4.5 min | not accepted: four drifting furnaces out by about 4 bands | found the drift; its offsets came out about a fifth low |
| C3 | 7 min | **accepted, 6 of 6**, worst 0.91 of the band | found the drift; the same balance, with a temperature term; tested on planted drifts |

Low effort: 1 of 3 solved, and all three found the condition within minutes. Over the bar. No xhigh round.

## Reading

- **Three signposts, all mine.** `probe_calibrated_day` in the furnace register told every run where to anchor;
  a column the standard never uses, described as what the controller adds to hold the probe at setpoint, told
  it what to check; and the brief's "nobody reviews" told it to check. A heat treater handed those asks whether
  the probe is right, and the gas answers it.
- **The estimate is the only difficulty left**, and it is ordinary: two of three runs got it within tolerance.
- The time limit separated nothing: all three vectorised across loads (4 to 6 s).

## Checks before the probes

| program | hidden |
|---|---|
| reference (`ref_case.py`) | accepted, 4.3 to 6.0 s, worst 0.72 of the band |
| the probe taken as the atmosphere (`probe_case.py`) | fails all four drifting furnaces, 58 to 207 loads out, up to 18 bands |
| unoptimised (each load stepped alone) | about 51 s with the offset estimate |

## Files

`cd.py`, `gen.py` (specs, shift, `core/manifest.json`; the data is rebuilt by `mk.sh` and kept out of git),
`ref_case.py`, `probe_case.py`, `grade.py`, `brief.txt`, `mk.sh`.
