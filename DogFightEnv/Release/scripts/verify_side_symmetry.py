"""Does the shipped config fly the same when the engagement is mirrored left-for-right?

WHY THIS EXISTS. Blue/Red alternates every game in the 본선 (COMPETITION_RULES.md 5.1), so half
of every match is flown from the mirrored geometry. A config with a left/right bias therefore
throws away half its games, and nothing in the eval harness could previously have seen it --
`apply_match_scenario()` draws the mirror randomly and, until 2026-09-04, did not record which
way it went, so a bias averaged into the noise instead of showing up as a column.

This is not hypothetical. `ShorterTurnDirection` picked its turn side by fore/aft instead of
left/right (c0f3eaf) and was shipped that way. That bug lived in the native BT; this check
covers the whole stack, because it compares OUTCOMES rather than reading code.

TWO MODES, and they cost very different amounts:

  --from-csv PATH...   FREE. Slices runs that already exist by their logged `initial_side` and
                       compares the two halves. Works on any CSV written after 2026-09-04. Use
                       this on the league matrix output -- it needs no extra episodes at all.
                       Weaker evidence: the two halves are different engagements, so a
                       difference can be sampling noise rather than bias.

  (default)            DECISIVE, and costs 2N episodes. Runs the same seeds twice with the
                       mirror FORCED each way (--match-side +1 / -1). Only the two headings
                       depend on the side -- positions do not, and the baseline heading is
                       drawn from the RNG BEFORE the side is -- so the pair is an exact
                       mirror image of the same engagement. Any outcome difference beyond the
                       simulator's own determinism is a real laterality bias.

WHAT COUNTS AS A FAILURE. There is no exact-equality test here: the FDM is not bit-symmetric,
and two mirrored engagements can legitimately diverge once they are chaotic. What is reported
is the SIZE of the asymmetry against the sampling error of the same measurement, so the reader
can judge. A win-rate gap inside ~1 sigma is noise; a gap of several sigma with a consistent
sign across archetypes is a bug worth hunting.

    python scripts/verify_side_symmetry.py --from-csv artifacts/eval/league_match_base__*.csv
    python scripts/verify_side_symmetry.py --episodes 30 --ownship-vptrack-range-m 6000 ...
"""

from __future__ import annotations

import argparse
import csv
import glob
import math
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PY = sys.executable
_OUT = _ROOT / "artifacts" / "eval"


def _rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def _score(rows: list[dict]) -> dict:
    """W/D/L, win rate and mean damage differential for one side's half of a run."""
    n = len(rows)
    if not n:
        return {"n": 0}
    w = sum(1 for r in rows if (r.get("phased_outcome") or "").strip().lower() == "win")
    l = sum(1 for r in rows if (r.get("phased_outcome") or "").strip().lower() == "loss")
    diff = sum(float(r.get("ep_damage_dealt") or 0) - float(r.get("ep_damage_taken") or 0)
               for r in rows) / n
    return {"n": n, "w": w, "d": n - w - l, "l": l, "win_rate": w / n, "diff": diff}


# Below this many episodes on either side the comparison is not worth making: the sigma of a
# win rate is dominated by n, and a 3-vs-1 split will happily report several sigma of "bias".
MIN_EPISODES_PER_SIDE = 10


def _sigma_win_rate(w: int, n: int) -> float:
    """Sigma of a win rate, Agresti-Coull adjusted.

    The textbook sqrt(p(1-p)/n) COLLAPSES TO ZERO at p=0 and p=1, which makes a lopsided small
    sample look infinitely significant -- a 0-of-1 versus 2-of-3 split reported 2.4 sigma in
    testing, which is nonsense. Shrinking the rate toward 1/2 by two pseudo-counts each way
    keeps the interval honest at the edges, which is exactly where a side bias would show up.
    """
    if n <= 0:
        return float("nan")
    p_adj = (w + 2.0) / (n + 4.0)
    return math.sqrt(p_adj * (1.0 - p_adj) / (n + 4.0))


def _report(label: str, plus: dict, minus: dict) -> bool:
    """Print one comparison. Returns True if the asymmetry looks like noise."""
    if not plus.get("n") or not minus.get("n"):
        print(f"  {label:<28} SKIPPED -- one side has no episodes "
              f"(+1: {plus.get('n', 0)}, -1: {minus.get('n', 0)})")
        return True
    if plus["n"] < MIN_EPISODES_PER_SIDE or minus["n"] < MIN_EPISODES_PER_SIDE:
        print(f"  {label:<28} INSUFFICIENT -- need >={MIN_EPISODES_PER_SIDE} episodes per side "
              f"(+1: {plus['n']}, -1: {minus['n']})")
        return True
    gap = plus["win_rate"] - minus["win_rate"]
    # Sigma of the DIFFERENCE of two independent rates.
    sig = math.sqrt(_sigma_win_rate(plus["w"], plus["n"]) ** 2
                    + _sigma_win_rate(minus["w"], minus["n"]) ** 2)
    sigmas = abs(gap) / sig if sig > 0 else float("inf")
    verdict = "ok" if sigmas < 2.0 else ("SUSPECT" if sigmas < 3.0 else "BIASED")
    print(f"  {label:<28} +1: {plus['w']:>3}/{plus['d']:>3}/{plus['l']:>3} "
          f"({plus['win_rate']:>5.1%}, diff {plus['diff']:+.3f})   "
          f"-1: {minus['w']:>3}/{minus['d']:>3}/{minus['l']:>3} "
          f"({minus['win_rate']:>5.1%}, diff {minus['diff']:+.3f})   "
          f"gap {gap:+.1%} = {sigmas:.1f} sigma  [{verdict}]")
    return sigmas < 2.0


def from_csv(patterns: list[str]) -> int:
    paths: list[Path] = []
    for pat in patterns:
        paths.extend(Path(p) for p in sorted(glob.glob(pat)))
    if not paths:
        print("no CSVs matched")
        return 1

    print("SIDE SYMMETRY -- post-hoc split of existing runs by logged initial_side")
    print("(free, but the two halves are different engagements: weaker than the paired mode)\n")
    clean = True
    checked = 0
    for path in paths:
        rows = _rows(path)
        if not rows or "initial_side" not in rows[0]:
            print(f"  {path.name:<28} SKIPPED -- no initial_side column (run predates 2026-09-04)")
            continue
        plus = _score([r for r in rows if (r.get("initial_side") or "").strip() == "1"])
        minus = _score([r for r in rows if (r.get("initial_side") or "").strip() == "-1"])
        clean &= _report(path.stem, plus, minus)
        checked += 1
    if not checked:
        print("\nNothing checked: every CSV predates the initial_side column. Re-run the eval.")
        return 1
    print("\nPASS -- no side gap beyond 2 sigma" if clean else
          "\nFAIL -- at least one run shows a side gap worth investigating")
    return 0 if clean else 1


def paired(args: argparse.Namespace, passthrough: list[str]) -> int:
    print("SIDE SYMMETRY -- paired forced-mirror run (decisive; costs 2N episodes)\n")
    # The cutoff archetype lives behind its own wrapper: eval_v5_vs_bt.py's own --target-backend
    # choices deliberately EXCLUDE "cutoff" (league.py hit this same gap first -- see its entry
    # dispatch). Match that here rather than let argparse reject the run before any episode runs.
    entry = "eval_vs_cutoff.py" if args.target_backend == "cutoff" else "eval_v5_vs_bt.py"
    outs = {}
    for side in (1.0, -1.0):
        tag = "p1" if side > 0 else "m1"
        out = _OUT / f"sidesym_{args.scenario_mode}__{tag}.csv"
        cmd = [_PY, str(_HERE / entry),
               "--ownship-backend", "vptrack", "--target-backend", args.target_backend,
               "--scenario-mode", args.scenario_mode,
               "--episodes", str(args.episodes), "--seed", str(args.seed),
               "--match-side", str(side),
               "--out-csv", str(out.relative_to(_ROOT))] + passthrough
        log = out.with_suffix(".log")
        print(f"  running side {side:+.0f} -> {out.name}")
        with log.open("w", encoding="utf-8") as fh:
            rc = subprocess.call(cmd, cwd=str(_ROOT), stdout=fh, stderr=subprocess.STDOUT)
        if rc != 0:
            print(f"  FAILED (rc={rc}) -- see {log}")
            return 1
        outs[side] = _rows(out)
    print()
    ok = _report("paired forced mirror", _score(outs[1.0]), _score(outs[-1.0]))
    print("\nPASS -- mirrored engagements score the same within noise" if ok else
          "\nFAIL -- the mirror changes the result: a real laterality bias")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--from-csv", nargs="*", default=None,
                   help="glob(s) of existing eval CSVs to split by initial_side (free mode)")
    p.add_argument("--episodes", type=int, default=30)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--scenario-mode", default="match_base",
                   choices=["match_base", "match_tiebreak"])
    p.add_argument("--target-backend", default="bt")
    args, passthrough = p.parse_known_args()
    return from_csv(args.from_csv) if args.from_csv is not None else paired(args, passthrough)


if __name__ == "__main__":
    sys.exit(main())
