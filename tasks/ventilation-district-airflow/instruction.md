Each mining district is ventilated by main fans exhausting in parallel through one fan house, with airflow recorded at the district's survey points under standard VS-4. The governing standard is `/app/data/docs/vs4_ventilation_networks.md`. Write the district calculation as `/app/output/airflow.py`.

A district arrives as a package in the format described by `/app/data/docs/district_package.md`. Running `python3 airflow.py PACKAGE_DIR OUT_CSV` reads that package and writes `OUT_CSV` with the header `point,flow_m3_s`, followed by one row for every survey point in the package and its airflow as a decimal number in m3/s. The output file must be no larger than 2000000 bytes. During a run, the program may place one order for that package with the survey crew through `pqsurvey`, which is available on the PATH.

Three packages are provided. `/app/data/examples/north_field` and `/app/data/examples/east_decline` include results prepared to VS-4, while `/app/data/pending/west_reef` does not.

The same program is later used on six other districts. Their packages have the same format, each district is within the scope of VS-4 section 1, and the survey crew is available for those runs. At every survey point, the reported airflow must be within 1.5 per cent of the result to VS-4, or within 0.03 m3/s where that gives the larger allowance. Each run of airflow.py must finish within 30 seconds on 1 CPU.

Runs take place one after another in a scratch directory containing a copy of `airflow.py` alone. The process runs as an unprivileged user without network access, with the package read-only, and must exit with status 0. `/app/data` remains readable at the same path. Python 3 with numpy, scipy and pandas is available.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
