# Vendor catalogue - fixed tubesheet coolers, carbon steel

One shell pass per shell (TEMA E shell), segmental baffles, tube pitch 1.25 times the tube OD. Shells can be
connected in series (oil side and water side both in series, counter-current between shells).

| item | choices |
|---|---|
| shell inside diameter, mm | 305, 337, 387, 438, 489, 540, 591, 635, 686, 737, 787, 838 |
| tubes (OD x wall, mm) | 19.05x1.65, 19.05x2.11, 25.40x2.11 |
| tube length, m | 2.44, 3.66, 4.88, 6.10 |
| tube passes | 2, 4, 6 |
| tube layout | 30 deg (triangular), 90 deg (square) |
| baffle cut, % of shell ID | 20, 25, 35 |
| central baffle spacing | any whole millimetre from 0.2 x shell ID (at least 50 mm) to the shell ID |
| shells in series | 1, 2, 3 |

Tube counts for each shell, tube, layout and pass arrangement are in vendor_catalogue_tube_counts.csv.

TEMA maximum unsupported straight span, carbon steel tubes: 1524 mm for 19.05 mm OD, 1880 mm for 25.40 mm OD.

Construction clearances (diametral): shell to baffle 3.1 mm + 0.004 x shell ID; tube to baffle hole 0.8 mm; bundle to
shell 12 mm + 0.005 x shell ID. No sealing strips. Inlet and outlet baffle spacings equal the central spacing; the
number of baffles is the tube length divided by the spacing, rounded, minus one.

## Price of one shell (USD, installed)

9000 + 26 x shell ID (mm) x tube length (m) + 210 x tube outside area (m2) + 450 x tube passes, plus 600 for the 90
deg layout; rounded to the nearest 10.
