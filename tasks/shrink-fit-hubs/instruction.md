Twelve hubs, J01 to J12, are to be shrink-fitted back onto their shafts after an overhaul. For each joint, specify the mean diametral interference, in whole micrometres, to which the shaft and bore are to be machined, and the oven temperature, in whole degrees C, to which the hub is heated for fitting, so that the joint meets every requirement of plant standard ST-9 in `/app/data/docs/standard.md` as the joint is now and in service.

The records are `/app/data/joint_register.csv`, `/app/data/hub_certificates.csv`, `/app/data/assembly_sheets.csv`, `/app/data/duty.csv`, `/app/data/thermography.csv`, `/app/data/materials.csv` and `/app/data/maintenance_log.csv`. The joint laboratory is described in `/app/data/docs/laboratory.md`. From `/app`, its commands are `slip <material> <dry|oiled|paste> <pressure_MPa> [shrink]` and `cte <material> <T>`; each uses one test, with 8 tests in total. Reports are written under `/app/lab_reports`.

Write the result to `/app/output/fits.json` in this form: `{"fits": {"J01": {"interference_um": <um>, "heating_C": <C>}, ..., "J12": {...}}}`, with J01 to J12 each appearing exactly once and every value a whole number. Every joint must meet all the requirements of ST-9.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
