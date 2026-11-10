"""Runs the submitted supervisor inside the verifier's sandbox process.

The verifier starts this script as an unprivileged user with the supervisor file beside it, and
talks to it over JSON lines on stdin/stdout:

    -> {"op": "init"}                  <- {"ok": true}
    -> {"op": "step", "obs": {...}}    <- {"ok": true, "command": {...}}
    -> {"op": "exit"}

One process serves the whole graded period, so the controller keeps its state across all steps.
The protocol uses private copies of the original stdin/stdout descriptors. Before the controller
is imported, descriptor 1 is pointed at stderr and descriptor 0 at /dev/null, so nothing the
controller prints or reads can corrupt or consume the protocol.
"""
import importlib.util
import json
import os
import sys
import traceback


def _plain(o):
    """numpy scalars become the plain Python value they hold and numpy arrays the list they hold, so returning
    numpy floats, a tuple or a length-2 numpy array from update() is not an interface error."""
    tolist = getattr(o, "tolist", None)
    if callable(tolist):
        return tolist()
    item = getattr(o, "item", None)
    if callable(item):
        return item()
    raise TypeError("%r is not JSON-serialisable" % (o,))


def main():
    proto_in = os.fdopen(os.dup(0), "r", buffering=1)
    proto_out = os.fdopen(os.dup(1), "w", buffering=1)
    devnull = os.open(os.devnull, os.O_RDONLY)
    os.dup2(devnull, 0)
    os.dup2(2, 1)
    sys.stdin = open(os.devnull)
    sys.stdout = sys.stderr

    def send(obj):
        proto_out.write(json.dumps(obj) + "\n")
        proto_out.flush()

    path = sys.argv[1]
    ctrl = None
    try:
        spec = importlib.util.spec_from_file_location("submitted_supervisor", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls = getattr(mod, "Supervisor")
    except BaseException:
        send({"ok": False, "error": "import failed: " + traceback.format_exc(limit=3)[-600:]})
        return

    for line in proto_in:
        try:
            msg = json.loads(line)
        except ValueError:
            return
        op = msg.get("op")
        if op == "exit":
            return
        try:
            if op == "init":
                ctrl = cls()
                send({"ok": True})
            elif op == "step":
                cmd = ctrl.update(msg["obs"])
                try:
                    payload = json.loads(json.dumps(cmd, default=_plain))
                except (TypeError, ValueError):
                    send({"ok": False, "error": "update returned something that is not "
                                                "JSON-serialisable: %r" % (cmd,)})
                    continue
                send({"ok": True, "command": payload})
            else:
                send({"ok": False, "error": "unknown op %r" % op})
        except BaseException:
            send({"ok": False, "error": traceback.format_exc(limit=3)[-600:]})


if __name__ == "__main__":
    main()
