"""Writes the summary of a ctrf report where pytest is installed and the pytest-json-ctrf plugin is not.

verifier_run.py loads this only when the real plugin cannot be imported, and says so in its output. It takes
the plugin's `--ctrf=PATH` option and leaves at PATH the one block tests/one_passed.py reads: the counts of
tests, passed, failed, skipped, pending and other. The verifier's image has the real plugin.
"""
import json

seen = {"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "pending": 0, "other": 0}


def pytest_addoption(parser):
    parser.addoption("--ctrf", action="store", default="")


def pytest_runtest_logreport(report):
    counted = report.when == "call" or (report.when == "setup" and not report.passed)
    if counted:
        seen["tests"] += 1
        seen[report.outcome if report.outcome in ("passed", "failed", "skipped") else "other"] += 1


def pytest_sessionfinish(session):
    where = session.config.getoption("--ctrf")
    if where:
        with open(where, "w") as out:
            json.dump({"results": {"tool": {"name": "pytest"}, "summary": seen}}, out)
