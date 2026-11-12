"""Writes README.md and task.toml from one copy of each explanation, so the two cannot drift apart.

    python3 -I meta.py          print the three explanations
    python3 -I meta.py --write  write ../../README.md and ../../task.toml
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))
EVIDENCE = os.path.join(TASK, "authoring", "evidence")

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
         "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}


class _Words(dict):
    """n -> the English word for n. A function, not a table: a table of the numbers that happened to come up
    once raised KeyError when a study's case count changed, which is the table's own fault and not the study's."""

    def __missing__(self, n):
        if not isinstance(n, int) or not 0 <= n < 100:
            raise KeyError(n)
        if n < 20:
            return _ONES[n]
        tens, ones = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[ones] if ones else "")


WORDS = _Words()

sys.path.insert(0, HERE)
import bpphys as PH                                                     # noqa: E402
import fleet as FL                                                      # noqa: E402


def _ev(name):
    with open(os.path.join(EVIDENCE, name)) as f:
        return f.read()


def _grab(text, pattern, name):
    """One capture group per figure, or a loud failure. A figure that cannot be read is never defaulted: the
    whole point is that no number in an explanation is typed by hand."""
    m = re.search(pattern, text)
    if m is None:
        raise SystemExit("meta.py: %s not found in the evidence; re-run the study that writes it" % name)
    return m.groups()


def facts():
    """Every load-bearing number the three explanations quote, read out of the evidence files that measured it, or
    out of the sealed definition where it is a property of the fleet rather than a measurement.

    The explanations used to state these from memory. They drifted - a method count, two deviations, the number
    of orders that work - leaving the prose asserting what the studies contradicted. Reading them here means
    the text cannot say anything the evidence does not, and `--check` fails if a study has been re-run since
    README.md was written."""
    f = {}

    t = _ev("method_spread.txt")
    f["spread_q"], f["spread_s"] = _grab(
        t, r"widest deviation over every sound method and chamber: gas load ([\d.]+)%, speed ([\d.]+)%", "spread")
    f["margin_q"], f["margin_s"] = _grab(t, r"margin ([\d.]+)x and ([\d.]+)x", "margins")
    (n,) = _grab(t, r"all (\d+) sound methods accepted, and both audits right on every laboratory seed",
                 "method count")
    f["methods"], f["methods_word"] = int(n), WORDS[int(n)]

    t = _ev("reference_run.txt")
    (ch, sp, nxt, x) = _grab(t, r"planned order: (VC\d\d) \S+ at [\d.]+ h; its spread ([\d.]+)%, the next "
                                r"chamber's ([\d.]+)% \(([\d.]+)x\)", "planned order")
    if ch != "VC06":
        raise SystemExit("meta.py: the planned order is on %s, not VC06" % ch)
    f["vc06_spread"] = "%.0f" % float(sp)
    f["plan_x"] = WORDS[int(float(x))]
    (v1,) = _grab(t, r"VC01 read with both gauges: ([\d.]+)% wide", "VC01 with both gauges")
    (v1n, naive_ch) = _grab(t, r"VC01 on the reference instrument alone: ([\d.]+)% wide; that profile orders (VC\d\d)",
                            "VC01 on the reference instrument")
    if naive_ch != "VC01":
        raise SystemExit("meta.py: the profile on the reference instrument alone orders %s, not VC01" % naive_ch)
    f["vc01_spread"], f["vc01_naive"] = "%.0f" % float(v1), "%.0f" % float(v1n)

    t = _ev("seed_screen.txt")
    (n,) = _grab(t, r"both audits accepted on the shipped seed and on all (\d+) screened seeds", "seed screen")
    f["screened"], f["screened_word"] = int(n), WORDS[int(n)]

    t = _ev("plan_sweep.txt")
    (good, tried) = _grab(t, r"ORDERS THAT WORK FOR THE REFERENCE: (\d+) of (\d+)", "orders that work")
    (good_i, tried_i) = _grab(t, r"ORDERS THAT WORK FOR THE INDEPENDENT: (\d+) of (\d+)", "independent orders")
    (edge,) = _grab(t, r"ORDERS AT THE EDGE, CARRYING ONE AUDIT ONLY: (.*)", "orders at the edge")
    f["orders_good"], f["orders_good_word"] = int(good), WORDS[int(good)]
    f["orders_tried"] = int(tried)
    f["orders_edge"] = ("" if edge == "none" else
                        " The one difference is at the edge of that region: %s." % edge)
    block = t.split("ORDERS THAT WORK FOR THE REFERENCE")[1].split("ORDERS THAT WORK FOR THE INDEPENDENT")[0]
    names = re.findall(r"^  (VC\d\d) (\S+) at ([\d.]+) h$", block, re.M)
    others = re.findall(r"^  (VC\d\d) (helium)$", block, re.M)
    if len(names) + len(others) != int(good):
        raise SystemExit("meta.py: plan_sweep.txt lists orders that are neither gas-load tests at a time nor helium")
    chambers = sorted({c for c, _k, _h in names} | {c for c, _k in others})
    f["order_chambers"] = " and ".join(chambers)
    f["order_tests"] = ", ".join(sorted({k for _c, k, _h in names}))
    hours = sorted({float(h) for _c, _k, h in names})
    f["order_hours"] = "from %g to %g h" % (hours[0], hours[-1])
    f["order_helium"] = (", or a helium test on %s, which measures the leak the face-value budget overstates"
                         % " and ".join(sorted({c for c, _k in others}))) if others else ""
    (times,) = _grab(t, r"pumping times tried: ([\d ]+) h", "pumping times")
    f["times_tried"] = ", ".join(times.split())
    f["default_h"] = "%g" % FL.DEFAULT_TEST_H

    t = _ev("route_study.txt")
    (n, c) = _grab(t, r"all (\d+) routes rejected; every chamber defeats at least (\d+) routes", "route count")
    f["routes"], f["routes_word"] = int(n), WORDS[int(n)]
    f["routes_per_chamber"], f["routes_per_chamber_word"] = int(c), WORDS[int(c)]
    f["nearest_miss"], f["nearest_miss_x"] = _grab(
        t, r"nearest defective miss on a quantity: ([\d.]+)% \(([\d.]+)x", "nearest defective miss")
    (n, names, big) = _grab(
        t, r"routes rejected by one chamber alone: (\d+) \((.+?)\), each required to miss it by at least"
           r" ([\d.]+)x", "single-chamber routes")
    f["single_routes"], f["single_routes_word"] = int(n), WORDS[int(n)]
    f["single_route_names"] = ", ".join(names.split())
    f["big_miss_x"] = big
    (fv,) = _grab(t, r"(?m)^face_value\s+(\d+)\s", "face-value route")
    f["face_value_word"] = WORDS[int(fv)]
    (fewest,) = _grab(t, r"\(fewest routes missing it on one seed\)\s+(\d+)", "fewest routes on a seed")
    f["fewest_on_seed"] = fewest

    t = _ev("null_baselines.txt")
    (n,) = _grab(t, r"the most any gets right is (\d+) of 10", "null baseline best")
    f["null_best"] = int(n)

    t = _ev("reference_run.txt")
    f["ref_q"], f["ref_s"] = _grab(t, r"worst deviation: gas load ([\d.]+)%, speed ([\d.]+)%", "reference run")
    (f["ref_order"],) = _grab(t, r"order placed: (.+)", "reference order")

    t = _ev("fleet_ranges.txt")
    for key in ("volume_l", "turbo_l_s", "port_l_s", "s_eff_l_s", "seal_cm", "seal_materials", "surface_m2",
                "wall_factor", "leak", "tau_h", "q_total", "p_base", "pumpdowns", "pumpdown_h", "climate",
                "log_period", "read_noise_pct"):
        (v,) = _grab(t, r"(?m)^%s: (.+)$" % key, "fleet range %s" % key)
        f[key] = v.strip()

    t = _ev("verifier_checks.txt")
    (n,) = _grab(t, r"all (\d+) cases behaved as the rules say", "verifier case count")
    f["cases"], f["cases_word"] = int(n), WORDS[int(n)]
    f["band_cases"] = len(re.findall(r"on the (?:gas-load|speed) band", t))

    t = _ev("hedge_study.txt")
    (n, nch, nc) = _grab(t, r"cases: (\d+) \(each of (\d+) chambers against each of the other (\d+) causes\)",
                         "hedge case count")
    f["hedge_total"], f["hedge_total_word"] = int(n), WORDS[int(n)]
    f["hedge_chambers"], f["hedge_alternatives"] = int(nch), int(nc)
    (f["hedge_inside"],) = _grab(t, r"forced readings that keep the gas load in its band: (\d+) of \d+",
                                 "hedge inside")
    f["hedge_inside"] = int(f["hedge_inside"])
    (u,) = _grab(t, r"forced readings the records leave too few observations to fit: (\d+) of \d+", "hedge unfit")
    f["hedge_unfit"], f["hedge_unfit_word"] = int(u), WORDS[int(u)]
    f["hedge_outside"] = f["hedge_total"] - f["hedge_inside"] - f["hedge_unfit"]
    if "PROBLEM" in t:
        raise SystemExit("meta.py: hedge_study.txt reports a sheet naming a wrong cause was accepted")

    # the grader's own figures
    sys.path.insert(0, os.path.join(TASK, "tests"))
    import grade_audit as G
    f["q_tol"], f["s_tol"] = "%.1f" % (100 * G.Q_TOL), "%.1f" % (100 * G.S_TOL)

    # properties of the fleet, from the sealed definition
    f["ref_h"] = "%g" % FL.REF_H
    f["test_h_min"], f["test_h_max"] = "%g" % FL.TEST_H_MIN, "%g" % FL.TEST_H_MAX
    f["cross_pct"] = "%.0f" % (100 * (FL.BY["VC07"]["certs"]["CC-7107"][0][1] - 1.0))
    f["cert_pct"] = "%.0f" % (100 * (FL.BY["VC01"]["true"]["cert_wrong"][1] - 1.0))
    f["gate_ratio"] = "%g" % PH.PUMP_GATE
    nv = sum(1 for cid in FL.CHAMBER_IDS if any(e[2] == "nitrogen" for e in FL.BY[cid]["log"]))
    f["n2_chambers_word"] = WORDS[nv]
    f["longest_log_h"] = "%g" % max(e[3] for cid in FL.CHAMBER_IDS for e in FL.BY[cid]["log"])
    longest = max(sp[1] for cid in FL.CHAMBER_IDS for sp in FL.BY[cid]["speed"])
    f["longest_test_h"] = "%g" % longest
    f["longest_test_at"] = [cid for cid in FL.CHAMBER_IDS if any(sp[1] == longest for sp in FL.BY[cid]["speed"])][0]
    return f


F = facts()


def fill(s):
    """Substitute every {name} from the measured facts, and refuse to emit text with one left over.

    Deliberately not %-formatting: these texts are prose with per cent signs in them, and a formatting
    character that has to be escaped is a formatting character that will one day be missed."""
    for k, v in F.items():
        v = str(v)
        s = s.replace("{%s}" % k, v)
        # {Name} for the same figure at the start of a sentence
        s = s.replace("{%s%s}" % (k[:1].upper(), k[1:]), v[:1].upper() + v[1:])
    left = re.search(r"\{[A-Za-z_]+\}", s)
    if left:
        raise SystemExit("meta.py: no measured fact for %s" % left.group(0))
    return rewrap(s)


WIDTH = 116


def _fold(words, first_indent, rest_indent):
    lines, line = [], ""
    for w in words:
        cand = (line + " " + w).strip()
        limit = WIDTH - len(first_indent if not lines else rest_indent)
        if line and len(cand) > limit:
            lines.append(line)
            line = w
        else:
            line = cand
    if line:
        lines.append(line)
    return [(first_indent if i == 0 else rest_indent) + ln for i, ln in enumerate(lines)]


def rewrap(s):
    """Reflow the generated prose to WIDTH columns.

    A substituted figure is a different length from the placeholder it replaced, so text wrapped by hand before
    substitution is not wrapped after it: lines run long and words are orphaned. Blocks that are not prose are
    left alone - headings, tables, and anything indented four spaces or more, which is code."""
    out = []
    for block in s.split("\n\n"):
        lines = block.split("\n")
        if not block.strip() or lines[0].startswith(("#", "|", "    ")):
            out.append(block)
            continue
        items, cur = [], None
        for ln in lines:
            if ln.startswith("- "):
                if cur:
                    items.append(cur)
                cur = ["- ", ln[2:].strip()]
            elif cur is not None and ln.startswith("  "):
                cur.append(ln.strip())
            else:
                if cur:
                    items.append(cur)
                    cur = None
                if items and items[-1][0] == "":
                    items[-1].append(ln.strip())
                else:
                    items.append(["", ln.strip()])
        if cur:
            items.append(cur)
        rendered = []
        for it in items:
            kind, words = it[0], " ".join(it[1:]).split()
            rendered.extend(_fold(words, kind, "  " if kind else ""))
        out.append("\n".join(rendered))
    return "\n\n".join(out)

DIFFICULTY = """In practice this is the work of a vacuum process engineer auditing a shop's chambers: naming what
limits each one's base pressure and quantifying it, so that the shutdown can be planned around the chambers worth
opening. The engineer has the chambers' own records and a single contractor's test that has to be ordered before its
result is known. Its research analogue is the identification of vacuum systems from operating data: the
steady gas balance p = Q / S_eff of a lumped volume, water desorption from chamber walls and its temperature
dependence, permeation of atmospheric gas through elastomer seals and the composition it admits, the emptying of a
trapped volume, gas corrections for nitrogen-calibrated gauges, and residual gas analysis read as a mixture of
sources.

The chambers and records are synthetic, written by `authoring/provenance` (`bpphys.py`, `fleet.py`, `docs_bp.py`,
`build.py`) from a sealed definition. They are realistic in their numbers:
- Chambers of {volume_l} L, on turbomolecular pumps of {turbo_l_s} L/s through ports of {port_l_s} L/s.
- Effective pumping speeds of {s_eff_l_s} L/s.
- Elastomer seals of {seal_cm} cm, in {seal_materials}.
- Turbo controllers reporting rotor frequency, drive power and bearing temperature weekly, against the maker's
  figures for a pump of that model in order.
- Internal surfaces of {surface_m2} m2, electropolished, machined or bead blasted, with anodised aluminium
  shields.
- Wall gas load coefficients of {wall_factor} times the outgassing table's nominal figure.
- Real air leaks of {leak} mbar L/s.
- Trapped volumes emptying with time constants of {tau_h} h.
- Total gas loads of {q_total} mbar L/s, and base pressures of {p_base} mbar, every one of them above the
  chamber's specified base pressure.
- {pumpdowns} recent pumpdowns per chamber, of {pumpdown_h} h, over {log_period}, in a shop whose air runs from
  {climate}, with gauge readings repeatable to {read_noise_pct} per cent.

The reference condition is the same for every chamber: {ref_h} h from the start of roughing after an air vent, the
chamber wall at 20 C, nothing in the chamber. That is longer than every pumpdown in the base-pressure log (the
longest is {longest_log_h} h), so no entry can be read across to it: every chamber's gas load is the sum of
mechanisms that extrapolate differently in pumping time and temperature, and only a budget identified across the
chamber's own entries reaches the reference condition. Each chamber's limiting cause is the mechanism with the
largest gas load there, except that a chamber whose actual speed is below {gate_ratio} of its rated speed is
limited by its pump whatever its gas load is doing.

The example chamber, VC00, has sound records throughout: one gauge, a speed test that still describes its pump, no
work in the maintenance log over the period of its log, and no load on any pumpdown. It is there to show the
format of the records and that they can be sound. **No audited result is given for it**: MS-BP clauses 2 to 7 fix
every convention the audit needs, so a worked answer would add nothing but an end-to-end check of a whole audit
against a known figure.

The ten chambers carry the faults that shop records carry. Each looks like ordinary data, and the documents say
only what was done, never its effect. Fourteen of the layers are settled by the data alone:
- **A reference condition no entry reaches.** Every chamber carries at least two mechanisms of comparable size,
  and its entries are spread in pumping time, vent gas and wall temperature, so that reading the latest entry
  across to the reference condition by any one mechanism's law misses. The budget has to be identified.
- **A fouling cold cathode.** On two chambers a cold cathode reads progressively low. The drift is a ramp and never
  a step, so it shows only as a slow trend in the ratio to the chamber's reference instrument, and on both the
  reference instrument fails part way through, leaving the later pumpdowns to be corrected by the fitted trend
  (VC02, VC09).
- **Crossed gauge serials.** Two chambers have each other's gauge serial in the log for their last three
  pumpdowns. The certificates are right, the two factors differ by {cross_pct} per cent, and the only sign is a step
  in each chamber's own series where its serial changes (VC03, VC07).
- **A seal the register gets wrong.** On one chamber the register names a perfluoroelastomer seal, while a nitrile
  one has been in place throughout, and nothing in any document says so. Taken from the register, the permeation is
  small and the rest of the constant gas load reads as a leak. Across the season that constant part follows the
  wall temperature as permeation through nitrile does, which a leak cannot (VC05).
- **A leak against permeation.** Both are constant in pumping time and both admit air, so only the gas load's
  temperature dependence across the log, or the oxygen and argon of a residual gas analysis, separates them
  (VC04 against VC06).
- **A shop instrument that is wrong for every chamber at once.** Every shop speed test admits the same calibrated
  leak, and since the spring it has admitted more than it states, so every shop test since reports a speed low by
  one factor, on every chamber, while each chamber's own record looks like a pump that has lost a little speed and
  every controller shows its pump in order. Only the fleet shows it: a pump in order delivers its rated speed, and
  every chamber whose rated speed is on record tested at it before the change and below it by the same factor
  after. It matters most where nothing else gives the speed: on two chambers a baffle or trap was fitted without
  its conductance being recorded, so their speed is their speed test's, put right by the fleet's factor (VC03,
  VC05). It also moves every gas load read through a test's speed, VC08's 42 h reading among them, and the factor
  a test puts on a gauge certificate (VC01, VC04).
- **A speed test that is also a reading.** A shop speed test records the chamber's own base pressure before the
  flow is admitted, at the pumping time and wall temperature of that pumpdown. On one chamber it is the only
  reading at a long pumping time: VC08's load went up ninefold when its cryopanel brackets were replaced, every
  log entry since is at 16 h, and the log alone says nothing about how fast the new source falls. Its October speed
  test, taken after a {longest_test_h} h weekend pumpdown, does, so VC08 is the chamber that looks as if it
  needs the test and does not.
- **A trapped volume that nothing shows.** VC06's shroud panels were replaced in September, and the new panels'
  fixing holes trap a volume that empties over well more than a day. It has been there since the refit, so nothing
  steps, and the earlier entries are void by the change of internals anyway. Of the five pumpdowns since, the two
  short ones were air vents and the three long ones nitrogen vents: in the face-value budget the trapped gas still
  there at 20 h reads as a constant leak, and its fall from the short pumpdowns to the long reads as the wall gas the
  nitrogen vents leave out. That budget fits the entries and the October speed test to the noise, with plausible
  coefficients, and puts the gas load at the reference condition about a sixth high. No residual, ratio, step or
  record points to it. What finds it is asking of every chamber how far its records determine the answer: refit
  each with every trapped volume clause 3.3 allows and keep the budgets the records cannot reject. VC06's kept
  budgets spread over {vc06_spread} per cent at 36 h, more than {plan_x} times any other chamber's; so it is the
  chamber the test is needed on, at a long pumping time.
- **Two gauge types that read the same gas differently, and a chamber that only both of them settle.** The vacuum
  data give each gauge type its own sensitivities, and the cold cathode reads water well below the ionization
  gauge, so every cold cathode reading needs its own type's correction, and on a pumpdown read with both the ratio
  of the two readings measures the wall's share of the gas. VC01 was relined in September; since then its air vents
  have been short and its nitrogen vent long, the same confounding as VC06's, and both gauges were read on every
  pumpdown. Profiled on its reference instrument alone, as clause 5's naming of the ionization gauge invites, VC01's
  gas load at 36 h is the fleet's least determined, at {vc01_naive} per cent, ahead of VC06; an audit that profiles
  that way spends the test on VC01 and misses VC06. Read with both gauges, each through its own sensitivities,
  VC01 closes to {vc01_spread} per cent and has no trapped volume. The same ratio, with the composition divided out,
  is what shows a cold cathode drifting.
- **A chamber that looks as if it needs the test and does not.** VC07's fixture plate was refitted in July and a
  trapped volume behind it empties with a time constant of a day; its pump is not the register's and its gauge
  serial is crossed with VC03's. Its pumpdowns since span 12 to 24 h and both vent gases, so once the pump and
  the certificate are right its own records settle the trapped volume.
- **A pump with an ordinary gas load.** Two chambers are limited by speed while their gas loads are unremarkable,
  so an audit that puts every shortfall down to gas names the wrong cause and reaches the wrong figure for both
  quantities (VC09, VC10).
- **A gauge correction that depends on the answer.** The correction of MS-BP clause 5 follows from the composition,
  the composition follows from the split of the gas load, and the split follows from the corrected pressures, so
  the cause and the quantities have to be settled together.
- **A wall gas load that is not the table's.** Every chamber's coefficient differs from the outgassing table's
  nominal figure, from {wall_factor} times it, so the table sizes a pump but does not audit a chamber.
- **A gauge certificate that is wrong, and that no residual can show.** On one chamber the calibration laboratory
  issued the factor {cert_pct} per cent out. The error cancels in the gas load - every pressure the certificate
  yields is low by the same factor and every speed it yields is high by it, so Q = p S_eff comes out right and the
  gas budget fits to the reading noise - and it shows only in the speed, which comes out above what the chamber's
  pump in series with its port can deliver. MS-BP clause 4 says a pump delivers at most its curve, so the chamber's
  own throughput tests contradict its certificate, and its hot-filament gauge, the reference instrument of clause 5,
  disagrees with it by exactly that factor (VC01).
- **A replacement gauge whose certificate is out, which every simple reading fits.** On one chamber the cold
  cathode was swapped part way through the log for a spare head from stores, and the spare's certificate, issued
  the year before, is out: it reads every pressure high, so the speed test run on it reports the pump, which its
  controller shows in order, well below rated, where the old gauge's tests put it at rated. Take
  that test at its word and the gas budget fits to the noise, with the gas load right and the speed wrong. Take the
  pump at its rated speed and the certificate as issued, and the readings step up at the replacement, which a
  trapped volume dated to that maintenance entry absorbs just as cleanly, with the gas load and the cause wrong.
  Only the gauge explains both the step and the low test: a trapped volume cannot change a throughput test, and the
  vacuum data say a pump in order delivers its rated speed (VC04).
- **A register that names the wrong pump, which no fit can see.** On one chamber the register names a larger pump
  than the one that is fitted. Nothing in the gas budget depends on it; what depends on it is the rated speed, and
  with the register's pump the chamber's sound speed falls below clause 6's gate. The controller reports the rotor
  frequency, drive power and bearing temperature of the pump that is actually turning, and the vacuum data give
  those three figures for each model (VC07).

Nine more are recorded somewhere in the documents and have to be found and applied:
- **Internal surfaces replaced**, so the register's surface no longer applies and the entries before the work
  cannot be pooled with those after it (VC01, VC02, VC06).
- **A seal changed**, so one permeation constant does not serve the whole log (VC04, VC06).
- **A baffle or trap fitted** in the high-vacuum port, so the chamber's rated speed is not the register's and a
  sound pump is not judged against a conductance it no longer has (VC03, VC04, VC05).
- **A turbo that has lost speed**, dated by the controller's weekly rows, which voids every speed test taken
  before it (VC09, VC10).
- **A dated recalibration** of a gauge, which the certificate carries and the log does not (VC10).
- **Dry nitrogen vents** on some pumpdowns, after which the wall gas load is a quarter of what an air vent leaves
  ({n2_chambers_word} of the ten chambers).
- **Fixtures left in the chamber** on some pumpdowns, adding their own area to the outgassing (VC01, VC02, VC04,
  VC10).
- **Pumpdowns of different lengths and wall temperatures**, which have to be referred to one condition before any
  of them can be compared.
- **A test taken when the plan says.** The contractor tests at {default_h} h unless the plan names another pumping
  time, from {test_h_min} to {test_h_max} h (`vacwork.md`). At {default_h} h the one chamber the test is needed on
  only repeats its log.

Each check left out or done the obvious way gets chambers wrong, and every chamber of the fleet must be right
(`authoring/evidence/route_study.txt`). {Routes_word} routes, each leaving out one check or doing it the obvious
way, are each rejected; each chamber is missed by at least {routes_per_chamber_word} routes; and each chamber is
missed by at least one route on its cause alone, so no chamber's grading turns on where the tolerance is drawn.
Taking the records at face value - the register's surfaces, seal and port, the latest speed test, the logged
serials, every entry pooled, the table's gas load and no gauge correction - gets {face_value_word} of the ten wrong.

The audit test is load-bearing and measured to be so (`authoring/evidence/plan_sweep.txt`), over the whole space
of orders the budget allows: each gas-load test (rga, rate-of-rise, speed-test) on each chamber at each of the
pumping times {times_tried} h, a helium test on each chamber, and placing no order at all, {orders_tried} orders in
all. {Orders_good_word} of them carry the reference to a pass, and the independent audit is carried by the same
ones: a gas-load test on {order_chambers} ({order_tests}) at a pumping time {order_hours}{order_helium}.{orders_edge} A test on
VC07 or VC08, the chambers whose records point at themselves, is spent where their own entries and speed tests
already answer; and at the contractor's default {default_h} h a test on VC06 only repeats what its log already
says."""

SOLUTION = """`solution/diagnose.py` is the reference audit and `solution/solve.sh` places the order and runs it.
For each chamber it does the following.

- **The chamber as it stands.** The register entry, changed by every maintenance row on or before the audit date:
  internal surfaces replaced, a seal changed in material or length, a trap or baffle fitted in the high-vacuum
  port. The pump is the one the controller's own figures identify. The seal is kept as a dated history, because a
  seal changed part way through the log means one permeation constant will not serve every entry.
- **The instruments.** Where a gauge serial in one chamber's log belongs to another chamber's certificate and that
  chamber's log carries this one's serial, the two are read back the right way round. A cold cathode is checked
  against the hot-filament gauge wherever both were read: the two types read the same gas through different
  sensitivities, so the composition each pumpdown's first budget gives is divided out of their ratio, and a drift in
  what is left is carried as a straight line to the pumpdowns the reference instrument did not see. Where the cold
  cathode holds its line, both readings of every pumpdown are kept. A certificate is out where the throughput tests read on that
  gauge report a speed the pump and port cannot have: above rated, or below it while the controller shows the pump
  in order. That gauge's readings and those tests' speeds are put right by the same factor.
- **The shop's calibrated leak.** Every shop speed test on a chamber whose rated speed is on record and whose pump
  was in order that day measures the leak's real flow against its stated one. Split in date order where the two
  sides' medians are best separated, they show the leak changed in the spring, and every test since is put right
  by that factor before anything else reads it.
- **The speed.** The pump curves are flat at base pressure, so the speed is one constant between the dates on which
  it can change: a trap fitted in the port, or a step in the controller's drive power and bearing temperature. The
  speed now is the ordered test's, read on the contractor's own gauge, or the latest shop test since the last such
  date; where neither exists it is found with the gas budget.
- **The observations.** Every kept base-pressure entry is an observation of the gas load at the speed in force on
  its date, whichever pump or port it was taken with: the gas load does not depend on the pump. Entries are kept
  from the last change of internals on. Each shop speed test is one more: its no-flow pressure is the empty
  chamber's base pressure at the test's own pumping time and wall temperature, taken with the speed that test
  measured. An ordered analysis or rate-of-rise is one more observation at its own pumping time and wall
  temperature, and a helium test is an observation of the leak.
- **The gas budget.** Fitted as MS-BP clause 3 gives it, Q_i = C_w W_i + Q_L + Q_v0 exp(-t_i / tau) + Q_perm,i,
  the trapped term only on and after the date it appeared, with W_i the table's nominal wall load for the entry's
  surfaces, fixtures, vent gas and wall temperature and Q_perm,i the seal's permeation at its temperature. Every
  coefficient is non-negative, each observation is weighted by its own repeatability, and the gauge correction of
  clause 5, which depends on the split and on the gauge's type, is iterated to a fixed point.
- **Which budget.** Every structure the records leave open is fitted: no trapped volume, one present from the
  start, or one that appeared on a date of logged work; the register's seal material, or another of the table's in
  its place. The fit with the least AIC is kept, with the small-sample correction wherever the sample allows it, so
  that a chamber with few entries since its last change does not take on a trapped volume on one degree of freedom.
  Setting the register's seal aside costs a fixed penalty, so it happens only where the records plainly contradict
  it. A structure is admissible only if it leaves more
  observations than parameters, and where the misfit is flat in the time constant - nothing measures how fast the
  trapped volume empties - the bound of clause 3.3 is taken, as a statement of what is not known.
- **The order.** Before any result is known, every chamber's records are fitted as above and then asked which
  other budgets they would accept as well. Clause 3.3 allows a trapped volume on any chamber, present from the
  start or from any logged work, of any size and with any time constant up to its bound; for each, the rest of the
  budget is refitted, and kept if its chi-square is within four of the best, the 95 per cent bound on one quantity.
  The spread of the kept budgets' gas loads at 36 h is how far that chamber's records determine its answer. It is
  worked where the observations are, each reading the mechanisms' loads weighted by its gauge type's sensitivity
  to their gas, so a pumpdown read on both types tells wall from air. The one test goes, at the reference
  condition's own 36 h, to the chamber where the spread is widest (`diagnose.py --plan`).
- **The reference condition and the cause.** The fitted budget is evaluated at {ref_h} h, 20 C, an air vent and
  no load, with the surfaces and seal the chamber has on the audit date. The cause is the pump where the actual
  speed is below {gate_ratio} of the rated speed of the chamber as it is now, and otherwise the mechanism with the
  largest load.

The order it places is the whole budget of one test: {ref_order}. Of the {orders_tried} orders the budget allows,
{orders_good_word} carry the reference to a pass, all on {order_chambers}: a gas-load test at a pumping time
{order_hours}{order_helium} (`authoring/evidence/plan_sweep.txt`).

Run through `tests/grade_audit.py` as the verifier reads a submission, the reference gets every chamber right, with
its gas loads within {ref_q} per cent of the truth and its speeds within {ref_s} per cent
(`authoring/evidence/reference_run.txt`)."""

VERIFICATION = """`tests/grade_audit.py` reads the submitted `/app/output/diagnosis.csv` and compares it with the
sealed fleet. The truth is computed from `tests/sealed/fleet.py` and `tests/sealed/bpphys.py` at grading time, from
the chamber's true volume, pumps, port, surfaces, seal, wall gas load coefficient, leak and trapped volume as they
are on the audit date, by MS-BP's model at the reference condition. It is never taken from running the reference
solution, and `authoring/evidence/preflight.py` checks that the sealed files under `tests/` and
`environment/rig/` are the provenance files byte for byte.

The sheet must be a regular file, not a symlink, of at most 100000 bytes of ASCII text: the header line exactly
`chamber,cause,q_total_mbarl_s,s_eff_l_s`, then one row for each of the ten chambers with none repeated, missing
or unknown; the cause one of MS-BP's five names, spelled as the standard spells it; the gas load and the speed
finite numbers inside generous ranges. Blank lines and surrounding spaces are ignored and the rows may be in any
order. Anything else is rejected, with a reason, and no submission crashes the grader. The instruction states
every one of these rules.

A chamber is right when all three of its fields are right: the cause matches exactly, the gas load is within {q_tol}
per cent of the truth and the speed within {s_tol} per cent. The sheet is accepted when every one of the ten
chambers is right. The instruction states the two tolerances; it does not say how many chambers must be right.

Why these tolerances, and why every chamber:
- **Correct methods.** Each tolerance is twice the widest deviation any sound method reaches on any chamber, and
  never less than the widest either audit reaches on records rebuilt from another draw of the instrument noise,
  rounded up to the half per cent; preflight recomputes that rule from the record. {Methods_word} sound methods
  are accepted, each a complete sheet scored through this grader (`authoring/evidence/method_spread.txt`): the
  reference on the order it places and on five other sound orders, gas-load tests on VC06 at other pumping times;
  `authoring/evidence/independent.py`, a second audit written from the documents alone that shares no code with
  the reference, on each of the same orders - it solves the whole budget jointly by nonlinear least squares in the
  logarithm of the gas load, selects structures by BIC rather than AIC, with any added mechanism required to leave two degrees of freedom and to improve the fit significantly at one per cent, finds a seal the register gets wrong as a
  free permeation scale that is adopted only where it is well determined and lands on a material of the table,
  dates a turbo's change by a changepoint test, and finds the calibrated leak's change by the largest separation of trimmed means rather than of medians; and six variations of the reference - dropping the oldest
  entry, averaging the period's speed tests, asking twice or half the evidence before setting the register's seal
  aside, weighting the ordered test as a gauge reading, and a finer grid of time constants. Both audits are also
  right on VC06 on each of the twenty laboratory seeds of the ordered test's scatter, and on records rebuilt from
  each of {screened_word} other draws of the shop's instrument noise (`authoring/evidence/seed_screen.txt`). Over
  every sound method and chamber the widest deviation is {spread_q} per cent on the gas load and {spread_s} per
  cent on the speed, so the tolerances stand at {margin_q} and {margin_s} times the spread of sound work.
- **Defective routes.** {Routes_word} routes, each the reference with one check left out or done the obvious way,
  are all rejected (`authoring/evidence/route_study.txt`). {Single_routes_word} of them are rejected by a single
  chamber - {single_route_names} - and the study fails unless each of those misses its chamber by at least
  {big_miss_x} times the tolerance or on the cause outright, so no route is rejected on a knife edge. Routes that
  miss several chambers may graze a band on one of them: the nearest miss on a quantity anywhere in the study is
  {nearest_miss} per cent, {nearest_miss_x} times the gas-load tolerance. That costs nothing, because every chamber
  is missed by at least {routes_per_chamber_word} routes, and by at least one on its cause alone. On every
  laboratory seed of the ordered test VC06 is still missed by at least {fewest_on_seed} routes.
- **Every chamber.** The allowance of one wrong chamber that earlier tasks carried is not used here, and the
  reason is measured (`authoring/evidence/plan_sweep.txt`): with an allowance of one, the audit test is not
  load-bearing at all, because the reference passes with no test ordered. Requiring every chamber makes the one
  chamber whose own records cannot settle its gas load decide the sheet, which is what the test is for.

Method-free answers are all rejected and none of them gets a single chamber right
(`authoring/evidence/null_baselines.txt`): the true result of one real chamber of the same shop copied onto all
ten; each of the five causes given to all ten; the latest reading times the latest speed test; the specified base
pressure times the latest speed test; the register's rated speed with the gas load it and the specification imply;
and three single-entry shortcuts that use the reference's own corrected readings and speed but read the gas load
off the latest entry - as it stands, with the table's wall and the rest a leak, or with the rest put down to the
wall. No chamber has a free pass.

`authoring/evidence/hedge_study.txt` records what a wrong attribution does to the quantities. It runs the reference
with its reading forced to each cause but the chamber's own - {hedge_chambers} chambers times {hedge_alternatives}
alternatives, {hedge_total_word} cases - and scores each sheet, naming that cause, through this grader. A wrong
cause fails the chamber by definition; what the study measures is whether the gas load survives the wrong reading.
In {hedge_inside} of the {hedge_total} cases it does and in {hedge_outside} it does not; in the other
{hedge_unfit_word} the records leave too few observations to fit the forced reading at all. Not one sheet is
accepted. Where the total survives a wrong attribution the chamber is decided by the cause, which is graded on its
own.

Malformed sheets and edge cases are all built from the current reference at run time, never hard-coded, and scored
by the same grader the verifier calls (`authoring/evidence/verifier_checks.txt`). {Cases_word} cases all behave as
the rules say: a sheet that is a symlink, a directory or absent; no header, a renamed column, the columns
reordered, an extra column; a row missing or repeated; an unknown chamber; a cause outside the list or in the
wrong case; a gas load that is not a number, NaN, infinite, negative, zero or far out of range; a speed of zero,
far out of range, or a boolean; an empty file; bytes that are not ASCII; and a sheet padded past the size limit.
{band_cases} of those cases are the bands themselves: each band is tried just inside and just outside, above and
below the truth, so both edges of both bands are measured rather than assumed.

Every evidence record carries on its first line a fingerprint of the files its result depends on, and preflight
fails if any record was written from inputs that have since changed.

The single pytest test decides the reward. `tests/test.sh` writes 0 to the reward file before grading starts, locks
`/logs/verifier` to root before grading and again before the reward, and writes 1 only when pytest exits 0 and the
ctrf report holds exactly one test, passed, with none failed, skipped, pending or other. A crash, a timeout or a
missing sheet all leave 0. Per-chamber results go to `/logs/verifier/metrics.json`, where they do not affect the
reward. The verifier pins numpy 2.1.3, scipy 1.14.1, pandas 2.2.3, pytest 8.4.1 and pytest-json-ctrf 0.3.5, runs in
its own environment without network, and keeps `/tests` at 700 so the sealed fleet is not readable.

In the agent's image the agent works as its own user and can write only to `/app/output`; `/app/data` is read-only.
The audit test order and the sealed definition belong to a separate contractor user, and the agent reaches the
order through one sudo rule that allows nothing but its status and submit commands. The order is charged to the
contractor's state file before any report is written, and a state that cannot be read counts as already placed, so
no test can be had twice."""



# Every figure in the three texts above comes from fill(), which reads the evidence files. A number typed into
# a figure into the prose by hand is how a method count, two deviations and the number of orders that work all
# came to disagree with the studies that measured them.
DIFFICULTY = fill(DIFFICULTY)
SOLUTION = fill(SOLUTION)
VERIFICATION = fill(VERIFICATION)

def readme():
    return """# base-pressure-diagnosis

A coating and thermal-processing shop audits the ten vacuum chambers that are not reaching their specified base
pressure. For each chamber the audit names what limits it and quantifies it, under the shop's standard MS-BP.

The chamber is a lumped volume, p = Q_total / S_eff, and MS-BP splits the gas load into four mechanisms: water
outgassing from the internal surfaces, which decays as a power of the pumping time and rises steeply with
temperature; a real air leak, constant in both; a trapped volume emptying as a single exponential; and permeation
of atmospheric air through the elastomer seals, constant in time, steeply temperature dependent and enriched in
oxygen by the elastomer. The effective speed is the turbo pump in series with the high-vacuum port as fitted. A
chamber whose actual speed has fallen below 0.75 of its rated speed is limited by its pump, whatever its gas load.

Everything is referred to one condition: %s h from the start of roughing after an air vent, the chamber wall at
20 C, nothing in the chamber.

The deliverable is `/app/output/diagnosis.csv`, with the header `chamber,cause,q_total_mbarl_s,s_eff_l_s` and one
row for each of VC01 to VC10: the limiting cause, the total gas load at the reference condition in mbar L/s, and
the chamber's actual effective pumping speed there in L/s.

The records are the chamber register, the base-pressure log, the shop's throughput speed tests, the turbo
controllers' weekly rows, the maintenance log, the gauge certificates and the shop's daily climate record, with the
standard and the shop's vacuum data in `docs/` and an example chamber's records, without a result, in `example/`.

Beyond the records there is one contractor's test, ordered once through the `vacwork` command before its result is
known, from four kinds: a rate-of-rise, a throughput speed test, a residual gas analysis and a helium leak test,
the first three taken after a pumping time the plan may choose.

## Difficulty

%s

## Reference solution

%s

## Verification

%s
""" % (F["ref_h"], DIFFICULTY, SOLUTION, VERIFICATION)


def _task_name():
    """The task's name as task.toml already holds it. The name's prefix is written in task.toml alone and appears
    nowhere else in the bundle (the playbook's packaging rule), so it is read back rather than restated here."""
    import tomllib
    with open(os.path.join(TASK, "task.toml"), "rb") as f:
        return tomllib.load(f)["task"]["name"]


def task_toml():
    return '''schema_version = "1.4"

artifacts = ["/app/output/diagnosis.csv"]

[task]
name = "%s"
description = "Audit the ten vacuum chambers of a coating shop that are missing their specified base pressure: for each one name the mechanism that limits it and report its total gas load and its actual effective pumping speed at the standard's reference condition, from the chambers' own records and one contractor's test order of a single test placed before any result is known."
authors = [{ name = "Alireza Bafandeh", email = "rahattar@gmail.com" }]
keywords = [
    "vacuum-technology",
    "base-pressure",
    "outgassing",
    "permeation",
    "residual-gas-analysis",
    "system-identification",
]

[metadata]
author_name = "Alireza Bafandeh"
author_email = "rahattar@gmail.com"
author_organization = "MEMC"
author_profile = "https://www.linkedin.com/in/alireza-bafandeh"
research_advisor = ""
referred_by = ""
conflicts_of_interest = "I am employed by MEMC (GlobalWafers), a silicon wafer manufacturer; this task has no connection to my employer's products, processes or data. It uses only published vacuum technology (the steady gas balance of a lumped volume, pump speed curves, water outgassing laws, permeation through elastomers, gauge gas corrections and residual gas analysis) on synthetic chambers and records. I also author evaluation tasks for other AI benchmark programs; this task shares no data, code or scenario with them."
domain = "engineering-sciences"
field = "mechanical-engineering"
subfield = "vacuum engineering and gas dynamics"
category = "Science"
subcategory = "Mechanical & Aerospace Engineering"
tags = [
    "vacuum-technology",
    "base-pressure",
    "outgassing",
    "permeation",
    "residual-gas-analysis",
    "system-identification",
]
expert_time_estimate_hours = 8
relevant_experience = """I am a control scientist and thermal engineer with a PhD in mechanical engineering. Vacuum and gas-handling systems of crystal growth and thermal processing equipment, identifying their models from operating records, and the fault diagnosis that turns those records into maintenance decisions are part of my work on industrial equipment and of my teaching. The chambers and records are synthetic."""
difficulty_explanation = """%s"""
solution_explanation = """%s"""
verification_explanation = """%s"""

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
''' % (_task_name(), DIFFICULTY, SOLUTION, VERIFICATION)


def main(argv):
    if "--write" in argv:
        texts = readme(), task_toml()         # built before either file is opened: task_toml reads the old name
        with open(os.path.join(TASK, "README.md"), "w") as f:
            f.write(texts[0])
        with open(os.path.join(TASK, "task.toml"), "w") as f:
            f.write(texts[1])
        print("wrote README.md and task.toml")
        return 0
    if "--check" in argv:
        # Regenerate in memory and compare. Because the texts are built from the evidence files, this fails
        # whenever a study has been re-run and README.md has not been rewritten: exactly the staleness that got
        # this bundle rejected. Preflight calls it.
        stale = []
        for name, want in (("README.md", readme()), ("task.toml", task_toml())):
            path = os.path.join(TASK, name)
            got = open(path).read() if os.path.exists(path) else ""
            if got != want:
                stale.append(name)
        if stale:
            print("STALE: %s do not match the evidence; run meta.py --write" % ", ".join(stale))
            return 1
        print("README.md and task.toml are current with the evidence")
        return 0
    print(DIFFICULTY)
    print()
    print(SOLUTION)
    print()
    print(VERIFICATION)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
