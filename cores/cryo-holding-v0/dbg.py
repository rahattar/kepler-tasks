import csv, json, os, subprocess, sys
info = json.load(open("hidden_lab/what_is_true.json"))
def run(n, prog="/tmp/ref.py", env=None):
    d = ("hidden/" + n) if info[n]["kind"] == "hidden" else ("core/environment/data/%s/%s" % ("examples" if info[n]["kind"] == "example" else "pending", n))
    lab = "/tmp/crlab"; os.makedirs(lab + "/state", exist_ok=True); os.system("rm -rf %s/sealed; cp -r hidden_lab/sealed %s/sealed; rm -f %s/state/*" % (lab, lab, lab))
    os.makedirs("/tmp/crbin", exist_ok=True); open("/tmp/crbin/nertest", "w").write('#!/bin/bash\nLAB_DIR=%s exec python3 -B %s/lab.py nertest "$@"\n' % (lab, os.getcwd())); os.chmod("/tmp/crbin/nertest", 0o755)
    e = dict(os.environ, PATH="/tmp/crbin:" + os.environ["PATH"], **(env or {}))
    p = subprocess.run([sys.executable, prog, d, "/tmp/out.csv"], env=e, capture_output=True, text=True); print(n, p.stderr.strip()[-300:])
    got = {r["record"]: r for r in csv.DictReader(open("/tmp/out.csv"))}
    for t in csv.DictReader(open("hidden_lab/truth/%s.csv" % n)):
        g = got[t["record"]]; e1 = abs(float(g["p_barg"]) - float(t["p_barg"])) / 0.15
        if e1 > 0.7 or g["state"] != t["state"]: print("   ", t["record"], t["p_barg"], g["p_barg"], t["vented_kg"], g["vented_kg"], t["state"], g["state"])
for n in sys.argv[1:]:
    print(n, info[n]["f"], info[n]["tanks"]); run(n)
