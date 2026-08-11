"""Benchmark any opponent, and re-score the configs we shelved for lack of one.

WHY THIS EXISTS. Every number this project has is measured against ourselves: our own BT
(which cannot point -- it strands at 4.4 deg and never fires) or our own controller in
self-play (symmetric by construction, so any edge cancels exactly). Neither can answer the
question the cutoff actually asks. The organizers are gating entry on a committee-built model
of "적당한 성능" (COMPETITION_RULES.md Sec 5.1): under proposal 1 only teams that BEAT it
advance, and a DRAW DOES NOT QUALIFY -- while a draw is our modal self-play outcome (53%).

So the moment that model exists, these runs should happen immediately and in this order.

IT ALSO RE-TESTS WHAT WE SHELVED. Two configs were measured null and defaulted off for a
reason that an opponent may invert:

  * defensive break -- denies 36% of damage taken and zeroes deaths, but costs offence
    almost exactly 1:1, so it is a wash in a SYMMETRIC fight. Against an opponent that
    OUT-shoots us, trading 1:1 is a gain, not a wash.
  * throttle control -- measured harmful in self-play (5W/11L), but that was against an
    opponent with our exact closure behaviour.

Both are one flag away and both should be re-measured rather than assumed.

USAGE
    python scripts/bench_opponent.py --opponent-dll THEIR.dll
    python scripts/bench_opponent.py --opponent-backend bt --episodes 30

The opponent enters as a DLL (drop theirs in and name it) or as any backend this harness
already knows. Everything runs on match_base -- the confirmed competition geometry -- and is
scored by the competition's own rule (damage differential at timeout).
"""
from __future__ import annotations
import argparse, subprocess, sys, csv, math, io

# Force UTF-8 on stdout/stderr. This file's help text quotes the rules in Korean, and when
# stdout is redirected to a file Python falls back to the Windows ANSI codepage (cp1252) and
# even `--help` raises UnicodeEncodeError. Third occurrence of this class in one session
# (train_curriculum.py, my_submission.py, here), so it is applied to every new entry point
# by default rather than after it bites.
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, io.UnsupportedOperation):
        pass
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "scripts" / "eval_v5_vs_bt.py"
OUT = ROOT / "artifacts" / "eval" / "bench_opponent"

# name -> extra ownship flags. Champion first; the rest are the shelved configs whose verdict
# an out-shooting opponent could flip.
ARMS = {
    "champion":        [],
    "defensive_break": ["--ownship-vptrack-defensive", "1"],
    "throttle_on":     ["--ownship-vptrack-throttle", "1"],
    "both":            ["--ownship-vptrack-defensive", "1", "--ownship-vptrack-throttle", "1"],
    "bt_only":         [],   # backend override below -- the no-RL, no-controller floor
}


def score(path: Path) -> dict | None:
    if not path.exists():
        return None
    rows = list(csv.DictReader(open(path)))
    if not rows:
        return None
    n = len(rows)
    c = Counter(r["phased_outcome"] for r in rows)
    w, d, l = c.get("win", 0), c.get("draw", 0), c.get("loss", 0)
    return {
        "n": n, "w": w, "d": d, "l": l,
        "win_pct": 100.0 * w / n,
        "se": 100.0 * math.sqrt((w / n) * (1 - w / n) / n),
        "kills": sum(1 for r in rows if r["outcome"] == "win"),
        "deaths": sum(1 for r in rows if r["outcome"] == "loss"),
        "dealt": sum(float(r["ep_damage_dealt"]) for r in rows),
        "taken": sum(float(r["ep_damage_taken"]) for r in rows),
    }


def main() -> int:
    # __doc__ carries literal '%' (win rates); argparse %-formats help text, so escape it.
    ap = argparse.ArgumentParser(description=(__doc__ or '').replace('%', '%%'),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--opponent-dll", help="Opponent BT DLL, e.g. the committee model. Must sit in Release/.")
    ap.add_argument("--opponent-backend", default="bt",
                    choices=["bt", "vptrack", "rl", "hybrid", "hybrid_gated"],
                    help="How the opponent is driven (default bt: a plain BT reading its DLL).")
    ap.add_argument("--opponent-bundle-dir", help="Required if --opponent-backend needs a policy.")
    ap.add_argument("--episodes", type=int, default=30, help="N per arm. Keep >=30: the harness is bimodal.")
    ap.add_argument("--arms", default="champion,defensive_break,throttle_on,both",
                    help="Comma-separated subset of: " + ",".join(ARMS))
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        if arm not in ARMS:
            print(f"[bench] unknown arm {arm!r}, skipping"); continue
        out_csv = OUT / f"{arm}.csv"
        cmd = [args.python, str(EVAL),
               "--ownship-backend", "bt" if arm == "bt_only" else "vptrack",
               "--target-backend", args.opponent_backend,
               "--episodes", str(args.episodes),
               "--scenario-mode", "match_base",
               "--out-csv", str(out_csv)]
        if args.opponent_dll:
            cmd += ["--target-bt-dll", args.opponent_dll]
        if args.opponent_bundle_dir:
            cmd += ["--target-bundle-dir", args.opponent_bundle_dir]
        cmd += ARMS[arm]
        print(f"[bench] {arm}: running {args.episodes} episodes ...", flush=True)
        log = OUT / f"{arm}.log"
        with open(log, "w") as fh:
            rc = subprocess.call(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=str(ROOT))
        s = score(out_csv)
        if s is None:
            print(f"[bench] {arm}: FAILED (rc={rc}), see {log}")
            continue
        results[arm] = s

    if not results:
        print("[bench] nothing scored."); return 1

    print("\n=== vs opponent, match_base, competition scoring (damage differential at timeout) ===")
    print(f"{'arm':<18} {'W':>3} {'D':>3} {'L':>3} {'win%':>15} {'kills':>6} {'deaths':>7} {'dmg dealt/taken':>18}")
    for arm, s in sorted(results.items(), key=lambda kv: -kv[1]["win_pct"]):
        print(f"{arm:<18} {s['w']:>3} {s['d']:>3} {s['l']:>3} "
              f"{s['win_pct']:>8.1f}% +/-{s['se']:>4.1f} {s['kills']:>6} {s['deaths']:>7} "
              f"{s['dealt']:>8.2f}/{s['taken']:<8.2f}")

    best = max(results.items(), key=lambda kv: kv[1]["win_pct"])
    champ = results.get("champion")
    print(f"\n  best arm: {best[0]} at {best[1]['win_pct']:.1f}%")
    if champ and best[0] != "champion":
        gap = best[1]["win_pct"] - champ["win_pct"]
        sig = gap > 2.0 * math.hypot(best[1]["se"], champ["se"])
        print(f"  vs champion: {gap:+.1f} pp -- {'SIGNIFICANT, switch the default' if sig else 'inside noise, keep the champion'}")
    if champ and champ["win_pct"] <= 50.0:
        print("  WARNING: champion does not beat this opponent. Under cutoff proposal 1 a draw "
              "does not advance -- this is the number that must exceed 50%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
