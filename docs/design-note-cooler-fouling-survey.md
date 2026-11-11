# Design note: cooler-fouling-survey (in build, Nov 10 2026)

**Status:** sealed definition written and the identifiability gate verified numerically. Records, crew service,
reference, grader and evidence still to build.

**The lever.** The first task of the new family, chosen against the brief in difficulty-calibration.md: an answer
that cannot be read out of the records at any level of care, because a measurement plan that is one point short
leaves two unknowns unobtainable, and nothing recovers that afterwards. The twelve probes of the previous tasks
never faced a decision they could not repair by working harder.

**Task.** An air-cooled exchanger bank: six bays in parallel on one process header, 120 kg/s of light hydrocarbon
in at 95 C, mixed return 38.1 C, total duty 15.1 MW.
- **Deliverable:** /app/output/fouling.csv, each bay's process flow in kg/s and its tube-side fouling resistance in
  m2 K/W. Twelve graded values; the flows within 3 per cent, the fouling within 10 per cent; the gate is all twelve.
- **Crew:** `probe <point>`, 4 points. A point is a bay's process outlet temperature, its air outlet temperature or
  its process flow, each by a calibrated portable instrument, five readings averaged.
- **Unknowns:** five. Bay F was re-tubed at the last shutdown, so the standard takes its tube side as clean.

**Why four points settle it and three do not.** Two of the plant's own readings bear on the fouling: the mixed
return temperature, which fixes the sum of the duties, and the common tube-side pressure drop, which the fouling
layer raises. Between them they can carry one unmeasured bay and no more - left to carry two they fix only a
combination. So one point on each of four of the five unknown bays determines the bank, and any plan that spends a
point elsewhere leaves two bays unmeasured.

Verified against the sealed definition (one standard deviation of the recovered value, from the stated instrument
uncertainties):

| plan | worst fouling | worst flow |
|---|---|---|
| one point on each of four unknown bays, leaving A, B, C, D or E | 2.9 to 6.3 % | 0.82 to 1.29 % |
| a point spent on the re-tubed bay | 24.1 % | 12.5 % |
| two points on one bay | 26.5 % | 14.9 % |
| three points on two bays | singular | singular |

So a good plan sits two to three times inside the grading band on every value, and every wasted point puts a flow
four times outside it. The flows are what make the gate crisp: they are far better conditioned than the fouling, so
a bad plan fails on them outright rather than probabilistically.

**The four ways to waste a point,** each fatal, each discoverable and none of them announced:
1. bay F was re-tubed last month (maintenance log), so its tube side is clean and a point on it buys nothing;
2. bay E's outlet tapping is plugged (log): the crew reports no access and the point is spent;
3. the header's inlet and mixed outlet temperatures, its differential pressure and the ambient are already on the
   plant's instruments, so a point on any of them buys nothing;
4. two points on one bay settle that bay twice and no other, so the information is one point, not two.

**Layers** (beyond the four above): the flows are neither equal nor measured and settle where every bay takes the
same pressure drop, which the fouling itself changes, so the split and the fouling have to be found together; bay
D's fan runs in reverse after a motor change (log), so its air flow is below its curve; bay B's louvres are stuck
part open; bay C was re-tubed to a heavier gauge two shutdowns ago (register), so its bore and clean conductance
are not the data sheet's; bay B is two-pass where the others are four-pass; the stream analysis of 2026-10-02
supersedes the data sheet's and the specific heat comes from the property table at the mean temperature; the total
flow on file is volumetric and wants the density at the header temperature; the ambient drifts through the survey
and the crew's readings are timestamped; a bay's air flow follows from its fan power and curve, not a measurement.
