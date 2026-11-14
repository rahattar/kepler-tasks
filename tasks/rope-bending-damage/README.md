# rope-bending-damage

Write a program that reckons the bending fatigue damage along the hoist ropes of a works' overhead cranes to a company standard (reeving geometry, rope tension, a Feyrer-type bending endurance and Miner's sum for each piece of rope), with each rope's history settled from its own diameter surveys, where a rope turned end for end on the crane and a survey written down from the other end look alike, and that finishes a works of up to 600,000 movements within 4 seconds on one CPU at works it has never seen.

## Difficulty

This is the work of a lifting-equipment engineer who keeps a steel company's rope standard and the program that applies it to the cranes of every works. A hoist rope wears out by bending. Each time a sheave's point of touch passes along a piece of rope, that piece is bent once over the sheave, and a rope is discarded when some piece of it has used up its bending endurance. The task is a program that reckons, metre by metre along every crane's rope, how much of that endurance has gone, from the hoist controller's log of movements and the rope's diameter surveys. The works, their logs and their surveys are synthetic and realistic: cranes of 4 to 8 falls with the upper block at 12.9 to 41.5 m, ropes of 74 to 362 m, logs of about 75,000 to 102,000 movements a crane over 300 days, and twenty surveys of each rope.

Three pieces of physics set every result.

- **Where a bending falls.** With the hook at height h, a sheave with p falls between it and the dead end touches the rope at a + p (H - h) from the dead end. A movement sweeps that point along the rope, so each movement bends a run of neighbouring stations over every sheave and over the drum, and places a few metres apart along the rope have very different histories: the damage piles up where the touch points dwell at the top of the lift and at the set-down heights.
- **How much a bending takes.** The endurance has Feyrer's form, lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d). At the ratios D/d of these cranes, doubling the tension divides the endurance by four to five, and the diameter d of the piece of rope enters both the specific tension S/d^2 and the ratio D/d, so a rope that has thinned bends with less endurance.
- **Whose damage it is.** Miner's sum belongs to a piece of rope, not to a place on the crane. When the rope moves, its history moves with it.

The fourth unknown is each rope's own history, and it is a measurement problem. Nothing in a works' records says what was done to a rope between two surveys. Two things are done in practice, and both are in these records:

- a rope is turned end for end, the usual way to bring its less worn end to where the bendings fall: from that day the piece of rope that lies x from the drum anchorage lay L - x from it before, and was bent there;
- a survey is taken from the dead end and written down as if from the drum anchorage: the rope has not moved, but the sheet gives its diameters in the opposite order.

Each shows in the surveys alone, and in the same way: from one survey to the next, the profile of diameters along the rope is mirrored. Across such a survey some station's diameter rises by at least 0.32 mm, against 0.05 mm at most between any two other surveys of any rope.

- in the two example works, the ones whose results the program's author has, neither happened;
- in the pending works melt_hall, which has no results, rope MH-1 was turned on day 138.08 and rope MH-5 was surveyed from the dead end from day 175.30 on;
- in five of the six works the program is run on, five ropes were turned, six were surveyed from the dead end, and one was first surveyed from the dead end and later turned.

The mirrored survey cannot tell the two apart; the physics can. Bendings fall where the reeving puts them, whichever way round the rope lies. After a turn the rope goes on thinning at the places where the log puts its bendings, station by station as the sheets are written; after a survey from the dead end it goes on thinning at the mirrored places. The two readings lead far apart. A turned rope read as never turned has at least 66 of its stations out by more than the accuracy asked; a rope surveyed from the dead end read as turned has at least 62 out; the mean of the two readings still leaves at least 44 out. When the turn happened within its gap of 12.8 to 17.9 days between two surveys does not decide a result: put at either edge of the gap, no station of any turned rope moves by more than 0.70 of the accuracy.

The time limit is the other half of the work. A works is up to 600,000 movements on six cranes, with ropes of up to 362 m surveyed every metre, and a run has 4 seconds on one CPU. Every movement bends a run of stations over every sheave of its crane. Counted as RS-4 words it, movement by movement in plain loops, a works takes 85 to 90 s. Vectorised but still holding every movement against every station in numpy arrays, it takes 6.9 to 16.1 s. Inside the limit the count has to become a sweep: for one sheave the stations a movement bends are a contiguous run, found by bisection at both ends, so a difference array and a running sum give every station's total at once. The diameter differs from station to station and with it the exponent of the endurance, so the tension's power has to be carried through the sweep by an expansion or an interpolation rather than by a sum for each station.

Its research analogue is the reconstruction of a running rope's service history from its nondestructive inspection records, as condition-based rope management needs it: an inverse problem in which interventions that leave the same trace in the inspection data (a reversal of the rope, a survey referenced to the other end) are separated by the forward model of where the duty falls, before a usage-based damage model is applied to the rope as it really ran.

Each of these defeats an assumption the general approach makes on first reading:
- that the damage at a station of the survey sheet is the damage of the rope at that place;
- that agreement with the two works whose results are on file shows a program right;
- that a mirrored survey means one thing;
- that half a million movements can be held against every station of every rope.

## Reference solution

solution/ropes.py is the reference; solution/solve.sh puts it at /app/output/ropes.py. It reads one package and writes the sheet, in three steps for each crane.

1. **Where each piece of rope lay.** Each survey is laid against the one before it twice, as written and end for end. Where the squared difference end for end is less than half of what it is as written, the pattern of wear has changed ends between the two surveys.
2. **What changed ends.** The surveys between two such changes form a run. For each run, the loss of diameter from its first survey to its last is correlated with the bendings the log lays in the same days, reckoned with the rope as new, once as the stations are written and once end for end. A run whose loss follows the bendings end for end was written from the dead end, and its stations are read from that end. A change with the same reading on both sides of it is a turn of the rope: the elements are followed to where they lay before it, and the turn is taken half way through its gap.
3. **RS-4.** For each stretch of the log between two surveys and each sheave and the drum, the bendings are counted by a sweep. The hook height at which the sheave meets each station is sorted, each movement's run of stations is found by bisection at its two heights, and each movement adds its share to a difference array whose running sum is every station's total. The share is w / N with N = 10^c S^q, c and q set by the station's diameter at the last survey not later than the movement: S^-q is written as S^-q0 exp(-(q - q0) ln S) about the mean exponent q0 and the second factor as five terms of a power series, so each station takes five running sums whatever its diameter.

**On the shipped works** (authoring/evidence/reference_run.txt, run through the verifier's bench) the reference is accepted at all six, with every station within 0.15 of its band, in runs of 1.2 to 1.4 s, so the limit of 4 s is 2.9 times the slowest. It is accepted on the three visible works too: exactly on the two examples, and within 0.27 of a band on melt_hall, where the day of MH-1's turn is the only thing it cannot know.

**Second solution.** authoring/evidence/plain_ropes.py was written apart from the reference and shares no code with it or with the sealed definition. It settles a rope by another statistic (absolute differences for the mirror, the part of the wear that is not alike from both ends for the end a run was counted from) and counts the bendings movement by movement in plain loops, exactly as RS-4 words it. authoring/evidence/quick_ropes.py is the same program with its counting made fast another way, by running sums over the movements sorted by their lower and their upper heights, joined across five values of the endurance exponent by Lagrange's formula. quick_ropes.py is accepted at all six works within 0.15 of a band, in 0.8 s a run.

`solution/solve.sh` starts by copying the reference to /app/output/ropes.py, then runs it on the three works under /app/data from an empty directory, the way it will be run, and lays the sheet of each example against its expected.csv rope by rope.

## Verification

The deliverable is a program, /app/output/ropes.py. The verifier reads nothing the agent's own runs left behind: tests/rope_bench.py, called by the one pytest test in tests/test_ropes.py, runs the program on six works it has not seen and holds each sheet the program writes against sealed results.

**A run.** For each works the bench makes a fresh directory with a copy of ropes.py alone, a read-only copy of the package and an empty folder for OUT_CSV, every mode set outright (test.sh works under umask 077). The program is started there as `python3 ropes.py WORKS_DIR OUT_CSV`, as the user nobody, in a session of its own, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 and no network. No CPU affinity is set.

**The limit.** The statement's sentence is "Each run of ropes.py must finish within 4 seconds on 1 CPU.", and the bench's LIMIT_S is 4 (preflight compares the two). The bench holds it twice: a run is over when 4 seconds have gone by on the clock since it started, and also when the CPU time, user and system, of the program and of every process it has started reaches 4 seconds, read from /proc while it runs and from the kernel's own count (wait4) when it ends. On one CPU the two come to the same; work spread over several processes meets the second first. A run that is over ends the judging: its processes are killed, its sheet is never opened, the works after it are not tried, and the program is not accepted. Nothing catches the end of a run and carries on.

**Acceptance.** Every run must end inside the limit with exit status 0, every OUT_CSV must read as the sheet the statement describes, and at every station of every crane of the six works the damage must be within 0.08 of the greatest sealed damage of that rope, the statement's 8 per cent. There is no share of rows, ropes or works that lets a miss through.

**The reader** holds the sheet to what the statement says and no further: an ordinary file, not a link, of at most 1 MiB; the header exactly `row,damage`; one row for every station of the works and none for anything else; each damage a finite decimal number. Row order, line ends, a final line end, empty lines, quoting and blanks round a field, and the number of digits are not judged.

**The truth** is the sealed definition authoring/provenance/rope.py. `life` follows every piece of rope through a crane's true log as material: an element that lies x from the drum anchorage at the end lay L - x from it before the day its rope was turned, and was bent there; every bending is counted at the tension of its movement, with the diameter the element had at the last survey. Its diameters at each survey come from a wear law of the damage the element has taken, with constants of the rope's own and a gain that varies element by element, read with the gauge's scatter. It never reads a package or a survey sheet and is never a run of the reference. authoring/provenance/works.py writes the packages from it: the log as the controller writes it, each survey as the surveyor wrote it down, from the dead end where that was so.

**The band** is checked against separately written solutions and against sound variations of the reference. The second solution's widest departure from the sealed results is 0.15 of a band, so the band is 6.7 times it. Eight sound variations of the reference (the turn put a third or two thirds into its gap; the mirror judged by correlation or by a stricter ratio; the bendings that settle the end reckoned with the first survey's diameters; the diameter read at the station as written; the diameter as new in every bending; more terms of the series) are accepted everywhere, the widest at 0.48 of a band, so the band is 2.1 times the widest sound departure. A turn put at the very first or very last moment of its gap is accepted too. On twenty other draws of the six works (seed_screen.txt) the reference is accepted on every one.

**What the six works are, and how they differ from the visible data.** They are six other works, none of them a visible one and none sharing a file with one. The difference is built in on purpose and is not a new seed of the visible works:
- at the two example works, whose results the agent has, no rope was turned and every survey was written from the drum anchorage;
- both conditions are present in the visible data, one rope each, in the pending works melt_hall, which has no results: MH-1 turned on day 138.08, MH-5 surveyed from the dead end from day 175.30 on;
- at five of the six works, ropes were turned (RS-6, PL-5, LA-5, SB-3, SB-4) or surveyed from the dead end (RS-2, PL-1, LA-4, LA-6, DS-2, SB-2) in other numbers and combinations, at other surveys and on other cranes, and one rope (DS-5) was first surveyed from the dead end and later turned; the sixth, coil_yard, is sound throughout;
- the cranes reach past the visible ones: the upper block at 13.3 to 41.5 m against 12.9 to 26.7 m, ropes of up to 362 m against 224 m, the greatest damage of a rope 0.083 to 0.492 against 0.086 to 0.212; 11 of the 36 cranes stand higher than every visible crane and 8 have a longer rope than any.
It is built in authoring/provenance/works.py: the `WORKS` table gives each works' role and how many of its ropes were turned, surveyed from the dead end, or both, and `draw` and `build` make the packages from it; authoring/provenance/manifest.json records what each crane's rope went through and the hash of every shipped file.

authoring/provenance/design_rules.py recomputes the design rules from the generator and the shipped files (authoring/evidence/design_rules.txt; 23 of 23 hold):
- 9 works: 2 with their results, 1 without, 6 the program is run on; no name twice; no file shared between a visible works and a works the program is run on;
- a works the program is run on has 6 cranes and 517935 to 549545 movements, ropes of up to 362 m; the statement's most is 6 cranes, 600,000 movements and 400 m;
- every turned rope, read as if never turned, has at least 66 stations more than a band out; every rope surveyed from the dead end, read as turned, at least 62; the mean of the two readings at least 44;
- the day of a turn does not decide: at either edge of its gap no station of any turned rope is more than 0.70 of a band out; no rope was turned within 3.5 days of a survey;
- a mirrored survey is plain: some station rises by at least 0.32 mm across it, against 0.05 mm at most between any two other surveys; laid end for end on the survey before, it leaves at most 0.05 of its squared difference as written, while any other survey from the third on leaves at least 2.33 times as much;
- two surveys of a rope are 12.8 to 17.9 days apart.

Every study below runs complete programs through tests/rope_bench.py as the verifier does: as nobody, with one thread to a library, each run in a directory of its own, the limit on the clock and on CPU.

**Correct programs that are not fast** (second_run.txt). The second solution in plain loops is accepted on the six works made again with a fiftieth of the lifts, where the limit is set aside; at its rate the shipped works would take 85 to 90 s a run, 21.2 to 22.5 times the limit, and run at the limit it is stopped on the first works, the others never tried. The reference's own method with the bendings counted by brute force (brute_ropes.py: every movement against every station in numpy arrays) is accepted at all six works with the limit set aside, in 6.9 to 16.1 s, 1.7 to 4.0 times the limit, and at the limit it is stopped on the first works too.

**Programs that stop short** (route_run.txt; each is the reference with one change, made by authoring/evidence/variants.py). None is accepted:

| program | the two examples | the pending works | works with rows out |
|---|---|---|---|
| RS-4 on the surveys as written; no survey laid against another | accepted | MH-1 out | 5 of 6 |
| every mirrored survey taken for a turned rope | accepted | MH-5 out | 5 of 6 |
| every mirrored survey taken for a survey from the other end; no rope followed | accepted | MH-1 out | 5 of 6 |
| a sheave's place a + p (H - h) taken from the drum anchorage | not accepted | out | 6 of 6 |
| the tension from the hook load alone | not accepted | out | 6 of 6 |
| a bending over the drum counted as over a sheave | not accepted | out | 6 of 6 |

Every works with a condition stops all six routes; coil_yard stops the three that get the standard wrong. The route nearest to right misses by 2.9 bands at the works it misses least.

**Programs without the calculation** (null_run.txt): every damage nil; every station the examples' mean; every station the examples' mean at the same share of the rope's length; the damage read off the last survey's loss of diameter by the power law that fits the examples; and the same law scaled rope by rope to the total the standard gives with the surveys as written. None gets a single rope wholly right; the best gets 3264 of 6292 rows.

**The verifier itself** (verifier_checks.txt, 70 cases, none unexpected; every program is written at run time round the sealed results of two works made with a hundredth of the lifts).
- Sheets refused: nothing written; a directory, a link to the true sheet or a named pipe where the sheet belongs; an empty file; the header alone; no header; a header in other case, with a blank, in quotes or with a third column; a row of three fields or of one; a row left out, given twice, for a station the rope has not, in lower case, or with its station number short of its zeros; a damage empty, n/a, nan, inf, 1e999, with a per cent sign, with a decimal comma, in hexadecimal, or doubly signed; a sheet over 1 MiB; a sheet in UTF-16; the true sheet with exit status 3, or after the program kills itself.
- Sheets accepted: the true sheet with CRLF line ends, no final line end, empty lines, the rows reversed, quoted or padded fields, plus signs, exponent form, and twelve decimals.
- The band: every row 0.9 of a band high or low is accepted, 1.1 is refused, and one row 1.2 of a band out is enough to refuse the program.
- The limit, set to 3 s for the purpose, with two works to try: the true sheet then a sleep, or then a spin with SIGTERM ignored, is over and refused, its sheet unread, the second works never tried; four processes spinning 1.5 s each are over on CPU even though the clock shows 1.5 s, whether they are waited for or left running in sessions of their own; a child left asleep after the program exits in time is killed, and the program is accepted.
- A run: its directory holds ropes.py and nothing else; it is the user nobody; it cannot write to the package or read the sealed results; it has one thread to a library and no CPU affinity; a program file that is a link is refused.
- The reward script, run for real with pytest stood in for: the reward is 1 only when pytest ends 0 and the report counts one test, passed; it is 0 for two tests, a failed, skipped or missing test, a failing exit with a passing report, no report, a report that is not JSON or has no summary, and no ropes.py delivered.

**The whole verifier** (verifier_run.txt). `bash tests/test.sh` itself, unchanged, with each program in turn at /app/output/ropes.py and the reward read from /logs/verifier/reward.txt afterwards: 1 for the reference and 1 for the fast second solution; 0 for RS-4 on the surveys as written, 0 for every mirrored survey taken for a turn, and 0 for the second solution in plain loops, which is stopped at the limit on the first works.

The agent works as a separate user that can write only to /app/output; /app/data is read-only and root's. The verifier runs in a separate container without network; /tests and /logs/verifier are readable by root alone, and the program runs there as nobody.

Evidence (`authoring/evidence/`): reference_run, route_run, spread_run, second_run (with plain_ropes.py, quick_ropes.py and brute_ropes.py), null_run, seed_screen, verifier_checks, verifier_run (with ctrf_standin.py where the ctrf plugin is not installed), design_rules and regenerate, each script with its .txt; common.py and variants.py are shared by them; preflight.py checks every rule of the bundle and writes preflight.txt. Provenance (`authoring/provenance/`): rope.py, the sealed definition; works.py, the generator; design_rules.py; manifest.py and manifest.json; regenerate.py; pending_results/, the sealed result of the pending works.

## Submission notes

- **The program is re-run on hidden inputs under a stated limit.** tests/rope_bench.py runs /app/output/ropes.py on the six works under tests/works, one run each, and holds the sheets against tests/sealed/results. The limit is LIMIT_S = 4 s in tests/rope_bench.py and "Each run of ropes.py must finish within 4 seconds on 1 CPU." in instruction.md, held on the clock and on CPU time; a run over it fails the task, with nothing written before the kill read.
- **A naive correct version times out.** plain_ropes.py (plain loops) would need 85 to 90 s a works and is stopped on the first; brute_ropes.py (every movement against every station, vectorised) needs 6.9 to 16.1 s and is stopped on the first. The reference takes 1.2 to 1.4 s, so the limit is 2.9 times it. Threads are pinned with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in every run.
- **The hidden data is deliberately shifted.** At the two example works no rope was turned and every survey was written from the drum anchorage. At five of the six hidden works ropes were turned end for end, surveyed from the dead end, or both, at times no record gives; one is sound. The cranes reach higher and the ropes are longer than any visible one. Each condition shows once in the visible data, in the pending works without results. Where it is built: the `WORKS` table and `draw` in authoring/provenance/works.py, the sealed definition authoring/provenance/rope.py, and the record of every crane in authoring/provenance/manifest.json.
