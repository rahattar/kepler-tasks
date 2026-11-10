# Facts instruction.md must carry (cz-silicon-control)

instruction.md is the author's own prose. This sheet lists what it has to state, so the task is fully
specified, and what it must not state. Write the contract, not the tour: no role, no file-by-file narration, no
tools sentence, no grading words.

## Must state

- Situation: Puller 11 moves from fast pull to the perfect-silicon recipe PS-R07; its supervisory program has
  to set the pull rate and the heater power every minute while a body grows. (Keep the hot zone and the
  controller interface wording out of the instruction: the similarity screen matched an earlier submission.)
- Where the facts are: `/app/data/` (design sheet, growth model notes, operations notes, controller interface, both
  recipes, minute logs and caliper profiles of eight HZ-B bodies).
- Deliverable: `/app/supervisor.py`, class `Supervisor` with `update(meas)` called once a minute and returning the
  pull-rate and heater-power setpoints, as described in `/app/data/docs/supervisor_interface.md` (meas keys, the
  returned pair, start conditions, computing limits).
- It will run on new HZ-B bodies grown with PS-R07, which differ from body to body as much as the logged bodies do.
- Requirements, on every body from 50 mm to 1500 mm:
  - the growth rate, averaged over each 5 mm of crystal, stays within +-1 % of the PS-R07 growth-rate program;
  - the true diameter never falls below 301.0 mm.
- Across all the bodies, the true diameter averaged from 50 mm to 1500 mm is at most 303.0 mm. Every body must
  reach 1500 mm.
- Runtime: the interface document lists the computing limits (120 s to construct, 5 s per call, 600 s per body,
  numpy and scipy only, no other files); `/app/check_interface.py` checks a program against them on logged data.
- Closing line, after a blank line, exactly:
  `You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.`

## Must not state

- Grader, verifier, scoring, test, reward words; state the limits as requirements.
- Any mechanism: that the design-sheet dynamics are wrong for HZ-B, the camera offset, the dead time, the rotation
  steps' effect, meniscus or growth-angle dynamics, that the pull rate is not the growth rate, MPC, Kalman filters,
  identification, which log has the step test, how many graded bodies there are.

## Numbers that must match the bundle

Puller 11; PS-R07; every minute; +-1 %; 5 mm; 50 mm to 1500 mm; 301.0 mm; 303.0 mm; eight logged
bodies; 120 s, 5 s, 600 s; 14400 seconds.
