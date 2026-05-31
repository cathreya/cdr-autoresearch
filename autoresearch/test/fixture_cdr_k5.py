"""Fixture from arXiv:2001.04939 "Coded Data Rebalancing", Example 1.

K=5 nodes, replication r=3, node 5 removed.

Placement: the file is split into P(5,2)=20 subfiles indexed by ORDERED 2-subsets
[i j] of {1..5}; node k stores W_[ij] iff k not in {i,j} (so each subfile sits on the
r=3 nodes outside its index). After removing node 5 the target has 4 subfiles W_[i],
i in {1..4}; node j stores W_[i] iff j != i.

Rebalancing: node 5's 12 subfiles split into 4 groups G_j (second index = j). In group
G_j the 3 subfiles W_[ij] (i in survivors\{j}) are exchanged among nodes survivors\{j}
via the 3-user data-exchange protocol: each subfile is halved, and node m broadcasts the
XOR of the m-indexed halves of the two subfiles not destined to it. The 8 subfiles that
contain index 5 are already on the correct survivors and pass through unmoved.

Sizes are in half-subfile units: a subfile = 2, a half = 1. Coded load = 12 half-units
(= 6 subfiles) vs. baseline 24 (= 12 subfiles): communication load 1/2, exactly the paper.
"""


def build():
    K, r, removed = 5, 3, 5
    survivors = [n for n in range(1, K + 1) if n != removed]  # [1,2,3,4]
    SUB = 2          # subfile size (in half-units)
    TSIZE = 5 * SUB  # target subfile = merge of 5 subfiles = 10

    def sid(i, j):
        return f"{i}_{j}"

    # ---- initial placement: ordered pairs over [K], storage = [K] \ {i,j} ----
    initial_segs = []
    for i in range(1, K + 1):
        for j in range(1, K + 1):
            if i == j:
                continue
            storage = sorted(n for n in range(1, K + 1) if n not in (i, j))
            initial_segs.append({"id": sid(i, j), "size": SUB, "storage": storage})
    initial = {"kind": "placement", "nodes": K, "r": r, "unit": SUB, "segments": initial_segs}

    # ---- target placement on survivors: W_[j], storage = survivors \ {j} ----
    target_segs = [
        {"id": j, "size": TSIZE, "storage": sorted(n for n in survivors if n != j)}
        for j in survivors
    ]
    target = {"kind": "placement", "nodes": K - 1, "r": r, "unit": SUB, "segments": target_segs}

    # ---- plan: pieces + merges ----
    pieces = []
    merges = {j: [] for j in survivors}

    # delivered subfiles W_[ij] (i,j survivors, i!=j) -> target j, dest {i}, split into
    # two halves indexed by the other two survivors (survivors \ {i,j}).
    for j in survivors:
        for i in survivors:
            if i == j:
                continue
            src = sid(i, j)
            for m in [n for n in survivors if n not in (i, j)]:
                pid = f"{src}_h{m}"
                pieces.append({"id": pid, "source": src, "dest": [i], "size": 1})
                merges[j].append(pid)

    # passthrough subfiles containing 5 (W_[j5], W_[5j]) -> target j, already in place.
    for j in survivors:
        for src in (sid(j, removed), sid(removed, j)):
            pid = f"{src}_pt"
            pieces.append({"id": pid, "source": src, "dest": [], "size": SUB})
            merges[j].append(pid)

    plan = {
        "kind": "plan", "removed": removed, "pieces": pieces,
        "merges": [{"target": j, "parts": merges[j]} for j in survivors],
    }

    # ---- repair: per group, the 3-user exchange ----
    broadcasts = []
    for j in survivors:
        M = [m for m in survivors if m != j]  # group node set
        for m in M:
            terms = [f"{sid(i, j)}_h{m}" for i in M if i != m]  # m-indexed halves of the other two
            broadcasts.append({"by": m, "terms": terms})
    repair = {"kind": "repair", "broadcasts": broadcasts}

    return {"K": K, "r": r, "removed": removed, "baseline": 24,
            "initial": initial, "target": target, "plan": plan, "repair": repair}
