"""Verifier: the oracle for coded data-rebalancing artifacts.

Agents may be arbitrarily creative in HOW they produce placements, plans, and
repair schemes. These functions decide, deterministically, whether an artifact
satisfies the non-negotiable balanced-condition invariants and whether a coded
broadcast actually decodes. No claim from an agent is trusted; everything is
recomputed from the artifact itself.

All sizes are integers in a shared ``unit`` (e.g. unit=14 means sizes are in T/14).
Node and segment ids are 1-based to match the cyclic placement model.

Artifacts are plain dicts (parsed from JSON). A result is a dict
``{"ok": bool, "errors": list[str], ...metrics}``.
"""

from __future__ import annotations

import hashlib
from itertools import permutations


# ---------- small set helpers (lists of distinct node ids) ----------

def _uniq_sorted(xs):
    return sorted(set(xs))


def _set_eq(a, b):
    return _uniq_sorted(a) == _uniq_sorted(b)


def _diff(a, b):
    """Elements of a not in b, deduped and sorted."""
    bs = set(b)
    return _uniq_sorted(x for x in a if x not in bs)


def _fail(errors, **extra):
    return {"ok": False, "errors": errors, **extra}


def _ok(**extra):
    return {"ok": True, "errors": [], **extra}


# ---------- 1. Placement validity ----------

def validate_placement(placement):
    """A placement is valid iff every segment is stored on exactly r distinct,
    in-range nodes, and the database is balanced: every node carries identical
    total size, equal to r * fileSize / nodes.
    """
    errors = []
    nodes = placement.get("nodes")
    r = placement.get("r")
    segments = placement.get("segments")

    if not isinstance(nodes, int) or nodes < 1:
        return _fail([f"nodes must be a positive integer (got {nodes})"])
    if not isinstance(r, int) or r < 1:
        errors.append(f"r must be a positive integer (got {r})")
    if not isinstance(segments, list) or not segments:
        errors.append("segments must be a non-empty list")
        return _fail(errors)

    seen = set()
    file_size = 0
    load = {n: 0 for n in range(1, nodes + 1)}

    for seg in segments:
        sid = seg.get("id")
        size = seg.get("size")
        storage = seg.get("storage") or []
        if sid in seen:
            errors.append(f"duplicate segment id {sid}")
        seen.add(sid)
        if not isinstance(size, int) or size <= 0:
            errors.append(f"segment {sid}: size must be a positive integer (got {size})")
        st = _uniq_sorted(storage)
        if len(st) != len(storage):
            errors.append(f"segment {sid}: storage has duplicate nodes")
        if len(st) != r:
            errors.append(f"segment {sid}: replication {len(st)} != r={r}")
        for n in st:
            if not isinstance(n, int) or n < 1 or n > nodes:
                errors.append(f"segment {sid}: node {n} out of range 1..{nodes}")
            else:
                load[n] += size or 0
        file_size += size or 0

    # Balance: r * fileSize must divide evenly across nodes, and every node must hit it.
    expected_num = r * file_size
    if expected_num % nodes != 0:
        errors.append(f"balance impossible: r*fileSize={expected_num} not divisible by nodes={nodes}")
    else:
        expected = expected_num // nodes
        for n in range(1, nodes + 1):
            if load[n] != expected:
                errors.append(f"node {n} load {load[n]} != expected balanced load {expected}")

    if errors:
        return _fail(errors, nodeLoads=load, fileSize=file_size)
    return _ok(nodeLoads=load, fileSize=file_size, N=len(segments))


def _seg_map(placement):
    return {s["id"]: s for s in placement["segments"]}


# ---------- 2. Split/merge plan validity ----------

def verify_plan(plan, initial_placement, target_placement):
    """Connects an initial placement (with `removed` node gone) to a target
    placement. Invariants:
      - per source: piece sizes sum to that source segment's size (data conserved);
      - per target: part sizes sum to that target segment's size (target balanced);
      - every piece is consumed by exactly one merge (no redundant / dropped bits);
      - destination rule: a piece carved from source i and merged into target j must
        have dest B == S~_j \\ S_i (the target nodes that don't already hold it).
    """
    errors = []
    init = _seg_map(initial_placement)
    tgt = _seg_map(target_placement)
    pieces = plan.get("pieces") or []
    merges = plan.get("merges") or []

    # index pieces
    piece_by_id = {}
    for p in pieces:
        pid = p.get("id")
        if pid in piece_by_id:
            errors.append(f"duplicate piece id {pid}")
        piece_by_id[pid] = p
        if p.get("source") not in init:
            errors.append(f"piece {pid}: source segment {p.get('source')} not in initial placement")
        if not isinstance(p.get("size"), int) or p.get("size", 0) <= 0:
            errors.append(f"piece {pid}: size must be a positive integer")
        if not isinstance(p.get("dest"), list):
            errors.append(f"piece {pid}: dest must be a list")

    # per-source conservation
    by_source = {}
    for p in pieces:
        by_source[p["source"]] = by_source.get(p["source"], 0) + (p.get("size") or 0)
    for sid, seg in init.items():
        got = by_source.get(sid, 0)
        if got != seg["size"]:
            errors.append(f"source {sid}: pieces sum to {got} but segment size is {seg['size']}")

    # every piece consumed exactly once; per-target conservation + destination rule
    consumed = {}
    target_total = {}
    for m in merges:
        tseg = tgt.get(m.get("target"))
        if tseg is None:
            errors.append(f"merge: target {m.get('target')} not in target placement")
            continue
        total = 0
        for ref in m.get("parts") or []:
            p = piece_by_id.get(ref)
            if p is None:
                errors.append(f"merge target {m['target']}: unknown piece {ref}")
                continue
            consumed[ref] = consumed.get(ref, 0) + 1
            total += p.get("size") or 0
            # destination rule: B == S~_j \ S_i
            si = init.get(p["source"], {}).get("storage", [])
            expected_dest = _diff(tseg["storage"], si)
            if not _set_eq(p.get("dest") or [], expected_dest):
                errors.append(
                    f"piece {ref} into target {m['target']}: dest "
                    f"{_uniq_sorted(p.get('dest') or [])} != "
                    f"S~_{m['target']}\\S_{p['source']}={expected_dest}"
                )
        target_total[m["target"]] = total
    for tid, seg in tgt.items():
        got = target_total.get(tid, 0)
        if got != seg["size"]:
            errors.append(f"target {tid}: parts sum to {got} but target size is {seg['size']}")
    for p in pieces:
        c = consumed.get(p["id"], 0)
        if c == 0:
            errors.append(f"piece {p['id']} is never consumed by a merge")
        if c > 1:
            errors.append(f"piece {p['id']} consumed by {c} merges (must be exactly 1)")

    # uncoded broadcast load = sum of sizes of pieces that actually move (nonempty dest).
    # On a broadcast bus one transmission reaches all destinations at once, so a moving
    # piece costs just its size.
    uncoded_load = sum(p.get("size") or 0 for p in pieces if len(_uniq_sorted(p.get("dest") or [])) > 0)

    if errors:
        return _fail(errors, uncodedLoad=uncoded_load)
    return _ok(uncodedLoad=uncoded_load)


# ---------- 3. Repair scheme (coded broadcast) decodability ----------

def verify_repair(repair, plan, initial_placement, baseline=None):
    """A broadcast is a node XORing several plan pieces into one transmission of
    size max(term sizes) (zero-padded). It is valid only if:
      - the transmitting node stores every term it XORs (and is not the removed node);
      - for every term, every receiver (a node in that term's dest) already stores
        all the OTHER terms in the same broadcast, so it can peel them off.
    The scheme must also DELIVER every (piece, destination-node) obligation.
    """
    errors = []
    init = _seg_map(initial_placement)
    removed = plan.get("removed")
    piece_by_id = {p["id"]: p for p in (plan.get("pieces") or [])}

    def stores(n, p):
        return n in (init.get(p["source"], {}).get("storage") or [])

    coded_load = 0
    delivered = set()  # (piece_id, node)

    for bi, b in enumerate(repair.get("broadcasts") or []):
        terms = [piece_by_id.get(ref) for ref in (b.get("terms") or [])]
        if any(t is None for t in terms):
            errors.append(f"broadcast #{bi}: references unknown piece")
            continue
        if not terms:
            errors.append(f"broadcast #{bi}: no terms")
            continue

        by = b.get("by")
        if by == removed:
            errors.append(f"broadcast #{bi}: transmitter {by} is the removed node")
        for t in terms:
            if not stores(by, t):
                errors.append(
                    f"broadcast #{bi}: transmitter {by} does not store piece {t['id']} "
                    f"(source {t['source']} on {init.get(t['source'], {}).get('storage')})"
                )

        size = max(t.get("size") or 0 for t in terms)
        if b.get("size") is not None and b["size"] != size:
            errors.append(f"broadcast #{bi}: declared size {b['size']} != computed {size}")
        coded_load += size

        for t in terms:
            receivers = [n for n in _uniq_sorted(t.get("dest") or []) if n != removed]
            for rcv in receivers:
                for other in terms:
                    if other["id"] == t["id"]:
                        continue
                    if not stores(rcv, other):
                        errors.append(
                            f"broadcast #{bi}: receiver {rcv} of piece {t['id']} "
                            f"cannot decode — lacks side-info piece {other['id']}"
                        )
                delivered.add((t["id"], rcv))

    # coverage: every (piece, destNode) obligation in the plan must be delivered
    for p in (plan.get("pieces") or []):
        for n in _uniq_sorted(p.get("dest") or []):
            if n == removed:
                continue
            if (p["id"], n) not in delivered:
                errors.append(f"obligation not met: piece {p['id']} never delivered to node {n}")

    gain = (baseline / coded_load) if (baseline is not None and coded_load > 0) else None
    if errors:
        return _fail(errors, codedLoad=coded_load, baseline=baseline, gain=gain)
    return _ok(codedLoad=coded_load, baseline=baseline, gain=gain)


# ---------- 4. Canonical hash (node-relabeling invariant for small node counts) ----------

def canonical_hash(placement):
    """Two placements identical up to renaming nodes get the same hash, so the
    research loop can dedup schemes it has already explored. Segment ids are ignored
    (arbitrary labels); only the multiset of (size, storage-set) matters.
    """
    nodes = placement["nodes"]
    segments = placement["segments"]

    def key(perm):  # perm: dict old_node -> new_node
        rows = sorted(
            f"{s['size']}:" + ",".join(str(x) for x in _uniq_sorted(perm[n] for n in s["storage"]))
            for s in segments
        )
        return "|".join(rows)

    if nodes <= 9:
        ids = list(range(1, nodes + 1))
        best = None
        for perm_tuple in permutations(ids):
            perm = {ids[i]: perm_tuple[i] for i in range(nodes)}
            k = key(perm)
            if best is None or k < best:
                best = k
    else:
        # too many nodes to brute-force; fall back to identity (NOT relabel-invariant)
        best = "NONCANON:" + key({n: n for n in range(1, nodes + 1)})

    return hashlib.sha1(best.encode()).hexdigest()[:16]


# ---------- top-level dispatch for the CLI / gate ----------

def verify_artifact(kind, payload):
    if kind == "placement":
        return validate_placement(payload)
    if kind == "plan":
        return verify_plan(payload["plan"], payload["initial"], payload["target"])
    if kind == "repair":
        return verify_repair(payload["repair"], payload["plan"], payload["initial"], payload.get("baseline"))
    return _fail([f"unknown artifact kind '{kind}'"])
