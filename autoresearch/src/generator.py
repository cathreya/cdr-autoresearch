"""Load and run an agent-written placement generator, verifying its instances.

This realizes "a Python script that generates a scheme JSON for given parameters, or
rejects": a single generator covers a whole (K, r) regime, and we verify it by running
it across a grid and validating each concrete instance with the oracle.

A generator is a Python module exposing:
    supports(K, r) -> bool                      # does this family cover this regime?
    placement(K, r) -> placement dict           # initial balanced placement on K nodes
    target(K, r, removed=None) -> placement dict # balanced target on K-1 nodes (removed defaults to K)

SECURITY: this executes agent-written Python in-process. In the loop each generator runs
inside its iteration's git worktree; sandbox it further before trusting untrusted code.
"""

import importlib.util
from pathlib import Path

from verifier import validate_placement


def load_generator(path):
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"generator_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_generator(path, grid):
    """grid: list of (K, r) or (K, r, removed). Returns per-instance verification
    plus the concrete placements (so the caller can feed them downstream).
    """
    mod = load_generator(path)
    instances = []
    for spec in grid:
        K, r = spec[0], spec[1]
        removed = spec[2] if len(spec) > 2 else K

        if hasattr(mod, "supports") and not mod.supports(K, r):
            instances.append({"K": K, "r": r, "removed": removed, "supported": False})
            continue

        rec = {"K": K, "r": r, "removed": removed, "supported": True}
        try:
            placement = mod.placement(K, r)
            pv = validate_placement(placement)
            rec["placement_ok"] = pv["ok"]
            rec["placement_errors"] = pv["errors"]
            rec["placement"] = placement
        except Exception as e:  # noqa: BLE001 — a raising generator is just an invalid one
            rec["placement_ok"] = False
            rec["placement_errors"] = [f"raised: {e}"]
        try:
            target = mod.target(K, r, removed)
            tv = validate_placement(target)
            rec["target_ok"] = tv["ok"]
            rec["target_errors"] = tv["errors"]
            rec["target"] = target
        except Exception as e:  # noqa: BLE001
            rec["target_ok"] = False
            rec["target_errors"] = [f"raised: {e}"]

        rec["ok"] = bool(rec.get("placement_ok") and rec.get("target_ok"))
        instances.append(rec)

    supported = [i for i in instances if i.get("supported")]
    ok = bool(supported) and all(i["ok"] for i in supported)
    return {"ok": ok, "instances": instances}
