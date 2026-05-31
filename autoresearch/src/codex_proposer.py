"""CodexProposer — drives the `codex` CLI to propose a concrete scheme per regime.

For a regime (K, r, removed) it runs a 3-step agent pipeline — placement → plan → repair
— each writing canonical JSON artifacts into a per-regime working directory, then reads
them back into a scheme. It does NOT trust the output: run_loop gates every scheme through
the oracle, so a bad agent yields a rejected (or, if it writes nothing, absent) candidate.

The codex call is isolated in `codex_runner` and INJECTABLE: tests pass a fake runner that
writes fixtures, so the proposer's plumbing is verified without codex installed. Adjust the
`codex exec` flags in `codex_runner` to match your installed codex version.
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def _load(p):
    return json.loads(Path(p).read_text())


def codex_runner(model=None, timeout=900):
    """Default runner: one `codex exec` turn in the workdir, with prompt/stdout/stderr
    logged for provenance. Returns the completed subprocess."""
    def run(step, prompt, workdir):
        wd = Path(workdir)
        (wd / f"{step}.prompt.txt").write_text(prompt)
        cmd = ["codex", "exec"]
        if model:
            cmd += ["--model", model]
        cmd += ["--cd", str(wd), prompt]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        (wd / f"{step}.stdout.txt").write_text(proc.stdout or "")
        (wd / f"{step}.stderr.txt").write_text(proc.stderr or "")
        return proc
    return run


def _ctx():
    parts = []
    for f in ("problem_context.md", "artifact_contract.md"):
        p = DOCS / f
        if p.exists():
            parts.append(p.read_text().strip())
    return "\n\n".join(parts)


def _placement_prompt(K, r, removed):
    return f"""You are the PLACEMENT agent. Produce ONE concrete balanced placement.

{_ctx()}

## Task
Regime: K={K} nodes, replication r={r}; node {removed} will be removed.
Write two files in the current directory:
- `cand.placement.json` — the initial balanced Placement on K={K} nodes.
- `cand.target.json` — the balanced target Placement on K-1={K - 1} nodes after node {removed} is removed.
Both must satisfy the Placement schema and the balanced-condition invariants. Self-check before finishing:
  python3 {ROOT}/src/verify_cli.py placement cand.placement.json
  python3 {ROOT}/src/verify_cli.py placement cand.target.json
Write only the JSON files; do not print prose."""


def _plan_prompt(K, r, removed):
    return f"""You are the PLAN agent. Produce the split/merge plan that rebalances after removing node {removed}.

{_ctx()}

## Task
Read `cand.placement.json` (initial, K={K}) and `cand.target.json` (target, K-1={K - 1}).
Write `cand.plan.json` — a SplitMergePlan: destination-tagged subsegments and merges that
turn the initial placement into the target. Respect the destination rule B = S~_j \\ S_i and
exact size conservation. Self-check before finishing:
  python3 {ROOT}/src/verify_cli.py plan cand.plan.json --initial cand.placement.json --target cand.target.json
Write only the JSON file."""


def _repair_prompt(K, r, removed):
    return f"""You are the REPAIR agent. Produce coded broadcasts that deliver every moving subsegment.

{_ctx()}

## Task
Read `cand.plan.json` and `cand.placement.json`. Write `cand.repair.json` — a RepairScheme
of broadcasts (XOR several subsegments when every receiver holds all-but-one as side info).
Minimize total broadcast units. Self-check before finishing:
  python3 {ROOT}/src/verify_cli.py repair cand.repair.json --plan cand.plan.json --initial cand.placement.json
Write only the JSON file."""


class CodexProposer:
    """A loop proposer backed by codex agents. `.propose(regime) -> list[candidate]`."""

    def __init__(self, runner=None, workroot=None, family="codex", model=None):
        self.runner = runner or codex_runner(model=model)
        self.workroot = Path(workroot) if workroot else (ROOT / "runs" / "codex")
        self.family = family

    def propose(self, regime):
        K, r, removed = regime
        wd = self.workroot / f"K{K}_r{r}_rm{removed}"
        wd.mkdir(parents=True, exist_ok=True)

        steps = [
            ("placement", _placement_prompt, ["cand.placement.json", "cand.target.json"]),
            ("plan", _plan_prompt, ["cand.plan.json"]),
            ("repair", _repair_prompt, ["cand.repair.json"]),
        ]
        for step, prompt_fn, outputs in steps:
            try:
                self.runner(step, prompt_fn(K, r, removed), wd)
            except Exception:
                return []  # codex unavailable / failed → no proposal (loop logs it)
            if not all((wd / o).exists() for o in outputs):
                return []  # agent didn't produce the artifact

        try:
            scheme = {
                "initial": _load(wd / "cand.placement.json"),
                "target": _load(wd / "cand.target.json"),
                "plan": _load(wd / "cand.plan.json"),
                "repair": _load(wd / "cand.repair.json"),
            }
        except Exception:
            return []  # unparseable artifact

        return [{"label": f"codex-K{K}r{r}", "family": self.family, "scheme": scheme}]
