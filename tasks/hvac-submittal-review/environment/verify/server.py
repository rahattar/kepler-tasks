"""Field-verification service of the facilities office. GET /status lists the items and the verifications
remaining; GET /verify?item=<id> returns the office's field report for that item, and each item is charged
once. Runs as its own user: the agent's user can neither read this directory nor the state file, so the
as-built values of items it did not verify never reach it. The budget is kept in the state file and written
before each report is returned, so a restart does not reset it.

    python3 -I server.py [port] [state_path]
"""
import json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project as P

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
STATE = sys.argv[2] if len(sys.argv) > 2 else "/var/lib/verify/state.json"
LOCK = threading.Lock()


def load():
    try:
        with open(STATE) as f:
            s = json.load(f)
        return dict(left=int(s["left"]), done=dict(s["done"]), log=list(s.get("log", [])))
    except (OSError, ValueError, KeyError):
        return dict(left=P.BUDGET, done={}, log=[])


def save(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, STATE)


state = load()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, obj):
        b = json.dumps(obj, indent=1).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/status":
            with LOCK:
                return self._send(200, dict(verifications_remaining=state["left"], verified=sorted(state["done"]), items=P.items(),
                                            note="GET /verify?item=<id> returns the facilities office's field report for that item; each item is charged once"))
        if u.path == "/verify":
            item = (q.get("item") or [""])[0]
            with LOCK:
                if item in state["done"]:
                    return self._send(200, state["done"][item])
                r = P.verification(item)
                if r is None:
                    return self._send(404, dict(error="unknown item", items=P.items()))
                if state["left"] <= 0:
                    state["log"].append([time.strftime("%H:%M:%S"), "refused", item]); save(state)
                    return self._send(429, dict(error="verification budget exhausted", verified=sorted(state["done"])))
                state["left"] -= 1; state["done"][item] = r
                state["log"].append([time.strftime("%H:%M:%S"), "verify", item]); save(state)
                return self._send(200, r)
        self._send(404, dict(error="not found", endpoints=["/status", "/verify?item=<id>"]))


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
