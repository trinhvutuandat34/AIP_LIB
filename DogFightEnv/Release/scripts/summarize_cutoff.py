"""Rank eval runs against the cutoff model on the organizers' stated bar.

THE BAR (organizers, 2026-08-19): the cutoff crashes on its own roughly 2-3 times in 10, and even
counting those in your favour, a win rate at or below 50% means reconsider entering the prelims.

THREE COLUMNS, AND WHY THEY DIFFER.

`env%` is what this project's eval already reports: the PHASED (real competition damage model)
outcome straight out of `_classify_outcome`.

`rule%` re-adjudicates the altitude floor the way COMPETITION_RULES Sec 5 states it -- "Minimum
altitude: 1000 ft (~300 m). Dropping below this is processed as a crash/loss." The env does NOT
do this symmetrically: `_classify_outcome` returns "crash" when OUR aircraft goes below the floor,
but falls through to "draw" when the TARGET does, because the target still had health left. So
every episode the cutoff flies itself into the ground is currently booked as a draw when the
competition rule makes it a win. That is exactly the allowance the organizers told us to count,
so `rule%` is the number to read against their bar.

`earned%` counts only episodes we ended by putting the target's health to zero. A margin made of
the opponent's self-crashes is not a margin we own: the cutoff tree has NO altitude protection at
all -- `DECO_TargetAltDifCheck` is dead code and there is no climb-to-safe-altitude node anywhere
in its active tree -- so if the organizers patch that, or the Unreal server's floor handling
differs from this env's, those wins revert. The gap between `rule%` and `earned%` is the risk.

    python scripts/summarize_cutoff.py "artifacts/eval/cutoff_*.csv"
"""

from __future__ import annotations

import csv
import glob
import sys
from pathlib import Path

# The cutoff put itself into the ground / lost its own FDM: a win under competition rules,
# but one we did not earn.
_TARGET_LOST = {"target altitude below min", "Target FDM output Fall"}
_OWNSHIP_LOST = {"ownship altitude below min", "Ownship FDM output Fall", "FDM Update Fail"}


def load(path: Path) -> dict | None:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if not rows:
        return None
    n = len(rows)

    env_w = env_d = env_l = 0
    rule_w = rule_d = rule_l = 0
    earned = free = our_crash = 0
    dealt = taken = 0.0

    for r in rows:
        phased = (r.get("phased_outcome") or "").strip().lower()
        end = (r.get("end_condition") or "").strip()
        dealt += float(r.get("ep_damage_dealt") or 0)
        taken += float(r.get("ep_damage_taken") or 0)

        if phased == "win":
            env_w += 1
        elif phased == "loss":
            env_l += 1
        else:
            env_d += 1

        # Competition adjudication: whoever went below the floor loses, regardless of health.
        if end in _TARGET_LOST:
            rule_w += 1
            free += 1
        elif end in _OWNSHIP_LOST:
            rule_l += 1
            our_crash += 1
        elif phased == "win":
            rule_w += 1
            earned += 1
        elif phased == "loss":
            rule_l += 1
        else:
            rule_d += 1

    return {
        "name": path.stem.replace("cutoff_", ""),
        "n": n,
        "env_w": env_w, "env_d": env_d, "env_l": env_l,
        "rule_w": rule_w, "rule_d": rule_d, "rule_l": rule_l,
        "env_rate": env_w / n,
        "rule_rate": rule_w / n,
        "earned_rate": earned / n,
        "free": free,
        "our_crash": our_crash,
        "dealt": dealt / n,
        "taken": taken / n,
    }


def main() -> None:
    patterns = sys.argv[1:] or ["artifacts/eval/cutoff_*.csv"]
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(Path(p) for p in sorted(glob.glob(pattern)))
    results = [r for r in (load(p) for p in paths) if r]
    if not results:
        print("no eval CSVs found")
        return
    results.sort(key=lambda r: (-r["rule_rate"], -r["earned_rate"]))

    print(f"{'config':<22} {'N':>3} | {'W':>2} {'D':>2} {'L':>2} {'rule%':>7} {'earned%':>8} "
          f"{'free':>5} {'ours':>5} | {'env%':>6} | {'dealt':>6} {'taken':>6}")
    print("-" * 100)
    for r in results:
        print(f"{r['name']:<22} {r['n']:>3} | {r['rule_w']:>2} {r['rule_d']:>2} {r['rule_l']:>2} "
              f"{r['rule_rate']:>6.1%} {r['earned_rate']:>8.1%} {r['free']:>5} {r['our_crash']:>5} "
              f"| {r['env_rate']:>5.1%} | {r['dealt']:>6.3f} {r['taken']:>6.3f}")
    print("-" * 100)
    print("rule%  = competition adjudication (altitude floor = loss for whoever descends)")
    print("earned%= wins where we put target health to zero; free = cutoff self-crashes")
    print("env%   = what eval_v5_vs_bt reports today (target floor booked as a draw)")

    best = results[0]
    print(f"\nBEST: {best['name']}   rule {best['rule_rate']:.1%}  "
          f"earned {best['earned_rate']:.1%}  (N={best['n']})")
    print(f"Organizers' bar (>50% win): {'PASS' if best['rule_rate'] > 0.50 else 'FAIL'}")
    if best["rule_rate"] > 0.50 >= best["earned_rate"]:
        print("  ^ margin depends on the cutoff's self-crashes; earned alone does not clear it.")


if __name__ == "__main__":
    main()
