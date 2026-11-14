A steel company reckons the bending fatigue damage along the hoist ropes of its overhead cranes to its standard RS-4, `/app/data/docs/rs4_rope_bending.md`, from each crane's movement log and the surveys of its rope. A works sends its records in as a package, laid out as `/app/data/docs/works_package.md` describes.

`/app/output/ropes.py` is the program that makes this calculation for one package. The command is `python3 ropes.py WORKS_DIR OUT_CSV`. `OUT_CSV` is written as an ordinary file, not a link, of at most 1 MiB (1,048,576 bytes): a CSV table with the header `row,damage` and one row for every station of every crane's rope, each row named as `works_package.md` names the rows of `expected.csv`, the damage written as a decimal number.

Three packages are on hand. `/app/data/examples/forge_bay` and `/app/data/examples/plate_shop` each hold `expected.csv`, the works' results to RS-4. `/app/data/pending/melt_hall` is a package without results.

Once delivered, ropes.py is run on the packages of six other works, one run for each package. A package holds up to 6 cranes, 600,000 movements counting every crane, and ropes of up to 400 m. Each run of ropes.py must finish within 4 seconds on 1 CPU. At every station the damage must be within 8 per cent of the greatest damage of that rope's result to RS-4.

A run starts in an empty working directory into which only `ropes.py` has been copied. The user is unprivileged, there is no network, the package cannot be written to, and the exit status has to be 0. The interpreter is Python 3 with numpy, scipy and pandas.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
