# shaft-alignment bare core, v2: a class the listing does not show. Low 1 of 6, xhigh 2 of 3 (Nov 11)

v1 with two changes, both aimed at the run that counts before it spends.

- **The legible count is one short of the budget.** Five needs can be read off the records: two turbines and
  three changed pump classes (lagged foot-mounted, blanked foot-mounted, blanked centreline). Six visits. A run
  that counts has one to spare.
- **The sixth need is in no cell.** `pump_data.csv` lists HSC-250 and HSC-400 identically (foot, water-cooled).
  In the 2019 survey their supports ran at 0.38 and 0.47 of the pumped rise. After the cooling was blanked they
  run at 0.80 and 0.66. One visit carried across both models leaves the other 0.36 to 0.59 mm out, against 0.05.
  The other two listed classes are each uniform in the 2019 survey and one visit does cover them.
- The three compressors with vibration complaints are still there, and still settled by the records.

Reference route 36 of 36, worst residual 0.012 mm. Every probe on `model: "opus"`.

| probe | effort | visits | trains | time |
|---|---|---|---|---|
| 1 | low | TP-301A, TP-301B, **K-201A**, P-310A, P-325B, P-342 | 34 of 36 | 99 s |
| 2 | low | TP-301A, TP-301B, **K-201A**, P-310A, P-325B, P-342 | 34 of 36 | 94 s |
| 3 | low | TP-301A, TP-301B, **K-201A**, P-301A, P-320A, P-340A | 33 of 36 | 95 s |
| 4 | low | TP-301A, TP-301B, **K-201A**, P-301A, P-320A, P-340A | 33 of 36 | 87 s |
| 5 | low | TP-301A, TP-301B, P-301A, P-322, P-340A, P-320A | 36 of 36 | 155 s |
| 6 | low | TP-301A, TP-301B, **K-201A**, P-310A, P-325B, P-342 | 34 of 36 | 113 s |
| 7 | xhigh | TP-301A, TP-301B, P-301A, P-325B, P-342, P-320A | 36 of 36 | 8.3 min |
| 8 | xhigh | TP-301A, TP-301B, P-310A, P-325A, P-342, P-320A | 36 of 36 | 10.9 min |
| 9 | xhigh | TP-301A, TP-301B, **K-201A**, P-304, P-325A, P-342 | 34 of 36 | 10.5 min |

**The five low-effort failures are one failure.** Each bought the compressor third, straight after the
turbines, "because all three have complaints and the figure dates from 2017". The laser returned the maker's
figure exactly and agreed with the sag-corrected dial sheet to 0.001 mm, which each run reported as confirming
its method. Three visits were left for three listed classes, so nothing pressed. Two of the five noticed the
0.38 and 0.47 afterwards and wrote it up as a judgement call with no visit left to settle it.

**The passes reasoned as intended.** Probe 7: "the two models behaved differently before the work (0.47 and
0.38), so each needed its own visit"; and of the centreline pair, "behaved the same before (0.16), so one visit
covers both". Both xhigh passes declined the compressors in terms: the revamp did not touch them and AP-12 gives
the maker's figure. The low-effort pass sampled the blanked pumps by model and used the 2019 fractions to decide
which unmeasured model could borrow a figure.

**Against section 5 of the trap analysis.**
1. No cell of text names it: the split is a ratio of two columns in a seven-year-old survey that the solver's
   own route has no use for, since a changed pump's old fraction is discarded.
2. The wrong route validates itself: the wasted visit confirms the method to a micrometre.
3. The miss is wide and the same in every run: 7 to 12 times the tolerance, on the same five pumps.
4. It survives the solver's tooling: nothing is fitted, so no residual shows it.
It is irreversible, like kind A: the visit is spent before the split is understood.

**What is not established.** 1 of 6 puts the low-effort solve rate somewhere under about 0.6 at 95 per cent.
At one in six the screen passes 58 per cent of the time. The one low-effort pass went by pump model, and the
model column is a cell of text that separates the two halves of the split.
