# Facts instruction.md must carry (furnace-tc-calibration)

instruction.md is the author's own prose. This sheet lists what it has to state, so the task is fully
specified, and what it must not state. Write the contract, not the tour: no role ("you are a process engineer"),
no file-by-file narration, no tools sentence, no grading words.

## Must state

- Situation: diffusion bay 2 has eight vertical furnaces, F1 to F8, each with five heater zones, Z1 to Z5. Each
  zone's controller adds a correction to the raw reading of its profile thermocouple (corrected = raw + correction)
  and holds the corrected reading at the setpoint. The correction is entered per zone at 850 C and at 1050 C. The
  bay is due for its yearly temperature calibration.
- Requirement, for every zone of every furnace: with the new corrections loaded, the wafer temperature is within
  2 K of the setpoint at 850 C and within 2 K of the setpoint at 1050 C.
- Where the facts are: `/app/data` (furnace register, maintenance log, 2025 TC-wafer calibration, the corrections
  loaded now, four weeks of controller trends for each furnace, the documents).
- TC-wafer runs: three temperature steps for the whole bay. The service is started with `start-tcwafer` and
  listens at `http://127.0.0.1:8000`; `GET /status` shows the steps left; `POST /run?furnace=F2&steps=600,1050`
  requests a run, listing any of the steps 600, 850 and 1050; each listed step uses one of the three. A run reports,
  for every zone and each requested step, the raw profile reading, the spike reading and the thermocouple-wafer
  temperature, with corrections disabled. Reports are also written to `/app/runs/`.
- Deliverable: `/app/output/corrections.csv` with the header `furnace,zone,correction_850_c,correction_1050_c` and
  one row for each of the 40 zones.
- Closing line, after a blank line, exactly:
  `You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.`

## Must not state

- Grader, verifier, scoring, test, reward or tolerance-as-grading words; state the 2 K as a requirement.
- Any mechanism or the furnaces that matter: drift or how it scales, the offset or its radiative shape, the ratio
  between 850 C and 1050 C, isothermal soaks or which states are isothermal, the hold, the liner, the boat loads, the tube change,
  the vendor's profile, which furnaces or steps to run, or that a measurement can serve two purposes.

## Numbers that must match the bundle

eight furnaces; five zones; 40 zones; 850 C; 1050 C; 2 K; three steps; 600, 850, 1050; 2025; four weeks; port 8000;
10800 seconds.
