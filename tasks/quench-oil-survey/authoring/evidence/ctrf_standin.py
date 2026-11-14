"""A stand-in for the pytest-json-ctrf plugin, for a machine that has pytest but not the plugin.

verifier_run.py loads it only when the plugin itself cannot be imported. It takes the same `--ctrf=PATH`
option and writes the same summary block (tests, passed, failed, skipped, pending, other), which is all that
tests/read_report.py reads. The verifier's image installs the real plugin and never sees this file.
"""
import json

TALLY = dict(tests=0, passed=0, failed=0, skipped=0, pending=0, other=0)


def pytest_addoption(parser):
    parser.addoption("--ctrf", action="store", default=None)


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        TALLY["tests"] += 1
        TALLY[report.outcome if report.outcome in TALLY else "other"] += 1


def pytest_sessionfinish(session):
    path = session.config.getoption("--ctrf")
    if path:
        with open(path, "w") as handle:
            json.dump({"results": {"tool": {"name": "pytest"}, "summary": TALLY}}, handle)
