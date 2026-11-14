# Design note: engine-indicating-analysis (Nov 13)

A timed program on shifted hidden data, to the Nov 11 ask. Built from bare cores v0 to v4
(`cores/engine-indicating-v*/RESULT.md`, and the engine indicating section of
`docs/difficulty-calibration.md`). The bundle is v3's design.

**Mechanism.** The instrument is not what its package says, and the proof is in the physics of the record,
not in a field. Two instrument conditions with nearly the same signature have to be separated, and the first
explanation a solver reaches confirms itself.

- A package gives each sample "the indicating system's angle" and "the indicating system's scale". IS-2 is
  written for the crank angle of the cylinder and the pressure in it.
- **Index.** The encoder's mark sits off top dead centre, 1.3 to 2.4 degrees. A degree moves the mean
  effective pressure by 4 to 12 per cent.
- **Gain.** The transducer gives 5 to 7 per cent more or less than the scale assumes.
- Both leave a gross heat release on the compression stroke where there is none. After pegging, a gain
  error bends the compression line much as an index error does: cell_13's gain of 1.063 fits as an index
  error of about +1.5 degrees, the same at every point and cylinder.
- Both examples with results are exactly sound. Two pending packages without results carry one condition
  each (cell_11 index, cell_13 gain). Five of six hidden cells carry one or both, of either sign.

**What must not be changed without re-probing.**
- The pending packages have no results. With results the wrong program fails a visible test.
- The examples are sound to the last digit. v2's examples carried 0.02 degrees of index error and a low run
  traced it.
- No field of `engine.json` or `points.csv` names the encoder or the transducer's state. v1 had an
  `encoder_index` entry that IS-2 never used: low 3 of 3.
- No result column that comes out impossible or constant-but-off when the records are taken as given. v0's
  heat release was negative on some rows (low 1 of 3); v4's polytropic exponent doubled the xhigh rate.
- The format document's two phrases, "the indicating system's angle for sample k" and "the indicating
  system's scale". They are accurate and they do not say the system is right.
- IS-2 section 2's sentence that p is the pressure in the cylinder and theta the crank angle of that
  cylinder. Without it three runs wrote that a result "to IS-2" might mean the records as given.
- The values are not round (v4: two runs called 1.600 degrees and 1.0600 planted).

**The timed half.** Limit 4 s a run on one CPU; the reference takes 0.9 to 1.6 s a cell, vectorised over
the cycles of a point, with index and gain settled once for a cell from the mean cycles (the committed run:
3.0 times the slowest). The second solution (plain loops, an ODE solver for the compression) is 12 to 24
times over. The cores were probed at 5 s; an accepted probe program runs in 0.4 to 0.5 s. As in journal bearing, the
limit separates no probe run: every run vectorised. It is there because the ask requires it.

**Verifier.** Each run as nobody, one thread to a library and no CPU affinity, in a directory of its own; a
run over the limit ends the assessment. `bash tests/test.sh` itself gives the reference reward 1. Bands are IS-2 section 9's: 2 per cent on mean effective pressure, 1 on peak pressure, 3 on heat
released, 0.3 degrees on angles. The truth is the sealed cylinder model on the true pressure, never a run of
the reference.

**Size.** Six hidden cells of 9,000 to 18,000 cycles are 104 MB of int16 records and the visible ones 58 MB;
the zip is the largest so far. The cycle counts are what make the limit bite; cutting them cuts the timed
half.

**Local rates** (`model: "opus"`, claude-opus-5-5; graded by the bundle's checker).

| design | low | xhigh |
|---|---|---|
| v3, the bundle's | 0 of 3, and 0 of 3 again on the finished bundle | 1 of 3 |
| v4, v3 plus the exponent column | 0 of 6 | 3 of 6 |

The exponent column is the known lever if the official difficulty count comes out at 0 of 8 and that is
judged too hard to be credible: it raises xhigh and leaves low where it is.

**Closed, Nov 13.** The bundle failed quality review ("well specified", "test instruction alignment") because
the deciding condition was never stated (`docs/rejection-patterns.md`). Stated in IS-2 with its criterion
(core v6), low effort solved it 2 of 3; redesigned with six stated layers (core v7), 3 of 3. Alex closed the
subject.

