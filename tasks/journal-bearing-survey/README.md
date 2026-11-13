# journal-bearing-survey

Write a program that calculates every operating point on record of a site's grooved journal bearings to a hydrodynamic lubrication standard (minimum film thickness, attitude angle, power loss, effective film temperature and peak film pressure, from the Reynolds equation with film rupture and a heat balance on the oil), with each bearing's oil identified from the analyses on file and from one laboratory order of a fixed number of samples that the program places itself, and that finishes a site of up to 3,000 points within 60 seconds on one CPU on sites it has never seen.

## Difficulty

This is the work of a tribology engineer who keeps a works group's bearing calculation standard and the program that applies it. A plain journal bearing carries its shaft on an oil film a few tens of micrometres thick, and whether a machine may run at a given speed, load and oil temperature is decided by that film: how thin it gets, how much power it dissipates, how hot it runs and how hard it presses on the lining. The task is a program that finds these five quantities for every operating point on record at a site, to within 1.5 per cent, 1 degree and 0.5 K, within 60 seconds for a site, at sites whose oil has been renewed and has to be sampled before it can be calculated with. The sites, their records and the standard are synthetic and realistic: journals of 90 to 200 mm at 600 to 3560 rpm on ISO VG 32 to 68 mineral oils, and at the six sites the program is run on, film thickness 18.2 to 110.7 um, attitude 31 to 77 degrees, power loss 0.35 to 8.45 kW, peak pressure 1.0 to 7.2 MPa, film 1.1 to 17.9 K above the inlet.

Four pieces of physics set every answer, and they have to be solved together.

- **The film.** The pressure obeys the Reynolds equation for a finite bearing with two axial grooves: an elliptic equation in the angle round the bearing and the axial coordinate, driven by the wedge the journal makes with the bush, with the pressure zero at the two ends and along each groove. At these length to diameter ratios there is no closed form; the short-bearing and long-bearing formulas both leave out a flow that matters here.
- **Rupture.** Oil does not carry tension. Where the equation would give a pressure below zero the film breaks, and where it breaks is part of the solution: the pressure and its gradient vanish together on a boundary that is not known in advance. The pressure field is the solution of a complementarity problem, not of one linear system.
- **Equilibrium.** The journal's position is not given. Eccentricity and attitude are where the resultant of the ruptured film equals the load in size and direction, two nonlinear conditions wrapped round the film.
- **Heat.** All the power lost in the film leaves with the oil, and these oils lose 2.7 to 4.7 per cent of their viscosity for each K. The film runs 1.1 to 17.9 K above the inlet, so the viscosity that sets the film is fixed by the loss that the film sets. Temperature, viscosity, position and loss are one fixed point.

The oil is the fifth unknown, and it is a measurement problem. The standard takes a bearing's oil from the laboratory's analysis of the charge that was in its supply, not from the grade: charges as delivered differ from the grade's nominal figures by up to 15 per cent, and every one of the five results moves with the viscosity. Most systems at these sites were drained and refilled in January 2026, so the oil now in most bearings has never been analysed. The laboratory analyses a fixed number of samples for a site, in one order, and the program has to place that order itself, while it runs, before it has seen a single result.

What has to be sampled is every body of oil that was renewed, and a body of oil is a physical thing, not a line of a register. Bearings fed from one reservoir give one analysis, within what the laboratory repeats; bearings that give two do not share a reservoir, whatever the register says. That is the measurement that settles it, and it is on file:

- two samples of one charge taken in the same round differ by at most 0.67 per cent in viscosity, and a charge moves by at most 0.92 per cent from one round to the next;
- at some sites one console that the register lists as a single system has given, at one of its three machines, analyses 9.4 to 12.1 per cent away from the other two in every one of the four sample rounds, 14 times the largest difference between two samples of one charge;
- at those sites the laboratory's allowance is one more than the number of systems the register shows renewed.

Such a console is two reservoirs. Taken as one, its oil on file is the mean of two different oils, 4.6 to 5.7 per cent from either, and after the renewal one sample stands for two new charges that differ by 10.2 to 24.9 per cent. The machine on the second reservoir has 110 to 220 operating points at a site. Nothing in the records says any of this in words, and the two example sites do not have such a console: there the register's systems are the charges and the allowance equals their number. The third visible package, the one without results, has one.

The time limit is the other half of the work. The standard asks for results converged to 0.2 per cent, a site has 2090 to 2420 points, and a run has 60 seconds on one CPU, a few hundredths of a second a point. Solving the film as one general sparse system, with the heat balance iterated outside the equilibrium and each point started cold, takes 0.46 s a point, 16 to 19 times the limit for a site. Meeting the limit takes the structure of the problem. The grooves cut the film into separate lands whose equations are banded. And once the viscosity is taken out, a laminar film's force and peak pressure depend only on where the journal sits, so the film can be solved once for each bearing geometry on a grid of journal positions and every point of that geometry found from the table, with position, attitude and temperature as the three unknowns of one Newton iteration carried out for all points at once.

Its research analogue is thermohydrodynamic lubrication analysis as a bearing design code does it: a free-boundary elliptic problem coupled to a force balance and an energy balance, made fast by a similarity reduction to a tabulated dimensionless solution. The oil adds the question that precedes any calibration: deciding from the measurements themselves which physical population each belongs to, and planning a fixed number of new measurements before any of them is known.

Each of these defeats an assumption the general approach makes on first reading:
- that a finite grooved bearing can be had from a short-bearing formula or from a film that is whole all round;
- that the viscosity can be taken at the inlet temperature, or from the grade;
- that a few thousand points can each be solved from scratch inside the limit;
- that the register's list of oil systems is the list of charges;
- that an allowance of one more sample than the register needs has one to spare.

## Reference solution

solution/bearing.py is the reference; solution/solve.sh puts it at /app/output/bearing.py. It reads one package, places the laboratory order and writes the table.

1. **Charges.** The machines of each listed system are sorted into charges by the analyses on file: two machines are on different charges when the analyses drawn at them nearest in date stand more than 3 per cent apart in viscosity at 40 C, six times what the laboratory repeats. A machine with no analysis stays with the first charge of its system.
2. **The order.** One sample from every charge whose system the oil log shows renewed, at the first bearing fed from it, placed through `labsample` in a single order.
3. **The oil of a point.** After the renewal, the laboratory's figure for the bearing's charge. Before it, and for a charge that was not renewed, the charge's latest analysis on file, the mean of that date's samples (LS-3 section 7).
4. **Bearing states and geometries.** Points are grouped by bearing and oil. Films that share a length to diameter ratio and groove positions share one dimensionless solution.
5. **The table.** For each geometry the laminar film is solved on a grid of 28 eccentricities by journal angles 4.5 degrees apart: resultant force, its direction and the peak pressure, each as a spline surface. Each land between two grooves is a banded system of half-width 16, with rupture as an active set started from the neighbouring solution.
6. **The points.** All points of a bearing state are solved from the table at once: a Newton iteration on eccentricity, attitude and film temperature, with the Walther viscosity and the heat balance inside it. The friction comes from the Couette term in closed form and the moment of the film's resultant.
7. **What the table cannot settle.** A point off the table's edge, or whose film is not laminar, is solved directly on the same banded lands with the same three unknowns, on 144 by 16 nodes and on 192 by 20 above an eccentricity of 0.75.

**On the shipped sites** (authoring/evidence/reference_run.txt, run by the checker as the verifier runs it) the reference is accepted: 13860 points at six sites, the largest error at any of them 0.09 of its band, runs of 19.9 to 26.9 s, so the limit of 60 s is 2.2 times the slowest run. It is accepted on both example sites as well, and on the pending package it orders 5 samples, K-114-DE, K-120-DE, M-123-DE, G-125-DE, C-139-DE: two of them from the console LO-2.

**authoring/evidence/naive_bearing.py** is a second solution, written apart from the reference and sharing no code with it. It joins machines into charges through a graph, with a threshold of 2 per cent, and solves the film as one sparse system over the whole bearing on 144 by 16 nodes, grooves included, with the journal position found inside a bracketing search on the film temperature, one point at a time. On the six sites cut down to every 40th point (349 points) it places the same orders as the reference and is accepted, and its widest departure from the sealed results is 0.07 of a band (authoring/evidence/naive_run.txt).

`solution/solve.sh` starts it inside the agent's container: it copies bearing.py to /app/output and runs it once on the three packages in /app/data, checking the two example sites against their results.

## Verification

The deliverable is a program, /app/output/bearing.py. The verifier does not read anything the agent's run left behind: tests/grade_program.py, run by the one pytest test in tests/test_program.py, runs the program on six site packages it has not seen and compares what each run writes with sealed results.

**A run.** For each site, a scratch directory holds a copy of bearing.py alone and a read-only copy of the package. The program is started there as `python3 bearing.py PACKAGE_DIR OUT_CSV`, as the user nobody, held to one CPU, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, in a process group of its own, with no network.

**The limit.** Each run has 60 seconds from start to exit, the same figure as the task statement's sentence "Each run of bearing.py must finish within 60 seconds on 1 CPU." (preflight compares the two). It is enforced by a timeout on the wait for the process, in tests/grade_program.py. A run that is still going at 60 s ends the assessment: its process group and every process of nobody are killed, nothing it wrote is opened, no later site is run, and the program is not accepted. There is no share of sites or points that lets such a run through.

**The laboratory.** During a run the checker is the laboratory. `labsample` in the verifier's image passes the order to the checker, which answers by the same rule as the agent's laboratory (tests/lab/lab.py is the same file as environment/rig/lab.py): one order for the site, of at most the package's allowance, written down before any figure is given; a second order is refused. The books are readable by root alone. In the agent's image the laboratory is a separate account reached through one sudo rule, and there it answers for the three visible sites only.

**Acceptance.** Every run must finish in time with exit status 0, every OUT_CSV must be the table the statement describes, and for every point of every site the minimum film thickness, the power loss and the peak pressure must be within 1.5 per cent of the sealed result, the attitude angle within 1 degree and the effective temperature within 0.5 K. One pytest test carries the reward. tests/test.sh writes 0 first and writes 1 only when pytest exits 0 and tests/read_report.py finds that the ctrf report shows exactly 1 test, 1 passed.

**The reader** holds the table to the statement and no further. The header must be exactly the one given; there must be one row for every point of the package and none for anything else; each value must be a finite decimal number. Row order, line ends, a final terminator, empty lines, quoting and blanks round a field are not stated and are not judged.

**The truth** is the sealed definition authoring/provenance/film.py, run by authoring/provenance/sites.py for the oil each bearing really drew: every point solved directly on 240 by 24 nodes, with no table. It is never a run of the reference, which tabulates the film on coarser grids. authoring/provenance/regenerate.py makes the nine sites again from the generator and finds all 71 shipped data files the same byte for byte (authoring/evidence/regenerate.txt); authoring/provenance/manifest.json lists them with their SHA-256.

**The bands** are checked against a separately written solution. authoring/evidence/naive_bearing.py shares no code with the reference or with the sealed definition, and its widest departure from the sealed results is 0.07 of a band, so every band is at least 15 times the widest departure of an independent, correct method. The reference's largest error is 0.09 of a band. A correct standard method is accepted with room to spare; nothing depends on matching a particular discretisation.

**What the six sites are, and how they differ from the visible data.** They are six other sites, none of them a visible one and none sharing a file with one. The difference is built in on purpose and is not a new seed of the visible sites:
- at the two example sites, whose results the agent has, every system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed;
- at five of the six sites one console that the register lists as a single system is two reservoirs, both renewed, in a console of a different number and grade from site to site; the allowance there is the number of charges, one more than the register's count; the sixth site has no such console;
- the condition is present in the visible data: the pending package, /app/data/pending/west_quarry, has such a console (LO-2), with the same two signs, and the agent's laboratory answers for it.
It is built in authoring/provenance/sites.py: the `SITES` table gives each site's role and which console is two charges, and `describe` builds the charges, the analyses on file and the allowance from it.

authoring/provenance/design_rules.py recomputes the design rules from the generator's description of each site and the shipped files (authoring/evidence/design_rules.txt; 19 of 19 hold):
- 9 sites: 2 with results beside them, 1 without, 6 the program is run on; no name twice;
- no file of a package the program is run on is a file of a package it was written beside (0 shared);
- operating points in a package: 1540 to 2640 beside the program, 2090 to 2420 where it is run; the stated most is 3 000;
- at every site the allowance is the number of charges that were renewed;
- at the two example sites every listed system is one charge, and the allowance is the register's count;
- 5 of the 6 sites the program is run on have one listed console that is two charges, both renewed, and an allowance one above the register's count; the sixth (south_yard) has none;
- the pending site, which the program's author can read, has such a console too: LO-2, allowance 5 against 4 systems renewed in the register;
- the console that is two charges is not one place: west_quarry LO-2 of ISO VG 46; quay_site LO-2 of ISO VG 68; ridge_plant LO-3 of ISO VG 46; canal_works LO-1 of ISO VG 46; upper_mill LO-4 of ISO VG 32; tank_farm LO-2 of ISO VG 46;
- two samples of one charge in one sample round differ by at most 0.67 per cent in viscosity at 40 C (the laboratory repeats within 0.5; the figures are given to 0.1 mm2/s);
- a charge's analysis moves by at most 0.92 per cent from one sample round to the next;
- in a console that is two charges, the two differ by 9.4 to 12.1 per cent in every one of the four sample rounds (24 rounds over 6 consoles);
- the smallest of those differences is 14 times the largest difference between two samples of one charge;
- the two new charges of such a console differ by 10.2 to 24.9 per cent in viscosity at 40 C;
- taken as one system, its oil on file is the mean of two oils, 4.6 to 5.7 per cent from either;
- the machine on the second charge has 110 to 220 operating points at a site, 68 to 151 of them after the renewal;
- results at the six sites: film thickness 18.2 to 110.7 um, attitude 31 to 77 degrees, power loss 0.35 to 8.45 kW, peak pressure 1.0 to 7.2 MPa, film 1.1 to 17.9 K above the inlet;
- the oils' viscosity falls by 2.7 to 4.7 per cent for each K between 45 and 75 C;
- every bearing and operating point of every package is within the scope of LS-3 section 1;
- the laboratory's book for every site answers for every bearing of the site and holds the package's allowance.

Every study below runs complete programs through tests/grade_program.py as the verifier does: as nobody, on one CPU, with the laboratory answering through the verifier's `labsample`.

**A correct program that is not fast** (naive_run.txt). The second solution is accepted on the cut-down sites, where the limit is set aside, at 0.46 s a point. At that rate the sites as they are, of 2090 to 2420 points, would take 959 to 1110 s a run, 16 to 19 times the limit. Run on them at the limit, it is stopped: sites run 1 of 6, the run on canal_works was still going after 60 s, not accepted.

**Programs written to the visible results** (register_run.txt, made from the reference by authoring/evidence/variants.py, one change each):
| program | the two example sites | sites with points out of band | points out at each of those |
|---|---|---|---|
| one sample for each listed system that was renewed; the rest of the allowance unused | accepted | 5 of 6 | 223 to 315 |
| the same, with the rest of the allowance spent on machines not yet sampled, a machine whose own sample stands apart keeping its own figures | accepted | 5 of 6 | 223 to 315 |
| machines sorted into charges by analysis for the oil on file, but one sample for each listed system that was renewed | accepted | 5 of 6 | 68 to 151 |

With one sample for each listed system the points out of band are canal_works 293, quay_site 315, ridge_plant 262, south_yard 0, tank_farm 223, upper_mill 243. The site with none is the one without such a console.

**The verifier itself** (verifier_checks.txt, 65 cases, none unexpected; every program is built at run time from the sealed results of a cut-down site).
- Tables refused: nothing written, OUT_CSV as a directory or as a symbolic link to a file holding the true table, an empty file, the header alone, no header, a misspelt, capitalised or padded header, a column added or left out, a row of five fields, a point left out, given twice, unknown or in lower case, a value empty, n/a, nan, inf, with its unit, with a decimal comma or with a digit separator, bytes that are not UTF-8, a file over the size cap, and the true table followed by exit status 3.
- Tables accepted: the true table with CRLF line ends, no final terminator, empty lines, the rows reversed, padded or quoted fields, plus signs, and exponent form.
- Bands: each quantity moved to just inside its band at every point is accepted (1.4 per cent, 0.9 degrees, 0.45 K) and to just outside is not (1.6 per cent, 1.1 degrees, 0.55 K); one point of a site with its power loss 2 per cent high is enough to refuse the program.
- The limit, set to 3 s for the purpose: a program that writes the true table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; with two sites to run the second is never started; a program that exits in time and leaves a child running in a session of its own is accepted and the child is killed.
- The laboratory during a run: an order over the allowance, an order naming a bearing the site does not have and an order through a package naming another site are refused and do not count as the site's order; the order after them is taken; a second order is refused; outside a run nothing answers.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest exits 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, a failing exit with a passing report, no report, a report that is not JSON, and no bearing.py delivered.

**The whole verifier** (verifier_run.txt). pytest on tests/test_program.py in a process of its own exits 0 for the reference and 1 for the program that samples by the register and for the second solution at the limit.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned, and the verifier's image carries the same /app/data at the same path. The verifier runs in a separate container without network; /tests and /logs/verifier are readable by root alone, and the program runs there as nobody.

Evidence (`authoring/evidence/`): `reference_run.txt`, `naive_run.txt`, `register_run.txt`, `verifier_checks.txt`,
`verifier_run.txt`, `design_rules.txt`, `regenerate.txt` and `preflight.txt`.

## Submission notes

What the shift in the hidden data is. The visible results (two example sites) come from sites where every oil system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed. At five of the six hidden sites one listed console is two reservoirs, both renewed, so the right laboratory order has one more sample than the register's count and the machine on the second reservoir has a different oil before and after the renewal. The condition appears once in the visible data, in the package without results (/app/data/pending/west_quarry, console LO-2). The hidden sites are other sites: no name and no file is shared with a visible one. A program that follows the register reproduces both visible result sets and is out of band at five hidden sites (authoring/evidence/register_run.txt).

Where it is built.
- Generator config: authoring/provenance/sites.py, the `SITES` table (seed, role, the console that is two charges, number of consoles and of self-contained machines) and `describe`.
- Manifest: authoring/provenance/manifest.json, the same table and the SHA-256 of every data file.
- Data files: tests/sites/ (the six packages), tests/sealed/truth/ (their results), tests/lab/sealed/ (the laboratory's books for them); environment/data/examples/ and environment/data/pending/ (the visible packages), environment/rig/sealed/ (the laboratory's books for those).
- Check: authoring/provenance/design_rules.py and authoring/evidence/design_rules.txt.

The timed re-run.
- The tests run the program: tests/grade_program.py, `run_site`.
- The limit: `RUN_LIMIT_S = 60` in tests/grade_program.py, and "Each run of bearing.py must finish within 60 seconds on 1 CPU." in instruction.md; preflight fails if they differ.
- The reference takes 19.9 to 26.9 s a run; the limit is 2.2 times the slowest.
- A correct program that is not fast times out: authoring/evidence/naive_bearing.py, authoring/evidence/naive_run.txt.
- A run over the limit ends the assessment and nothing it wrote is read: authoring/evidence/verifier_checks.txt, "The limit".
- Threads: OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in the environment of each run, which is also held to one CPU.
