# vibration-route-diagnosis

A plant wants a program that gives a first-pass diagnosis of every machine on a monthly vibration route. The solver
gets the condition codes, the route package format and one example route package (route U-2, 12 machines, with the
analyst's report), and delivers `/app/output/diagnose.py`, which is run on six hidden route packages (60 machines)
and must diagnose at least 58 of them correctly, condition code and component.

## Difficulty

A vibration analyst, or the reliability engineer who runs a plant's route-based condition monitoring, does this when the plant wants a first-pass diagnosis that it can trust on routes nobody has looked at yet. Each month a technician walks a route with a portable collector; the program has to say, for every machine, which developing fault it has (or none) and in which component, from raw accelerometer captures, tach pulses, the machine register, bearing geometry and the maintenance log. The machines, routes and signals are synthetic, written by authoring/provenance from a sealed definition.

The core difficulty is that diagnosing the example route by eye is not the job. The program must get the physics right for machines it has not seen, and it must check the data before it trusts it, because the collector stores what it acquired without checking it:
- Speed. Every frequency in a diagnosis is an order of the running speed, and the speed has to be established, not assumed: a tach with a second bright mark gives two pulses per turn; a fan on a VFD runs at whatever speed its loop sets; a belt-driven fan's bearings and rotor turn at the sheave ratio, not at motor speed.
- Frequency resolution. A two-pole motor's twice-line-frequency line (stator) and twice running speed (misalignment) are a fraction of a hertz apart, and so are a pump's own 1x and the 1x of the unbalanced pump beside it on the same skid, which is not the healthy pump's condition. Rotor bars show only as pole-pass sidebands about 1 Hz from 1x.
- Records. A bearing replaced with a different design changes every defect frequency; the register still shows the old one, and only the maintenance log tells.
- Data that the collector did not check. A high-rate capture taken at another sample rate than the route planned shifts every bearing and gear line by the same factor; two points' files can be crossed over, which moves a bearing or unbalance diagnosis to the wrong component; a cable fault leaves a low-frequency wander in one channel. The analyst recognises each from the data itself (running-speed lines in the wrong place, the vane-pass and electrical lines in the wrong file, energy below any machine line).
- Fault physics in general: bearing defect frequencies from geometry, inner-race modulation, ball-spin sidebands at the cage rate, gear-mesh sidebands at the pinion or the gear speed, looseness half orders, belt frequencies, resonance confirmed by an impact test in one direction only, cavitation as random impacts with the NPSH margin gone.

The example route shows some of these situations and none of the data faults. The hidden routes have all of them, 60 machines on six routes. Each of the speed, sample-rate, crossed-point, records and neighbour checks left out misdiagnoses 3 or 4 hidden machines (authoring/evidence/route_study.txt) against an allowance of 2.

## Reference solution

solution/diagnose.py is the reference program; solution/solve.sh installs it as /app/output/diagnose.py and runs it on the example route. For each machine in the route's register it does the following.

Data checks:
- Speed: from the tach, with the pulses per turn set so that a motor runs just below synchronous speed (two bright marks give twice the pulse rate); without a tach, from the 1x line just below synchronous speed; on a VFD, from the motor line whose 2 x drive-frequency line sits a few percent of slip above it, with the fan line at the sheave ratio.
- Crossed points: if the other file carries the motor's 2 x drive-frequency line at more than three times the level in the file labelled MOT, and the MOT file carries the stronger driven-machine lines (vane, lobe, fan or mesh), the two are swapped back.
- Channel: a channel whose velocity spectrum below 4 Hz has a median above 0.5 mm/s (no machine line is there) is a sensor or cable fault and is not used.
- High-rate capture: its true sample rate is the candidate (planned, 0.8, 0.5, 0.625, 0.4 times) at which its 1x, 2x and 3x lines stand out where the low capture puts them.
- Bearings: as in the register unless the maintenance log records a replacement with another designation.

Diagnosis, in this order, on velocity spectra (Hann window, the full 16 s, 0.0625 Hz lines) read at exact orders of each shaft's own speed:
- ELECTRICAL: 2 x drive frequency at the motor above 2.5 mm/s and resolved from 2x running speed.
- ROTOR_BAR: both pole-pass sidebands of 1x above 0.45 mm/s and 4x the local floor.
- BELT: belt frequency, 2x or 3x above 1 mm/s (belt drives).
- LOOSENESS: a half order (0.5x, 1.5x, 2.5x) 5x above the local floor and above 0.5 mm/s; component from the point.
- MISALIGNMENT: 2x above 2.5 mm/s across a coupling.
- GEAR_TOOTH: mesh sidebands, gear or pinion from whichever spacing is stronger.
- BEARING_*: envelope spectrum (1.5-7 kHz) of the high capture at its true rate, with lines at a defect frequency and its second harmonic 8x and 4x the floor (ball spin taken at twice BSF); component from the point.
- CAVITATION: NPSH available below required and a kurtosis above 4 at the pump.
- RESONANCE or UNBALANCE: 1x above 3.5 mm/s; resonance when the impact test puts the natural frequency within 8 percent of 1x and the other direction is less than a third, else unbalance at the point with the larger 1x.
- Otherwise NONE.

On the 60 hidden machines it is right on all 60, and on the example route on all 12.

`solution/solve.sh` installs `diagnose.py` and runs it on the example route (a few seconds).

## Verification

tests/grade_routes.py runs the submitted /app/output/diagnose.py on each of six hidden route packages (tests/hidden; the agent's image does not contain them).

The verifier image has the agent's /app/data at the same path and read-only (tests/app_data, a copy that authoring/provenance/build.py writes). A program that reads the documents or the example at run time therefore behaves as it did in development.

How each route is run:
- diagnose.py alone and the route package are copied to a scratch directory.
- It runs as the unprivileged user nobody, with only PATH and HOME set, as `python3 -I diagnose.py ROUTE OUT.csv`, within 300 seconds; the six runs are sequential, so the worst case (1800 s) fits the 3600 s verifier timeout. The instruction states these run conditions, including that diagnose.py must be self-contained.
- The sealed diagnoses (tests/hidden/truth.json) stay in /tests, which only root can read.

A machine counts as right when its row has the sealed condition code and component (case and surrounding spaces ignored); a missing row, and every machine of a route on which the program fails, counts as wrong. The single pytest test passes when at most 2 of the 60 hidden machines are wrong. Per-route results go to /logs/verifier/metrics.json and do not affect the reward.

The hidden routes hold 60 machines of five kinds (end-suction pumps with two- and four-pole motors, cooling tower fans with right-angle gearboxes, belt-driven fans, some on VFDs, screw compressors and vertical turbine pumps) with every condition code. They include, by design:
- six machines whose high-rate captures were taken at another sample rate than the route file states;
- five machines whose two points' files are crossed over;
- five machines whose tach sees two marks per turn;
- five channels with a cable fault;
- three healthy pumps beside an unbalanced pump on the same skid;
- four bearings replaced with another designation, logged 3 to 40 days before the survey (every maintenance log entry predates its survey, as route_package.md states);
- six belt-driven fans on VFDs.

A vertical pump coded NONE or UNBALANCE has no natural frequency, in either direction, within 25 percent of 1x or 2x; the two coded RESONANCE have one within 4 percent of 1x in the x direction.

Why at most 2 wrong:
- Correct side: authoring/evidence/independent_diagnose.py, a second program sharing no code with the reference (scipy filters and Hilbert envelope, flat-top window with zero padding, tach marks from the interval pattern, the sample-rate check by line positions, a Welch-based channel check, crossed points from the electrical line alone, and a score for every code instead of an ordered rule list), misdiagnoses none of the 60 (independent.txt). Other sound thresholds and settings leave the reference at 0 (method_spread.txt).
- Wrong side: leaving out any one of the speed, sample-rate, crossed-point, records, sheave-ratio or neighbour steps misdiagnoses 3 or 4 hidden machines (route_study.txt). The channel check costs nothing on these routes: the reference reads lines against their local floor, which a cable fault's low-frequency wander does not reach; it stays in the reference as practice.

A program that reports every machine NONE misdiagnoses 51 of 60, and one that copies the example's diagnosis by machine kind 49 (constant_null.txt).

The agent works as a separate user that can only write to /app/output; /app/data is read-only. The verifier runs separately without network, and /logs/verifier is root-only.

Files in `authoring/evidence/`: `common.py` (grades a program text with the verifier's own grade_routes),
`route_study.py` (each check or step left out), `method_spread.py` (other sound settings), `independent_diagnose.py`
and `independent.py` (a second program sharing no code with the reference), `constant_null.py`, their `.txt`
outputs, and `preflight.py` (structure, names, ASCII, sealed diagnoses against the definition, byte-exact
regeneration by `authoring/provenance/build.py`). `authoring/provenance/` holds the sealed signal synthesis
(`sim2.py`), the machine cases and route writer (`gen2.py`), the public documents (`docs/`) and `build.py`.
