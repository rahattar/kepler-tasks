The eight vertical furnaces in diffusion bay 2, F1 through F8, are due for their yearly temperature calibration. Each has five heater zones, Z1 through Z5. In each zone, the controller adds a correction to the raw profile thermocouple reading and holds the corrected reading at the setpoint. Separate corrections apply at 850 C and 1050 C.

Everything known is in `/app/data`: the furnace register, maintenance log, 2025 TC-wafer calibration, currently loaded corrections, four weeks of controller trends for each furnace, and the documents.

Only three TC-wafer temperature steps are available across the whole bay. The command `start-tcwafer` starts the service at `http://127.0.0.1:8000`; `GET /status` shows how many steps remain. Run requests use the form `POST /run?furnace=F2&steps=600,1050`, with temperatures chosen from 600, 850, and 1050 C. Each requested temperature uses one step. Grouping several into a single run does not reduce that count. Runs take place with corrections disabled and report every zone's raw profile reading, spike reading, and TC-wafer temperature at each requested step. The reports also go to `/app/runs/`.

The new corrections go in a csv file named `/app/output/corrections.csv`, with the header `furnace,zone,correction_850_c,correction_1050_c` and one row for each of the 40 zones. After those corrections are loaded, every zone on every furnace must have a wafer temperature within 2 K of the setpoint at both 850 C and 1050 C.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
