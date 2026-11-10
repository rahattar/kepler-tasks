# Plant standard RS-3: shrink-fitted rotor parts

Impellers, balance drums and thrust collars are fitted to the rotor by heating the part in an oven and sliding it onto
its seat; they are held by the fit alone. Dimensions are at 20 C.

The bore is finish-honed to Rz 3.2 um and to IT5 (for the seat's nominal diameter) about its specified diameter, so
the interference lies within the mean -/+ IT5 / 2. The interference that acts in the fit is the geometric interference less the smoothing of the
surfaces on fitting, 0.8 x (Rz of the bore + Rz of the seat).

1. Retention: at the least interference, at rest and at trip speed in running, the contact pressure at the seat is at
   least 15 MPa, and an impeller's fit carries twice the stage's torque at MCS with the friction coefficient below.
2. Hub stress: at the greatest interference, at rest and at trip speed in running, the von Mises stress at the bore,
   including the hoop stress of rotation, does not exceed the part's yield strength divided by 1.2.
3. Assembly: at the oven temperature the bore clears the seat, as the rotor stands in the overhaul bay, by at least
   0.001 x the seat diameter, and the oven temperature does not exceed the part's heating limit.

In running means at the temperatures of the thermal survey (`thermal_survey.csv`).

Friction coefficient of a dry, degreased fit on rotor steel: FV520B 0.15, 42CrMo4 0.15, Ti-6Al-4V 0.12.

| Diameter (mm) | IT5 (um) |
|---|---|
| up to 80 | 13 |
| up to 120 | 15 |
| up to 180 | 18 |
