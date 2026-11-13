# FP-7: Hydraulic re-rating of existing wet-pipe sprinkler systems

Site fire protection standard, revision 4. It applies when an existing wet-pipe sprinkler system is re-rated for
a new hazard: the system's demand at the base of its riser is worked out from the system as it stands on the
day of the field test, with the pipe whose condition is not known established by one field flow test on the
system.

## 1. Scope

A system is one riser feeding one network: a feed main to cross main A, branch lines off cross main A, and, in a
gridded system, a cross main B joining the far ends of the branch lines. Every system has a single source, the
base of its riser. The hazard sets a design density (gpm/ft2) over a design area (ft2), applied to the
sprinklers of that area alone, and an inside hose allowance (gpm).

The results are the pressure the system needs at the base of its riser to supply the most demanding design area
(section 5), and the flow there.

## 2. Friction loss

Each pipe's friction loss is by Hazen-Williams:

    p_f = 4.52 Q^1.85 / (C^1.85 d^4.87)        psi per ft of pipe

with Q the flow in gpm, d the internal diameter in inches (table 1, by nominal size and schedule) and C the
pipe's Hazen-Williams coefficient (section 3). The length a pipe's loss is taken over is its length plus the
equivalent length of each of its fittings (table 2). Table 2 is for C = 120: for a pipe of another C, each
fitting's equivalent length is multiplied by (C/120)^1.85. Flow may run either way in any pipe of a gridded
system; the loss is always against the flow.

Table 1. Internal diameter, in.

| nominal | sch 40 | sch 10 |
|---|---|---|
| 1 | 1.049 | 1.097 |
| 1-1/4 | 1.380 | 1.442 |
| 1-1/2 | 1.610 | 1.682 |
| 2 | 2.067 | 2.157 |
| 2-1/2 | 2.469 | 2.635 |
| 3 | 3.068 | 3.260 |
| 4 | 4.026 | 4.260 |
| 6 | 6.065 | 6.357 |
| 8 | 7.981 | 8.249 |

Table 2. Equivalent length of fittings, ft of pipe, for C = 120.

| fitting | 1 | 1-1/4 | 1-1/2 | 2 | 2-1/2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| elbow | 2 | 3 | 4 | 5 | 6 | 7 | 10 | 14 | 18 |
| tee | 5 | 6 | 8 | 10 | 12 | 15 | 20 | 30 | 35 |
| gate valve | | | | 1 | 1 | 1 | 2 | 3 | 4 |
| butterfly valve | | | | 6 | 7 | 10 | 12 | 10 | 12 |
| check valve | | | | 11 | 14 | 16 | 22 | 32 | 45 |

A fitting is listed on the pipe whose loss it adds to, once.

## 3. Pipe condition

Each pipe belongs to a group of the package (pipe installed at one time, for one service); pipe of a group
shares one C. Pipe ages in service, at a rate that differs from one pipe to the next, and a coefficient is the
pipe's at the date it was found: the register's is the figure entered for the group when its pipe was
installed, and a flow test's is the pipe on the day of that test.

A group the register carries no C for has aged by an amount the records do not settle. Pipe whose condition
today the records do not settle is established by the field test (section 6). Aged unlined steel in this
site's service has been found from C 55 to C 120.

A valve listed as not verified open may be partly closed. Its equivalent length is then its table 2 figure times
a factor f, from f = 1 (fully open) to f = 1000. The factor is established by the field test. Every other valve is
open, f = 1.

## 4. Sprinklers and elevation

An open sprinkler discharges q = K sqrt(p), with K its K-factor (gpm/psi^0.5) and p the pressure at it, psi. Each
sprinkler of the design area must discharge at least the density times its coverage (its spacing along the branch
line times the spacing between lines), and its pressure must be at least 7 psi. Every sprinkler outside the
design area is closed.

Elevation counts at 0.433 psi per ft: the pressure at a point higher than another by h ft, with no flow between
them, is lower by 0.433 h.

## 5. The design area

The design area holds n = ceil(A / s) sprinklers, with A the design area and s the coverage of one sprinkler. It
lies across adjacent branch lines, with m = ceil(1.2 sqrt(A) / S) sprinklers on each line, S the spacing along
the branch line (m no more than the shortest line holds), on k = ceil(n / m) lines. Every line of the area has its
sprinklers on the same columns, except the line with the highest number, which holds the remainder,
n - m(k - 1), on the area's lowest-numbered columns. Lines are numbered from the riser end of cross main A, and
columns from the cross main A end of each line.

An area may be placed on any k adjacent lines and any m adjacent columns. The most demanding area is the
placement that needs the highest pressure at the base of the riser, with every sprinkler of it meeting section 4,
the most heavily loaded of them exactly.

## 6. The field test

One flow test is made on each system before it is re-rated. Water is drawn at one of the system's test outlets,
at a flow the test sets, and the pressure is read, static (before the flow) and flowing, at the base of the riser
and at two of the system's gauge ports chosen for the test. The base of the riser is supplied along the supply
curve of the package: at a flow Q the pressure there is

    p = p_static - (p_static - p_residual) (Q / Q_residual)^1.85

The test is not made, and counts as made, if the flow would draw the base of the riser below 20 psi, or if the
outlet cannot pass the flow at the pressure the system gives it: an outlet passes at most K sqrt(p), with p the
pressure at it while it flows. The gauges are digital test gauges read to 0.1 psi; each reading scatters by about
0.1 psi about the true pressure.

The groups' C and the valves' factors are those that reproduce the test's readings.

## 7. Results

- **pressure_psi**: the pressure at the base of the riser for the most demanding area.
- **flow_gpm**: the sprinklers' flow at that pressure, plus the inside hose allowance.
