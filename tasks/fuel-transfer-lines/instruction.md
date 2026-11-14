A fuel terminal sends heated fuel oil from its heaters to the plants it feeds through covered transfer lines, some of them single pipes and some pairs of pipes laid side by side between one inlet and one outlet manifold. For every line it keeps an hourly record and, for each record, the pressure drop across the line and the temperature of the oil leaving it, worked out to its standard TS-2, `/app/data/docs/ts2_oil_lines.md`. That calculation, for one site at a time, is to be written as `/app/output/lines.py`.

Each site sends its lines in as a package, laid out as `/app/data/docs/site_package.md` describes. The program is started as `python3 lines.py PACKAGE_DIR OUT_CSV`. It writes `OUT_CSV` with the header `record,dp_kPa,t_out_C` and below it one row for each row of the package's `records.csv`: the pressure drop in kPa and the outlet temperature in degrees C, as decimal numbers. `OUT_CSV` may not exceed 1000000 bytes. A site's package can be given one order for the survey crew described in `/app/data/docs/site_package.md`, which the program places while it runs with the `heatsurvey` command; that command is on the PATH wherever the program is started.

`/app/data/examples/north_quay` and `/app/data/examples/east_depot` are two packages with their results to TS-2. `/app/data/pending/west_jetty` is a third package, not yet calculated.

The program will then be run on the packages of six other sites, in the same format, every line and record within the scope of TS-2 section 1, and the crew taking their orders. At every record of every site the pressure drop has to be within 2.5 per cent of its result to TS-2 and the outlet temperature within 0.5 K of it. Each run of lines.py must finish within 40 seconds on 1 CPU.

Every run starts in a scratch directory holding a copy of `lines.py` alone, under an unprivileged account without network access, with the package read-only, and must end with exit status 0. Python 3 with numpy, scipy and pandas is available, and `/app/data` can be read at the same path.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
