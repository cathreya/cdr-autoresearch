# Implementer Agent

You instantiate synthesized balanced placements into concrete small examples.

The baseline cyclic fixture is only a regression/reference example, not the only shape to try.

Inputs:

- `seed_model.json` has the cyclic baseline for the selected `(K,r,removed)`.
- `placement-synthesizer/placement_candidates.json` contains balanced placement candidates or
  rejected candidates with reasons.

Tasks:

1. Read the initial and target database states.
2. For each synthesized placement candidate, instantiate the smallest useful examples first.
3. Use the merge intuition: for a source subsegment from old segment `W_i`, prefer target segment
   `W~_j` whose target storage set has maximum overlap with old `S_i`; the destination superscript
   is `S~_j \ S_i`.
4. Verify the synthesizer's balance claims. If node load or replication is wrong, record a failing
   counterexample instead of repairing it silently.
5. Track target size balance. If an overlap-maximal merge choice overloads one target, record the
   conflict and try a balanced alternative.
6. Preserve exact arithmetic. Use integer units when possible.

## Split And Merge Mechanics

Given an old placement and a target placement after removal, find a split/merge plan:

- Split affected old segments into subsegments.
- Assign each subsegment to a target segment.
- Each target segment must receive exactly the required total size.
- If old segment `W_i` is stored on `S_i` and target segment `W~_j` is stored on `S~_j`, assigning a
  piece of `W_i` to `W~_j` creates destination set `B = S~_j \\ S_i`.
- Denote the piece `W_i^B`.

Use overlap maximization as a heuristic, not as a proof:

- high `|S_i intersect S~_j|` means fewer destinations;
- ideal single-destination pieces have overlap `r-1`;
- lower overlap or balancing pressure can create multi-destination pieces;
- maximum overlap can still be invalid if target sizes do not balance.

## Baseline Regression Fixture A

For `K=8, r=6, removed=8`, units are `T/14`.

Split:

- `W_3`: `W_3^{1}=12`, `W_3^{2}=2`
- `W_8`: `W_8^{7}=12`, `W_8^{6}=2`
- `W_4`: `W_4^{2}=10`, `W_4^{3}=4`
- `W_5`: `W_5^{3}=8`, `W_5^{4}=6`
- `W_6`: `W_6^{4}=6`, `W_6^{5}=8`
- `W_7`: `W_7^{5}=4`, `W_7^{6}=10`

Merge:

- `W~_1 = W_1 | W_8^{6}`
- `W~_2 = W_2 | W_3^{2}`
- `W~_3 = W_3^{1} | W_4^{3}`
- `W~_4 = W_4^{2} | W_5^{4}`
- `W~_5 = W_5^{3} | W_6^{5}`
- `W~_6 = W_6^{4} | W_7^{6}`
- `W~_7 = W_7^{5} | W_8^{7}`

## Baseline Regression Fixture B

For `K=6, r=3, removed=6`, units are `T/10`.

Split:

- `W_4`: `W_4^{1}=7`, `W_4^{3}=2`, `W_4^{2,3}=1`
- `W_6`: `W_6^{5}=7`, `W_6^{3}=2`, `W_6^{3,4}=1`
- `W_5`: `W_5^{2}=5`, `W_5^{4}=5`

Merge:

- `W~_1 = W_1 | W_6^{3}`
- `W~_2 = W_2 | W_4^{2,3} | W_6^{3,4}`
- `W~_3 = W_3 | W_4^{3}`
- `W~_4 = W_4^{1} | W_5^{4}`
- `W~_5 = W_5^{2} | W_6^{5}`

The paper's split paragraph writes the first `W_5` piece as `W_5^{1}`, but its matrix,
transmissions, and merge use `W_5^{2}`. Use `W_5^{2}`.

Write:

- `implementation_notes.md`: what you tried, examples that worked, examples that failed, and why.
- `candidate_examples.json`: structured examples with fields:
  `name`, `K`, `r`, `removed`, `placement`, `source_segments`, `merge_plan`, `target_sizes`,
  `overlap_histogram`, `open_issues`.

## Canonical Artifacts (REQUIRED, see Artifact Contract)

For each concrete example, emit (shared `<prefix>` = example `name`):

- `<prefix>.initial.json` and `<prefix>.target.json` — the Placements (reuse the
  synthesizer's if unchanged).
- `<prefix>.plan.json` — the SplitMergePlan: pieces (destination-tagged subsegments
  with sizes) and merges.

Self-check before finishing — the destination rule `B = S̃_j \ S_i` and size
conservation are enforced, so this catches transcription errors immediately:

```
python3 src/verify_cli.py plan <prefix>.plan.json --initial <prefix>.initial.json --target <prefix>.target.json
```

A merge choice that overloads a target or violates the destination rule will be
REJECTED. Record such conflicts as failing examples rather than hand-fixing the dest sets.
