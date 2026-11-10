"""Capture-hood visits by the TAB contractor (runs as the tab user). Five visits in total.

    python3 -I server.py PORT OUT_DIR STATE_FILE
      GET  /status              visits left and the boxes visited so far
      POST /visit?box=VAV-3-07  the box is driven to design minimum, a midpoint and design maximum; at each point
                                the report gives the hood reading at every diffuser and the box's trended values

Each request uses one visit, a repeated box included. The visit is charged to the state file before the readings
are taken, so restarting the service does not reset the count. Reports are returned and also written to
OUT_DIR/visit<k>_<tag>.json, readable by the agent. The service's code, the sealed definition and the state file
are private to the tab user.
"""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vav

BUDGET = 5
PORT, OUT, STATE = int(sys.argv[1]), sys.argv[2], sys.argv[3]
LOCK = threading.Lock()
FLOOR = {b["tag"]: b for b in vav.make_floor(31)}


def load_state():
    try:
        with open(STATE) as f:
            s = json.load(f)
        return dict(left=int(s["left"]), visits=list(s["visits"]))
    except (OSError, ValueError, KeyError):
        return dict(left=BUDGET, visits=[])


def save_state(s):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, STATE)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, obj):
        body = json.dumps(obj, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/status":
            with LOCK:
                s = load_state()
            return self.reply(200, dict(visits_left=s["left"], visits=[v["tag"] for v in s["visits"]],
                                        note="POST /visit?box=<tag> uses one visit"))
        self.reply(404, dict(error="unknown path", endpoints=["GET /status", "POST /visit?box=<tag>"]))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/visit":
            return self.reply(404, dict(error="unknown path", endpoints=["GET /status", "POST /visit?box=<tag>"]))
        tag = (parse_qs(u.query).get("box") or [""])[0].strip().upper()
        if tag not in FLOOR:
            return self.reply(400, dict(error="unknown box %r" % tag, boxes=sorted(FLOOR)))
        with LOCK:
            s = load_state()
            if s["left"] <= 0:
                return self.reply(409, dict(error="no visits left", visits=[v["tag"] for v in s["visits"]]))
            s["left"] -= 1                      # charged before the readings are taken
            k = len(s["visits"]) + 1
            s["visits"].append(dict(visit=k, tag=tag))
            save_state(s)
            rec = dict(visit=k, tag=tag, points=vav.hood_visit(FLOOR[tag], k), visits_left=s["left"])
            path = os.path.join(OUT, "visit%d_%s.json" % (k, tag))
            with open(path, "w") as f:
                json.dump(rec, f, indent=1)
            os.chmod(path, 0o644)
        self.reply(200, rec)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
