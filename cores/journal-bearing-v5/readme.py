#!/usr/bin/env python3
"""Assemble tasks/journal-bearing-survey/README.md. Every figure is lifted from an evidence file, the statement
or the generator, so the README cannot drift from the logs. Kept outside the bundle; run after the evidence is
regenerated, then tools/sync_explanations.py."""
import re

T = "/home/claude/kepler-tasks/tasks/journal-bearing-survey"
EV = T + "/authoring/evidence/"


def ev(name):
    return open(EV + name + ".txt").read()


def grab(text, pattern, group=1):
    m = re.search(pattern, text)
    assert m, pattern
    return m.group(group) if group else m.groups()


ref, naive, reg, rules, checks, vrun, regen = (ev(n) for n in ("reference_run", "naive_run", "register_run",
                                                              "design_rules", "verifier_checks", "verifier_run",
                                                              "regenerate"))
r_lo, r_hi, limit, ratio = grab(ref, r"runs take (\d+\.\d) to (\d+\.\d) s; the limit of (\d+) s is (\d+\.\d) times", 0)
r_err = grab(ref, r"largest error at any point of any site: (\d\.\d+) of its band")
r_points = grab(ref, r"points in all: (\d+)")
pending_order = grab(ref, r"west_quarry .*order: (.*)")
n_rate = grab(naive, r"points in \d+ s: (\d+\.\d+) s a point")
n_wide, n_times = grab(naive, r"is (\d\.\d+) of a band, so every band is at least (\d+) times", 0)
n_lo, n_hi, n_slo, n_shi, n_xlo, n_xhi = grab(
    naive, r"of (\d+) to (\d+) points, would take (\d+) to (\d+) s a run, (\d+) to (\d+) times the limit", 0)
n_thin = grab(naive, r"\n(\d+) points in \d+ s")
n_stop = grab(naive, r"sites run: (\d of \d); stopped: (.*)", 0)
n_cases = grab(checks, r"\n(\d+) cases, 0 unexpected")
held = [l[len("holds   "):] for l in rules.splitlines() if l.startswith("holds ")]
n_rules = grab(rules, r"\n(\d+) rules, 0 not holding")
n_files = grab(regen, r"\n(\d+) files, 0 different")


def rule(start):
    found = [h for h in held if h.startswith(start)]
    assert len(found) == 1, start
    return found[0]


gap_old = grab(rule("in a console that is two charges"), r"differ by (\d+\.\d to \d+\.\d) per cent")
same = grab(rule("two samples of one charge"), r"at most (\d\.\d+) per cent")
step = grab(rule("a charge's analysis moves"), r"at most (\d\.\d+) per cent")
times = grab(rule("the smallest of those differences"), r"is (\d+) times")
gap_new = grab(rule("the two new charges"), r"differ by (\d+\.\d to \d+\.\d) per cent")
mixed = grab(rule("taken as one system"), r"oils, (\d+\.\d to \d+\.\d) per cent")
second = grab(rule("the machine on the second charge"), r"has (\d+ to \d+) operating points at a site, (\d+ to \d+) of them", 0)
sizes = grab(rule("operating points in a package"), r"(\d+ to \d+) beside the program, (\d+ to \d+) where it is run", 0)
span = rule("results at the six sites")[len("results at the six sites: "):]
slope = grab(rule("the oils' viscosity falls"), r"by (\d\.\d to \d\.\d) per cent")

# the register table
kinds = {}
current = None
for l in reg.splitlines():
    m = re.match(r"(register|register_spare|on_file_only): (.*)", l)
    if m:
        current = m.group(1)
        kinds[current] = dict(what=m.group(2), sites=[], examples=None)
    elif current and "the two example sites:" in l:
        kinds[current]["examples"] = l.split(":")[1].strip()
    elif current and "the six sites:" in l:
        kinds[current]["verdict"] = l.strip()[len("the six sites: "):]
    elif current and re.match(r"\s+\w+\s+\d+\.\d s\s+\d+ of\s+\d+ points out of band", l) and "verdict" in kinds[current]:
        name, out = re.match(r"\s+(\w+)\s+\d+\.\d s\s+(\d+) of", l).groups()
        kinds[current]["sites"].append((name, int(out)))
label = {"register": "one sample for each listed system that was renewed; the rest of the allowance unused",
         "register_spare": "the same, with the rest of the allowance spent on machines not yet sampled, a machine "
                           "whose own sample stands apart keeping its own figures",
         "on_file_only": "machines sorted into charges by analysis for the oil on file, but one sample for each "
                         "listed system that was renewed"}
reg_rows = []
for kind in ("register", "register_spare", "on_file_only"):
    k = kinds[kind]
    out = [o for _, o in k["sites"] if o]
    reg_rows.append("| %s | %s | %d of 6 | %d to %d |" % (label[kind], k["examples"], len(out), min(out), max(out)))
reg_table = "| program | the two example sites | sites with points out of band | points out at each of those |\n|---|---|---|---|\n" + "\n".join(reg_rows)
reg_sites = ", ".join("%s %d" % (n, o) for n, o in kinds["register"]["sites"])
rule_list = "\n".join("- " + h[0].lower() + h[1:] + (";" if i < len(held) - 1 else ".") for i, h in enumerate(held))

DESCRIPTION = re.search(r'^description = "(.*)"$', open(T + "/task.toml").read(), re.M).group(1)

DIFFICULTY = """This is the work of a tribology engineer who keeps a works group's bearing calculation standard and the program that applies it. A plain journal bearing carries its shaft on an oil film a few tens of micrometres thick, and whether a machine may run at a given speed, load and oil temperature is decided by that film: how thin it gets, how much power it dissipates, how hot it runs and how hard it presses on the lining. The task is a program that finds these five quantities for every operating point on record at a site, to within 1.5 per cent, 1 degree and 0.5 K, within 60 seconds for a site, at sites whose oil has been renewed and has to be sampled before it can be calculated with. The sites, their records and the standard are synthetic and realistic: journals of 90 to 200 mm at 600 to 3560 rpm on ISO VG 32 to 68 mineral oils, and at the six sites the program is run on, {span}.

Four pieces of physics set every answer, and they have to be solved together.

- **The film.** The pressure obeys the Reynolds equation for a finite bearing with two axial grooves: an elliptic equation in the angle round the bearing and the axial coordinate, driven by the wedge the journal makes with the bush, with the pressure zero at the two ends and along each groove. At these length to diameter ratios there is no closed form; the short-bearing and long-bearing formulas both leave out a flow that matters here.
- **Rupture.** Oil does not carry tension. Where the equation would give a pressure below zero the film breaks, and where it breaks is part of the solution: the pressure and its gradient vanish together on a boundary that is not known in advance. The pressure field is the solution of a complementarity problem, not of one linear system.
- **Equilibrium.** The journal's position is not given. Eccentricity and attitude are where the resultant of the ruptured film equals the load in size and direction, two nonlinear conditions wrapped round the film.
- **Heat.** All the power lost in the film leaves with the oil, and these oils lose {slope} per cent of their viscosity for each K. The film runs {rise} K above the inlet, so the viscosity that sets the film is fixed by the loss that the film sets. Temperature, viscosity, position and loss are one fixed point.

The oil is the fifth unknown, and it is a measurement problem. The standard takes a bearing's oil from the laboratory's analysis of the charge that was in its supply, not from the grade: charges as delivered differ from the grade's nominal figures by up to 15 per cent, and every one of the five results moves with the viscosity. Most systems at these sites were drained and refilled in January 2026, so the oil now in most bearings has never been analysed. The laboratory analyses a fixed number of samples for a site, in one order, and the program has to place that order itself, while it runs, before it has seen a single result.

What has to be sampled is every body of oil that was renewed, and a body of oil is a physical thing, not a line of a register. Bearings fed from one reservoir give one analysis, within what the laboratory repeats; bearings that give two do not share a reservoir, whatever the register says. That is the measurement that settles it, and it is on file:

- two samples of one charge taken in the same round differ by at most {same} per cent in viscosity, and a charge moves by at most {step} per cent from one round to the next;
- at some sites one console that the register lists as a single system has given, at one of its three machines, analyses {gap_old} per cent away from the other two in every one of the four sample rounds, {times} times the largest difference between two samples of one charge;
- at those sites the laboratory's allowance is one more than the number of systems the register shows renewed.

Such a console is two reservoirs. Taken as one, its oil on file is the mean of two different oils, {mixed} per cent from either, and after the renewal one sample stands for two new charges that differ by {gap_new} per cent. The machine on the second reservoir has {second_points} operating points at a site. Nothing in the records says any of this in words, and the two example sites do not have such a console: there the register's systems are the charges and the allowance equals their number. The third visible package, the one without results, has one.

The time limit is the other half of the work. The standard asks for results converged to 0.2 per cent, a site has {hidden_sizes} points, and a run has 60 seconds on one CPU, a few hundredths of a second a point. Solving the film as one general sparse system, with the heat balance iterated outside the equilibrium and each point started cold, takes {n_rate} s a point, {n_xlo} to {n_xhi} times the limit for a site. Meeting the limit takes the structure of the problem. The grooves cut the film into separate lands whose equations are banded. And once the viscosity is taken out, a laminar film's force and peak pressure depend only on where the journal sits, so the film can be solved once for each bearing geometry on a grid of journal positions and every point of that geometry found from the table, with position, attitude and temperature as the three unknowns of one Newton iteration carried out for all points at once.

Its research analogue is thermohydrodynamic lubrication analysis as a bearing design code does it: a free-boundary elliptic problem coupled to a force balance and an energy balance, made fast by a similarity reduction to a tabulated dimensionless solution. The oil adds the question that precedes any calibration: deciding from the measurements themselves which physical population each belongs to, and planning a fixed number of new measurements before any of them is known.

Each of these defeats an assumption the general approach makes on first reading:
- that a finite grooved bearing can be had from a short-bearing formula or from a film that is whole all round;
- that the viscosity can be taken at the inlet temperature, or from the grade;
- that a few thousand points can each be solved from scratch inside the limit;
- that the register's list of oil systems is the list of charges;
- that an allowance of one more sample than the register needs has one to spare."""

SOLUTION = """solution/bearing.py is the reference; solution/solve.sh puts it at /app/output/bearing.py. It reads one package, places the laboratory order and writes the table.

1. **Charges.** The machines of each listed system are sorted into charges by the analyses on file: two machines are on different charges when the analyses drawn at them nearest in date stand more than 3 per cent apart in viscosity at 40 C, six times what the laboratory repeats. A machine with no analysis stays with the first charge of its system.
2. **The order.** One sample from every charge whose system the oil log shows renewed, at the first bearing fed from it, placed through `labsample` in a single order.
3. **The oil of a point.** After the renewal, the laboratory's figure for the bearing's charge. Before it, and for a charge that was not renewed, the charge's latest analysis on file, the mean of that date's samples (LS-3 section 7).
4. **Bearing states and geometries.** Points are grouped by bearing and oil. Films that share a length to diameter ratio and groove positions share one dimensionless solution.
5. **The table.** For each geometry the laminar film is solved on a grid of 28 eccentricities by journal angles 4.5 degrees apart: resultant force, its direction and the peak pressure, each as a spline surface. Each land between two grooves is a banded system of half-width 16, with rupture as an active set started from the neighbouring solution.
6. **The points.** All points of a bearing state are solved from the table at once: a Newton iteration on eccentricity, attitude and film temperature, with the Walther viscosity and the heat balance inside it. The friction comes from the Couette term in closed form and the moment of the film's resultant.
7. **What the table cannot settle.** A point off the table's edge, or whose film is not laminar, is solved directly on the same banded lands with the same three unknowns, on 144 by 16 nodes and on 192 by 20 above an eccentricity of 0.75.

**On the shipped sites** (authoring/evidence/reference_run.txt, run by the checker as the verifier runs it) the reference is accepted: {r_points} points at six sites, the largest error at any of them {r_err} of its band, runs of {r_lo} to {r_hi} s, so the limit of {limit} s is {ratio} times the slowest run. It is accepted on both example sites as well, and on the pending package it orders {pending_n} samples, {pending_order}: two of them from the console LO-2.

**authoring/evidence/naive_bearing.py** is a second solution, written apart from the reference and sharing no code with it. It joins machines into charges through a graph, with a threshold of 2 per cent, and solves the film as one sparse system over the whole bearing on 144 by 16 nodes, grooves included, with the journal position found inside a bracketing search on the film temperature, one point at a time. On the six sites cut down to every 40th point ({n_thin} points) it places the same orders as the reference and is accepted, and its widest departure from the sealed results is {n_wide} of a band (authoring/evidence/naive_run.txt)."""

VERIFICATION = """The deliverable is a program, /app/output/bearing.py. The verifier does not read anything the agent's run left behind: tests/grade_program.py, run by the one pytest test in tests/test_program.py, runs the program on six site packages it has not seen and compares what each run writes with sealed results.

**A run.** For each site, a scratch directory holds a copy of bearing.py alone and a read-only copy of the package. The program is started there as `python3 bearing.py PACKAGE_DIR OUT_CSV`, as the user nobody, held to one CPU, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, in a process group of its own, with no network.

**The limit.** Each run has 60 seconds from start to exit, the same figure as the task statement's sentence "Each run of bearing.py must finish within 60 seconds on 1 CPU." (preflight compares the two). It is enforced by a timeout on the wait for the process, in tests/grade_program.py. A run that is still going at 60 s ends the assessment: its process group and every process of nobody are killed, nothing it wrote is opened, no later site is run, and the program is not accepted. There is no share of sites or points that lets such a run through.

**The laboratory.** During a run the checker is the laboratory. `labsample` in the verifier's image passes the order to the checker, which answers by the same rule as the agent's laboratory (tests/lab/lab.py is the same file as environment/rig/lab.py): one order for the site, of at most the package's allowance, written down before any figure is given; a second order is refused. The books are readable by root alone. In the agent's image the laboratory is a separate account reached through one sudo rule, and there it answers for the three visible sites only.

**Acceptance.** Every run must finish in time with exit status 0, every OUT_CSV must be the table the statement describes, and for every point of every site the minimum film thickness, the power loss and the peak pressure must be within 1.5 per cent of the sealed result, the attitude angle within 1 degree and the effective temperature within 0.5 K. One pytest test carries the reward. tests/test.sh writes 0 first and writes 1 only when pytest exits 0 and tests/read_report.py finds that the ctrf report shows exactly 1 test, 1 passed.

**The reader** holds the table to the statement and no further. The header must be exactly the one given; there must be one row for every point of the package and none for anything else; each value must be a finite decimal number. Row order, line ends, a final terminator, empty lines, quoting and blanks round a field are not stated and are not judged.

**The truth** is the sealed definition authoring/provenance/film.py, run by authoring/provenance/sites.py for the oil each bearing really drew: every point solved directly on 240 by 24 nodes, with no table. It is never a run of the reference, which tabulates the film on coarser grids. authoring/provenance/regenerate.py makes the nine sites again from the generator and finds all {n_files} shipped data files the same byte for byte (authoring/evidence/regenerate.txt); authoring/provenance/manifest.json lists them with their SHA-256.

**The bands** are checked against a separately written solution. authoring/evidence/naive_bearing.py shares no code with the reference or with the sealed definition, and its widest departure from the sealed results is {n_wide} of a band, so every band is at least {n_times} times the widest departure of an independent, correct method. The reference's largest error is {r_err} of a band. A correct standard method is accepted with room to spare; nothing depends on matching a particular discretisation.

**What the six sites are, and how they differ from the visible data.** They are six other sites, none of them a visible one and none sharing a file with one. The difference is built in on purpose and is not a new seed of the visible sites:
- at the two example sites, whose results the agent has, every system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed;
- at five of the six sites one console that the register lists as a single system is two reservoirs, both renewed, in a console of a different number and grade from site to site; the allowance there is the number of charges, one more than the register's count; the sixth site has no such console;
- the condition is present in the visible data: the pending package, /app/data/pending/west_quarry, has such a console (LO-2), with the same two signs, and the agent's laboratory answers for it.
It is built in authoring/provenance/sites.py: the `SITES` table gives each site's role and which console is two charges, and `describe` builds the charges, the analyses on file and the allowance from it.

authoring/provenance/design_rules.py recomputes the design rules from the generator's description of each site and the shipped files (authoring/evidence/design_rules.txt; {n_rules} of {n_rules} hold):
{rule_list}

Every study below runs complete programs through tests/grade_program.py as the verifier does: as nobody, on one CPU, with the laboratory answering through the verifier's `labsample`.

**A correct program that is not fast** (naive_run.txt). The second solution is accepted on the cut-down sites, where the limit is set aside, at {n_rate} s a point. At that rate the sites as they are, of {n_lo} to {n_hi} points, would take {n_slo} to {n_shi} s a run, {n_xlo} to {n_xhi} times the limit. Run on them at the limit, it is stopped: sites run {n_stop0}, {n_stop1}, not accepted.

**Programs written to the visible results** (register_run.txt, made from the reference by authoring/evidence/variants.py, one change each):
{reg_table}

With one sample for each listed system the points out of band are {reg_sites}. The site with none is the one without such a console.

**The verifier itself** (verifier_checks.txt, {n_cases} cases, none unexpected; every program is built at run time from the sealed results of a cut-down site).
- Tables refused: nothing written, OUT_CSV as a directory or as a symbolic link to a file holding the true table, an empty file, the header alone, no header, a misspelt, capitalised or padded header, a column added or left out, a row of five fields, a point left out, given twice, unknown or in lower case, a value empty, n/a, nan, inf, with its unit, with a decimal comma or with a digit separator, bytes that are not UTF-8, a file over the size cap, and the true table followed by exit status 3.
- Tables accepted: the true table with CRLF line ends, no final terminator, empty lines, the rows reversed, padded or quoted fields, plus signs, and exponent form.
- Bands: each quantity moved to just inside its band at every point is accepted (1.4 per cent, 0.9 degrees, 0.45 K) and to just outside is not (1.6 per cent, 1.1 degrees, 0.55 K); one point of a site with its power loss 2 per cent high is enough to refuse the program.
- The limit, set to 3 s for the purpose: a program that writes the true table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; with two sites to run the second is never started; a program that exits in time and leaves a child running in a session of its own is accepted and the child is killed.
- The laboratory during a run: an order over the allowance, an order naming a bearing the site does not have and an order through a package naming another site are refused and do not count as the site's order; the order after them is taken; a second order is refused; outside a run nothing answers.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest exits 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, a failing exit with a passing report, no report, a report that is not JSON, and no bearing.py delivered.

**The whole verifier** (verifier_run.txt). pytest on tests/test_program.py in a process of its own exits 0 for the reference and 1 for the program that samples by the register and for the second solution at the limit.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned, and the verifier's image carries the same /app/data at the same path. The verifier runs in a separate container without network; /tests and /logs/verifier are readable by root alone, and the program runs there as nobody."""

NOTES = """What the shift in the hidden data is. The visible results (two example sites) come from sites where every oil system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed. At five of the six hidden sites one listed console is two reservoirs, both renewed, so the right laboratory order has one more sample than the register's count and the machine on the second reservoir has a different oil before and after the renewal. The condition appears once in the visible data, in the package without results (/app/data/pending/west_quarry, console LO-2). The hidden sites are other sites: no name and no file is shared with a visible one. A program that follows the register reproduces both visible result sets and is out of band at five hidden sites (authoring/evidence/register_run.txt).

Where it is built.
- Generator config: authoring/provenance/sites.py, the `SITES` table (seed, role, the console that is two charges, number of consoles and of self-contained machines) and `describe`.
- Manifest: authoring/provenance/manifest.json, the same table and the SHA-256 of every data file.
- Data files: tests/sites/ (the six packages), tests/sealed/truth/ (their results), tests/lab/sealed/ (the laboratory's books for them); environment/data/examples/ and environment/data/pending/ (the visible packages), environment/rig/sealed/ (the laboratory's books for those).
- Check: authoring/provenance/design_rules.py and authoring/evidence/design_rules.txt.

The timed re-run.
- The tests run the program: tests/grade_program.py, `run_site`.
- The limit: `RUN_LIMIT_S = 60` in tests/grade_program.py, and "Each run of bearing.py must finish within 60 seconds on 1 CPU." in instruction.md; preflight fails if they differ.
- The reference takes {r_lo} to {r_hi} s a run; the limit is {ratio} times the slowest.
- A correct program that is not fast times out: authoring/evidence/naive_bearing.py, authoring/evidence/naive_run.txt.
- A run over the limit ends the assessment and nothing it wrote is read: authoring/evidence/verifier_checks.txt, "The limit".
- Threads: OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in the environment of each run, which is also held to one CPU."""

rise = grab(span, r"film (\d+\.\d to \d+\.\d) K above the inlet")
vals = dict(span=span, slope=slope, rise=rise, same=same, step=step, gap_old=gap_old, times=times, mixed=mixed,
            gap_new=gap_new, second_points=second[0], hidden_sizes=sizes[1], n_rate=n_rate, n_xlo=n_xlo, n_xhi=n_xhi,
            r_points=r_points, r_err=r_err, r_lo=r_lo, r_hi=r_hi, limit=limit, ratio=ratio,
            pending_n=len(pending_order.split()), pending_order=pending_order.strip().replace(" ", ", "), n_thin=n_thin,
            n_wide=n_wide, n_times=n_times, n_files=n_files, n_rules=n_rules, rule_list=rule_list, n_lo=n_lo, n_hi=n_hi,
            n_slo=n_slo, n_shi=n_shi, n_stop0=n_stop[0], n_stop1=n_stop[1], reg_table=reg_table, reg_sites=reg_sites,
            n_cases=n_cases)

readme = """# journal-bearing-survey

{description}

## Difficulty

{difficulty}

## Reference solution

{solution}

`solution/solve.sh` starts it inside the agent's container: it copies bearing.py to /app/output and runs it once on the three packages in /app/data, checking the two example sites against their results.

## Verification

{verification}

Evidence (`authoring/evidence/`): `reference_run.txt`, `naive_run.txt`, `register_run.txt`, `verifier_checks.txt`,
`verifier_run.txt`, `design_rules.txt`, `regenerate.txt` and `preflight.txt`.

## Submission notes

{notes}
""".format(description=DESCRIPTION, difficulty=DIFFICULTY.format(**vals), solution=SOLUTION.format(**vals),
           verification=VERIFICATION.format(**vals), notes=NOTES.format(**vals))
open(T + "/README.md", "w").write(readme)
print(len(readme), "chars")
