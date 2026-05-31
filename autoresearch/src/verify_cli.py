#!/usr/bin/env python3
"""CLI wrapper around the verifier — the tool agents invoke to self-check an
artifact before emitting it. Also exposes verify_file() for reuse.

Usage:
    python3 src/verify_cli.py placement <file.json>
    python3 src/verify_cli.py plan   <plan.json>   --initial <init.json> --target <target.json>
    python3 src/verify_cli.py repair <repair.json> --plan <plan.json> --initial <init.json> [--baseline N]

Prints a JSON result {ok, errors, ...metrics} and exits 0 (valid) or 1 (invalid).
"""

import json
import sys

from verifier import validate_placement, verify_plan, verify_repair


def _read_json(path):
    with open(path) as f:
        return json.load(f)


def verify_file(kind, file, opts=None):
    opts = opts or {}
    if kind == "placement":
        return validate_placement(_read_json(file))
    if kind == "plan":
        return verify_plan(_read_json(file), _read_json(opts["initial"]), _read_json(opts["target"]))
    if kind == "repair":
        baseline = float(opts["baseline"]) if opts.get("baseline") is not None else None
        return verify_repair(_read_json(file), _read_json(opts["plan"]), _read_json(opts["initial"]), baseline)
    return {"ok": False, "errors": [f"unknown kind '{kind}'"]}


def _parse_flags(argv):
    flags = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--"):
            flags[argv[i][2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return flags


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(
            "usage: verify_cli.py <placement|plan|repair> <file.json> "
            "[--initial f --target f --plan f --baseline N]",
            file=sys.stderr,
        )
        sys.exit(2)
    kind, file = args[0], args[1]
    flags = _parse_flags(args[2:])
    result = verify_file(kind, file, flags)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
