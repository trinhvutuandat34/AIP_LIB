"""Summarize eval_v5_vs_bt CSVs as a head-to-head table (2026-08-22).

`summarize_cutoff.py` re-adjudicates the altitude floor the way COMPETITION_RULES Sec 5 states
it, which is the right lens against a crash-prone opponent. This does the same for ordinary
mode-vs-mode runs, so a head-to-head table is read on the same scale as the cutoff table.

    python scripts/summarize_h2h.py "artifacts/eval/h2h_*.csv"
"""
from __future__ import annotations

import csv
import glob
import sys
from pathlib import Path

_TARGET_LOST = {"target altitude below min", "Target FDM output Fall"}
_OWNSHIP_LOST = {"ownship altitude below min", "Ownship FDM output Fall", "FDM Update Fail"}


def load(path: Path) -> dict | None:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if not rows:
        return None
    n = len(rows)
    w = d = l = earned = free = ours = 0
    dealt = taken = wez = 0.0
    for r in rows:
        phased = (r.get("phased_outcome") or "").strip().lower()
        end = (r.get("end_condition") or "").strip()
        dealt += float(r.get("ep_damage_dealt") or 0)
        taken += float(r.get("ep_damage_taken") or 0)
        wez += float(r.get("ep_wez_steps_phased") or 0)
        if end in _OWNSHIP_LOST:
            l += 1; ours += 1; continue
        if end in _TARGET_LOST:
            w += 1; free += 1; continue
        if phased == "win":
            w += 1; earned += 1
        elif phased == "loss":
            l += 1
        else:
            d += 1
    return {"name": path.stem, "n": n, "w": w, "d": d, "l": l,
            "earned": earned, "free": free, "ours": ours,
            "dealt": dealt / n, "taken": taken / n, "wez": wez / n}


def main() -> int:
    pats = sys.argv[1:] or ["artifacts/eval/h2h_*.csv"]
    files = sorted({Path(p) for pat in pats for p in glob.glob(pat)})
    rows = [r for r in (load(f) for f in files) if r]
    if not rows:
        print("no rows"); return 1
    rows.sort(key=lambda r: (-(r["w"] / r["n"]), r["l"] / r["n"]))
    print(f"{'config':<34}{'N':>4} | {'W':>3}{'D':>3}{'L':>3}  {'win%':>6} {'loss%':>6} "
          f"{'draw%':>6} | {'dmg dealt':>10} {'taken':>7} {'WEZ/ep':>7} | {'selfkill':>8}")
    print("-" * 122)
    for r in rows:
        n = r["n"]
        print(f"{r['name']:<34}{n:>4} | {r['w']:>3}{r['d']:>3}{r['l']:>3}  "
              f"{r['w']/n:>6.1%} {r['l']/n:>6.1%} {r['d']/n:>6.1%} | "
              f"{r['dealt']:>10.3f} {r['taken']:>7.3f} {r['wez']:>7.1f} | {r['ours']:>8}")
    print("-" * 122)
    print("win/loss re-adjudicated on the RULES Sec 5 altitude floor (below 1000 ft = loss for "
          "whoever descends);\nselfkill = episodes we ended by flying ourselves into the ground.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
