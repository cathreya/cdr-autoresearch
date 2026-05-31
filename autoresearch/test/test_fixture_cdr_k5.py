#!/usr/bin/env python3
"""Validate the arXiv:2001.04939 Example 1 fixture (K=5, r=3, node 5 removed) against
the oracle, and check its metrics match the paper (coded load 1/2 of baseline).

Run: python3 test/test_fixture_cdr_k5.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

from verifier import validate_placement, verify_plan, verify_repair  # noqa: E402
from metrics import compute_metrics  # noqa: E402
from fixture_cdr_k5 import build  # noqa: E402

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


fx = build()
initial, target, plan, repair = fx["initial"], fx["target"], fx["plan"], fx["repair"]

# structure sanity
check("20 initial subfiles (P(5,2))", len(initial["segments"]) == 20, str(len(initial["segments"])))
check("4 target subfiles (P(4,1))", len(target["segments"]) == 4)

# oracle
pv = validate_placement(initial)
check("initial placement valid (r=3, balanced)", pv["ok"], str(pv["errors"]))
tv = validate_placement(target)
check("target placement valid (r=3, balanced)", tv["ok"], str(tv["errors"]))
plv = verify_plan(plan, initial, target)
check("plan valid (conservation + dest rule B=S~_j\\S_i)", plv["ok"], "; ".join(plv["errors"][:4]))
rv = verify_repair(repair, plan, initial, fx["baseline"])
check("repair decodes + covers all obligations", rv["ok"], "; ".join(rv["errors"][:4]))

# metrics — must match the paper
m = compute_metrics(initial, target, plan, repair)
check("scheme fully valid", m["valid"], "; ".join(m["errors"][:4]))
check("baseline 24 (12 subfiles)", m["baseline"] == 24, f"got {m['baseline']}")
check("coded load 12 (6 subfiles)", m["comm_load"] == 12, f"got {m['comm_load']}")
check("communication load = 1/2 (paper)", m["load_fraction"] == 0.5, f"got {m['load_fraction']}")
check("coding gain = 2x", rv["gain"] == 2.0, f"got {rv['gain']}")
check("12 broadcasts (3 per group x 4 groups)", len(repair["broadcasts"]) == 12)
check("io_reads 24 (all XORs are pairs)", m["io_reads"] == 24, f"got {m['io_reads']}")
check("subpacketization N=20 (P(5,2) subfiles, factorial)", m["subpacketization"] == 20, f"got {m['subpacketization']}")
check("split_factor 2 (subfiles halved)", m["split_factor"] == 2, f"got {m['split_factor']}")

# Cross-family tradeoff: at the SAME (K,r)=(5,3) the cyclic family uses N=K=5 subfiles,
# vs the ordered-subset scheme's N=20 — the load-vs-subpacketization tradeoff the Judge sees.
from generator import run_generator  # noqa: E402
cyc = run_generator(ROOT / "generators" / "cyclic.py", [(5, 3)])
cyc_pl = cyc["instances"][0]["placement"]
check("cyclic K=5 uses N=K=5 subfiles (vs ordered-subset's 20)",
      len(cyc_pl["segments"]) == 5, f"got {len(cyc_pl['segments'])}")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
