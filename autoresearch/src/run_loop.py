#!/usr/bin/env python3
"""Run the autonomous research loop against codex agents.

    python3 src/run_loop.py --regimes "8,6,8"
    python3 src/run_loop.py --regimes "8,6,8;5,3,5" --store runs/codex/store.json

Each regime is K,r,removed. The CodexProposer drives the agents; every scheme is gated by
the oracle before it can enter a per-regime Pareto frontier. If codex isn't available the
proposer yields no candidate and the regime is logged as 'no proposal' (the loop is safe
either way). Results persist to the store.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codex_proposer import CodexProposer  # noqa: E402
from loop import run_loop  # noqa: E402
from store import PlacementStore  # noqa: E402


def parse_regimes(s):
    out = []
    for group in s.split(";"):
        parts = [int(x) for x in group.split(",")]
        K, r = parts[0], parts[1]
        removed = parts[2] if len(parts) > 2 else K
        out.append((K, r, removed))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description="Run the CDR autoresearch loop via codex")
    ap.add_argument("--regimes", default="8,6,8", help='"K,r,removed;K,r,removed;..."')
    ap.add_argument("--store", default="runs/codex/store.json")
    ap.add_argument("--model", default=None, help="codex model override")
    args = ap.parse_args(argv)

    regimes = parse_regimes(args.regimes)
    store = PlacementStore(args.store)
    proposer = CodexProposer(model=args.model)

    summary = run_loop(proposer, regimes, store)
    store.save()

    print(json.dumps(summary, indent=2))
    print(f"\naccepted {summary['accepted']} · rejected {summary['rejected']} · store → {args.store}")


if __name__ == "__main__":
    main(sys.argv[1:])
