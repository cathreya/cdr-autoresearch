"""Metrics for a verified (initial, target, plan, repair) scheme — the Pareto axes
the Judge optimizes. All axes are MINIMIZED:

  - comm_load        coded broadcast units (verify_repair.codedLoad)
  - io_reads         reads to form the broadcasts (sum of XOR term counts)
  - subpacketization number of file pieces N (segments); proxy for metadata complexity.
                     This is the axis where families diverge: ordered-subset placement has
                     N = P(K, K-r) (factorial), cyclic has N = K (linear). `split_factor`
                     (the placement `unit`) is reported secondarily.

Metrics are only trustworthy on a fully-valid scheme, so this re-runs the whole oracle
(placement + target + plan + repair) and reports `valid`. Metrics are per regime (K, r):
a scheme can win in one regime and lose in another, so the caller keys results by (K, r).
"""

from verifier import validate_placement, verify_plan, verify_repair


def baseline_load(placement):
    """The Nr/K naive load: the size of the removed node."""
    file_size = sum(s["size"] for s in placement["segments"])
    num = placement["r"] * file_size
    nodes = placement["nodes"]
    return num // nodes if num % nodes == 0 else num / nodes


def compute_metrics(initial, target, plan, repair):
    pv = validate_placement(initial)
    tv = validate_placement(target)
    plv = verify_plan(plan, initial, target)
    baseline = baseline_load(initial)
    rv = verify_repair(repair, plan, initial, baseline)

    valid = pv["ok"] and tv["ok"] and plv["ok"] and rv["ok"]
    errors = pv["errors"] + tv["errors"] + plv["errors"] + rv["errors"]

    io_reads = sum(len(b.get("terms") or []) for b in repair.get("broadcasts") or [])
    comm_load = rv.get("codedLoad")

    return {
        "valid": valid,
        "errors": errors,
        "comm_load": comm_load,
        "baseline": baseline,
        "load_fraction": (comm_load / baseline) if (baseline and comm_load is not None) else None,
        "io_reads": io_reads,
        "subpacketization": len(initial.get("segments") or []),  # N: number of file pieces
        "split_factor": initial.get("unit"),                     # secondary: within-segment split
        "num_pieces": len(plan.get("pieces") or []),
    }
