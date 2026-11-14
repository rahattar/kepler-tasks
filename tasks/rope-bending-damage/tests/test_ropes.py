"""The verifier's single pytest test. All the deciding is done in rope_bench.py; see its docstring."""
from rope_bench import delivered_verdict


def test_bench_accepts_delivered_ropes_program():
    accepted, story = delivered_verdict()
    assert accepted, "the bench does not accept ropes.py:\n" + story
