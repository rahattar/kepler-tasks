# engine-indicating-analysis

Write a program that reduces a test cell's cylinder pressure records to an indicating standard (gross indicated mean effective pressure, peak pressure and its angle, burn angles and gross heat released, from the first law for the closed charge with temperature-dependent properties and wall heat transfer), with the crank angle and the pressure scale of each indicating system settled from the thermodynamics of the compression stroke in its own records, and that finishes a session of up to 20,000 cycles within 4 seconds on one CPU on cells it has never seen.

## Difficulty

This is the work of a combustion engineer who keeps an engine group's indicating standard and the program that applies it. Indicating is how combustion in an engine is measured: a pressure transducer in each cylinder, an encoder on the crankshaft, and a calculation that turns pressure against crank angle into indicated work, peak pressure, burn angles and heat released. The task is a program that makes that calculation for a session of up to 20,000 cycles within 4 seconds on one CPU, to 2 per cent on mean effective pressure, 1 per cent on peak pressure, 3 per cent on heat released and 0.3 degrees on angles, at cells whose indicating systems are not all in the state their packages give. The cells, their records and the standard are synthetic and realistic: compression ratio 9.6 to 17.5 against 10.0 to 11.0, bore 74 to 130 against 76 to 86 mm, manifold pressure 0.38 to 2.51 against 0.42 to 1.62 bar, speed 800 to 5000 against 1200 to 4000 rpm, the first figure of each pair being the six cells the program is run on and the second the visible ones. Results at the six cells (250 rows): mean effective pressure 3.1 to 19.3 bar, peak pressure 21 to 141 bar at 3.7 to 12.9 degrees, 10 per cent burned at -18.7 to 4.8 and 50 per cent at -8.6 to 16.4 degrees, heat released 264 to 6645 J.

Four pieces of physics set every result.

- **Work.** The indicated work of a cycle is the integral of p dV over compression and expansion. The two strokes nearly cancel, and the volume changes fastest where the pressure is highest, so the result turns on where top dead centre is taken to be: at these cells one degree of crank angle moves the mean effective pressure by 4.4 to 11.8 per cent, and every angle by a degree.
- **Heat release.** For the closed charge the first law gives the heat released from pressure and volume alone, dQ = gamma/(gamma - 1) p dV + 1/(gamma - 1) V dp plus the heat passed to the walls. On the compression stroke the two terms are large and of opposite sign; combustion is what they leave over.
- **Properties.** The ratio of specific heats falls with temperature and with the burned fraction, and the burned fraction is the heat release itself, so each cycle is a fixed point.
- **Wall heat.** Hohenberg's coefficient goes as p^0.8 T^-0.4 V^-0.06 and the wall heat is part of every balance, including the one that says nothing is burning yet.

The fifth unknown is the indicating system, and it is a measurement problem. A record is not the pressure in the cylinder against the crank angle. It is counts against encoder pulses: the system's scale turns counts into pressure, and the system's angle for a pulse is the crank angle only if the encoder's mark sits on top dead centre. A package gives the scale and the angle of each sample as the system has them. The standard is written for the pressure in the cylinder and the crank angle of that cylinder.

Whether the two agree is in the records themselves, on the compression stroke, where the physics is known. Until the charge begins to burn, which at these cells is not before 25.4 degrees before top dead centre, the first law leaves nothing over: taken at the true angle and the true pressure, the heat release is nil at every sample from inlet valve closing on. An encoder mark off top dead centre and a transducer that gives more or less than the scale assumes each leave a heat release that is not nil, and each bends it its own way along the stroke:

- in the two example cells, the ones whose results the program's author has, both are exact;
- in pending cell_11 the mark is 1.57 degrees from top dead centre, and in pending cell_13 the transducer gives 1.063 of what the scale assumes; neither package has results;
- in five of the six cells the program is run on, the mark is 1.34 to 2.41 degrees out, or the transducer 4.2 to 7.1 per cent out, or both, of either sign.

The two are easily taken for each other. Once the level of a cycle is set at manifold pressure, a transducer that reads high steepens the compression line much as a late top dead centre does. Put down to the encoder alone, cell_13's transducer reads as a mark 1.551 degrees out, the same at every point and cylinder, and a program that corrects the angle alone agrees with both examples, is right at cell_11 and is out at every cell where the transducer is out, by 6.2 bands at the least. What tells them apart is the shape of what the first law leaves over along the stroke, not its size: an angle error acts through dV/V, which grows towards top dead centre, and a scale error through the rise of pressure above the manifold, which is proportional to the pressure itself. Nothing in a package says any of this in words.

The time limit is the other half of the work. A session of 20,000 cycles is 14 million samples, the heat release of every cycle has to be repeated until its burned fraction settles, and a run has 4 seconds on one CPU. Worked through cycle by cycle in plain loops, with the compression stroke simulated by an ODE solver to settle angle and scale, the calculation takes 0.0054 s a cycle, 12 to 24 times the limit for a cell. Inside the limit it has to be carried out for all the cycles of a point at once, and the angle and the scale settled once for a cell from the mean cycles of its points.

Its research analogue is the thermodynamic determination of top dead centre and of transducer sensitivity in combustion diagnostics: an inverse problem in which the parameters of the instrument are identified from the first law on the part of the cycle where the answer is known, and two instrument errors with nearly collinear signatures have to be separated before any result is taken from the record.

Each of these defeats an assumption the general approach makes on first reading:
- that a record is cylinder pressure against crank angle;
- that agreement with the two sessions whose results are on file shows a program right;
- that a compression line which does not close is a matter of top dead centre;
- that a few thousand cycles can be worked through one at a time.

## Reference solution

solution/indicate.py is the reference; solution/solve.sh puts it at /app/output/indicate.py. It reads one package and writes the table, in three steps.

1. **What the indicating system did to the pressure.** The mean cycle of every point and cylinder is taken over the samples from 12 degrees after inlet valve closing to 47 degrees before top dead centre, where no charge of these engines has begun to burn. For a trial index error of the encoder and a trial gain of the transducer, the gross heat release of IS-2 section 7 is summed along that stretch. The sum is weighted by 1/V, which makes it the size of a pressure error, a free level is taken out, and the squares are minimised over index and gain together by Gauss-Newton from the best point of a coarse grid. One index and one gain are found for a cell.
2. **IS-2 on every cycle.** Counts become pressure by the system's scale divided by the gain, each cycle's level is set at manifold pressure over its first ten degrees, and the crank angle of a sample is the system's angle plus the index error. For all the cycles of a point at once: the work by the trapezoidal rule, the peak by a least-squares parabola through the 21 samples round the highest, the heat release at the mid-points of the half-degree steps with Hohenberg's wall heat, repeated until no cycle's total changes by more than one part in a million, and the burn angles by linear interpolation where the burned fraction first reaches 0.1 and 0.5.
3. **The table.** The mean over the cycles of each point and cylinder, to four decimals.

**On the shipped cells** (authoring/evidence/reference_run.txt, run by the checker as the verifier runs it) the reference is accepted: 250 rows at six cells, the widest departure at any of them 0.37 of its band, runs of 0.9 to 1.3 s, so the limit of 4 s is 3.0 times the slowest run. It is accepted on both example cells as well. What it finds: cell_03 index error -0.045 degrees, transducer gain 1.0016; cell_08 index error 0.011 degrees, transducer gain 0.9997; pending cell_11 index error -1.633 degrees, transducer gain 1.0022; pending cell_13 index error 0.026 degrees, transducer gain 1.0621. The few hundredths of a degree and tenths of a per cent it finds where both are exact are the engines' own wall heat, which is within 10 per cent of Hohenberg's and not equal to it.

**authoring/evidence/slow_indicate.py** is a second solution, written apart from the reference and sharing no code with it or with the sealed definition. It simulates the compression stroke of each point with an ODE solver and fits index and gain to the mean cycles in pressure, then works through the cycles one at a time in plain loops. On the six cells made again by the generator with 75 cycles a point it is accepted, and its widest departure from the sealed results is 0.49 of a band (authoring/evidence/slow_run.txt).

`solution/solve.sh` starts it inside the agent's container: it copies indicate.py to /app/output and runs it once on the four packages in /app/data, comparing the two example cells with their results.

## Verification

The deliverable is a program, /app/output/indicate.py. The verifier reads nothing the agent's own runs left behind: tests/check_program.py, run by the one pytest test in tests/test_indicate.py, runs the program on six cell packages it has not seen and holds what each run writes to sealed results.

**A run.** For each cell a scratch directory gets a folder holding a copy of indicate.py alone and a read-only copy of the package. The program is started there as `python3 indicate.py PACKAGE_DIR OUT_CSV`, as the user nobody, on one CPU, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, as the leader of a session of its own, with no network.

**The limit.** Each run has 4 seconds from start to exit, the figure of the task statement's sentence "Each run of indicate.py must finish within 4 seconds on 1 CPU." (preflight compares the two). It is a timeout on the wait for the process, in tests/check_program.py. A run still going at 4 s ends the assessment: its session and every process of nobody are killed, the table it may have written is never opened, no later cell is run, and the program is not accepted. No share of cells or rows lets such a run through.

**Acceptance.** Every run must end in time with exit status 0, every OUT_CSV must be the table the statement describes, and for every point and cylinder of every cell the mean effective pressure must be within 2 per cent of the sealed result, the peak pressure within 1 per cent, the heat released within 3 per cent, and the angle of peak pressure and the two burn angles within 0.3 degrees. These are the figures of the statement and of IS-2 section 9. One pytest test carries the reward. tests/test.sh writes 0 first and writes 1 only when pytest ends with status 0 and tests/one_passed.py finds that the ctrf report counts exactly 1 test, passed.

**The reader** holds the table to the statement and no further. The header must be exactly the one given; there must be one row for every point and cylinder of the package and none for anything else; each value must be a finite decimal number. Row order, line ends, a final terminator, empty lines, quoting and blanks round a field are not stated and are not judged.

**The truth** is the sealed definition authoring/provenance/cylinder.py: `simulate` gives the pressure of every cycle from the closed charge's energy equation, and `results` applies IS-2 to that pressure at its true crank angle and true level, on a grid five times finer than a record. It never sees a record, an encoder or a transducer, and it is never a run of the reference. authoring/provenance/cells.py makes each cell's records from the same pressure, through that cell's encoder mark and transducer gain. authoring/provenance/regenerate.py makes the ten cells again and finds all 130 shipped data files the same byte for byte (authoring/evidence/regenerate.txt); authoring/provenance/manifest.json lists them with their SHA-256.

**The bands** are checked against a separately written solution. authoring/evidence/slow_indicate.py shares no code with the reference or the sealed definition and settles index and gain by another route (a simulated compression fitted in pressure); its widest departure from the sealed results is 0.49 of a band, so every band is at least 2.0 times the widest departure of an independent, correct method. The reference's widest is 0.37 of a band, and 5 sound variations of its method (another stretch of the stroke, another weighting, half the cycles, a looser repeat of the burned fraction) are all accepted, the widest at 0.44 of a band. On 20 other seeds of everything random, with 40 cycles a point in place of 300, the reference is accepted every time (authoring/evidence/seed_screen.txt; widest 0.82 of a band). A correct standard method is accepted with room to spare; nothing depends on matching the reference's stretch, weighting or arithmetic.

**What the six cells are, and how they differ from the visible data.** They are six other cells, none of them a visible one and none sharing a file with one. The difference is built in on purpose and is not a new seed of the visible cells:
- at the two example cells, whose results the agent has, the encoder mark is on top dead centre and the scale is the transducer's, exactly;
- at five of the six cells the mark is 1.34 to 2.41 degrees out, or the transducer 4.2 to 7.1 per cent out, or both, of either sign; the sixth is exact;
- both conditions are present in the visible data, one each, in the two pending packages without results: cell_11 (the mark, -1.57 degrees) and cell_13 (the transducer, 1.063);
- the engines are other engines: compression ratio 9.6 to 17.5 against 10.0 to 11.0, bore 74 to 130 against 76 to 86 mm, manifold pressure 0.38 to 2.51 against 0.42 to 1.62 bar, speed 800 to 5000 against 1200 to 4000 rpm; three of the six are compression-ignition engines and every visible one is spark-ignited.
It is built in authoring/provenance/cells.py: the `CELLS` table gives each cell's role, engine, `index_deg` and `gain`, and `build` makes the records from them.

authoring/provenance/design_rules.py recomputes the design rules from the generator's table and the shipped files (authoring/evidence/design_rules.txt; 21 of 21 hold):
- 10 cells: 2 with their results beside them, 2 without results, 6 the program is run on; no name twice;
- cell_03 carries expected.csv;
- cell_08 carries expected.csv;
- cell_11 carries no results;
- cell_13 carries no results;
- no file of a cell the program is run on is a file of a visible cell (0 shared);
- cycles in a package: 6000 to 6000 in the examples, 12000 to 18000 in the pending packages, 9000 to 18000 where the program is run; the stated most is 20,000, and 6 cylinders;
- the largest package the program is run on (18000 cycles) is no larger than the largest visible one (18000 cycles);
- in the two examples the index mark is on top dead centre and the scale is the transducer's, exactly;
- pending cell_11: the index is -1.57 degrees out and the scale is right;
- pending cell_13: the index is right and the transducer gives 1.063 of what the scale assumes;
- the six cells: 1 exact (cell_12), 1 with the index out (cell_02), 2 with the gain out (cell_05, cell_14), 2 with both (cell_06, cell_09);
- where it is out, the index is 1.34 to 2.41 degrees out, of either sign, and the gain 4.2 to 7.1 per cent, of either sign;
- both signs of each occur among the six, and the visible instances have one sign of each (-1.57 degrees, gain 1.063);
- each engine's wall heat is 0.93 to 1.07 of Hohenberg's with IS-2's constants; IS-2 says within 10 per cent;
- the engines the program is run on reach past the visible ones: compression ratio 9.6 to 17.5 against 10.0 to 11.0, bore 74 to 130 against 76 to 86 mm, manifold pressure 0.38 to 2.51 against 0.42 to 1.62 bar, speed 800 to 5000 against 1200 to 4000 rpm;
- 3 of the six are compression-ignition engines; every visible engine is spark-ignited;
- every engine and operating point of every package is within the scope of IS-2 section 1;
- results at the six cells (250 rows): mean effective pressure 3.1 to 19.3 bar, peak pressure 21 to 141 bar at 3.7 to 12.9 degrees, 10 per cent burned at -18.7 to 4.8 and 50 per cent at -8.6 to 16.4 degrees, heat released 264 to 6645 J;
- at the six cells a degree of index error moves the mean effective pressure by 4.4 to 11.8 per cent, and every angle by a degree; a gain error moves every pressure, the work and the heat by its own share;
- at its true index and gain, no mean cycle of any cell has released 1 per cent of its heat before -25.4 degrees; the compression stroke is free of combustion to 40 degrees before top dead centre.

Every study below runs complete programs through tests/check_program.py as the verifier does: as nobody, on one CPU, each run in a directory of its own.

**A correct program that is not fast** (slow_run.txt). The second solution is accepted on the cells with 75 cycles a point, where the limit is set aside, at 0.0054 s a cycle (18750 cycles in 102 s). At that rate the shipped cells, of 9000 to 18000 cycles, would take 49 to 98 s a run, 12 to 24 times the limit. Run on them at the limit, it is stopped on the first cell: cells run 1 of 6, the run on cell_02 was still going after 4 s, not accepted.

**Programs that stop short** (route_run.txt; each is the reference with one change, made by authoring/evidence/variants.py):

| program | the two example cells | cells with rows out of band | its widest departure at the cell it misses least, in bands |
|---|---|---|---|
| IS-2 on the indicating system's angles and scale; nothing is settled from the records | accepted | 5 of 6 | 5.2 |
| the misfit on the compression stroke is put down to the encoder's index, whatever its shape | accepted | 4 of 6 | 6.2 |
| the misfit on the compression stroke is put down to the transducer's gain, whatever its shape | accepted | 3 of 6 | 6.4 |
| index and gain are fitted to an adiabatic compression | not accepted | 6 of 6 | 4.5 |
| index and gain are fitted with gamma fixed at 1.35 on the compression stroke | not accepted | 6 of 6 | 4.3 |

How many of these routes each cell stops: cell_02 (index +2.23 degrees) 4 of 5; cell_05 (gain 0.95) 4 of 5; cell_06 (index +1.34 degrees, gain 1.05) 5 of 5; cell_09 (index -2.41 degrees, gain 0.96) 5 of 5; cell_12 (index and gain exact) 2 of 5; cell_14 (gain 1.07) 4 of 5. Where only the transducer is out, the program that corrects the angle alone reports an index error of 1.551 degrees at cell_13, -1.173 degrees at cell_05, 1.475 degrees at cell_14.

**Programs with no physics** (null_run.txt). A table of the examples' mean results and a table of the nearest example point's results get 0 of 250 rows right.

**The verifier itself** (verifier_checks.txt, 70 cases, none unexpected; every program is built at run time round the sealed results of a cell made with 4 cycles a point).
- Tables refused: nothing written, a directory or a symbolic link to the true table where the table belongs, an empty file, the header alone, no header, a misspelt, padded or quoted header, a column added or left out, a row of seven fields, a row left out, given twice, for an unknown point or with the point in lower case, cylinder 0 or 1.0, a value empty, n/a, nan, inf, with its unit, with a decimal comma, with a digit separator or in hexadecimal, bytes that are not text, a file over the size cap, and the true table followed by exit status 3.
- Tables accepted: the true table with CRLF line ends, no final terminator, empty lines, the rows reversed, padded or quoted fields, plus signs, exponent form, ten decimals, and cylinders written 01, 02, 03.
- Bands: each quantity moved by 0.9 of its band at every row is accepted and by 1.1 is not; one row of one cell with its mean effective pressure 3 per cent high is enough to refuse the program.
- The limit, set to 2 s for the purpose: a program that writes the true table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; with two cells to run the second is never started; a program that exits in time and leaves a child running in a session of its own is accepted and the child is killed.
- A run: its directory holds indicate.py and nothing else; it is the user nobody; it cannot list a directory of root's; it cannot write to the package; it has one CPU and one thread to a library.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest ends 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, a failing exit with a passing report, no report, a report that is not JSON, and no indicate.py delivered.

**The whole verifier** (verifier_run.txt). pytest on tests/test_indicate.py in a process of its own ends 0 for the reference and 1 for the program that takes the records as the system has them, for the program that corrects the angle alone and for the second solution at the limit. On the machine the evidence was made on pytest-json-ctrf was not installed, so the report there was written by authoring/evidence/ctrf_standin.py, which writes the same summary block; the verifier's image installs the plugin itself.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned. The verifier runs in a separate container without network; /tests and /logs/verifier are readable by root alone, and the program runs there as nobody.

Evidence (`authoring/evidence/`): `reference_run.txt`, `slow_run.txt`, `route_run.txt`, `null_run.txt`, `seed_screen.txt`,
`verifier_checks.txt`, `verifier_run.txt`, `design_rules.txt`, `regenerate.txt` and `preflight.txt`.

## Submission notes

What the shift in the hidden data is. The visible results (two example cells) come from cells whose indicating systems are exact: the encoder mark on top dead centre and the scale the transducer's. At five of the six hidden cells the mark is 1.34 to 2.41 degrees out, or the transducer 4.2 to 7.1 per cent out, or both, of either sign, so results calculated from the records as the system has them are out on every row of those cells. Both conditions show in the visible data, one each, in the two pending packages without results (cell_11, cell_13). The hidden engines are also other engines: three compression-ignition engines among them, compression ratios to 17.5 against 11.0, manifold pressures to 2.5 bar against 1.6. No visible cell is a hidden cell and no file is shared.

Where it is built.
- Generator config: authoring/provenance/cells.py, the `CELLS` table (role, engine, `index_deg`, `gain`, seed) and `build`.
- Manifest: authoring/provenance/manifest.json, the same facts for each cell and the SHA-256 of every data file.
- Data files: tests/cells/ (the six packages), tests/sealed/results/ (their results); environment/data/examples/ and environment/data/pending/ (the visible packages).
- Check: authoring/provenance/design_rules.py and authoring/evidence/design_rules.txt.

The timed re-run.
- The tests run the program: tests/check_program.py, `run_once`.
- The limit: `RUN_LIMIT_S = 4` in tests/check_program.py, and "Each run of indicate.py must finish within 4 seconds on 1 CPU." in instruction.md; preflight fails if they differ.
- The reference takes 0.9 to 1.3 s a run; the limit is 3.0 times the slowest.
- A correct program that is not fast times out: authoring/evidence/slow_indicate.py, authoring/evidence/slow_run.txt.
- A run over the limit ends the assessment and nothing it wrote is read: authoring/evidence/verifier_checks.txt, "The limit".
- Threads: OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in the environment of each run, which is also held to one CPU.
