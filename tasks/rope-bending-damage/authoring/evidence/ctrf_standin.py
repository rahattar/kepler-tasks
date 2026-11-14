"""Writes pytest's ctrf report where the pytest-json-ctrf plugin is missing.

The verifier's image has pytest-json-ctrf 0.3.5, and tests/test.sh passes pytest the plugin's option,
`--ctrf=PATH`. A machine with no network cannot install the plugin. On such a machine verifier_run.py puts this
module in PYTEST_PLUGINS; it accepts the same option and writes, at PATH, the one part of the report that
tests/tally.py looks at, results.summary with its six counts. The verifier never loads it. verifier_run.txt
says in its first lines whether it was used.
"""
import json

COUNTED = ("passed", "failed", "skipped")


def pytest_addoption(parser):
    parser.addoption("--ctrf", default=None, metavar="PATH", help="where the ctrf report goes")


def pytest_configure(config):
    where = config.getoption("--ctrf")
    if where:
        config.pluginmanager.register(Summary(where), name="summary-for-tally")


class Summary:
    def __init__(self, where):
        self.where = where
        self.summary = dict.fromkeys(("tests",) + COUNTED + ("pending", "other"), 0)

    def pytest_runtest_logreport(self, report):
        ran = report.when == "call"
        broke_before = report.when == "setup" and not report.passed
        if ran or broke_before:
            self.summary["tests"] += 1
            self.summary[report.outcome if report.outcome in COUNTED else "other"] += 1

    def pytest_sessionfinish(self):
        with open(self.where, "w") as handle:
            json.dump({"results": {"tool": {"name": "pytest"}, "summary": self.summary}}, handle)
