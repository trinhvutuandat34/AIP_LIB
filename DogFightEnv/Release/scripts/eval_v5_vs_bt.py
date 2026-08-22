"""Corrected copy of scripts/eval_matchup.py for the real_eagle v5 evaluation.

Only change vs eval_matchup.py: forward the effective observation mode +
observation module into build_provider(), so verify_bundle_observation compares
the bundle's recorded obs_mode ("real_eagle15") against the SAME mode the env
runs with -- instead of the empty string eval_matchup passes, which makes the
guard raise a false "Bundle/runtime observation mismatch" for any bundle that
correctly records its obs_mode. Also runs a bundle-health (NaN/Inf) check first.

PHASE-AWARE SCORING (2026-08-06)
--------------------------------
This harness used to report only `ep_wez_steps`, which comes from the platform's
`single_agent_env.py::update_damage()` -- a FLAT cone: |ATA| <= angle_deg/2 = 1.0 deg,
500-3000 ft, no time phases, no damage coefficient. The real competition
(COMPETITION_RULES.md Sec6.2) WIDENS the cone as the 200 s match runs:

    Phase 1   0-100 s   LOS < 1 deg   500-3000 ft   coef 1.0
    Phase 2 100-150 s   LOS < 2 deg   500-3500 ft   coef 0.3
    Phase 3 150-200 s   LOS < 3 deg   500-4000 ft   coef 0.1

with narrowest-qualifying-phase-wins (a Phase-1-quality shot pays Phase-1 damage
even late). That gap is not academic for this project: the BT's tracking converges
to a documented ~1.038 deg ATA attractor (Controller_CY.cpp's history), which is
OUTSIDE the flat 1.0 deg gate and therefore scores exactly zero locally -- but
INSIDE the Phase-2 and Phase-3 cones, i.e. it scores on the live server from
t=100 s onward. Every A/B run judged on `ep_wez_steps` alone has been reading 0
for a configuration that is not actually scoreless.

So each episode is now ALSO scored against the real phased model, using
student/reward_lib.py's existing `match_wez_phase()` / `wez_damage_estimate()`
(the same functions my_reward.py's damage term already uses). Both numbers are
reported side by side; the flat one is kept because it is what the platform's
own termination/health path actually uses locally.

ANGLE CONVENTIONS -- 2D vs 3D, why every angle column is suffixed
-----------------------------------------------------------------
The WEZ is a CONE about the nose, not a horizontal sector, and GeoMathUtil exposes two
different angles under one function name (`_get_antenna_train_angle`, `proj` flag):

  proj=False  3D: full Tx*Ty*Tz into body frame, then arccos(p_unit_t[0]) -- the true
                  angle between the nose and the LOS vector. Unsigned. THIS is the cone
                  half-angle the damage gate tests, and what update_damage() uses.
  proj=True   2D: Tz (heading) only, then arctan2(y, x) -- horizontal azimuth, signed,
                  elevation discarded entirely.

They are different quantities and can disagree by a lot: a target directly above you is
0 deg in 2D and 90 deg in 3D. The platform's info dict reports `final_ata_deg`/`final_aa_deg`
with proj=True, while this harness's per-step tracking metrics use proj=False -- so the old
CSV put both in the same row under names that gave no way to tell them apart, and reading
`final_ata_deg` as "how close to the gate" silently understated the miss. Every angle column
now carries an explicit `_2d` / `_3d` suffix; when in doubt, `_3d` is the one the gate uses.

No `final_aa_deg_3d` is emitted on purpose: GeoMathUtil's 3D aspect-angle mode has a matrix
singularity exactly at 180 deg (head-on) where it silently returns 0 -- documented in
student/my_observation_v2.py, which is why the observation builder passes proj=True for AA
specifically. Aspect angle stays 2D-only here rather than shipping a column that reads 0 at
the single geometry it most needs to be right about.

CAVEATS -- read before trusting the phased columns:
  * This is an ESTIMATE of live-server scoring, not ground truth. The live Unreal
    server scores independently of this codebase, and `update_damage()` remains
    the only thing that mutates local health / drives local win-loss termination.
    `phased_outcome` is therefore advisory: it never changes how the episode ran.
  * Sampled once per env step. Exact when step_ratio == 1 (the default this
    harness runs at -- env_config sets no step_ratio/delta/time_step, and
    _resolve_step_ratio() falls back to 1.0), because update_damage() then also
    runs once per env step on the same post-step state. If step_ratio > 1 the
    per-substep geometry is invisible from here and the estimate scales one
    sample across the whole hold -- the harness warns when that happens.
  * Phase 2/3 only exist after t=100 s / t=150 s. An episode that ends early
    (e.g. "target altitude below min", which truncated the 2026-08-05 runs at
    ~42 s) never reaches them, so its phased score is NOT representative of a
    200 s match. The summary reports phase-time coverage for exactly this reason.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]   # Release/ root (scripts/ is one below)
SRC = ROOT / "src"
for _p in (ROOT, SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from DogFightEnvWrapper import DogFightWrapper
from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.ai.student_hooks import load_observation_hook
from run_local_dogfight import (
    backend_to_env_mode,
    build_provider,
    resolve_vptrack_floor,
)
from student.controller_providers import (
    ENGAGE_LOS_DEG as VPT_LOS_DEFAULT,
    ENGAGE_RANGE_M as VPT_RANGE_DEFAULT,
    THROTTLE_CONTROL as VPT_THROTTLE_DEFAULT,
)
from student.inference_providers import require_healthy_bundle
from student.obfm_scenario_wrapper import ObfmScenarioWrapper, OBFM_ALTITUDE_M, OBFM_SPEED_MPS
from student.match_scenario_wrapper import (
    MatchScenarioWrapper, MATCH_ALTITUDE_M, MATCH_SPEED_MPS,
    MATCH_SEPARATION_MIN_M, MATCH_SEPARATION_MAX_M, MATCH_LOS_DEG,
)
from student.reward_lib import WEZ_PHASES, match_wez_phase, wez_damage_estimate
from dogfight.sim.state_schema import StateIndex

ALPHA_SCHEDULE_DEG = (0, 20, 40, 60, 80, 100, 120, 140, 160, 180)

# Competition match length (COMPETITION_RULES.md Sec5): 200 s. At the 60 Hz sim rate and this
# harness's step_ratio=1 that is 12000 env steps. Both defaults below encode the SAME 200 s so
# neither can silently truncate the match before Phase 3 -- the previous 300 s / 18000-step
# defaults ran a match 1.5x longer than the real one, which reweights the phase mix.
MATCH_DURATION_S = 200.0
MATCH_STEP_LIMIT = 12000

CSV_FIELDS = [
    "episode", "alpha_deg", "outcome", "end_condition",
    "ownship_health", "target_health", "total_reward", "steps",
    "ep_wez_steps", "ep_min_distance", "initial_distance_m",
    # _2d / _3d suffixes are mandatory here -- see the ANGLE CONVENTIONS note in the module
    # docstring. These two come straight from the platform's info dict, which computes them
    # with proj=True (2D azimuth). They are NOT comparable to the gate.
    "final_ata_deg_2d", "final_aa_deg_2d",
    # 2026-08-05: terminal-tracking quality. ep_min_ata_deg_3d classifies which mode the episode
    # landed in (see the bimodality note in the episode loop); the le*_deg_3d pair is its dwell.
    "ep_min_ata_deg_3d", "ep_steps_le2_deg_3d",
    # 2026-08-06: ep_steps_le1_deg_3d is the dwell inside the ACTUAL flat gate (angle_deg/2 = 1.0
    # deg), added because le2's 2.0 deg is the full cone width, not the gate -- reading it as
    # "steps that scored" overstates by exactly the margin this project is stuck on.
    # final_ata_deg_3d is the cone-convention counterpart of final_ata_deg_2d, so "how did the
    # episode end" can be read against the gate instead of against a different quantity.
    "ep_steps_le1_deg_3d", "final_ata_deg_3d",
    # 2026-08-06: phase-aware (real competition) scoring -- see the module docstring.
    "match_time_s", "ep_wez_steps_phased",
    "ep_wez_steps_p1", "ep_wez_steps_p2", "ep_wez_steps_p3",
    "ep_damage_dealt", "ep_damage_taken", "phased_outcome",
]


def _infer_gate(own_ata, tgt_ata, hca, dist):
    """Approximate reconstruction of Rule_forTraining.xml gate priority to label each step's
    likely active branch. Omits Gate 0 (altitude), energy ratios, Notch/scissors -- it resolves
    only the key question: does the geometry land in Gate 1 (defensive preemption) vs Gate 2.5
    (gun-hold) vs a maneuver. NOT a substitute for the BT's GetAnnotation (not exposed to Python);
    read it as a strong hint, not ground truth."""
    enemy_in_sight = tgt_ata <= 95.7                 # CheckSight.cpp: target's LOS-to-us <= 95.74
    if enemy_in_sight and dist <= 2000.0 and hca < 150.0:
        return "Gate1_threat"                         # jink/break preempt
    if hca > 150.0 and own_ata < 20.0 and tgt_ata < 20.0 and 500.0 < dist < 10000.0:
        return "Gate2_headon"
    if 150.0 < dist < 914.0 and own_ata < 8.0:        # matches the widened gun-hold gate
        return "Gate2p5_gunhold"
    return "maneuver"


class VPProbe:
    """Transparent ActionProvider wrapper that captures BTActionProvider's `vp_valid` flag.

    WHY. BTActionProvider._vp_to_array() substitutes SAFE_VP (a ZERO vector) whenever GetVP()
    returns a non-finite value, and reports that only through ActionResult.info["vp_valid"] --
    which the env discards. The result is that `sim.VP` reads exactly (0,0,0) in two completely
    different situations: the BT genuinely aiming at a zero point, or GetVP failing and the
    provider quietly zeroing it. The controller-mirror columns cannot be interpreted until those
    are separated, because in the second case the mirror is being fed a substituted zero rather
    than the aimpoint the DLL actually steered to.

    Delegates everything else via __getattr__, so _iter_bt_providers() still finds the wrapped
    BT through `ai_pilot`/`_registered_fighter_ids` and the episode recycler keeps working.

    Only the TOP-level provider is probed. With --ownship-backend bt that IS the
    BTActionProvider; under `hybrid` the BT is nested and info["vp_valid"] will be absent, in
    which case vp_valid logs as empty rather than silently reading False.
    """

    def __init__(self, inner):
        self._inner = inner
        self.last_vp_valid = None
        self.invalid_steps = 0
        self.total_steps = 0

    def compute_action(self, context):
        result = self._inner.compute_action(context)
        info = getattr(result, "info", None) or {}
        if "vp_valid" in info:
            self.last_vp_valid = bool(info["vp_valid"])
            self.total_steps += 1
            if not self.last_vp_valid:
                self.invalid_steps += 1
        else:
            self.last_vp_valid = None
        return result

    def reset(self, context=None):
        return self._inner.reset(context)

    def __getattr__(self, name):
        # Only called for attributes not found on the wrapper itself.
        return getattr(self._inner, name)


def _iter_bt_providers(prov, _seen=None):
    """Yield every BT-bearing provider reachable from `prov`, including nested ones.

    A BTActionProvider exposes both `ai_pilot` and `_registered_fighter_ids`; a hybrid exposes
    neither but reaches one through `primary_provider`/`secondary_provider`. Recursion (rather
    than a hasattr check on the top-level object) is what makes `--*-backend hybrid` work -- see
    the MUST RECURSE note in _recycle_native_bts. `_seen` guards against a provider graph that
    is not a strict tree.
    """
    if prov is None:
        return
    if _seen is None:
        _seen = set()
    if id(prov) in _seen:
        return
    _seen.add(id(prov))
    if getattr(prov, "ai_pilot", None) is not None and getattr(prov, "_registered_fighter_ids", None) is not None:
        yield prov
    for attr in ("primary_provider", "secondary_provider"):
        yield from _iter_bt_providers(getattr(prov, attr, None), _seen)


RADTODEG = 180.0 / np.pi

# The BT's Cartesian frame is a flat-earth local tangent plane about a FIXED base LLA, hardcoded
# at LibMain.cpp's GetStick call site. sim.VP arrives in that frame, so reproducing it here is
# what lets the controller replica use the real aimpoint instead of assuming pure pursuit.
BT_BASE_LLA = (37.91455691666666, 128.18188127777776, 0.0)


def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def _lla_to_bt_cartesian(lat_deg, lon_deg, alt_m):
    """Replicate LibMain.cpp's LLAtoCartesian(LLA, BaseLLA) -> (dN, dE, dAlt), metres, Z up.

    Deliberately bug-compatible: the C++ writes `pow(1 - e2*sin^2, 3 / 2)`, and `3 / 2` is
    INTEGER division in C++, so the meridian radius M uses exponent 1, not 1.5. Replicating the
    exponent rather than "fixing" it keeps this mirror aligned with the frame the BT actually
    computes in -- correcting it here would introduce a disagreement, not remove one. (The error
    is small: e2 ~ 0.0067, so M is off by ~0.3%, well under the aimpoint offsets being measured.)
    """
    e2 = 1.0 - (6356752.3142 ** 2) / (6378137.0 ** 2)
    blat, blon, balt = BT_BASE_LLA
    s = np.sin(np.radians(blat))
    denom = 1.0 - e2 * s * s
    N = 6378137.0 / np.sqrt(denom)
    M = 6378137.0 * (1.0 - e2) / denom          # C++ exponent 3/2 -> 1; see docstring
    dN = (M + balt) * np.radians(lat_deg - blat)
    dE = (N + balt) * np.cos(np.radians(blat)) * np.radians(lon_deg - blon)
    return np.array([dN, dE, alt_m - balt])


def _controller_mirror(own, tgt, vp_neu=None):
    """Python mirror of StickController::GetStick's roll/yaw path, for the out-of-plane test.

    WHY THIS EXISTS. Controller_CY.cpp's history rules out both pitch knobs for the ~1.038 deg
    ATA attractor (INTEGRAL_CAP is not binding there; INTEGRAL_DIV swept 7.5->4.5 moved it by
    less than one sd) and lands on this hypothesis: PitchCMD = ERROR_Effect * Roll_Effect *
    Horizon_Effect is a PRODUCT, with Roll_Effect = 1 - clamp(|UTAngle|*RADTODEG/90, 0, 1). If
    the residual error is out of the pitch plane (|UTAngle| near 90 deg) then Roll_Effect ~ 0
    and the whole pitch expression is multiplied by nothing -- which is exactly the flat sweep
    response observed. That note concludes the confirmation "needs UTAngle/RollCMD/Roll_Effect
    logged per tick, which the Python-side trace cannot see" and asks for a C++ rebuild first.

    It does not need one. Every input to that path is a pure function of ownship attitude and
    the ownship->aimpoint vector, both of which the eval already holds, so the geometry can be
    recomputed here tick-for-tick with no rebuild and no DLL instrumentation.

    TWO THINGS TO KNOW BEFORE READING THE OUTPUT:
      1. It assumes the aimpoint IS the target (pure pursuit). True for Task_GunTrack -- which
         sets VP_Cartesian = TargetLocaion_Cartesian and is the node that owns the gun-hold
         regime the attractor lives in -- and for Task_pure. NOT true of lead/lag/offset nodes.
      2. So it self-validates: `rollcmd_mirror` is compared against the BT's ACTUAL RollCMD
         (BTActionProvider writes it into sim.action). When `rollcmd_delta` is ~0 the mirror is
         reproducing the real controller and its UTAngle/Roll_Effect can be trusted; when it is
         large, a different VP is active and these columns describe pure pursuit, not the tick
         that actually flew. Read Roll_Effect only on low-delta rows.

    Frame: the controller works in an altitude-POSITIVE-up Cartesian (X=N, Y=E, Z=up), while
    the env state is NED, hence the -D on the third component. Every term below is a difference
    of positions, so translating the origin to ownship is exact -- no dependence on the BT's
    LLA reference, which differs from the env's.
    """
    roll, pitch, yaw = (float(own[StateIndex.ROLL]) / RADTODEG,
                        float(own[StateIndex.PITCH]) / RADTODEG,
                        float(own[StateIndex.YAW]) / RADTODEG)
    # EulerAngle::toQuaternion -- this codebase's own non-standard construction, replicated
    # verbatim rather than swapped for a textbook one (verified 2026-08-06 to reproduce
    # CheckSight/GetStick's forward vector to 0.000 deg across attitudes incl. large roll).
    c1, s1 = np.cos(yaw / 2), np.sin(yaw / 2)
    c2, s2 = np.cos(pitch / 2), np.sin(pitch / 2)
    c3, s3 = np.cos(roll / 2), np.sin(roll / 2)
    c1c2, s1s2 = c1 * c2, s1 * s2
    W, X, Y, Z = (c1c2 * c3 + s1s2 * s3, c1 * s2 * c3 + s1 * c2 * s3,
                  s1 * c2 * c3 - c1 * s2 * s3, c1 * c2 * s3 - s1s2 * c3)
    n = np.sqrt(W * W + X * X + Y * Y + Z * Z)
    W, X, Y, Z = W / n, X / n, Y / n, Z / n

    fwd = np.array([1 - 2 * (X * X + Y * Y), 2 * (X * Z + W * Y), -2 * (Y * Z - W * X)])
    up = np.array([-2 * (Y * Z + W * X), -2 * (X * Y - W * Z), 1 - 2 * (X * X + Z * Z)])
    right = np.array([2 * (X * Z - W * Y), 1 - 2 * (Y * Y + Z * Z), -2 * (X * Y + W * Z)])

    rel = np.array([float(tgt[StateIndex.N]) - float(own[StateIndex.N]),
                    float(tgt[StateIndex.E]) - float(own[StateIndex.E]),
                    -(float(tgt[StateIndex.D]) - float(own[StateIndex.D]))])
    rel_n = float(np.linalg.norm(rel))
    if rel_n <= 0:
        return None
    rel_u = rel / rel_n
    los_deg = float(np.arccos(_clamp(float(np.dot(fwd, rel_u)), -1.0, 1.0)) * RADTODEG)

    # The controller aims at the VP, which is NOT always the target. When the caller supplies the
    # real one, drive the replica off it; otherwise fall back to pure pursuit. `vp_target_deg` is
    # the answer to "is this node aiming at the target?" -- 0 means pure pursuit, large means a
    # lead/lag/offset aimpoint is active.
    aim = rel if vp_neu is None else np.asarray(vp_neu, dtype=float)
    aim_n = float(np.linalg.norm(aim))
    if aim_n <= 0:
        aim, aim_n = rel, rel_n
    vp_target_deg = float(np.arccos(_clamp(float(np.dot(aim / aim_n, rel_u)), -1.0, 1.0)) * RADTODEG)
    # GetStick's own LOS is measured to the VP, not the target -- every RollCMD/RudderCMD term
    # below scales off THIS, so the replica has to use it rather than the target-relative los_deg.
    aim_los_deg = float(np.arccos(_clamp(float(np.dot(fwd, aim / aim_n)), -1.0, 1.0)) * RADTODEG)

    # Proj_TV: the aimpoint's offset from the nose ray, in the plane normal to forward.
    fvp = fwd * 1000.0
    proj_v = float(np.dot(aim - fvp, fwd)) * fwd
    proj_tv = (aim - proj_v) - fvp
    ptv_n = float(np.linalg.norm(proj_tv))
    if ptv_n <= 0:
        ptv_n = 1e-4
    ptv_u = proj_tv / ptv_n

    ut = float(np.arccos(_clamp(float(np.dot(up, ptv_u)), -1.0, 1.0)))     # radians, as in C++
    if np.isnan(ut):
        ut = 0.0
    if float(np.dot(right, ptv_u)) < 0:
        ut = -ut
    ut_deg = ut * RADTODEG

    # The term the hypothesis is about. 1.0 = error is in the pitch plane (full pitch
    # authority); 0.0 = error is purely lateral and PitchCMD is multiplied to nothing.
    roll_effect = 1.0 - _clamp(abs(ut_deg) / 90.0, 0.0, 1.0)

    # RollCMD, replicated branch for branch, on the VP-relative LOS the controller uses.
    if abs(ut_deg) > 90:
        rollcmd = np.sin(ut)
        rollcmd = _clamp(rollcmd, -1, 1) if aim_los_deg > 3 else rollcmd * aim_los_deg * (-0.1)
    else:
        rollcmd = _clamp(np.sin(ut), -1, 1)
        rollcmd = rollcmd * abs(rollcmd)
    if rollcmd < 0.1:
        rollcmd = rollcmd * 3
    los_roll_gain = float(_clamp(aim_los_deg, 0, 1))  # collapses linearly once LOS drops below 1
    rollcmd = rollcmd * los_roll_gain

    return {
        "los_deg": los_deg,
        "aim_los_deg": aim_los_deg,
        "vp_target_deg": vp_target_deg,
        # Signed body-frame split of the SAME error: how much is in the pitch plane vs lateral.
        "el_err": float(np.arcsin(_clamp(float(np.dot(up, rel_u)), -1.0, 1.0)) * RADTODEG),
        "az_err": float(np.arcsin(_clamp(float(np.dot(right, rel_u)), -1.0, 1.0)) * RADTODEG),
        "ut_angle_deg": ut_deg,
        "roll_effect": roll_effect,
        "los_roll_gain": los_roll_gain,
        "rollcmd_mirror": float(rollcmd),
    }


def _geom_row(env, step, probe=None):
    b = env.unwrapped
    own, tgt, geo = b._ownship_state, b._target_state, b._geo_info
    own_ata = abs(float(geo._get_antenna_train_angle(own, tgt, False)))   # proj=False == WEZ convention
    tgt_ata = abs(float(geo._get_antenna_train_angle(tgt, own, False)))
    try:
        hca = abs(float(geo._get_heading_cross_angle(own, tgt, False)))
    except Exception:
        hca = float("nan")
    try:
        aspect = abs(float(geo._get_aspect_angle(own, tgt, False)))
    except Exception:
        aspect = float("nan")
    dist = float(geo._get_distance(own, tgt))
    # Controller mirror (2026-08-06): the out-of-plane test for the ~1.038 deg attractor.
    # rollcmd_actual is what the BT really commanded this tick (BTActionProvider writes its
    # clipped action into sim.action); rollcmd_delta against the mirror is the validity gate.
    # Real aimpoint: BTActionProvider writes GetVP()'s output into sim.VP, in the BT's flat-earth
    # frame. Convert ownship into that same frame and difference, so the replica sees the vector
    # the controller actually got instead of assuming the target.
    try:
        vp_abs = np.asarray(b._sim.VP, dtype=float)
        own_cart = _lla_to_bt_cartesian(float(own[StateIndex.LAT]), float(own[StateIndex.LON]),
                                        float(own[StateIndex.ALT]))
        vp_neu = vp_abs - own_cart
        if not np.all(np.isfinite(vp_neu)) or float(np.linalg.norm(vp_neu)) <= 0:
            vp_neu = None
    except Exception:
        vp_neu = None
    mirror = _controller_mirror(own, tgt, vp_neu) or {}
    # Where IS the aimpoint, in plain terms? vp_target_deg says it is ~85 deg off the target;
    # these two say whether it is a plausible point in space or something degenerate (below
    # ground, absurdly far, or pinned at the frame origin).
    if vp_neu is None:
        vp_range_m = vp_alt_m = float("nan")
    else:
        vp_range_m = float(np.linalg.norm(vp_neu))
        vp_alt_m = float(own[StateIndex.ALT]) + float(vp_neu[2])
    try:
        rollcmd_actual = float(b._sim.action[0])
    except Exception:
        rollcmd_actual = float("nan")
    rollcmd_delta = (abs(rollcmd_actual - mirror["rollcmd_mirror"])
                     if mirror and rollcmd_actual == rollcmd_actual else float("nan"))
    return {
        "step": step,
        "own_ata": round(own_ata, 3),
        # Same error, split by plane: |az_err| >> |el_err| at the attractor would confirm the
        # residual is lateral, which is what drives roll_effect (and thus PitchCMD) to ~0.
        "el_err": round(mirror.get("el_err", float("nan")), 3),
        "az_err": round(mirror.get("az_err", float("nan")), 3),
        "ut_angle": round(mirror.get("ut_angle_deg", float("nan")), 2),
        # 0 = the active node is aiming pure-pursuit at the target; large = lead/lag/offset VP.
        "vp_target_deg": round(mirror.get("vp_target_deg", float("nan")), 2),
        "aim_los_deg": round(mirror.get("aim_los_deg", float("nan")), 3),
        "vp_range_m": round(vp_range_m, 1),
        "vp_alt_m": round(vp_alt_m, 1),
        # "" when the provider did not report it (nested/hybrid); 0 means GetVP returned
        # non-finite and sim.VP was REPLACED by SAFE_VP zeros -- the mirror is then reading a
        # substitution, not the aimpoint the DLL steered to.
        "vp_valid": ("" if probe is None or probe.last_vp_valid is None
                     else int(probe.last_vp_valid)),
        "roll_effect": round(mirror.get("roll_effect", float("nan")), 4),
        "los_roll_gain": round(mirror.get("los_roll_gain", float("nan")), 4),
        "rollcmd_mirror": round(mirror.get("rollcmd_mirror", float("nan")), 4),
        "rollcmd_actual": round(rollcmd_actual, 4),
        "rollcmd_delta": round(rollcmd_delta, 4),
        "tgt_ata": round(tgt_ata, 2),
        "hca": round(hca, 2),
        "aspect": round(aspect, 2),
        "dist": round(dist, 1),
        "own_alt": round(float(own[StateIndex.ALT]), 1),
        "tgt_alt": round(float(tgt[StateIndex.ALT]), 1),
        "in_wez": int(bool(getattr(b, "_in_wez", False))),
        "gun_aligned": int(own_ata < 8.0 and 152.4 <= dist <= 914.4),
        "inferred_gate": _infer_gate(own_ata, tgt_ata, hca, dist),
    }


def _dump_trace(rows, path, scenario, backend):
    import csv as _csv, os as _os
    from collections import Counter
    d = _os.path.dirname(path)
    if d:
        _os.makedirs(d, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    n = len(rows)
    pct = lambda c: (100.0 * c / n) if n else 0.0
    min_ata = min(r["own_ata"] for r in rows)
    a8 = sum(1 for r in rows if r["own_ata"] < 8.0)
    a5 = sum(1 for r in rows if r["own_ata"] < 5.0)
    a1 = sum(1 for r in rows if r["own_ata"] <= 1.0)
    rng = sum(1 for r in rows if 152.4 <= r["dist"] <= 914.4)
    wez = sum(1 for r in rows if r["in_wez"])
    shot = [r for r in rows if r["gun_aligned"]]
    gate_shot = Counter(r["inferred_gate"] for r in shot)
    gate_all = Counter(r["inferred_gate"] for r in rows)
    print(f"[trace] {backend} {scenario}: {n} steps -> {path}")
    print(f"[trace] min own_ata={min_ata:.2f} deg | own_ata<8:{pct(a8):.0f}% <5:{pct(a5):.0f}% <=1(WEZ angle):{pct(a1):.0f}%")
    print(f"[trace] in gun range[152-914]:{pct(rng):.0f}% | in_wez(env):{pct(wez):.0f}% ({wez} steps)")
    print(f"[trace] shot available (own_ata<8 AND in range): {len(shot)} steps ({pct(len(shot)):.0f}%)")
    if shot:
        print(f"[trace]   inferred gate WHILE shot available: {dict(gate_shot)}")
        print(f"[trace]   ^ 'Gate1_threat' here = defensive preemption stealing the shot; 'gunhold' = holding it")
    print(f"[trace] inferred gate over ALL steps: {dict(gate_all)}")

    # --- out-of-plane test (2026-08-06) -------------------------------------------------
    # Judged on the rows that matter: close tracking, where the attractor lives. Reported only
    # over rows whose mirror reproduces the BT's actual RollCMD, so a lead/lag node using a
    # different VP cannot contaminate the answer.
    # Two tiers, deliberately separated -- they have different dependencies and only the first
    # is trustworthy today.
    #
    # TIER 1 (target-based, VP-INDEPENDENT): is the residual pointing error in the pitch plane
    # or lateral? Computed from ownship attitude and the direction to the TARGET, so it needs no
    # assumption about the BT's aimpoint. This is also the question the WEZ actually asks, since
    # the cone is measured to the target, not to whatever the tree is aiming at.
    #
    # TIER 2 (controller replica, VP-DEPENDENT): reproducing the tick's real RollCMD. Only valid
    # where the active node aims pure-pursuit; `rollcmd_delta` measures that and is reported as a
    # rate, never silently averaged over.
    import math as _math

    def _num(r, k):
        # int is deliberate: _clamp() returns its integer bound unchanged, so a saturated
        # clamp(LOS,0,1) arrives here as int 1, not 1.0. An isinstance(x, float) guard rejects
        # it, every row reads NaN, and the mean silently prints nan -- which it did.
        v = r.get(k)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else float("nan")
    tracking = [r for r in rows if r["own_ata"] < 5.0
                and not _math.isnan(_num(r, "az_err")) and not _math.isnan(_num(r, "el_err"))]
    def _mean(key, absolute=False):
        """NaN-safe mean over `tracking`. A single NaN row would otherwise poison the whole
        statistic silently -- which is how `clamp(LOS,0,1) roll gain` first printed as nan."""
        vals = [abs(v) if absolute else v
                for v in (_num(r, key) for r in tracking) if not _math.isnan(v)]
        return (sum(vals) / len(vals)) if vals else float("nan")

    if tracking:
        m_el, m_az = _mean("el_err", True), _mean("az_err", True)
        m_re, m_gain = _mean("roll_effect"), _mean("los_roll_gain")
        print(f"[trace] OUT-OF-PLANE TEST over {len(tracking)} close-tracking steps (own_ata<5 deg)")
        # This harness is BIMODAL per episode (Controller_CY.cpp: ATA-min clusters at ~1.04 deg
        # or ~4.40 deg, nothing between, from a ~0.017 deg spawn perturbation inside the
        # protected JSBSimAIPLib.dll). --trace-geometry samples ONE episode, so these means
        # describe whichever mode this episode landed in; run several before concluding.
        print(f"[trace]   NOTE single episode, and outcomes here are bimodal -- this episode's "
              f"min own_ata was {min(r['own_ata'] for r in rows):.2f} deg. Repeat across "
              f"episodes before treating any of the numbers below as the answer.")
        print(f"[trace]   mean |elevation err|={m_el:.3f} deg   mean |azimuth err|={m_az:.3f} deg"
              f"   -> {'LATERAL' if m_az > m_el else 'IN-PITCH-PLANE'}-dominant")
        print(f"[trace]   mean pitch-plane fraction (Roll_Effect form)={m_re:.4f}  -- near 0 means "
              f"the error lies where PitchCMD's Roll_Effect factor multiplies it away, so the "
              f"pitch knobs structurally cannot close it (Controller_CY.cpp's hypothesis).")
        print(f"[trace]   mean clamp(LOS,0,1) roll gain={m_gain:.4f}  -- RollCMD's own scale "
              f"factor; decays linearly below LOS=1 deg, so roll authority fades at the gate.")
    else:
        print("[trace] OUT-OF-PLANE TEST: no close-tracking steps in this episode.")

    # THE DISAMBIGUATION. sim.VP reads (0,0,0) both when the BT genuinely aims at a zero point
    # and when GetVP returned non-finite and BTActionProvider substituted SAFE_VP. Until this
    # line is read, every vp_* / ut_angle / roll_effect number above is uninterpretable.
    reported = [r for r in rows if r.get("vp_valid") not in ("", None)]
    if reported:
        invalid = [r for r in reported if int(r["vp_valid"]) == 0]
        zero_vp = [r for r in rows if abs(_num(r, "vp_alt_m")) < 1e-6]
        print(f"[trace] VP VALIDITY: {len(invalid)}/{len(reported)} steps had vp_valid=0 "
              f"(GetVP non-finite -> sim.VP REPLACED by SAFE_VP zeros); "
              f"{len(zero_vp)}/{n} steps had vp_alt == 0")
        if invalid:
            print(f"[trace]   ^ the zero-VP steps are a SUBSTITUTION, not an aimpoint. The "
                  f"vp_*/ut_angle/roll_effect columns on those rows describe SAFE_VP, not what "
                  f"the DLL steered to. Root cause moves to: why does GetVP return non-finite?")
        else:
            print(f"[trace]   ^ vp_valid=1 on every reported step, so the zero-altitude VP is "
                  f"REAL: the BT genuinely aimed there and the mirror columns stand.")
    else:
        print("[trace] VP VALIDITY: not reported (provider does not expose vp_valid -- nested "
              "under a hybrid?). The vp_* columns cannot be disambiguated from this run.")

    ok = [r for r in rows if not _math.isnan(_num(r, "rollcmd_delta"))
          and _num(r, "rollcmd_delta") < 0.05]
    ok_track = [r for r in tracking if not _math.isnan(_num(r, "rollcmd_delta"))
                and _num(r, "rollcmd_delta") < 0.05]
    print(f"[trace]   controller-replica agreement: {len(ok)}/{n} steps overall, "
          f"{len(ok_track)}/{len(tracking)} of the close-tracking ones "
          f"(|rollcmd_mirror - rollcmd_actual| < 0.05)")
    if tracking:
        m_vp = _mean("vp_target_deg", True)
        print(f"[trace]   mean VP-vs-target angle={m_vp:.2f} deg over close tracking "
              f"-- 0 means the active node aims pure-pursuit at the target (Task_GunTrack / "
              f"Task_pure); large means a lead/lag/offset aimpoint is flying those ticks.")
    if tracking and len(ok_track) < 0.5 * len(tracking):
        print(f"[trace]   ^ replica agreement is LOW even with the real VP. That points at a "
              f"remaining mismatch in the replica itself (or at sim.VP being stale relative to "
              f"the tick that flew), NOT at the aimpoint assumption. The Tier-1 numbers above "
              f"are unaffected -- they never use the aimpoint.")


class PhasedScore:
    """Per-episode accumulator for the real competition's phase-widening WEZ.

    One instance per episode. `observe()` is called once per env step with the post-step
    geometry -- the same state and the same ATA convention (proj=False) that
    update_damage() uses, so the flat and phased numbers are computed from identical
    inputs and any difference between them is the RULE, not the measurement.

    `substep_s` is the wall-time one env step covers (delta_t * step_ratio). At the
    harness default (step_ratio=1) that is exactly delta_t and the integration matches
    update_damage() tick for tick; see the module docstring for the step_ratio > 1 caveat.
    """

    def __init__(self, substep_s: float):
        self._substep_s = substep_s
        self.wez_steps = 0
        self.phase_steps = [0] * len(WEZ_PHASES)
        self.damage_dealt = 0.0
        self.damage_taken = 0.0
        self.match_time_s = 0.0
        self.errors = 0

    def observe(self, dist_m: float, own_ata_deg: float, tgt_ata_deg: float, sim_time_s: float) -> None:
        self.match_time_s = sim_time_s
        phase = match_wez_phase(WEZ_PHASES, dist_m, own_ata_deg, sim_time_s)
        if phase is not None:
            self.wez_steps += 1
            self.phase_steps[WEZ_PHASES.index(phase)] += 1
        # Both directions: the competition decides on damage DEALT vs TAKEN, so a harness
        # that scores only our own cone cannot tell a win from a mutual-tracking draw.
        self.damage_dealt += wez_damage_estimate(
            WEZ_PHASES, dist_m, own_ata_deg, sim_time_s, self._substep_s)
        self.damage_taken += wez_damage_estimate(
            WEZ_PHASES, dist_m, tgt_ata_deg, sim_time_s, self._substep_s)

    # Episode endings where nobody crashed and no health ran out -- the match reached the clock,
    # so the winner is whoever dealt more damage (COMPETITION_RULES.md Sec5).
    CLOCK_END_CONDITIONS = frozenset({"max time out", "episode step limit"})

    def outcome(self, platform_outcome: str, end_condition: str) -> str:
        """Advisory win/loss/draw under the phased cone. NEVER affects how the episode ran.

        Deliberately narrow: this re-adjudicates ONLY the thing the phased model actually
        changes -- who out-damaged whom through a widening cone -- and only for matches that
        ran to the clock. Every other ending (crash, destroyed, FDM failure, guard fail) is
        passed through from the platform untouched.

        The alternative, re-deciding crashes here too, was tried and removed: with a `fixed`
        target that flies itself into the ground at ~42 s it reported a 100% phased win rate,
        which is a statement about a degenerate opponent rather than about the cone. Keeping
        the override surface minimal is what makes a flat-vs-phased disagreement interpretable.
        """
        if end_condition not in self.CLOCK_END_CONDITIONS:
            return platform_outcome
        if self.damage_dealt > self.damage_taken:
            return "win"
        if self.damage_taken > self.damage_dealt:
            return "loss"
        return "draw"


# Target backends that are flown by the ENV (no ActionProvider) -- run_local_dogfight's
# build_provider() only knows "fixed" and raises on the rest, so they are intercepted here.
# Added 2026-08-06 because "fixed" descends: step_fix() holds controls, not altitude, so the
# target sinks into the 300 m floor and ends the episode at ~42 s on "target altitude below min".
# That truncation put Phase 2/3 of the widened WEZ permanently out of reach in exactly the
# geometry where tracking is best. "autopilot" holds heading/altitude/speed for the full match.
ENV_FLOWN_TARGETS = {"fixed": "fixed", "autopilot": "autopilot", "loiter": "loiter"}


def build_provider_or_none(backend: str, **kwargs):
    return None if backend in ENV_FLOWN_TARGETS else build_provider(backend=backend, **kwargs)


def target_env_mode(backend: str) -> str:
    return ENV_FLOWN_TARGETS.get(backend, backend_to_env_mode(backend))


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ownship-backend", choices=["rl", "bt", "vptrack", "hybrid", "hybrid_vptrack", "hybrid_gated", "fixed"], required=True)
    p.add_argument("--target-backend",
                   choices=["rl", "bt", "vptrack", "hybrid", "hybrid_vptrack", "hybrid_gated",
                            "fixed", "autopilot", "loiter"], required=True,
                   help="'vptrack' is the strongest opponent we have and the ONLY one that can "
                        "actually point -- use it for self-play, the closest available proxy for "
                        "the organizers' cutoff model. Every result against 'bt' is against an "
                        "opponent that never shoots (0.00 damage taken across 60+ episodes), so "
                        "it says nothing about robustness. "
                        "'autopilot' holds heading/altitude/speed for the full 200 s -- prefer it "
                        "over 'fixed', which sinks into the altitude floor at ~42 s and truncates "
                        "the match before the WEZ cone widens.")
    p.add_argument("--target-autopilot", nargs=3, type=float,
                   metavar=("HEADING_DEG", "ALTITUDE_M_AMSL", "SPEED_MPS"),
                   default=[180.0, 7000.0, 250.0],
                   help="Setpoint for --target-backend autopilot. ALTITUDE IS METRES ABOVE SEA "
                        "LEVEL (positive up) and is negated internally into the NED-down "
                        "convention step_autopilot() actually wants -- see SIGN TRAP below.")
    p.add_argument("--ownship-bundle-dir")
    p.add_argument("--target-bundle-dir")
    p.add_argument("--ownship-bt-dll", default="AIP_BASE.dll")
    p.add_argument("--target-bt-dll", default="AIP_BASE_target.dll")
    p.add_argument("--bt-rule-xml")
    p.add_argument("--ownship-policy-id", default="default_policy")
    p.add_argument("--target-policy-id", default="default_policy")
    p.add_argument("--observation-mode", default="tactical16",
                   choices=["classic12", "relative14", "tactical16", "custom"])
    p.add_argument("--observation-module", default="")
    p.add_argument("--hybrid-mode", choices=["residual", "blend", "switch"], default="residual")
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--residual-scale", type=float, default=0.35)
    p.add_argument("--episodes", type=int, default=30)
    # 2026-08-06: 300.0/18000 -> the real 200 s match (see MATCH_DURATION_S). The old defaults
    # ran 1.5x long, which inflates the Phase-3 share of any phased score.
    p.add_argument("--max-engage-time", type=float, default=MATCH_DURATION_S)
    p.add_argument("--episode-step-limit", type=int, default=MATCH_STEP_LIMIT)
    p.add_argument("--min-altitude", type=float, default=300.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--scenario-mode",
                   choices=["two_circle_headon", "obfm_offensive", "obfm_defensive",
                            "match_base", "match_tiebreak"],
                   default="two_circle_headon",
                   help="Initial geometry. two_circle_headon varies over the alpha schedule; "
                        "obfm_* uses the fixed ~556 m six-o'clock advantage geometry "
                        "(via ObfmScenarioWrapper; heading randomized per episode). "
                        "match_base is THE COMPETITION SCENARIO (prelim + finals rounds "
                        "1-3): antiparallel BEAM merge, LOS ~90 deg both sides, at "
                        "2000-3000 ft. match_tiebreak is the round-4 head-on at 10000ft+. "
                        "Prefer these over the other three for any result meant to predict "
                        "match performance -- obfm_* stages a six-o'clock advantage the "
                        "rules never grant.")
    # Per-side controller overrides (2026-08-06). The Rule XML is global to both DLLs, so BT
    # changes cannot be given to one side only: self-play cancels them exactly and the vs-BT
    # benchmark is saturated. Varying the CONTROLLER per side is the only asymmetry available
    # without touching the DLL, and it is what makes "tuned vs untuned" measurable at all.
    for _side in ("ownship", "target"):
        p.add_argument(f"--{_side}-vptrack-range-m", type=float, default=None,
                       help=f"{_side} vptrack engagement range (default {2500.0:.0f} m).")
        p.add_argument(f"--{_side}-vptrack-los-deg", type=float, default=None,
                       help=f"{_side} vptrack engagement LOS half-angle (default 45 deg).")
        p.add_argument(f"--{_side}-vptrack-throttle", type=int, choices=[0, 1], default=None,
                       help=f"{_side} vptrack range/throttle control (default off; measured null).")
        p.add_argument(f"--{_side}-vptrack-defensive", type=int, choices=[0, 1], default=None,
                       help=f"{_side} defensive break when losing the gun duel (default off).")
        p.add_argument(f"--{_side}-vptrack-corner", type=int, choices=[0, 1], default=None,
                       help=f"{_side} hold corner speed (~440 KTAS) for peak turn rate (default off).")
        p.add_argument(f"--{_side}-vptrack-roll-taper", type=float, default=None,
                       help=f"{_side}: taper the ROLL command by pointing-error magnitude "
                            f"below this many degrees (0 = off, the shipped default). See "
                            f"ROLL_TAPER_DEG in student/controller_providers.py for the "
                            f"measured authority inversion this addresses.")
    p.add_argument("--match-los-deg", type=float, default=None,
                   help="Override each aircraft's LOS-off-nose for match_* modes. The "
                        "rounds-1-3 slide art supports two readings: 90 (antiparallel and "
                        "abeam -- a beam merge, the default) or 180 (antiparallel and "
                        "nose-away, tail-to-tail). Measure both rather than assuming.")
    p.add_argument("--out-csv", default="artifacts/eval/matchup.csv")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--trace-geometry", action="store_true",
                   help="Log per-step ATA/HCA/range/altitude + env in_wez + inferred BT gate for "
                        "one episode (rebuild-free instrumentation for the gun-solution root cause).")
    p.add_argument("--trace-episode", type=int, default=0, help="Which episode index to trace.")
    p.add_argument("--trace-out", default="artifacts/eval/geom_trace.csv",
                   help="Per-step geometry trace CSV output path.")
    return p.parse_args()


def main():
    args = parse_args()

    out_csv = Path(args.out_csv)
    alpha_plan = [ALPHA_SCHEDULE_DEG[i % len(ALPHA_SCHEDULE_DEG)] for i in range(args.episodes)]

    observation_hook = load_observation_hook(args.observation_module) if args.observation_module else None
    effective_observation_mode = observation_hook["mode"] if observation_hook else args.observation_mode

    print(f"[eval] {args.ownship_backend} (ownship) vs {args.target_backend} (target)")
    print(f"[eval] episodes={args.episodes}  obs_mode={effective_observation_mode}  obs_module={args.observation_module or '(builtin)'}")
    print(f"[eval] scenario={args.scenario_mode}")
    print(f"[eval] ownship bundle: {args.ownship_bundle_dir}")
    # Log the composition parameters (2026-08-22). They were previously invisible in the
    # artifact, and two of them silently defaulted in ways that changed what was measured:
    # `--residual-scale` defaults to 0.35 while the v10 bundle was TRAINED at 0.10, and the
    # `hybrid_vptrack` / `hybrid_gated` backends build their vptrack floor from the class
    # defaults (2500 m / 45 deg / throttle off -- the pre-F29/F39 config, 13.3% vs the cutoff)
    # unless the --{side}-vptrack-* flags are passed. Same failure shape as F44, one layer down:
    # a run named after a mode, flying a different aircraft than the reader assumes.
    for _s in ("ownship", "target"):
        _b = getattr(args, f"{_s}_backend")
        if _b in ("vptrack", "hybrid_vptrack", "hybrid_gated"):
            # Resolved through the SAME helper build_provider uses, so the banner cannot
            # disagree with the aircraft that is actually constructed (F48).
            _r, _l, _t = resolve_vptrack_floor(
                _b,
                getattr(args, f"{_s}_vptrack_range_m"),
                getattr(args, f"{_s}_vptrack_los_deg"),
                getattr(args, f"{_s}_vptrack_throttle"),
            )
            _explicit = getattr(args, f"{_s}_vptrack_range_m") is not None
            _rt = getattr(args, f"{_s}_vptrack_roll_taper")
            _src = "explicit" if _explicit else (
                "shipped default" if _b in ("hybrid_vptrack", "hybrid_gated") else "class default")
            print(f"[eval] {_s} vptrack floor: "
                  f"range={_r if _r is not None else VPT_RANGE_DEFAULT} "
                  f"los={_l if _l is not None else VPT_LOS_DEFAULT} "
                  f"throttle={int(_t) if _t is not None else int(VPT_THROTTLE_DEFAULT)} "
                  f"roll_taper={_rt if _rt is not None else 0.0} ({_src})")
        if _b in ("hybrid", "hybrid_vptrack", "hybrid_gated"):
            print(f"[eval] {_s} hybrid composition: mode={args.hybrid_mode} "
                  f"residual_scale={args.residual_scale} alpha={args.alpha}")
    print(f"[eval] alpha schedule (deg): {alpha_plan}")
    print(f"[eval] out-csv: {out_csv}")
    if args.dry_run:
        print("[dry-run] no env constructed, no episodes run.")
        return

    if args.ownship_backend in ("rl", "hybrid") and args.ownship_bundle_dir:
        require_healthy_bundle(args.ownship_bundle_dir, strict=True)

    ownship_provider = build_provider(
        side="ownship", backend=args.ownship_backend, bundle_dir=args.ownship_bundle_dir,
        bt_dll=args.ownship_bt_dll, policy_id=args.ownship_policy_id,
        hybrid_mode=args.hybrid_mode, alpha=args.alpha, residual_scale=args.residual_scale,
        observation_mode=effective_observation_mode, observation_module=args.observation_module,
        vptrack_range_m=args.ownship_vptrack_range_m,
        vptrack_los_deg=args.ownship_vptrack_los_deg,
        vptrack_throttle=(None if args.ownship_vptrack_throttle is None
                          else bool(args.ownship_vptrack_throttle)),
        vptrack_defensive=(None if args.ownship_vptrack_defensive is None
                           else bool(args.ownship_vptrack_defensive)),
        vptrack_corner=(None if args.ownship_vptrack_corner is None
                        else bool(args.ownship_vptrack_corner)),
        vptrack_roll_taper=args.ownship_vptrack_roll_taper,
    )
    # Capture vp_valid so a SAFE_VP zero substitution is distinguishable from a genuine zero
    # aimpoint. Wrapping is transparent; see VPProbe.
    vp_probe = VPProbe(ownship_provider) if ownship_provider is not None else None
    if vp_probe is not None:
        ownship_provider = vp_probe
    target_provider = build_provider_or_none(
        side="target", backend=args.target_backend, bundle_dir=args.target_bundle_dir,
        bt_dll=args.target_bt_dll, policy_id=args.target_policy_id,
        hybrid_mode=args.hybrid_mode, alpha=args.alpha, residual_scale=args.residual_scale,
        observation_mode=effective_observation_mode, observation_module=args.observation_module,
        vptrack_range_m=args.target_vptrack_range_m,
        vptrack_los_deg=args.target_vptrack_los_deg,
        vptrack_throttle=(None if args.target_vptrack_throttle is None
                          else bool(args.target_vptrack_throttle)),
        vptrack_defensive=(None if args.target_vptrack_defensive is None
                           else bool(args.target_vptrack_defensive)),
        vptrack_corner=(None if args.target_vptrack_corner is None
                        else bool(args.target_vptrack_corner)),
        vptrack_roll_taper=args.target_vptrack_roll_taper,
    )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    outcomes: Counter[str] = Counter()
    wez_contact_episodes = 0
    # Phase-aware (real competition) totals, reported alongside the flat platform ones.
    phased_outcomes: Counter[str] = Counter()
    phased_contact_episodes = 0
    phase_step_totals = [0] * len(WEZ_PHASES)
    total_damage_dealt = 0.0
    total_damage_taken = 0.0
    truncated_before_p2 = 0
    geometry_errors = 0
    zero_action = np.zeros(4, dtype=np.float32)

    with activate_rule_xml(args.bt_rule_xml, ROOT), open(out_csv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()

        env = DogFightWrapper(
            env_config={
                "observation_mode": effective_observation_mode,
                "observation_module": args.observation_module,
                "ownship_control_mode": backend_to_env_mode(args.ownship_backend),
                "target_mode": target_env_mode(args.target_backend),
                # SIGN TRAP (2026-08-06). FighterSim.step_autopilot()'s altitude_cmd is documented
                # "meter (NED, Down direction +)" and it computes `-altitude_cmd * METER_TO_FEET`,
                # so commanding 7000 m of ALTITUDE requires passing -7000. The platform default in
                # src/dogfight/config.py is +7000.0, which resolves to -22966 ft -- an order to fly
                # far below sea level. That is why an "altitude-hold" target still ended episodes on
                # "target altitude below min" (at 24 s, even sooner than the fixed target's 42 s).
                # The CLI takes metres AMSL and the negation happens here, once, so the intuitive
                # value is the correct one. NOTE: the same +7000.0 default feeds the curriculum's
                # autopilot stages -- worth checking there separately.
                "target_autopilot": {
                    "heading_cmd": args.target_autopilot[0],
                    "altitude_cmd": -args.target_autopilot[1],
                    "speed_cmd": args.target_autopilot[2],
                },
                "max_engage_time": args.max_engage_time,
                "episode_step_limit": args.episode_step_limit,
                "min_altitude": args.min_altitude,
            },
            observation_fn=observation_hook["build_observation"] if observation_hook else None,
            observation_size=observation_hook["size"] if observation_hook else None,
            observation_low=observation_hook["low"] if observation_hook else None,
            observation_high=observation_hook["high"] if observation_hook else None,
            ownship_action_provider=ownship_provider,
            target_action_provider=target_provider,
        )
        # OBFM geometry ("obfm" scenario mode) is not native to single_agent_env.py;
        # it is staged by ObfmScenarioWrapper.reset() via change_init_position(),
        # exactly as train_curriculum.py wraps the env for the obfm_* stages. No-op
        # for two_circle_headon, so only wrap when actually needed.
        if args.scenario_mode.startswith("obfm"):
            env = ObfmScenarioWrapper(env)
        # Same reason as the OBFM wrapper above: "headon_short" is not native to
        # single_agent_env.py, it is staged via change_init_position() at reset.
        if args.scenario_mode.startswith("match_"):
            env = MatchScenarioWrapper(env)

        # Wall-time covered by one env step, for the phased damage integration. Read off the
        # env rather than assumed: step_ratio is resolved from config (explicit, or legacy
        # delta/time_step, else 1.0) and silently getting this wrong scales every damage number.
        _base = env.unwrapped
        step_ratio = int(_base._step_ratio)
        substep_s = float(_base._delta_t) * step_ratio
        print(f"[phased] sim_hz={_base._sim_hz} step_ratio={step_ratio} "
              f"-> {substep_s:.5f} s per env step; match={args.max_engage_time:.0f} s "
              f"/ {args.episode_step_limit} steps")
        if step_ratio > 1:
            print(f"[phased] WARNING: step_ratio={step_ratio} > 1 -- geometry is sampled once per "
                  f"env step but update_damage() runs {step_ratio}x per step on substep geometry "
                  f"this harness cannot see. Phased damage is an approximation here, not a "
                  f"tick-exact mirror.")

        def _recycle_native_bts() -> int:
            """Force a fresh native BT (blackboard + StickController) for the next episode.

            SAMPLE INDEPENDENCE, added 2026-08-05. BtActionProvider.reset() is a deliberate no-op
            ("Keep native BT alive across episode resets for multienv") and _ensure_behavior_tree()
            creates the BT once and reuses it until provider close(), so ONE UCPPBehaviorTree --
            with its CPPBlackBoard AND its StickController -- serves every episode of a run. That
            carries across episode boundaries:
              * BB->RunningTime, which is NEVER reset (only the CPPBlackBoard ctor zeroes it).
                Task_EnergyTactics reads `lateMatch = RunningTime > 180`, so from episode 2 onward
                EVERY episode is permanently "late match" from tick 1. Task_JinkingTurn likewise
                phases its sine off RunningTime, so each episode starts mid-oscillation.
              * PreviousAltitudeForRate -> first tick of episode N+1 computes AltSpeed from the
                altitude discontinuity between episodes; at dt=1/60 s even 100 m is ~6000 m/s,
                which feeds Task_ClimbToSafeAltitude's runaway-descent trigger (Gate 0, top
                priority), so episodes can open with a spurious climb.
              * StickController's SumCount / ErrorSum[60] / MF[20] / FilterIndex -- the integral
                starts each episode loaded with the previous episode's error history.
              * ActiveManeuverID / NeutralEngagementStartTime / ManeuverCooldownUntil[].

            This does NOT make the harness deterministic -- that source is inside JSBSimAIPLib.dll
            (a protected binary), and a single fresh episode is already bimodal. It makes episodes
            INDEPENDENT, which is what lets N-episode success-rate be a valid statistic.

            src/dogfight/** is a hard no-edit boundary, so this is done from the (editable) eval
            script. Both the native BT and the provider's own registry must be cleared: RemoveBT
            alone leaves the id in _registered_fighter_ids, so _ensure_behavior_tree() early-returns
            and never re-creates, and Step() then logs "No BT found for MyID".

            MUST RECURSE (fixed 2026-08-05, same session): the first version of this looked for
            ai_pilot/_registered_fighter_ids DIRECTLY on the provider. StudentHybridProvider has
            NEITHER -- its *secondary_provider* is the BTActionProvider -- so every
            `--*-backend hybrid` run was silently skipped, keeping the exact cross-episode leak
            this function exists to remove, with no output to say so. Caught while wiring-checking
            the hybrid path before using it. The skip is now reported, because a recycler whose
            failure mode is invisible is worse than none: results still look plausible.
            """
            recycled = 0
            for prov in (ownship_provider, target_provider):
                for bt_prov in _iter_bt_providers(prov):
                    reg = bt_prov._registered_fighter_ids
                    pilot = bt_prov.ai_pilot
                    for fid in list(reg):
                        try:
                            pilot.RemoveBT(fid)
                        except Exception as e:
                            print(f"[recycle] RemoveBT({fid}) failed: {e}")
                            continue
                        reg.pop(fid, None)
                        recycled += 1
            return recycled

        # Make a no-op recycler VISIBLE. If a BT-bearing backend is configured but no BT provider
        # is reachable, every episode after the first silently inherits the previous one's
        # blackboard + StickController and the numbers still look plausible -- exactly the failure
        # the hybrid-nesting bug produced. Report the topology once, up front.
        _bt_backends = [s for s, b in (("ownship", args.ownship_backend),
                                       ("target", args.target_backend)) if b in ("bt", "hybrid")]
        _found = sum(1 for p in (ownship_provider, target_provider) for _ in _iter_bt_providers(p))
        if _bt_backends and _found == 0:
            print(f"[recycle] WARNING: backends {_bt_backends} should own a native BT but none was "
                  f"reachable — episodes will NOT be independent (cross-episode state will leak).")
        else:
            print(f"[recycle] {_found} native BT provider(s) will be recycled between episodes.")

        try:
            for episode, alpha_deg in enumerate(alpha_plan):
                if episode > 0:
                    _recycle_native_bts()
                if args.scenario_mode == "two_circle_headon":
                    scen = {"mode": "two_circle_headon", "alpha_deg": float(alpha_deg)}
                elif args.scenario_mode.startswith("match_"):
                    # alpha_deg from the schedule is NOT a geometry knob here (LOS is fixed
                    # by the mode); it is reused as a deterministic sweep across the
                    # 2000-3000 ft band so the N episodes cover the published range evenly
                    # instead of clustering wherever the RNG happens to land.
                    _frac = (float(alpha_deg) % 180.0) / 180.0
                    scen = {"mode": args.scenario_mode,
                            "altitude_m": MATCH_ALTITUDE_M,
                            "speed_mps": MATCH_SPEED_MPS}
                    if args.scenario_mode == "match_base":
                        scen["separation_m"] = (
                            MATCH_SEPARATION_MIN_M
                            + _frac * (MATCH_SEPARATION_MAX_M - MATCH_SEPARATION_MIN_M)
                        )
                    if args.match_los_deg is not None:
                        scen["los_deg"] = float(args.match_los_deg)
                else:
                    role = "offensive" if args.scenario_mode == "obfm_offensive" else "defensive"
                    scen = {"mode": "obfm", "role": role,
                            "altitude_m": OBFM_ALTITUDE_M, "speed_mps": OBFM_SPEED_MPS}
                # Capture reset()'s info (2026-08-06). The env sets the initial-geometry keys
                # (initial_distance_m / initial_ata_deg / initial_aa_deg) ONLY at reset --
                # single_agent_env.py's step() never re-emits them. Discarding this return meant
                # the row below read them off the FINAL step's info and fell through to the 0.0
                # default: every episode in artifacts/eval/v6_rl_vs_bt.csv logged
                # initial_distance_m = 0.0, so the newest eval could not report its own spawn
                # geometry (v5_vs_bt.csv, written before the phased-scoring rewrite, has real
                # values). Spawn geometry is load-bearing here -- E1 traced the bimodality to a
                # 0.017 deg spawn perturbation, which is unreadable without it.
                _, reset_info = env.reset(
                    seed=args.seed + episode, options={"initial_scenario": scen}
                )
                reset_info = reset_info or {}
                # Fallback for scenario modes single_agent_env.py does not know about
                # (obfm/habfm/match_*, all staged by student-space wrappers via
                # change_init_position). Its _update_initial_geometry_metrics() only fills
                # initial_* for its own native modes, so those runs logged
                # initial_distance_m = 0.0 -- and for match_* the separation is the SWEPT
                # variable, so losing it makes the sweep unreadable. Measured here from the
                # post-reset state instead, using the same geo helper the step loop uses.
                if not reset_info.get("initial_distance_m"):
                    try:
                        _b0 = env.unwrapped
                        reset_info["initial_distance_m"] = float(
                            _b0._geo_info._get_distance(_b0._ownship_state, _b0._target_state)
                        )
                    except Exception:
                        pass
                terminated = truncated = False
                total_reward = 0.0
                info: dict = {}
                trace_on = args.trace_geometry and episode == args.trace_episode
                trace_rows = []
                # Per-episode terminal-tracking metrics, added 2026-08-05. The eval previously
                # recorded only FINAL ata/aa, which says nothing about the best solution reached.
                # Needed because BT outcomes here are BIMODAL (bisect 2026-08-05: ATA-min clusters
                # at ~1.037 deg or ~4.40 deg, nothing between) driven by a ~0.017 deg spawn
                # perturbation from JSBSimAIPLib.dll. Single-episode point values are therefore
                # meaningless; the valid statistic is the RATE at which episodes land in the
                # converging mode, which needs a per-episode min to classify. Tracked every step
                # regardless of --trace-geometry, which only samples one episode.
                ep_min_ata = float("inf")
                ep_steps_le2 = 0
                ep_steps_le1 = 0
                last_ata_3d = float("nan")   # cone-convention counterpart of info's 2D final_ata
                phased = PhasedScore(substep_s)
                while not (terminated or truncated):
                    _obs, reward, terminated, truncated, info = env.step(zero_action)
                    total_reward += reward
                    try:
                        _b = env.unwrapped
                        _own, _tgt, _geo = _b._ownship_state, _b._target_state, _b._geo_info
                        # proj=False throughout: the WEZ convention update_damage() uses.
                        _ata = abs(float(_geo._get_antenna_train_angle(_own, _tgt, False)))
                        _tgt_ata = abs(float(_geo._get_antenna_train_angle(_tgt, _own, False)))
                        _dist = float(_geo._get_distance(_own, _tgt))
                        # SIM_TIME, not step*delta_t: it is the same clock evaluate_termination()
                        # compares against max_engage_time, so phase boundaries land exactly where
                        # the match clock says they do regardless of step_ratio.
                        _t = float(_own[StateIndex.SIM_TIME])
                        last_ata_3d = _ata
                        if _ata < ep_min_ata:
                            ep_min_ata = _ata
                        if _ata <= 2.0:
                            ep_steps_le2 += 1
                        if _ata <= 1.0:
                            ep_steps_le1 += 1
                        phased.observe(_dist, _ata, _tgt_ata, _t)
                    except Exception:
                        # Was a bare pass. A silently-swallowed geometry failure here would
                        # zero the phased columns while the run still printed plausible
                        # numbers -- the same invisible-failure mode the recycler note warns
                        # about. Counted per episode and reported in the summary.
                        phased.errors += 1
                    if trace_on:
                        try:
                            trace_rows.append(_geom_row(env, len(trace_rows), vp_probe))
                        except Exception as _e:
                            trace_on = False
                            print(f"[trace] disabled mid-episode (geometry access failed: {_e})")
                if trace_rows:
                    _dump_trace(trace_rows, args.trace_out, args.scenario_mode, args.ownship_backend)

                outcome = info.get("outcome", "unknown")
                outcomes[outcome] += 1
                if float(info.get("ep_wez_steps", 0)) > 0:
                    wez_contact_episodes += 1

                phased_outcome = phased.outcome(outcome, info.get("end_condition", ""))
                phased_outcomes[phased_outcome] += 1
                if phased.wez_steps > 0:
                    phased_contact_episodes += 1
                total_damage_dealt += phased.damage_dealt
                total_damage_taken += phased.damage_taken
                for _i, _c in enumerate(phased.phase_steps):
                    phase_step_totals[_i] += _c
                if phased.match_time_s < WEZ_PHASES[1]["min_time_s"]:
                    truncated_before_p2 += 1
                geometry_errors += phased.errors

                writer.writerow({
                    "episode": episode,
                    "alpha_deg": alpha_deg,
                    "outcome": outcome,
                    "end_condition": info.get("end_condition", ""),
                    "ownship_health": info.get("ownship_health", ""),
                    "target_health": info.get("target_health", ""),
                    "total_reward": round(total_reward, 4),
                    "steps": info.get("ep_step_count", ""),
                    "ep_wez_steps": info.get("ep_wez_steps", ""),
                    "ep_min_distance": round(float(info.get("ep_min_distance", 0.0)), 1),
                    # From reset_info, not info: step() never re-emits the initial geometry.
                    "initial_distance_m": round(
                        float(reset_info.get("initial_distance_m",
                                             info.get("initial_distance_m", 0.0))), 1),
                    # proj=True (2D azimuth) -- straight from the platform info dict.
                    "final_ata_deg_2d": round(float(info.get("final_ata_deg", 0.0)), 1),
                    "final_aa_deg_2d": round(float(info.get("final_aa_deg", 0.0)), 1),
                    # proj=False (3D cone) -- the convention the damage gate actually tests.
                    "ep_min_ata_deg_3d": (round(ep_min_ata, 4) if ep_min_ata != float("inf") else ""),
                    "ep_steps_le2_deg_3d": ep_steps_le2,
                    "ep_steps_le1_deg_3d": ep_steps_le1,
                    "final_ata_deg_3d": ("" if last_ata_3d != last_ata_3d else round(last_ata_3d, 4)),
                    "match_time_s": round(phased.match_time_s, 1),
                    "ep_wez_steps_phased": phased.wez_steps,
                    "ep_wez_steps_p1": phased.phase_steps[0],
                    "ep_wez_steps_p2": phased.phase_steps[1],
                    "ep_wez_steps_p3": phased.phase_steps[2],
                    "ep_damage_dealt": round(phased.damage_dealt, 5),
                    "ep_damage_taken": round(phased.damage_taken, 5),
                    "phased_outcome": phased_outcome,
                })
                fh.flush()
                print(f"[ep {episode:>3}/{args.episodes}] alpha={alpha_deg:>3} -> {outcome:<8} "
                      f"({info.get('end_condition', '')})  own_hp={info.get('ownship_health','?')} "
                      f"tgt_hp={info.get('target_health','?')} wez={info.get('ep_wez_steps','?')} "
                      f"steps={info.get('ep_step_count','?')}")
                print(f"          phased[{phased.match_time_s:>5.1f}s] -> {phased_outcome:<5} "
                      f"wez={phased.wez_steps} (p1={phased.phase_steps[0]} "
                      f"p2={phased.phase_steps[1]} p3={phased.phase_steps[2]})  "
                      f"dmg {phased.damage_dealt:.4f} vs {phased.damage_taken:.4f}")
        finally:
            env.close()

    n = max(args.episodes, 1)
    print("\n[eval] summary -- FLAT platform model (update_damage(): |ATA|<=1.0 deg, 500-3000 ft)")
    print(f"  episodes: {args.episodes}")
    for name in ("win", "loss", "draw", "timeout"):
        c = outcomes.get(name, 0)
        print(f"  {name:<8}: {c:>3}  ({c / n:.1%})")
    other = {k: v for k, v in outcomes.items() if k not in ("win", "loss", "draw", "timeout")}
    if other:
        print(f"  other   : {dict(other)}")
    print(f"  wez-contact episodes: {wez_contact_episodes} ({wez_contact_episodes / n:.1%})")

    print("\n[eval] summary -- PHASED competition model (1/2/3 deg widening at 100 s/150 s)")
    print("  (only clock-ending matches are re-adjudicated on damage; all other endings "
          "pass through from the flat model above)")
    for name in ("win", "loss", "draw", "timeout"):
        c = phased_outcomes.get(name, 0)
        print(f"  {name:<8}: {c:>3}  ({c / n:.1%})")
    phased_other = {k: v for k, v in phased_outcomes.items()
                    if k not in ("win", "loss", "draw", "timeout")}
    if phased_other:
        print(f"  other   : {dict(phased_other)}")
    print(f"  wez-contact episodes: {phased_contact_episodes} ({phased_contact_episodes / n:.1%})")
    print(f"  wez steps by phase  : p1={phase_step_totals[0]} "
          f"p2={phase_step_totals[1]} p3={phase_step_totals[2]}")
    print(f"  damage dealt/taken  : {total_damage_dealt:.4f} / {total_damage_taken:.4f} "
          f"(mean per episode {total_damage_dealt / n:.4f} / {total_damage_taken / n:.4f})")

    # The headline of this harness change: when these two disagree, the flat number is the
    # local artifact and the phased one is the estimate of what the live server would score.
    if wez_contact_episodes == 0 and phased_contact_episodes > 0:
        print(f"  ^^ FLAT reads 0 WEZ contact but PHASED reads {phased_contact_episodes}/{n} "
              f"episodes with contact. The tracking is landing INSIDE the widened late-match "
              f"cone and outside the flat 1.0 deg gate -- i.e. scoreless locally, scoring live.")

    if truncated_before_p2:
        print(f"  !! {truncated_before_p2}/{n} episodes ended before t="
              f"{WEZ_PHASES[1]['min_time_s']:.0f} s, so Phase 2/3 were never reachable. Their "
              f"phased score is NOT representative of a 200 s match -- fix the scenario "
              f"(check end_condition; a target that flies itself into the ground ends the "
              f"episode early) before drawing conclusions from the phased columns.")
    if geometry_errors:
        print(f"  !! {geometry_errors} per-step geometry read(s) failed and were skipped; "
              f"phased columns undercount by that many steps.")
    print(f"\n  csv: {out_csv}")


if __name__ == "__main__":
    main()
