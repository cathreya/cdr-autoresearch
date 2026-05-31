# AutoResearch Architecture

A closed research loop, not a single linear pass. A **Judge** drives iteration; a
persistent **Placement Store** is the shared memory; the **verifier** (`src/verifier.py`)
is the trusted substrate under every step.

```
                ┌──────────────────────────────────────────────┐
                │              Placement Store                   │
                │  Literature · Done · Reject · Accept           │
                │  (keyed by canonical_hash — relabel-invariant) │
                └──────────────────────────────────────────────┘
                        ▲                              ▲
                        │ informs                      │ records
   ┌────────────┐       │      ┌──────────────────────────────────┐
   │ Lit Review │───────┘      │  one iteration (own git worktree) │
   └────────────┘              │                                   │
        ▲                      │  Placement gen → Plan gen →       │
        │ "explore family X"   │  Repair gen → Fuzzy Eval (report) │
   ┌────────┐                  └──────────────────────────────────┘
   │ Judge  │◀──── metrics ────────────────┘
   └────────┘   (comm load, IO reads, subpacketization)
        │
        └── extends the Pareto frontier → picks next direction
```

## Agents

1. **Lit Review** — surveys combinatorial-design literature for promising families,
   appends them to the store's *Literature* list. Re-invoked when the Judge asks for
   new leads.
2. **Placement gen** — for the branch's specific `(K, r)`, emits a **concrete**
   `placement.json` (and its post-removal `target.json`), **or rejects**. Each `(K, r)`
   is explored in its own branch; schemes can differ by regime, so we do not force one
   generator to cover all of them. A `place(K, r)` *generator* is an OPTIONAL artifact the
   generalizer emits later, once several branches are found to share structure — and
   `src/generator.py` then verifies it across that cluster of regimes.
3. **Plan gen** — given `(K, r)` and `(K-1, r)`, produces a `plan.json` (split/merge)
   from overlap intuition. Gated by `verify_plan`.
4. **Repair gen** — finds coding opportunities in the plan, emits `repair.json`. Gated
   by `verify_repair`.
5. **Fuzzy Eval** — writes `report.md`: does this win on *any* axis?
6. **Judge** — maintains a **Pareto frontier** over `(comm_load, io_reads, subpacketization)`
   (all minimized). Picks the next direction expected to extend the front; promotes
   schemes to *Accept*, dead-ends to *Reject*; tells Lit Review / Placement what to try.

## Why the verifier is central

Every arrow bottoms out in the oracle: "or rejects" = `validate_placement` failing, a
valid plan = `verify_plan`, "coding opp" = `verify_repair`, "does it win" = metrics
computed on *verified* artifacts. Agents are creative; the invariants are not negotiable,
so the Judge's feedback signal is trustworthy.

## Metrics (Pareto axes, all minimized)

- **comm_load** — coded broadcast units (`verify_repair.codedLoad`); also reported as a
  fraction of the `Nr/K` baseline.
- **io_reads** — reads needed to form the broadcasts (`Σ |terms|` over broadcasts).
- **subpacketization** — the placement `unit` (split granularity); proxy for metadata /
  implementation complexity.

A scheme is interesting if it is **non-dominated** — better on at least one axis without
being worse on the others — even if it loses on `comm_load`.

## Isolation & provenance

Each iteration runs in its own **git worktree** and commits its artifacts, so every
explored (and rejected) scheme is logged and reproducible. (Requires `git init` in this
directory.)

## Build status

- Done: verifier/gate/schemas, metrics, Pareto frontier, Placement Store, generator
  contract + runner, reference cyclic generator.
- Next: the Judge (LLM) + the loop orchestrator + worktree-per-iteration + Codex wiring.
