A fuel terminal moves heated fuel oil from its heaters to several plants through covered transfer lines. Some lines are a single pipe and others a pair of pipes between common inlet and outlet manifolds. For each site, the pressure drop and outlet oil temperature are to be worked out under TS-2 in `/app/data/docs/ts2_oil_lines.md`. Write that calculation as `/app/output/lines.py`.

The layout of a site package and the available survey service are described in `/app/data/docs/site_package.md`. Run the program as `python3 lines.py PACKAGE_DIR OUT_CSV`. It must write `OUT_CSV` with the header `record,dp_kPa,t_out_C` and one row for every row of the package's `records.csv`. Report pressure drop in kPa and outlet temperature in degrees C as decimal numbers. The file may not exceed 1000000 bytes.

During a run, one survey order may be placed for that package with `heatsurvey`. The order may include no more than the package's `survey_allowance` pipes, and the command is available on the PATH.

Three packages are available. `/app/data/examples/north_quay` and `/app/data/examples/east_depot` include their TS-2 results. `/app/data/pending/west_jetty` is provided without results.

The same program is later used on six other sites whose packages have the same format and whose lines and records fall under TS-2 section 1. The survey crew is available for those runs as well. At every record, pressure drop must be within 2.5 per cent of the result to TS-2, and outlet temperature must be within 0.5 K. Each run of lines.py must finish within 40 seconds on 1 CPU.

Each run starts in a scratch directory containing a copy of `lines.py` alone. It runs under an unprivileged user without network access, with the package read-only, and must end with exit status 0. Python 3 with numpy, scipy and pandas is available, and `/app/data` remains readable at the same path.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
