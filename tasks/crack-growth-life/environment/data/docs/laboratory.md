# Crack growth testing

The materials laboratory tests compact-tension (CT) specimens to ASTM E647, cut from retained flange plate of any of
the four heats (H1 to H4) and stress relieved before machining, in laboratory air at room temperature, at a load ratio
R = Kmin/Kmax of your choosing (0.05 to 0.90). Results are reported as crack growth rate da/dN (m/cycle) against the
stress intensity factor range dK (MPa sqrt(m)).

The laboratory keeps Kmax = dK / (1 - R) below 75 MPa sqrt(m), well under the specimens' toughness.

- `fcgr paris <R> [<heat>]`: a constant-amplitude test at R, ten points spaced evenly on a log scale from a top dK of
  45 MPa sqrt(m), or 75 (1 - R) where that is lower, down to a 3.75th of it: at R = 0.1 the test runs from 12 to
  45 MPa sqrt(m), at R = 0.8 from 4 to 15. Uses 1 test slot.
- `fcgr threshold <R> [<heat>]`: a K-decreasing test at R from dK of 14 MPa sqrt(m), or 75 (1 - R) where that is
  lower, down to the threshold, where the growth rate falls to 1e-10 m/cycle; the report also states that threshold.
  Uses 3 test slots.

The heat is H1, H2, H3 or H4; without one the specimen is from heat H1. Points where the crack grows slower than
1e-11 m/cycle are not reported.

The allowance for this assessment is 5 test slots in total; the laboratory refuses further tests once it is used.
Each report is also saved under /app/lab_reports.
