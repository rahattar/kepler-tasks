# engine-indicating bare core v4 (Nov 13): low 0 of 6, xhigh 3 of 6. Measured, not built.

v4 is v3's records with a seventh result in the table: IS-2's polytropic exponent of compression, the slope of
ln p against ln V from 100 to 50 degrees before top dead centre. Under the standard it is 1.337 to 1.345 at
every point of every sound cell. As recorded it is 1.30 to 1.31 at pending cell_11 (index) and 1.37 to 1.38
at pending cell_13 (gain), so a program's own output on the pending packages shows both. Put down to the
index alone, cell_13's exponent returns to 1.339 to 1.345: the wrong diagnosis confirms itself exactly.

## Probes (opus = claude-opus-5-5), graded by the bundle's checker

| probe | time | hidden | what it did |
|---|---|---|---|
| low 1 | 2.1 min | 5 of 6 cells out | reported "1.30-1.31 for cell_11 and 1.37-1.38 for cell_13, against about 1.34"; calculated as written |
| low 2 | 6.7 min | 5 of 6 cells out | IS-2 as written |
| low 3 | 7.1 min | 4 of 6 cells out | "cell_11 reads about 1.6 degrees off and cell_13 about -1.4, consistently over every point and cylinder": index alone |
| low 7 | 1.5 min | 5 of 6 cells out | IS-2 as written |
| low 8 | 1.9 min | 5 of 6 cells out | "cell_13 gives about 1.37 ... nothing in the package lets me tell which, so the program calculates it as written" |
| low 9 | 4.9 min | 5 of 6 cells out | IS-2 as written |
| xhigh 4 | 31 min | **accepted**, worst 0.45 | index, gain and a wall-heat factor for each cylinder |
| xhigh 5 | 22 min | 5 of 6 cells out | IS-2 as written |
| xhigh 6 | 44 min | **accepted**, worst 0.19 | index from the valve events, gain from the compression |
| xhigh 10 | 25 min | 5 of 6 cells out | IS-2 as written; noted the expected exponent is the same for every cylinder |
| xhigh 11 | 46 min | **accepted** | index from the exhaust-valve kink, gain from the compression |
| xhigh 12 | 30 min | 1 row of 250 out (10 per cent burned, 2.2 bands) | found both; its pooling of estimates slipped on one point and cylinder |

- **The column doubles what careful runs find:** 4 of 6 xhigh runs diagnosed both conditions against 1 of 3
  in v3, and 3 of 6 were accepted.
- **Low effort sees it and does not act, or acts on the first explanation.** Three of six low runs remarked
  on the exponent; one corrected the index alone and was confirmed by the exponent itself.
- **Three runs wrote that the result "to IS-2" might mean the records as given.** IS-2 now says in section 2
  that p is the pressure in the cylinder and theta the crank angle of that cylinder.
- **Two runs called the values planted** (1.600 degrees, 1.0600). The bundle's are not round.

## Reading

Inside the band on these counts, but at 3 to 4 in 6 an official 8 lands on 6 or more about one time in three.
The bundle keeps v3's table. The exponent column is the known lever if the official difficulty count comes
out too low to be credible: it moves xhigh up and leaves low where it is.
