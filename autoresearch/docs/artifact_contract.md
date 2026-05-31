# Artifact Contract

Agents communicate through **typed, verifiable artifacts**, not prose. You may be
arbitrarily creative in HOW you find a scheme, but the balanced-condition invariants
below are non-negotiable: the orchestrator re-verifies every artifact you emit with
`src/verifier.py` and **rejects** your output if an invariant fails, regardless of
what your report claims. Self-check before you emit (see "How to verify").

All sizes are integers in a shared `unit` (e.g. `unit: 14` means sizes are in `T/14`).
Node and segment ids are 1-based.

## Artifact kinds (JSON Schemas in `schemas/`)

### Placement — `<prefix>.placement.json`
Which nodes store each segment. Invariants (`validate_placement`):
- every segment is stored on **exactly `r`** distinct in-range nodes;
- the database is **balanced**: every node carries identical total size `= r·fileSize/nodes`.

### SplitMergePlan — `<prefix>.plan.json`
Splits source segments into destination-tagged subsegments and merges them into the
post-removal target segments. Needs sibling `<prefix>.initial.json` and
`<prefix>.target.json` placements. Invariants (`verify_plan`):
- **size conservation**: each source segment's pieces sum to its size;
- **target balance**: each target segment's parts sum to its size; each piece is
  consumed by exactly one merge;
- **destination rule**: a piece carved from source `i` and merged into target `j`
  must have `dest == S̃_j \ S_i` (the target-storage nodes that don't already hold it).

### RepairScheme — `<prefix>.repair.json`
An executable sequence of coded broadcasts delivering every moving piece. Needs
sibling `<prefix>.plan.json` and `<prefix>.initial.json`. Invariants (`verify_repair`):
- the transmitting node **stores every term** it XORs (and is not the removed node);
- **decodability**: for each term, every receiver (a node in that term's `dest`)
  already stores all the *other* terms in the same broadcast, so it can peel them off;
- **coverage**: every `(piece, destination-node)` obligation in the plan is delivered.
The broadcast size is `max(term sizes)` (zero-padded XOR). The baseline (`Nr/K`,
the removed node's load) is computed from the initial placement by the gate — you
cannot inflate the coding gain by misreporting it.

## File naming

Use a shared `<prefix>` so the gate can find siblings, e.g. for a candidate named
`design3`: `design3.initial.json`, `design3.target.json`, `design3.plan.json`,
`design3.repair.json`. Emit these *in addition to* your human-readable `.md` report
and any exploratory JSON; the gate only verifies files matching the suffixes above.

## How to verify (do this before emitting)

```bash
python3 src/verify_cli.py placement <prefix>.placement.json
python3 src/verify_cli.py plan   <prefix>.plan.json   --initial <prefix>.initial.json --target <prefix>.target.json
python3 src/verify_cli.py repair <prefix>.repair.json --plan <prefix>.plan.json --initial <prefix>.initial.json
```

Exit code 0 = valid; 1 = invalid (the JSON `errors` array tells you exactly what broke).
A worked, passing example lives in `test/fixtures/fixtureA.*` (K=8, r=6, removed=8).
