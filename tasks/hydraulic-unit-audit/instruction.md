For the plant's pump-retrofit study, write a program to produce audit results from press hydraulic power unit logs. Save it at `/app/output/hpu.py`. Running `python3 hpu.py PACKAGE_DIR OUT_JSON` must read one press's package and write the results to `OUT_JSON` as defined in `/app/data/docs/hp2_procedure.md`. The units and package layout are described in `/app/data/docs/unit_records.md`. A previous package, together with the plant engineer's reported results, is available in `/app/data/examples/p-01/`.

The same program is needed for eight other presses. For at least seven of them, all five results must meet the required limits: `oil_delivered_l`, `hydraulic_energy_kj` and `electrical_energy_kj` must each be within 3 % of their correct values, `peak_flow_l_min` within 5 %, and `unit_efficiency` within 0.03.

These eight packages run one after another with `python3 -I hpu.py PACKAGE_DIR OUT_JSON`. Each run takes place in a scratch directory containing a copy of `hpu.py` alone, as an unprivileged user without network access. Allow no more than 60 seconds per run. `/app/data` remains readable at the same path, and Python 3 is available with numpy, scipy and pandas.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
