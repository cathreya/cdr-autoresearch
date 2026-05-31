"""The hard gate. After an agent runs, the orchestrator re-verifies every canonical
artifact it emitted — no matter what the agent claimed in prose. Agents may be
creative; the balanced-condition invariants are non-negotiable.

Discovery convention inside an agent's output dir (prefix shared across siblings):
    <prefix>.placement.json   -> validated as a Placement
    <prefix>.plan.json        -> needs <prefix>.initial.json + <prefix>.target.json
    <prefix>.repair.json      -> needs <prefix>.plan.json + <prefix>.initial.json
The baseline for a repair (the Nr/K naive load) is computed from its initial
placement, so agents cannot inflate the coding gain by misreporting it.
"""

import json
import os
from pathlib import Path

from verifier import validate_placement, verify_plan, verify_repair


def _read_json(path):
    with open(path) as f:
        return json.load(f)


def _baseline_from_placement(placement):
    file_size = sum(s["size"] for s in placement["segments"])
    num = placement["r"] * file_size
    nodes = placement["nodes"]
    return num // nodes if num % nodes == 0 else num / nodes  # load of the removed node


def gate_agent_dir(directory):
    d = Path(directory)
    if not d.is_dir():
        return {"ok": True, "artifacts": []}

    artifacts = []

    def sibling(prefix, suffix):
        return d / f"{prefix}.{suffix}.json"

    for name in sorted(os.listdir(d)):
        if name.endswith(".placement.json"):
            kind, prefix = "placement", name[: -len(".placement.json")]
        elif name.endswith(".plan.json"):
            kind, prefix = "plan", name[: -len(".plan.json")]
        elif name.endswith(".repair.json"):
            kind, prefix = "repair", name[: -len(".repair.json")]
        else:
            continue

        path = d / name
        try:
            if kind == "placement":
                result = validate_placement(_read_json(path))
            elif kind == "plan":
                result = verify_plan(
                    _read_json(path),
                    _read_json(sibling(prefix, "initial")),
                    _read_json(sibling(prefix, "target")),
                )
            else:
                initial = _read_json(sibling(prefix, "initial"))
                result = verify_repair(
                    _read_json(path),
                    _read_json(sibling(prefix, "plan")),
                    initial,
                    _baseline_from_placement(initial),
                )
        except Exception as err:  # noqa: BLE001 — any failure is a gate failure
            result = {"ok": False, "errors": [f"could not verify ({err})"]}
        artifacts.append({"file": name, "kind": kind, **result})

    return {"ok": all(a["ok"] for a in artifacts), "artifacts": artifacts}


def gate_and_report(directory):
    """Run the gate on an agent dir and persist verification.json. Returns the report."""
    report = gate_agent_dir(directory)
    with open(Path(directory) / "verification.json", "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    return report
