"""Score OUR side against the cutoff with the 10 G limiter REMOVED from the ownship.

WHY THIS EXISTS (2026-08-22). `GLimitedProvider` is on both the eval path and the live
submission path, but it is only FUNCTIONAL on the eval path. `GLimiter.observe()` takes dt from
`StateIndex.SIM_TIME` (state[41]); `src/dogfight/unreal/policies.py::plane_info_to_state` fills
indices 0..8 only, so on the live wire state[41] is 0.0 on every frame, dt is always 0.0, the
`dt < MIN_DT` guard returns early, and the measured load factor stays pinned at 1.0 forever.
Proven in `scripts/probe_live_g_limiter.py`: identical 12 G pull -> LOCAL clamps 97.5% of steps
and scales pitch to -0.77, LIVE clamps 0.0% and passes -1.00 straight through.

So every number in COMPETITION_PLAN.md 4.1 was measured on a G-LIMITED aircraft and the
submission flies an UNLIMITED one. This run is the missing control: same shipped config, same
seeds, same opponent binary, ownship limiter off -- i.e. what actually goes on the wire.

    python scripts/eval_vs_cutoff_ownship_unlimited.py --ownship-backend vptrack \
        --target-backend cutoff --scenario-mode match_base --episodes 50 \
        --out-csv artifacts/eval/cutoff_env_r4000_l60_nolimit.csv

Every flag of scripts/eval_vs_cutoff.py is accepted unchanged; only the ownship's g_limit is
forced to None. The CUTOFF side keeps its limiter, exactly as in the F45 baseline, so the only
variable that moves is ours.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT), str(_ROOT / "src"), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import eval_v5_vs_bt
import eval_vs_cutoff

_orig_build = eval_v5_vs_bt.build_provider


def _build(**kwargs):
    if kwargs.get("side") == "ownship":
        kwargs["g_limit"] = None
        print("[nolimit] ownship provider built WITHOUT the 10 G limiter "
              "(live-path parity -- see module docstring)", flush=True)
    return _orig_build(**kwargs)


eval_v5_vs_bt.build_provider = _build
eval_vs_cutoff.main()
