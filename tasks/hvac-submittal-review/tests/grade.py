"""Grade a review file (path argument, or REVIEW_PATH, default /app/review.json) against the District's own
review, project.truth(), computed from the sealed as-built definition with the method in method.py.

The file must be a regular file (not a symlink) holding one JSON object without duplicate keys, with exactly the
keys units and submittal; units holds exactly RTU-1 to RTU-7. A unit with verdict undetermined holds exactly
verdict and missing; any other unit holds exactly verdict and the eight quantities in TOL, each a finite number
(not a boolean, string or null). A file that breaks any of this fails as a whole.

Per unit: the verdict must match; for determined units every quantity in TOL must be within its tolerance
(relative, except the coil entering wet bulb, absolute in K); for the undetermined unit the missing-information
code must match. The submittal decision must match. Pass when at most ALLOW_WRONG units are wrong."""
import json, math, os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project as P

# tolerances: relative unless noted. Loads and outdoor air carry the inference of unverified rooms (3%);
# capacities carry only the spread of psychrometric formulations and interpolation (2%); latent quantities
# are differences of two near numbers (5%); the coil entering wet bulb is absolute.
TOL = {"outdoor_air_l_s": ("rel", 0.03), "coil_entering_wb_c": ("abs", 0.3),
       "block_total_kw": ("rel", 0.03), "block_sensible_kw": ("rel", 0.03), "block_latent_kw": ("rel", 0.05),
       "net_capacity_total_kw": ("rel", 0.02), "net_capacity_sensible_kw": ("rel", 0.02),
       "net_capacity_latent_kw": ("rel", 0.05)}
ALLOW_WRONG = 0
VERDICTS = {"accept", "reject_undersized", "reject_oversized", "undetermined"}
MISSING = {"tenant_fitout_loads", "envelope_areas", "catalogue_data", "design_conditions"}


def _num(d, k):
    v = d.get(k)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _close(a, b, kind, tol):
    if a is None: return False
    return abs(a - b) <= (tol if kind == "abs" else tol * abs(b))


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key %r" % sorted({k for k in keys if keys.count(k) > 1}))
    return dict(pairs)


def _reject_constant(c):
    raise ValueError("%s is not a finite number" % c)


def read_review(path):
    """The review as a dict, or ValueError/OSError when the file breaks the required structure."""
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("not a regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, encoding="utf-8") as f:
        d = json.load(f, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    if not isinstance(d, dict):
        raise ValueError("not a JSON object")
    if set(d) != {"units", "submittal"}:
        raise ValueError("top-level keys must be exactly ['submittal', 'units'], got %s" % sorted(d))
    if not isinstance(d["units"], dict) or set(d["units"]) != set(P.UNITS):
        raise ValueError("units must hold exactly %s" % P.UNITS)
    for u in P.UNITS:
        a = d["units"][u]
        if not isinstance(a, dict):
            raise ValueError("%s is not an object" % u)
        want = {"verdict", "missing"} if a.get("verdict") == "undetermined" else {"verdict"} | set(TOL)
        if set(a) != want:
            raise ValueError("%s must hold exactly %s, got %s" % (u, sorted(want), sorted(a)))
        if a.get("verdict") != "undetermined":
            for k in TOL:
                if _num(a, k) is None:
                    raise ValueError("%s %s is not a finite number" % (u, k))
    return d


def grade(path):
    T = P.truth()
    rec = dict(passed=False, error=None, units={}, wrong=[])
    try:
        d = read_review(path)
    except Exception as e:
        rec["error"] = f"{path}: {e!r}"; return rec
    for u in P.UNITS:
        t = T[u]; a = d["units"][u]
        v = a.get("verdict")
        r = dict(verdict=v, expected_verdict=t["verdict"], ok=False, reasons=[])
        if v not in VERDICTS:
            r["reasons"].append("verdict missing or not one of %s" % sorted(VERDICTS))
        elif v != t["verdict"]:
            r["reasons"].append("verdict %s, review says %s" % (v, t["verdict"]))
        if t["verdict"] == "undetermined":
            if a.get("missing") != t["missing"]:
                r["reasons"].append("missing-information code %r, review says %r" % (a.get("missing"), t["missing"]))
        else:
            for k, (kind, tol) in TOL.items():
                x = _num(a, k)
                r[k] = x; r["expected_" + k] = t[k]
                if not _close(x, t[k], kind, tol):
                    r["reasons"].append("%s %s, review says %.2f (tolerance %s)" % (k, x, t[k], ("%.1f K" % tol) if kind == "abs" else ("%d%%" % round(100 * tol))))
        r["ok"] = not r["reasons"]
        rec["units"][u] = r
        if not r["ok"]: rec["wrong"].append(u)
    rec["submittal"] = d.get("submittal"); rec["expected_submittal"] = T["submittal"]
    rec["submittal_ok"] = d.get("submittal") == T["submittal"]
    rec["passed"] = len(rec["wrong"]) <= ALLOW_WRONG and rec["submittal_ok"]
    return rec


if __name__ == "__main__":
    r = grade(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REVIEW_PATH", "/app/review.json"))
    print(json.dumps(dict(passed=r["passed"], wrong=r["wrong"], error=r["error"],
                          reasons={u: r["units"][u]["reasons"] for u in r["wrong"]}), indent=1))
