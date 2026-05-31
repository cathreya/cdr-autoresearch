# AutoResearch

AutoResearch is a Codex orchestration scaffold for exploring coded data-rebalancing schemes.
It coordinates six specialized Codex agents through file artifacts instead of hidden chat state:

1. `lit-review`: survey combinatorial design literature for reusable design primitives.
2. `placement-synthesizer`: convert design primitives into balanced placement candidates.
3. `implementer`: instantiate small `(K,r)` databases, split/merge subsegments, and measure overlap.
4. `example-evaluator`: look for coding opportunities in the concrete examples.
5. `generalizer`: turn promising examples into a parameterized scheme.
6. `fuzzy-eval`: evaluate tradeoffs such as communication load, IO reads, implementation complexity, and brittleness.

Pure Python, no third-party dependencies (Python 3.9+). Each agent is driven via the
`codex` CLI as a subprocess; adjust the command in `run_codex()` (`src/orchestrate.py`)
to match your installed `codex` version.

## Quick Start

```bash
# prepare prompts/manifest/seed without invoking Codex
python3 src/orchestrate.py --dry-run --k 6 --r 3

# full run
python3 src/orchestrate.py --k 8 --r 6 --removed 8
```

Outputs are written to `runs/<timestamp>/`.

## Useful Options

```bash
python3 src/orchestrate.py --k 6 --r 3 --removed 6
python3 src/orchestrate.py --dry-run --k 7 --r 4
python3 src/orchestrate.py --k 8 --r 6 --no-strict   # don't halt on gate failures
```

`--dry-run` does not invoke Codex. It writes the same manifest, prompts, and seed
placement artifacts so you can inspect the planned workflow.

## Demo UI

A Streamlit dashboard that runs the real oracle on the verified reference schemes —
deterministic, no API keys.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Three tabs:
- **▶️ Discover** (the <1-minute demo) — one click runs the loop "discovering" the cyclic
  scheme while the oracle verifies each JSON artifact (placement → plan → repair) live.
- **🔬 Verifier Gate** — tamper with a verified scheme and watch the oracle reject it with
  the exact invariant violated.
- **📈 Schemes & Tradeoffs** — the two oracle-verified schemes and the subpacketization-vs-K
  tradeoff between families.

## The verifier (oracle)

Correctness is enforced by code, not by the agents. `src/verifier.py` validates the
balanced-condition invariants; the gate (`src/gate.py`) re-runs it on every canonical
artifact an agent emits and (in strict mode) halts the run on any failure.

```bash
# tests / regression fixtures (18 vectors incl. paper Fixture A)
python3 test/test_verifier.py

# self-check a single artifact (the tool agents call)
python3 src/verify_cli.py placement <file>.placement.json
python3 src/verify_cli.py plan   <p>.plan.json   --initial <p>.initial.json --target <p>.target.json
python3 src/verify_cli.py repair <p>.repair.json --plan <p>.plan.json --initial <p>.initial.json

# print the cyclic seed model
python3 src/placement_model.py --k 8 --r 6
```

See `docs/artifact_contract.md` for the artifact schemas and invariants, and
`schemas/*.schema.json` for the formal JSON Schemas.

## Artifact Contract

Each agent receives the shared problem context, the artifact contract, the run
manifest, the seed placement model, and the outputs of upstream agents. It must write
a markdown report plus canonical JSON artifacts (`<prefix>.placement.json`,
`<prefix>.plan.json`, `<prefix>.repair.json`) that pass the verifier. The final
summary is `runs/<timestamp>/final_report.md`.
