# FP-7: Hydraulic re-rating of existing wet-pipe sprinkler systems

Site fire protection standard, revision 5. It applies when an existing wet-pipe sprinkler system is re-rated for
a new hazard: the system's demand at the base of its riser is worked out for the system as it stands, from the
flow-test campaign run on it before re-rating.

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

## 3. Pipe condition and valves

Each pipe belongs to a group of the package (pipe installed at one time, for one service), and the pipe of a
group shares one C. The package gives a group's C from the site's pipe register where the register has one.
Unlined steel pipe is C 120 when new and loses C as it ages in service; on this site it has been found from
C 55 to C 120.

A gate valve or a butterfly valve that is not fully open adds loss: its equivalent length is its table 2 figure
times a factor f, with f = 1 for the valve fully open and f greater than 1, up to 1000, as it closes. A check
valve is always at its table 2 figure.

A system is rated as it stands on the day of its re-rating campaign (section 6): with the C its pipe has that
day and with every valve as it stands that day. Defects a campaign brings to light are put right under a
separate work order and the system is re-rated afterwards; they are not assumed away in the rating.

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

## 6. The re-rating campaign

Before a system is re-rated a campaign of flow tests is run on it, with every sprinkler shut. In each run water
is drawn at one of the system's test outlets at a steady flow, set and measured on a meter in the outlet's
discharge, and the pressure is read at the base of the riser and at every gauge port. A campaign opens and
closes with a static run, read with no water drawn. The supply gives the base of the riser whatever pressure it
has at the time, and that pressure moves from run to run.

The gauges are digital test gauges read to 0.1 psi; a gauge's readings scatter by about 0.1 psi. The readings
and the flows are entered on the campaign sheet by hand, each reading against the tag of its port.

The package's `campaign.csv` is the campaign sheet.

## 7. Results

- **pressure_psi**: the pressure at the base of the riser for the most demanding area.
- **flow_gpm**: the sprinklers' flow at that pressure, plus the inside hose allowance.
