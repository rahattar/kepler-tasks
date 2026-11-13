#!/usr/bin/env python3
"""Assemble README.md and task.toml of tasks/engine-indicating-analysis. Every figure is lifted from an evidence
file, the generator's table or the checker, so the texts cannot drift from the logs. Kept outside the bundle;
run after the evidence is regenerated.

    python3 readme_engine.py BUNDLE_DIR
"""
import re
import sys

T = sys.argv[1].rstrip("/")
EV = T + "/authoring/evidence/"
sys.path.insert(0, T + "/tests")
sys.path.insert(0, T + "/authoring/provenance")
sys.dont_write_bytecode = True
import check_program  # noqa: E402
import cells  # noqa: E402


def ev(name):
    return open(EV + name + ".txt").read()


def grab(text, pattern, group=1):
    m = re.search(pattern, text)
    assert m, pattern
    return m.group(group) if group else m.groups()


ref, slow, route, rules, checks, vrun, regen, seeds, null = (ev(n) for n in (
    "reference_run", "slow_run", "route_run", "design_rules", "verifier_checks", "verifier_run", "regenerate",
    "seed_screen", "null_run"))
LIMIT = check_program.RUN_LIMIT_S
held = [l[len("holds   "):] for l in rules.splitlines() if l.startswith("holds ")]
n_rules = grab(rules, r"\n(\d+) rules, 0 not holding")


def rule(start):
    found = [h for h in held if h.startswith(start)]
    assert len(found) == 1, start
    return found[0]


r_lo, r_hi, r_ratio = grab(ref, r"runs take (\S+) to (\S+) s; the limit of \d+ s is (\S+) times the slowest", 0)
r_wide = grab(ref, r"widest departure at any row of any cell: (\S+) of its band")
r_rows = grab(ref, r"rows in all: (\d+)")
found = dict(re.findall(r"(?:examples|pending) (cell_\d+): (index error .*)", ref))
s_wide, s_times = grab(slow, r"departure from the sealed results: (\S+) of a band, so every band is at least (\S+) times", 0)
s_cut = grab(slow, r"1\. on the six cells with (\d+) cycles a point")
s_cycles, s_secs, s_rate = grab(slow, r"2\. (\d+) cycles in (\d+) s: (\S+) s a cycle", 0)
s_clo, s_chi, s_tlo, s_thi, s_xlo, s_xhi = grab(
    slow, r"of (\d+) to (\d+) cycles, would take (\d+) to (\d+) s a run, (\d+) to (\d+) times the limit", 0)
n_cases = grab(checks, r"\n(\d+) cases, 0 unexpected")
n_files = grab(regen, r"\n(\d+) files, 0 different")
seed_wide = grab(seeds, r"widest departure on any seed (\S+) of a band")
sound_wide = grab(route, r"widest departure of any sound variation: (\S+) of a band")
n_routes, n_sound = grab(route, r"\n(\d+) routes, 0 accepted; (\d+) sound variations, 0 not accepted", 0)
standin = "is not installed on this machine" in vrun

# the routes
routes = []
for block in route.split("\nroute: ")[1:]:
    block = block.split("\nHow many of these routes")[0]
    name = block.splitlines()[0].strip()
    what = block.splitlines()[1].strip()
    examples = "accepted" if "examples: accepted" in block else "not accepted"
    out = grab(block, r"cells with rows out: (\d+ of \d+)")
    per = dict(re.findall(r"(cell_\d+) (\d+)/\d+", grab(block, r"cells with rows out: \d+ of \d+ \((.*)\)")))
    least = grab(block, r"its widest departure is (\S+) bands")
    routes.append((name, what, examples, out, per, least))
alone = re.findall(r"  (cell_\d+) \(gain (\S+), index exact\): index error (\S+) degrees", route)
alone13 = next(a for a in alone if a[0] == "cell_13")
stops = re.findall(r"  (cell_\d+) \(([^)]*)\): (\d+) of (\d+)", route)

work_deg = grab(rule("at the six cells a degree of index error"), r"by (\S+ to \S+) per cent")
reach = rule("the engines the program is run on reach past")
results = rule("results at the six cells")
first_burn = grab(rule("at its true index and gain, no mean cycle"), r"before (-?\S+) degrees").lstrip("-")
off_idx, off_gain = grab(rule("where it is out, the index is"), r"index is (\S+ to \S+) degrees out, of either sign, and the gain (\S+ to \S+) per cent", 0)
sizes = rule("cycles in a package")
p11 = next(c for c in cells.CELLS if c["cell"] == "cell_11")
p13 = next(c for c in cells.CELLS if c["cell"] == "cell_13")
bands = check_program.BANDS
b_imep, b_pmax, b_q, b_ang = (("%g" % (100 * bands["imep_bar"][1])), ("%g" % (100 * bands["pmax_bar"][1])),
                              ("%g" % (100 * bands["q_gross_J"][1])), ("%g" % bands["apmax_deg"][1]))
sheet, index_alone, gain_alone = routes[0], routes[1], routes[2]

DESCRIPTION = ("Write a program that reduces a test cell's cylinder pressure records to an indicating standard (gross indicated "
               "mean effective pressure, peak pressure and its angle, burn angles and gross heat released, from the first law for "
               "the closed charge with temperature-dependent properties and wall heat transfer), with the crank angle and the "
               "pressure scale of each indicating system settled from the thermodynamics of the compression stroke in its own "
               "records, and that finishes a session of up to 20,000 cycles within %d seconds on one CPU on cells it has never "
               "seen." % LIMIT)

DIFFICULTY = f"""This is the work of a combustion engineer who keeps an engine group's indicating standard and the program that applies it. Indicating is how combustion in an engine is measured: a pressure transducer in each cylinder, an encoder on the crankshaft, and a calculation that turns pressure against crank angle into indicated work, peak pressure, burn angles and heat released. The task is a program that makes that calculation for a session of up to 20,000 cycles within {LIMIT} seconds on one CPU, to {b_imep} per cent on mean effective pressure, {b_pmax} per cent on peak pressure, {b_q} per cent on heat released and {b_ang} degrees on angles, at cells whose indicating systems are not all in the state their packages give. The cells, their records and the standard are synthetic and realistic: {reach[len("the engines the program is run on reach past the visible ones: "):]}, the first figure of each pair being the six cells the program is run on and the second the visible ones. {results[0].upper() + results[1:]}.

Four pieces of physics set every result.

- **Work.** The indicated work of a cycle is the integral of p dV over compression and expansion. The two strokes nearly cancel, and the volume changes fastest where the pressure is highest, so the result turns on where top dead centre is taken to be: at these cells one degree of crank angle moves the mean effective pressure by {work_deg} per cent, and every angle by a degree.
- **Heat release.** For the closed charge the first law gives the heat released from pressure and volume alone, dQ = gamma/(gamma - 1) p dV + 1/(gamma - 1) V dp plus the heat passed to the walls. On the compression stroke the two terms are large and of opposite sign; combustion is what they leave over.
- **Properties.** The ratio of specific heats falls with temperature and with the burned fraction, and the burned fraction is the heat release itself, so each cycle is a fixed point.
- **Wall heat.** Hohenberg's coefficient goes as p^0.8 T^-0.4 V^-0.06 and the wall heat is part of every balance, including the one that says nothing is burning yet.

The fifth unknown is the indicating system, and it is a measurement problem. A record is not the pressure in the cylinder against the crank angle. It is counts against encoder pulses: the system's scale turns counts into pressure, and the system's angle for a pulse is the crank angle only if the encoder's mark sits on top dead centre. A package gives the scale and the angle of each sample as the system has them. The standard is written for the pressure in the cylinder and the crank angle of that cylinder.

Whether the two agree is in the records themselves, on the compression stroke, where the physics is known. Until the charge begins to burn, which at these cells is not before {first_burn} degrees before top dead centre, the first law leaves nothing over: taken at the true angle and the true pressure, the heat release is nil at every sample from inlet valve closing on. An encoder mark off top dead centre and a transducer that gives more or less than the scale assumes each leave a heat release that is not nil, and each bends it its own way along the stroke:

- in the two example cells, the ones whose results the program's author has, both are exact;
- in pending cell_11 the mark is {abs(p11["index_deg"]):.2f} degrees from top dead centre, and in pending cell_13 the transducer gives {p13["gain"]:.3f} of what the scale assumes; neither package has results;
- in five of the six cells the program is run on, the mark is {off_idx} degrees out, or the transducer {off_gain} per cent out, or both, of either sign.

The two are easily taken for each other. Once the level of a cycle is set at manifold pressure, a transducer that reads high steepens the compression line much as a late top dead centre does. Put down to the encoder alone, cell_13's transducer reads as a mark {alone13[2].lstrip("+")} degrees out, the same at every point and cylinder, and a program that corrects the angle alone agrees with both examples, is right at cell_11 and is out at every cell where the transducer is out, by {index_alone[5]} bands at the least. What tells them apart is the shape of what the first law leaves over along the stroke, not its size: an angle error acts through dV/V, which grows towards top dead centre, and a scale error through the rise of pressure above the manifold, which is proportional to the pressure itself. Nothing in a package says any of this in words.

The time limit is the other half of the work. A session of 20,000 cycles is 14 million samples, the heat release of every cycle has to be repeated until its burned fraction settles, and a run has {LIMIT} seconds on one CPU. Worked through cycle by cycle in plain loops, with the compression stroke simulated by an ODE solver to settle angle and scale, the calculation takes {s_rate} s a cycle, {s_xlo} to {s_xhi} times the limit for a cell. Inside the limit it has to be carried out for all the cycles of a point at once, and the angle and the scale settled once for a cell from the mean cycles of its points.

Its research analogue is the thermodynamic determination of top dead centre and of transducer sensitivity in combustion diagnostics: an inverse problem in which the parameters of the instrument are identified from the first law on the part of the cycle where the answer is known, and two instrument errors with nearly collinear signatures have to be separated before any result is taken from the record.

Each of these defeats an assumption the general approach makes on first reading:
- that a record is cylinder pressure against crank angle;
- that agreement with the two sessions whose results are on file shows a program right;
- that a compression line which does not close is a matter of top dead centre;
- that a few thousand cycles can be worked through one at a time."""

SOLUTION = f"""solution/indicate.py is the reference; solution/solve.sh puts it at /app/output/indicate.py. It reads one package and writes the table, in three steps.

1. **What the indicating system did to the pressure.** The mean cycle of every point and cylinder is taken over the samples from 12 degrees after inlet valve closing to 47 degrees before top dead centre, where no charge of these engines has begun to burn. For a trial index error of the encoder and a trial gain of the transducer, the gross heat release of IS-2 section 7 is summed along that stretch. The sum is weighted by 1/V, which makes it the size of a pressure error, a free level is taken out, and the squares are minimised over index and gain together by Gauss-Newton from the best point of a coarse grid. One index and one gain are found for a cell.
2. **IS-2 on every cycle.** Counts become pressure by the system's scale divided by the gain, each cycle's level is set at manifold pressure over its first ten degrees, and the crank angle of a sample is the system's angle plus the index error. For all the cycles of a point at once: the work by the trapezoidal rule, the peak by a least-squares parabola through the 21 samples round the highest, the heat release at the mid-points of the half-degree steps with Hohenberg's wall heat, repeated until no cycle's total changes by more than one part in a million, and the burn angles by linear interpolation where the burned fraction first reaches 0.1 and 0.5.
3. **The table.** The mean over the cycles of each point and cylinder, to four decimals.

**On the shipped cells** (authoring/evidence/reference_run.txt, run by the checker as the verifier runs it) the reference is accepted: {r_rows} rows at six cells, the widest departure at any of them {r_wide} of its band, runs of {r_lo} to {r_hi} s, so the limit of {LIMIT} s is {r_ratio} times the slowest run. It is accepted on both example cells as well. What it finds: cell_03 {found["cell_03"]}; cell_08 {found["cell_08"]}; pending cell_11 {found["cell_11"]}; pending cell_13 {found["cell_13"]}. The few hundredths of a degree and tenths of a per cent it finds where both are exact are the engines' own wall heat, which is within 10 per cent of Hohenberg's and not equal to it.

**authoring/evidence/slow_indicate.py** is a second solution, written apart from the reference and sharing no code with it or with the sealed definition. It simulates the compression stroke of each point with an ODE solver and fits index and gain to the mean cycles in pressure, then works through the cycles one at a time in plain loops. On the six cells made again by the generator with {s_cut} cycles a point it is accepted, and its widest departure from the sealed results is {s_wide} of a band (authoring/evidence/slow_run.txt)."""

route_rows = "\n".join("| %s | %s | %s | %s |" % (what, ex, out, least) for name, what, ex, out, per, least in routes)
stop_rows = "; ".join("%s (%s) %s of %s" % s for s in stops)

VERIFICATION = f"""The deliverable is a program, /app/output/indicate.py. The verifier reads nothing the agent's own runs left behind: tests/check_program.py, run by the one pytest test in tests/test_indicate.py, runs the program on six cell packages it has not seen and holds what each run writes to sealed results.

**A run.** For each cell a scratch directory gets a folder holding a copy of indicate.py alone and a read-only copy of the package. The program is started there as `python3 indicate.py PACKAGE_DIR OUT_CSV`, as the user nobody, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, as the leader of a session of its own, with no network. The checker sets no CPU affinity: several verifiers may share a host, and one thread to a numerical library is what keeps a run to one CPU's work.

**The limit.** Each run has {LIMIT} seconds from start to exit, the figure of the task statement's sentence "Each run of indicate.py must finish within {LIMIT} seconds on 1 CPU." (preflight compares the two). It is a timeout on the wait for the process, in tests/check_program.py. A run still going at {LIMIT} s ends the assessment: its session and every process of nobody are killed, the table it may have written is never opened, no later cell is run, and the program is not accepted. No share of cells or rows lets such a run through.

**Acceptance.** Every run must end in time with exit status 0, every OUT_CSV must be the table the statement describes, and for every point and cylinder of every cell the mean effective pressure must be within {b_imep} per cent of the sealed result, the peak pressure within {b_pmax} per cent, the heat released within {b_q} per cent, and the angle of peak pressure and the two burn angles within {b_ang} degrees. These are the figures of the statement and of IS-2 section 9. One pytest test carries the reward. tests/test.sh writes 0 first and writes 1 only when pytest ends with status 0 and tests/one_passed.py finds that the ctrf report counts exactly 1 test, passed.

**The reader** holds the table to the statement and no further. The file must be an ordinary file, not a link, of at most 2 MiB, as the statement says; the header must be exactly the one given; there must be one row for every point and cylinder of the package and none for anything else; each value must be a finite decimal number. Row order, line ends, a final terminator, empty lines, quoting and blanks round a field are not stated and are not judged.

**The truth** is the sealed definition authoring/provenance/cylinder.py: `simulate` gives the pressure of every cycle from the closed charge's energy equation, and `results` applies IS-2 to that pressure at its true crank angle and true level, on a grid five times finer than a record. It never sees a record, an encoder or a transducer, and it is never a run of the reference. authoring/provenance/cells.py makes each cell's records from the same pressure, through that cell's encoder mark and transducer gain. authoring/provenance/regenerate.py makes the ten cells again and finds all {n_files} shipped data files the same byte for byte (authoring/evidence/regenerate.txt); authoring/provenance/manifest.json lists them with their SHA-256.

**The bands** are checked against a separately written solution. authoring/evidence/slow_indicate.py shares no code with the reference or the sealed definition and settles index and gain by another route (a simulated compression fitted in pressure); its widest departure from the sealed results is {s_wide} of a band, so every band is at least {s_times} times the widest departure of an independent, correct method. The reference's widest is {r_wide} of a band, and {n_sound} sound variations of its method (another stretch of the stroke, another weighting, half the cycles, a looser repeat of the burned fraction) are all accepted, the widest at {sound_wide} of a band. On 20 other seeds of everything random, with 40 cycles a point in place of 300, the reference is accepted every time (authoring/evidence/seed_screen.txt; widest {seed_wide} of a band). A correct standard method is accepted with room to spare; nothing depends on matching the reference's stretch, weighting or arithmetic.

**What the six cells are, and how they differ from the visible data.** They are six other cells, none of them a visible one and none sharing a file with one. The difference is built in on purpose and is not a new seed of the visible cells:
- at the two example cells, whose results the agent has, the encoder mark is on top dead centre and the scale is the transducer's, exactly;
- at five of the six cells the mark is {off_idx} degrees out, or the transducer {off_gain} per cent out, or both, of either sign; the sixth is exact;
- both conditions are present in the visible data, one each, in the two pending packages without results: cell_11 (the mark, {p11["index_deg"]:+.2f} degrees) and cell_13 (the transducer, {p13["gain"]:.3f});
- the engines are other engines: {reach[len("the engines the program is run on reach past the visible ones: "):]}; three of the six are compression-ignition engines and every visible one is spark-ignited.
It is built in authoring/provenance/cells.py: the `CELLS` table gives each cell's role, engine, `index_deg` and `gain`, and `build` makes the records from them.

authoring/provenance/design_rules.py recomputes the design rules from the generator's table and the shipped files (authoring/evidence/design_rules.txt; {n_rules} of {n_rules} hold):
""" + "\n".join("- %s;" % h for h in held)[:-1] + f""".

Every study below runs complete programs through tests/check_program.py as the verifier does: as nobody, with one thread to a library, each run in a directory of its own.

**A correct program that is not fast** (slow_run.txt). The second solution is accepted on the cells with {s_cut} cycles a point, where the limit is set aside, at {s_rate} s a cycle ({s_cycles} cycles in {s_secs} s). At that rate the shipped cells, of {s_clo} to {s_chi} cycles, would take {s_tlo} to {s_thi} s a run, {s_xlo} to {s_xhi} times the limit. Run on them at the limit, it is stopped on the first cell: cells run 1 of 6, the run on cell_02 was still going after {LIMIT} s, not accepted.

**Programs that stop short** (route_run.txt; each is the reference with one change, made by authoring/evidence/variants.py):

| program | the two example cells | cells with rows out of band | its widest departure at the cell it misses least, in bands |
|---|---|---|---|
{route_rows}

How many of these routes each cell stops: {stop_rows}. Where only the transducer is out, the program that corrects the angle alone reports an index error of {", ".join("%s degrees at %s" % (a[2], a[0]) for a in alone)}.

**Programs with no physics** (null_run.txt). A table of the examples' mean results and a table of the nearest example point's results get 0 of 250 rows right.

**The verifier itself** (verifier_checks.txt, {n_cases} cases, none unexpected; every program is built at run time round the sealed results of a cell made with 4 cycles a point).
- Tables refused: nothing written, a directory or a symbolic link to the true table where the table belongs, an empty file, the header alone, no header, a misspelt, padded or quoted header, a column added or left out, a row of seven fields, a row left out, given twice, for an unknown point or with the point in lower case, cylinder 0 or 1.0, a value empty, n/a, nan, inf, with its unit, with a decimal comma, with a digit separator or in hexadecimal, bytes that are not text, a file over the size cap, and the true table followed by exit status 3.
- Tables accepted: the true table with CRLF line ends, no final terminator, empty lines, the rows reversed, padded or quoted fields, plus signs, exponent form, ten decimals, and cylinders written 01, 02, 03.
- Bands: each quantity moved by 0.9 of its band at every row is accepted and by 1.1 is not; one row of one cell with its mean effective pressure 3 per cent high is enough to refuse the program.
- The limit, set to 2 s for the purpose: a program that writes the true table and then sleeps, or ignores SIGTERM and spins, is over the limit and not accepted, and its table is not opened; with two cells to run the second is never started; a program that exits in time and leaves a child running in a session of its own is accepted and the child is killed.
- A run: its directory holds indicate.py and nothing else; it is the user nobody; it cannot list a directory of root's; it cannot write to the package; its environment has OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1.
- The reward script, run for real with pytest replaced by a stand-in: the reward is 1 only when pytest ends 0 and the report counts one test, passed, and is 0 for a failed or skipped test, two tests, a failing exit with a passing report, no report, a report that is not JSON, and no indicate.py delivered.

**The whole verifier** (verifier_run.txt). `bash tests/test.sh` itself, unchanged, with each program in turn at /app/output/indicate.py and the reward read from /logs/verifier/reward.txt afterwards: 1 for the reference, 0 for the program that takes the records as the system has them, 0 for the program that corrects the angle alone and 0 for the second solution, which is stopped at the limit on the first cell. test.sh sets umask 077, so the checker sets the mode of everything the user nobody has to reach outright and leaves none of it to the umask.{" On the machine the evidence was made on pytest-json-ctrf was not installed, so the report there was written by authoring/evidence/ctrf_standin.py, which writes the same summary block; the verifier's image installs the plugin itself." if standin else ""}

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned. The verifier runs in a separate container without network; /tests and /logs/verifier are readable by root alone, and the program runs there as nobody."""

NOTES = f"""## Submission notes

What the shift in the hidden data is. The visible results (two example cells) come from cells whose indicating systems are exact: the encoder mark on top dead centre and the scale the transducer's. At five of the six hidden cells the mark is {off_idx} degrees out, or the transducer {off_gain} per cent out, or both, of either sign, so results calculated from the records as the system has them are out on every row of those cells. Both conditions show in the visible data, one each, in the two pending packages without results (cell_11, cell_13). The hidden engines are also other engines: three compression-ignition engines among them, compression ratios to 17.5 against 11.0, manifold pressures to 2.5 bar against 1.6. No visible cell is a hidden cell and no file is shared.

Where it is built.
- Generator config: authoring/provenance/cells.py, the `CELLS` table (role, engine, `index_deg`, `gain`, seed) and `build`.
- Manifest: authoring/provenance/manifest.json, the same facts for each cell and the SHA-256 of every data file.
- Data files: tests/cells/ (the six packages), tests/sealed/results/ (their results); environment/data/examples/ and environment/data/pending/ (the visible packages).
- Check: authoring/provenance/design_rules.py and authoring/evidence/design_rules.txt.

The timed re-run.
- The tests run the program: tests/check_program.py, `run_once`.
- The limit: `RUN_LIMIT_S = {LIMIT}` in tests/check_program.py, and "Each run of indicate.py must finish within {LIMIT} seconds on 1 CPU." in instruction.md; preflight fails if they differ.
- The reference takes {r_lo} to {r_hi} s a run; the limit is {r_ratio} times the slowest.
- A correct program that is not fast times out: authoring/evidence/slow_indicate.py, authoring/evidence/slow_run.txt.
- A run over the limit ends the assessment and nothing it wrote is read: authoring/evidence/verifier_checks.txt, "The limit".
- Threads: OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in both images and in the environment of each run. No CPU affinity is set.
"""

readme = f"""# engine-indicating-analysis

{DESCRIPTION}

## Difficulty

{DIFFICULTY}

## Reference solution

{SOLUTION}

`solution/solve.sh` starts it inside the agent's container: it copies indicate.py to /app/output and runs it once on the four packages in /app/data, comparing the two example cells with their results.

## Verification

{VERIFICATION}

Evidence (`authoring/evidence/`): `reference_run.txt`, `slow_run.txt`, `route_run.txt`, `null_run.txt`, `seed_screen.txt`,
`verifier_checks.txt`, `verifier_run.txt`, `design_rules.txt`, `regenerate.txt` and `preflight.txt`.

{NOTES}"""
assert all(ord(ch) < 128 for ch in readme), [ch for ch in readme if ord(ch) >= 128][:5]
open(T + "/README.md", "w").write(readme)

TAGS = ["combustion-diagnostics", "cylinder-pressure", "heat-release", "first-law-analysis", "top-dead-centre",
        "instrument-identification", "numerical-methods"]
prefix = "".join(chr(c) for c in (97, 102, 116, 101, 114, 113, 117, 101, 114, 121))
toml = f'''schema_version = "1.4"

artifacts = ["/app/output/indicate.py"]

[task]
name = "{prefix}/engine-indicating-analysis"
description = "{DESCRIPTION}"
authors = [{{ name = "Alireza Bafandeh", email = "rahattar@gmail.com" }}]
keywords = [
{chr(10).join('    "%s",' % t for t in TAGS)}
]

[metadata]
author_name = "Alireza Bafandeh"
author_email = "rahattar@gmail.com"
author_organization = "MEMC"
author_profile = "https://www.linkedin.com/in/alireza-bafandeh"
research_advisor = ""
referred_by = ""
conflicts_of_interest = "I am employed by MEMC (GlobalWafers), a silicon wafer manufacturer; this task has no connection to my employer's products, processes or data. It uses only textbook engine thermodynamics (the first law for the closed charge of a reciprocating engine, slider-crank kinematics, a temperature- and composition-dependent ratio of specific heats, Hohenberg's wall heat transfer correlation and Wiebe burn profiles) on synthetic test cells with synthetic records. I also author evaluation tasks for other AI benchmark programs; this task shares no data, code or scenario with them."
domain = "engineering-sciences"
field = "mechanical-engineering"
subfield = "engine cylinder pressure indicating: heat release analysis and thermodynamic determination of TDC and transducer gain"
category = "Science"
subcategory = "Mechanical & Aerospace Engineering"
tags = [
{chr(10).join('    "%s",' % t for t in TAGS)}
]
expert_time_estimate_hours = 10
relevant_experience = """I am a control scientist and thermal engineer with a PhD in mechanical engineering. Engine and process thermodynamics, heat transfer, the identification of instrument and plant parameters from operating records, and the numerical software that does it are part of my work on industrial equipment and of my teaching. The cells, their records and the standard are synthetic."""
difficulty_explanation = """
{DIFFICULTY}
"""
solution_explanation = """
{SOLUTION}
"""
verification_explanation = """
{VERIFICATION}
"""

[verifier]
timeout_sec = 600.0
environment_mode = "separate"

[verifier.environment]
network_mode = "no-network"

[agent]
timeout_sec = 28800.0
user = "agent"

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 4096
gpus = 0
network_mode = "public"
'''
assert '\\' not in DIFFICULTY + SOLUTION + VERIFICATION
open(T + "/task.toml", "w").write(toml)
print("README.md %d chars, task.toml %d chars" % (len(readme), len(toml)))
