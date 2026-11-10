# Facts instruction.md must carry (cz-perfect-silicon-control)

instruction.md is the author's own prose. This sheet lists what it has to state, so the task is fully
specified, and what it must not state. Write the contract, not the tour: no role, no file-by-file narration, no
tools sentence, no grading words.

## Must state

- Situation: Puller 11, hot zone HZ-B, is moving from fast pull to the perfect-silicon recipe PS-R07. A new
  supervisory controller has to set the pull rate and the heater power every minute while a 300 mm body grows.
- Where the facts are: `/app/data/` (design sheet, growth model notes, operations notes, controller interface, both
  recipes, minute logs and caliper profiles of eight HZ-B bodies).
- Deliverable: `/app/controller.py`, one self-contained Python file defining `Controller` with a no-argument
  constructor and `step(obs)`, as described in `/app/data/docs/controller_interface.md` (obs keys, the return dict
  `{"pull_rate_mm_min": x, "heater_power_kw": y}`, start conditions).
- It will run on new HZ-B bodies grown with PS-R07, which differ from body to body as much as the logged bodies do.
- Requirements, on every body from 50 mm to 1500 mm:
  - the growth rate, averaged over each 5 mm of crystal, stays within +-1 % of the PS-R07 growth-rate program;
  - the true diameter never falls below 301.0 mm.
- Across all the bodies, the true diameter averaged from 50 mm to 1500 mm is at most 303.0 mm. Every body must
  reach 1500 mm.
- Runtime: the file runs alone in an empty directory with Python 3, numpy and scipy, and cannot read any other
  file; the constructor has 120 s, each `step` 5 s, and a body 600 s of controller time in total.
  `/app/check_controller.py` checks the interface and timing on logged data.
- Closing line, after a blank line, exactly:
  `You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.`

## Must not state

- Grader, verifier, scoring, test, reward words; state the limits as requirements.
- Any mechanism: that the design-sheet dynamics are wrong for HZ-B, the camera offset, the dead time, the rotation
  steps' effect, meniscus or growth-angle dynamics, that the pull rate is not the growth rate, MPC, Kalman filters,
  identification, which log has the step test, how many graded bodies there are.

## Numbers that must match the bundle

Puller 11; HZ-B; PS-R07; 300 mm; every minute; +-1 %; 5 mm; 50 mm to 1500 mm; 301.0 mm; 303.0 mm; eight logged
bodies; 120 s, 5 s, 600 s; 14400 seconds.
