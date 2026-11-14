# Design note: ventilation-district-airflow (Nov 13)

A timed program on shifted hidden data, to the Nov 11 ask. Built from bare cores v0 to v2
(`docs/difficulty-calibration.md`, the vent fan stall sections; `cores/vent-fan-stall-v0`, `-v1`, `-v2`).

**Subject.** A mine ventilation district: 806 to 955 branches, two axial fans in parallel at one fan house,
three weeks of regulator and door movements (1153 to 1322 log rows), 3570 to 3948 survey points. Standard
VS-4 states the network law, where resistances come from, the fan characteristic and that every change is
gradual.

**Mechanism.** Kind A of `docs/trap-analysis-2026-11-11.md` inside a program, twice over: a record that is
wrong with no physical reason to doubt it, and an outcome the records cannot decide, each curable only by a
survey the program has to order before it sees any result.

- Stall and its history are in the examples with results. v0 showed low effort finds a dip in a table in
  eleven minutes, so it is physics every solver gets, not the decider.
- Airway resistances come from surveys on file. Airways worked on since their last survey have to be ordered
  from the survey crew: one order a run, at most `survey_allowance` branches. That is the legible need, and
  it bites in the examples (a run without the order is out of band on both).
- **Open stopping** (pending, 3 of 6 hidden). Booked at 1721 to 3744 N s2/m8, in fact 7.1 to 8.9. No file
  says so. The two gate-road quantities at its intake end miss balance by 5.1 to 10.1 m3/s in every campaign
  against 1.02 at the worst of 2099 sound stoppings. Allowance: one more.
- **Open closure** (pending, 4 of 6 hidden). The last SD-2 closure is built between the edge of the healthy
  state for the district as it is and as its records have it (0.32 to 0.60 per cent apart). Two stall where
  the records hold, two hold where the records stall. Only a fan reading says which. Allowance: one more.
- The examples have neither and an allowance equal to the airways worked on. The pending district has both
  and no results, and the crew does not answer for it where the program is written.

**What must not be changed without re-probing.**
- The crew answers for the two example districts only. With the crew answering for the pending district two
  of three xhigh probes compared their program with the crew's present readings there and were shown both
  conditions (v1). An oracle on the pending instance is a results table by another name.
- The pending package has no results.
- The examples' allowance equals the airways worked on. A spare place in an example is a visible test.
- One order for a package, placed by the program.
- The documents say what a resistance is and what is on record. Nothing says a record can be wrong, what a
  spare place is for, or the word stall.

**What the generator has to hold to** (`authoring/provenance/districts.py`, `district.py`).
- Truth is quasi-static: each change gradual, the flow settled on the inertial equations. A record is
  refused unless the result is the same in finer steps, along another path, with other inertias and in two
  steps, and unless every stall and recovery before the last closure survives 3 per cent either way.
- The stall fold is not always the peak. A fan that passes its peak against a load line steeper than its
  rising limb does not jump: it sits between trough and peak and comes back when the door reopens. With
  unequal blade settings the healthy fan is far out on its falling limb, the load seen by the other is steep,
  and a closure built at the peak leaves no hysteresis (lower_levels at blades 4 and 3: 13 draws of 13
  refused). Districts with an open closure have two equal fans, and no record has a log entry that leaves a
  fan between trough and peak.
- The healthy state's edge is found exactly: each fan given its falling limb alone, one solve, every fan
  above its peak. Stepping towards the edge was twelve times the work.
- Alterations are sized to matter: the survey on file reads 4.1 to 7.9 times the airway as it is. At the
  first sizing (0.5 to 0.75 times) the examples passed with no order placed.
- Checksums by hashlib: the zip checker refuses zlib in code.

**The timed half.** Limit 35 s a run on one CPU; reference 8.7 to 10.5 s (3.3 times the slowest). The
second solution, dense and from scratch at every entry, is right on the small districts and stopped at the
limit on the first of the six. The limit does not separate probes: three low-effort programs ran a district
in 5 to 12 s.

**Verifier.** As journal-bearing-survey: the program runs as nobody, the checker opens a Unix socket for the
length of a run and `pqsurvey` in the verifier's image is a client of it; the same `lab.py` in both images.
No CPU affinity. The crew counts an order against the process that placed it.

**Local rates** (`model: "opus"`).

| | low | xhigh |
|---|---|---|
| core v1, small, crew answers for pending | 0 of 3 | at least 2 of 3 |
| core v2, small, crew answers for examples only | 0 of 3 | 1 of 3 |
| the bundle | 0 of 3 (3 to 7 min) | 1 of 3 |

Every low probe, core and bundle, surveyed the airways worked on and nothing else, and failed the five
districts that have a condition exactly as the `worked_on` variant does.

The bundle's xhigh probes: D accepted on all six and on the three visible districts (stoppings balanced at
their nodes, the fan behind the longer ducting read and the turn found; its program was complete after 46
minutes and its report says the pending district's last closure comes within 0.012 per cent of the stall
point, which no calculation from the records decides); E surveyed the airways worked on only (25 min); F found the open
stopping from the node balances and spent the last place on a fan, but used the reading as a check, and
failed the two districts that hold where their records stall (33 min).

- **Averaging the campaigns is a coin, not a route.** F averaged the three surveys of an unaltered airway
  (VS-4 says the latest is used). That puts its district between the records' and the real one, and it went
  the right way at two of the four open closures and the wrong way at two. The closure is built between the
  two edges, so anything that moves the records towards the district makes the outcome a toss.
- **The limit did not bind.** Probe programs ran a district in 1.3 to 12 s against 35; the reference is the
  slow one at 8.7 to 10.5 s. The one long run was D's on the pending district, 26 s with the turn search.
- Probe programs are in `cores/vent-fan-stall-v2/probes/full_*.py`.

**Packed** as ventilation-district-airflow-20261113.zip with Alex's instruction (preflight 77 of 77, shipcheck
clean). No Docker daemon in the session that built it: the oracle evidence is `verifier_run.txt`
(`bash tests/test.sh` itself, reward 1), and the two Dockerfiles, reworded for the similarity gate after the
studies, have not been built. Instruction against lube-oil-survey: 0.53 difflib, 0.095 5-gram Jaccard.

**Rejected and fixed (20261113b).** Quality review, three blocking criteria
(`docs/rejection-patterns.md`): VS-4 did not state the fans' state as the record opens or which state a
district goes to when the one it is in ends; "on 1 CPU" was enforced as wall time only; and no independent
solution was shown passing at full size. VS-4 sections 1, 4 and 5 now state the opening state and the rule,
without the words the preflight keeps out. The checker counts CPU time of the whole process tree. fast_airflow.py,
the second solution with sparse warm-started solves and the fans carried by the stated rule with no integration,
is accepted on all sixteen districts in 4.9 to 7.5 s a run, which also shows the rule decides the truth. Three
low probes on the new documents: 0 of 3, each the `worked_on` miss; they used the stated rule directly. No
xhigh probes on 20261113b.
