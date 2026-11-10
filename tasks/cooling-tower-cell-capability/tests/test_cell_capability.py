"""Pytest entry for cooling-tower-cell-capability. A single test decides the reward: every cell's capability in
/app/output/cell_capability.csv within 3 percentage points of the sealed value. The per-cell misses are written to
/logs/verifier/metrics.json for the record only. Nothing from the solution or the shipped data is read.
"""
import json
import os

import grade_cells

PATH = os.environ.get("CELL_CAPABILITY_PATH", "/app/output/cell_capability.csv")


def run():
    try:
        r = grade_cells.score(PATH)
    except Exception as e:                           # absent, not CSV, wrong columns or values
        r = {"accepted": False, "cells": {}, "missing": [], "error": repr(e)}
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, limit_pp=grade_cells.LIMIT), f, indent=1)
    except OSError:
        pass
    return r


def test_all_eight_cells_within_limit():
    r = run()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "missing cells: %s" % ", ".join(r["missing"])
    off = {c: v for c, v in r["cells"].items() if not v["accepted"]}
    assert not off, "; ".join("%s off by %+.1f pp" % (c, v["miss_pp"]) for c, v in sorted(off.items()))
