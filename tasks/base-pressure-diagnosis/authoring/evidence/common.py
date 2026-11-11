"""Shared harness for the evidence scripts.

Every answer an evidence script measures is written as a complete audit sheet and scored through the task's own
grader, exactly as the verifier scores a submission: `grade_audit.score()` reads the file from disk, validates it
and compares it with the sealed fleet. No evidence script asks the grader anything the verifier would not ask.

    sheet(answers)                 -> the CSV text of an audit sheet
    score(answers)                 -> the grader's result for it
    place_order(plan)              -> runs the real vacwork program on a scratch state and returns its output dir
    DATA                           -> the agent's /app/data as build.py writes it
    require_baseline(answers)      -> fails the study unless the reference itself is accepted

A study whose baseline is wrong measures nothing: a route "defeated" by a chamber the reference also gets wrong has
not been defeated by its defect. Every study calls require_baseline before it reports anything.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))
PROV = os.path.join(TASK, "authoring", "provenance")
TESTS = os.path.join(TASK, "tests")
RIG = os.path.join(TASK, "environment", "rig")
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.join(TESTS, "sealed"))
import fleet as F                                                       # noqa: E402
import grade_audit as G                                                 # noqa: E402

IDS = list(F.CHAMBER_IDS)
_work = tempfile.mkdtemp(prefix="bpd-evidence-")
DATA = os.path.join(_work, "data")


def _build():
    if not os.path.isdir(DATA):
        subprocess.run([sys.executable, "-I", os.path.join(PROV, "build.py"), DATA],
                       check=True, capture_output=True)
    return DATA


_build()


def sheet(answers):
    """answers: {chamber: (cause, q_total, s_eff)}."""
    lines = ["chamber,cause,q_total_mbarl_s,s_eff_l_s"]
    for cid in IDS:
        if answers.get(cid) is None:          # no answer for this chamber: the row is left out
            continue
        cause, q, s = answers[cid]
        lines.append("%s,%s,%.4e,%.1f" % (cid, cause, q, s))
    return "\n".join(lines) + "\n"


def score(answers, text=None):
    """Writes the sheet to a scratch file and scores it through the grader the verifier uses."""
    d = tempfile.mkdtemp(prefix="bpd-sheet-", dir=_work)
    path = os.path.join(d, "diagnosis.csv")
    with open(path, "w") as f:
        f.write(text if text is not None else sheet(answers))
    return G.score(path)


def score_text(text):
    return score(None, text=text)


def place_order(plan, tag="order", lab_seed=None):
    """Runs the real vacwork program on its own scratch state, as the agent's one order, and returns the
    directory holding its reports. The scratch state is keyed by the plan itself as well as the tag, so two
    different plans can never share one set of reports. With lab_seed, a copy of the program is run with the
    laboratory's scatter drawn from that seed: the shipped program has no way to change it."""
    key = hashlib.sha1(json.dumps([plan, lab_seed], sort_keys=True).encode()).hexdigest()[:12]
    d = os.path.join(_work, "vacwork-%s-%s" % (tag, key))
    rig = RIG
    if lab_seed is not None:
        rig = os.path.join(_work, "rig-%d" % lab_seed)
        if not os.path.isdir(rig):
            shutil.copytree(RIG, rig, ignore=shutil.ignore_patterns("__pycache__"))
            src = open(os.path.join(rig, "vacwork.py")).read()
            line = [l for l in src.splitlines() if l.startswith("LAB_SEED = ")]
            assert len(line) == 1, "vacwork.py must hold exactly one LAB_SEED line"
            open(os.path.join(rig, "vacwork.py"), "w").write(
                src.replace(line[0], "LAB_SEED = %d" % lab_seed, 1))
    out = os.path.join(d, "out")
    if os.path.isdir(out):
        return out
    os.makedirs(out)
    state = os.path.join(d, "state.json")
    p = subprocess.run([sys.executable, "-I", os.path.join(rig, "vacwork.py"), "submit", out, state],
                       input=json.dumps(dict(tests=plan)), text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("vacwork refused the plan: %s%s" % (p.stdout, p.stderr))
    return out


REFERENCE_PLAN = [dict(chamber="VC08", test="rga", pumping_time_h=36.0)]   # as solution/solve.sh places it


def reference_answers(plan=None, tag="reference"):
    """The shipped reference solution's own answers, by running it as the solution script does."""
    vac = place_order(plan or REFERENCE_PLAN, tag)
    out = os.path.join(_work, "ref-%s.csv" % tag)
    p = subprocess.run([sys.executable, "-I", os.path.join(TASK, "solution", "diagnose.py"), DATA, out, vac],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("the reference failed: %s%s" % (p.stdout, p.stderr))
    answers = {}
    with open(out) as f:
        next(f)
        for line in f:
            cid, cause, q, s = line.strip().split(",")
            answers[cid] = (cause, float(q), float(s))
    return answers


def reference_answers_without_order():
    """The reference run with no audit order placed at all, which is what an agent that never calls vacwork has."""
    out = os.path.join(_work, "ref-no-order.csv")
    p = subprocess.run([sys.executable, "-I", os.path.join(TASK, "solution", "diagnose.py"), DATA, out,
                        os.path.join(_work, "no-such-vacwork")], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("the reference failed without an order: %s%s" % (p.stdout, p.stderr))
    answers = {}
    with open(out) as f:
        next(f)
        for line in f:
            cid, cause, q, s = line.strip().split(",")
            answers[cid] = (cause, float(q), float(s))
    return answers


LAB_SEEDS = list(range(5301, 5321))   # the playbook's laboratory seeds


# what every study's result depends on, besides its own script
_INPUTS = ["tests/sealed/bpphys.py", "tests/sealed/fleet.py", "tests/grade_audit.py", "solution/diagnose.py",
           "solution/solve.sh", "environment/rig/vacwork.py", "authoring/provenance/build.py",
           "authoring/provenance/docs_bp.py", "authoring/evidence/common.py", "authoring/evidence/routes.py",
           "authoring/evidence/independent.py", "authoring/provenance/fleet.py", "authoring/provenance/bpphys.py"]


def fingerprint(script):
    """A digest of every file the study's result depends on. Each study prints it as its first line, and preflight
    recomputes it: a record whose inputs have changed since it was written is stale, whatever it says."""
    h = hashlib.sha1()
    for rel in sorted(_INPUTS + [os.path.relpath(os.path.abspath(script), TASK)]):
        h.update(rel.encode())
        with open(os.path.join(TASK, rel), "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:16]


def header(script):
    print("inputs: %s" % fingerprint(script))


def chamber_ok(base, cid, answer):
    """Whether the grader takes `answer` on chamber cid, scored as a whole sheet: `base` with that one row replaced.
    Nothing here repeats the grader's rules."""
    sheet_answers = dict(base)
    sheet_answers[cid] = answer
    r = score(sheet_answers)
    return bool(r["chambers"].get(cid, {}).get("ok"))


def truth():
    return {cid: F.truth(F.BY[cid]) for cid in IDS}


def require_baseline(answers, what="the reference"):
    """Stops the study unless the baseline it measures against is itself accepted, chamber by chamber."""
    r = score(answers)
    if not r["accepted"]:
        wrong = [cid for cid in IDS if not r["chambers"].get(cid, {}).get("ok")] or [r.get("error", "?")]
        print("BASELINE NOT ACCEPTED: %s gets %s wrong; this study measures nothing until it is fixed"
              % (what, " ".join(wrong)))
        cleanup()
        sys.exit(1)
    return r


def report(title, rows, head):
    """A fixed-width table for the .txt companions."""
    widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0)) for i, h in enumerate(head)]
    out = [title, "=" * len(title), ""]
    out.append("  ".join(str(h).ljust(w) for h, w in zip(head, widths)).rstrip())
    out.append("  ".join("-" * w for w in widths))
    for r in rows:
        out.append("  ".join(str(c).ljust(w) for c, w in zip(r, widths)).rstrip())
    return "\n".join(out) + "\n"


def cleanup():
    shutil.rmtree(_work, ignore_errors=True)
