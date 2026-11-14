#!/usr/bin/env python3
"""Assemble tasks/lube-oil-survey/README.md. Every figure is lifted from an evidence file, the statement
or the generator, so the README cannot drift from the logs. Kept outside the bundle; run after the evidence is
regenerated, then tools/sync_explanations.py."""
import re

T = "/home/claude/kepler-tasks/tasks/quench-oil-survey"
EV = T + "/authoring/evidence/"


def ev(name):
    return open(EV + name + ".txt").read()


def grab(text, pattern, group=1):
    m = re.search(pattern, text)
    assert m, pattern
    return m.group(group) if group else m.groups()


ref, naive, reg, rules, checks, vrun, regen, conv = (ev(n) for n in ("reference_run", "naive_run", "register_run", "design_rules", "verifier_checks", "verifier_run", "regenerate", "convergence"))
r_lo, r_hi, limit, ratio = grab(ref, r"runs take (\d+\.\d) to (\d+\.\d) s; the limit of (\d+) s is (\d+\.\d) times", 0)
r_err = grab(ref, r"largest error at any load of any site: (\d\.\d+) of its band")
r_points = grab(ref, r"loads in all: (\d+)")
pending_order = grab(ref, r"west_quarry .*order: (.*)")
n_rate = grab(naive, r"loads in \d+ s: (\d+\.\d+) s a load")
n_wide, n_times = grab(naive, r"is (\d\.\d+) of a band, so every band is at least (\d+) times", 0)
n_lo, n_hi, n_slo, n_shi, n_xlo, n_xhi = grab(
    naive, r"of (\d+) to (\d+) loads, would take (\d+) to (\d+) s a run, (\d+) to (\d+) times the limit", 0)
n_thin = grab(naive, r"\n(\d+) loads in \d+ s")
n_stop = grab(naive, r"sites run: (\d of \d); stopped: (.*)", 0)
n_cases = grab(checks, r"\n(\d+) cases, 0 unexpected")
held = [l[len("holds   "):] for l in rules.splitlines() if l.startswith("holds ")]
n_rules = grab(rules, r"\n(\d+) rules, 0 not holding")
n_files = grab(regen, r"\n(\d+) files, 0 different")


def rule(start):
    found = [h for h in held if h.startswith(start)]
    assert len(found) == 1, start
    return found[0]


gap_old = grab(rule("in a system that is two charges"), r"differ by (\d+\.\d to \d+\.\d) per cent")
same = grab(rule("two samples of one charge"), r"at most (\d\.\d+) per cent")
step = grab(rule("a charge's analysis moves"), r"at most (\d\.\d+) per cent")
times = grab(rule("the smallest of those differences"), r"is (\d+) times")
gap_new = grab(rule("the two new charges"), r"differ by (\d+\.\d to \d+\.\d) per cent")
mixed = grab(rule("taken as one system"), r"oils, (\d+\.\d to \d+\.\d) per cent")
second = grab(rule("the tank on the second charge"), r"has (\d+) loads at a site, (\d+ to \d+) of them", 0)
sizes = grab(rule("loads in a package"), r"(\d+ to \d+) beside the program, (\d+ to \d+) where it is run", 0)
span = rule("results at the six sites")[len("results at the six sites: "):]
peak = grab(rule("the oils' peak heat transfer coefficient"), r"is (\d+ to \d+) W/m2K")
c_most, c_share = grab(conv, r"relative differences: (\d\.\d+) per cent, which is (\d\.\d+) of", 0)

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
    elif current and re.match(r"\s+\w+\s+\d+\.\d s\s+\d+ of\s+\d+ loads out of band", l) and "verdict" in kinds[current]:
        name, out = re.match(r"\s+(\w+)\s+\d+\.\d s\s+(\d+) of", l).groups()
        kinds[current]["sites"].append((name, int(out)))
label = {"register": "one sample for each listed system that was renewed; the rest of the allowance unused",
         "register_spare": "the same, with the rest of the allowance spent on tanks not yet sampled, a tank "
                           "whose own sample stands apart keeping its own figures",
         "on_file_only": "tanks sorted into charges by analysis for the oil on file, but one sample for each "
                         "listed system that was renewed"}
reg_rows = []
for kind in ("register", "register_spare", "on_file_only"):
    k = kinds[kind]
    out = [o for _, o in k["sites"] if o]
    reg_rows.append("| %s | %s | %d of 6 | %d to %d |" % (label[kind], k["examples"], len(out), min(out), max(out)))
reg_table = "| program | the two example sites | sites with loads out of band | loads out at each of those |\n|---|---|---|---|\n" + "\n".join(reg_rows)
reg_sites = ", ".join("%s %d" % (n, o) for n, o in kinds["register"]["sites"])
rule_list = "\n".join("- " + h[0].lower() + h[1:] + (";" if i < len(held) - 1 else ".") for i, h in enumerate(held))

DESCRIPTION = re.search(r'^description = "(.*)"$', open(T + "/task.toml").read(), re.M).group(1)

DIFFICULTY = """This is the work of a heat treatment engineer who keeps a works group's quenching standard and the program that applies it. When a steel bar leaves the furnace at about 850 C and goes into oil, what it becomes is decided in the next minute: how fast its centre passes through the transformation range fixes how much of it hardens, how far the surface runs ahead of the centre fixes the stress and distortion it carries, and the time to reach handling temperature fixes the cycle. The task is a program that finds these for every load on record at a hardening shop, to within 1.5 per cent and 3 K, within 50 seconds for a site, at sites whose quench oil has been renewed and has to be sampled before it can be calculated with. The sites, their records and the standard are synthetic and realistic: bars of 20 to 100 mm in two steels, furnace at 830 to 880 C, baths at 50 to 80 C, oils whose peak heat transfer coefficient is {peak} W/m2K, and at the six sites the program is run on, {span}.

Three pieces of physics set every answer, and none of them is linear.

- **Conduction with changing properties.** Heat leaves the bar by radial conduction, and over the range the bar crosses the steel's conductivity falls by almost half and its heat capacity nearly doubles and then drops again through the transformation. The equation has no closed solution and the classical charts for a cylinder, which assume constant properties and a constant surface coefficient, do not apply.
- **The boiling curve.** The oil does not cool the surface at a steady rate. Above about 700 C the bar sits in a vapour blanket and loses little; the blanket collapses into nucleate boiling, where the coefficient rises sixfold; below 300 C the oil cools by convection alone. The surface coefficient is a steep function of the surface temperature, which is itself the unknown, so the boundary condition is the stiffest part of the problem and drives the time step.
- **A coupled surface and centre.** The results asked for are events at the centre, set by a surface that is passing through all three regimes while the centre is still hot. A bar of 20 mm follows the oil; a bar of 100 mm is limited by its own conduction. No single simplification covers the range.

The oil is the fourth unknown, and it is a measurement problem. The standard takes a load's oil from the laboratory's cooling-curve analysis of the charge that was in the tank, not from the oil type: charges as delivered differ from the catalogue by up to 15 per cent, and a tenth more cooling power shortens the centre's cooling time by a twentieth to a tenth. Most systems at these sites were drained and refilled in January 2026, so the oil now in most tanks has never been analysed. The laboratory analyses a fixed number of samples for a site, in one order, and the program has to place that order itself, while it runs, before it has seen a single result.

What has to be sampled is every body of oil that was renewed, and a body of oil is a physical thing, not a line of a register. Tanks fed from one reservoir give one cooling curve, within what the laboratory repeats; tanks that give two do not share a reservoir, whatever the register says. That is the measurement that settles it, and it is on file:

- two samples of one charge taken in the same round differ by at most {same} per cent in maximum cooling rate, and a charge moves by at most {step} per cent from one round to the next;
- at some sites one central system that the register lists as a single system has given, at one of its three tanks, analyses {gap_old} per cent away from the other two in every one of the four sample rounds, {times} times the largest difference between two samples of one charge;
- at those sites the laboratory's allowance is one more than the number of systems the register shows renewed.

Such a system is two reservoirs. Taken as one, its oil on file is the mean of two different oils, {mixed} per cent from either, and after the renewal one sample stands for two new charges that differ by {gap_new} per cent. The tank on the second reservoir has {second_loads} loads at a site. Nothing in the records says any of this in words, and the two example sites do not have such a system: there the register's systems are the charges and the allowance equals their number. The third visible package, the one without results, has one.

The time limit is the other half of the work. A site has {hidden_sizes} loads and no two need be alike, since diameter, steel, furnace and bath temperature and oil all enter and nothing can be tabulated; a run has 50 seconds on one CPU, about a fiftieth of a second a load. Handing each bar in turn to a stiff library integrator, which is the natural way to write it, takes {n_rate} s a load, {n_xlo} to {n_xhi} times the limit for a site. Meeting the limit takes a scheme built for the whole site at once: every bar on the same number of radial intervals, time stepped in proportion to each bar's own R squared so that all bars reach the same stage at the same step, the tridiagonal elimination written out along the radius so that one pass advances every bar, and a step that is short through the boiling peak and long in the convective tail.

Its research analogue is the inverse and forward heat conduction work behind quench process models: nonlinear transient conduction under a boiling boundary condition measured by a probe test, solved for populations of parts. The oil adds the question that precedes any calibration: deciding from the measurements themselves which physical population each belongs to, and planning a fixed number of new measurements before any of them is known.

Each of these defeats an assumption the general approach makes on first reading:
- that a cylinder chart or a lumped model with a mean coefficient gives the centre's cooling time;
- that the oil can be taken from its type's catalogue figures;
- that two thousand bars can each be integrated on their own inside the limit;
- that the register's list of oil systems is the list of charges;
- that an allowance of one more sample than the register needs has one to spare."""

SOLUTION = """solution/quench.py is the reference; solution/solve.sh puts it at /app/output/quench.py. It reads one package, places the laboratory order and writes the table.

1. **Charges.** The tanks of each listed system are sorted into charges by the analyses on file: two tanks hold different charges when the analyses drawn from them nearest in date stand more than 3 per cent apart in maximum cooling rate, six times what the laboratory repeats. A tank with no analysis stays with the first charge of its system.
2. **The order.** One sample from every charge whose system the oil log shows renewed, at the first tank fed from it, placed through `labsample` in a single order.
3. **The oil of a load.** After the renewal, the laboratory's figure for the tank's charge. Before it, and for a charge that was not renewed, the charge's latest analysis on file, the mean of that date's samples (HT-5 section 5).
4. **One array for a steel.** All loads of a steel are rows of one array: 32 radial intervals for every bar, finite volumes in r, conductivity at the faces from the mean of the neighbouring temperatures.
5. **Time.** Every bar is stepped by the same share of its own R squared over 6e-6 m2/s, so bars of all sizes pass the same stage at the same step. The share starts at 2e-4, grows by 4 per cent a step to 2e-3 while any centre is above 500 C, and to 2e-2 after that. The first four steps are backward Euler and the rest the trapezoidal rule.
6. **A step.** The properties and the surface coefficient are taken at the mid-step temperature by three passes. Each pass is one tridiagonal elimination along the radius, carried out for every bar at once.
7. **Events.** The times at which a centre passes 800, 725, 675, 500 and 150 C are found by linear interpolation inside the step, the surface temperature at the 500 C crossing likewise, and the largest centre to surface difference is kept as the march goes.

**On the shipped sites** (authoring/evidence/reference_run.txt, run by the checker as the verifier runs it) the reference is accepted: {r_points} loads at six sites, the largest error at any of them {r_err} of its band, runs of {r_lo} to {r_hi} s, so the limit of {limit} s is {ratio} times the slowest run. It is accepted on both example sites as well, and on the pending package it orders {pending_n} samples, {pending_order}: two of them from the system QS-2.

**authoring/evidence/naive_quench.py** is a second solution, written apart from the reference and sharing no code with it. It joins tanks into charges through a graph, with a threshold of 2 per cent, and cools each load on its own: finite differences on 60 radial intervals with a fictitious node at the surface, integrated by a library stiff integrator with its own error control, the events found as roots of the integrator's interpolant. On the six sites cut down to every 40th load ({n_thin} loads) it places the same orders as the reference and is accepted, and its widest departure from the sealed results is {n_wide} of a band (authoring/evidence/naive_run.txt)."""

VERIFICATION = """The deliverable is a program, /app/output/quench.py. The verifier does not read anything the agent's run left behind: tests/grade_program.py, run by the one pytest test in tests/test_program.py, runs the program on six site packages it has not seen and compares what each run writes with sealed results.

**A run.** For each site, a scratch directory holds a copy of quench.py alone and a read-only copy of the package. The program is started there as `python3 quench.py PACKAGE_DIR OUT_CSV`, as the user nobody, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, in a process group of its own, with no network. The run is single-threaded by those settings and is not tied to a particular CPU, because trials that run side by side on one host would then share it.

**The limit.** Each run has 50 seconds from start to exit, the same figure as the task statement's sentence "Each run of quench.py must finish within 50 seconds on 1 CPU." (preflight compares the two). It is enforced by a timeout on the wait for the process, in tests/grade_program.py. A run that is still going at 50 s ends the assessment: its process group and every process of nobody are killed, nothing it wrote is opened, no later site is run, and the program is not accepted. There is no share of sites or loads that lets such a run through.

**The laboratory.** During a run the checker is the laboratory. `labsample` in the verifier's image passes the order to the checker, which answers by the same rule as the agent's laboratory (tests/lab/lab.py is the same file as environment/rig/lab.py): one order for the site, of at most the package's allowance, written down before any figure is given; a second order is refused. The books are readable by root alone. In the agent's image the laboratory is a separate account reached through one sudo rule, and there it answers for the three visible sites only.

**Acceptance.** Every run must finish in time with exit status 0, every OUT_CSV must be the table the statement describes, and for every load of every site the two times, the cooling rate and the largest temperature difference must be within 1.5 per cent of the sealed result and the surface temperature within 3 K. One pytest test carries the reward. tests/test.sh writes 0 first and writes 1 only when pytest exits 0 and tests/read_report.py finds that the ctrf report shows exactly 1 test, 1 passed.

**The reader** holds the table to the statement and no further. The header must be exactly the one given; there must be one row for every load of the package and none for anything else; each value must be a finite decimal number; and the file must be no larger than the 4194304 bytes the statement gives. Row order, line ends, a final terminator, empty lines, quoting and blanks round a field are not stated and are not judged.

**The truth** is the sealed definition authoring/provenance/quench.py, run by authoring/provenance/sites.py for the oil each tank really held: 64 radial intervals and about 5 600 time steps for every load. It is never a run of the reference, which is its own program on half the intervals and far fewer steps. Against 200 intervals and steps a quarter as long the sealed results move by {c_most} per cent at most, {c_share} of a band (authoring/evidence/convergence.txt). authoring/provenance/regenerate.py makes the nine sites again from the generator and finds all {n_files} shipped data files the same byte for byte (authoring/evidence/regenerate.txt); authoring/provenance/manifest.json lists them with their SHA-256.

**The bands** are checked against a separately written solution. authoring/evidence/naive_quench.py shares no code with the reference or with the sealed definition and uses a different discretisation and a library integrator, and its widest departure from the sealed results is {n_wide} of a band, so every band is at least {n_times} times the widest departure of an independent, correct method. The reference's largest error is {r_err} of a band. A correct standard method is accepted with room to spare; nothing depends on matching a particular scheme.

**What the six sites are, and how they differ from the visible data.** They are six other sites, none of them a visible one and none sharing a file with one. The difference is built in on purpose and is not a new seed of the visible sites:
- at the two example sites, whose results the agent has, every system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed;
- at five of the six sites one central system that the register lists as a single system is two reservoirs, both renewed, in a system of a different number and oil type from site to site; the allowance there is the number of charges, one more than the register's count; the sixth site has no such system;
- the condition is present in the visible data: the pending package, /app/data/pending/west_quarry, has such a system (QS-2), with the same two signs, and the agent's laboratory answers for it.
It is built in authoring/provenance/sites.py: the `SITES` table gives each site's role and which system is two charges, and `describe` builds the charges, the analyses on file and the allowance from it.

authoring/provenance/design_rules.py recomputes the design rules from the generator's description of each site and the shipped files (authoring/evidence/design_rules.txt; {n_rules} of {n_rules} hold):
{rule_list}

Every study below runs complete programs through tests/grade_program.py as the verifier does: as nobody, with one thread to a numerical library, with the laboratory answering through the verifier's `labsample`.

**A correct program that is not fast** (naive_run.txt). The second solution is accepted on the cut-down sites, where the limit is set aside, at {n_rate} s a load. At that rate the sites as they are, of {n_lo} to {n_hi} loads, would take {n_slo} to {n_shi} s a run, {n_xlo} to {n_xhi} times the limit. Run on them at the limit, it is stopped: sites run {n_stop0}, {n_stop1}, not accepted.

**Programs written to the visible results** (register_run.txt, made from the reference by authoring/evidence/variants.py, one change each):
{reg_table}

With one sample for each listed system the loads out of band are {reg_sites}. The site with none is the one without such a system.

**The verifier itself** (verifier_checks.txt, {n_cases} cases, none unexpected; every program is built at run time from the sealed results of a cut-down site).
- Tables refused: nothing written, OUT_CSV as a directory or as a symbolic link to a file holding the true table, an empty file, the header alone, no header, a misspelt, capitalised or padded header, a column added or left out, a row of five fields, a load left out, given twice, unknown or in lower case, a value empty, n/a, nan, inf, with its unit, with a decimal comma or with a digit separator, bytes that are not UTF-8, a file over the size cap, and the true table followed by exit status 3.
- Tables accepted: the true table with CRLF line ends, no final terminator, empty lines, the rows reversed, padded or quoted fields, plus signs, and exponent form.
- Bands: each quantity moved to just inside its band at every load is accepted (1.4 per cent, 2.8 K) and to just outside is not (1.6 per cent, 3.2 K); one load of a site with its core cooling time 2 per cent out is enough to refuse the program.
- The limit, set to 3 s for the purpose: a program that writes the true table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; with two sites to run the second is never started; a program that exits in time and leaves a child running in a session of its own is accepted and the child is killed.
- The laboratory during a run: an order over the allowance, an order naming a tank the site does not have and an order through a package naming another site are refused and do not count as the site's order; the order after them is taken; a second order is refused; outside a run nothing answers.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest exits 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, a failing exit with a passing report, no report, a report that is not JSON, and no quench.py delivered.

**The whole verifier** (verifier_run.txt). tests/test.sh itself, run as it stands with each program in turn at /app/output/quench.py, under the umask it sets, with the checker running the program as nobody: the reward is 1 for the reference and 0 for the program that samples by the register and for the second solution at the limit. Where that study was run the pytest-json-ctrf plugin was not installed, and authoring/evidence/ctrf_standin.py wrote the report in its place; the verifier's image installs the plugin itself.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned, and the verifier's image carries the same /app/data at the same path. The verifier runs in a separate container without network; /tests and /logs/verifier are readable by root alone, and the program runs there as nobody."""

NOTES = """What the shift in the hidden data is. The visible results (two example sites) come from sites where every quench oil system the register lists is one charge of oil and the laboratory's allowance equals the number of systems renewed. At five of the six hidden sites one listed central system is two reservoirs, both renewed, so the right laboratory order has one more sample than the register's count and the tank on the second reservoir has a different oil before and after the renewal. The condition appears once in the visible data, in the package without results (/app/data/pending/west_quarry, system QS-2). The hidden sites are other sites: no name and no file is shared with a visible one. A program that follows the register reproduces both visible result sets and is out of band at five hidden sites (authoring/evidence/register_run.txt).

Where it is built.
- Generator config: authoring/provenance/sites.py, the `SITES` table (seed, role, the system that is two charges, number of central systems and of tanks with their own oil) and `describe`.
- Manifest: authoring/provenance/manifest.json, the same table and the SHA-256 of every data file.
- Data files: tests/sites/ (the six packages), tests/sealed/truth/ (their results), tests/lab/sealed/ (the laboratory's books for them); environment/data/examples/ and environment/data/pending/ (the visible packages), environment/rig/sealed/ (the laboratory's books for those).
- Check: authoring/provenance/design_rules.py and authoring/evidence/design_rules.txt.

The timed re-run.
- The tests run the program: tests/grade_program.py, `run_site`.
- The limit: `RUN_LIMIT_S = 50` in tests/grade_program.py, and "Each run of quench.py must finish within 50 seconds on 1 CPU." in instruction.md; preflight fails if they differ.
- The reference takes {r_lo} to {r_hi} s a run; the limit is {ratio} times the slowest.
- A correct program that is not fast times out: authoring/evidence/naive_quench.py, authoring/evidence/naive_run.txt.
- A run over the limit ends the assessment and nothing it wrote is read: authoring/evidence/verifier_checks.txt, "The limit".
- Threads: OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in the environment of each run. Runs are not tied to one CPU, since trials side by side on one host would then share a core."""

vals = dict(span=span, peak=peak, same=same, step=step, gap_old=gap_old, times=times, mixed=mixed,
            gap_new=gap_new, second_loads=second[0], hidden_sizes=sizes[1], n_rate=n_rate, n_xlo=n_xlo, n_xhi=n_xhi,
            r_points=r_points, r_err=r_err, r_lo=r_lo, r_hi=r_hi, limit=limit, ratio=ratio,
            pending_n=len(pending_order.split()), pending_order=pending_order.strip().replace(" ", ", "), n_thin=n_thin,
            n_wide=n_wide, n_times=n_times, n_files=n_files, n_rules=n_rules, rule_list=rule_list, n_lo=n_lo, n_hi=n_hi,
            n_slo=n_slo, n_shi=n_shi, n_stop0=n_stop[0], n_stop1=n_stop[1], reg_table=reg_table, reg_sites=reg_sites,
            n_cases=n_cases, c_most=c_most, c_share=c_share)

readme = """# quench-oil-survey

{description}

## Difficulty

{difficulty}

## Reference solution

{solution}

`solution/solve.sh` starts it inside the agent's container: it copies quench.py to /app/output and runs it once on the three packages in /app/data, checking the two example sites against their results.

## Verification

{verification}

Evidence (`authoring/evidence/`): `reference_run.txt`, `naive_run.txt`, `register_run.txt`, `verifier_checks.txt`,
`verifier_run.txt`, `design_rules.txt`, `convergence.txt`, `regenerate.txt` and `preflight.txt`.

## Submission notes

{notes}
""".format(description=DESCRIPTION, difficulty=DIFFICULTY.format(**vals), solution=SOLUTION.format(**vals),
           verification=VERIFICATION.format(**vals), notes=NOTES.format(**vals))
open(T + "/README.md", "w").write(readme)
print(len(readme), "chars")
