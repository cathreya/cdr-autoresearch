#!/usr/bin/env python3
"""Tests for CodexProposer wiring, using a FAKE runner (no codex needed).

The fake runner stands in for the codex agents by writing artifacts into the workdir,
exactly as a real agent would. We test three agent behaviors end-to-end through run_loop:
  - a good agent -> scheme proposed, gated, accepted on the frontier;
  - a silent agent (writes nothing) -> no proposal;
  - a broken agent (invalid placement) -> scheme proposed but gated out as invalid.

Run: python3 test/test_codex_proposer.py
"""

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from codex_proposer import CodexProposer  # noqa: E402
from loop import run_loop  # noqa: E402
from store import PlacementStore  # noqa: E402
import fixture_a  # noqa: E402

passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}" + (f"  — {detail}" if detail else ""))


def _w(path, obj):
    Path(path).write_text(json.dumps(obj))


def make_runner(mode="good"):
    """Return a fake runner(step, prompt, workdir) that simulates an agent writing files."""
    def run(step, prompt, workdir):
        wd = Path(workdir)
        fx = fixture_a.build()
        if step == "placement":
            initial = fx["initial"]
            if mode == "broken":
                initial = json.loads(json.dumps(initial))
                initial["segments"][0]["storage"] = initial["segments"][0]["storage"][:-1]
            if mode != "silent":
                _w(wd / "cand.placement.json", initial)
                _w(wd / "cand.target.json", fx["target"])
        elif step == "plan" and mode != "silent":
            _w(wd / "cand.plan.json", fx["plan"])
        elif step == "repair" and mode != "silent":
            _w(wd / "cand.repair.json", fx["repair"])
        return None
    return run


# --- good agent: proposed, gated, accepted ---
with tempfile.TemporaryDirectory() as d:
    prop = CodexProposer(runner=make_runner("good"), workroot=Path(d) / "wk")
    cands = prop.propose((8, 6, 8))
    check("good agent -> 1 candidate", len(cands) == 1, str(len(cands)))
    check("candidate carries full scheme", all(k in cands[0]["scheme"] for k in ("initial", "target", "plan", "repair")))
    store = PlacementStore(Path(d) / "store.json")
    summary = run_loop(prop, [(8, 6, 8)], store)
    check("loop accepts the codex scheme", summary["accepted"] == 1, str(summary))
    fr = summary["regimes"][0]["frontier"]
    check("accepted scheme is the verified coded one (load 72)", fr and fr[0]["comm_load"] == 72,
          str(fr))
    check("store has 1 accepted", len(store.accepted()) == 1)

# --- silent agent: no files -> no proposal ---
with tempfile.TemporaryDirectory() as d:
    prop = CodexProposer(runner=make_runner("silent"), workroot=Path(d) / "wk")
    check("silent agent -> no candidate", prop.propose((8, 6, 8)) == [])
    store = PlacementStore(Path(d) / "store.json")
    summary = run_loop(prop, [(8, 6, 8)], store)
    check("loop logs 'no proposal'", summary["regimes"][0].get("note") == "no proposal")

# --- broken agent: invalid placement -> proposed but gated out ---
with tempfile.TemporaryDirectory() as d:
    prop = CodexProposer(runner=make_runner("broken"), workroot=Path(d) / "wk")
    cands = prop.propose((8, 6, 8))
    check("broken agent still returns a candidate (files exist)", len(cands) == 1)
    store = PlacementStore(Path(d) / "store.json")
    summary = run_loop(prop, [(8, 6, 8)], store)
    check("loop gates the invalid scheme out (0 accepted)", summary["accepted"] == 0, str(summary))
    check("invalid scheme recorded as rejected", summary["rejected"] == 1)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
