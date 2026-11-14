"""A pytest plugin that stands in for pytest-json-ctrf where that plugin is not installed.

verifier_run.py loads it (PYTEST_PLUGINS) only when pytest_jsonctrf cannot be imported, and says so in what it
writes. It accepts `--ctrf=PATH` and leaves at PATH a report with the parts tests/tally.py reads: the summary
counts and the list of tests with their outcome. The verifier's image installs the real plugin.
"""
import json

_tests = []


def pytest_addoption(parser):
    parser.addoption("--ctrf", action="store", default="", help="where to write the report")


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _tests.append({"name": report.nodeid, "status": report.outcome if report.outcome in ("passed", "failed", "skipped") else "other"})


def pytest_sessionfinish(session):
    where = session.config.getoption("--ctrf")
    if not where:
        return
    summary = {key: sum(1 for t in _tests if t["status"] == key) for key in ("passed", "failed", "skipped", "other")}
    summary.update(tests=len(_tests), pending=0)
    with open(where, "w") as handle:
        json.dump({"results": {"tool": {"name": "pytest"}, "summary": summary, "tests": _tests}}, handle)
