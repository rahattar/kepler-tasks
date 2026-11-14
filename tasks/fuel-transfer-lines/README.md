# fuel-transfer-lines

Write a program that gives the pressure drop and the outlet temperature at every hourly record of a fuel terminal's heated oil transfer lines, single pipes and pairs of pipes between common manifolds: it takes each covering's outside coefficient from the heat-loss surveys on file, decides from those surveys what the site's one survey order has to read and places it while it runs, and carries every pair's division of the oil through its hours. The tests re-run the program on six other sites under a time limit.

## Difficulty

This is the work of the engineer who keeps a fuel terminal's line calculation standard and the program that applies it. Fuel oil of heavy grades, and vacuum gas oil, leaves a heater at 66 to 93 C and is pumped to the plant it feeds through covered lines 200 to 890 m long, either a single pipe or a pair of pipes laid side by side between one inlet and one outlet manifold. For every hourly record the standard asks for the pressure drop across the line and the temperature of the oil delivered: 1240 to 1285 records at a site of 30 lines and 50 pipes, each line followed for 36 to 48 hours of service.

Three things decide every answer, and each is needed for the other two.

- **The pipe.** The oil loses heat through an inside film and the pipe's covering in series, and its viscosity, by ASTM D341, changes by a factor of ten and more over the temperatures it passes through. The heat balance, the film of thermally developing laminar flow with its wall-viscosity correction and the laminar friction with its own are one integration along the pipe, with the wall temperature found at every station.
- **The pair.** Two pipes between the same manifolds carry the oil in whatever division gives them one pressure drop. A pipe that is given less oil cools more, its oil thickens, and below some delivered flow its pressure drop rises as its flow falls, so that a pair has three or five such divisions. TS-2 states which one holds: oil shifts from the pipe with the higher drop to the other, starting from the division of the previous record. As the delivered flow falls, one pipe's share collapses to a trickle of cold oil, and when the flow rises again the pair stays collapsed until that division ceases to exist. 175 of the 180 pairs at the nine sites collapse at some hours, so each line's run of records is a history and is calculated in hour order.
- **The coverings.** No pipe's outside coefficient is given. It is what a heat-loss survey found: the coefficient for which the standard returns the outlet temperature that was read, with the flow, the inlet temperature and the surroundings that were read. Three campaigns of every pipe are on file. A covering renewed or repaired after the last campaign is not the covering that was surveyed (it has 0.42 to 0.74 times the coefficient on file), and the survey crew will survey pipes as they stand today, in one order of a fixed number of pipes that the program places itself while it runs. Each site has 3 or 4 such pipes, and without the order even the two examples are out of band at every record of those lines.

What the order has to read is the fourth part of the work, and it is a question about measurements, not about the register. Two things are in the surveys in numbers and nowhere in words.

- **A pipe of a pair that is narrower than laid.** At some sites one pipe of a pair has lost bore to deposit, 11.2 to 12.3 per cent of it as it stands today. The lines register gives the bore as laid, and pipes are not gauged in service. The surveys show it: a survey of a pair's pipe reads the oil delivered to the line as well as the flow through the pipe, so every campaign gives the pair's division, and 4.1 says the two pipes have one pressure drop. With the register's bore for both, their pressure drops at the flows read are 0.142 to 0.185 apart in ln in every one of the three campaigns, where at 176 sound pairs they agree within 0.010. The cure is two steps: survey the pipe today, and solve its bore so that, with the coefficient that bore gives from the new reading, its pressure drop equals its mate's at the flows read. A heat balance read with the wrong bore gives the wrong coefficient, so ordering the pipe and keeping the register's bore puts every record of its line out of band, by up to 18.6 times the tolerance.
- **A covering that is failing.** At some sites one pipe's coefficient on file rises from campaign to campaign with no work logged: by 0.163 to 0.210 in ln between the last two, where with no work on it no other pipe's moves by more than 0.022, which is what the reading accuracy of TS-2 5.4 allows. Today it stands 1.47 to 1.62 times its last survey. Taken from the file, it puts every record of its line out, by up to 15.4 times the tolerance.

At those sites the crew's allowance is one pipe more than the covering jobs for each of the two, so a site with both has two places more than its work log accounts for, and nothing says what they are for. The two examples, whose results are given, have neither and an allowance that is exactly their covering jobs, so a program that surveys those pipes, takes the rest from file and follows the pairs by TS-2 4.2 reproduces both sets of results. The pending site, west_jetty, whose package is given without results, has both: FL-212-A is the narrowed pipe and FL-224-A the failing covering. Where the program is written the crew answers for the two examples only, so at the pending site the surveys on file are the evidence and nothing answers back.

The time limit is the other half of the work: 40 seconds on one CPU for a site of up to 60 pipes and 1500 records. At every record of a pair the difference of the two pipes' pressure drops has to be had across the whole range of divisions to find them all, each value an integration along two pipes, and a coefficient from a reading or a bore from a division is a root of such integrations in turn. The second solution in authoring/evidence, written apart from the reference, takes each pipe with scipy's adaptive integrator and each root with brentq, one case at a time; it is right on small sites and is stopped at the limit on the first of the six. As first written it takes 100 s of CPU for a small site of 250 records. The same method made fast, every case of a kind in one array, runs a full site in 15.8 to 17.9 s, and the reference in 11.6 to 14.8 s.

The data is synthetic and realistic: terminals of a refinery's or a power station's fuel-oil system, with heavy fuel oils, bores, lengths, coverings and heater outlet temperatures in the range of working plant, and survey campaigns, a work log and hourly records as a terminal's engineering office keeps them. The research analogue is flow maldistribution in parallel channels carrying a fluid whose viscosity rises steeply as it cools, the viscous counterpart of the Ledinegg instability of boiling channels, met in heavy-oil and waxy-crude lines, in magma conduits and in compact heat exchangers; and with it the inference of fouling and deposit in a network from the measurements that are taken anyway, a parameter that has left its register value found from conservation and consistency rather than from a flag.

Each of these defeats an assumption the general approach makes on first reading:

- that a pair's division follows from the conditions of its hour;
- that two pipes laid alike carry the oil alike;
- that the bore on the register is the bore of the pipe;
- that a coefficient on file is the coefficient today when no work is logged against it;
- that a survey of a pipe gives its coefficient whatever bore it is read with;
- that an allowance larger than the work log needs has places to spare;
- that every record can be integrated case by case with a library integrator inside the limit.

## Reference solution

solution/lines.py is the reference; solution/solve.sh puts it at /app/output/lines.py. It reads one package, places the survey order and writes the table.

1. **Coefficients on file.** For every pipe and every campaign, the outside coefficient for which TS-2 3.1 to 3.3 return the outlet temperature read, with the register's bore (`coefficients_on_file`). The pipe is integrated along 50 stations crowded towards the inlet, each step with the local decay of the oil's excess temperature at its middle and the wall temperature by iteration (`march`); a coefficient is a root in ln Uo by the Illinois method (`coefficient`).
2. **What the order reads** (`pipes_to_survey`). The pipes with a covering job after the last campaign, from the work log. In each pair, the pressure drops of the two pipes at the flows of each campaign: where they differ by more than 0.06 in ln the same way in all three campaigns, the pipe with too little drop for its flow is narrower than laid. And every pipe whose coefficient moves by more than 0.05 in ln between the last two campaigns with no covering job between. The three lists, in that order, up to the allowance, go in one `heatsurvey` order.
3. **The pipes as they stand** (`as_they_stand`). A surveyed pipe takes the coefficient of its new reading. A narrower pipe takes the bore at which, with the coefficient that bore gives from the new reading, its pressure drop equals its mate's at the mate's flow in the same reading: 24 trial bores at once, three times over, then the coefficient again with that bore.
4. **The records** (`calculate`). Single pipes in one sweep. For every record of a pair, the difference of the two pressure drops at 64 divisions from a trickle to the whole flow, every division where it changes sign refined by the Illinois method (`divisions`). Each pair is then taken through its records in hour order: the first takes its one division (4.3), every later one the next division below the held one when the drops there send oil out of pipe A and the next above otherwise (4.2).
5. **The table.** `record,dp_kPa,t_out_C`, one row for every record.

## Verification

The deliverable is a program, /app/output/lines.py. The verifier does not read anything the agent's run left behind: tests/rerun.py, called by the one pytest test in tests/test_lines.py, runs the delivered program on six sites it has never seen and compares every result with the sealed one. tests/test.sh writes the reward: 1 if that one test passed and its report says so, 0 otherwise.

**A run.** For each site in turn a scratch directory is laid out with a copy of lines.py alone and a copy of the package that the program can read and not change. The program is started there as the user nobody, in a session of its own, with one thread to a numerical library and no network, as `python3 lines.py PACKAGE_DIR OUT_CSV`. It has 40 seconds on 1 CPU, held two ways: 40 seconds on the clock, and 40 seconds of CPU time, user and system, added over the program and every process it starts. No CPU affinity is set. The `heatsurvey` on the PATH leaves the program's order at the crew's desk, which rerun.py keeps for the length of the run: it answers one order for that site from books under /tests that nobody cannot open, by the rule in tests/crew/lab.py, the same file the agent's `heatsurvey` runs. At exit or at the limit every process of the run is killed. A run over the limit ends the judging and nothing it wrote is opened. Otherwise OUT_CSV has to be the table the statement describes, no larger than 1000000 bytes, with one row for every record and no other, and at every record the pressure drop within 2.5 per cent and the outlet temperature within 0.5 K of the sealed result.

**Why the band.** The sealed result is the site as it is, from the sealed definition in authoring/provenance (oil_line.py, oil_pair.py) at 480 stations a pipe, with the pipes' true bores and coefficients and nothing shared with the reference but the standard. A program has the coefficients and the narrowed bores only as surveys give them, read to 0.2 per cent in flow, 0.02 K in oil temperature and 0.1 K in the surroundings, so its results differ from the sealed ones by what that does to a line. The pressure drop goes as the inverse fourth power of the bore, so the widest departure is at a narrowed line, where the bore is solved from one reading: on canal_basin's FL-216 the reference and the second solution, written apart, are both about 1 per cent off, 0.40 of the band. Everywhere else both are within 0.30 of it, and on the examples and the pending site within 0.18. The band is 2.5 times the widest departure, and the departure is the reading's, not a method's: the reference at 120 stations instead of 50 has the same largest error.

**What the six sites are, and how they differ from the visible data.** They are six other sites, none of them a visible one and none sharing a record file with one. The difference is built in on purpose and is the one described under Difficulty:

- at the two examples, whose results the agent has, no pipe is narrower than laid, no covering is failing, and the allowance is the number of covering jobs since the last campaign;
- 3 of the six have a narrowed pipe (south_wharf, canal_basin, upper_yard) and 4 a failing covering (south_wharf, canal_basin, kiln_road, tank_row); boiler_lane has neither; the narrowed pipe and the failing covering are a different pipe at every site;
- both conditions are in the visible data: the pending package, /app/data/pending/west_jetty, has FL-212-A narrowed and FL-224-A failing, with an allowance two above its covering jobs. Where the program is written the crew does not answer for that site, and site_package.md says so.

It is built in authoring/provenance/sites.py: the `SITES` table gives each site its seed, its role and whether it has a narrowed pipe and a failing covering, and `draw_site` and `build` draw the site, check it and write it. A line is drawn again until its survey rating and all its records are laminar in every pipe, and a record is refused unless the division of every pair at every hour is the same with the flows 4 per cent higher or lower and with each hour taken in six steps. A site is drawn again if any reading moves its outlet temperature by less than 0.15 K for a coefficient 1.1 times higher rather than lower, which is where the inside film carries nearly all of the resistance and no survey can say what the covering is.

authoring/provenance/design_rules.py recomputes the design rules from the shipped files (authoring/evidence/design_rules.txt; 21 of 21 hold):

- 9 sites: 2 with results beside the program, 1 without, 6 the program is run on; no name twice, and no lines, surveys, work log or records file of a site run on is one of a site written beside;
- a package holds 30 lines, 50 pipes and 1240 to 1285 records; site_package.md gives at most 60 pipes and 1500 records;
- every survey on file, every pipe as the crew reads it today and every record is laminar in every pipe: the largest Reynolds number is 1550, against TS-2's 2000;
- the pipes with a covering job after the last campaign are the ones the site was built with, and have 0.42 to 0.74 times the coefficient of their last survey;
- the allowance is the covering jobs, one more for a narrowed pipe and one more for a failing covering;
- every reading on file and every reading the crew gives says what the covering is: with the coefficient 1.1 times higher rather than 1.1 times lower its outlet temperature moves by 0.206 K or more, against a reading accuracy of 0.02 K;
- at a sound pair the two pressure drops at the flows read agree within 0.010 in ln in every campaign (176 pairs); at a pair with a narrowed pipe they are 0.142 to 0.185 apart in every campaign;
- with no covering job between the last two campaigns a pipe's coefficient moves by at most 0.022 in ln (427 pipes); a failing covering's moves by 0.163 to 0.210;
- 175 of the 180 pairs collapse at some record; every pair's run opens where one division only satisfies 4.1.

Every study below runs complete programs through tests/rerun.judge as the verifier does: as nobody, timed on the clock and in CPU, with the crew answering through the verifier's `heatsurvey`.

**The reference** (reference_run.txt): accepted on the six sites in runs of 11.6 to 14.8 s of CPU, the limit 2.7 times the slowest; accepted on the two examples and, with the crew answering for it, on the pending site; accepted on the nine small sites.

**The second solution** (second_run.txt): written apart from the reference. As first written, authoring/evidence/plain_lines.py, it is right on three small sites (one with both conditions, one with each) with the limit lifted, in 100.3 to 102.2 s of CPU for some 250 records, and is stopped at the limit on the first of the six. Made fast, authoring/evidence/second_lines.py, it is accepted on the nine small sites, the three visible ones and the six, the six in runs of 15.8 to 17.9 s.

**Programs written to the visible results** (records_run.txt, made from the reference by authoring/evidence/variants.py, one change each):

| program | the two examples | sites of the six with records out of band |
|---|---|---|
| surveys the pipes with a covering job and nothing else | accepted | 5 of 6 |
| never compares a pair's division with one pressure drop | accepted | 3 of 6 |
| never compares a coefficient from campaign to campaign | accepted | 4 of 6 |
| surveys the narrowed pipe and takes its coefficient with the register's bore | accepted | 3 of 6 |
| finds the narrowed pipe, does not survey it, its bore from the last campaign | accepted | 3 of 6 |
| places no survey order at all | not accepted | 6 of 6 |

Three sound variations (120 stations for 50; other thresholds for the two checks; the order in reverse) are accepted on the examples and on the six.

**The verifier itself** (verifier_checks.txt, every case built at run time from the sealed result of a small site; none unexpected).

- Tables accepted: CRLF line ends, no final line end, empty lines, the rows reversed, padded or quoted fields, plus signs, exponent form and fifteen decimals.
- Tables refused: no file, a directory or a symbolic link in its place, bytes that are not text, a file larger than 1000000 bytes; a header missing, misspelt, in capitals or padded, a column more or less; a record left out, given twice or not of the package; a value that is empty, a word, nan or inf, carries a unit, a decimal comma, a digit separator or is hexadecimal; and the sealed table followed by exit status 3.
- The band: every pressure drop 2.4 per cent high or low and every outlet temperature 0.45 K high or low is accepted, 2.6 per cent and 0.55 K is not, and one value out among true ones is enough to refuse.
- The limit, set to 3 s for the purpose: a program that writes the sealed table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; the CPU time of processes it starts is counted with its own, and one that keeps two of them busy is over the limit; with two sites to run the second is never started; a process left running in a session of its own is gone after the run.
- The crew during a run: an order of the whole allowance is answered with one row a pipe in the order asked; an order over the allowance, one naming a pipe twice or a pipe the site does not have, and one through a copy of the package naming another site are refused, and a refused order is not the site's order; a second order is refused; the package cannot be written to.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest exits 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, an exit status of 1, no report, a report that is not JSON and no lines.py.

**tests/test.sh as it stands** (verifier_run.txt): `bash tests/test.sh` with the reference at /app/output/lines.py ends with reward 1; with a program that surveys only the pipes with a covering job, and with the second solution as first written, which is stopped at the limit, reward 0.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root's, and the verifier's image carries the same /app/data at the same path. The verifier runs in its own image without network; /tests and /logs/verifier are closed to every account but root, and the program runs as nobody.

## Submission notes

- **The time limit** is 40 s a run on 1 CPU, the same number in instruction.md and in tests/rerun.py (`LIMIT_S`). The reference takes 11.6 to 14.8 s of CPU a site, so the limit is 2.7 times its slowest run. A correct but unoptimised version, authoring/evidence/plain_lines.py, is right and is stopped at the limit (second_run.txt); a timeout fails the whole task. Threads are held to one in both images and in the run's own environment.
- **The shift in the hidden data** is deliberately built, not a reseed: the six sites carry a narrowed pipe of a pair and a failing covering in the combinations listed under Verification, conditions the two examples with results do not have and the pending visible package does. It is built in authoring/provenance/sites.py, `SITES`; manifest.json lists every data file with its SHA-256, and regenerate.txt shows sites.py making all of them again byte for byte.
- **Evidence** (authoring/evidence/): reference_run, second_run, records_run, verifier_checks, verifier_run, design_rules, regenerate and preflight, each a .py with its .txt. preflight.py checks the playbook's rules on the files and runs a few live cases.
