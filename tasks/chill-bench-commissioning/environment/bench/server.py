"""Commissioning bench service.

Runs in its own container. Holds the sealed per-station accommodation coefficients and
the physics module; neither is present in the agent's container, and the agent reaches
this service only over the compose network.

The commissioning budget is decremented HERE, in the server, so it cannot be edited,
reset or bypassed from the agent side. A refused request costs nothing.

Standard library only -- no third-party dependency beyond numpy, which the physics
module needs.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import bench_core as core

PORT = int(os.environ.get("BENCH_PORT", "8000"))
_LOCK = threading.Lock()
_STATE = {"budget_total": core.BUDGET_RUNS, "runs_used": 0, "runs": []}


def _status():
    return {
        "budget_total": _STATE["budget_total"],
        "runs_used": _STATE["runs_used"],
        "runs_remaining": _STATE["budget_total"] - _STATE["runs_used"],
        "stations": core.names(),
        "max_run_s": core.MAX_RUN_S,
        "runs": _STATE["runs"],
    }


def _run(station, pressure, seconds):
    with _LOCK:
        if _STATE["runs_used"] >= _STATE["budget_total"]:
            return 402, {"error": "commissioning budget exhausted: "
                                  f"{_STATE['budget_total']} runs were available and "
                                  "all have been used. No further runs are possible."}
        index = _STATE["runs_used"] + 1
        try:
            header, rows = core.trace(station, pressure, seconds, index)
        except KeyError as e:
            return 404, {"error": str(e).strip("'"), "budget_charged": False}
        except ValueError as e:
            return 400, {"error": str(e), "budget_charged": False}
        _STATE["runs_used"] = index
        _STATE["runs"].append({"index": index, "station": station,
                               "pressure_torr": float(pressure),
                               "seconds": float(seconds)})
    csv_text = ",".join(header) + "\n" + "\n".join(",".join(r) for r in rows) + "\n"
    return 200, {"index": index, "station": station,
                 "pressure_torr": float(pressure), "seconds": float(seconds),
                 "samples": len(rows),
                 "runs_remaining": _STATE["budget_total"] - index,
                 "csv": csv_text}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/status", "/"):
            return self._send(200, _status())
        if u.path == "/run":
            missing = [k for k in ("station", "pressure", "seconds") if k not in q]
            if missing:
                return self._send(400, {"error": "missing query parameters: "
                                                 + ", ".join(missing)})
            try:
                p, s = float(q["pressure"][0]), float(q["seconds"][0])
            except ValueError:
                return self._send(400, {"error": "pressure and seconds must be numbers"})
            code, payload = _run(q["station"][0], p, s)
            return self._send(code, payload)
        self._send(404, {"error": f"no such endpoint {u.path}; "
                                  "use /status or /run"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
