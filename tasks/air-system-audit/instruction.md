For each compressed air audit, the plant needs a set of results calculated from the logger data. Write `/app/output/audit.py` so that `python3 audit.py AUDIT_DIR OUT_JSON` reads one audit package from `AUDIT_DIR` and writes the results to `OUT_JSON` as JSON. `/app/data/docs/audit_procedure.md` defines those results, while `/app/data/docs/site_package.md` describes the package format. A past audit is available in `/app/data/examples/s-201/`, along with the results reported by the plant's energy engineer.

The program must also handle audit packages from eight other sites. For at least seven of those eight sites, average demand and specific power must each be within 3 % of the correct values, and peak demand and leak flow must each be within 5 %.

The eight audits run one after another, each through `python3 -I audit.py AUDIT_DIR OUT_JSON` in a scratch directory containing a copy of `audit.py` alone. The program must not read or import any other files from `/app/output`. Each run has 120 seconds to finish, under an unprivileged user without network access. `/app/data` remains readable at the same path. Python 3, numpy, scipy and pandas are available.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
