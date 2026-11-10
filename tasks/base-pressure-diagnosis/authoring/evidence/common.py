"""Shared harness for the evidence scripts.

Every answer an evidence script measures is written as a complete audit sheet and scored through the task's own
grader, exactly as the verifier scores a submission: `grade_audit.score()` reads the file from disk, validates it
and compares it with the sealed fleet. No evidence script asks the grader anything the verifier would not ask.

    sheet(answers)                 -> the CSV text of an audit sheet
    score(answers)                 -> the grader's result for it
    place_order(plan)              -> runs the real vacwork program on a scratch state and returns its output dir
    DATA                           -> the agent's /app/data as build.py writes it
"""
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


def place_order(plan, tag="order"):
    """Runs the real vacwork program on its own scratch state, as the agent's one order, and returns the
    directory holding its reports."""
    d = os.path.join(_work, "vacwork-" + tag)
    out = os.path.join(d, "out")
    if os.path.isdir(out):
        return out
    os.makedirs(out)
    state = os.path.join(d, "state.json")
    p = subprocess.run([sys.executable, "-I", os.path.join(RIG, "vacwork.py"), "submit", out, state],
                       input=json.dumps(dict(tests=plan)), text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("vacwork refused the plan: %s%s" % (p.stdout, p.stderr))
    return out


REFERENCE_PLAN = [dict(chamber="VC06", test="rga"), dict(chamber="VC08", test="rga"),
                  dict(chamber="VC09", test="speed-test"), dict(chamber="VC10", test="speed-test")]


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


def truth():
    return {cid: F.truth(F.BY[cid]) for cid in IDS}


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
