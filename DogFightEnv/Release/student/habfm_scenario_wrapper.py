# -*- coding: utf-8 -*-
"""Reconstructs the HABFM (beam/high-aspect merge) initial-scenario spawn --
one of the four confirmed real competition starting geometries (see
memory/project_bt_headon_merge_fix_2026_07_16.md), which has NO dedicated
curriculum stage: closest existing coverage is full_dogfight's randomized
spawn, which might produce something similar by chance but nothing
deliberately trains it.

Confirmed geometry (2026-07-16, user screenshots): separation ~496 m, LOS
~91 deg off each aircraft's own nose (unsigned angle, 0 deg = pointed
directly at target, matching CheckSight.cpp's convention). Distinct from
OBFM (556 m, asymmetric 4.6/175.4 deg) despite the similar distance -- HABFM
is symmetric on both sides.

This is NOT a new geometry family: src/dogfight/envs/single_agent_env.py's
surviving _apply_two_circle_headon_initial_scenario() already produces
exactly this shape (own_heading = side*alpha, target_heading =
180+side*alpha, both placed along a line separated by separation_m) --
algebraically, that placement gives LOS = alpha on BOTH sides for any alpha,
which is how the existing alpha=90 rung of the two-circle ladder already
works. Rather than back-solving that function's indirect
turn_diameter_ft/sin(alpha) formula to hit exactly 496 m, this module
reimplements the same placement directly parametrized by the confirmed
separation_m/alpha_deg constants, staged as its own scenario mode ("habfm")
-- same idiom as obfm_scenario_wrapper.py, and for the same reason: no
plug-in hook in single_agent_env.py for a new mode, and that file is a hard
src/dogfight/** no-edit boundary (team policy, see CLAUDE.md's editing
table).

Per-episode heading/side randomization added (matching both
_apply_two_circle_headon_initial_scenario's own side flip and
apply_obfm_scenario's added full compass rotation) so the policy doesn't
overfit to one fixed absolute heading -- the confirmed numbers only pin the
RELATIVE geometry (separation + each side's own LOS), not an absolute
compass direction.
"""
from __future__ import annotations

import math

import gymnasium as gym
import numpy as np


HABFM_SEPARATION_M = 496.0
HABFM_LOS_DEG = 91.0
HABFM_ALTITUDE_M = 4572.0
HABFM_SPEED_MPS = 200.0


def _wrap_heading(deg: float) -> float:
    return deg % 360.0


def apply_habfm_scenario(
    env,
    separation_m: float = HABFM_SEPARATION_M,
    alpha_deg: float = HABFM_LOS_DEG,
    altitude_m: float = HABFM_ALTITUDE_M,
    speed_mps: float = HABFM_SPEED_MPS,
    rng: np.random.Generator | None = None,
) -> None:
    """Stage both aircraft's init position via env.change_init_position() so
    the next env.reset() places them in the confirmed HABFM geometry: both
    aircraft separation_m apart along a randomized baseline axis, each
    aircraft's heading rotated alpha_deg off that axis (mirrored by a random
    +/-1 side) -- which places BOTH aircraft's own nose alpha_deg off their
    LOS to the other, the symmetric beam/high-aspect signature confirmed at
    alpha_deg~91.
    """
    rng = rng if rng is not None else np.random.default_rng()
    heading_deg = float(rng.uniform(0.0, 360.0))
    side = float(rng.choice([-1.0, 1.0]))

    heading_rad = math.radians(heading_deg)
    forward = (math.cos(heading_rad), math.sin(heading_rad))
    half_sep = separation_m / 2.0

    own_n = -half_sep * forward[0]
    own_e = -half_sep * forward[1]
    target_n = half_sep * forward[0]
    target_e = half_sep * forward[1]

    own_heading = _wrap_heading(heading_deg + side * alpha_deg)
    target_heading = _wrap_heading(heading_deg + 180.0 + side * alpha_deg)

    env.change_init_position(
        "ownship",
        init_n=own_n,
        init_e=own_e,
        init_d=-altitude_m,
        init_roll=0.0,
        init_pitch=0.0,
        init_heading=own_heading,
        init_speed=speed_mps,
    )
    env.change_init_position(
        "target",
        init_n=target_n,
        init_e=target_e,
        init_d=-altitude_m,
        init_roll=0.0,
        init_pitch=0.0,
        init_heading=target_heading,
        init_speed=speed_mps,
    )


class HabfmScenarioWrapper(gym.Wrapper):
    """Applies apply_habfm_scenario() before reset() whenever the wrapped
    env's config requests initial_scenario.mode == "habfm" -- see this
    module's docstring for why this exists instead of a src/dogfight/** fix.
    Transparent no-op for every other scenario mode.
    """

    def reset(self, *, seed=None, options=None):
        base = self.unwrapped
        scenario = dict(base.config.get("initial_scenario", {}) or {})
        if options and "initial_scenario" in options:
            scenario = dict(options["initial_scenario"])
        if scenario.get("mode") == "habfm":
            rng = getattr(base, "np_random", None)
            apply_habfm_scenario(
                base,
                separation_m=float(scenario.get("separation_m", HABFM_SEPARATION_M)),
                alpha_deg=float(scenario.get("alpha_deg", HABFM_LOS_DEG)),
                altitude_m=float(scenario.get("altitude_m", HABFM_ALTITUDE_M)),
                speed_mps=float(scenario.get("speed_mps", HABFM_SPEED_MPS)),
                rng=rng if isinstance(rng, np.random.Generator) else None,
            )
        return self.env.reset(seed=seed, options=options)

    def make_tacviewLog(self):
        # This Gymnasium version's gym.Wrapper has no __getattr__ forwarding
        # (see train_curriculum.py's env_creator() comment), so callers that
        # hold this wrapper as "the env" (e.g. EngagementReplayLogger) can't
        # reach the base DogFightEnv's make_tacviewLog() without this.
        return self.unwrapped.make_tacviewLog()


__all__ = ["HabfmScenarioWrapper", "apply_habfm_scenario"]
