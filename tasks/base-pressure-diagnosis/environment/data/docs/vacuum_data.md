# Shop vacuum data

The tables MS-BP refers to. All values are for the shop reference temperature of 20.00 C unless stated.

## Turbomolecular pumps

Speed against inlet pressure for nitrogen, as the maker publishes it. Between table points the speed is linear in
log10 p; beyond the ends it is held at the end value. The last three columns are what a pump of that model in good
order reports to its controller at its rated speed, which is how a controller record is read.

| pump | speed curve, mbar: L/s | rotor, Hz | drive power, W | bearing, C |
|---|---|---|---|---|
| TMP-1100 | 1e-09: 1010; 1e-03: 1010; 1e-02: 640; 5e-02: 230; 2e-01: 55 | 700 | 130 | 45 |
| TMP-1600 | 1e-09: 1480; 1e-03: 1480; 1e-02: 900; 5e-02: 310; 2e-01: 70 | 600 | 170 | 48 |
| TMP-400 | 1e-09: 360; 1e-03: 360; 1e-02: 250; 5e-02: 100; 2e-01: 28 | 1000 | 60 | 38 |
| TMP-700 | 1e-09: 640; 1e-03: 640; 1e-02: 420; 5e-02: 160; 2e-01: 40 | 820 | 95 | 42 |

## Outgassing of internal surfaces after an air vent

Specific gas load at 1 h and 20.00 C, and the decay exponent alpha of MS-BP clause 3.1.

| surface | q1, mbar L/(s cm2) at 1 h | alpha |
|---|---|---|
| PEEK | 3.5e-07 | 0.60 |
| aluminum, anodized | 5.5e-07 | 0.85 |
| aluminum, bare | 1.4e-08 | 1.00 |
| copper, bare | 2.2e-08 | 1.00 |
| graphite felt | 9.0e-07 | 0.70 |
| stainless steel, as machined | 2.6e-08 | 1.00 |
| stainless steel, bead blasted | 6.5e-08 | 0.95 |
| stainless steel, electropolished | 7.0e-09 | 1.00 |

## Elastomer seals

K20 is the permeation gas load per cm of seal length for atmospheric air at 20.00 C. The relative permeabilities
are referred to nitrogen and set the composition of permeated gas.

| seal material | K20, mbar L/(s cm) | relative permeability |
|---|---|---|
| fluoroelastomer | 1.15e-07 | n2 1.00, o2 3.00, ar 0.35, co2 12.00 |
| nitrile | 3.40e-07 | n2 1.00, o2 2.60, ar 0.40, co2 10.00 |
| perfluoroelastomer | 4.20e-08 | n2 1.00, o2 2.80, ar 0.30, co2 11.00 |

## Dry air

| species | fraction of dry air |
|---|---|
| ar | 0.00934 |
| co2 | 0.00042 |
| n2 | 0.78080 |
| o2 | 0.20950 |

## Gauge sensitivities

Relative sensitivity of a nitrogen-calibrated ionization or cold cathode gauge to each species, for MS-BP clause 5.

| species | relative sensitivity K |
|---|---|
| ar | 1.29 |
| co2 | 1.42 |
| h2 | 0.42 |
| h2o | 1.12 |
| n2 | 1.00 |
| o2 | 1.01 |

## Composition of the gas each mechanism admits

| mechanism | composition of the gas it admits |
|---|---|
| wall-outgassing | h2 0.015, h2o 0.960, n2 0.025 |
| air-leak | ar 0.009, co2 0.000, n2 0.781, o2 0.209 |
| virtual-leak | ar 0.009, co2 0.000, n2 0.781, o2 0.209 |
| permeation | dry air, each species weighted by the seal's relative permeability, renormalised |

## Shop fixtures

The areas and surfaces of the fixtures, carriers and racks the shop puts in its chambers. A load in the chamber adds
its area to the outgassing sum of MS-BP clause 3.1.

| item | area, m2 | surface |
|---|---|---|
| braze fixture | 2.10 | stainless steel, bead blasted |
| carrier set A | 2.40 | stainless steel, as machined |
| carrier set B | 1.60 | stainless steel, bead blasted |
| harness tray | 0.30 | PEEK |
| lens rack | 0.55 | aluminum, anodized |
| shield set | 1.80 | aluminum, bare |
