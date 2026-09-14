"""Per-matchup report over the whole league matrix, plus a robustness ranking.

    python scripts/matrix_report.py
    python scripts/matrix_report.py --scenario match_base --candidates ship_6000_120_deck standoff220_deck

Complements `league.py --summarize`, which ranks candidates but prints one aggregate per cell.
This prints the full per-matchup vector the selection actually needs -- damage both ways, kill
rate, survival, missed opportunities -- and then flags the failure PATTERN in each cell, because
"we lose this matchup" and "we lose it by never pointing" call for different fixes.

SCORING IS league.py's. `_load` is imported, not restated: it carries the 2026-09-08 crash
bucketing fixes, and a second opinion about what counts as a win is exactly how this project got
into trouble twice before.

TWO THINGS THE RANKING WILL NOT DO FOR YOU.

1. Self-play columns are excluded from the floor, via league's own `_is_selfplay`. `aggressor` is
   parameter-for-parameter identical to `ship_6000_120_deck` and `mirror` to `prev_6000_90`, so
   those cells are pinned near 50% by construction. They cannot be won, and a large deviation
   from ~50% means a side-dependent bug rather than an improvement. They stay in MEAN (so the
   number is comparable to the F-register) but never decide WORST.
2. `sniper` is a low-confidence analogue for GoGoSSung AND HAnnamAir, `aggressor` for Fight's on!
   -- built from a handful of broadcast episodes, not replicas. A column reading "94%" is not a
   claim about that team. And `cutoff` is the organizers' entry benchmark, never played in the
   tournament at all.

ROBUSTNESS is what the brief asks for: the ranking key is mean BO3 points, then the minimax floor
over non-self-play columns, then lower draw rate. A config that wins one column and regresses
another loses to one that is merely good everywhere -- which is the whole point of a floor.
"""
from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent), str(_HERE.parent / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from league import ARCHETYPES, CANDIDATES, _is_selfplay, _load  # noqa: E402

_OUT = _HERE.parent / "artifacts" / "eval"
_NEEDED = ("phased_outcome", "end_condition", "ep_wez_steps", "ep_damage_dealt",
           "ep_damage_taken", "ownship_health", "target_health")


def clean(path: Path):
    rows, dropped, header = [], 0, None
    with path.open(encoding="utf-8", errors="replace") as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames
        for r in rd:
            if any(r.get(k) in (None, "") for k in _NEEDED):
                dropped += 1
                continue
            rows.append(r)
    if not header or not rows:
        return [], dropped, None
    tmp = Path(tempfile.gettempdir()) / f"mx_{path.stem}.csv"
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return rows, dropped, tmp


def extras(rows: list[dict]) -> dict:
    n = len(rows)
    g = lambda k: [float(r[k]) for r in rows]
    return dict(
        nopoint=sum(1 for r in rows if float(r["ep_wez_steps"]) == 0) / n,
        died=sum(1 for r in rows if r["end_condition"] == "ownship destroyed") / n,
        deck=sum(1 for r in rows if r["end_condition"] == "ownship altitude below min") / n,
        hp=sum(g("ownship_health")) / n,
        timeout=sum(1 for r in rows if r["end_condition"] == "max time out") / n,
    )


def weakness(s: dict, x: dict) -> str:
    """Name the failure pattern, not just the fact of losing."""
    bits = []
    if x["nopoint"] >= 0.30:
        bits.append(f"never points in {x['nopoint']:.0%}")
    if s["diff"] < -0.05:
        bits.append(f"out-damaged {s['diff']:+.3f}")
    if x["died"] >= 0.15:
        bits.append(f"shot down {x['died']:.0%}")
    if x["deck"] >= 0.08:
        bits.append(f"own floor {x['deck']:.0%}")
    if x["timeout"] >= 0.50 and abs(s["diff"]) < 0.05:
        bits.append(f"stalemate {x['timeout']:.0%} timeouts")
    return "; ".join(bits) or "-"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="match_base")
    ap.add_argument("--candidates", nargs="*", default=None)
    a = ap.parse_args()

    cands = a.candidates or list(CANDIDATES)
    archs = list(ARCHETYPES)
    table: dict[str, dict[str, tuple]] = {}

    for c in cands:
        for arch in archs:
            p = _OUT / f"league_{a.scenario}__{c}__vs__{arch}.csv"
            if not p.is_file():
                continue
            rows, drop, tmp = clean(p)
            if not rows:
                continue
            table.setdefault(c, {})[arch] = (_load(tmp), extras(rows), drop)

    if not table:
        print("no matrix CSVs found yet")
        return 1

    for c in [c for c in cands if c in table]:
        print(f"\n=== {c}")
        print(f"    {'opponent':10s} {'n':>4} {'bo3':>5} {'W-D-L':>10} {'kills':>6} "
              f"{'dealt':>7} {'taken':>7} {'NET':>7} {'wez':>6} {'nopoint':>8} {'HP':>6}  weakness")
        for arch in archs:
            if arch not in table[c]:
                continue
            s, x, drop = table[c][arch]
            sp = " (self-play)" if _is_selfplay(c, arch) else ""
            print(f"    {arch:10s} {s['n']:>4} {s['bo3_points']:>5.2f} "
                  f"{f'{s[chr(119)]}-{s[chr(100)]}-{s[chr(108)]}':>10} {s['kills']:>6} "
                  f"{s['dealt']:>7.3f} {s['taken']:>7.3f} {s['diff']:>+7.3f} "
                  f"{s['wez_rate']:>6.0%} {x['nopoint']:>8.0%} {x['hp']:>6.2f}  "
                  f"{weakness(s, x)}{sp}")

    print("\n\n=== ROBUSTNESS RANKING  (mean BO3 -> minimax floor over non-self-play -> fewer draws)")
    ranked = []
    for c, per in table.items():
        pts = [per[x][0]["bo3_points"] for x in per]
        floor_cols = [x for x in per if not _is_selfplay(c, x)] or list(per)
        floor = min(per[x][0]["bo3_points"] for x in floor_cols)
        draw = sum(per[x][0]["draw_rate"] for x in per) / len(per)
        ns = {per[x][0]["n"] for x in per}
        ranked.append((sum(pts) / len(pts), floor, -draw, c, len(per), ns))
    ranked.sort(reverse=True)
    print(f"    {'candidate':24s} {'cells':>6} {'mean':>7} {'floor':>7} {'draw':>7}   N")
    for mean, floor, ndraw, c, cells, ns in ranked:
        warn = "  !! MIXED N" if len(ns) > 1 else ""
        print(f"    {c:24s} {cells:>6} {mean:>7.2f} {floor:>7.2f} {-ndraw:>7.1%}   {sorted(ns)}{warn}")
    print("\n    Floor excludes self-play columns (league._is_selfplay): a symmetric matchup is")
    print("    pinned near 50% and cannot be won. Compare candidates only at equal cell counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
