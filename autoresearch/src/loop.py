"""The autonomous research loop: Judge + per-regime Pareto control.

A *proposer* yields candidate schemes for a regime (K, r, removed). Each candidate is
GATED by the oracle (compute_metrics re-runs the full verifier); only fully-valid schemes
are scored. The *Judge* keeps the per-regime Pareto-non-dominated set over the chosen axes
(all minimized); everything else is recorded as rejected — invalid, or dominated. Results
land in the PlacementStore, keyed by a relabeling-invariant hash so a family is never
re-explored.

A proposer is any object with `.propose(regime) -> list[candidate]`, where a candidate is
`{"label": str, "family": str, "scheme": {initial, target, plan, repair}}`. The
deterministic proposer used in tests replays verified schemes; the live one drives Codex.

NOTE: regime selection here is a fixed sweep over the provided list — the Judge's job is
frontier maintenance. Steering (choosing regimes that could extend the frontier) plugs in
once the proposer is generative; see `Judge.suggest_regimes`.
"""

from metrics import compute_metrics
from pareto import ParetoFront
from verifier import canonical_hash

AXES = ["comm_load", "io_reads", "subpacketization"]


def uncoded_repair(plan, initial):
    """Baseline repair: broadcast each moving subsegment uncoded (one transmission each).
    Always valid — a useful Pareto reference point against the coded scheme."""
    removed = plan["removed"]
    seg = {s["id"]: s for s in initial["segments"]}
    broadcasts = []
    for p in plan["pieces"]:
        if not p.get("dest"):
            continue
        by = next(n for n in seg[p["source"]]["storage"] if n != removed)
        broadcasts.append({"by": by, "terms": [p["id"]]})
    return {"kind": "repair", "broadcasts": broadcasts}


class Judge:
    """Maintains the Pareto-non-dominated set over `axes` (all minimized)."""

    def __init__(self, axes=AXES):
        self.axes = list(axes)

    def select(self, points):
        """Return the set of point ids that lie on the non-dominated frontier."""
        front = ParetoFront(self.axes)
        for p in points:
            front.add(p)
        return {p["id"] for p in front.front()}

    def suggest_regimes(self, history):
        """Placeholder for frontier-driven steering with a generative proposer.
        Today the loop sweeps a fixed regime list; this is where a generative proposer
        would be told which (K, r) to attack next to extend the frontier."""
        raise NotImplementedError


def _metrics(scheme):
    return compute_metrics(scheme["initial"], scheme["target"], scheme["plan"], scheme["repair"])


def run_loop(proposer, regimes, store, axes=AXES, judge=None):
    """Explore each regime: propose → gate → score → Judge selects frontier → record.

    `regimes` is a list of (K, r, removed). Returns a summary dict and mutates `store`.
    """
    judge = judge or Judge(axes)
    summary = {"regimes": [], "accepted": 0, "rejected": 0}

    for (K, r, removed) in regimes:
        cands = proposer.propose((K, r, removed))
        rec = {"regime": {"K": K, "r": r, "removed": removed},
               "proposed": len(cands), "frontier": [], "rejected": []}

        if not cands:
            rec["note"] = "no proposal"
            summary["regimes"].append(rec)
            continue

        fam_hash = canonical_hash(cands[0]["scheme"]["initial"])
        if store.seen(fam_hash, K, r):
            rec["note"] = "already explored (skipped)"
            summary["regimes"].append(rec)
            continue

        # gate: only fully-valid schemes are scored
        valid = []
        for c in cands:
            m = _metrics(c["scheme"])
            if m["valid"]:
                valid.append((c, m))
            else:
                store.record(scheme_hash=fam_hash, family_id=c["family"], K=K, r=r, removed=removed,
                             status="reject", metrics=m,
                             reason="invalid: " + "; ".join(m["errors"][:2]))
                rec["rejected"].append({"label": c["label"], "reason": "invalid"})
                summary["rejected"] += 1

        # Judge keeps the non-dominated set
        points = [dict(id=c["label"], **{a: m[a] for a in axes}) for c, m in valid]
        front_ids = judge.select(points)

        for c, m in valid:
            on_front = c["label"] in front_ids
            store.record(scheme_hash=fam_hash, family_id=c["family"], K=K, r=r, removed=removed,
                         status="accept" if on_front else "reject",
                         metrics=m, reason=None if on_front else "dominated")
            entry = {"label": c["label"], "family": c["family"],
                     **{a: m[a] for a in axes}, "load_fraction": round(m["load_fraction"], 3)}
            if on_front:
                rec["frontier"].append(entry)
                summary["accepted"] += 1
            else:
                rec["rejected"].append({"label": c["label"], "reason": "dominated"})
                summary["rejected"] += 1

        summary["regimes"].append(rec)

    return summary
