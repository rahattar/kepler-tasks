A steel company uses RS-4 in `/app/data/docs/rs4_rope_bending.md` to reckon bending fatigue damage along the hoist ropes of its overhead cranes from the recorded movements and rope surveys. Each works provides a package in the format described by `/app/data/docs/works_package.md`.

Write `/app/output/ropes.py` to process one works package with `python3 ropes.py WORKS_DIR OUT_CSV`. The resulting `OUT_CSV` must be an ordinary file, not a link, no larger than 1 MiB (1,048,576 bytes). Use the header `row,damage`, followed by one row for every station of every crane's rope. Row names follow the convention used for `expected.csv` in `/app/data/docs/works_package.md`, and each damage value is written as a decimal number.

Three packages are available. `/app/data/examples/forge_bay` and `/app/data/examples/plate_shop` each include `expected.csv` with that works' RS-4 results. `/app/data/pending/melt_hall` is provided without results.

The same program is later used once on each package from six other works. A package may contain up to 6 cranes, 600,000 movements counting every crane, and ropes of up to 400 m. At every station, the reported damage must be within 8 per cent of the greatest damage of that rope's result to RS-4. Each run of ropes.py must finish within 4 seconds on 1 CPU.

Runs take place in an empty working directory containing only a copied `ropes.py`. The process uses an unprivileged account without network access, the package cannot be written to, and the program must exit with status 0. Python 3 with numpy, scipy and pandas is available.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
