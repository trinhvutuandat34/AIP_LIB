#!/usr/bin/env python3
"""Local pre-flight check for ai-combat-core2 agent YAML files.

This is NOT the official validator. The official one is the SDK's own
``tools/validate_agent.py`` (same parser the server uses) — always run that
before submitting. This script only catches what's mechanically checkable
from ``agent.schema.json`` plus the lo/hi doctrine-band rule documented in
RULEBOOK.md section 10.2, so mistakes get caught locally before burning a
submission slot (min. 2h between submissions).

Usage:
    python3 validate_local.py ../agents/agent.yaml
"""
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE.parent / "reference" / "agent.schema.json"


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <agent.yaml>", file=sys.stderr)
        return 2

    agent_path = Path(sys.argv[1])
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    doc = yaml.safe_load(agent_path.read_text(encoding="utf-8"))

    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))

    ok = True
    if errors:
        ok = False
        print(f"[SCHEMA] {len(errors)} error(s) in {agent_path}:")
        for e in errors:
            path = "/".join(str(p) for p in e.absolute_path) or "<root>"
            print(f"  - at {path}: {e.message}")
    else:
        print(f"[SCHEMA] OK — {agent_path} matches agent.schema.json")

    # Cross-field rule from RULEBOOK.md §10.2: any doctrine `<x>_lo` must be
    # <= its matching `<x>_hi`. The JSON Schema has no cross-field checks,
    # so the server enforces this separately — replicate it here.
    doctrine = (doc or {}).get("doctrine", {}) or {}
    for key in list(doctrine):
        if key.endswith("_lo"):
            base = key[: -len("_lo")]
            hi_key = f"{base}_hi"
            if hi_key in doctrine and doctrine[key] > doctrine[hi_key]:
                ok = False
                print(
                    f"[DOCTRINE] {key}={doctrine[key]} > {hi_key}={doctrine[hi_key]} "
                    f"— band inverted, server will reject this"
                )
    if not doctrine:
        pass
    elif ok:
        print("[DOCTRINE] all lo/hi bands consistent")

    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
