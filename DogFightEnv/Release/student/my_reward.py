# -*- coding: utf-8 -*-
"""real_eagle reward — ported from src/dogfight/envs/reward.py's reference anatomy.

RECOVERED 2026-07-15: the 2026-07-15 accidental full-tree revert (see
memory/project_bulk_revert_regression_2026_07_15.md) overwrote this file back to
the bare starter template. This version is reconstructed from a stale
__pycache__/my_reward.cpython-313.pyc (compiled 2026-07-12 03:36 by a different
interpreter than the active `aip` env, so it survived the revert) via bytecode
disassembly -- the component structure, MY_REWARD_CONFIG keys/values, and
compute_reward() logic below are a byte-exact recovery, not a guess.

That recovered snapshot still had the pre-audit bug: a ground-impact crash
(end_condition == "ownship altitude below min") isn't distinguished from a
genuine stalemate, so it fell through to draw_reward -- positive on the OBFM
defensive stage (surviving to a timeout is a real defensive win there), which
is exactly how v1/v3 learned a 100% suicide rate on that stage (see
real_eagle_v4.yaml's fix #1 and COMPETITION_PLAN.md). The
_OWNSHIP_CRASH_CONDITIONS / _TARGET_CRASH_CONDITIONS routing below is that fix,
applied fresh here since the original fix lived only in the wiped file.

wez_pursuit_multipliers() used to come from `dogfight.config` (also wiped, see
student/reward_lib.py's WEZ_PHASES for the byte-exact recovery of that data);
importing it from reward_lib instead keeps this file working without touching
the now-hard-boundary src/dogfight/**.

DAMAGE TERM IS NOW PHASE-AWARE TOO (2026-07-16, user-requested "can we apply the
real competition WEZ into the code"). The platform's own damage/health
computation (src/dogfight/envs/single_agent_env.py::update_damage()) still uses
the flat, non-widening cone -- deliberately left that way, see
COMPETITION_RULES.md Sec6.3 -- because it calls self._sim.deduct_health()
*inside* the closed FighterSim object the instant it runs, so nothing outside
src/dogfight can intercept or correct it before termination checks fire on that
value. That means win/loss TIMING cannot be fixed from student space, full
stop. What CAN be fixed: the reward's damage term no longer trusts the
ownship_damage/target_damage the platform hands in (computed against the wrong,
flat cone) -- it computes its own estimate via reward_lib.wez_damage_estimate(),
using the real 3-phase model, from geometry this function already has. This is
an approximation, not a replacement for the platform's number: update_damage()
accumulates true per-tick damage across step_ratio (6) physics ticks per env
step, but compute_reward() only sees the state AFTER all 6 ticks -- so this
estimate treats the whole step_ratio block as one delta_t at the end-of-block
geometry (wez_step_ratio/wez_sim_hz in MY_REWARD_CONFIG), not true per-tick
accumulation. Closer to the real model than the flat cone regardless,
especially for late-match wide-cone shots the flat cone can't register at all.

ENERGY-STATE TERM ADDED 2026-07-16 (the "no energy-aware term" gap flagged in
memory/project_competition_readiness_assessment_2026_07_16.md). A new "energy"
component rewards ownship's specific-energy advantage over the target
(reward_lib.energy_advantage(): altitude + airspeed collapsed into one tanh
scalar) -- the one BFM axis the pursuit/position/advantage terms, all pure
angle x range geometry, never touch. INERT by default: energy_scale=0.0 in
MY_REWARD_CONFIG, opt-in per stage exactly like advantage_scale, so this changes
nothing for any currently-configured stage (including v4's in-progress run)
until a stage sets energy_scale > 0. A rate-based P_s (dE_s/dt) term was
considered and rejected: compute_reward() is a stateless per-step function with
no env handle, so a rate would need a module-level 'previous energy' that would
corrupt across Ray's interleaved vectorized/multi-worker envs. The differential
form needs no cross-step state and is learnable from the current 15-feature
observation. See reward_lib.energy_advantage()'s docstring for the zoom-and-run
caution.

Required contract:
  - MY_REWARD_CONFIG must be a dict.
  - compute_reward(...) must return (total_reward: float, components: dict).
  - Each item in components is recorded as ep_reward_<name> by the callbacks.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dogfight.sim.state_schema import StateIndex, velocity_xyz

from . import reward_lib
from .reward_lib import WEZ_PHASES, wez_pursuit_multipliers


MY_REWARD_CONFIG = {
    "survival_bonus": 0.0,
    "step_penalty": -0.01,
    "damage_scale": 20.0,
    "pursuit_scale": 0.3,
    "pursuit_half_angle_deg": 30.0,
    "pursuit_range_m": 3000.0,
    "position_scale": 0.3,
    "position_half_angle_deg": 30.0,
    "advantage_scale": 0.0,
    # Energy-state advantage (ownship vs target specific energy). INERT by
    # default (scale 0.0), opt-in per stage exactly like advantage_scale above --
    # so adding it changes NOTHING for any currently-configured stage, including
    # v4's in-progress run, until a stage sets energy_scale > 0 in its
    # reward_overrides. energy_ref_m is the "meaningful edge" scale for the
    # tanh (~1000 m of energy height). See reward_lib.energy_advantage()'s
    # docstring for the zoom-and-run caution before enabling it.
    "energy_scale": 0.0,
    "energy_ref_m": 1000.0,
    "low_altitude_penalty": 0.1,
    # Per-step total-reward clamp (finite-guard, added 2026-08-01). Wide enough
    # that terminal +/-100 and all normal shaping never touch it; only bounds a
    # pathological outlier. Set to 0.0 to disable the clamp (the NaN/Inf coercion
    # always runs regardless). See the finite-guard block in compute_reward().
    "reward_clip": 150.0,
    "wez_step_ratio": 6.0,
    "wez_sim_hz": 60.0,
    "win_reward": 100.0,
    "loss_reward": -100.0,
    "draw_reward": -30.0,
    "guard_fail_penalty": -50.0,
}

# end_condition strings (src/dogfight/envs/termination.py) that mean one side
# self-destructed (ground impact) rather than the episode reaching a genuine
# stalemate -- see the crash-routing note in the module docstring above.
_OWNSHIP_CRASH_CONDITIONS = {"ownship altitude below min"}
_TARGET_CRASH_CONDITIONS = {"target altitude below min"}


def compute_reward(
    ownship_state,
    target_state,
    ownship_damage: float,
    target_damage: float,
    geo_info,
    wez_config: dict,
    reward_config: dict,
    terminated: bool,
    truncated: bool,
    end_condition: str,
) -> tuple[float, dict]:
    """Compute step reward and return (total, components) tuple.

    components keys: survival, step, pursuit, position, advantage, energy, damage, safety, terminal
    """
    components: dict[str, float] = {}

    r_survival = float(reward_config.get("survival_bonus", 0.0))
    components["survival"] = r_survival

    r_step = float(reward_config["step_penalty"])
    components["step"] = r_step

    distance = geo_info._get_distance(ownship_state, target_state)
    ata = abs(geo_info._get_antenna_train_angle(ownship_state, target_state, False))
    elapsed_s = float(ownship_state[StateIndex.SIM_TIME])
    range_mult, angle_mult = wez_pursuit_multipliers(WEZ_PHASES, elapsed_s)
    base_half_angle = float(reward_config["pursuit_half_angle_deg"])

    half_angle = base_half_angle * angle_mult
    pursuit_range = float(reward_config["pursuit_range_m"]) * range_mult
    ata_factor = max(0.0, 1.0 - ata / half_angle)
    range_factor = max(0.0, 1.0 - distance / pursuit_range)
    r_pursuit = float(reward_config["pursuit_scale"]) * ata_factor * range_factor
    components["pursuit"] = r_pursuit

    aa = abs(geo_info._get_aspect_angle(ownship_state, target_state, True))
    position_half_angle = float(reward_config.get("position_half_angle_deg", base_half_angle))
    aa_factor = max(0.0, 1.0 - aa / position_half_angle)
    r_position = float(reward_config.get("position_scale", 0.0)) * aa_factor * range_factor
    components["position"] = r_position

    r_advantage = float(reward_config.get("advantage_scale", 0.0)) * reward_lib.positional_advantage(ata, aa)
    components["advantage"] = r_advantage

    # Energy-state advantage: the one BFM axis the angle x range terms above never
    # capture (altitude + airspeed, not geometry). Uses -D for altitude (matches
    # the observation's own altitude feature exactly, so the reward gradient lines
    # up with what the policy sees) and velocity_xyz norm for true airspeed. Inert
    # unless a stage sets energy_scale > 0 -- see MY_REWARD_CONFIG's note.
    energy_scale = float(reward_config.get("energy_scale", 0.0))
    if energy_scale != 0.0:
        own_alt = -float(ownship_state[StateIndex.D])
        tgt_alt = -float(target_state[StateIndex.D])
        own_speed = float(np.linalg.norm(velocity_xyz(ownship_state)))
        tgt_speed = float(np.linalg.norm(velocity_xyz(target_state)))
        r_energy = energy_scale * reward_lib.energy_advantage(
            own_alt, own_speed, tgt_alt, tgt_speed,
            energy_ref_m=float(reward_config.get("energy_ref_m", 1000.0)),
        )
    else:
        r_energy = 0.0
    components["energy"] = r_energy

    # Phase-aware damage estimate -- see the module docstring's 2026-07-16 note.
    # `ata` above is ownship's ATA-to-target (gates damage ownship deals); the
    # reverse angle gates damage the target deals to ownship.
    target_ata = abs(geo_info._get_antenna_train_angle(target_state, ownship_state, False))
    wez_delta_t = float(reward_config.get("wez_step_ratio", 6.0)) / float(
        reward_config.get("wez_sim_hz", 60.0)
    )
    est_target_damage = reward_lib.wez_damage_estimate(WEZ_PHASES, distance, ata, elapsed_s, wez_delta_t)
    est_ownship_damage = reward_lib.wez_damage_estimate(
        WEZ_PHASES, distance, target_ata, elapsed_s, wez_delta_t
    )
    r_damage = float(reward_config["damage_scale"]) * (est_target_damage - est_ownship_damage)
    components["damage"] = r_damage

    r_safety = 0.0
    if float(ownship_state[StateIndex.ALT]) < 600.0:
        r_safety = -float(reward_config["low_altitude_penalty"])
    components["safety"] = r_safety

    r_terminal = 0.0
    if terminated or truncated:
        ownship_health = float(ownship_state[StateIndex.HEALTH])
        target_health = float(target_state[StateIndex.HEALTH])
        if end_condition == "two circle headon guard fail":
            r_terminal = float(reward_config.get("guard_fail_penalty", -50.0))
        elif end_condition in _OWNSHIP_CRASH_CONDITIONS:
            r_terminal = float(reward_config["loss_reward"])
        elif end_condition in _TARGET_CRASH_CONDITIONS:
            r_terminal = float(reward_config["win_reward"])
        elif target_health <= 0.0 < ownship_health:
            r_terminal = float(reward_config["win_reward"])
        elif ownship_health <= 0.0 < target_health:
            r_terminal = float(reward_config["loss_reward"])
        else:
            r_terminal = float(reward_config["draw_reward"])
    components["terminal"] = r_terminal

    total = (
        r_survival + r_step + r_pursuit + r_position + r_advantage
        + r_energy + r_damage + r_safety + r_terminal
    )

    # --- Finite-guard + outlier clamp (added 2026-08-01) ----------------------
    # Defense-in-depth against the SAC NaN divergence that killed real_eagle v4
    # (paired with the grad_clip fix in train_curriculum.py). A single non-finite
    # reward entering the replay buffer poisons every subsequent TD target, so
    # guard it at the source: any NaN/Inf component is coerced to 0.0, and the
    # per-step total is clamped to +/- reward_clip. The clamp is deliberately wide
    # (150) -- the terminal +/-100 plus all normal shaping (|damage|<=~2, every
    # other term <1) never reaches it, so normal-range learning dynamics are
    # UNCHANGED; it only catches a pathological geometry that would otherwise emit
    # a runaway magnitude. Set reward_clip=0 in a stage's overrides to disable.
    reward_clip = float(reward_config.get("reward_clip", 150.0))
    for _name, _value in components.items():
        if not math.isfinite(_value):
            components[_name] = 0.0
    if not math.isfinite(total):
        total = float(sum(components.values()))
    if reward_clip > 0.0:
        total = max(-reward_clip, min(reward_clip, total))
    return float(total), components


__all__ = ["MY_REWARD_CONFIG", "compute_reward"]
