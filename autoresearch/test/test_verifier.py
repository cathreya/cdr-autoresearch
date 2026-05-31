#!/usr/bin/env python3
"""Test vectors for the verifier oracle.

  - Regression Fixture A (K=8, r=6, removed=8) must validate end to end.
  - A hand-built coded XOR broadcast must decode.
  - Negative cases (broken replication, conservation, dest rule, double-consume,
    orphan, decodability) MUST be rejected. If the oracle ever passes these, it is
    worthless.

Run: python3 test/test_verifier.py
"""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from verifier import validate_placement, verify_plan, verify_repair, canonical_hash  # noqa: E402

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


def mod1(x, n):
    return ((x - 1) % n + n) % n + 1


def cyc(s, n, r):
    return sorted(mod1(s + t, n) for t in range(r))


# ---------- Fixture A: K=8, r=6, removed=8, unit T=14 ----------
K, r, unit, removed = 8, 6, 14, 8
initial = {
    "kind": "placement", "nodes": K, "r": r, "unit": unit,
    "segments": [{"id": i + 1, "size": unit, "storage": cyc(i + 1, K, r)} for i in range(K)],
}
target_size = (unit * K) // (K - 1)  # file/(K-1) = 16, with N=K (cyclic fixture)
target = {
    "kind": "placement", "nodes": K - 1, "r": r, "unit": unit,
    "segments": [{"id": i + 1, "size": target_size, "storage": cyc(i + 1, K - 1, r)} for i in range(K - 1)],
}

check("initial placement valid", validate_placement(initial)["ok"], str(validate_placement(initial)["errors"]))
check("target placement valid", validate_placement(target)["ok"], str(validate_placement(target)["errors"]))
check("target segment size is 16", target_size == 16)


def P(pid, source, dest, size):
    return {"id": pid, "source": source, "dest": dest, "size": size}


plan = {
    "kind": "plan", "removed": removed,
    "pieces": [
        P("W1", 1, [], 14), P("W2", 2, [], 14),
        P("W3_1", 3, [1], 12), P("W3_2", 3, [2], 2),
        P("W4_2", 4, [2], 10), P("W4_3", 4, [3], 4),
        P("W5_3", 5, [3], 8), P("W5_4", 5, [4], 6),
        P("W6_4", 6, [4], 6), P("W6_5", 6, [5], 8),
        P("W7_5", 7, [5], 4), P("W7_6", 7, [6], 10),
        P("W8_6", 8, [6], 2), P("W8_7", 8, [7], 12),
    ],
    "merges": [
        {"target": 1, "parts": ["W1", "W8_6"]},
        {"target": 2, "parts": ["W2", "W3_2"]},
        {"target": 3, "parts": ["W3_1", "W4_3"]},
        {"target": 4, "parts": ["W4_2", "W5_4"]},
        {"target": 5, "parts": ["W5_3", "W6_5"]},
        {"target": 6, "parts": ["W6_4", "W7_6"]},
        {"target": 7, "parts": ["W7_5", "W8_7"]},
    ],
}
plan_res = verify_plan(plan, initial, target)
check("fixture A plan valid (conservation + dest rule)", plan_res["ok"], str(plan_res["errors"]))
check("uncoded load == baseline 84", plan_res["uncodedLoad"] == 84, f"got {plan_res['uncodedLoad']}")

# ---------- valid coded broadcast: XOR W3_1 and W8_7 ----------
moving = [p for p in plan["pieces"] if len(p["dest"]) > 0]
baseline = 84
coded = {
    "kind": "repair",
    "broadcasts": [{"by": 3, "terms": ["W3_1", "W8_7"]}] + [
        {"by": next(n for n in initial["segments"][p["source"] - 1]["storage"] if n != removed),
         "terms": [p["id"]]}
        for p in moving if p["id"] not in ("W3_1", "W8_7")
    ],
}
coded_res = verify_repair(coded, plan, initial, baseline)
check("coded repair decodes + covers all obligations", coded_res["ok"], str(coded_res["errors"]))
check("coded load (72) beats baseline (84)", coded_res["codedLoad"] == 72, f"got {coded_res['codedLoad']}")
check("coding gain > 1", coded_res["gain"] > 1, f"gain {coded_res['gain']}")

# ---------- NEGATIVE: these MUST be rejected ----------
bad_repl = copy.deepcopy(initial)
bad_repl["segments"][0]["storage"] = [1, 2, 3, 4, 5]  # r=5 != 6
check("rejects wrong replication", not validate_placement(bad_repl)["ok"])

bad_balance = copy.deepcopy(initial)
bad_balance["segments"][0]["size"] = 13  # breaks equal node load
check("rejects unbalanced load", not validate_placement(bad_balance)["ok"])

bad_conserv = copy.deepcopy(plan)
next(p for p in bad_conserv["pieces"] if p["id"] == "W3_1")["size"] = 11  # source 3 no longer sums to 14
check("rejects broken size conservation", not verify_plan(bad_conserv, initial, target)["ok"])

bad_dest = copy.deepcopy(plan)
next(p for p in bad_dest["pieces"] if p["id"] == "W3_1")["dest"] = [2]  # should be [1]
check("rejects wrong destination set", not verify_plan(bad_dest, initial, target)["ok"])

# redundant bits: a subsegment merged into more than one target
double_use = copy.deepcopy(plan)
next(m for m in double_use["merges"] if m["target"] == 2)["parts"].append("W3_1")  # already in target 3
dbl = verify_plan(double_use, initial, target)
check("rejects subsegment merged into >1 target (redundant bits)",
      not dbl["ok"] and any("W3_1" in e and "merges" in e for e in dbl["errors"]), "; ".join(dbl["errors"]))

# dropped bits: a subsegment consumed by no merge
orphan = copy.deepcopy(plan)
orphan["merges"] = [m for m in orphan["merges"] if m["target"] != 7]  # W7_5, W8_7 now consumed by nothing
orp = verify_plan(orphan, initial, target)
check("rejects orphaned subsegment (dropped bits)",
      not orp["ok"] and any("never consumed" in e for e in orp["errors"]), "; ".join(orp["errors"]))

# decodability negative on a sparse synthetic instance
synth_init = {
    "kind": "placement", "nodes": 4, "r": 2, "unit": 1,
    "segments": [{"id": 1, "size": 1, "storage": [1, 2]}, {"id": 2, "size": 1, "storage": [2, 3]}],
}
synth_plan = {"kind": "plan", "removed": 99, "pieces": [P("P", 1, [3], 1), P("Q", 2, [4], 1)], "merges": []}
# node 4 receives Q but does not store seg 1 -> cannot peel P -> undecodable
bad_decode = {"kind": "repair", "broadcasts": [{"by": 2, "terms": ["P", "Q"]}]}
check("rejects undecodable XOR (receiver lacks side info)",
      not verify_repair(bad_decode, synth_plan, synth_init, None)["ok"])

bad_transmit = {"kind": "repair", "broadcasts": [{"by": 1, "terms": ["W3_1"]}]}  # node 1 doesn't store seg 3
check("rejects transmitter that lacks the piece", not verify_repair(bad_transmit, plan, initial, baseline)["ok"])

missing_delivery = {"kind": "repair", "broadcasts": []}  # delivers nothing
check("rejects scheme that leaves obligations unmet",
      not verify_repair(missing_delivery, plan, initial, baseline)["ok"])

# ---------- canonical hash: rotation-invariant ----------
cyc6a = {"kind": "placement", "nodes": 6, "r": 3, "unit": 1,
         "segments": [{"id": i + 1, "size": 1, "storage": cyc(i + 1, 6, 3)} for i in range(6)]}
cyc6rot = {"kind": "placement", "nodes": 6, "r": 3, "unit": 1,
           "segments": [{"id": s["id"], "size": 1, "storage": sorted(mod1(n + 1, 6) for n in s["storage"])}
                        for s in cyc6a["segments"]]}
check("canonical hash is rotation-invariant", canonical_hash(cyc6a) == canonical_hash(cyc6rot))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
