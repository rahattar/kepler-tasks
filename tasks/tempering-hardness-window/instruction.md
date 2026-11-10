Thirteen batches of alloy steel parts, B01 to B13, have finished hardening and are waiting for tempering. Choose one furnace setpoint for each batch, in whole degrees C, so the finished parts meet the hardness range on their drawing at the location the drawing names, when they are tempered as heat treatment procedure HT-4 in `/app/data/docs/procedure.md` requires.

The available records are `/app/data/batches.csv`, `/app/data/mill_certificates.csv`, `/app/data/production_log.csv`, and `/app/data/supplier_tempering_curves.csv`. Laboratory work is described in `/app/data/docs/laboratory.md`. From `/app`, the lab command is `temper <heat> <T> [<diameter_mm> <surface|half-radius>] [double]`. The furnace booking allows 11 tempers for all thirteen batches. A test tempered once uses one temper; a test tempered twice uses two. Reports are written under `/app/lab_reports`.

Write the final temperatures to `/app/output/tempering.json` in this form: `{"tempering_C": {"B01": <C>, ..., "B13": <C>}}`. B01 through B13 must each appear exactly once, and every value must be a whole degree C. Every batch must meet its required hardness range at a temperature permitted by HT-4.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
