The hydraulic press is apart for overhaul, and its cylinder bores, gland bores, and ram journals have already been finish-machined and measured. Before the press goes back together, the overhaul engineer needs a disposition for every measured feature.

There are 14 features in `/app/data/feature_register.csv`. For each one, report its form error and decide whether it is acceptable against the drawing. Plant standard FM-7 in `/app/data/docs/standard_fm7.md` defines what a measurement of a feature means and what makes that feature acceptable; follow FM-7 as written. The drawing requirements are in `/app/data/drawing_requirements.csv`. Every feature is to be sentenced as it now stands.

The rest of the records are `/app/data/machining_log.csv`, `/app/data/measurement_index.csv`, and the individual measured-point files under `/app/data/measurements`. Supporting documents are `/app/data/docs/inspection_report.md`, `/app/data/docs/instrument_notes.md`, `/app/data/docs/boring_practice.md`, and `/app/data/docs/metrology_room.md`.

Additional metrology is available through the room described in `/app/data/docs/metrology_room.md`. From `/app`, the request is `formscan <feature>`. The booking covers 4 scans for the whole job and does not refill. Each scan writes its measured points under `/app/scan_reports`. Plan the booking before using any of it.

Write `/app/output/form.csv` with the exact header `feature,form_um,verdict` and one row for each of the 14 features. Give `form_um` in micrometres to two decimal places. The `verdict` must be one of `accept`, `reject_size`, `reject_form`, or `reject_both`.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
