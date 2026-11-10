"""Checks that the verifier fails malformed review files instead of crashing or reading them leniently. Each case
starts from the District's own review (which passes) and breaks one thing.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import copy, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import project as P, grade as G

T = P.truth()
GOOD = dict(units={u: (dict(verdict=T[u]["verdict"], missing=T[u]["missing"]) if T[u]["verdict"] == "undetermined"
                       else dict(verdict=T[u]["verdict"], **{k: T[u][k] for k in G.TOL})) for u in P.UNITS},
            submittal=T["submittal"])
TEXT = json.dumps(GOOD)


def edit(f):
    d = copy.deepcopy(GOOD); f(d); return json.dumps(d)


CASES = {
    "the District's review": TEXT,
    "NaN quantity": TEXT.replace('"outdoor_air_l_s": %s' % json.dumps(T["RTU-1"]["outdoor_air_l_s"]), '"outdoor_air_l_s": NaN', 1),
    "infinite quantity": TEXT.replace('"block_total_kw": %s' % json.dumps(T["RTU-2"]["block_total_kw"]), '"block_total_kw": Infinity', 1),
    "boolean quantity": edit(lambda d: d["units"]["RTU-3"].update(block_latent_kw=True)),
    "string quantity": edit(lambda d: d["units"]["RTU-3"].update(block_latent_kw=str(T["RTU-3"]["block_latent_kw"]))),
    "null quantity": edit(lambda d: d["units"]["RTU-4"].update(net_capacity_total_kw=None)),
    "duplicate key in a unit": TEXT.replace('"verdict": "accept"', '"verdict": "accept", "verdict": "accept"', 1),
    "duplicate unit": TEXT.replace('"units": {', '"units": {"RTU-1": %s, ' % json.dumps(GOOD["units"]["RTU-1"]), 1),
    "missing quantity": edit(lambda d: d["units"]["RTU-6"].pop("coil_entering_wb_c")),
    "extra key in a unit": edit(lambda d: d["units"]["RTU-6"].update(note="checked")),
    "quantities on the undetermined unit": edit(lambda d: d["units"]["RTU-5"].update(block_total_kw=15.78)),
    "missing unit": edit(lambda d: d["units"].pop("RTU-7")),
    "extra unit": edit(lambda d: d["units"].update({"RTU-8": d["units"]["RTU-2"]})),
    "extra top-level key": edit(lambda d: d.update(notes="")),
    "no submittal": edit(lambda d: d.pop("submittal")),
    "array instead of an object": "[]",
    "not JSON": "verdicts follow",
}

if __name__ == "__main__":
    print("Verifier robustness: only the well-formed District review may pass; every malformed file fails as a whole.\n")
    d = tempfile.mkdtemp()
    for name, text in CASES.items():
        p = os.path.join(d, "review.json")
        if os.path.lexists(p): os.unlink(p)
        open(p, "w").write(text)
        g = G.grade(p)
        print("%-38s %s  %s" % (name, "PASS" if g["passed"] else "FAIL", (g["error"] or "")[len(p) + 2:][:90]))
    os.mkdir(os.path.join(d, "target")); tgt = os.path.join(d, "target", "review.json"); open(tgt, "w").write(TEXT)
    for i, (case, make) in enumerate((("symlink to a correct review", lambda p: os.symlink(tgt, p)),
                                      ("directory", os.mkdir), ("no file", lambda p: None))):
        os.mkdir(os.path.join(d, str(i))); p = os.path.join(d, str(i), "review.json"); make(p)
        g = G.grade(p)
        print("%-38s %s  %s" % (case, "PASS" if g["passed"] else "FAIL", (g["error"] or "")[len(p) + 2:][:90]))
