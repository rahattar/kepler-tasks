"""A stand-in for the pytest-json-ctrf plugin, for machines where that plugin is not installed.

The verifier's image installs pytest-json-ctrf==0.3.5 and tests/test.sh uses its `--ctrf=PATH` option. Where an
evidence script has to run pytest on a machine without the plugin (one without network access cannot install
it), it loads this module with `-p ctrf_standin` instead. It takes the same option and writes the part of a
ctrf report that tests/one_passed.py reads: results.summary, with the counts of tests, passed, failed, skipped,
pending and other. It is never used by the verifier, and verifier_run.txt says when it was used.
"""
import json


def pytest_addoption(parser):
    parser.addoption("--ctrf", action="store", default=None, help="path of the ctrf report")


class _Tally:
    def __init__(self, path):
        self.path = path
        self.counts = {"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "pending": 0, "other": 0}

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            self.counts["tests"] += 1
            self.counts[report.outcome if report.outcome in ("passed", "failed", "skipped") else "other"] += 1

    def pytest_sessionfinish(self, session):
        with open(self.path, "w") as handle:
            json.dump({"results": {"tool": {"name": "pytest"}, "summary": self.counts}}, handle)


def pytest_configure(config):
    path = config.getoption("--ctrf")
    if path:
        config.pluginmanager.register(_Tally(path), "ctrf-stand-in")
