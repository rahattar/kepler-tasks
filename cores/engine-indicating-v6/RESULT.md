# engine-indicating v6 (Nov 13 evening): the requirement stated, after the quality rejection

The shipped bundle (v5) failed "well specified" and "test instruction alignment" because nothing the agent
read said that the package's angle and scale might not be the crank angle and the pressure
(`docs/rejection-patterns.md`). v6 states it. IS-2 gains section 3 (`is2_indicating.md` here), which says:
- the encoder's mark may stand off top dead centre by an index delta (theta = theta_sys + delta);
- the transducers may give more or less than the scale assumes by a gain g;
- one of each holds for a package, delta within 4 degrees and g within 0.9 to 1.1;
- both are established from the package's records: from 10 degrees after inlet valve closing to 40 degrees
  before top dead centre Q must be nil, and the pair is the one that brings Q nearest to nil by least squares
  over the mean cycles.

Data, examples and the instruction (Alex's) are unchanged. The reference was moved onto the stated stretch:
accepted, widest 0.40 of a band. The checker now counts processor time of the whole run.

## Probes (opus = claude-opus-5-5), the brief is the shipped instruction

| probe | hidden | what it did |
|---|---|---|
| low 1 | accepted, widest 0.38 of a band | the stated fit, a free level per trace; found -1.63 / 1.002 and 0.03 / 1.062 on the pending packages |
| low 2 | accepted, widest 0.37 | the same, with a coarse grid then least squares |
| low 3 | cell_02 out on every row (1.6 bands), the rest in | a fit that came out short at the largest index |

Low 2 of 3: the easiness bar (0 of 3) fails. xhigh not run.

Both accepted runs said they had to depart from a literal fit: no resampling of the record onto the
corrected angle, and a free level taken out of Q, since noise early in the stroke shifts Q by a constant.
Neither departure was hard for them.

## What it shows

Once the condition and its criterion are written down, the task is a two-parameter least-squares fit with a
first-law residual that low effort writes in under ten minutes. The difficulty of v3 to v5 lived in the
condition being unstated, and the quality review does not accept that.
