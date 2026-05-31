#!/usr/bin/env python3
"""AutoResearch orchestrator.

Runs the six-agent Codex pipeline through file artifacts instead of hidden chat
state. Each agent is driven via the `codex` CLI as a subprocess. After each agent,
a hard gate (gate.py) re-verifies every canonical artifact it emitted, ignoring the
agent's prose claims; in strict mode a gate failure halts the run.

    python3 src/orchestrate.py --dry-run --k 6 --r 3
    python3 src/orchestrate.py --k 8 --r 6 --removed 8

--dry-run prepares prompts/manifest/seed without invoking Codex.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# src/ is on sys.path[0] when run as `python3 src/orchestrate.py`, so siblings import directly.
from gate import gate_and_report
from placement_model import write_seed_model

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
PROBLEM_CONTEXT = ROOT / "docs" / "problem_context.md"
ARTIFACT_CONTRACT = ROOT / "docs" / "artifact_contract.md"

AGENT_PLAN = [
    {"id": "lit-review", "prompt": "lit_review.md",
     "outputs": ["lit_review.md", "design_primitives.json"]},
    {"id": "placement-synthesizer", "prompt": "placement_synthesizer.md", "needs": ["lit-review"],
     "outputs": ["placement_synthesis.md", "placement_candidates.json"]},
    {"id": "implementer", "prompt": "implementer.md", "needs": ["placement-synthesizer"],
     "outputs": ["implementation_notes.md", "candidate_examples.json"]},
    {"id": "example-evaluator", "prompt": "example_evaluator.md", "needs": ["implementer"],
     "outputs": ["coding_opportunities.md", "broadcast_candidates.json"]},
    {"id": "generalizer", "prompt": "generalizer.md",
     "needs": ["lit-review", "placement-synthesizer", "implementer", "example-evaluator"],
     "outputs": ["generalized_scheme.md", "scheme_spec.json"]},
    {"id": "fuzzy-eval", "prompt": "fuzzy_eval.md", "needs": ["generalizer", "example-evaluator"],
     "outputs": ["tradeoff_eval.md", "scorecard.json"]},
]


def parse_args(argv):
    p = argparse.ArgumentParser(description="AutoResearch Codex orchestrator")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--r", type=int, default=6)
    p.add_argument("--removed", type=int, default=None)
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    p.add_argument("--parallel-evals", dest="parallel_evals", action="store_true")
    p.add_argument("--no-gate", dest="gate", action="store_false")
    p.add_argument("--no-strict", dest="strict", action="store_false")
    p.add_argument("--codex-model", dest="codex_model", default=None)
    args = p.parse_args(argv)
    if args.removed is None:
        args.removed = args.k
    if not (3 <= args.r <= args.k - 1):
        p.error("Require 3 <= r <= K-1.")
    return args


def load_prompt(agent, context):
    prompt = (PROMPTS_DIR / agent["prompt"]).read_text().strip()
    problem = PROBLEM_CONTEXT.read_text().strip()
    contract = ARTIFACT_CONTRACT.read_text().strip()
    outputs = "\n".join(f"- {name}" for name in agent["outputs"])
    return f"""{prompt}

## Shared Problem Context

{problem}

## Artifact Contract

{contract}

## Run Context

{json.dumps(context, indent=2)}

## Required Output Location

Write your outputs under:

{context['agentOutputDir']}

Required files:

{outputs}
"""


def run_codex(prompt, cwd, model=None):
    """Drive a single Codex turn non-interactively via the CLI.

    NOTE: adjust this command to match your installed `codex` version. `codex exec`
    runs a one-shot prompt in `cwd` and writes the result to stdout. Returns the
    completed subprocess (stdout/stderr captured).
    """
    cmd = ["codex", "exec"]
    if model:
        cmd += ["--model", model]
    cmd += ["--cd", str(cwd), prompt]
    return subprocess.run(cmd, capture_output=True, text=True)


def run_agent(run_dir, manifest, params, agent):
    agent_out = run_dir / agent["id"]
    agent_out.mkdir(parents=True, exist_ok=True)
    context = {
        "runDir": str(run_dir),
        "agentOutputDir": str(agent_out),
        "manifestPath": str(run_dir / "manifest.json"),
        "problemContextPath": str(PROBLEM_CONTEXT),
        "seedModelPath": str(run_dir / "seed_model.json"),
        "parameters": {"K": params.k, "r": params.r, "removed": params.removed},
        "upstreamArtifacts": {n: str(run_dir / n) for n in agent.get("needs", [])},
    }
    prompt = load_prompt(agent, context)
    (agent_out / "prompt.md").write_text(prompt)

    if params.dry_run:
        (agent_out / "DRY_RUN.md").write_text(f"# {agent['id']}\n\nPrompt prepared but Codex was not invoked.\n")
        return {"agent": agent["id"], "status": "dry-run"}

    proc = run_codex(prompt, ROOT, params.codex_model)
    (agent_out / "codex_stdout.md").write_text(proc.stdout or "")
    (agent_out / "codex_stderr.md").write_text(proc.stderr or "")

    # Hard gate: re-verify every canonical artifact the agent emitted.
    gate = {"ok": True, "artifacts": []}
    if params.gate:
        gate = gate_and_report(agent_out)
        invalid = [a for a in gate["artifacts"] if not a["ok"]]
        if invalid:
            print(f"  [gate] {agent['id']}: {len(invalid)} invalid artifact(s):", file=sys.stderr)
            for a in invalid:
                print(f"    - {a['file']}: {'; '.join(a['errors'])}", file=sys.stderr)
            if params.strict:
                raise SystemExit(
                    f"Gate rejected {agent['id']}: {', '.join(a['file'] for a in invalid)}. "
                    "Invariants must hold. Re-run with --no-strict to continue past gate failures."
                )
        elif gate["artifacts"]:
            print(f"  [gate] {agent['id']}: {len(gate['artifacts'])} artifact(s) verified")

    return {"agent": agent["id"], "status": "completed", "gate": gate}


def write_manifest(run_dir, params):
    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "parameters": {"K": params.k, "r": params.r, "removed": params.removed,
                       "dryRun": params.dry_run, "gate": params.gate, "strict": params.strict},
        "agents": AGENT_PLAN,
        "artifactPolicy": "Agents communicate only through files in this run directory.",
    }
    with open(run_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return manifest


def build_final_report(run_dir, results):
    lines = [
        "# AutoResearch Run Summary",
        "",
        f"Run directory: {run_dir}",
        "",
        "## Agent Status",
        "",
        *[f"- {r['agent']}: {r['status']}" for r in results],
        "",
        "## Next Read Order",
        "",
        "- `lit-review/lit_review.md`",
        "- `placement-synthesizer/placement_synthesis.md`",
        "- `implementer/implementation_notes.md`",
        "- `example-evaluator/coding_opportunities.md`",
        "- `generalizer/generalized_scheme.md`",
        "- `fuzzy-eval/tradeoff_eval.md`",
    ]
    (run_dir / "final_report.md").write_text("\n".join(lines) + "\n")


def main(argv):
    params = parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"
    run_dir = ROOT / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    write_seed_model(run_dir, params.k, params.r, params.removed)
    manifest = write_manifest(run_dir, params)

    results = []
    for agent in AGENT_PLAN:
        print(f"Running {agent['id']}{' (dry-run)' if params.dry_run else ''}")
        results.append(run_agent(run_dir, manifest, params, agent))
    build_final_report(run_dir, results)
    print(f"Wrote {run_dir}")


if __name__ == "__main__":
    main(sys.argv[1:])
