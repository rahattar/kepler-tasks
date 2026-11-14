An engine test cell records cylinder pressure over many cycles at each operating point. Each session arrives as a package in the format described by `/app/data/docs/cell_package.md`, and IS-2 in `/app/data/docs/is2_indicating.md` defines the six results required for every operating point and cylinder: gross indicated mean effective pressure, peak pressure, crank angle at peak pressure, crank angles at 10 and 50 per cent burned, and gross heat released.

Write `/app/output/indicate.py` to process one package with `python3 indicate.py PACKAGE_DIR OUT_CSV`. The output must be an ordinary file, not a link, and at most 2 MiB (2,097,152 bytes). Use the exact header `point,cylinder,imep_bar,pmax_bar,apmax_deg,ca10_deg,ca50_deg,q_gross_J`, followed by one row for every point in the package's `points.csv` and every cylinder. Write the values as decimal numbers in the units named by the header.

Four packages are available. `/app/data/examples/cell_03` and `/app/data/examples/cell_08` each include `expected.csv` with that session's IS-2 results. `/app/data/pending/cell_11` and `/app/data/pending/cell_13` are packages without results.

The same program is later used once on each package from six other cells. Their packages use the same format, every engine and operating point is within IS-2 section 1, and a package may contain up to 6 cylinders and 20,000 cycles. For every point and cylinder, mean effective pressure must be within 2 per cent of the result to IS-2, peak pressure within 1 per cent, heat released within 3 per cent, and the three angles each within 0.3 degrees. Each run of indicate.py must finish within 4 seconds on 1 CPU.

For each run, a scratch directory contains a copy of `indicate.py` alone. The process runs as an unprivileged user without network access, the package is read-only, and the program must exit with status 0. Python 3 with numpy, scipy and pandas is available.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
