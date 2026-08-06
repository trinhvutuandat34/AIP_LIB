"""Terminal-tracking controller that bypasses `Controller_CY`'s VP->stick law.

WHY (measured 2026-08-06, `artifacts/eval/scratch_20260806/b1_obfm_trace.csv`, N=8 OBFM):
the native BT already holds **413 steps per episode inside the WEZ range band**
(152.4-914.4 m) -- range is NOT the binding constraint. But the best antenna-train angle
across all 413 of those in-band steps is **4.096 deg** against a **<=1.000 deg** scoring
gate, and at every one of the best steps `Roll_Effect` is **exactly 0.0** with the BT's
aim point (VP) **86.4-86.8 deg off the target LOS**. Zero sub-1-deg steps occur in-band in
either geometry tested.

THE TRAP, read straight off `AIP_DCS/Geometry/Controller_CY.cpp::GetStick` (lines 340-390).
Both control authorities vanish simultaneously near `UTAngle` = 180 deg:

  * `Roll_Effect = 1 - clamp(|UTAngle|/90, 0, 1)` is **identically 0 for |UTAngle| >= 90**,
    and `PitchCMD = ERROR_Effect * Roll_Effect * Horizon_Effect * (-1)` is a PRODUCT --
    so pitch authority is multiplicatively annihilated, not merely reduced.
  * In that same branch `RollCMD = sin(UTAngle)`, which **decays to 0 as UTAngle -> 180 deg**
    (measured: UTAngle 152-172 deg -> sin = 0.47..0.14 and falling).

So at large UTAngle the controller commands almost no roll and exactly no pitch: a genuine
attractor in the control law. That is the 4.4-deg mode, and it is why COMPETITION_PLAN.md
Sec 4.1 E1e's five scalar-gain sweeps all came back null -- no gain multiplies a zero into
something. This is a control-law defect, not a tuning problem.

WHAT THIS DOES. Inside a terminal-tracking envelope only, replace roll+pitch with a
roll-to-pull law that has no multiplicative kill and no zero-command trap:

  phi = atan2(az_err, el_err)          # where the error sits about the nose axis
  roll  = K_ROLL * wrap(phi)/pi        # MAXIMAL at phi = 180 deg, where the old law gave ~0
  pitch = -K_PITCH * err_gain * max(cos(phi), 0)   # pull; no (1 - |UT|/90) factor at all

Pull is NEGATIVE PitchCMD in this codebase's convention -- read off `GetStick` line 387
(`... * (-1)`) and line 389 (`PitchCMD = -1` for the LOS >= 90 full-pull branch), not assumed.
Positive RollCMD = roll right, anchored on the verified Python replica in
`scripts/eval_v5_vs_bt.py` (whose `rollcmd_mirror` reproduces the C++ `rollcmd_actual`).

Rudder is deliberately left in its existing post-`MFsum`-fix form. It is the one term that was
just measured to help (attractor 1.0380 -> 1.0070 deg), and Sec 4.1 E1e S3 showed *more* rudder
authority is monotonically worse -- so this changes roll and pitch only, one mechanism at a time.

OUTSIDE the envelope the native BT keeps full control, so every tactic in the ~25-node tree
still flies the approach. `Step()` is called on every tick regardless, so the tree's blackboard,
gates and maneuver phases advance exactly as they otherwise would -- this only overrides the
stick during the terminal solution, which is precisely where the 413 in-band steps are.

Boundary: `src/dogfight/**` is untouched (team policy, 2026-07-14). This composes the platform
by subclassing, the same idiom as `student/inference_providers.py`.
"""

from __future__ import annotations

import numpy as np

from dogfight.ai.action_provider import ActionContext, ActionResult, clip_action
from dogfight.ai.bt_action_provider import BTActionProvider
from dogfight.sim.state_schema import StateIndex

RADTODEG = 180.0 / np.pi

# ---- Terminal-tracking envelope -------------------------------------------------------
# Chosen to cover the measured in-band tracking window (the 413 steps sit at 152-914 m) with
# margin, while leaving the approach entirely to the BT. Widening these hands the BT's tactics
# to this controller -- which it does NOT implement -- so widen only with a measured reason.
ENGAGE_RANGE_M = 1200.0
ENGAGE_LOS_DEG = 20.0

# ---- Gains ----------------------------------------------------------------------------
K_ROLL = 1.0
K_PITCH = 1.0
PROPORTIONAL_DIV = 6.0    # same as Controller_CY's, so error->command scaling is comparable
INTEGRAL_DIV = 7.5        # E1c measured these two as non-binding at the attractor; kept only
INTEGRAL_CAP = 0.25       # so the pitch magnitude stays on the scale the airframe is tuned for
ERROR_EFFECT_CAP = 1.5

# Rudder: unchanged from the post-fix Controller_CY form. RUDDER_TAPER_CEIL 6.0 is the value
# E1e S3 measured as best (3.0 and 1.5 were monotonically worse).
K_RUDDER = 1.0
RUDDER_TAPER_CEIL = 6.0

# Aim at the target LOS, not the BT's VP. The VP is 86.4-86.8 deg off target during gun-hold,
# which is the whole problem. Flip to True to A/B the VP-following path.
AIM_AT_VP = False


def body_axes(state: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Forward/up/right unit vectors in the N-E-Up frame.

    Replicates `EulerAngle::toQuaternion` -- this codebase's own non-standard construction,
    NOT a textbook one. Verified 2026-08-06 (in `scripts/eval_v5_vs_bt.py`, from which this is
    carried over) to reproduce CheckSight/GetStick's forward vector to 0.000 deg across
    attitudes including large roll. Keep the two copies in sync; a textbook quaternion here
    silently disagrees with the C++ at high bank angles.
    """
    roll = float(state[StateIndex.ROLL]) / RADTODEG
    pitch = float(state[StateIndex.PITCH]) / RADTODEG
    yaw = float(state[StateIndex.YAW]) / RADTODEG

    c1, s1 = np.cos(yaw / 2), np.sin(yaw / 2)
    c2, s2 = np.cos(pitch / 2), np.sin(pitch / 2)
    c3, s3 = np.cos(roll / 2), np.sin(roll / 2)
    c1c2, s1s2 = c1 * c2, s1 * s2
    W, X, Y, Z = (c1c2 * c3 + s1s2 * s3, c1 * s2 * c3 + s1 * c2 * s3,
                  s1 * c2 * c3 - c1 * s2 * s3, c1 * c2 * s3 - s1s2 * c3)
    n = float(np.sqrt(W * W + X * X + Y * Y + Z * Z))
    if n <= 0:
        n = 1.0
    W, X, Y, Z = W / n, X / n, Y / n, Z / n

    fwd = np.array([1 - 2 * (X * X + Y * Y), 2 * (X * Z + W * Y), -2 * (Y * Z - W * X)])
    up = np.array([-2 * (Y * Z + W * X), -2 * (X * Y - W * Z), 1 - 2 * (X * X + Z * Z)])
    right = np.array([2 * (X * Z - W * Y), 1 - 2 * (Y * Y + Z * Z), -2 * (X * Y + W * Z)])
    return fwd, up, right


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else (hi if v > hi else v)


class VPTrackingProvider(BTActionProvider):
    """Native BT for tactics and throttle; student-space control law for terminal pointing."""

    def __init__(self, *args, **kwargs):
        self.engage_range_m = float(kwargs.pop("engage_range_m", ENGAGE_RANGE_M))
        self.engage_los_deg = float(kwargs.pop("engage_los_deg", ENGAGE_LOS_DEG))
        self.aim_at_vp = bool(kwargs.pop("aim_at_vp", AIM_AT_VP))
        super().__init__(*args, **kwargs)
        self._los_error_sum = 0.0
        self._override_steps = 0
        self._total_steps = 0

    def reset(self, context: ActionContext | None = None) -> None:
        # The base class reset() is a deliberate no-op (native BT is kept alive across episode
        # resets for multienv). The integral is OURS and is per-episode: carrying it across
        # episodes is exactly the cross-episode leak class that Sec 4.1 E1-leaks documents for
        # ErrorSum/SumCount, and it would destroy the sample independence the N>=30 statistics
        # depend on.
        self._los_error_sum = 0.0
        return super().reset(context)

    def _tracking_stick(
        self, own: np.ndarray, tgt: np.ndarray, vp_neu: np.ndarray | None
    ) -> tuple[float, float, float] | None:
        """Return (roll, pitch, rudder), or None to defer to the BT."""
        fwd, up, right = body_axes(own)

        # N-E-Up: D is negated, matching the eval replica and GetStick's own frame.
        rel = np.array([
            float(tgt[StateIndex.N]) - float(own[StateIndex.N]),
            float(tgt[StateIndex.E]) - float(own[StateIndex.E]),
            -(float(tgt[StateIndex.D]) - float(own[StateIndex.D])),
        ])
        rng = float(np.linalg.norm(rel))
        if not np.isfinite(rng) or rng <= 1.0:
            return None
        rel_u = rel / rng

        aim_u = rel_u
        if self.aim_at_vp and vp_neu is not None:
            vp = np.asarray(vp_neu, dtype=float)
            vp_n = float(np.linalg.norm(vp))
            if np.isfinite(vp_n) and vp_n > 0:
                aim_u = vp / vp_n

        los_deg = float(np.arccos(_clamp(float(np.dot(fwd, aim_u)), -1.0, 1.0)) * RADTODEG)
        if not np.isfinite(los_deg):
            return None

        # Envelope check -- outside it, the BT's tactics are better than this controller's
        # (which has none).
        if rng > self.engage_range_m or los_deg > self.engage_los_deg:
            return None

        # Signed body-frame split of the pointing error.
        el = float(np.arcsin(_clamp(float(np.dot(up, aim_u)), -1.0, 1.0)))      # + = above
        az = float(np.arcsin(_clamp(float(np.dot(right, aim_u)), -1.0, 1.0)))   # + = right

        # phi: where the error sits about the nose axis. 0 = straight up (pull directly at it),
        # +90 = off the right wing, 180 = straight down.
        phi = float(np.arctan2(az, el))
        if not np.isfinite(phi):
            return None

        # ROLL. Proportional to phi itself, NOT sin(phi). This is the whole fix: at phi = 180 deg
        # -- the old law's dead spot, where sin(phi) -> 0 and it commanded nothing -- this is
        # MAXIMAL, because 180 deg is the farthest the error can be from the pull plane.
        roll_cmd = _clamp(K_ROLL * phi / np.pi, -1.0, 1.0)

        # PITCH. Pull toward the target, scaled by how much of the error is already in the pull
        # plane. There is deliberately NO (1 - |UTAngle|/90) factor: that term is what made
        # PitchCMD identically zero for every one of the measured stuck-mode steps.
        self._los_error_sum += los_deg
        err_gain = _clamp(
            los_deg / PROPORTIONAL_DIV
            + _clamp(self._los_error_sum / INTEGRAL_DIV, 0.0, INTEGRAL_CAP),
            0.0,
            ERROR_EFFECT_CAP,
        )
        align = max(float(np.cos(phi)), 0.0)
        pitch_cmd = _clamp(-K_PITCH * err_gain * align, -1.0, 1.0)

        # RUDDER. Same form as the post-MFsum-fix Controller_CY: -sin(angle) * tapered LOS.
        rudder_cmd = _clamp(
            -K_RUDDER * float(np.sin(phi)) * _clamp(los_deg, 0.0, RUDDER_TAPER_CEIL) / RUDDER_TAPER_CEIL,
            -1.0,
            1.0,
        )
        return roll_cmd, pitch_cmd, rudder_cmd

    def compute_action(self, context: ActionContext) -> ActionResult:
        # Always tick the BT first: it owns throttle, and its blackboard/gates/maneuver phases
        # must advance whether or not we use its stick this step.
        result = super().compute_action(context)

        own = context.ownship_state
        tgt = context.target_state
        if own is None or tgt is None:
            return result

        self._total_steps += 1
        try:
            stick = self._tracking_stick(own, tgt, result.info.get("vp"))
        except Exception:
            # Never let a controller error kill a match -- same failure posture as
            # student/submission_resilience.py. Fall through to the BT.
            stick = None

        if stick is None:
            result.info["ctrl_source"] = "bt"
            return result

        self._override_steps += 1
        roll_cmd, pitch_cmd, rudder_cmd = stick
        action = clip_action([roll_cmd, pitch_cmd, rudder_cmd, float(result.action[3])])

        if context.sim is not None and hasattr(context.sim, "action"):
            context.sim.action[:] = action

        info = dict(result.info)
        info.update({
            "ctrl_source": "vptrack",
            "ctrl_override_steps": self._override_steps,
            "ctrl_total_steps": self._total_steps,
        })
        return ActionResult(
            action=action,
            source="vptrack",
            confidence=result.confidence,
            info=info,
        )
