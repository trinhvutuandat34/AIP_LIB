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

import os

import numpy as np

from dogfight.ai.action_provider import (
    ActionContext,
    ActionProvider,
    ActionResult,
    clip_action,
)
from dogfight.ai.bt_action_provider import BTActionProvider
from dogfight.sim.state_schema import StateIndex
from student.inference_providers import StudentHybridProvider
from student.g_limiter import GLimiter, G_LIMIT as G_LIMIT_DEFAULT

RADTODEG = 180.0 / np.pi

# ---- Terminal-tracking envelope -------------------------------------------------------
# Chosen to cover the measured in-band tracking window (the 413 steps sit at 152-914 m) with
# margin, while leaving the approach entirely to the BT. Widening these hands the BT's tactics
# to this controller -- which it does NOT implement -- so widen only with a measured reason.
#
# THERE IS NOW A MEASURED REASON TO SWEEP THEM (2026-08-06). These bounds were sized against
# OBFM, where the ownship starts at the target's six and the fight is already inside them.
# On the OFFICIAL match geometry (match_scenario_wrapper: antiparallel beam merge at
# 2000-3000 ft) the aircraft cross and separate, the fight develops as a turning contest
# BEYOND 1200 m, and the controller barely engages: median min-ATA 1.272 deg vs the BT's
# 1.419 deg, both stranded above the 1.0 deg gate, 1/30 wins. Compare OBFM, same backend:
# 0.024 deg and 12/30. Widening trades pointing precision for engagement time in a regime
# the controller has no energy management for, so it is an empirical question either way.
#
# Overridable from the environment for sweeps ONLY -- these are not a runtime configuration
# surface, and the submission path never sets them (student/my_submission.py).
# RETUNED 2026-08-06 to 2500 m / 45 deg, swept on the official match geometry (N=30 per
# config, competition scoring = damage differential at timeout, COMPETITION_RULES.md line 65):
#
#     config        win%(rule)   kills  wez  damage  median min-ATA  losses
#     BT baseline    1/30  3.3%      0     1    0.05     1.419 deg      0
#     1200m/20deg    5/30 16.7%      1     3    1.31     1.272 deg      0   <- previous default
#     2500m/20deg   22/30 73.3%      1    19    4.51     0.022 deg      0
#     2500m/30deg   22/30 73.3%      1    21    6.21     0.127 deg      0
#     2500m/45deg   22/30 73.3%      8    19   14.29     0.097 deg      0   <- chosen
#     3000m/30deg   21/30 70.0%      3    20    9.10     0.085 deg      0
#     2800m/45deg   19/30 63.3%      8    18   12.55     0.068 deg      0
#     4000m/45deg   19/30 63.3%      8    18   13.14     0.068 deg      0
#     2500m/60deg   16/30 53.3%      9    14   15.35     0.023 deg      0
#
# Range is the dominant factor and 2500 m is a plateau (20/30/45 deg all tie at 22/30), not a
# noise spike; 45 deg is chosen off the tiebreakers -- 8 kills and 14.29 damage at the same win
# rate. Beyond 2500 m it regresses. Caveat kept visible: this is the best of 7 configs at
# SE ~8%, so some of the margin over 3000m/30 is selection luck; the 1200 -> 2500 step is far
# larger than that and is the real finding.
ENGAGE_RANGE_M = float(os.environ.get("DOGFIGHT_VPTRACK_RANGE_M", "2500.0"))
ENGAGE_LOS_DEG = float(os.environ.get("DOGFIGHT_VPTRACK_LOS_DEG", "45.0"))

# ---- THE SHIPPED COMBAT CONFIG -- single source of truth (2026-08-21, F44) -------------
# The class defaults above are the ORIGINAL sweep champion and are deliberately left alone:
# they are what every historical measurement in the register was taken at, so changing them
# would silently re-interpret old results. What actually ships is different, and it lived only
# as literals inside student/my_submission.py -- which meant `run_unreal_inference.py --mode
# vptrack` built a bare VPTrackingProvider and silently flew 2500m/45deg/throttle-off: the
# pre-F29/F39 config, measured at 13.3% against the cutoff where the shipped one scores 100%
# (N=100). Same flag, same mode name, an order-of-magnitude different aircraft.
#
# Both live entry points now take these, so the two cannot drift apart:
#   throttle  -- F29, adopted on 3 seeds; losses fell in every one (8->5,5,4)
#   4000/60   -- F39-ENVELOPE-MARGIN; 100% win / 95% earned vs cutoff at N=100, and unlike
#                4000/45 it costs nothing on the peer rig (match_base 46.7% vs 43.3%)
SHIP_ENGAGE_RANGE_M = 4000.0
SHIP_ENGAGE_LOS_DEG = 60.0
SHIP_THROTTLE_CONTROL = True

# ---- Gains ----------------------------------------------------------------------------
K_ROLL = 1.0
K_PITCH = 1.0
# Floor under the pitch alignment gate: pitch = -K * err_gain * max(cos(phi), PITCH_FLOOR).
#
# HYPOTHESIS (MINE, AND REFUTED). scripts/g_limit_check.py measured full pitch delivering 3.97 G
# at 250 kt rising to 14.86 G at 550 kt, so ~6.7 G is available at the 340 kt this aircraft
# fights at -- while scripts/turn_rate_sweep.py measures it pulling 1.48 G in real matches, a
# FIFTH of what is there. I read that as having reintroduced Controller_CY's multiplicative kill
# in milder form, and expected a floor > 0 to help.
#
# MEASURED, N=30 per arm -- HARMFUL, and monotonically so from zero:
#     vs BT       floor 0.00  73.3%, 8 kills, 19 wez eps, damage 14.29/0.00
#                 floor 0.25  73.3%, 8 kills, 15 wez eps, damage 13.83/0.17
#     self-play   control     23.3%, 6 kills, 14 wez eps, damage 11.85/11.86
#                 floor 0.35  13.3%, 0 kills,  7 wez eps, damage  1.19/3.58
#
# WHY THE GATE IS LOAD-BEARING, and how it differs from the defect it resembles. In
# Controller_CY, Roll_Effect -> 0 at UTAngle ~180 AND RollCMD = sin(UTAngle) -> 0 at the same
# time: both authorities died together, so nothing could escape -- that is the trap. Here,
# align -> 0 at phi = 180 is exactly where ROLL IS MAXIMAL (K_ROLL * phi/pi). They are
# complementary: roll hard when pulling would not help, pull when it would. Pulling at
# cos(phi) < 0 pulls AWAY from the solution, which is what the numbers show.
#
# The low average G is therefore correct behaviour, not a defect: this controller pulls hard
# only when pulling helps. Keep at 0.0.
PITCH_FLOOR = float(os.environ.get("DOGFIGHT_VPTRACK_PITCH_FLOOR", "0.0"))
PROPORTIONAL_DIV = 6.0    # same as Controller_CY's, so error->command scaling is comparable
INTEGRAL_DIV = 7.5        # E1c measured these two as non-binding at the attractor; kept only
INTEGRAL_CAP = 0.25       # so the pitch magnitude stays on the scale the airframe is tuned for
ERROR_EFFECT_CAP = 1.5

# Rudder: unchanged from the post-fix Controller_CY form. RUDDER_TAPER_CEIL 6.0 is the value
# E1e S3 measured as best (3.0 and 1.5 were monotonically worse).
K_RUDDER = 1.0
RUDDER_TAPER_CEIL = 6.0

# ---- Range / throttle control -- MEASURED NULL, DEFAULT OFF (2026-08-06) ----------------
# The WEZ band is 152.4-914.4 m with damage coefficient (3000 - r_ft)/2500: ~0.09 at the far
# edge, ~0.91 at 220 m, and exactly 0 below 152.4 m (a hard dead zone). So this drives to a
# SETPOINT, not monotonically closer. 220 m matches the target A2 chose for Task_GunTrack's
# range bias, so the C++ and this agree instead of fighting each other.
#
# HYPOTHESIS (wrong): of the 8 draws the retuned controller left against the BT, 3 reached the
# angle gate and still scored nothing, so giving the controller throttle -- the one axis it had
# never touched -- should convert them by fixing range.
#
# MEASURED, N=30 per arm, same seeds:
#     vs BT        73.3% -> 70.0%  (8 -> 9 kills, damage 14.29 -> 15.96)
#     self-play    23.3% -> 26.7%  (6 -> 3 kills, damage taken 11.86 -> 13.61)
# Both differences are well inside 1 SE (+/-8%), i.e. no effect either way.
#
# WHY IT CANNOT HELP, from the same runs: median ep_min_distance is already **92.8 m vs the BT
# and 20.2 m in self-play** -- BELOW the 152.4 m zero-damage floor. The aircraft are not failing
# to close; they close far too much. Those 3 draws were never a range problem: angle and range
# are simply not coincident (the angle arrives when the range is wrong, and vice versa). That is
# a timing problem and belongs to the same positional gap as the other 5.
#
# Kept, off by default, because it is correct code for a hypothesis worth re-testing once the
# positional problem is addressed -- at which point range control may start to matter. Enable
# with DOGFIGHT_VPTRACK_THROTTLE=1.
THROTTLE_CONTROL = os.environ.get("DOGFIGHT_VPTRACK_THROTTLE", "0") not in ("0", "false", "False")

# ---- Corner-speed hold (2026-08-07) ----------------------------------------------------
# A DIFFERENT lever from the range setpoint above, and it targets a different quantity. BFM
# fundamentals (theaviationist, F-16): turn RATE peaks at corner speed ~430-450 KTAS / 0.8 M,
# giving a 2500 ft radius at 20 deg/sec; rate is what wins an angles fight between identical
# aircraft. Nothing in this stack has ever targeted speed -- every BT Task node hardcodes a
# throttle constant (Sec 4.1 D4) and the range setpoint above chases distance, not energy.
#
# MEASURED (scripts/corner_speed_probe.py, N=20 self-play on match_base): we spawn at 388.8 kt
# and DECELERATE, averaging 339.6 kt over the match -- 90-110 kt below the band -- and spend
# only 7.3% of the match inside it. The opponent does the same (7.2%), which is exactly why
# self-play cannot answer whether it matters: neither side ever fights at corner. The
# asymmetric harness can.
#
# MEASURED 2026-08-07 -- HARMFUL AT 440 kt. Default OFF.
#     self-play vs champion  7W/16D/7L, identical to control (23.3%)
#     vs BT                  73.1% win rate but 0 KILLS and 0.63 damage (champion: 8 and 14.29)
# The win RATE survived while damage collapsed 96%: dealing 0.63 against an opponent dealing
# zero still scores as a differential win. Win rate alone would have passed this change --
# check damage and kills alongside it.
# Most likely the setpoint, not the idea: the probe shows this airframe settles naturally at
# 339.6 kt, and forcing it ~100 kt faster widens the turn radius so it cannot hold a 152-914 m
# WEZ. 430-450 kt is a real-F-16 figure at a particular weight and altitude; this JSBSim model's
# rate may well peak near where it already settles. A proper test is an IN-SIM rate sweep
# (turn rate vs TAS at fixed G) to find this model's actual corner, not the article's number.
# Enable with DOGFIGHT_VPTRACK_CORNER=1, and sweep DOGFIGHT_VPTRACK_CORNER_KT if so.
CORNER_HOLD = os.environ.get("DOGFIGHT_VPTRACK_CORNER", "0") not in ("0", "false", "False")
CORNER_KT = float(os.environ.get("DOGFIGHT_VPTRACK_CORNER_KT", "440.0"))
CORNER_BAND_KT = 15.0        # deadband so throttle does not chatter around the setpoint
MPS_TO_KT = 1.94384
TARGET_RANGE_M = float(os.environ.get("DOGFIGHT_VPTRACK_TARGET_M", "220.0"))
RANGE_P = 1.0 / 400.0     # full authority at 400 m of range error
CLOSURE_D = 1.0 / 40.0    # damping on per-step closure, so it settles instead of oscillating
THROTTLE_AUTHORITY = float(os.environ.get("DOGFIGHT_VPTRACK_THR_AUTH", "0.7"))

# ---- Deny damage (defensive break) -----------------------------------------------------
# EVERYTHING in this controller had been offensive. Measured in self-play (N=30, match_base):
# damage dealt 11.85 vs damage TAKEN 11.86 -- perfectly symmetric, because nothing anywhere in
# the stack considers not being shot. In a fight where both sides score equally and neither
# dies (53% draws), a point of damage denied is worth exactly as much as a point dealt, and it
# is the only asymmetry never explored.
#
# NOT blanket evasion. Self-play rewards mutual passivity -- a config that avoids damage by
# disengaging scores well here and loses the real match on damage differential (the competition
# adjudicates a timeout on who dealt more, COMPETITION_RULES.md Sec 5). So this fires only when
# we are LOSING the gun duel: the opponent is inside their own WEZ range band on us AND their
# ATA is tighter than ours, i.e. they will score before we do. If we are better aligned we keep
# tracking and win the exchange.
#
# The break itself is a max-rate turn INTO the threat: same roll-to-pull machinery as the
# tracking law (roll to put the threat in the pull plane) but with full pitch instead of
# error-proportional. That both spoils their tracking solution and generates angles, rather
# than running away, which only prolongs their shot.
# MEASURED 2026-08-06 -- IT WORKS AND IT IS STILL NOT WORTH SHIPPING. Default OFF.
#   self-play vs champion   W/D/L 7/14/9 (control 7/16/7), win rate 23.3% both
#                           damage taken 11.86 -> 7.55 (-36%), deaths 3 -> 0
#                           damage dealt 11.85 -> 7.99 (-33%)
#   vs BT (passivity guard) 70.0% vs 73.3%, same 8 kills -- no regression, guard passes
# The mechanism does exactly what it claims: it denies damage and we are never shot down. But
# it costs offence almost exactly 1:1, so the DIFFERENTIAL barely moves and the phased record
# is slightly worse. Breaking off a shot to avoid one is a wash when both sides shoot equally
# well -- and the competition scores a timeout on differential, not on survival
# (COMPETITION_RULES.md Sec 5).
# WORTH RE-TESTING against an opponent that out-shoots us, where trading 1:1 is a gain rather
# than a wash -- e.g. the organizers' cutoff model. Enable with DOGFIGHT_VPTRACK_DEFENSIVE=1
# or --{side}-vptrack-defensive 1.
DEFENSIVE_BREAK = os.environ.get("DOGFIGHT_VPTRACK_DEFENSIVE", "0") not in ("0", "false", "False")
THREAT_ATA_DEG = float(os.environ.get("DOGFIGHT_VPTRACK_THREAT_ATA", "8.0"))
WEZ_MIN_M, WEZ_MAX_M = 152.4, 914.4

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
        # Every one of OUR kwargs must be popped BEFORE super().__init__, which is
        # BTActionProvider's and rejects anything it does not know. throttle_control was
        # popped after it, which was latent until the per-side CLI made it reachable:
        # passing --{side}-vptrack-throttle raised
        # "BTActionProvider.__init__() got an unexpected keyword argument 'throttle_control'".
        # It never surfaced earlier because the flag had only ever been set via env var.
        self.throttle_control = bool(kwargs.pop("throttle_control", THROTTLE_CONTROL))
        self.defensive_break = bool(kwargs.pop("defensive_break", DEFENSIVE_BREAK))
        self.corner_hold = bool(kwargs.pop("corner_hold", CORNER_HOLD))
        self.corner_kt = float(kwargs.pop("corner_kt", CORNER_KT))
        self.pitch_floor = float(kwargs.pop("pitch_floor", PITCH_FLOOR))
        self.threat_ata_deg = float(kwargs.pop("threat_ata_deg", THREAT_ATA_DEG))
        super().__init__(*args, **kwargs)
        self._los_error_sum = 0.0
        self._prev_range_m: float | None = None
        self._override_steps = 0
        self._total_steps = 0
        self._break_steps = 0

    def reset(self, context: ActionContext | None = None) -> None:
        # The base class reset() is a deliberate no-op (native BT is kept alive across episode
        # resets for multienv). The integral is OURS and is per-episode: carrying it across
        # episodes is exactly the cross-episode leak class that Sec 4.1 E1-leaks documents for
        # ErrorSum/SumCount, and it would destroy the sample independence the N>=30 statistics
        # depend on. Same argument for the range memory below.
        self._los_error_sum = 0.0
        self._prev_range_m = None
        return super().reset(context)

    def _losing_gun_duel(self, own, tgt, rng: float, own_ata_deg: float) -> bool:
        """True when the opponent will score before we do.

        Their ATA (angle from THEIR nose to us) is what puts us in their gun cone, so it is
        computed from the target's own body axes, not ours. Requires all three: they are inside
        their scoring range band, their ATA is inside the threat threshold, and their ATA is
        tighter than ours -- the last term is what keeps this from degenerating into evasion.
        """
        if not (WEZ_MIN_M <= rng <= WEZ_MAX_M):
            return False
        tgt_fwd, _, _ = body_axes(tgt)
        to_us = np.array([
            float(own[StateIndex.N]) - float(tgt[StateIndex.N]),
            float(own[StateIndex.E]) - float(tgt[StateIndex.E]),
            -(float(own[StateIndex.D]) - float(tgt[StateIndex.D])),
        ])
        n = float(np.linalg.norm(to_us))
        if not np.isfinite(n) or n <= 0:
            return False
        tgt_ata = float(np.arccos(_clamp(float(np.dot(tgt_fwd, to_us / n)), -1.0, 1.0)) * RADTODEG)
        return tgt_ata < self.threat_ata_deg and tgt_ata < own_ata_deg

    def _range_throttle(self, rng: float, bt_throttle: float) -> float:
        """Close to the high-damage edge of the WEZ band, without overshooting through it.

        WHY (measured 2026-08-06). Of the 8 draws left by the retuned controller against the
        BT, **3 reached the angle gate and still scored nothing** (min-ATA 0.13 / 0.41 /
        0.74 deg, 0 WEZ steps) -- angle satisfied, range not, at the same instant. Throttle
        was the one axis this controller never touched: it passed the BT's value straight
        through, and every Task node hardcodes a constant (Sec 4.1 D4).

        The band is 152.4-914.4 m with damage coefficient (3000 - r_ft)/2500, so value rises
        steeply as range closes: ~0.09 at the far edge, ~0.91 at 220 m, and **0.0 below
        152.4 m** -- a hard dead zone, which is why this drives to a setpoint rather than
        closing monotonically. 220 m is the same target A2 chose for `Task_GunTrack`'s range
        bias, so the two agree rather than fighting.

        Proportional on range error with a damping term on closure so it settles instead of
        oscillating through the dead zone. Closure is measured per-step (no dt needed -- it
        only has to be proportional to the rate).
        """
        err = rng - TARGET_RANGE_M                      # >0: too far, close in
        closure = 0.0 if self._prev_range_m is None else (self._prev_range_m - rng)
        self._prev_range_m = rng
        cmd = 0.5 + RANGE_P * err - CLOSURE_D * closure
        # Blend toward the BT's own throttle so the tree still has a say in energy state.
        cmd = THROTTLE_AUTHORITY * cmd + (1.0 - THROTTLE_AUTHORITY) * float(bt_throttle)
        return _clamp(cmd, 0.0, 1.0)

    def _tracking_stick(
        self, own: np.ndarray, tgt: np.ndarray, vp_neu: np.ndarray | None,
        bt_throttle: float = 0.5,
    ) -> tuple[float, float, float, float | None] | None:
        """Return (roll, pitch, rudder, throttle|None), or None to defer entirely to the BT.

        A None throttle means "keep the BT's" -- the behaviour before throttle control existed.
        """
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
        align = max(float(np.cos(phi)), self.pitch_floor)
        pitch_cmd = _clamp(-K_PITCH * err_gain * align, -1.0, 1.0)

        # RUDDER. Same form as the post-MFsum-fix Controller_CY: -sin(angle) * tapered LOS.
        rudder_cmd = _clamp(
            -K_RUDDER * float(np.sin(phi)) * _clamp(los_deg, 0.0, RUDDER_TAPER_CEIL) / RUDDER_TAPER_CEIL,
            -1.0,
            1.0,
        )
        # DENY DAMAGE. If the opponent will score before we do, stop flying the predictable
        # tracking solution and break INTO them at max rate: same roll (put the threat in the
        # pull plane) but full pitch instead of error-proportional. Overrides the offensive
        # commands rather than blending, because a half-committed break is the worst of both.
        if self.defensive_break and self._losing_gun_duel(own, tgt, rng, los_deg):
            self._break_steps += 1
            roll_cmd = _clamp(K_ROLL * phi / np.pi, -1.0, 1.0)
            pitch_cmd = -1.0
            rudder_cmd = 0.0          # uncoordinated rudder only slows the roll rate here

        if self.corner_hold:
            # Hold the rate-optimal speed: full throttle when slow, idle when fast, BT's value
            # inside the deadband. Deliberately independent of range -- this is an energy
            # objective, and mixing it with the range setpoint would let them fight.
            tas_kt = float(np.linalg.norm([own[StateIndex.VX], own[StateIndex.VY],
                                           own[StateIndex.VZ]])) * MPS_TO_KT
            if tas_kt < self.corner_kt - CORNER_BAND_KT:
                throttle_cmd = 1.0
            elif tas_kt > self.corner_kt + CORNER_BAND_KT:
                throttle_cmd = 0.0
            else:
                throttle_cmd = float(bt_throttle)
        elif self.throttle_control:
            throttle_cmd = self._range_throttle(rng, bt_throttle)
        else:
            throttle_cmd = None
        return roll_cmd, pitch_cmd, rudder_cmd, throttle_cmd

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
            stick = self._tracking_stick(
                own, tgt, result.info.get("vp"), float(result.action[3])
            )
        except Exception:
            # Never let a controller error kill a match -- same failure posture as
            # student/submission_resilience.py. Fall through to the BT.
            stick = None

        if stick is None:
            result.info["ctrl_source"] = "bt"
            return result

        self._override_steps += 1
        roll_cmd, pitch_cmd, rudder_cmd, throttle_cmd = stick
        action = clip_action([
            roll_cmd, pitch_cmd, rudder_cmd,
            float(result.action[3]) if throttle_cmd is None else throttle_cmd,
        ])

        if context.sim is not None and hasattr(context.sim, "action"):
            context.sim.action[:] = action

        info = dict(result.info)
        info.update({
            "ctrl_source": "vptrack",
            "ctrl_override_steps": self._override_steps,
            "ctrl_break_steps": self._break_steps,
            "ctrl_total_steps": self._total_steps,
        })
        return ActionResult(
            action=action,
            source="vptrack",
            confidence=result.confidence,
            info=info,
        )


class EnvelopeGatedHybridProvider(StudentHybridProvider):
    """Residual RL during the approach; undiluted terminal tracking during the shot.

    WHY (measured 2026-08-06, N=30 OBFM, same harness/seeds):

        vptrack alone                        12/30 wins, 30/30 WEZ eps, median min-ATA 0.024 deg
        StudentHybridProvider on that floor   0/30 wins,  5/30 WEZ eps, median min-ATA 2.260 deg

    The plain residual does not merely fail to help -- it takes a backend that wins 40% of
    episodes to zero. The reason is a scale mismatch, not a bug: the scoring gate is <=1.0 deg
    and `VPTrackingProvider` converges to 0.024 deg, so a 0.35-weighted correction from the
    (untrained, 0-win) v6 policy is orders of magnitude larger than the precision it is
    perturbing. Adding noise to a solved terminal solution can only destroy it.

    But the residual is not worthless -- it acts on the phase the fixed floor CANNOT solve.
    `VPTrackingProvider` only takes the stick inside its terminal envelope, and outside it the
    native BT flies and loses the neutral merge (vptrack scores 1/30 on two_circle_headon vs
    12/30 on OBFM, which starts advantaged). Winning the merge is the remaining gap.

    So gate the residual on the same envelope, which the floor already reports per step via
    `info["ctrl_source"]`:

        ctrl_source == "vptrack"  ->  terminal tracking: pass the floor through UNTOUCHED
        ctrl_source == "bt"       ->  approach/maneuvering: apply the residual as usual

    This keeps Sec 3's architecture intact (RL corrects the BT, BT is the safety net) while
    making the correction structurally incapable of spoiling a firing solution. Throttle is
    left on the residual path in both phases -- it is a separate sanctioned RL target (Sec 4.1
    D4), it is not part of the pointing solution, and every Task node currently hardcodes it.
    """

    def compute_action(self, context: ActionContext) -> ActionResult:
        secondary_result = self.secondary_provider.compute_action(context)

        if secondary_result.info.get("ctrl_source") != "vptrack":
            # Approach phase -- the floor is just the BT here, so behave exactly as the plain
            # residual hybrid. Recomputing through super() would tick the secondary provider a
            # SECOND time this step (double-stepping the native BT and its blackboard), so the
            # composition is done here against the result already in hand.
            primary_result = self.primary_provider.compute_action(context)
            primary = np.asarray(primary_result.action, dtype=np.float32)
            action = np.asarray(secondary_result.action, dtype=np.float32).copy()
            action[:3] += self.residual_scale * primary[:3]
            action[3] += self.residual_scale * (2.0 * primary[3] - 1.0)
            return ActionResult(
                action=clip_action(action),
                source="hybrid_gated",
                confidence=self.confidence,
                info={
                    "mode": "residual",
                    "phase": "approach",
                    "residual_scale": self.residual_scale,
                    "ctrl_source": secondary_result.info.get("ctrl_source"),
                },
            )

        # Terminal tracking -- hand the floor through untouched. The RL policy is deliberately
        # NOT queried here: it costs an inference call whose output would be discarded.
        info = dict(secondary_result.info)
        info.update({"mode": "residual", "phase": "terminal", "residual_applied": False})
        return ActionResult(
            action=clip_action(secondary_result.action),
            source="hybrid_gated",
            confidence=self.confidence,
            info=info,
        )


class GLimitedProvider(ActionProvider):
    """Wraps ANY provider and holds the load factor under a limit.

    Universal by design: the BT, this controller, a hybrid and an RL policy all emit through the
    same 4-vector, so limiting at the provider boundary covers every backend without touching
    src/dogfight or duplicating the logic per backend.

    See student/g_limiter.py for why the sim needs this at all -- it enforces no structural limit
    and hands out up to 14.86 G against a 9 G airframe rating.

    NOTE ON COVERAGE. This wraps the PROVIDER path, which is what eval and the live submission
    use. RL TRAINING drives the env's action argument directly with no provider, so a policy in
    training is NOT limited by this and can still learn to exploit 15 G. Limiting that path needs
    an env wrapper in the same student space; flagged rather than silently assumed.
    """

    def __init__(self, inner: ActionProvider, limit_g: float = G_LIMIT_DEFAULT):
        self._inner = inner
        self._limiter = GLimiter(limit_g=limit_g)

    def reset(self, context: ActionContext | None = None) -> None:
        self._limiter.reset()
        return self._inner.reset(context)

    def compute_action(self, context: ActionContext) -> ActionResult:
        result = self._inner.compute_action(context)
        own = context.ownship_state
        if own is None:
            return result
        action = np.asarray(result.action, dtype=np.float32).copy()
        action[1] = self._limiter.limit_pitch(float(action[1]), own)
        if context.sim is not None and hasattr(context.sim, "action"):
            context.sim.action[:] = action
        info = dict(result.info)
        info.update({"g_measured": self._limiter.last_n,
                     "g_clamp_fraction": self._limiter.clamp_fraction})
        return ActionResult(action=action, source=result.source,
                            confidence=result.confidence, info=info)

    def close(self) -> None:
        return self._inner.close()

    # Let the eval harness's BT recycler and health checks see through the wrapper.
    @property
    def ai_pilot(self):
        return getattr(self._inner, "ai_pilot")

    @property
    def _registered_fighter_ids(self):
        return getattr(self._inner, "_registered_fighter_ids")

    @property
    def primary_provider(self):
        return getattr(self._inner, "primary_provider", None)

    @property
    def secondary_provider(self):
        return getattr(self._inner, "secondary_provider", None)
