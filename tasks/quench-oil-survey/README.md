# quench-oil-survey

Write a program that settles which body of quench oil each tank of a hardening shop really holds after the shop's oil was renewed: it sorts the tanks into oil charges from the laboratory cooling-curve analyses on file, places the site's one laboratory order of a fixed number of samples itself while it runs, and with the oil so identified computes the transient cooling of every bar on record to a heat treatment standard (nonlinear radial conduction under the oil's boiling curve), a site of up to 3,000 loads within 50 seconds on one CPU, on sites it has never seen.

## Difficulty

This is the work of a heat treatment engineer who keeps a works group's quenching standard and the program that applies it. When a steel bar leaves the furnace at about 850 C and goes into oil, what it becomes is decided in the next minute: how fast its centre passes through the transformation range fixes how much of it hardens, how far the surface runs ahead of the centre fixes the stress and distortion it carries, and the time to reach handling temperature fixes the cycle. The task is a program that finds these for every load on record at a hardening shop, to within 1.5 per cent and 3 K, within 50 seconds for a site, at sites whose quench oil has been renewed and has to be sampled before it can be calculated with. The sites, their records and the standard are synthetic and realistic: bars of 20 to 100 mm in two steels, furnace at 830 to 880 C, baths at 50 to 80 C, oils whose peak heat transfer coefficient is 1624 to 2708 W/m2K, and at the six sites the program is run on, centre from 800 to 500 C in 12.6 to 148.7 s, centre cooling rate through 700 C 2.6 to 35.2 K/s, largest centre to surface difference 102 to 409 K, surface at 321 to 444 C when the centre reaches 500 C, centre at 150 C after 74 to 1007 s.

Three pieces of physics set every answer, and none of them is linear.

- **Conduction with changing properties.** Heat leaves the bar by radial conduction, and over the range the bar crosses the steel's conductivity falls by almost half and its heat capacity nearly doubles and then drops again through the transformation. The equation has no closed solution and the classical charts for a cylinder, which assume constant properties and a constant surface coefficient, do not apply.
- **The boiling curve.** The oil does not cool the surface at a steady rate. Above about 700 C the bar sits in a vapour blanket and loses little; the blanket collapses into nucleate boiling, where the coefficient rises sixfold; below 300 C the oil cools by convection alone. The surface coefficient is a steep function of the surface temperature, which is itself the unknown, so the boundary condition is the stiffest part of the problem and drives the time step.
- **A coupled surface and centre.** The results asked for are events at the centre, set by a surface that is passing through all three regimes while the centre is still hot. A bar of 20 mm follows the oil; a bar of 100 mm is limited by its own conduction. No single simplification covers the range.

The oil is the fourth unknown, and it is a measurement problem. The standard takes a load's oil from the laboratory's cooling-curve analysis of the charge that was in the tank, not from the oil type: charges as delivered differ from the catalogue by up to 15 per cent, and a tenth more cooling power shortens the centre's cooling time by a twentieth to a tenth. Most systems at these sites were drained and refilled in January 2026, so the oil now in most tanks has never been analysed. The laboratory analyses a fixed number of samples for a site, in one order, and the program has to place that order itself, while it runs, before it has seen a single result.

What has to be sampled is every body of oil that was renewed, and a body of oil is a physical thing, not a line of a register. Tanks fed from one reservoir give one cooling curve, within what the laboratory repeats; tanks that give two do not share a reservoir, whatever the register says. That is the measurement that settles it, and it is on file:

- two samples of one charge taken in the same round differ by at most 0.33 per cent in maximum cooling rate, and a charge moves by at most 0.68 per cent from one round to the next;
- at some sites one central system that the register lists as a single system has given, at one of its three tanks, analyses 10.1 to 12.0 per cent away from the other two in every one of the four sample rounds, 31 times the largest difference between two samples of one charge;
- at those sites the laboratory's allowance is one more than the number of systems the register shows renewed.

Such a system is two reservoirs. Taken as one, its oil on file is the mean of two different oils, 4.8 to 5.6 per cent from either, and after the renewal one sample stands for two new charges that differ by 8.5 to 20.8 per cent. The tank on the second reservoir has 150 loads at a site. Nothing in the records says any of this in words, and the two example sites do not have such a system: there the register's systems are the charges and the allowance equals their number. The third visible package, the one without results, has one.

The time limit is the other half of the work. A site has 1800 to 2400 loads and no two need be alike, since diameter, steel, furnace and bath temperature and oil all enter and nothing can be tabulated; a run has 50 seconds on one CPU, about a fiftieth of a second a load. Handing each bar in turn to a stiff library integrator, which is the natural way to write it, takes 0.15 s a load, 5 to 7 times the limit for a site. Meeting the limit takes a scheme built for the whole site at once: every bar on the same number of radial intervals, time stepped in proportion to each bar's own R squared so that all bars reach the same stage at the same step, the tridiagonal elimination written out along the radius so that one pass advances every bar, and a step that is short through the boiling peak and long in the convective tail.

Its research analogue is the inverse and forward heat conduction work behind quench process models: nonlinear transient conduction under a boiling boundary condition measured by a probe test, solved for populations of parts. The oil adds the question that precedes any calibration: deciding from the measurements themselves which physical population each belongs to, and planning a fixed number of new measurements before any of them is known.

Each of these defeats an assumption the general approach makes on first reading:
- that a cylinder chart or a lumped model with a mean coefficient gives the centre's cooling time;
- that the oil can be taken from its type's catalogue figures;
- that two thousand bars can each be integrated on their own inside the limit;
- that the register's list of oil systems is the list of charges;
- that an allowance of one more sample than the register needs has one to spare.

## Reference solution

solution/quench.py is the reference; solution/solve.sh puts it at /app/output/quench.py. It reads one package, places the laboratory order and writes the table.

1. **Charges.** The tanks of each listed system are sorted into charges by the analyses on file: two tanks hold different charges when the analyses drawn from them nearest in date stand more than 3 per cent apart in maximum cooling rate, six times what the laboratory repeats. A tank with no analysis stays with the first charge of its system.
2. **The order.** One sample from every charge whose system the oil log shows renewed, at the first tank fed from it, placed through `labsample` in a single order.
3. **The oil of a load.** After the renewal, the laboratory's figure for the tank's charge. Before it, and for a charge that was not renewed, the charge's latest analysis on file, the mean of that date's samples (HT-5 section 5).
4. **One array for a steel.** All loads of a steel are rows of one array: 32 radial intervals for every bar, finite volumes in r, conductivity at the faces from the mean of the neighbouring temperatures.
5. **Time.** Every bar is stepped by the same share of its own R squared over 6e-6 m2/s, so bars of all sizes pass the same stage at the same step. The share starts at 2e-4, grows by 4 per cent a step to 2e-3 while any centre is above 500 C, and to 2e-2 after that. The first four steps are backward Euler and the rest the trapezoidal rule.
6. **A step.** The properties and the surface coefficient are taken at the mid-step temperature by three passes. Each pass is one tridiagonal elimination along the radius, carried out for every bar at once.
7. **Events.** The times at which a centre passes 800, 725, 675, 500 and 150 C are found by linear interpolation inside the step, the surface temperature at the 500 C crossing likewise, and the largest centre to surface difference is kept as the march goes.

**On the shipped sites** (authoring/evidence/reference_run.txt, run by the checker as the verifier runs it) the reference is accepted: 12150 loads at six sites, the largest error at any of them 0.17 of its band, runs of 11.2 to 18.6 s, so the limit of 50 s is 2.7 times the slowest run. It is accepted on both example sites as well, and on the pending package it orders 5 samples, QT-114, QT-118, QT-124, QT-126, QT-138: two of them from the system QS-2.

**authoring/evidence/naive_quench.py** is a second solution, written apart from the reference and sharing no code with it. It joins tanks into charges through a graph, with a threshold of 2 per cent, and cools each load on its own: finite differences on 60 radial intervals with a fictitious node at the surface, integrated by a library stiff integrator with its own error control, the events found as roots of the integrator's interpolant. On the six sites cut down to every 40th load (305 loads) it places the same orders as the reference and is accepted, and its widest departure from the sealed results is 0.17 of a band (authoring/evidence/naive_run.txt).

`solution/solve.sh` starts it inside the agent's container: it copies quench.py to /app/output and runs it once on the three packages in /app/data, checking the two example sites against their results.

## Verification

The deliverable is a program, /app/output/quench.py. The verifier does not read anything the agent's run left behind: tests/grade_program.py, run by the one pytest test in tests/test_program.py, runs the program on six site packages it has not seen and compares what each run writes with sealed results.

**A run.** For each site, a scratch directory holds a copy of quench.py alone and a read-only copy of the package. The program is started there as `python3 quench.py PACKAGE_DIR OUT_CSV`, as the user nobody, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, in a process group of its own, with no network. The run is single-threaded by those settings and is not tied to a particular CPU, because trials that run side by side on one host would then share it.

**The limit.** Each run has 50 seconds from start to exit, the same figure as the task statement's sentence "Each run of quench.py must finish within 50 seconds on 1 CPU." (preflight compares the two). It is enforced by a timeout on the wait for the process, in tests/grade_program.py. A run that is still going at 50 s ends the assessment: its process group and every process of nobody are killed, nothing it wrote is opened, no later site is run, and the program is not accepted. There is no share of sites or loads that lets such a run through.

**The laboratory.** During a run the checker is the laboratory. `labsample` in the verifier's image passes the order to the checker, which answers by the same rule as the agent's laboratory (tests/lab/lab.py is the same file as environment/rig/lab.py): one order for the site, of at most the package's allowance, written down before any figure is given; a second order is refused. The books are readable by root alone. In the agent's image the laboratory is a separate account reached through one sudo rule, and there it answers for the three visible sites only.

**Acceptance.** Every run must finish in time with exit status 0, every OUT_CSV must be the table the statement describes, and for every load of every site the two times, the cooling rate and the largest temperature difference must be within 1.5 per cent of the sealed result and the surface temperature within 3 K. One pytest test carries the reward. tests/test.sh writes 0 first and writes 1 only when pytest exits 0 and tests/read_report.py finds that the ctrf report shows exactly 1 test, 1 passed.

**The reader** holds the table to the statement and no further. The header must be exactly the one given; there must be one row for every load of the package and none for anything else; each value must be a finite decimal number; and the file must be no larger than the 4194304 bytes the statement gives. Row order, line ends, a final terminator, empty lines, quoting and blanks round a field are not stated and are not judged.

**The truth** is the sealed definition authoring/provenance/quench.py, run by authoring/provenance/sites.py for the oil each tank really held: 64 radial intervals and about 5 600 time steps for every load. It is never a run of the reference, which is its own program on half the intervals and far fewer steps. Against 200 intervals and steps a quarter as long the sealed results move by 0.080 per cent at most, 0.05 of a band (authoring/evidence/convergence.txt). authoring/provenance/regenerate.py makes the nine sites again from the generator and finds all 71 shipped data files the same byte for byte (authoring/evidence/regenerate.txt); authoring/provenance/manifest.json lists them with their SHA-256.

**The bands** are checked against a separately written solution. authoring/evidence/naive_quench.py shares no code with the reference or with the sealed definition and uses a different discretisation and a library integrator, and its widest departure from the sealed results is 0.17 of a band, so every band is at least 6 times the widest departure of an independent, correct method. The reference's largest error is 0.17 of a band. A correct standard method is accepted with room to spare; nothing depends on matching a particular scheme.

**What the six sites are, and how they differ from the visible data.** They are six other sites, none of them a visible one and none sharing a file with one. The difference is built in on purpose and is not a new seed of the visible sites:
- at the two example sites, whose results the agent has, every system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed;
- at five of the six sites one central system that the register lists as a single system is two reservoirs, both renewed, in a system of a different number and oil type from site to site; the allowance there is the number of charges, one more than the register's count; the sixth site has no such system;
- the condition is present in the visible data: the pending package, /app/data/pending/west_quarry, has such a system (QS-2), with the same two signs, and the agent's laboratory answers for it.
It is built in authoring/provenance/sites.py: the `SITES` table gives each site's role and which system is two charges, and `describe` builds the charges, the analyses on file and the allowance from it.

authoring/provenance/design_rules.py recomputes the design rules from the generator's description of each site and the shipped files (authoring/evidence/design_rules.txt; 19 of 19 hold):
- 9 sites: 2 with results beside them, 1 without, 6 the program is run on; no name twice;
- no file of a package the program is run on is a file of a package it was written beside (0 shared);
- loads in a package: 1500 to 1950 beside the program, 1800 to 2400 where it is run; the stated most is 3 000;
- at every site the allowance is the number of charges that were renewed;
- at the two example sites every listed system is one charge, and the allowance is the register's count;
- 5 of the 6 sites the program is run on have one central system that is two charges, both renewed, and an allowance one above the register's count; the sixth (south_yard) has none;
- the pending site, which the program's author can read, has such a system too: QS-2, allowance 5 against 4 systems renewed in the register;
- the system that is two charges is not one place: west_quarry QS-2 of Type M; quay_site QS-2 of Type S; ridge_plant QS-3 of Type M; canal_works QS-1 of Type M; upper_mill QS-4 of Type F; tank_farm QS-2 of Type F;
- two samples of one charge in one sample round differ by at most 0.33 per cent in maximum cooling rate (the laboratory repeats within 0.5; the figures are given to 0.1 K/s);
- a charge's analysis moves by at most 0.68 per cent from one sample round to the next;
- in a system that is two charges, the two differ by 10.1 to 12.0 per cent in every one of the four sample rounds (24 rounds over 6 systems);
- the smallest of those differences is 31 times the largest difference between two samples of one charge;
- the two new charges of such a system differ by 8.5 to 20.8 per cent in maximum cooling rate;
- taken as one system, its oil on file is the mean of two oils, 4.8 to 5.6 per cent from either;
- the tank on the second charge has 150 loads at a site, 87 to 102 of them after the renewal;
- results at the six sites: centre from 800 to 500 C in 12.6 to 148.7 s, centre cooling rate through 700 C 2.6 to 35.2 K/s, largest centre to surface difference 102 to 409 K, surface at 321 to 444 C when the centre reaches 500 C, centre at 150 C after 74 to 1007 s;
- the oils' peak heat transfer coefficient is 1624 to 2708 W/m2K;
- every load of every package is within the scope of HT-5 section 1: bars of 20 to 100 mm, furnace at 830 to 880 C, bath at 50 to 80 C;
- the laboratory's book for every site answers for every tank of the site and holds the package's allowance.

Every study below runs complete programs through tests/grade_program.py as the verifier does: as nobody, with one thread to a numerical library, with the laboratory answering through the verifier's `labsample`.

**A correct program that is not fast** (naive_run.txt). The second solution is accepted on the cut-down sites, where the limit is set aside, at 0.15 s a load. At that rate the sites as they are, of 1800 to 2400 loads, would take 266 to 355 s a run, 5 to 7 times the limit. Run on them at the limit, it is stopped: sites run 1 of 6, the run on canal_works was still going after 50 s, not accepted.

**Programs written to the visible results** (register_run.txt, made from the reference by authoring/evidence/variants.py, one change each):
| program | the two example sites | sites with loads out of band | loads out at each of those |
|---|---|---|---|
| one sample for each listed system that was renewed; the rest of the allowance unused | accepted | 5 of 6 | 245 to 270 |
| the same, with the rest of the allowance spent on tanks not yet sampled, a tank whose own sample stands apart keeping its own figures | accepted | 5 of 6 | 245 to 270 |
| tanks sorted into charges by analysis for the oil on file, but one sample for each listed system that was renewed | accepted | 5 of 6 | 87 to 102 |

With one sample for each listed system the loads out of band are canal_works 251, quay_site 254, ridge_plant 270, south_yard 0, tank_farm 252, upper_mill 245. The site with none is the one without such a system.

**The verifier itself** (verifier_checks.txt, 65 cases, none unexpected; every program is built at run time from the sealed results of a cut-down site).
- Tables refused: nothing written, OUT_CSV as a directory or as a symbolic link to a file holding the true table, an empty file, the header alone, no header, a misspelt, capitalised or padded header, a column added or left out, a row of five fields, a load left out, given twice, unknown or in lower case, a value empty, n/a, nan, inf, with its unit, with a decimal comma or with a digit separator, bytes that are not UTF-8, a file over the size cap, and the true table followed by exit status 3.
- Tables accepted: the true table with CRLF line ends, no final terminator, empty lines, the rows reversed, padded or quoted fields, plus signs, and exponent form.
- Bands: each quantity moved to just inside its band at every load is accepted (1.4 per cent, 2.8 K) and to just outside is not (1.6 per cent, 3.2 K); one load of a site with its core cooling time 2 per cent out is enough to refuse the program.
- The limit, set to 3 s for the purpose: a program that writes the true table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; with two sites to run the second is never started; a program that exits in time and leaves a child running in a session of its own is accepted and the child is killed.
- The laboratory during a run: an order over the allowance, an order naming a tank the site does not have and an order through a package naming another site are refused and do not count as the site's order; the order after them is taken; a second order is refused; outside a run nothing answers.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest exits 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, a failing exit with a passing report, no report, a report that is not JSON, and no quench.py delivered.

**The whole verifier** (verifier_run.txt). tests/test.sh itself, run as it stands with each program in turn at /app/output/quench.py, under the umask it sets, with the checker running the program as nobody: the reward is 1 for the reference and 0 for the program that samples by the register and for the second solution at the limit. Where that study was run the pytest-json-ctrf plugin was not installed, and authoring/evidence/ctrf_standin.py wrote the report in its place; the verifier's image installs the plugin itself.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned, and the verifier's image carries the same /app/data at the same path. The verifier runs in a separate container without network; /tests and /logs/verifier are readable by root alone, and the program runs there as nobody.

Evidence (`authoring/evidence/`): `reference_run.txt`, `naive_run.txt`, `register_run.txt`, `verifier_checks.txt`,
`verifier_run.txt`, `design_rules.txt`, `convergence.txt`, `regenerate.txt` and `preflight.txt`.

## Submission notes

What the shift in the hidden data is. The visible results (two example sites) come from sites where every quench oil system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed. At five of the six hidden sites one listed central system is two reservoirs, both renewed, so the right laboratory order has one more sample than the register's count and the tank on the second reservoir has a different oil before and after the renewal. The condition appears once in the visible data, in the package without results (/app/data/pending/west_quarry, system QS-2). The hidden sites are other sites: no name and no file is shared with a visible one. A program that follows the register reproduces both visible result sets and is out of band at five hidden sites (authoring/evidence/register_run.txt).

Where it is built.
- Generator config: authoring/provenance/sites.py, the `SITES` table (seed, role, the system that is two charges, number of central systems and of tanks with their own oil) and `describe`.
- Manifest: authoring/provenance/manifest.json, the same table and the SHA-256 of every data file.
- Data files: tests/sites/ (the six packages), tests/sealed/truth/ (their results), tests/lab/sealed/ (the laboratory's books for them); environment/data/examples/ and environment/data/pending/ (the visible packages), environment/rig/sealed/ (the laboratory's books for those).
- Check: authoring/provenance/design_rules.py and authoring/evidence/design_rules.txt.

The timed re-run.
- The tests run the program: tests/grade_program.py, `run_site`.
- The limit: `RUN_LIMIT_S = 50` in tests/grade_program.py, and "Each run of quench.py must finish within 50 seconds on 1 CPU." in instruction.md; preflight fails if they differ.
- The reference takes 11.2 to 18.6 s a run; the limit is 2.7 times the slowest.
- A correct program that is not fast times out: authoring/evidence/naive_quench.py, authoring/evidence/naive_run.txt.
- A run over the limit ends the assessment and nothing it wrote is read: authoring/evidence/verifier_checks.txt, "The limit".
- Threads: OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in the environment of each run. Runs are not tied to one CPU, since trials side by side on one host would then share a core.
