# Difficulty calibration lessons (from Alex's Kepler tasks, Oct-Nov 2026)

## What makes official xhigh fail
- Official xhigh fails on rare coverage slips spread over many independent layers, not on hard modelling.
  pump-wear-assessment: about 10 layers went 8 of 8 officially; about 13 layers went 7 of 8.
- Layers that only the data reveal (records disagree, and only the data settle which is right) slip more often
  than documented corrections. Aim for 13-15 independent layers, several of them data-only.
- Heavy modelling alone does not open the effort gap. Identifying and simulating a lightly damped two-mode
  suspension (screen-fatigue) was done by low effort and xhigh alike.
- superheater-tube-life passed every stage: records-only, about 12 layers, several data-only (thermocouple offsets
  visible only as a ratio step against a neighbour, a silent drift, swapped tags, a tube thinner than the
  register). Local probes: low 1/3, xhigh 2/2. Official: all green, with one difficulty trial failing.
- Local xhigh probes (Claude subagents at xhigh) are stronger than official runs. A local 3/3 has shipped and
  still passed the official difficulty screen.

## What did not work
- Rotor field balancing (three designs): low effort solved it every time. Influence-coefficient balancing is
  linear algebra on documented conventions.
- A one-shot measurement budget whose gaps are flagged plainly in the log is found by low effort. Hiding a gap
  behind a correctable-looking fault traps xhigh more than low.
- The service-plus-budget skeleton (a fieldwork command, ten units, a JSON damage file) failed similarity against
  screen-fatigue. Don't reuse it.
- Clean steps get found: a fault that shows as a clean step against peers, or in a single balance, is found by low
  effort. Opus low runs header balances, peer ratios and step searches unprompted.
- Procedure lines can hint. "Hours whose inputs are unknown are left out", combined with a repaired fault, invites
  the solver to use only the post-repair window.
- Noise-driven difficulty: an agent hugging a single lab reading with no stated repeatability fails on unlucky
  draws. That is a knife-edge, and reviewers dislike it. State the repeatability, then ship a seed on which a
  bore placed only 1 sd inside a limit fails (impeller-shrink-fits).

## What opened the effort gap
- Several faults projecting onto one diagnostic (cooling-tower: three faults all sit in the
  header-minus-risers residual).
- A test budget smaller than the number of things needing measurement, with one escape hidden in a record
  (impeller-shrink-fits: four materials need data above 100 C, 3 tests, and a mill value in one certificate).
- A dated change in the log that makes an earlier survey or certificate stop applying.
- A one-column detail in a table (a spin-test speed differing for one row), or an instrument calibration error
  given in an inspection report.

## Fairness
- Zero-flow windows must be unambiguous. Show a zero error where zero flow is certain (blind flange, pump trip).
- Correct methods can be fragile too. Check method_spread before keeping a layer: every sound method must pass on
  the shipped seed and on nearly all of the 20 laboratory seeds.
- Quality review wants:
  - the solution text to match the code exactly;
  - a structurally independent second implementation;
  - the nearest trap at 1.5x the bound or more;
  - a difficulty explanation that says who does the work;
  - the load-bearing document named by absolute path in the instruction;
  - no narration.

## impeller-shrink-fits official difficulty run (Nov 9): 8 of 8 solved, rejected as too easy
- Every trial found all 12 layers in 14-28 minutes, including those meant to be subtle:
  - the rotor steel test;
  - the mill value in a certificate note;
  - the micrometer error in an inspection-report table;
  - S4's spin speed in one table column;
  - the S2 recoat in the log.
- Frontier agents read every file in full and reconcile every record. A fact that is stated anywhere (a note, a
  column, a log line) is not a trap, however small.
- Narrow windows don't help either. Agents placed bores to within micrometres; one passed with an S4 stress margin
  of +0.00004 (relative).
- Local xhigh 3/3 predicted this correctly. Treat local 3/3 as "too easy"; don't ship on the hope that official
  runs are weaker.
- **What is left to try:** layers that need inference rather than reading.
  - A fault visible only in raw data: a drifting sensor, swapped tags, an instrument offset that must be estimated
    from repeated readings of a standard.
  - A quantity that must be identified from noisy measurements, where the natural model is biased.
  - Conflicts no record resolves, where only physics or a consistency check settles which source is right.

## Designing for inference rather than reading (base-pressure-diagnosis, Nov 9)
- **If a handbook table gives the quantity per unit, the records are decorative.** The first design let the
  outgassing table give each surface's gas load; five of ten chambers were then answerable from the register and
  the tables alone, and two were defeated by no defective route at all. Making the coefficient a *property of the
  unit*, identified from the unit's own records, with the table demoted to a nominal planning figure, is what made
  every other layer load-bearing. This is the general move: the table sizes the equipment, the records audit it.
- **Fitting a coefficient absorbs any constant scale error.** A layer that changes an area, a material or a
  magnitude is invisible once a coefficient is fitted to the same records. Such layers bite only where entries
  straddle the change, or through an exponent or a shape. Plan them that way or they do nothing.
- **Date a change more finely than the records it voids.** Monthly controller rows dated an equipment change up to
  three weeks late, which quietly contaminated the escape route the design depended on. Weekly rows fixed it.
  Whenever a dated change voids earlier records, check that no record falls in the gap between the event and the
  first row that shows it.
- **A forgiven case can make a measurement budget decorative.** With one chamber of ten forgiven, the reference
  passed having placed no test order at all, because only one chamber truly needed a test. Either make two or more
  units genuinely need the budget, or require every unit. Measure it with a plan sweep rather than assuming it.
- **With a categorical deliverable, check every unit is defeated on the categorical.** A unit that only ever fails
  a route on a quantity has its grading decided by where the band sits, which is the first thing reviewers
  challenge. A wrong category is wrong at any tolerance.
- **A duplicated physical constant will drift, and it will bias a whole class of units.** The reference carried its
  own copy of a gas composition and had drifted 5 % from the generator's. Preflight should compare every shared
  table in the solution and in the independent implementation against the sealed definition, and check the shipped
  documents are what the generator writes now.
- **Generate the documents from the sealed constants.** Tables written by hand into a standard drift away from the
  physics they describe; written by the generator they cannot.
- **Derive dependent record fields from one source.** Wall temperatures were first written by hand and happened to
  sit symmetrically about the reference temperature, so the temperature layer cancelled in the fit and defeated no
  chamber. Deriving them from the climate curve, which runs from 25 C in July to 14 C in November, put the usable
  entries on one side of the reference and gave the layer teeth.
- **Watch for knife edges in a measurement a sound method reads directly.** A rate-of-rise slope fitted over the
  whole run is the gas load averaged over the run, not the load at the reported time; and a base pressure taken
  from the trace's first sample carries the whole of that sample's scatter when the pressure rises a hundredfold
  across the window. Both cost about 2 % of sound-method agreement until fixed.
