# slab-cooling-dispatch: facts instruction.md must state

instruction.md is yours, in your own words. These are the contract facts it has to carry, and nothing
more. `authoring/evidence/check_instruction.py` checks every number, path and key below against the bundle.

Rules from the Oct 14-15 reviews: write the task, not the grader (no "verifier", "graded", "passes",
"score", "hidden"; state limits as requirements, and the closed-loop run as setup: "controller.py is run
alone with Python 3, numpy and scipy"); no role-play opening; no tour of the data files; no tools sentence.

## Setting (one or two sentences, no tour)
- Two perimeter office zones (east, west) cooled by concrete-core activation from one manifold; a
  dedicated chiller's leaving water is the slab supply for both; each zone has an on/off valve.
- Replace the current BMS sequence with a supervisory controller: comfort in occupied hours, low
  electricity cost.

## Data (absolute paths)
- Everything known is in `/app/data/`, including eight weeks of 15-minute trend logs from 2017-05-20 to
  2017-07-14. The as-built zones may differ from their design values.
- Do not tour the files or narrate their fields; the files are self-describing.

## Deliverable
- `/app/controller.py`: one self-contained Python file, class `Controller` with a no-argument
  constructor and a method `step(obs)`.
- It is run alone, in an empty directory, with Python 3, numpy and scipy only; it cannot read any other
  file (so no reading `/app/data` at run time). Say this as setup, not as what a verifier does.
- `step` is called every 15 minutes from 2017-07-15T00:00 to 2017-09-08T23:45, continuing directly
  from the end of the trend log.

## obs (state the keys; one sentence each)
- `time` (local standard time at the start of the interval), `outdoor_temp_c` (current),
  `facade_irradiance_w_m2` (`west`, `east`; mean over the previous interval), `supply_temp_c`
  (chiller leaving water, mean over the previous interval), `supply_setpoint_c` (previous setpoint),
  `zones` (`west`, `east`, each with current `air_temp_c` and `slab_temp_c`, and `return_temp_c` and
  `valve_duty` for the previous interval), `forecast`.
- Forecasts are issued at 00:00, 06:00, 12:00 and 18:00 with 216 values at 15-minute spacing starting
  at the issue time: `{"issued", "step_minutes", "outdoor_temp_c", "facade_irradiance_w_m2": {"west", "east"}}`.

## Return value
- `{"supply_temp_c": float, "valve_duty": {"west": float, "east": float}}`, held for 15 minutes.
- Setpoint clipped to 15-22 C. Duty in [0, 1] keeps the valve open for that fraction of the interval,
  rounded to whole minutes, from the start of the interval.
- When the open valves ask for more heat than the chiller can remove, its leaving temperature rises
  above the setpoint. No heat is removed from a slab colder than the supply; the system cannot heat.

## Requirements (the eight weeks of the run, each Saturday 00:00 to Friday 24:00; both must hold)
1. Per zone and week, occupied-hour operative temperature, evaluated every minute, accumulates at
   most 0.5 K h outside 21.0-26.0 C. At most one of the 16 zone-weeks may exceed this.
2. Total cooling electricity cost over the eight weeks at most 1.15 times the benchmark's. Cost =
   sum over minutes of heat removed from both zones (kWh) / chiller COP at its actual leaving
   temperature and the outdoor temperature x tariff price.
- The benchmark: knows both zones' exact models and states, receives the same forecasts after
  removing the systematic error the forecast archive shows, assumes design internal gains, keeps its
  predicted operative temperatures within 21.3-25.7 C, plans 48 h ahead with the chiller's
  efficiency and capacity, re-plans every hour.

## Limits
- Constructor within 600 s, each `step` within 10 s, 7200 s of controller time over the whole run.
- `/app/check_controller.py` checks the interface and timing on logged data (say what it does, not what it
  does not do).

## Closing line (exact, after one blank line, at most one trailing newline)
You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.

## Style the quality review punishes (from the Oct reviews)
No first person ("we"), no scene-setting with slips or comma splices, no redundant contrastives
("not just ..."), no closing sentence that restates the criteria, no narrating details the agent can
discover (field lists, where outputs land).
