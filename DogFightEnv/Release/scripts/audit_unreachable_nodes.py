"""Find rule-XML nodes that never execute, or execute but never succeed.

WHY THIS EXISTS (2026-08-21). This project has shipped an unreachable tactical layer twice:
F25 (all 17 named control nodes built with zero children, so only 2 leaf nodes had EVER run)
and F37 (`Task_Evade` structurally unreachable because `Task_JinkingTurn` always won the
Fallback above it). Both were invisible to outcome-based measurement -- the aircraft flew, the
evals produced numbers, and the numbers were simply of a tree that wasn't running.

The organizers' own cutoff model has the identical class of defect, found independently while
analysing it: `DECO_EnemyWEZCheck`, `DefenceTurn`, `JinkingTurn`, `JinkingTurnSelector` and
`DECO_JinkingCoolTimeCheck` are all compiled into `unreal_bt_client.exe` and referenced ZERO
times by its active tree. Two separate teams building on the same base tree both shipped a
disconnected defensive layer. That makes this a property of the base, not bad luck, and worth
a standing check rather than a one-off.

INPUT: the `.nodes.txt` inventory and trace CSVs produced by AIP_BT_GATE_TRACE (see
COMPETITION_PLAN.md 4.1 F25 for the recipe). Pass one or more trace CSVs; each is expected to
have a sibling `<trace>.nodes.txt`.

VERDICTS, and why the second one matters as much as the first:
  NEVER-EVALUATED  the node is never even visited -- structurally unreachable (the F25 shape).
  NEVER-SUCCEEDS   visited, but returns FAILURE on every single tick it was ever evaluated on.
                   Its guard never passes, so whatever sits below/behind it is dead in
                   practice. This is the F37 shape, and it is the one an outcome metric will
                   never show you.

A node listed here is NOT automatically a bug -- a defensive node legitimately never fires in a
purely offensive geometry. That is exactly why this takes MULTIPLE traces and reports which
geometries each node was seen in. Judge a node by whether it stayed silent in the geometry that
should have triggered it.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)  # winning_path is one huge field per tick


def load_inventory(nodes_txt: Path) -> dict[str, str]:
    """name -> node type, from a `.nodes.txt` dump. Unnamed structural nodes are skipped:
    every Sequence/Fallback is literally called "Sequence"/"Fallback" post-F25 (the fix REMOVED
    the name= attribute), so they are indistinguishable from each other and cannot be tracked
    individually."""
    inv: dict[str, str] = {}
    pat = re.compile(r'^\s*(\S+)\s+name="([^"]*)"\s+children=(\S+)\s*$')
    for line in nodes_txt.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pat.match(line)
        if not m:
            continue
        ntype, name, _children = m.groups()
        if name in ("Sequence", "Fallback", "Inverter", ""):
            continue
        inv[name] = ntype
    return inv


def scan_trace(trace_csv: Path) -> dict[str, set[str]]:
    """name -> set of statuses ever returned ('S'/'F'/'R') across every tick in this trace."""
    seen: dict[str, set[str]] = defaultdict(set)
    with trace_csv.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            path = row.get("winning_path") or ""
            if not path:
                continue
            for entry in path.split("|"):
                name, _, status = entry.rpartition(":")
                if name:
                    seen[name].add(status)
    return seen


def main(argv: list[str]) -> int:
    traces = [Path(p) for p in argv[1:]]
    if not traces:
        print(__doc__)
        return 2

    inventory: dict[str, str] = {}
    per_geo: dict[str, dict[str, set[str]]] = {}
    for t in traces:
        if not t.exists():
            print(f"[audit] MISSING trace: {t}")
            continue
        nodes_txt = Path(str(t) + ".nodes.txt")
        if not nodes_txt.exists():
            nodes_txt = t.with_suffix(".nodes.txt")
        if nodes_txt.exists():
            inventory.update(load_inventory(nodes_txt))
        else:
            print(f"[audit] WARNING no .nodes.txt beside {t.name}; inventory may be partial")
        geo = t.stem.replace("audit_", "")
        per_geo[geo] = scan_trace(t)
        print(f"[audit] {geo:<20} {len(per_geo[geo]):>4} distinct nodes observed  ({t.name})")

    if not inventory:
        print("[audit] no inventory recovered -- cannot audit")
        return 1

    print(f"\n[audit] inventory: {len(inventory)} NAMED nodes across {len(per_geo)} geometries")

    never_eval: list[str] = []
    never_succeed: list[str] = []
    for name in sorted(inventory):
        statuses: set[str] = set()
        for seen in per_geo.values():
            statuses |= seen.get(name, set())
        if not statuses:
            never_eval.append(name)
        elif "S" not in statuses:
            never_succeed.append(name)

    def where(name: str) -> str:
        gs = [g for g, seen in per_geo.items() if name in seen]
        return ", ".join(gs) if gs else "-"

    print("\n" + "=" * 78)
    print(f"NEVER EVALUATED -- structurally unreachable ({len(never_eval)})")
    print("=" * 78)
    for n in never_eval:
        print(f"  {inventory[n]:<28} {n}")
    if not never_eval:
        print("  (none)")

    print("\n" + "=" * 78)
    print(f"NEVER SUCCEEDS -- evaluated, always FAILURE ({len(never_succeed)})")
    print("=" * 78)
    for n in never_succeed:
        print(f"  {inventory[n]:<28} {n:<44} seen in: {where(n)}")
    if not never_succeed:
        print("  (none)")

    healthy = len(inventory) - len(never_eval) - len(never_succeed)
    print(f"\n[audit] {healthy}/{len(inventory)} named nodes succeed at least once somewhere.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
