"""Wire-faithful, HEADLESS regression test for the two live-path frame bugs.

WHY THIS EXISTS. `LIVE_INFERENCE_FRAME_BUGS.md` §5 item 3 records the gap this closes:

    "No local harness exists that can even test these bugs. CutoffProvider would need to be
     modified to deliberately reproduce Unreal's raw-metre/up-positive-altitude feed (rather
     than feeding local-convention state directly) to give the fix something to correct
     locally. Building that 'wire-format-faithful' local harness is the way to get a fast,
     headless regression test instead of relying entirely on live connections."

Every eval this project has ever run constructs a real local `sim`, which routes through
`ai_pilot.Step()` -> `ChangeData()` -- the CORRECT-geometry branch. The live path
(`StepWithPlaneData`, taken when `context.sim is None`) has never been exercised by any local
measurement, which is precisely why both bugs survived to a real match. Testing it previously
required `DogFightViewer.exe` (crashes on a headless/no-GPU box -- confirmed 2026-08-20) or the
organizers' server address (unreleased, F27). This script needs neither.

WHAT IT MEASURES, AND WHY THAT IS THE DECISIVE NUMBER. It feeds the native BT the exact bytes the
live path feeds it, then reads back what the tree ITSELF believes the range is, out of the
blackboard, via GateTrace.h's `distance_m` column (AIP_BASE_gatetrace.dll). Every tactical gate in
the tree is threshold-gated on that one value (`DECO_DistanceCheck` at 152.4/914/2000/2500/3000 m,
and LOS/AngleOff checks computed from the same corrupted vector), so if it is wrong, the entire
tactical layer is choosing branches against a fictional geometry -- no separate per-gate test is
needed. Ground truth is the raw Unreal Cartesian separation, which IS metres.

INPUT IS REAL WIRE DATA, not synthetic: MT_PlaneInfo packets captured from an actual server
session (logs/unreal_packets/), decoded with the project's own `unpack_plane_info`.

USAGE
    python scripts/verify_live_frame_fix.py
    python scripts/verify_live_frame_fix.py --capture logs/unreal_packets/<file>.jsonl --pairs 40

Exit code 0 = fix verified (broken geometry reproduced AND corrected), 1 = verification failed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

DEFAULT_CAPTURE = "logs/unreal_packets/rx_packets_20260514_155232_15208.jsonl"
# Tolerance on "the tree now sees the true range". The live wire path stores position in
# OPlaneData.LocationX/Y as c_float (native_bt.py:80-82) and _pack_plane_data_buffer packs the
# target with "fffffffifff" -- also float32. Encoding a latitude (~37.9) in float32 quantises to
# ~2.4e-6 deg ~= 0.27 m, where encoding a raw metre value (~500) quantises to ~3e-5 m. So the fix
# trades ~0.3 m of position precision for correct geometry: irrelevant against gates at 152 m and
# up (and ~0.03 deg at 500 m against a 1 deg gun gate), but it is why this is not exact.
ABS_TOL_M = 5.0
REL_TOL = 0.02


def _load_plane_info_pairs(capture: Path, max_pairs: int):
    """Decode MT_PlaneInfo packets and pair the two aircraft by frame index."""
    from dogfight.unreal.protocol import unpack_plane_info

    by_index: dict[int, dict[int, object]] = {}
    order: list[int] = []
    with capture.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("message_type") != "MT_PlaneInfo" or "hex" not in rec:
                continue
            try:
                raw = bytes.fromhex(rec["hex"].replace(" ", ""))
                pi = unpack_plane_info(raw)
            except Exception:
                continue
            slot = by_index.setdefault(pi.index, {})
            if pi.index not in order:
                order.append(pi.index)
            slot[pi.plane_id] = pi

    pairs = []
    for idx in order:
        slot = by_index[idx]
        if len(slot) >= 2:
            ids = sorted(slot)[:2]
            pairs.append((slot[ids[0]], slot[ids[1]]))
        if len(pairs) >= max_pairs:
            break
    return pairs


def _true_separation_m(a, b) -> float:
    """Ground truth: raw Unreal position IS local Cartesian metres."""
    return math.dist(
        (a.position.x, a.position.y, a.position.z),
        (b.position.x, b.position.y, b.position.z),
    )


def _read_trace_distances(trace: Path, plane_id: int):
    if not trace.exists():
        return []
    out = []
    with trace.open("r", encoding="utf-8", errors="replace") as fh:
        for row in csv.DictReader(fh):
            try:
                if int(row["id"]) == plane_id:
                    out.append((int(row["tick"]), float(row["distance_m"])))
            except (KeyError, ValueError):
                continue
    return out


def _check_wrapper_engages(pair) -> bool:
    """Bug 1 + activation check: does LiveVerticalFrameProvider actually fire, and only live?

    A correct transform installed where it never executes is worth nothing -- this project has
    already shipped exactly that failure once (the 10 G limiter was "present in the tree, wired
    into nothing", run_local_dogfight.py:164-168). The distance test above calls the transform
    function directly, so it would still pass if the WRAPPER were inert. This closes that gap,
    and covers bug 1 (state[2] sign), which the distance test does not touch.
    """
    import numpy as np

    from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult
    from dogfight.ai.native_bt import AIPilot
    from student.live_frame_fix import LiveVerticalFrameProvider

    seen: dict[str, object] = {}

    class _Spy(ActionProvider):
        def compute_action(self, context: ActionContext) -> ActionResult:
            seen["state2"] = float(context.ownship_state[2])
            seen["locx"] = float(context.info["my_plane_data"].LocationX)
            return ActionResult(action=np.zeros(4, dtype=np.float32), source="spy")

    me, tgt = pair
    state = np.zeros(9, dtype=np.float64)
    state[2] = 1234.0  # Unreal sends altitude up-positive; local consumers read state[2] as NED Down
    pd = AIPilot.BuildPlaneData([me.position.x, me.position.y, me.position.z], [0, 0, 0], 200.0, 1)

    def run(sim):
        seen.clear()
        wrapped = LiveVerticalFrameProvider(_Spy())
        wrapped.compute_action(ActionContext(
            sim=sim, opponent_sim=sim, ownship_state=state.copy(), target_state=state.copy(),
            observation=None,
            info={"my_plane_data": pd, "target_plane_data": pd},
        ))
        return dict(seen)

    live = run(None)          # live discriminator: sim is None
    local = run(object())     # local sim present -> must be a transparent pass-through

    live_flipped = live["state2"] == -1234.0
    live_lla = abs(live["locx"] - _ORI_LAT_GUARD) < 1.0        # metres -> ~37.9 deg latitude
    local_untouched = local["state2"] == 1234.0 and local["locx"] == float(pd.LocationX)

    print()
    print("wrapper engagement check")
    print(f"  live  (sim=None) : state[2] {1234.0:+.1f} -> {live['state2']:+.1f}"
          f"   LocationX {float(pd.LocationX):.2f} -> {live['locx']:.5f}"
          f"   {'OK' if live_flipped and live_lla else 'XX'}")
    print(f"  local (sim set)  : untouched pass-through            "
          f"                     {'OK' if local_untouched else 'XX'}")
    return bool(live_flipped and live_lla and local_untouched)


_ORI_LAT_GUARD = 37.91455691666666  # CPPBehaviorTree.h:18 -- corrected LocationX must land here


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--pairs", type=int, default=25)
    ap.add_argument("--dll", default="AIP_BASE_gatetrace.dll",
                    help="must be a GateTrace-instrumented build; that is what exposes "
                         "the blackboard Distance this test reads")
    ap.add_argument("--trace-out", default="artifacts/eval/live_frame_verify_trace.csv")
    args = ap.parse_args()

    capture = (ROOT / args.capture) if not os.path.isabs(args.capture) else Path(args.capture)
    if not capture.exists():
        print(f"FAIL: capture not found: {capture}")
        return 1

    trace = (ROOT / args.trace_out) if not os.path.isabs(args.trace_out) else Path(args.trace_out)
    trace.parent.mkdir(parents=True, exist_ok=True)
    for stale in (trace, Path(str(trace) + ".nodes.txt")):
        if stale.exists():
            stale.unlink()

    # GateTrace.h reads this ONCE per process (static), so it must be set before the DLL loads.
    os.environ["AIP_BT_GATE_TRACE"] = str(trace)
    os.environ["AIP_BT_GATE_TRACE_FIRST"] = "100000"  # log every tick, not just the first 300

    pairs = _load_plane_info_pairs(capture, args.pairs)
    if len(pairs) < 2:
        print(f"FAIL: fewer than 2 usable PlaneInfo pairs decoded from {capture.name}")
        return 1

    from dogfight.ai.native_bt import AIPilot
    from student.live_frame_fix import _unreal_xy_to_fake_lla

    pilot = AIPilot(args.dll)
    # Wire-faithful: the live path registers the tree under REMOTE_BT_FIGHTER_ID = 0
    # (bt_action_provider.py:9,122) and AIPilot.BuildPlaneData hardcodes Resv0 = 0.0, which is
    # the id the DLL looks the tree up by. Using anything else here gets "No BT found for MyID".
    from dogfight.ai.bt_action_provider import REMOTE_BT_FIGHTER_ID

    MY_ID, MY_SIDE, TGT_SIDE = REMOTE_BT_FIGHTER_ID, 1, 2
    pilot.CreateBehaviorTree(MY_ID, MY_SIDE)

    def step(me, tgt, *, fix: bool):
        mx, my_ = (_unreal_xy_to_fake_lla(me.position.x, me.position.y) if fix
                   else (me.position.x, me.position.y))
        tx, ty = (_unreal_xy_to_fake_lla(tgt.position.x, tgt.position.y) if fix
                  else (tgt.position.x, tgt.position.y))
        mine = AIPilot.BuildPlaneData([mx, my_, me.position.z],
                                      [me.rotation.roll, me.rotation.pitch, me.rotation.yaw],
                                      200.0, MY_SIDE)
        theirs = AIPilot.BuildPlaneData([tx, ty, tgt.position.z],
                                        [tgt.rotation.roll, tgt.rotation.pitch, tgt.rotation.yaw],
                                        200.0, TGT_SIDE)
        return pilot.StepWithPlaneData(mine, theirs)

    # Phase 1: exactly what ships TODAY on the live path if live_frame_fix is not installed.
    n_broken = 0
    for me, tgt in pairs:
        step(me, tgt, fix=False)
        n_broken += 1
    # Phase 2: the same geometry through student/live_frame_fix.py's inverse transform.
    for me, tgt in pairs:
        step(me, tgt, fix=True)

    pilot.RemoveBT(MY_ID)

    rows = _read_trace_distances(trace, MY_ID)
    if len(rows) < n_broken + len(pairs):
        print(f"FAIL: expected >= {n_broken + len(pairs)} trace rows for id={MY_ID}, "
              f"got {len(rows)}. Is {args.dll} a GateTrace build?")
        return 1
    rows.sort()
    seen_broken = [d for _, d in rows[:n_broken]]
    seen_fixed = [d for _, d in rows[n_broken:n_broken + len(pairs)]]
    truth = [_true_separation_m(a, b) for a, b in pairs]

    print(f"capture      : {capture.name}")
    print(f"pairs        : {len(pairs)}  (real MT_PlaneInfo frames, both aircraft present)")
    print(f"dll          : {args.dll}")
    print()
    print(f"{'#':>3}  {'true sep (m)':>13}  {'BT sees, UNFIXED':>19}  {'BT sees, FIXED':>16}  ok")
    print("-" * 66)
    ok_count = 0
    for i, (t, b, f) in enumerate(zip(truth, seen_broken, seen_fixed)):
        ok = abs(f - t) <= max(ABS_TOL_M, REL_TOL * t)
        ok_count += ok
        if i < 12:
            print(f"{i:>3}  {t:>13.1f}  {b:>19,.0f}  {f:>16.1f}  {'OK' if ok else 'XX'}")
    if len(truth) > 12:
        print(f"     ... {len(truth) - 12} more")
    print("-" * 66)

    med_broken_ratio = sorted(b / t for b, t in zip(seen_broken, truth))[len(truth) // 2]
    print()
    print(f"UNFIXED: median {med_broken_ratio:,.0f}x the true range "
          f"-- every DECO_DistanceCheck/LOSCheck in the tree is gated on this")
    print(f"FIXED  : {ok_count}/{len(truth)} within max({ABS_TOL_M} m, {REL_TOL:.0%})")

    wrapper_ok = _check_wrapper_engages(pairs[0])

    bug_reproduced = med_broken_ratio > 1000.0
    fix_works = ok_count == len(truth)
    print()
    if bug_reproduced and fix_works and wrapper_ok:
        print("PASS -- bug 2 reproduced on the live path, live_frame_fix.py corrects it, "
              "and the wrapper engages on live contexts / passes through on local ones.")
        return 0
    if not wrapper_ok:
        print("FAIL -- LiveVerticalFrameProvider did not behave correctly as a wrapper. "
              "A correct transform that never runs is worth nothing (cf. the G-limiter, which "
              "shipped INERT for weeks: run_local_dogfight.py:164-168).")
    if not bug_reproduced:
        print("FAIL -- could not reproduce the broken geometry; this test is not measuring "
              "what it claims. Do NOT read a subsequent PASS as meaningful.")
    if not fix_works:
        print("FAIL -- the fix did not restore true range on every sample.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
