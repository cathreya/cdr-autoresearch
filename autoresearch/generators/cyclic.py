"""Reference placement generator: cyclic intervals (the paper's canonical family).

Conforms to the generator contract in src/generator.py. Self-contained on purpose —
agent-written generators should not depend on internal modules. Uses unit = 2(K-1) so
the initial segment is 2(K-1) chunks and the post-removal target segment is 2K chunks
(= file/(K-1)); for K=8 this reproduces Fixture A exactly (unit 14, target size 16).
"""


def supports(K, r):
    return isinstance(K, int) and isinstance(r, int) and 3 <= r <= K - 1


def _mod1(x, n):
    return ((x - 1) % n + n) % n + 1


def _cyc(start, n, r):
    return sorted(_mod1(start + t, n) for t in range(r))


def placement(K, r):
    unit = 2 * (K - 1)
    return {
        "kind": "placement", "nodes": K, "r": r, "unit": unit,
        "segments": [{"id": i + 1, "size": unit, "storage": _cyc(i + 1, K, r)} for i in range(K)],
    }


def target(K, r, removed=None):
    if removed is None:
        removed = K
    # WLOG removed == K: survivors are nodes 1..K-1, cyclic on K-1 nodes.
    unit = 2 * (K - 1)
    size = 2 * K  # file/(K-1) in chunks
    return {
        "kind": "placement", "nodes": K - 1, "r": r, "unit": unit,
        "segments": [{"id": i + 1, "size": size, "storage": _cyc(i + 1, K - 1, r)} for i in range(K - 1)],
    }
