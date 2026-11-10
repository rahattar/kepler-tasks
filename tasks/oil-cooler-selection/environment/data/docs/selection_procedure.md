# Lube oil cooler replacement - selection procedure

The plant replaces its lube oil coolers in kind: shell-and-tube, oil on the shell side, cooling water in the tubes,
a standard design from the vendor catalogue (vendor_catalogue.md). Each cooler has a case package
(case_package.md) with its requirements and its records.

## Design case

The design case is the cooler's operation over the period in case.json. For each of the following, the design value
is the highest one-hour mean of the true process value over the period:
- oil flow to the cooler;
- oil temperature at the cooler inlet;
- cooling water supply temperature at the cooler inlet.

Cooling water flow: the allotment in case.json.

Oil properties: those of the oil in service at the end of the period, from its latest analysis. If the oil was
changed to another grade after the latest analysis, the typical properties of the new grade (oil_grades.csv).

## Requirements at the design case

- Oil outlet temperature, oil side and water side pressure drop across the cooler (all shells), and tube velocity:
  the limits in case.json.
- Tube support: the unsupported tube span (twice the central baffle spacing) must not exceed the TEMA maximum for
  the tube size (vendor_catalogue.md).
- Rating, fouling resistances and fluid properties: the plant rating standard (rating_standard.md).

Of the designs that meet every requirement, the plant buys the one with the lowest installed price (the
catalogue price of one shell times the number of shells).
