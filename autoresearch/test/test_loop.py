#!/usr/bin/env python3
"""Tests for the autonomous loop + Judge, driven by a deterministic proposer.

The proposer replays the two oracle-verified schemes (coded) plus an uncoded baseline
of each. Coded should dominate uncoded on load (equal elsewhere), so the per-regime
frontier keeps the coded scheme and rejects the uncoded one as dominated.

Run: python3 test/test_loop.py
"""

import copy
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from loop import run_loop, uncoded_repair  # noqa: E402
from store import PlacementStore  # noqa: E402
import fixture_a  # noqa: E402
import fixture_cdr_k5  # noqa: E402

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


class FixtureProposer:
    """Replays verified schemes: a coded candidate and an uncoded baseline per regime."""
    BUILD = {(8, 6, 8): ("cyclic", fixture_a.build),
             (5, 3, 5): ("ordered-subset", fixture_cdr_k5.build)}

    def propose(self, regime):
        if regime not in self.BUILD:
            return []
        family, build = self.BUILD[regime]
        fx = build()
        base = {k: fx[k] for k in ("initial", "target", "plan", "repair")}
        uncoded = {**base, "repair": uncoded_repair(fx["plan"], fx["initial"])}
        return [
            {"label": f"{family}-coded", "family": family, "scheme": base},
            {"label": f"{family}-uncoded", "family": family, "scheme": uncoded},
        ]


class BrokenProposer:
    """Emits an invalid scheme (dropped replica) to exercise the gate's reject path."""
    def propose(self, regime):
        fx = fixture_a.build()
        s = copy.deepcopy({k: fx[k] for k in ("initial", "target", "plan", "repair")})
        s["initial"]["segments"][0]["storage"] = s["initial"]["segments"][0]["storage"][:-1]
        return [{"label": "broken", "family": "cyclic", "scheme": s}]


with tempfile.TemporaryDirectory() as d:
    store = PlacementStore(Path(d) / "store.json")
    summary = run_loop(FixtureProposer(), [(8, 6, 8), (5, 3, 5), (6, 3, 6)], store)

    check("2 schemes accepted (coded in each regime)", summary["accepted"] == 2, str(summary["accepted"]))
    check("2 schemes rejected (uncoded dominated)", summary["rejected"] == 2, str(summary["rejected"]))

    r86 = next(r for r in summary["regimes"] if r["regime"]["K"] == 8)
    check("(8,6) frontier = 1 coded scheme", len(r86["frontier"]) == 1 and "coded" in r86["frontier"][0]["label"])
    check("(8,6) coded load is 72 on the frontier", r86["frontier"][0]["comm_load"] == 72,
          str(r86["frontier"][0]["comm_load"]))
    check("(8,6) uncoded rejected as dominated",
          any(x["reason"] == "dominated" for x in r86["rejected"]))

    r53 = next(r for r in summary["regimes"] if r["regime"]["K"] == 5)
    check("(5,3) frontier = 1 coded scheme, load 12", len(r53["frontier"]) == 1 and r53["frontier"][0]["comm_load"] == 12)

    r63 = next(r for r in summary["regimes"] if r["regime"]["K"] == 6)
    check("(6,3) no proposal (proposer has no scheme)", r63.get("note") == "no proposal")

    check("store holds 2 accepted", len(store.accepted()) == 2)

    # idempotent: re-running an explored regime adds nothing (dedup by canonical hash)
    summary2 = run_loop(FixtureProposer(), [(8, 6, 8)], store)
    check("re-explored regime is skipped", summary2["regimes"][0].get("note") == "already explored (skipped)")
    check("store still holds 2 accepted after re-run", len(store.accepted()) == 2)

# gate rejects invalid proposals
with tempfile.TemporaryDirectory() as d:
    store2 = PlacementStore(Path(d) / "store.json")
    summary3 = run_loop(BrokenProposer(), [(8, 6, 8)], store2)
    check("invalid scheme: 0 accepted", summary3["accepted"] == 0)
    check("invalid scheme: 1 rejected", summary3["rejected"] == 1)
    check("invalid scheme recorded with reason 'invalid…'",
          any((rec.get("reason") or "").startswith("invalid") for rec in store2.results(status="reject")))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
