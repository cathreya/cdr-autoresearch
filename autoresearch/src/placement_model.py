"""Cyclic baseline placement model — the reference / regression seed (N = K).

This is one canonical balanced database, used as a fixture and a starting point.
It is NOT the only allowed segmentation: N is a free design parameter (see
docs/problem_context.md). Agents are free to ignore this shape entirely.
"""

import json
from pathlib import Path


def mod1(x, n):
    """1-based modulo: maps into 1..n."""
    return ((x - 1) % n + n) % n + 1


def cyclic_set(start, n, r):
    return sorted(mod1(start + t, n) for t in range(r))


def initial_database(K, r):
    return [{"segment": i + 1, "storage": cyclic_set(i + 1, K, r)} for i in range(K)]


def target_database(K, r, removed=None):
    if removed is None:
        removed = K
    canonical = [{"target": i + 1, "storage": cyclic_set(i + 1, K - 1, r)} for i in range(K - 1)]
    if removed == K:
        return canonical
    shift = removed
    rows = [
        {
            "target": mod1(row["target"] + shift, K),
            "storage": sorted(mod1(n + shift, K) for n in row["storage"]),
        }
        for row in canonical
    ]
    return sorted(rows, key=lambda r_: r_["target"])


def removed_segments(K, r, removed=None):
    if removed is None:
        removed = K
    return [mod1(removed - r + 1 + t, K) for t in range(r)]


def overlap_rows(K, r, removed=None):
    if removed is None:
        removed = K
    initial = initial_database(K, r)
    targets = target_database(K, r, removed)
    lost = set(removed_segments(K, r, removed))
    rows = []
    for source in initial:
        if source["segment"] not in lost:
            continue
        for tgt in targets:
            overlap = [n for n in source["storage"] if n in tgt["storage"]]
            missing = [n for n in tgt["storage"] if n not in source["storage"]]
            rows.append(
                {
                    "source": source["segment"],
                    "target": tgt["target"],
                    "oldStorage": source["storage"],
                    "targetStorage": tgt["storage"],
                    "overlap": overlap,
                    "overlapCount": len(overlap),
                    "missingDestinations": missing,
                }
            )
    return rows


def seed_model(K=8, r=6, removed=None):
    if removed is None:
        removed = K
    return {
        "parameters": {"K": K, "r": r, "removed": removed},
        "units": "T/(2(K-1))",
        "initialDatabase": initial_database(K, r),
        "targetDatabase": target_database(K, r, removed),
        "removedSegments": removed_segments(K, r, removed),
        "overlapRows": overlap_rows(K, r, removed),
    }


def write_seed_model(out_dir, K, r, removed):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    model = seed_model(K, r, removed)
    file = Path(out_dir) / "seed_model.json"
    with open(file, "w") as f:
        json.dump(model, f, indent=2)
        f.write("\n")
    return file, model


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--r", type=int, default=6)
    ap.add_argument("--removed", type=int, default=None)
    a = ap.parse_args()
    print(json.dumps(seed_model(a.k, a.r, a.removed if a.removed is not None else a.k), indent=2))
