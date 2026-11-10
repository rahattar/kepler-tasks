# Heat treatment procedure HT-4: hardening and tempering of alloy steel parts

1. Hardening: austenitise and quench in oil (all grades). The parts are then tempered as below without delay.
2. Tempering: the furnace setpoint is a whole degree C. The soak time at temperature is 1 h per 25 mm of ruling section,
   and at least 2 h, counted from when the load thermocouple reaches the setpoint. Grade G52 is double tempered: two
   identical tempers, with the parts cooled to room temperature between them. The lowest permitted tempering
   temperatures are 400 C for G41 and G43, 500 C for G32 and 540 C for G52.
3. Acceptance: the hardness at the location the drawing names (the surface, or half the radius of the ruling section)
   is within the drawing's range.

Grades: G41 (1 % Cr - 0.2 % Mo), G43 (1.8 % Ni - 0.8 % Cr - 0.25 % Mo), G32 (3 % Cr - 0.9 % Mo - V), G52 (5 % Cr - 1.3 % Mo - 1 % V).

Equivalent Jominy distance of oil-quenched rounds (mm), by ruling section diameter (mm):

| Diameter | Surface | Half-radius |
|---|---|---|
| 25 | 1.5 | 5.0 |
| 50 | 3.0 | 10.0 |
| 75 | 4.5 | 14.0 |
| 100 | 6.0 | 18.0 |
| 150 | 8.5 | 25.0 |
| 200 | 11.0 | 32.0 |
| 250 | 13.0 | 38.0 |
| 300 | 15.0 | 44.0 |

Records: `mill_certificates.csv` (composition and Jominy hardness of each heat), `batches.csv` (the thirteen batches),
`production_log.csv`, and `supplier_tempering_curves.csv` (the steel supplier's typical tempering curves: one 2 h
temper of a 25 mm round, hardness at half-radius).
