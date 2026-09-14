"""Does the match clock survive a wire that carries no clock?

    python scripts/test_match_clock.py

WHY. `plane_info_to_state()` fills only state indices 0-8 (position, rotation, velocity) because
that is all the wire struct "<iQb3f3f3f" carries. StateIndex.SIM_TIME is index 41, so it is
PERMANENTLY ZERO in competition while being perfectly real in the local simulator. Anything keyed
on it passes every benchmark and does nothing on match day.

That already broke DECK_TTC_S: it finite-differences altitude over dt taken from SIM_TIME, so
live dt is 0.0, the _DECK_DT_MIN_S guard rejects every sample, and the time-to-impact deck guard
can never fire. This test pins the repair.

Asserted here:
  1. With SIM_TIME populated (simulator), the clock returns SIM_TIME unchanged, so every existing
     measurement stays bit-identical.
  2. With SIM_TIME zero (live wire), the clock advances from the frame count instead of being
     stuck at 0.0 -- and 0.0 is the dangerous value, because it reads as "Phase 1 forever".
  3. The SERVER's frame index, when the context carries one, outranks our own call count --
     it is monotonic and cannot drift on a double-step or a dropped frame.
  4. reset() clears both, so episodes stay independent (the E1-leaks class).
"""
from __future__ import annotations
import sys
from pathlib import Path
_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE.parent / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np
from dogfight.sim.state_schema import StateIndex
from student.controller_providers import VPTrackingProvider, TICK_HZ, phase_window


def _p():
    p = object.__new__(VPTrackingProvider)
    p._ticks = 0
    p._frame_index = None
    return p


def main() -> int:
    st = np.zeros(int(max(StateIndex)) + 1, dtype=float)

    # 1. simulator: SIM_TIME populated and preferred
    prov = _p()
    st[StateIndex.SIM_TIME] = 137.5
    assert prov._match_time_s(st) == 137.5, "SIM_TIME must win when it is real"
    prov._ticks = 99999
    assert prov._match_time_s(st) == 137.5, "the counter must not override a real SIM_TIME"

    # 2. live wire: SIM_TIME is zero, the counter carries the clock
    prov = _p()
    st[StateIndex.SIM_TIME] = 0.0
    assert prov._match_time_s(st) == 0.0
    prov._ticks = int(120 * TICK_HZ)
    got = prov._match_time_s(st)
    assert abs(got - 120.0) < 1e-9, f"counted clock gave {got}, expected 120.0"
    # and it must actually move the phase, which is the whole point
    assert phase_window(got)[1] == 2.0, "at t=120 s the live clock must select Phase 2"
    assert phase_window(prov._match_time_s(st))[0] > phase_window(0.0)[0]

    # 2b. THE SERVER'S OWN COUNTER OUTRANKS OURS. Both live sites in
    # dogfight/unreal/policies.py pass info={"frame_index": ...}; that is monotonic and cannot
    # drift if the harness double-steps or drops a frame, which counting our own calls can.
    prov = _p()
    st[StateIndex.SIM_TIME] = 0.0
    prov._ticks = 10             # deliberately WRONG, as a dropped-frame harness would leave it
    prov._frame_index = int(150 * TICK_HZ)
    got = prov._match_time_s(st)
    assert abs(got - 150.0) < 1e-9, f"server frame index ignored: got {got}, expected 150.0"
    assert phase_window(got)[1] == 3.0, "at t=150 s the server clock must select Phase 3"

    # 3. episode independence
    prov._ticks = 5000
    prov._los_error_sum = 1.0
    prov._prev_range_m = 10.0
    VPTrackingProvider.reset(prov, None) if hasattr(VPTrackingProvider, "reset") else None
    assert prov._ticks == 0, "reset() must clear the frame count or episodes leak into each other"
    assert prov._frame_index is None, "reset() must clear the cached server frame index too"

    print(f"OK  SIM_TIME preferred when real; live wire falls back to the frame count "
          f"({int(120 * TICK_HZ)} ticks -> 120.0 s -> Phase 2); reset clears it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
