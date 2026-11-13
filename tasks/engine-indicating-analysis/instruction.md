On an engine test cell the pressure in every cylinder is recorded over many cycles at each operating point, and a session's records are sent in as a package, laid out as `/app/data/docs/cell_package.md` describes. The indicating standard IS-2, `/app/data/docs/is2_indicating.md`, gives six results for each operating point of the package's `points.csv` and each cylinder: the gross indicated mean effective pressure, the peak pressure, the crank angle at which the peak occurs, the crank angles of 10 and 50 per cent burned, and the gross heat released.

`/app/output/indicate.py` is the program that calculates one package to IS-2. The command is `python3 indicate.py PACKAGE_DIR OUT_CSV`. `OUT_CSV` is written as an ordinary file, not a link, of at most 2 MiB (2,097,152 bytes): a CSV table with the header `point,cylinder,imep_bar,pmax_bar,apmax_deg,ca10_deg,ca50_deg,q_gross_J` and one row for each point and cylinder, the values written as decimal numbers in the header's units.

Four packages are on hand. `/app/data/examples/cell_03` and `/app/data/examples/cell_08` each hold `expected.csv`, the session's results to IS-2. `/app/data/pending/cell_11` and `/app/data/pending/cell_13` are packages without results.

Once delivered, indicate.py is run on the packages of six further cells, one run for each package. All of their engines and operating points lie within the scope of IS-2 section 1, and a package holds up to 6 cylinders and 20,000 cycles, counting every cylinder. Each run of indicate.py must finish within 4 seconds on 1 CPU. At every point and cylinder of the six packages the mean effective pressure must be within 2 per cent of the result to IS-2, the peak pressure within 1 per cent, the heat released within 3 per cent, and the three angles each within 0.3 degrees.

A run starts in an empty working directory into which only `indicate.py` has been copied. The user is unprivileged, there is no network, the package cannot be written to, and the exit status has to be 0. The interpreter is Python 3 with numpy, scipy and pandas.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
