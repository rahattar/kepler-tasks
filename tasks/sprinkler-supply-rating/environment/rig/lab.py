#!/usr/bin/env python3
"""The contractor's flow test order.

    lab.py flowtest status
    lab.py flowtest submit        (the plan as JSON on standard input)

LAB_DIR holds `sealed/` (the site as it is) and `state/` (the order once placed); REPORT_DIR receives the report.
The order is placed once. A plan that is not in form is refused without using the order up.
"""
import json
import os
import sys

LAB_DIR = os.environ.get("LAB_DIR", "/opt/flowtest")
REPORT_DIR = os.environ.get("REPORT_DIR", "/app/flowtest")
STATE = os.path.join(LAB_DIR, "state", "order.json")
sys.path.insert(0, os.path.join(LAB_DIR, "sealed"))
sys.dont_write_bytecode = True


def placed():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return None


def status():
    order = placed()
    if order is None:
        print("No order has been placed. One flow test is available.")
    else:
        print("The order has been placed: riser %s at %.0f gpm. No test remains." % (order["riser"], order["flow_gpm"]))
    return 0


def refuse(why):
    print("flowtest: plan refused: %s" % why, file=sys.stderr)
    return 2


def submit():
    import supply_site as S
    if placed() is not None:
        print("flowtest: the order has already been placed and cannot be changed", file=sys.stderr)
        return 3
    try:
        plan = json.loads(sys.stdin.read())
    except ValueError:
        return refuse("the plan is not JSON")
    if not isinstance(plan, dict) or set(plan) != {"riser", "flow_gpm"}:
        return refuse('the plan is an object with exactly "riser" and "flow_gpm"')
    riser, flow = plan["riser"], plan["flow_gpm"]
    if riser not in [r["id"] for r in S.RISERS]:
        return refuse("no such riser")
    if isinstance(flow, bool) or not isinstance(flow, (int, float)):
        return refuse("flow_gpm is not a number")
    lo, hi = S.FLOW_TEST_RANGE
    if not lo <= flow <= hi:
        return refuse("flow_gpm is outside %.0f to %.0f" % (lo, hi))
    with open(os.path.join(LAB_DIR, "sealed", "seed.json")) as f:
        seed = json.load(f)["seed"]
    rep = S.flow_test(riser, float(flow), seed)
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump({"riser": riser, "flow_gpm": float(flow)}, f)
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "flow_test_report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    with open(os.path.join(REPORT_DIR, "flow_test_report.md"), "w") as f:
        f.write("# Flow test report\n\n"
                "- riser: %(riser)s\n- date and time: %(date)s %(time)s\n"
                "- flow on the contractor's meter: %(flow_gpm).0f gpm\n"
                "- supply gauge: %(gauge_serial)s\n"
                "- supply gauge before the header was opened: %(static_psi).1f psi\n"
                "- supply gauge with the flow steady: %(residual_psi).1f psi\n"
                "- transmitter PT-0 at the same minute: %(transmitter_psi).2f psi\n" % rep)
    print("Order placed: riser %s at %.0f gpm. Report written to %s" % (riser, flow, REPORT_DIR))
    return 0


def main(argv):
    if len(argv) == 3 and argv[1] == "flowtest" and argv[2] in ("status", "submit"):
        return status() if argv[2] == "status" else submit()
    print("usage: flowtest status | flowtest submit < plan.json", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
