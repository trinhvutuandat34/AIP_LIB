"""Play ONE live local match against the organizers' real cutoff binary, with --save-log support.

WHY THIS EXISTS. `run_local_dogfight.py` is the single-match, watch-it-play entry point --
`--target-backend` choices are `rl|bt|vptrack|hybrid|hybrid_vptrack|hybrid_gated|fixed`, and it is
the only local entry point that supports `--save-log` (a per-timestep Tacview-format CSV of both
aircraft's full trajectory -- position, attitude, health -- for exactly this kind of manual replay
analysis). Cutoff support has only ever existed in the batch eval harness
(`scripts/eval_vs_cutoff.py`), which has no per-timestep log, only a one-row-per-episode summary
CSV. This adds the missing combination: single live match, trajectory CSV, real cutoff opponent.

Same idiom as `eval_vs_cutoff.py` (argv rewrite around the `choices=[...]` constraint,
`build_provider` patched at import time) and the SAME F54 vertical-axis correction as
`eval_vs_cutoff_zfix.py` -- the cutoff receives up-positive altitude, matching what the real
Unreal server sends it, not the local sim's NED-down convention. `cutoff_provider.py` itself is
untouched.

    python scripts/run_local_dogfight_vs_cutoff.py --ownship-backend vptrack \\
        --ownship-vptrack-throttle 1 --ownship-vptrack-range-m 4000 --ownship-vptrack-los-deg 60 \\
        --target-backend cutoff --save-log

CSV lands in `artifacts/logs/<timestamp>_ownship_(F-16)[Blue].csv` and
`..._target_(F-16)[Red].csv` (the cutoff's own trajectory), plus a `..._summary.json`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT), str(_ROOT / "src"), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

import run_local_dogfight as rld
from cutoff_provider import CutoffProvider
from student.controller_providers import GLimitedProvider
from student.g_limiter import G_LIMIT


def _plane_fields_zfix(state):
    """As CutoffProvider._plane_fields, but z is sent up-positive -- see eval_vs_cutoff_zfix.py."""
    s = np.asarray(state, dtype=np.float64)
    s = np.nan_to_num(s, nan=0.0, posinf=0.0, neginf=0.0)
    return (
        [float(s[0]), float(s[1]), -float(s[2])],
        [float(s[3]), float(s[4]), float(s[5])],
        [float(s[6]), float(s[7]), float(s[8])],
    )


CutoffProvider._plane_fields = staticmethod(_plane_fields_zfix)

_orig_build_provider = rld.build_provider


def _build_provider(*args, **kwargs):
    if kwargs.get("backend") != "cutoff":
        return _orig_build_provider(*args, **kwargs)
    provider = CutoffProvider(
        # The cutoff flies whichever seat it's put in; force sides are BT blackboard labels
        # only, real identity comes from SetPlaneID. Matches eval_vs_cutoff.py's convention.
        own_force_side=2, target_force_side=1,
    )
    return GLimitedProvider(provider, limit_g=G_LIMIT)


rld.build_provider = _build_provider


def main() -> None:
    wanted_cutoff = {"ownship": False, "target": False}
    argv = sys.argv[1:]
    for side in ("ownship", "target"):
        flag = f"--{side}-backend"
        for i, tok in enumerate(argv):
            if tok == flag and i + 1 < len(argv) and argv[i + 1] == "cutoff":
                argv[i + 1] = "bt"
                wanted_cutoff[side] = True
            elif tok == f"{flag}=cutoff":
                argv[i] = f"{flag}=bt"
                wanted_cutoff[side] = True
    sys.argv = [sys.argv[0]] + argv

    original_parse_args = rld.parse_args

    def parse_args():
        args = original_parse_args()
        if wanted_cutoff["ownship"]:
            args.ownship_backend = "cutoff"
        if wanted_cutoff["target"]:
            args.target_backend = "cutoff"
        return args

    rld.parse_args = parse_args
    rld.main()


if __name__ == "__main__":
    main()
