Process engineering needs fouling figures to plan the glycol cooler bank's cleaning during the 2027 outage. The bank has ten shell-and-tube coolers, E1 to E10, with glycol on the shell side and cooling water in the tubes. Report the as-found condition on 2026-10-26, before any cleaning that day.

Available under `/app/data` are the unit register, maintenance log, acceptance tests following the March 2025 cleaning, seven weeks of hourly DCS trends for each unit, and a folder of documents.

For the contractor's work on 2026-10-26, the whole bank shares three cleaning-and-test slots. Access is through `http://127.0.0.1:8000` after launching `start-hxtest`. Use `GET /status` for the remaining slot count and `POST /test?unit=<id>` to spend one slot on the cooler named by its unit ID. The contractor runs an as-found performance test with calibrated portable instruments, recording their readings alongside the DCS readings, then hydroblasts the cooler and repeats the test. Each report is saved to `/app/test_reports/`. Once used, a slot is gone, even after a service restart.

Put the results in `/app/output/fouling.csv` with the header `unit,fouling_m2k_per_kw` and ten data rows, one per cooler. Fouling resistance is 1/U as found minus 1/U clean at the same flows, with U referred to the unit's actual heat-transfer area (open tubes only). Report it in m2K/kW, one figure per cooler: your best estimate of that cooler's true as-found fouling resistance.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
