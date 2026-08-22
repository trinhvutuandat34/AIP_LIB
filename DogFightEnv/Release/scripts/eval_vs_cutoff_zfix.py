"""Score against the cutoff with the vertical axis it would receive from the REAL server.

WHY (2026-08-22). `cutoff_provider._plane_fields` forwards the local sim's `state[0:3]` as the
PlaneInfo position, on the stated grounds that the provider is "the inverse of
plane_info_to_state(), so the bytes the binary receives here are the same bytes it receives from
Unreal." That claim was written 2026-08-19 and `student/live_frame_fix.py` refuted it on
2026-08-20 without the provider being revisited:

    local sim   state[2] = pm.geodetic2ned(...)[2] = NED Down, NEGATIVE above ground
    live Unreal state[2] = PlaneInfo.position.z    = altitude, POSITIVE up

Verified over 2,984 captured frames: z is positive throughout and rises with positive pitch.

So the harness hands the cutoff z = -4572 where the real server hands it +4572, and inverts the
sign of the vertical separation between the two aircraft along with it -- exactly the defect our
own aircraft carried as bug 1, aimed at the opponent instead. If the cutoff's tree uses the
vertical axis at all, every result measured against it is against a crippled opponent.

This flips only that one sign, on the cutoff's input, and changes nothing else.

    python scripts/eval_vs_cutoff_zfix.py --ownship-backend vptrack --target-backend cutoff \
        --scenario-mode match_base --episodes 50 --seed 0 \
        --ownship-vptrack-throttle 1 --ownship-vptrack-range-m 4000 --ownship-vptrack-los-deg 60 \
        --out-csv artifacts/eval/cutoff_env_r4000_l60_zfix.csv
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

import cutoff_provider
import eval_vs_cutoff


def _plane_fields_zfix(state):
    """As CutoffProvider._plane_fields, but z is sent up-positive, as the real server sends it."""
    s = np.asarray(state, dtype=np.float64)
    s = np.nan_to_num(s, nan=0.0, posinf=0.0, neginf=0.0)
    return (
        [float(s[0]), float(s[1]), -float(s[2])],   # <- the one change: NED Down -> altitude up
        [float(s[3]), float(s[4]), float(s[5])],
        [float(s[6]), float(s[7]), float(s[8])],
    )


cutoff_provider.CutoffProvider._plane_fields = staticmethod(_plane_fields_zfix)
print("[zfix] cutoff receives UP-POSITIVE altitude, as the real Unreal server sends it", flush=True)
eval_vs_cutoff.main()
