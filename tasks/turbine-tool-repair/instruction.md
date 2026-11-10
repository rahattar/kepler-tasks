Repair the plant's GT-1 performance program and save the corrected version as `/app/output/gtperf.py`. The current program at `/app/tool/gtperf.py` is read-only, and the plant does not trust its results. For one day's test records, the program must report corrected gross output in MW and corrected heat rate in kJ/kWh on the LHV basis, both at the contract reference conditions.

The calculation follows `/app/data/docs/gt1_performance_procedure.md`. Record formats are described in `/app/data/docs/gt1_record_format.md`; the other documents are in `/app/data/docs/`, and two example record sets are in `/app/data/examples/`.

Keep the interface `python3 gtperf.py RECORD_DIR OUT_CSV`, reading the records in RECORD_DIR and writing OUT_CSV with the header `corrected_output_mw,corrected_heat_rate_kj_kwh` and one data row. The program will also run on eight other GT-1 record sets in the same format. On every set, both values must be within 0.3 % of their true values. Python 3 is available with numpy and pandas as the only additional libraries.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
