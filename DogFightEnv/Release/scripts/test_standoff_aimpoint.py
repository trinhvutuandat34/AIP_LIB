"""Does the aim-point standoff actually hold range, and is it inert when off?

    python scripts/test_standoff_aimpoint.py

WHY THIS EXISTS. STANDOFF_M is the first thing in this stack that biases the AIM POINT rather
than the throttle, and it is the intended answer to a measured defect: median ep_min_distance
19.9 m against a 152.4 m zero-damage floor, with 80/100 episodes inside that floor. Two
properties have to hold or the knob is worse than nothing:

  1. OFF IS BIT-IDENTICAL. Default 0.0 must leave `_tracking_stick` exactly as it was, or every
     register measurement taken before today silently stops comparing.
  2. NO STEP AT THE BOUNDARY. Lag is (standoff - rng), so at rng == standoff it is zero and the
     command must equal the pure-pursuit command. A knob that jumps when it engages would show
     up as a control discontinuity, not as better range keeping.

It also asserts the PHASE-1 GATE: with a qualifying shot in hand the knob must stand down
entirely, because the angle is a binary gate on 92.6% of all available damage while range is
only a smooth multiplier. And it asserts the thing the knob is FOR: on a CROSSING target inside the radius, the nose is
commanded away from the collision course toward the target's six. And it pins one known null --
the adaptive-range branch (close when we out-angle them, extend when we do not), and a
co-aligned stern chase, where sliding the aim point along the line of sight cannot rotate it,
so the stick is unchanged by construction. That is a property of this control law (roll is a
function of error DIRECTION, not magnitude), not a defect in the knob.

The provider is built with `object.__new__` and only the attributes `_tracking_stick` reads.
That is deliberate -- a real VPTrackingProvider loads AIP_BASE.dll, and this test must not need
the native tree (or contend with an eval that is using it) to check a piece of pure geometry.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
from dogfight.sim.state_schema import StateIndex
from student.controller_providers import VPTrackingProvider, body_axes


def _provider(standoff_m: float, adaptive: bool = False, phased: bool = False) -> VPTrackingProvider:
    p = object.__new__(VPTrackingProvider)
    p.phased_window = phased
    p.adaptive_range = adaptive
    p.engage_range_m, p.engage_los_deg = 6000.0, 120.0
    p.aim_at_vp = False
    p.standoff_m = standoff_m
    p.throttle_control = False
    p.defensive_break = False
    p.corner_hold = False
    p.corner_kt = 440.0
    p.pitch_floor = 0.0
    p.roll_taper_deg = 0.0
    p.threat_ata_deg = 8.0
    p.hard_deck_m = 0.0
    p.deck_ttc_s = 0.0
    p._deck_prev_alt_m = None
    p._deck_prev_t_s = None
    p._los_error_sum = 0.0
    p._break_steps = 0
    return p


def _state(n, e, alt, yaw_deg=0.0, pitch_deg=0.0, roll_deg=0.0, speed=250.0):
    s = np.zeros(int(max(StateIndex)) + 1, dtype=float)
    s[StateIndex.N], s[StateIndex.E], s[StateIndex.D] = n, e, -alt
    s[StateIndex.ROLL], s[StateIndex.PITCH], s[StateIndex.YAW] = roll_deg, pitch_deg, yaw_deg
    s[StateIndex.VX] = speed
    s[StateIndex.SIM_TIME] = 1.0
    return s


def _stick(p, own, tgt):
    out = p._tracking_stick(own, tgt, None, 0.5)
    assert out is not None, "controller deferred to the BT; test geometry is inside the envelope"
    return out[:3]


def main() -> int:
    # Ownship at the origin pointing north. Target ahead and slightly right, also pointing north,
    # so its forward vector is a clean +N and "behind its tail" is unambiguous.
    own = _state(0.0, 0.0, 4000.0, yaw_deg=0.0)

    # 1. OFF is inert, at every range.
    off = _provider(0.0)
    for rng in (50.0, 220.0, 800.0):
        tgt = _state(rng, 5.0, 4000.0, yaw_deg=0.0)
        a = _stick(_provider(0.0), own, tgt)
        b = _stick(off.__class__ and _provider(0.0), own, tgt)
        assert a == b, f"non-determinism at {rng} m"
    for rng in (50.0, 100.0, 219.0):
        tgt = _state(rng, 5.0, 4000.0)
        base = _stick(_provider(0.0), own, tgt)
        assert base == _stick(_provider(0.0), own, tgt)

    # 2. No step at the boundary: rng == standoff must equal pure pursuit.
    tgt = _state(220.0, 5.0, 4000.0)
    at_boundary = _stick(_provider(220.0), own, tgt)
    pure = _stick(_provider(0.0), own, tgt)
    for x, y in zip(at_boundary, pure):
        assert abs(x - y) < 1e-12, f"discontinuity at the standoff boundary: {at_boundary} vs {pure}"

    # 3a. KNOWN NULL, pinned deliberately: a co-aligned stern chase. The target's forward axis
    # is parallel to our line of sight, so sliding the aim point along it shortens the aim vector
    # without rotating it -- same unit vector, same phi, same stick. This controller's roll is a
    # function of the error's DIRECTION only (roll = K * phi/pi), so a change that preserves phi
    # cannot move the stick at all. Range control in a pure stern chase belongs to the throttle
    # setpoint (TARGET_RANGE_M), not here. Assert it so nobody later reads this as a bug.
    tgt_stern = _state(30.0, 5.0, 4000.0, yaw_deg=0.0)
    assert _stick(_provider(220.0), own, tgt_stern) == _stick(_provider(0.0), own, tgt_stern),         "stern-chase case unexpectedly moved; the known-null assumption above no longer holds"

    # 3b. THE CASE IT IS FOR: a crossing target, which is the overshoot geometry. Its forward
    # axis is across our line of sight, so the lag rotates the aim point and the stick must move.
    tgt_close = _state(30.0, 5.0, 4050.0, yaw_deg=90.0)
    inside = _stick(_provider(220.0), own, tgt_close)
    pure_close = _stick(_provider(0.0), own, tgt_close)
    assert inside != pure_close, "standoff engaged but commanded the same stick as pure pursuit"

    # 3c. THE PHASE-1 GATE: with a shot actually in hand the standoff must stand down.
    # Phase 1 pays 1.0 x (3000 - r_ft)/2500 and requires range 500-3000 ft AND LOS < 1 deg.
    # Range is a smooth multiplier, the angle a binary gate, so nudging the aim point off the
    # target to gain range can drop us out of the cone and score nothing. Target dead ahead at
    # 200 m (656 ft, inside the band) with ~0 deg of error: the commanded stick must be
    # identical to pure pursuit even though 200 m is well inside a 220 m standoff radius.
    own_level = _state(0.0, 0.0, 4000.0, yaw_deg=0.0)
    tgt_shot = _state(200.0, 0.0, 4000.0, yaw_deg=90.0)   # crossing, so lag WOULD bite if applied
    assert _stick(_provider(220.0), own_level, tgt_shot) == _stick(_provider(0.0), own_level, tgt_shot),         "standoff engaged while a Phase-1 shot was in hand; it must never trade angle for range there"

    # And just OUTSIDE the angle gate it must engage again.
    tgt_noshot = _state(200.0, 30.0, 4000.0, yaw_deg=90.0)   # ~8.5 deg off the nose
    assert _stick(_provider(220.0), own_level, tgt_noshot) != _stick(_provider(0.0), own_level, tgt_noshot),         "standoff stayed off despite no shot being available"

    # 3d. ADAPTIVE RANGE. Damage is symmetric in range, so f(r) multiplies whichever side holds
    # the tighter angle. Extend only while THEY out-angle US; close when we out-angle them.
    #   own nose on the target, their nose 90 deg away -> WE out-angle them -> must NOT extend
    tgt_weangle = _state(120.0, 0.0, 4060.0, yaw_deg=90.0)
    assert _stick(_provider(220.0, adaptive=True), own, tgt_weangle)            == _stick(_provider(0.0), own, tgt_weangle),         "adaptive range extended while WE held the better angle; it should close and press"
    #   now THEY out-angle us: our nose 60 deg off, theirs only 30 deg off. Deliberately NOT the
    #   nose-straight-at-us case -- see the degeneracy note below.
    # Vertical separation is REQUIRED for this assertion to discriminate: with both aircraft at
    # one altitude el = 0, so phi = atan2(az, 0) = +/-90 deg whatever the aim magnitude, and this
    # control law's roll (K * phi/pi) and pitch (cos phi = 0) are both blind to an in-plane
    # rotation of the aim point. The geometry is fine; a coplanar test simply cannot see it.
    own_off = _state(0.0, 0.0, 4000.0, yaw_deg=60.0)
    tgt_theyangle = _state(120.0, 0.0, 4060.0, yaw_deg=150.0)
    assert _stick(_provider(220.0, adaptive=True), own_off, tgt_theyangle)            != _stick(_provider(0.0), own_off, tgt_theyangle),         "adaptive range failed to extend while THEY held the better angle"

    # KNOWN DEGENERACY, pinned deliberately. When the bandit's nose is pointed STRAIGHT at us its
    # forward vector is anti-parallel to our line of sight, so sliding the aim point along that
    # vector shortens it without rotating it -- identical unit vector, identical stick. So the lag
    # mechanism is weakest exactly in the geometry it exists to escape. Extending from a
    # nose-on threat needs throttle/energy, not an aim-point bias; this asserts the limit rather
    # than letting a future reader assume the knob covers that case.
    own_nose = _state(0.0, 0.0, 4000.0, yaw_deg=40.0)
    tgt_nose_on = _state(120.0, 0.0, 4000.0, yaw_deg=180.0)
    assert _stick(_provider(220.0, adaptive=True), own_nose, tgt_nose_on)            == _stick(_provider(0.0), own_nose, tgt_nose_on),         "nose-on degeneracy no longer holds; re-derive the lag geometry"

    # 4. The aim point is genuinely behind the target, and by the right amount.
    standoff = 220.0
    rel = np.array([tgt_close[StateIndex.N] - own[StateIndex.N],
                    tgt_close[StateIndex.E] - own[StateIndex.E],
                    -(tgt_close[StateIndex.D] - own[StateIndex.D])])
    rng = float(np.linalg.norm(rel))
    tgt_fwd, _, _ = body_axes(tgt_close)
    lag_expect = min(standoff - float(np.linalg.norm(rel)), float(np.linalg.norm(rel)))
    aim_vec = rel - tgt_fwd * lag_expect
    # The lag point must sit aft of the target along ITS forward axis.
    assert float(np.dot(aim_vec - rel, tgt_fwd)) < 0.0, "aim point is ahead of the target, not behind"
    lag_m = float(np.linalg.norm(aim_vec - rel))
    assert abs(lag_m - lag_expect) < 1e-6, f"lag {lag_m:.3f} m, expected {lag_expect:.3f}"
    # The cap is the point: uncapped this would be 190 m and would push the aim point behind us.
    assert lag_m <= rng + 1e-9, f"lag {lag_m:.1f} m exceeds the range {rng:.1f} m -- cap not applied"

    # 5. And it opens the angle off the collision course rather than tightening it.
    fwd, _, _ = body_axes(own)
    ata_pure = math.degrees(math.acos(float(np.dot(fwd, rel / np.linalg.norm(rel)))))
    ata_lag = math.degrees(math.acos(float(np.dot(fwd, aim_vec / np.linalg.norm(aim_vec)))))
    assert ata_lag > ata_pure, f"lag ATA {ata_lag:.2f} not greater than pure {ata_pure:.2f}"

    print(f"OK  boundary continuous; at {rng:.0f} m the aim point sits {lag_m:.0f} m aft of the "
          f"target and moves the commanded ATA {ata_pure:.2f} -> {ata_lag:.2f} deg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
