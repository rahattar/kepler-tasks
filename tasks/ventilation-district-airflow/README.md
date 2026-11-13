# ventilation-district-airflow

Write a program that gives the airflow at every survey point of a mine ventilation district over three weeks of regulator and door movements: it takes the airways' resistances from the pressure-quantity surveys on file, decides from those records what the district's one survey order has to measure and places it while it runs, and carries two parallel axial fans through stall and recovery along the log. The tests re-run the program on six other districts under a time limit.

## Difficulty

This is the work of a mine ventilation engineer who keeps a mining group's network calculation standard and the program that applies it. A district is exhausted by two axial fans standing in parallel at one fan house. The air goes down a shaft, along the intake mains, through nine or ten panels of gate roads and faces, and back along the returns, with a stopping in every cut-through between an intake and a return. Whether a face has its air at a given hour is a number in m3/s, and the standard asks for it at every survey point on record: 3570 to 3948 points in a district of 806 to 955 branches, at 42 survey rounds over 21 days in which regulators and doors were moved more than a thousand times.

Three things set every answer, and none of them can be had alone.

- **The network.** Every branch obeys the square law, p_from - p_to = R q |q|, and the airflows balance at every node. A district is several hundred nonlinear loop equations closed through two fans, and a regulator moved in one panel moves the air in every other.
- **Stall.** The characteristic of an axial fan is not monotone: from shutoff the pressure falls into a trough, rises to a peak and only then falls to free delivery. Two such fans in parallel against one district have more than one steady state over a band of district resistance, both fans healthy or one of them in stall at about half its airflow. Here a fan stalls when the district's resistance reaches 1.20 to 1.33 times its working value and recovers only when it has come down to 0.75 to 0.83 times. In between, which state the district is in is not a function of its settings. It is the state it was already in. Closing the intake's bulkhead door stalls a fan, opening the door again does not bring it back, and opening the airlock does. The standard says that every change is made slowly and the flow is steady at every moment, and the rest follows from the mechanics: the log is the district's history, and a calculation has to carry the state through it. Every district has a fan in stall at 9 to 28 of its 42 survey rounds.
- **The resistances.** They are not given. An airway's resistance is what a pressure-quantity survey of it found, read to 0.3 per cent in pressure and in quantity; a stopping's is what the register says it was built to; and the surveys on file are the three campaigns of the past year. An airway that was re-supported or enlarged after its latest survey is no longer the airway that was surveyed: the survey on file gives 4.1 to 7.9 times its resistance as it is. The standard says so, and the survey crew will survey the district as it stands today, in one order of a fixed number of branches that the program places itself while it runs. Each district has 6 to 9 such airways, and without the order even the two example districts are out of band.

What the order has to measure is the fourth part of the work, and it is a question about measurements, not about the register. Two things are in the records in numbers and nowhere in words.

- **A stopping that is open.** At some districts one stopping that the register books at 1721 to 3744 N s2/m8 is in fact at 7.1 to 8.9 and passes several m3/s from the intake gate road to the return. Stoppings are not surveyed, so no file says it. The gate roads on either side are: in every one of the three campaigns the air that arrives at the stopping's intake end along the surveyed airways exceeds the air that leaves it along them by 5.1 to 10.1 m3/s, where at 2099 stoppings as built the same balance closes within 1.02 m3/s. Conservation of air at a node is the measurement, and it has been on file for a year. Taken as booked, the stopping puts 399 to 889 of the district's points out of band, by up to 9 times the tolerance.
- **A closure whose outcome the records cannot decide.** At some districts the last movement of the return's bulkhead door takes the district to the stall point within what the surveys can resolve: the resistance at which the healthy state ceases, for the district as it is and for the district as its records have it, is 0.32 to 0.60 per cent apart, and the closure lies between the two. One of them stalls and the other does not, and from there to the end of the record, the last 5 survey rounds, the two are in different states. No amount of care with the records settles it. A survey of a fan branch does: the crew reads the fan's airflow as the district stands now, and a fan in stall carries about half the air of a healthy one. The program then has to find which movement turned, and carry the record on from it the other way.

At those districts the crew's allowance is one branch more than the airways worked on, for each of the two. A district with both has two places more than its work log accounts for, and nothing says what they are for. The two example districts, whose results are given, have neither condition and an allowance that is exactly the number of airways worked on, so a program that surveys the airways worked on, takes stoppings as booked and follows the log reproduces both sets of results. The pending district, whose package is given without results, has both: stopping P1-X-03, and the closure of 2026-03-20 10:15. Where the program is written the crew answers for the two example districts only, so the pending district's records are the evidence and nothing answers back.

The time limit is the other half of the work. A run has 35 seconds on one CPU for a district of up to 1,000 branches and 1,500 log rows. A network solved from scratch for every log entry, each change made gradually as the standard has it, is far over: the second solution in authoring/evidence, which reduces the district to one resistance by a dense linear-theory iteration at every entry, takes 2.1 to 20.9 s on districts a tenth of the size and is stopped at the limit on the first of the six. The reference takes 8.7 to 10.5 s by solving nodes and branches together as one sparse Newton system started from the last state, making a change in gradual steps only where a fan would leave its limb, and replaying single movements from stored states when it looks for the one that turned.

The data is synthetic and realistic: districts of a longwall mine's layout, resistances, leakage and fan duties in the range of working collieries, with survey campaigns, a work log and a settings log as a ventilation office keeps them. The research analogue is state estimation and model validation for a nonlinear flow network with more than one equilibrium, as in gas and water networks and in power-flow studies: bad data found from conservation residuals rather than from a flag, and a bistable system whose basin cannot be decided from a model whose uncertainty straddles a fold, decided by one measurement chosen for the purpose.

Each of these defeats an assumption the general approach makes on first reading:

- that the airflow at a time follows from the settings at that time;
- that a fan which has passed its peak is in stall, and one whose district has come back is healthy;
- that the register's resistance of a stopping is the stopping's resistance;
- that an allowance larger than the work log needs has places to spare;
- that a calculation carried to 0.1 per cent on records good to 0.3 per cent decides a closure that turns within 0.6 per cent;
- that a thousand log entries can each be solved from scratch inside the limit.

## Reference solution

solution/airflow.py is the reference; solution/solve.sh puts it at /app/output/airflow.py. It reads one package, places the survey order and writes the table.

1. **Records.** Every airway's resistance is dp / (q |q|) from its latest survey on file. The airways re-supported or enlarged after their latest survey are listed from the work log (`on_file`).
2. **Stoppings.** For every stopping and every campaign: the air arriving at its intake end along surveyed airways and not leaving along them, the same at its return end, and the pressure across it, summed along the surveyed airways of that campaign (`across`). A stopping is taken to be open when, in every campaign, the missing air exceeds four times what the accuracy of the readings allows plus three times what the booked resistance would pass (`breached`). Its resistance is then the pressure across it over the square of the missing air, the mean of the campaigns.
3. **The order.** The airways worked on, the stoppings found open, and with a place left, the fan behind the longer ducting, in one `pqsurvey` order. Surveyed branches take the resistance the crew read.
4. **The district.** Nodes and branches are solved together: Newton's method on the node balances and the branch laws as one sparse system, the fans' characteristics as straight lines between catalogue points (`step`, `newton`). Where Newton does not hold the fans on their limbs, the inertial equations are integrated implicitly until the flow settles, which takes the district where its own dynamics take it (`settle`).
5. **The log.** Each entry is first tried as one Newton solve from the last state; if every fan stays on its limb, that is the new state. Otherwise the change is made in 12 gradual steps, settled after each (`change`). The flows at every survey round are kept, and before every change of more than three times in a resistance the state is stored, with the fans' limbs before and after it and how near the nearest healthy fan was left to its peak (`carry`).
6. **The fan.** If the crew's reading puts the fan on another limb than the calculation ends on, some change went the other way in the district than on its records. Going back from the end over the stored changes at which a fan changed limb or was left within 5 per cent of its peak, the first whose outcome reverses when the airways' resistances are moved by up to 1.2 per cent either way is taken to be the one. The least such move is found by bisection, each trial a replay of that one change from its stored state, and the record is carried on from there with it.
7. **The table.** `point,flow_m3_s`, one row for every survey point.

## Verification

The deliverable is a program, /app/output/airflow.py. The verifier does not read anything the agent's run left behind: tests/judge_airflow.py, run by the one pytest test in tests/test_airflow.py, runs the delivered program on six districts it has never seen and compares every airflow with the sealed result. tests/test.sh writes the reward: 1 if that one test passed, 0 otherwise.

**A run.** For each district in turn a scratch directory is laid out with a copy of airflow.py alone and a read-only copy of the package. The program is started there as the user nobody, in a session of its own, with one thread to a numerical library and no network, as `python3 airflow.py PACKAGE_DIR OUT_CSV`, and has 35 seconds to exit; no CPU affinity is set. `pqsurvey` on the PATH carries the program's order to the checker, which holds the crew's books where nobody cannot open them and answers one order for that district by the rule in tests/crew/lab.py, the same file the agent's `pqsurvey` runs. At exit or at the limit every process of the run is killed. A run still going at the limit ends the judging and nothing it wrote is opened. Otherwise OUT_CSV has to be the table the statement describes, no larger than 2000000 bytes, with one row for every survey point and no other, and every airflow within 1.5 per cent of the sealed result or within 0.03 m3/s where that is more.

**Why the band.** The sealed result is the district as it is, carried through its log by an implicit integration of the inertial equations (authoring/provenance/network.py, district.py), with nothing shared with the reference but the standard. A program has the resistances only as surveys give them, each reading within 0.3 per cent, so its results differ from the sealed ones by what that scatter does to a network: the reference's largest error at any of 22932 points is 0.22 of the band, and the separately written second solution's is 0.30 of the band on the small districts. The band is five times the first and more than three times the second.

**What the six districts are, and how they differ from the visible data.** They are six other districts, none of them a visible one and none sharing a record file with one. The difference is built in on purpose and is the one described under Difficulty:

- at the two example districts, whose results the agent has, no stopping is open, the records leave no closure open, and the allowance is the number of airways worked on;
- 3 of the six have an open stopping (deep_south, old_shaft, lower_levels) and 4 a closure the records leave open (deep_south, far_east, lower_levels, river_block); in two the district stalls where its records hold and in two it holds where its records stall; new_incline has neither;
- both conditions are present in the visible data: the pending package, /app/data/pending/west_reef, has stopping P1-X-03 open and the closure of 2026-03-20 10:15 left open, with an allowance two above its airways worked on. Where the program is written the crew does not answer for that district, and district_package.md says so.

It is built in authoring/provenance/districts.py: the `SITES` table gives each district's role, its fans, whether a stopping is open and which way its last closure goes, and `make` draws a record, checks it and keeps the first that every rule accepts. A record is refused unless the sealed result is the same when every change is made in finer steps, along another path, with other inertias and in two steps, unless every stall and recovery before the last closure survives every resistance being 3 per cent higher or lower, and unless no log entry leaves a fan between trough and peak (district.py, `audit`).

authoring/provenance/design_rules.py recomputes the design rules from the shipped files (authoring/evidence/design_rules.txt; 21 of 21 hold):

- 9 districts: 2 with results beside the program, 1 without, 6 the program is run on; no name twice;
- no file of a district's record in a package the program is run on is a file of a package it was written beside;
- a package holds 806 to 955 branches, 1153 to 1322 log rows and 3570 to 3948 survey points; the stated most are 1000, 1500 and 4500;
- the airways re-supported or enlarged since their latest survey, read from the work log and the surveys, are the ones the district was built with, 6 to 9 a district, and the survey on file gives 4.1 to 7.9 times such an airway's resistance as it is;
- at every district the allowance is the number of airways worked on, and one more for an open stopping, and one more for a closure the records leave open;
- at a stopping as built the surveyed airflows at its intake end balance within 1.02 m3/s in every campaign (2099 stoppings, 6297 balances); at an open stopping they miss by 5.1 to 10.1 m3/s in every one of the three campaigns;
- the open stopping is not one place: west_reef P1-X-03; deep_south P10-X-08; old_shaft P9-X-06; lower_levels P4-X-04;
- at a closure left open the two resistances at which the healthy state ceases are 0.32 to 0.60 per cent apart, and from that closure on the district and its records are in different states for the last 5 survey rounds;
- where the records leave no closure open, the district and its records are in the same state at every round;
- the crew's book for every district holds the package's allowance and a reading for every branch.

Every study below runs complete programs through tests/judge_airflow.py as the verifier does: as nobody, with one thread to a numerical library, with the crew answering through the verifier's `pqsurvey`.

**The reference** (reference_run.txt): accepted on the six districts in runs of 8.7 to 10.5 s, the limit 3.3 times the slowest; accepted on the two examples and, with the crew answering for it, on the pending district; accepted on the seven small districts.

**A correct program that is not fast** (naive_run.txt): authoring/evidence/naive_airflow.py is a second solution written apart from the reference, the district reduced to one resistance by a dense linear-theory iteration at every log entry and the fans carried as a small system of their own. It is accepted on all seven small districts, within 0.30 of the band, and is stopped at the limit on the first of the six.

**Programs written to the visible results** (records_run.txt, made from the reference by authoring/evidence/variants.py, one change each):

| program | the two examples | districts with points out of band | points out at each of those |
|---|---|---|---|
| surveys the airways worked on and nothing else: stoppings as booked, no fan read | accepted | 5 of 6 | 399 to 1019 |
| finds the open stopping and surveys it, reads no fan | accepted | 4 of 6 | 425 to 470 |
| reads a fan with what is left of the allowance, takes every stopping as booked | accepted | 3 of 6 | 399 to 889 |
| the reference with the open stopping's resistance worked out from the campaigns and not surveyed | accepted | 0 of 6 | none: a sound variation, and it is accepted |
| places no survey order at all | not accepted: 1192 and 1772 points out | 6 of 6 | 439 to 2633 |

With only the airways worked on surveyed, the points out of band are deep_south 1019, far_east 470, lower_levels 399, new_incline 0, old_shaft 889, river_block 425. The district with none is the one with neither condition. An open stopping taken as booked puts 399 to 889 points of its district out; a closure that went the other way puts out every point of the last 5 rounds, 425 or 470 points.

**The verifier itself** (verifier_checks.txt, 61 cases, none unexpected; every program is built at run time from the sealed result of a small district).

- Tables accepted: the sealed table with CRLF line ends, no final line end, empty lines, the rows reversed, padded or quoted fields, plus signs, exponent form and fifteen decimals.
- Tables refused: no file, a directory or a symbolic link in its place, bytes that are not text, a file larger than 2000000 bytes; a header missing, misspelt, in capitals or padded, a column more or less; a point left out, given twice or not of the package; an airflow that is empty, not a number, nan or inf, or carries a unit, a decimal comma or a digit separator; and the sealed table followed by exit status 3.
- The band: every airflow at 0.95 of its band, high or low, is accepted, at 1.05 of it is not, and one airflow 2 per cent high among true ones is enough.
- The limit, set to 3 s for the purpose: a program that writes the sealed table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; with two districts to run the second is never started; a child left running in a session of its own is gone after the run.
- The crew during a run: an order of the whole allowance is answered with one row a branch; an order over the allowance, one naming a branch twice or a branch the district does not have, and one through a copy of the package naming another district are refused, and a refused order is not the district's order; a second order is refused; a fan branch, a cut-through and a regulator can be named like any other branch.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest exits 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, an exit status of 1, no report, a report that is not JSON and no airflow.py.

**tests/test.sh as it stands** (verifier_run.txt): `bash tests/test.sh` with the reference at /app/output/airflow.py ends with reward 1; with a program that surveys only the airways worked on, and with the second solution, which is stopped at the limit, reward 0.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned, and the verifier's image carries the same /app/data at the same path. The verifier runs in its own image without network; /tests and /logs/verifier are closed to every account but root, and the program runs as nobody.

Evidence (`authoring/evidence/`): design_rules.txt, reference_run.txt, naive_run.txt, records_run.txt, verifier_checks.txt, verifier_run.txt, regenerate.txt, preflight.txt. Each is the output of the script of the same name, run as its first lines say.

## Submission notes

What the shift in the hidden data is. The visible results (two example districts) come from districts where every stopping is as the register books it, the records decide every stall and recovery, and the survey allowance equals the number of airways worked on. At five of the six hidden districts one or both of two things hold that the records show only in numbers: a stopping passes 5 to 10 m3/s that the register does not account for, seen as a failure of the surveyed airflows to balance at its ends in every campaign; and the record's last bulkhead closure turns within the accuracy of the surveys, so that only a survey of a fan says which way it went. The allowance there is one more for each. Both appear in the visible data, in the pending package /app/data/pending/west_reef, which has no results; the crew does not answer for it where the program is written.

Where it is built.
- Generator config: authoring/provenance/districts.py, the `SITES` table (seed, the draw kept, role, panels, fans, `breach`, `close`) and `make`.
- Manifest: authoring/provenance/manifest.json, the same table and the SHA-256 of every data file; authoring/provenance/regenerate.py makes every file again and compares (authoring/evidence/regenerate.txt).
- Data files: tests/districts/ (the six packages), tests/results/ (their sealed results), tests/crew/books/ (the crew's books for them); environment/data/examples/ and environment/data/pending/ (the visible packages), environment/rig/sealed/ (the crew's books for the two examples); authoring/provenance/as_it_is/ (every district as it is, and the pending district's sealed result and book).
- Check: authoring/provenance/design_rules.py and authoring/evidence/design_rules.txt.

The timed re-run.
- The tests run the program: tests/judge_airflow.py, `run_district`.
- The limit: `LIMIT_S = 35` in tests/judge_airflow.py, and "Each run of airflow.py must finish within 35 seconds on 1 CPU." in instruction.md; preflight fails if they differ.
- The reference takes 8.7 to 10.5 s a run; the limit is 3.3 times the slowest.
- A correct program that is not fast times out: authoring/evidence/naive_airflow.py, authoring/evidence/naive_run.txt.
- A run over the limit ends the judging and nothing it wrote is read: authoring/evidence/verifier_checks.txt.
- Threads: OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in the environment of each run. Runs are not tied to one CPU.
- The cap on OUT_CSV, 2000000 bytes, is in instruction.md with its number.
