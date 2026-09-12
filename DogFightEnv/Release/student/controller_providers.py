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
from student.reward_lib import WEZ_PHASES as _WEZ_PHASES

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
#   6000/120  -- F59 (2026-09-03) + hard deck 1000 m. SUPERSEDES 6000/90, which superseded
#                4000/60. Measured on BOTH opponents and BOTH geometries:
#                  vs cutoff  match_base : rule 28.0%, damage 0.394/0.374 (diff +0.020),
#                                          0 self-crashes -- vs 6000/90's +0.004
#                  peer H2H   match_base : 21W/18D/11L, damage 0.523/0.365 (diff +0.159)
#                  peer H2H   tiebreak   : 16W/16D/18L -- a dead heat, 2-episode margin
#                Clearly better on the geometry played EVERY match three times a BO3; a wash on
#                the one played only when three rounds are level. corner_hold was tested on top
#                and is HARMFUL here (rule 24.0%, diff -0.042) even though it HELPED at 6000/90
#                -- forcing corner speed widens the turn radius a wide envelope cannot afford.
#
# WHY 6000/90, AND WHY THE OLD JUSTIFICATION FOR 4000/60 IS VOID.
#
# 4000/60 was adopted on F39-ENVELOPE-MARGIN: "100% win / 95% earned vs cutoff at N=100, and
# unlike 4000/45 it costs nothing on the peer rig (match_base 46.7% vs 43.3%)". **The first half
# of that is void** -- F54 found the cutoff had been fed an INVERTED VERTICAL AXIS, so every
# pre-fix cutoff number was scored against an opponent that was blind in the vertical. With the
# feed corrected (folded into scripts/cutoff_provider.py 2026-09-02), all 15 runnable modes were
# re-scored at N=50:
#
#     envelope     damage dealt   rule%     differential
#     2500/45          0.000       0.0%       negative
#     4000/45          0.000       0.0%       negative
#     2500/90          0.014       0.0%       negative
#     4000/60          0.122      12.0%        -0.046
#     6000/90          0.282      28.0%        +0.004   <- only non-negative one in the sweep
#
# Every other config -- including every throttle/corner/defensive/2200-35/2000-45 variant --
# dealt LITERALLY ZERO damage. The gradient is entirely envelope width, both axes must widen
# together, and it has not turned over: 6000/90 is the widest ever tested and the best.
#
# **The second half of F39's justification was re-tested rather than assumed**, because the peer
# rig -- not the cutoff -- is what originally picked 4000/60. Head to head on match_base, N=50,
# seed 0, ownship 6000/90 vs target 4000/60, both with throttle: **17W/13D/18L, 11 kills vs 12
# deaths**. A 1-episode margin where 1 sigma is ~3.4 episodes -- a dead heat. F37's "costs real
# match_base performance" DOES NOT REPRODUCE.
#
# Net: strictly better against one opponent, statistically indistinguishable against the other.
# The real trade is VARIANCE -- 6000/90 converts draws into decisive results in both directions
# (against the cutoff 4000/60 times out 43 of 50). For a BO3 where a draw advances nobody,
# against a field we are the underdog in, that is the correct direction.
#
# TO REVERT: set these two back to 4000.0 / 60.0. Nothing else changes -- both live entry points
# read these constants, which is the F44 single-source-of-truth guarantee.
SHIP_ENGAGE_RANGE_M = 6000.0
SHIP_ENGAGE_LOS_DEG = 120.0
SHIP_THROTTLE_CONTROL = True
# Hard-deck guard, ON in the shipped config (F59, 2026-09-03). At 120 deg the controller owns
# the stick even with the bandit behind us, so Gate 0 never climbs: 6/50 self-crashes. With the
# guard at 1000 m (just above Gate 0's own 914 m trigger) those go to ZERO and damage dealt
# RISES 0.341 -> 0.394. NOT a global default -- applied to 6000/90 (which never crashed) it
# measured slightly WORSE, so it is a fix for wide envelopes specifically.
SHIP_HARD_DECK_M = 1000.0
# Time-to-impact deck guard (F62). 0.0 = OFF, which is what ships today -- the knob exists so
# the matrix can measure it. Adopting it is a one-line change here, and both entry points read
# this constant (the F44 single-source guarantee), so there is nowhere else to remember.
SHIP_DECK_TTC_S = 0.0

# ---- Model 1 / Model 2 profiles (2026-09-05, F61) ---------------------------------------
# The finals accept TWO artifacts: Model 1 (main, plays every standard game) and Model 2 (used
# only after Head-On mode triggers -- both games 1 AND 2 drawn in a knockout BO5). Per
# COMPETITION_RULES.md 7.1 Model 2 is OPTIONAL; Model 1 is required.
#
# A "model" here is nothing but a set of controller constants over the SAME code and the SAME
# DLLs -- exactly what league.py's CANDIDATES already demonstrates, where each candidate is
# just a list of CLI flags. There is no second build and no second bundle.
#
# WHY A DICT INSTEAD OF EDITING THE SHIP_* CONSTANTS. Those constants are the F44
# single-source-of-truth that BOTH live entry points read, and every number in the F66 N=150
# matrix was measured at exactly those values. So profile 1 is BUILT FROM them rather than
# copying them: there is still exactly one place to change the shipped config, and the two
# cannot silently drift apart.
#
# PROFILE 2 IS DELIBERATELY IDENTICAL TO PROFILE 1 until the head-on separation sweep lands.
# Shipping an unmeasured Model 2 is strictly worse than shipping Model 1 in both slots, so the
# safe default is "Model 2 == Model 1, never switch"; adopting a real Model 2 is a one-dict
# change here and nowhere else.
MODEL_PROFILES: dict[int, dict[str, object]] = {
    1: {
        "engage_range_m": SHIP_ENGAGE_RANGE_M,
        "engage_los_deg": SHIP_ENGAGE_LOS_DEG,
        "throttle_control": SHIP_THROTTLE_CONTROL,
        "hard_deck_m": SHIP_HARD_DECK_M,
        "deck_ttc_s": SHIP_DECK_TTC_S,
    },
}
# MODEL 2 ADOPTED 2026-09-05 (F74): `prev_6000_90` -- 6000 m, LOS 90 deg, throttle ON, NO hard
# deck. Measured head-on at the organizer-confirmed 3,048 m (F72), N=60 x 5 archetypes x 4
# candidates = 1,200 episodes.
#
# WHY IT DIFFERS FROM MODEL 1, AND WHY THAT IS NOT A CONTRADICTION. Model 1's 120 deg LOS hands
# the controller the stick early, which pays in the offset beam merge every standard game starts
# from -- and is exactly wrong nose-to-nose at 3 km. Head-on, Model 1's config scores 0.44
# expected BO3 points against the cutoff (11W/10D/39L, 7% BO5) versus 1.18 for this one
# (19W/17D/24L, 32%). Both configs are correct; they are correct for different geometries, which
# is the entire reason the rules allow two artifacts.
#
# THE HARD DECK WAS TESTED HERE AND REJECTED ON EVIDENCE, not inherited from F59. `6000/90 +
# deck 1000` (candidate `m2_6000_90_deck`, N=300) cut self-crashes from 11/300 to 3/300 -- the
# guard demonstrably works -- and STILL scored slightly worse (floor 1.02 vs 1.18, mean 1.62 vs
# 1.64). So those crashes were not free losses: the aircraft reaching the deck were already
# losing, and the guard also fires where the controller would have recovered. F59 reached the
# same verdict in match_base on a premise ("6000/90 never crashed") that is FALSE here -- right
# answer, wrong reason. Do not re-open this without new evidence.
#
# Side symmetry verified on this exact profile: paired forced-mirror run vs cutoff at head-on,
# 0.3 sigma (8/6/11 vs 9/6/10). F67's 26-point asymmetry is geometry-specific -- it lives in the
# offset merge, not the symmetric nose-to-nose start.
MODEL_PROFILES[2] = {
    "engage_range_m": 6000.0,
    "engage_los_deg": 90.0,
    "throttle_control": True,
    "hard_deck_m": 0.0,     # OFF -- measured better than 1000.0 here; see above
    "deck_ttc_s": 0.0,
}


def get_model_profile(model=None) -> dict:
    """Return the controller constants for Model 1 or Model 2, as a fresh dict.

    Resolution order: explicit argument -> DOGFIGHT_MODEL_PROFILE env var -> 1.

    An unrecognised value falls back to Model 1 rather than raising. On match day a typo in an
    operator's environment must not take the process down, and Model 1 is always a valid thing
    to fly; a Model 2 that silently becomes Model 1 loses at most the head-on edge, whereas an
    exception at startup loses the game.
    """
    if model is None:
        model = os.environ.get("DOGFIGHT_MODEL_PROFILE", "1")
    try:
        key = int(model)
    except (TypeError, ValueError):
        key = 1
    return dict(MODEL_PROFILES.get(key, MODEL_PROFILES[1]))

# ---- Gains ----------------------------------------------------------------------------
K_ROLL = 1.0
# Taper the ROLL command by pointing-error MAGNITUDE below this many degrees. 0.0 = OFF, which
# is the historical behaviour every register measurement was taken at, and remains the default.
#
# THE DEFECT IT ADDRESSES (measured 2026-08-22). `phi = atan2(az, el)` is a DIRECTION -- where
# the error sits about the nose axis -- and carries no information about how BIG the error is.
# `pitch` is scaled by `err_gain ~ los_deg / PROPORTIONAL_DIV` and so decays to ~0 as the
# solution converges; `roll` has no such term, so as los_deg -> 0 both az and el vanish and
# atan2() returns an essentially arbitrary angle. Measured over 20,914 in-envelope steps of
# match_base self-play at the shipped 4000 m / 60 deg envelope, roll authority is INVERTED with
# respect to error:
#
#     LOS band     steps   mean|roll|   frac |roll| > 0.5
#      0.0-0.5 deg  5746      0.481          47.9%     <- on target, rolling hard
#      1.0-2.0 deg  4948      0.460          19.2%
#      5.0- 15 deg  1347      0.251          17.5%
#       15- 60 deg  1061      0.045           0.0%     <- far off, barely rolling
#
#   Inside the actual scoring window (152.4-914.4 m AND LOS <= 1.0 deg): 375 steps,
#   mean |roll| 0.561, and 18.9% of them at near-full-scale roll (> 0.9).
#
# i.e. the aircraft throws the gun line around at exactly the moment it must hold the pipper
# inside the <=1 deg gate. That is consistent with this project's long-standing signature of
# excellent MINIMUM ATA (0.014-0.024 deg) but poor DWELL, and with the three draws that
# "reached the angle gate and scored nothing" (Sec 4.1, throttle rationale).
#
# The taper must NOT reach the large-error regime: roll being maximal at phi = 180 deg is the
# whole point of this controller (it is what escapes Controller_CY's dead spot), so the gain is
# 1.0 everywhere above ROLL_TAPER_DEG and only shrinks below it.
ROLL_TAPER_DEG = float(os.environ.get("DOGFIGHT_VPTRACK_ROLL_TAPER_DEG", "0.0"))
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
# RE-MEASURED 2026-09-09 -- THE PREMISE BELOW IS STALE AND THE SIGN HAS FLIPPED.
# corner_speed_probe.py on the CURRENT DLL and the shipped 6000/120 config (N=20 self-play,
# match_base) reports mean TAS **506.4 kt** (min episode mean 374.2, max 594.0) -- we now fly
# ~66 kt ABOVE the 430-450 band, not ~100 below it. The 339.6 kt figure below was measured
# 2026-08-07, before the 6000/120 envelope, the hard deck and three tree rebuilds.
# So CORNER_KT = 440 is now a DECELERATING setpoint, and the 2026-08-07 rejection ("forcing it
# ~100 kt faster widens the turn radius") argued against a change this knob no longer makes.
# Being above corner widens the radius the same way, which is a candidate mechanism for the
# measured overshoot (median ep_min_distance 19.9 m vs the 152.4 m zero-damage floor).
# Weak directional support from the same probe: won episodes carry +3.19 pp of corner-time
# advantage vs +1.22 lost (+0.72 pooled SD).
#
# RE-MEASURED 2026-09-09 WITH THE CORRECTED PREMISE -- STILL HARMFUL. N=40/cell against the
# N=100 shipped control: WEZ-entry cutoff 60.0 -> 47.5%, aggressor 72.0 -> 65.0%, sniper
# 91.0 -> 65.0% (z = -3.75); damage differential vs cutoff -0.078 -> -0.191. And the radius
# story is refuted by its own arm -- against `sniper`, the one archetype we do NOT overshoot
# into, slowing made the overshoot WORSE (median min range 242 -> 102 m). Two independent
# measurements now reject this knob from opposite sides of the band. KEEP IT OFF.
#
# MEASURED 2026-08-07 -- HARMFUL AT 440 kt. Default OFF. (Stale premise; see above.)
#     self-play vs champion  7W/16D/7L, identical to control (23.3%)
#     vs BT                  73.1% win rate but 0 KILLS and 0.63 damage (champion: 8 and 14.29)
# The win RATE survived while damage collapsed 96%: dealing 0.63 against an opponent dealing
# zero still scores as a differential win. Win rate alone would have passed this change --
# check damage and kills alongside it.
# Most likely the setpoint, not the idea: the 2026-08-07 probe showed this airframe settling at
# 339.6 kt, and forcing it ~100 kt faster widens the turn radius so it cannot hold a 152-914 m
# WEZ. THAT SETTLING SPEED NO LONGER HOLDS -- it is 506.4 kt now, so the same argument now runs
# the other way. 430-450 kt is a real-F-16 figure at a particular weight and altitude; this JSBSim model's
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
# RE-TESTED 2026-09-09 AGAINST THE CUTOFF -- THE OPPONENT THIS WAS PARKED WAITING FOR. It lost,
# and worse than the 2026-08-06 wash. N=40/cell against the N=100 shipped control:
#
#     vs cutoff     wins 38% -> 15%;  dealt 0.471 -> 0.301, TAKEN 0.549 -> 0.605
#                   damage differential -0.078 -> -0.304
#     vs aggressor  dealt 0.600 -> 0.271, taken 0.626 -> 0.535; differential -0.027 -> -0.264
#     vs sniper     dealt 0.821 -> 0.667, taken 0.084 -> 0.048; differential +0.737 -> +0.619
#
# Note the cutoff column: damage taken went UP. Against that opponent the break does not even
# deny damage, it only spoils our own solution. The likely reason is the guard's own blind spot
# -- _losing_gun_duel() requires 152.4 <= rng and the median closest approach is ~20 m, so it
# fires late and rarely, in a geometry where breaking cannot buy separation.
#
# F26-DEFENSIVE IS THEREFORE CLOSED, not parked. Re-open it only if the overshoot is fixed first
# (see STANDOFF_M), which would put the fight back inside the band where this test can fire.
# Enable with DOGFIGHT_VPTRACK_DEFENSIVE=1 or --{side}-vptrack-defensive 1.
# ---- Hard-deck guard (2026-09-03) ------------------------------------------------------
# THE DEFECT IT ADDRESSES. This controller overrides roll/pitch/rudder for every step inside the
# engagement envelope, and it has no altitude term at all. Widen the envelope far enough and it
# therefore keeps flying the aircraft even when the bandit is behind us and the BT wants to climb
# -- Gate 0 (Task_ClimbToSafeAltitude, trigger 914 m) never gets the stick. Measured cost at
# N=50 vs the corrected cutoff on match_base:
#
#     envelope    own altitude-floor losses    kills    damage dealt/taken
#     6000/90               0                    11        0.282 / 0.278
#     6000/120              6                     5        0.341 / 0.318
#     8000/120              7                     5        0.348 / 0.318
#
# The 120 deg arms have the best damage differential this project has ever measured (+0.030) and
# throw it away by flying into the ground 6-7 times in 50.
#
# Deliberately altitude-only, NO sink-rate term: state[VZ] is NED-down locally but the wire sends
# velocity.z UP-POSITIVE, and LiveVerticalFrameProvider only corrects state[2] unless
# DOGFIGHT_LIVE_STATE_COMPLETE=1 (Sec 4.1 F46). A guard keyed on VZ would invert on the live path
# -- exactly the train/deploy divergence this file exists to avoid. state[D] IS corrected live
# (F53), so altitude alone is the safe signal.
#
# Set ABOVE Gate 0's own 914 m trigger so the BT is already climbing when we hand back.
# DEFAULT OFF: the shipped 6000/90 takes ZERO altitude-floor losses, so this can only cost it.
# Enable with DOGFIGHT_VPTRACK_HARD_DECK_M or --{side}-vptrack-hard-deck.
HARD_DECK_M = float(os.environ.get("DOGFIGHT_VPTRACK_HARD_DECK_M", "0.0"))

# TIME-TO-IMPACT DECK GUARD (F62, added 2026-09-04). Hands back when the aircraft is this many
# seconds from the ground AT ITS CURRENT SINK RATE, regardless of how high it currently is.
#
# WHY ALTITUDE ALONE IS THE WRONG QUANTITY. The 8-27 trajectory (F62) crosses this file's 1000 m
# floor at 236 m/s of sink, inverted at -95 deg bank and -43 deg pitch. That is 3.9 s of life.
# A wings-level 9 g pull at 331 m/s has a 1,249 m radius and loses ~375 m recovering from -45
# deg -- survivable -- but from -95 deg of bank the aircraft must ROLL FIRST, and one second of
# roll costs another 236 m. The margin is gone before the pull starts. An altitude threshold
# cannot express "how long do I have"; alt / sink_rate can.
#
# HOW IT AVOIDS F46's SIGN INVERSION. It does NOT read state[VZ]. state[VZ] is NED-down locally
# but the wire sends velocity.z UP-POSITIVE, and LiveVerticalFrameProvider only corrects
# state[2] unless DOGFIGHT_LIVE_STATE_COMPLETE=1 -- a VZ-keyed guard would dive when it should
# climb on the live path. Sink rate here is FINITE-DIFFERENCED from state[D], the one vertical
# channel confirmed corrected live (F53). A stale or noisy altitude gives a noisy rate, not an
# inverted one, which is the failure mode we can afford.
#
# WHAT THIS DOES NOT FIX. Handing back earlier gives Gate 0 more room; it does not teach Gate 0
# to roll wings-level before pulling. The 8-27 trace shows a pull-while-inverted geometry that
# lives in the BT (Task_ClimbToSafeAltitude aims +5000 m straight up), not in this file, and
# fixing it needs a DLL/XML change. This buys that recovery TIME, not competence.
#
# DEFAULT OFF, like HARD_DECK_M: unmeasured knobs do not ship (F59, F60-corner_hold).
DECK_TTC_S = float(os.environ.get("DOGFIGHT_VPTRACK_DECK_TTC_S", "0.0"))
# Sink rates below this are treated as level flight -- differencing altitude across one tick is
# noisy, and a guard that trips on numerical jitter at 8,000 m would hand back permanently.
_DECK_MIN_SINK_MPS = 5.0
# Sanity band for the differenced timestep. Outside it the sample is discarded rather than
# turned into a wild rate: SIM_TIME is not on the list of channels F53 confirmed corrected on
# the live path, so it is used defensively here and never trusted blindly.
_DECK_DT_MIN_S, _DECK_DT_MAX_S = 1e-4, 1.0

# ---- Range standoff on the AIM POINT (2026-09-09) --------------------------------------
# THE DEFECT IT ADDRESSES, measured on the current DLL (artifacts/eval/ab_fixed_0908, N=100 vs
# the organizers' cutoff): median ep_min_distance is **19.9 m** and **80 of 100 episodes go
# inside the 152.4 m zero-damage floor**. We hold <=1 deg for a mean of 173.5 steps but only
# 62.6 of them are inside the scoring band -- 64% of our pointing time is spent where the gun
# scores nothing. The first gate trace ever taken says the same thing from the other side: the
# Gun_DistLt914 decorator passes on 1,056 of 15,611 ticks and Gun_Track ends up running on 0.2%.
#
# WHY THE TWO EXISTING RANGE MECHANISMS CANNOT FIX IT. Both are THROTTLE-only --
# GUNTRACK_TARGET_RANGE_M in Task_GunTrack.cpp and TARGET_RANGE_M below, the latter already
# active in the shipped config. Throttle cannot arrest a merge; the aim point is what decides
# whether the flight path intersects the target or passes behind it. Nothing anywhere biases the
# aim point for range, so the law flies pure pursuit -- a collision course -- every tick.
#
# WHAT THIS DOES. Inside the standoff radius, aim at a point on the target's SIX rather than at
# the target: lag grows as (standoff - rng), so at the boundary this is exactly pure pursuit (no
# discontinuity) and at 20 m it points 200 m behind their tail. That is lag pursuit -- the
# textbook answer to an overshoot -- and it opens range instead of trading nose position for it.
#
# DEFAULT 0.0 = OFF, so every register measurement stays valid and the shipped config is
# unchanged until a measurement says otherwise (F59/F60: unmeasured knobs do not ship). Enable
# with DOGFIGHT_VPTRACK_STANDOFF_M or --{side}-vptrack-standoff-m. 220 m is the natural first
# value -- it is where the damage coefficient peaks and what both existing mechanisms already
# target, so the three would finally agree instead of two of them being ignored.
STANDOFF_M = float(os.environ.get("DOGFIGHT_VPTRACK_STANDOFF_M", "0.0"))

DEFENSIVE_BREAK = os.environ.get("DOGFIGHT_VPTRACK_DEFENSIVE", "0") not in ("0", "false", "False")
THREAT_ATA_DEG = float(os.environ.get("DOGFIGHT_VPTRACK_THREAT_ATA", "8.0"))
WEZ_MIN_M, WEZ_MAX_M = 152.4, 914.4
# Phase 1's half-angle gate (COMPETITION_RULES Sec 6.2; `reward_lib.WEZ_PHASES` stores the same
# thing as a FULL cone width, hence 2.0 there and 1.0 here). Binary: inside it a hit pays the
# full 1.0 coefficient, outside it pays nothing at all in Phase 1.
PHASE1_LOS_DEG = 1.0

# ---- Time-phased engagement window (2026-09-09) ----------------------------------------
# COMPETITION_RULES Sec 6.2: the server WIDENS the scoring cone as the 200 s clock runs down --
# LOS < 1/2/3 deg and 500-3000/3500/4000 ft at t = 0/100/150 s -- explicitly to stop draws. Until
# now nothing on our side knew that: every engagement threshold in this file and in the Rule XML
# is a fixed constant, so the aircraft flew identical geometry at t = 10 s and t = 190 s.
#
# WHAT THIS CHANGES. Only what counts as "I already have a shot, stop manoeuvring for range".
# Late in the match a wider, longer cone genuinely scores, so treating it as a shot is correct;
# early it does not, and the tighter Phase 1 gate should hold.
#
# THE ARGUMENT AGAINST, recorded because it is real and this may still lose: later phases pay
# 0.3 and 0.1 against Phase 1's 1.0, and a Phase-1-quality shot pays 1.0 AT ANY TIME (narrowest
# qualifying phase wins). Measured over the shipped config's own traces, Phase 1 is ~92.6% of
# expected damage. So widening our own acceptance can only help where a Phase 1 shot was NOT
# available anyway -- it must never displace one, which is why `shot_in_hand` keeps using the
# tightest qualifying phase.
#
# THE ARGUMENT FOR: 43% of episodes against the cutoff end on the 200 s clock, and a timeout is
# adjudicated purely on damage differential. In a match decided by a hair, 0.1-coefficient hits
# that would otherwise be zero can flip it. That is a real mechanism, not a rounding error.
#
# Sourced from reward_lib.WEZ_PHASES so the schedule cannot drift from the one the scorer uses.
# DEFAULT OFF: every register number was measured without it.
# ---- Adaptive range: close when we out-angle them, extend when we do not (2026-09-09) ------
# THE MECHANIC THIS EXPLOITS. Damage is SYMMETRIC in range: at separation r the damage to them is
# f(r) if OUR ata is in the cone, and the damage to us is the SAME f(r) if THEIR ata is in it
# (COMPETITION_RULES Sec 6.2; f is monotonically decreasing in r). So range does not create
# advantage -- it MULTIPLIES whatever angular advantage already exists:
#
#     differential = f(r) x [ 1{we are in cone} - 1{they are in cone} ]
#
# Closing amplifies that bracket. If it is positive, closing wins harder; if it is NEGATIVE,
# closing loses harder. A fixed standoff distance cannot express this, because the right answer
# genuinely differs by opponent: measured dealt/taken is 0.86 vs the cutoff (we lose the
# exchange), 0.96 vs aggressor (even) and 1.42 vs mirror (we win it).
#
# THE POLICY. Extend only while the bandit holds the tighter angle; otherwise close and press.
# That is `_losing_gun_duel`'s comparison reused as a RANGE controller rather than as a break
# trigger, and it composes with the Phase-1 gate below: a shot already in hand always wins.
#
# WHY NOT JUST PICK A BETTER FIXED NUMBER. Because the damage-optimal setpoint is opponent
# independent (~620 ft at tight range control, drifting outward as range-holding degrades) but
# the DIFFERENTIAL-optimal setpoint is not: against an opponent who out-angles us, the best range
# is as far as possible, and against one we out-angle it is as close as the 500 ft floor allows.
#
# DEFAULT OFF. Enable with DOGFIGHT_VPTRACK_ADAPTIVE_RANGE=1 or --{side}-vptrack-adaptive-range.
# ---- Match clock that survives the live wire (2026-09-10) ------------------------------
# THE DEFECT. `plane_info_to_state()` zeroes a 51-slot array and fills ONLY indices 0-8:
# position, rotation, velocity. The wire struct ("<iQb3f3f3f") carries nothing else. But
# StateIndex.SIM_TIME is index 41 and StateIndex.HEALTH is 45, so BOTH ARE PERMANENTLY ZERO IN
# COMPETITION -- they exist only inside the local simulator.
#
# Anything keyed on them therefore works in every benchmark we run and does nothing at all on
# match day. That already bit one shipped-adjacent knob: DECK_TTC_S finite-differences altitude
# over `dt` taken from SIM_TIME, so live `dt` is 0.0, which fails its own _DECK_DT_MIN_S guard
# and the time-to-impact deck guard can never fire. It measured fine locally because locally
# SIM_TIME is real. This is the F46 train/deploy divergence class, and it is why HARD_DECK_M's
# comment insists on altitude rather than VZ.
#
# THE FIX. compute_action() is called exactly once per frame, so counting calls gives elapsed
# time without the wire. SIM_TIME is still preferred when it is actually populated, so every
# local measurement stays bit-identical and only the live path changes behaviour.
#
# THE CEILING, named because it is real: the counter assumes one call per frame at TICK_HZ. If
# the harness ever double-steps or drops frames the clock drifts, silently. It is reset per
# episode in reset(). A native clock exists and is correct (CPPBehaviorTree.cpp:297 advances
# BB->RunningTime by DeltaSecond, verified 0.02 to 199.98 s over 374,748 traced ticks), but
# reaching it from Python needs a DLL rebuild, which would invalidate every current benchmark.
TICK_HZ = 60.0

ADAPTIVE_RANGE = os.environ.get("DOGFIGHT_VPTRACK_ADAPTIVE_RANGE", "0") not in ("0", "false", "False")

PHASED_WINDOW = os.environ.get("DOGFIGHT_VPTRACK_PHASED_WINDOW", "0") not in ("0", "false", "False")


def phase_window(sim_time_s: float) -> tuple[float, float]:
    """(max_range_m, los_half_angle_deg) of the WIDEST cone scoring at this match time.

    WEZ_PHASES stores angle_deg as the FULL cone width; the half-angle is what an ATA compares
    against, hence the /2. Falls back to Phase 1 on a non-finite clock -- a bad timestamp must
    tighten us to the highest-paying cone, never loosen us into one that scores nothing.
    """
    if not np.isfinite(sim_time_s):
        return WEZ_MAX_M, PHASE1_LOS_DEG
    widest = _WEZ_PHASES[0]
    for ph in _WEZ_PHASES:
        if sim_time_s >= ph["min_time_s"]:
            widest = ph
    return float(widest["max_range_m"]), float(widest["angle_deg"]) / 2.0

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
        self.roll_taper_deg = float(kwargs.pop("roll_taper_deg", ROLL_TAPER_DEG))
        self.threat_ata_deg = float(kwargs.pop("threat_ata_deg", THREAT_ATA_DEG))
        self.standoff_m = float(kwargs.pop("standoff_m", STANDOFF_M))
        self.phased_window = bool(kwargs.pop("phased_window", PHASED_WINDOW))
        self.adaptive_range = bool(kwargs.pop("adaptive_range", ADAPTIVE_RANGE))
        # Frames seen this episode; the last-resort clock. See TICK_HZ above.
        self._ticks = 0
        # The server's own frame counter when the context carries one; preferred over _ticks.
        self._frame_index: int | None = None
        self.hard_deck_m = float(kwargs.pop("hard_deck_m", HARD_DECK_M))
        self.deck_ttc_s = float(kwargs.pop("deck_ttc_s", DECK_TTC_S))
        # Previous sample for the finite difference. None until the second call.
        self._deck_prev_alt_m: float | None = None
        self._deck_prev_t_s: float | None = None
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
        self._ticks = 0
        self._frame_index = None
        return super().reset(context)

    def _match_time_s(self, own) -> float:
        """Elapsed match seconds, working on the live wire as well as in the simulator.

        Three sources, most authoritative first:
          1. StateIndex.SIM_TIME, when populated. Local runs therefore stay bit-identical.
          2. The SERVER's frame index, from context.info. Both live sites in
             dogfight/unreal/policies.py pass "frame_index" and the local env passes "timestep",
             so this is monotonic and immune to a harness that double-steps or drops frames.
          3. Our own call count, as a last resort if a caller supplies neither.

        Never returns a bare 0.0 for "unknown", because 0.0 reads as "Phase 1 forever" and "no
        time has passed" to every caller downstream.
        """
        t = float(own[StateIndex.SIM_TIME])
        if np.isfinite(t) and t > 0.0:
            return t
        if self._frame_index is not None:
            return self._frame_index / TICK_HZ
        return self._ticks / TICK_HZ

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

        # HARD DECK. Below this, hand the aircraft back to the BT: Gate 0 self-triggers at 914 m
        # and is the only thing in the stack that climbs. Returning None (rather than biasing
        # pitch here) keeps survival in ONE place instead of two that can fight each other.
        if self.hard_deck_m > 0.0 or self.deck_ttc_s > 0.0:
            own_alt_m = -float(own[StateIndex.D])
            if np.isfinite(own_alt_m):
                if self.hard_deck_m > 0.0 and own_alt_m < self.hard_deck_m:
                    self._deck_prev_alt_m = own_alt_m
                    self._deck_prev_t_s = self._match_time_s(own)
                    return None
                if self.deck_ttc_s > 0.0:
                    t_s = self._match_time_s(own)
                    prev_alt, prev_t = self._deck_prev_alt_m, self._deck_prev_t_s
                    self._deck_prev_alt_m, self._deck_prev_t_s = own_alt_m, t_s
                    if prev_alt is not None and prev_t is not None:
                        dt = t_s - prev_t
                        if _DECK_DT_MIN_S <= dt <= _DECK_DT_MAX_S:
                            sink_mps = (prev_alt - own_alt_m) / dt   # +ve = descending
                            if sink_mps >= _DECK_MIN_SINK_MPS:
                                if own_alt_m / sink_mps < self.deck_ttc_s:
                                    return None
                else:
                    self._deck_prev_alt_m = own_alt_m
                    self._deck_prev_t_s = self._match_time_s(own)

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

        # RANGE STANDOFF. Slide the aim point back along the TARGET's own forward axis -- i.e.
        # toward their six -- by however far inside the standoff radius we are. Zero lag exactly
        # at the boundary, so enabling this does not put a step in the command; full effect only
        # in the knife-fight regime the measurement says we live in. Guarded so the default
        # (0.0) leaves this function bit-identical to before it existed.
        # DO NOT TRADE ANGLE FOR RANGE WHILE A SHOT IS ON THE TABLE (2026-09-09).
        #
        # COMPETITION_RULES Sec 6.2: Phase 1 pays `1.0 * (3000 - r_ft) / 2500` and needs range
        # 500-3000 ft AND LOS < 1 deg. Range is a SMOOTH multiplier; the angle is a BINARY GATE.
        # Sliding the aim point off the target to open range therefore risks dropping us out of
        # the cone entirely and scoring zero, in exchange for a fractional improvement in a
        # multiplier. That asymmetry is almost certainly why the ungated standoff lost its N=100
        # confirmation (bo3 1.53 vs 1.60 control) after looking strong at N=40.
        #
        # Phase 1 is 92.6% of expected damage (measured from the per-phase step counts and the
        # rules' own formulas), so protecting the Phase-1 gate dominates every range refinement.
        # Lag only when we do NOT already have the shot.
        own_ata_deg = float(np.arccos(_clamp(float(np.dot(fwd, rel_u)), -1.0, 1.0)) * RADTODEG)
        if self.phased_window:
            # The server's cone widens at 100 s and 150 s (COMPETITION_RULES Sec 6.2). Accept the
            # widest cone that actually scores right now, so a late shot that pays 0.3 or 0.1 is
            # treated as a shot instead of being manoeuvred away from. It can only ADD acceptance:
            # Phase 1 stays inside every later phase, so a 1.0-coefficient solution is never
            # displaced by a cheaper one.
            _max_r, _los = phase_window(self._match_time_s(own))
        else:
            _max_r, _los = WEZ_MAX_M, PHASE1_LOS_DEG
        shot_in_hand = (WEZ_MIN_M <= rng <= _max_r) and own_ata_deg <= _los
        # ADAPTIVE RANGE. Extend only while they out-angle us; otherwise close and press the
        # advantage, because f(r) multiplies the differential in whichever direction it points.
        losing_angle = True
        if self.adaptive_range:
            _tf, _, _ = body_axes(tgt)
            _to_us = np.array([
                float(own[StateIndex.N]) - float(tgt[StateIndex.N]),
                float(own[StateIndex.E]) - float(tgt[StateIndex.E]),
                -(float(own[StateIndex.D]) - float(tgt[StateIndex.D]))])
            _n = float(np.linalg.norm(_to_us))
            if np.isfinite(_n) and _n > 0:
                _tgt_ata = float(np.arccos(_clamp(float(np.dot(_tf, _to_us / _n)), -1.0, 1.0)) * RADTODEG)
                losing_angle = _tgt_ata < own_ata_deg
            # A degenerate relative vector leaves losing_angle True, i.e. falls back to the
            # cautious branch: extend. Erring toward separation cannot cost more than the
            # multiplier, while erring toward closure hands the exchange to a better-angled foe.

        if (self.standoff_m > 0.0 and rng < self.standoff_m
                and not shot_in_hand and losing_angle):
            tgt_fwd, _, _ = body_axes(tgt)
            # CAP THE LAG AT THE RANGE ITSELF (<= 45 deg of lag). Uncapped, the deficit grows
            # without bound as range collapses: at 30 m inside a 220 m standoff the aim point
            # lands 190 m BEHIND the target, i.e. behind US, los_deg exceeds engage_los_deg and
            # `_tracking_stick` silently returns None and hands the aircraft to the BT. Caught by
            # scripts/test_standoff_aimpoint.py -- the knob would have quietly disabled the
            # controller in exactly the knife-fight geometry it was built to fix.
            lag_m = min(self.standoff_m - rng, rng)
            aim_vec = rel - tgt_fwd * lag_m
            aim_n = float(np.linalg.norm(aim_vec))
            if np.isfinite(aim_n) and aim_n > 1e-6:
                aim_u = aim_vec / aim_n

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
        roll_gain = (
            1.0 if self.roll_taper_deg <= 0.0
            else _clamp(los_deg / self.roll_taper_deg, 0.0, 1.0)
        )
        roll_cmd = _clamp(K_ROLL * roll_gain * phi / np.pi, -1.0, 1.0)

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
        # Deliberately NOT los_deg: with a standoff active that is the angle to the LAG POINT,
        # and _losing_gun_duel compares our ATA against theirs. Feeding it the lag angle would
        # make us look worse-aligned than we are and fire the break spuriously. Computed inside
        # the guard so the default path (defensive_break off) does no extra work at all.
        if self.defensive_break and self._losing_gun_duel(own, tgt, rng, own_ata_deg):
            self._break_steps += 1
            # Deliberately UNTAPERED: this is a max-rate break, not a tracking command, and it
            # only fires when we are losing the gun duel -- holding a steady pipper is exactly
            # what we are trying to stop doing here.
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
        # ONE FRAME. Counted here rather than in _tracking_stick, which returns early on several
        # paths (hard deck, degenerate range, outside the envelope) and would under-count the
        # clock exactly when the aircraft is in trouble. See TICK_HZ for why a counted clock is
        # needed at all: StateIndex.SIM_TIME is index 41 and the live wire fills only 0-8.
        self._ticks += 1
        # PREFER THE SERVER'S OWN FRAME COUNTER. Both live construction sites in
        # dogfight/unreal/policies.py pass info={"frame_index": ...}, and the local env passes
        # info={"timestep": ...}. Either is monotonic and authoritative, so it cannot drift the
        # way counting our own calls can if the harness ever double-steps or drops a frame.
        # Reading it needs no change to src/dogfight -- it is already in the context.
        _info = getattr(context, "info", None) or {}
        _fi = _info.get("frame_index", _info.get("timestep"))
        if _fi is not None:
            try:
                self._frame_index = int(_fi)
            except (TypeError, ValueError):
                pass

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
