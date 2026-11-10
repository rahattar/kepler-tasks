Before Level 3 of Building C can be handed back, its airflow needs to be calibrated. AHU-3 serves the floor through 40 pressure-independent VAV boxes, VAV-3-01 to VAV-3-40. The east wing was re-ducted and fitted out in 2025.

Everything known is in `/app/data`, including the box schedule, inlet survey, 2024 TAB report, two weeks of BAS trends and supporting documents.

Each box controller reports airflow as K x sqrt(VP - offset) and controls that reported flow to its setpoint. Calibrating a box means choosing K, in cfm per sqrt(in. w.c.), and the offset, in inches of water column (in. w.c.).

The TAB contractor has five capture-hood visits available for the whole floor. The service starts with `start-hood` and listens at `http://127.0.0.1:8000`. `GET /status` shows the visits left, and `POST /visit?box=VAV-3-07` requests a visit. Each visit request uses one visit. During a visit, the contractor drives the box to its design minimum, a midpoint and its design maximum. At each setting, the report gives the hood reading at each diffuser together with the box's trended values during those readings. Reports are also written to `/app/visits/`.

Write `/app/output/calibration.csv` with the header `tag,k_factor,vp_offset_inwc` and one row for each of the 40 boxes. The `k_factor` column holds K, and `vp_offset_inwc` holds the offset. With those values loaded, every box must deliver actual airflow within 10 percent of its design maximum while controlling to that maximum. At the design minimum setpoint, every box must deliver airflow within 10 percent of its design minimum.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
