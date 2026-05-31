"""The Placement Store — persistent shared memory for the research loop.

Two collections, backed by one JSON file:

  - literature : design families the Lit Review agent has surfaced.
  - results    : one record per (family, K, r) scheme that has been evaluated, with its
                 status (done / reject / accept), metrics, and (for rejects) a reason.

Schemes are keyed by `canonical_hash` (from verifier.py), which is relabeling-invariant,
so the Judge never re-explores a scheme — or a node-relabeling of it — it has seen.
Results are per regime: the same family appears once per (K, r) it was tried in.
"""

import json
from pathlib import Path

STATUSES = ("done", "reject", "accept")


class PlacementStore:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {"literature": [], "results": []}

    # ---- literature ----
    def add_literature(self, family_id, name, source=None, notes=None):
        if any(f["family_id"] == family_id for f in self.data["literature"]):
            return False
        self.data["literature"].append(
            {"family_id": family_id, "name": name, "source": source, "notes": notes}
        )
        return True

    def families(self):
        return list(self.data["literature"])

    # ---- results ----
    def seen(self, scheme_hash, K=None, r=None):
        for rec in self.data["results"]:
            if rec["hash"] != scheme_hash:
                continue
            if (K is None or rec["K"] == K) and (r is None or rec["r"] == r):
                return True
        return False

    def record(self, *, scheme_hash, family_id, K, r, removed, status, metrics=None, reason=None):
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
        self.data["results"].append(
            {
                "hash": scheme_hash,
                "family_id": family_id,
                "K": K,
                "r": r,
                "removed": removed,
                "status": status,
                "metrics": metrics,
                "reason": reason,
            }
        )

    def results(self, status=None, family_id=None, K=None, r=None):
        out = []
        for rec in self.data["results"]:
            if status is not None and rec["status"] != status:
                continue
            if family_id is not None and rec["family_id"] != family_id:
                continue
            if K is not None and rec["K"] != K:
                continue
            if r is not None and rec["r"] != r:
                continue
            out.append(rec)
        return out

    def accepted(self):
        return self.results(status="accept")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2) + "\n")
