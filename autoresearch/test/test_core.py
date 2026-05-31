#!/usr/bin/env python3
"""Tests for the research-loop substrate: metrics, Pareto frontier, store, generator.

Run: python3 test/test_core.py
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from metrics import compute_metrics, baseline_load  # noqa: E402
from pareto import ParetoFront, dominates, frontier_by_regime  # noqa: E402
from store import PlacementStore  # noqa: E402
from generator import run_generator  # noqa: E402
from fixture_a import build  # noqa: E402

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


# ---------- metrics ----------
fa = build()
m = compute_metrics(fa["initial"], fa["target"], fa["plan"], fa["repair"])
check("metrics: scheme fully valid", m["valid"], str(m["errors"]))
check("metrics: comm_load 72", m["comm_load"] == 72, f"got {m['comm_load']}")
check("metrics: baseline 84", m["baseline"] == 84, f"got {m['baseline']}")
check("metrics: io_reads 12", m["io_reads"] == 12, f"got {m['io_reads']}")
check("metrics: subpacketization N=8 (cyclic, =K)", m["subpacketization"] == 8, f"got {m['subpacketization']}")
check("metrics: split_factor 14 (unit)", m["split_factor"] == 14, f"got {m['split_factor']}")
check("metrics: load_fraction < 1 (beats baseline)", m["load_fraction"] < 1)

# ---------- pareto ----------
axes = ["comm_load", "io_reads", "subpacketization"]
p1 = {"id": "a", "comm_load": 72, "io_reads": 12, "subpacketization": 14}
p2 = {"id": "b", "comm_load": 84, "io_reads": 10, "subpacketization": 14}   # tradeoff vs p1
p3 = {"id": "c", "comm_load": 72, "io_reads": 12, "subpacketization": 16}   # dominated by p1
check("pareto: dominates p1>p3", dominates(p1, p3, axes))
check("pareto: p1, p2 mutually non-dominated", not dominates(p1, p2, axes) and not dominates(p2, p1, axes))
f = ParetoFront(axes)
check("pareto: p1 enters front", f.add(p1))
check("pareto: p2 enters front (wins on io)", f.add(p2))
check("pareto: p3 rejected (dominated)", not f.add(p3))
check("pareto: front size 2", len(f.front()) == 2)

# regime-keyed frontiers — same scheme, different (K,r)
recs = [
    {"id": "x", "K": 8, "r": 6, "comm_load": 72, "io_reads": 12, "subpacketization": 14},
    {"id": "y", "K": 6, "r": 3, "comm_load": 30, "io_reads": 8, "subpacketization": 10},
]
fronts = frontier_by_regime(recs, axes)
check("pareto: frontier per regime", set(fronts.keys()) == {(8, 6), (6, 3)})

# ---------- store ----------
with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "store.json"
    s = PlacementStore(path)
    s.add_literature("cyclic", "Cyclic intervals", source="reference paper")
    s.record(scheme_hash="h1", family_id="cyclic", K=8, r=6, removed=8, status="accept", metrics=m)
    s.record(scheme_hash="h1", family_id="cyclic", K=6, r=3, removed=6, status="reject", reason="dominated")
    s.save()

    s2 = PlacementStore(path)  # reload from disk
    check("store: persists results", len(s2.results()) == 2)
    check("store: seen is regime-aware", s2.seen("h1", K=8, r=6) and not s2.seen("h1", K=10, r=5))
    check("store: accepted filter", len(s2.accepted()) == 1)
    check("store: literature persisted", len(s2.families()) == 1)
    check("store: dedup literature", s2.add_literature("cyclic", "dup") is False)

# ---------- generator across regimes ----------
res = run_generator(ROOT / "generators" / "cyclic.py", [(6, 3), (8, 6), (7, 4), (10, 5)])
check("generator: valid across all regimes", res["ok"], str([i for i in res["instances"] if not i.get("ok", True)]))
check("generator: K=8 instance matches Fixture A unit/size",
      any(i["K"] == 8 and i["placement"]["unit"] == 14 and i["target"]["segments"][0]["size"] == 16
          for i in res["instances"]))
# rejects unsupported regimes gracefully
res_bad = run_generator(ROOT / "generators" / "cyclic.py", [(4, 6)])  # r > K-1
check("generator: rejects unsupported regime", res_bad["instances"][0]["supported"] is False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
