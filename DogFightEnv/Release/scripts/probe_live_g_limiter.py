"""Is the shipped 10 G limiter alive on the LIVE wire? (2026-08-22)

`student/my_submission.py` wraps every backend in `GLimitedProvider`, and `student/g_limiter.py`
exists specifically to stop a train/deploy divergence: the sim hands out up to 14.86 G against a
9 G airframe, so anything tuned locally against 15 G behaves differently on a server that clamps.

`GLimiter.observe()` derives load factor from a velocity difference and needs dt, which it takes
from `StateIndex.SIM_TIME` (state[41]). On the LIVE path the state vector is built by
`src/dogfight/unreal/policies.py::plane_info_to_state`, which fills indices 0..8 and nothing else
-- state[41] is 0.0 on every frame. dt is therefore always 0.0, `dt < MIN_DT` returns early on
every call, `last_n` never leaves its 1.0 initial value, and the limiter never clamps anything.

Second, smaller defect on the same lines: `_vel_neu` reads VZ as NED-down and negates it, but the
live wire sends velocity.z UP-positive (verified from `logs/unreal_packets/
rx_packets_20260514_155232_15208.jsonl`: corr(pitch, vz) = +0.84, corr(dz, vz) = +0.73). So even
with dt repaired, the vertical component would enter the acceleration estimate sign-flipped.
`student/live_frame_fix.py` corrects state[2] but not state[8], and it sits INSIDE the limiter
anyway -- `GLimitedProvider` reads `context.ownship_state` before the correction is applied.

This prints the two paths side by side under an identical, unambiguous ~12 G pull.

    python scripts/probe_live_g_limiter.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from dogfight.sim.state_schema import StateIndex
from student.g_limiter import G_LIMIT, GLimiter

DT = 1.0 / 60.0
SPEED_MPS = 250.0
TARGET_G = 12.0


def _live_state(vx: float, vy: float, vz: float) -> np.ndarray:
    """Exactly what plane_info_to_state() produces: indices 0..8 set, everything else zero."""
    s = np.zeros(51, dtype=np.float32)
    s[StateIndex.VX], s[StateIndex.VY], s[StateIndex.VZ] = vx, vy, vz
    return s


def _local_state(vx: float, vy: float, vz: float, t: float) -> np.ndarray:
    s = _live_state(vx, vy, vz)
    s[StateIndex.SIM_TIME] = t          # FighterSim.py:224 fills this; the live path does not
    return s


def _velocity_at(step: int) -> tuple[float, float, float]:
    """A steady ~12 G turn in the vertical plane, at constant speed."""
    omega = TARGET_G * 9.80665 / SPEED_MPS
    th = omega * DT * step
    return SPEED_MPS * np.cos(th), 0.0, -SPEED_MPS * np.sin(th)   # VZ NED-down


def main() -> int:
    rows = []
    for label, make in (
        ("LIVE  (wire state: SIM_TIME never filled)", lambda i: _live_state(*_velocity_at(i))),
        ("LOCAL (sim state:  SIM_TIME filled)      ", lambda i: _local_state(*_velocity_at(i), i * DT)),
    ):
        lim = GLimiter(limit_g=G_LIMIT)
        cmd = [lim.limit_pitch(-1.0, make(i)) for i in range(40)]
        rows.append((label, lim.last_n, lim.clamp_fraction, cmd[-1]))
        print(f"{label}  measured_n={lim.last_n:7.3f}  clamped={lim.clamp_fraction:6.1%}  "
              f"pitch_cmd_out={cmd[-1]:+.4f}  (commanded -1.0000)")

    live, local = rows[0], rows[1]
    ok = live[2] == 0.0 and local[2] > 0.5
    print()
    if ok:
        print(f"VERDICT: the {G_LIMIT:.0f} G limiter is INERT on the live path and ACTIVE locally.")
        print("         Every number in COMPETITION_PLAN.md 4.1 was measured on a LIMITED")
        print("         aircraft; the submission flies an UNLIMITED one.")
    else:
        print(f"VERDICT: the {G_LIMIT:.0f} G limiter behaves the same on both paths.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
