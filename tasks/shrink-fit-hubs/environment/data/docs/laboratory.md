# Joint laboratory

    slip <material> <dry|oiled|paste> <pressure_MPa> [shrink]

makes a 40 mm specimen joint of a hub of the material on a steel shaft, with the surface preparation given, at an
interference that gives the contact pressure stated (10 to 200 MPa), and reports the coefficient of friction from the
torque at which it slips. The specimen is pressed together on a press; with `shrink` it is assembled by heating the
hub instead. Materials: steel, ductile-iron, bronze, aluminium.

    cte <material> <T>

reports the mean coefficient of expansion of the material from 20 C to T (100 to 400 C), from a dilatometer.

Run them from `/app`; each report is printed and saved under `/app/lab_reports`. The laboratory is booked for 8 tests
in all.
