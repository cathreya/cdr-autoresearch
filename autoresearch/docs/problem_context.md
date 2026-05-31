# Shared Problem Context

## Description

Consider a distributed system with K nodes. Consider a file containing NT bits. Let r be the replication factor.

We group the bits into logical segments W_i, for i = 1 to N. Each segment is of size T. Each segment is replicated r times in the system. Let S_i represent all nodes that store segment W_i.

A database is balanced if the following hold - 
1. every segment has replication r. i.e. size of each S_i = r.
2. every node stores the same amount of data - NTr/K.

The number of segments `N` and the placement are DESIGN CHOICES, not fixed by `(K, r)`.
Many balanced databases exist for the same `(K, r)`. The cyclic construction used below
and in the seed model (`N = K`, each `S_i` a length-`r` cyclic interval) is just one
canonical example — the one used by the reference paper. Exploring other segmentations,
including `N != K` (e.g. `N` = number of blocks in a combinatorial design), is a primary
goal of this project; the synthesizer and lit-review agents should treat `N` as free.

Feasibility (do not over-constrain): with `N` equal-size segments, balance requires each
node to hold `N*T*r/K` bits, so `K` must divide `r * N * (chunks per T)`. A finer
subpacketization (the `unit` in the Artifact Contract) can always clear this divisibility,
so `N` is effectively unconstrained — `unit` is the slack variable, not `N`.

## Single-Node Removal Objective

Nodes in the system can be removed. Without loss of generality lets asssume that node K is removed. All segments contained in node K lose a replica.

This is an imbalanced state.


## Rebalancing

Given a balanced database on (K,r), if node K is removed, then we have an imbalanced intermediate database. We want to restore it to a new balanced database on (K-1, r).

Individual segments can be split, shuffled and merged to fit the target database.

