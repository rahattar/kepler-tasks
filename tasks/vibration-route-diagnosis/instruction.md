The plant needs a program to give a first-pass diagnosis for every machine on a vibration route. Save it as `/app/output/diagnose.py`, to run with `python3 diagnose.py ROUTE_DIR OUT_CSV`. It must read one route package and write OUT_CSV with the header `machine,fault,component` and one row per machine in the route's register. Use the condition codes and components defined in `/app/data/docs/condition_codes.md`.

The route package format is described in `/app/data/docs/route_package.md`. An example from route U-2 on October 20, 2026, along with the analyst's report, is in `/app/data/examples/u2-2026-10-20/`.

The program will be tested on six other route packages from other areas of the plant, covering 60 machines. At least 58 must be diagnosed correctly, with both the condition code and component matching. Python 3, numpy, scipy, and pandas are available. For testing, the six routes are run one after another, each with `python3 -I diagnose.py ROUTE_DIR OUT_CSV` in a scratch directory that holds a copy of `diagnose.py` alone (so it must not import or read other files from `/app/output`), as an unprivileged user without network access, and each run must finish within 300 seconds. `/app/data` is readable at the same path during testing.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
