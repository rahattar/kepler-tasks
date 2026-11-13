A mining group ventilates each of its districts with main fans exhausting in parallel at one fan house, and keeps for every district the airflow at each survey point on record, calculated to its standard VS-4, `/app/data/docs/vs4_ventilation_networks.md`. The calculation for one district is to be a program, `/app/output/airflow.py`.

A district's records arrive as a package, a folder whose files `/app/data/docs/district_package.md` describes. The program is run as `python3 airflow.py PACKAGE_DIR OUT_CSV` and writes `OUT_CSV`: the header `point,flow_m3_s`, then one row for every point of the package's `points.csv` with the airflow there as a decimal number in m3/s. `OUT_CSV` must be no larger than 2000000 bytes. The survey crew of `/app/data/docs/district_package.md` takes one order for a package, and the program can place it during its run with the `pqsurvey` command, which is on the PATH wherever the program runs.

Three packages are at hand. `/app/data/examples/north_field` and `/app/data/examples/east_decline` come with their results to VS-4. `/app/data/pending/west_reef` has none.

Afterwards the program is run on six districts that are not among these, each in the same format and within the scope of VS-4 section 1, with the survey crew answering for them. At every survey point of every one of them the airflow must be within 1.5 per cent of the result to VS-4, or within 0.03 m3/s where that is more. Each run of airflow.py must finish within 35 seconds on 1 CPU.

A run is made in a scratch directory that holds a copy of `airflow.py` and nothing else, as an unprivileged user with no network, the package read-only, and has to end with exit status 0. Python 3 with numpy, scipy and pandas is installed, and `/app/data` is readable at the same path.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
