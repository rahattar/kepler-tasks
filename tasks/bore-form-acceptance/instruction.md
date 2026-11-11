The hydraulic press of a forging shop has been stripped for overhaul. Its cylinder bores, gland bores and ram journals have been finish-machined and measured, and the overhaul engineer has to sentence every one of them before the press is rebuilt.

Sentence each of the 14 features in `/app/data/feature_register.csv`: its form error, and whether it is acceptable against its drawing. Plant standard FM-7, `/app/data/docs/standard_fm7.md`, defines what a measurement of a feature means and what makes a feature acceptable. Follow it as written. The drawings' requirements are in `/app/data/drawing_requirements.csv`.

Every feature is to be sentenced as it now stands. The records are the feature register, the drawing requirements, the machining log, the measurement index and one file of measured points per feature under `/app/data/measurements`, together with the shop's inspection report, the instrument notes and the metrology room's note in `/app/data/docs`.

The metrology room will scan a feature on request, as `/app/data/docs/metrology_room.md` describes: `formscan <feature>`. The booking is 4 scans in all and it does not refill. Each scan's points are written to `/app/scan_reports`. Plan the booking before you spend any of it.

Write your answer to `/app/output/form.csv`, with the header `feature,form_um,verdict` and one row for each of the 14 features: the form error in micrometres to two decimal places, and one of `accept`, `reject_size`, `reject_form`, `reject_both`.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
