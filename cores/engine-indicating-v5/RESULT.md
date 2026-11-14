# engine-indicating v5 (Nov 13): the bundle, built on v3

`tasks/engine-indicating-analysis`. v3's design with values that are not round, and what changed while it
was built.

- **Values.** cell_11 index -1.57 degrees, cell_13 gain 1.063; hidden: +2.23, gain 0.947, +1.34 with 1.052,
  -2.41 with 0.958, exact, gain 1.071.
- **IS-2 section 2** now says that p is the pressure in the cylinder and theta the crank angle of that
  cylinder, after three v4 runs wrote that a result "to IS-2" might mean the records as given.
- **Bands** are IS-2 section 9's: 2 per cent on mean effective pressure, 1 on peak pressure, 3 on heat
  released, 0.3 degrees on angles. The second solution's widest departure is 0.49 of a band.
- **Limit 4 s**, not v3's 5: the reference takes 0.9 to 1.6 s a cell alone on the machine, and 5 s came out
  at 3.9 times the slowest run on a quiet one.
- **Record files are `records/p01.npy`**, lower case: shipcheck refuses an all-uppercase file name.
- **After the journal bearing oracle failures of the same day:** the checker sets no CPU affinity, the
  whole-verifier study runs `bash tests/test.sh` itself (reward 1 for the reference under its umask 077), and
  the instruction states the reader's cap on OUT_CSV (2 MiB) and that it is an ordinary file, not a link.
- **Subfield** 117 characters (limit 120).

## Probes on the finished bundle (opus = claude-opus-5-5), at the 5 s limit and the first draft's wording

| probe | hidden | what it did |
|---|---|---|
| low 1 | 5 of 6 cells out, every row | IS-2 as written |
| low 2 | 5 of 6 cells out, every row | IS-2 as written |
| low 3 | 5 of 6 cells out, every row | IS-2 as written; noted that the angle of a sample is the system's and did not test it |

Regraded at the 4 s limit: the same, 1.1 to 1.9 s a run. The three programs agree with each other to a
hundredth of a band, as programs that follow one standard should. v3's accepted xhigh 5 regraded on the
bundle's cells and bands: accepted, widest 0.20 of a band, 0.4 to 0.5 s a run.

No xhigh run on the bundle; v3's 1 of 3 and v4's 3 of 6 stand for it.

## Files

- `brief.txt` what the probes were given; `readme.py` writes README.md and task.toml from the evidence;
  `run_evidence.sh` regenerates every study in order (about 25 minutes, the seed screen 14 of them).
- The instruction draft was reworded after the probes to bring it away from journal-bearing-survey's, now
  lube-oil-survey (difflib ratio 0.70 to 0.43). Same facts, plus the cap; not re-probed.
- **Shipped instruction** is Alex's rewrite of the draft (Nov 13 evening): preflight clean, shipcheck clean,
  reward 1 for the reference through `bash tests/test.sh` from the unzipped bundle. It says "up to 6 cylinders
  and 20,000 cycles" without "counting every cylinder"; the largest hidden package has 18,000 in all, so either
  reading covers it. Not probed in this wording.
