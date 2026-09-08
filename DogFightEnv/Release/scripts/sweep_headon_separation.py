"""Sweep the Head-On (Model 2) start separation, one league run per separation value.

WHY THIS EXISTS
---------------
Model 2 only ever plays ONE geometry: Head-On mode, which the 2026-09-03 announcement triggers
when both game 1 AND game 2 of a knockout BO5 are drawn (COMPETITION_RULES.md 5.2, 7). So it does
not need the full randomised-condition matrix that `ship_6000_120_deck` got -- it needs to be good
at one thing. The problem is that **we do not know what that one thing is**: the organizers have
never published Head-On mode's start separation.

`student/match_scenario_wrapper.py:101` therefore carries

    TIEBREAK_SEPARATION_M = float(os.environ.get("DOGFIGHT_HEADON_SEPARATION_M", "3048.0"))

and 3,048 m (10,000 ft) is an **ASSUMPTION, NOT A CITATION** -- it is inherited from a reading of
the rules that has since been SUPERSEDED (the old "round 4 = 10,000 ft head-on" interpretation,
corrected in COMPETITION_RULES.md 5.1 on 2026-09-03). Until an organizer answer lands, the honest
move is to sweep a bracket and pick a profile that is robust across it, rather than tune to a
number we made up.

THE TRAP THIS SCRIPT EXISTS TO AVOID
------------------------------------
You cannot sweep this by looping `league.py` in a shell. Three facts combine badly:

  1. Separation reaches the child ONLY as the `DOGFIGHT_HEADON_SEPARATION_M` environment
     variable, read at module IMPORT time in the child process.
  2. `league.py` does not encode separation in its output filenames -- `_csv_path()` keys on
     scenario/candidate/archetype only.
  3. `league.py` is resumable by ROW COUNT: it reads an existing CSV, counts rows, and appends
     only the shortfall.

So the second separation in a naive loop finds the first one's CSVs at the same paths, with an
IDENTICAL schema, counts their rows as progress, and appends a DIFFERENT GEOMETRY's episodes into
them -- silently averaging two separations into one number. `_RESUME_SCHEMA_COLUMNS` cannot catch
this, because the schema is genuinely the same; only the physics differs. This script gives every
separation its own output root via `DOGFIGHT_LEAGUE_OUT_DIR`, so resume stays correct per value.

USAGE
-----
    # bracket around the (assumed) 3048 m, 60 episodes per pair
    python scripts/sweep_headon_separation.py --separations 914 1524 3048 4572 --episodes 60

    # resume: re-run the IDENTICAL command; each separation continues where its CSVs left off
    python scripts/sweep_headon_separation.py --separations 914 1524 3048 4572 --episodes 60

    # just print what is already on disk, run nothing
    python scripts/sweep_headon_separation.py --separations 914 1524 3048 4572 --summarize-only

NOTES
-----
* Runs are CHUNKED (`--chunk-episodes`, default 15) for the same reason the F66 matrix was: the
  full thing does not survive as one long background command (F65). Re-running resumes.
* `JSBSimWrapper.Fighter.__init__` rewrites `aircraft/f16/f16_init.xml` on every episode reset, so
  the protected spawn preset WILL drift during this sweep. That is expected, not a bug. Run
  `python scripts/spawn_preset_guard.py --restore` before committing or packaging (F57/F65).
* Output lands in `artifacts/eval/headon_<sep>m/`, one directory per separation.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PY = sys.executable
_LEAGUE = _HERE / "league.py"

# Head-On mode is still a GAME, so the announcement's per-game altitude/speed randomisation
# applies to it too. Default to the same band the F66 matrix used, so Model 2's numbers are
# comparable with Model 1's rather than being measured under a quieter condition set.
_DEFAULT_ALT_RANGE = "1000,7700"
_DEFAULT_SPEED_RANGE = "150,280"


def _out_dir(sep_m: float) -> Path:
    """One output root per separation. This is the whole point -- see the module docstring."""
    return _ROOT / "artifacts" / "eval" / f"headon_{sep_m:g}m"


def _run_one(sep_m: float, args: argparse.Namespace, summarize_only: bool) -> int:
    out = _out_dir(sep_m)
    out.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    # Both of these must be in the CHILD's environment: the first is read at import time by
    # student/match_scenario_wrapper.py, the second by scripts/league.py.
    env["DOGFIGHT_HEADON_SEPARATION_M"] = repr(float(sep_m))
    env["DOGFIGHT_LEAGUE_OUT_DIR"] = str(out)

    cmd = [
        _PY, str(_LEAGUE),
        "--scenario-mode", "match_tiebreak",
        "--episodes", str(args.episodes),
        "--chunk-episodes", str(args.chunk_episodes),
        "--jobs", str(args.jobs),
        "--seed", str(args.seed),
        "--altitude-range", args.altitude_range,
        "--speed-range", args.speed_range,
    ]
    if args.candidates:
        cmd += ["--candidates", *args.candidates]
    if args.archetypes:
        cmd += ["--archetypes", *args.archetypes]
    if summarize_only:
        cmd += ["--summarize"]

    # NEVER pass --skip-existing here: after the first chunk every pair's CSV exists, so it would
    # stall the whole sweep silently (league.py says as much in its own help text).
    print(f"\n{'=' * 88}\n  separation {sep_m:g} m   ->  {out.relative_to(_ROOT)}\n{'=' * 88}", flush=True)
    return subprocess.call(cmd, env=env, cwd=str(_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sweep Head-On start separation for Model 2, one league run per value.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--separations", type=float, nargs="+", required=True,
        help="Separations in METRES. 3048 is the inherited ASSUMPTION (10,000 ft) from a "
             "superseded rules reading -- bracket it, do not trust it. The standard-game set for "
             "reference is 609.6/762/914.4 m (2000/2500/3000 ft).",
    )
    ap.add_argument("--episodes", type=int, default=60,
                    help="TARGET episodes per pair (not per invocation). Default 60.")
    ap.add_argument("--chunk-episodes", type=int, default=15,
                    help="Max NEW episodes per pair per invocation (F65 chunking). Default 15.")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--candidates", nargs="*", default=None,
                    help="Subset of league.py CANDIDATES. Default: all.")
    ap.add_argument("--archetypes", nargs="*", default=None,
                    help="Subset of league.py ARCHETYPES. Default: all.")
    ap.add_argument("--altitude-range", default=_DEFAULT_ALT_RANGE,
                    help=f'"lo,hi" metres, "" disables. Default {_DEFAULT_ALT_RANGE}.')
    ap.add_argument("--speed-range", default=_DEFAULT_SPEED_RANGE,
                    help=f'"lo,hi" m/s, "" disables. Default {_DEFAULT_SPEED_RANGE}.')
    ap.add_argument("--summarize-only", action="store_true",
                    help="Print each separation's existing results and run no episodes.")
    args = ap.parse_args()

    seps = list(dict.fromkeys(args.separations))   # de-dupe, keep order
    if len(seps) != len(args.separations):
        print("note: duplicate separations collapsed", file=sys.stderr)

    rc_total = 0
    for sep in seps:
        rc = _run_one(sep, args, args.summarize_only)
        if rc != 0:
            print(f"  [WARN] separation {sep:g} m exited rc={rc}", file=sys.stderr)
            rc_total = rc

    print(f"\n{'=' * 88}")
    print("  sweep pass complete. Re-run the IDENTICAL command to continue any pair that has")
    print("  not yet reached its --episodes target; chunking means a kill loses at most one chunk.")
    print(f"  Results: {', '.join(str(_out_dir(s).relative_to(_ROOT)) for s in seps)}")
    print("  REMEMBER: python scripts/spawn_preset_guard.py --restore   (the sweep drifts it)")
    print(f"{'=' * 88}")
    return rc_total


if __name__ == "__main__":
    raise SystemExit(main())
