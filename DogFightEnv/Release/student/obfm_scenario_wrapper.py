# -*- coding: utf-8 -*-
"""Reconstructs the OBFM (offensive BFM) initial-scenario spawn that
src/dogfight/envs/single_agent_env.py used to apply for
initial_scenario.mode == "obfm", wiped by the 2026-07-15 revert along with
everything else added to that file after 2026-07-11 (see
memory/project_bulk_revert_regression_2026_07_15.md). single_agent_env.py's
reset() has no branch for an unrecognized scenario_mode -- it silently falls
through to the generic default spawn (symmetric, ~2500ft) -- so
student/my_curriculum.py's obfm_offensive/obfm_defensive stages have been
training against the wrong geometry the entire time this went unnoticed
(confirmed: stage 4 had already run 248 iterations against the wrong spawn
before this was found, 2026-07-16).

Deliberately NOT a src/dogfight/** edit (hard no-edit boundary, team policy,
see CLAUDE.md's editing table). Composes around the env via a standard
Gymnasium Wrapper instead, calling change_init_position() -- a public method
on DogFightEnv that survived the revert untouched -- before delegating to the
wrapped env's own reset(). This is the same idiom
_apply_two_circle_headon_initial_scenario() uses internally, just invoked
from outside the file instead of from within it.

No byte-exact recovery was possible for this one (unlike WEZ_PHASES/
velocity_xyz elsewhere this session): the only surviving bytecode cache for
single_agent_env.py postdates the revert itself (mtimes 2026-07-15 21:37 and
2026-07-16 01:07, both after the 21:11 revert), so there is nothing to
decompile. Reconstructed instead from the confirmed parameters in
memory/project_competition_initial_scenarios.md: separation_m=556,
lateral_offset_m=45 (giving an attacker ATA of atan(45/556) = 4.63deg,
matching the real captured screenshot's LOS 4.63/175.37 almost exactly),
altitude_m=4572 (15000ft), speed_mps=200.0. Per-episode heading/side
randomization added (matching _apply_two_circle_headon_initial_scenario's own
established pattern) so the policy doesn't overfit to one fixed compass
heading -- the confirmed numbers only pin the RELATIVE geometry, not an
absolute heading.
"""
from __future__ import annotations

import math

import gymnasium as gym
import numpy as np


OBFM_SEPARATION_M = 556.0
OBFM_LATERAL_OFFSET_M = 45.0
OBFM_ALTITUDE_M = 4572.0
OBFM_SPEED_MPS = 200.0


def _wrap_heading(deg: float) -> float:
    return deg % 360.0


def apply_obfm_scenario(
    env,
    role: str,
    separation_m: float = OBFM_SEPARATION_M,
    lateral_offset_m: float = OBFM_LATERAL_OFFSET_M,
    altitude_m: float = OBFM_ALTITUDE_M,
    speed_mps: float = OBFM_SPEED_MPS,
    rng: np.random.Generator | None = None,
) -> None:
    """Stage both aircraft's init position via env.change_init_position() so
    the next env.reset() places them in the confirmed OBFM geometry: the
    offensive-role aircraft separation_m directly behind the defensive-role
    aircraft, both co-heading (chase geometry, HCA~0), offset laterally by
    lateral_offset_m so the attacker's ATA is a real but small angle
    (~4.6deg at the defaults) rather than a degenerate 0deg dead-six.
    """
    rng = rng if rng is not None else np.random.default_rng()
    heading_deg = float(rng.uniform(0.0, 360.0))
    side = float(rng.choice([-1.0, 1.0]))

    heading_rad = math.radians(heading_deg)
    forward = (math.cos(heading_rad), math.sin(heading_rad))
    right = (math.sin(heading_rad), -math.cos(heading_rad))

    defender_n, defender_e = 0.0, 0.0
    attacker_n = defender_n - separation_m * forward[0] + side * lateral_offset_m * right[0]
    attacker_e = defender_e - separation_m * forward[1] + side * lateral_offset_m * right[1]

    offensive_flight = "ownship" if role == "offensive" else "target"
    defensive_flight = "target" if role == "offensive" else "ownship"
    heading = _wrap_heading(heading_deg)

    env.change_init_position(
        defensive_flight,
        init_n=defender_n,
        init_e=defender_e,
        init_d=-altitude_m,
        init_roll=0.0,
        init_pitch=0.0,
        init_heading=heading,
        init_speed=speed_mps,
    )
    env.change_init_position(
        offensive_flight,
        init_n=attacker_n,
        init_e=attacker_e,
        init_d=-altitude_m,
        init_roll=0.0,
        init_pitch=0.0,
        init_heading=heading,
        init_speed=speed_mps,
    )


class ObfmScenarioWrapper(gym.Wrapper):
    """Applies apply_obfm_scenario() before reset() whenever the wrapped
    env's config requests initial_scenario.mode == "obfm" -- see this
    module's docstring for why this exists instead of a src/dogfight/** fix.
    Transparent no-op for every other scenario mode (two_circle_headon,
    ref_old_random, default) -- the wrapped env's own reset() handles those
    exactly as before.
    """

    def reset(self, *, seed=None, options=None):
        # Use .unwrapped rather than .env: this wrapper happens to sit directly
        # on the base env today, but .env would resolve to another Wrapper
        # (with no .config of its own -- this Gymnasium version has no
        # Wrapper.__getattr__ forwarding) the moment stacking order changes,
        # e.g. when HabfmScenarioWrapper wraps around this one.
        base = self.unwrapped
        scenario = dict(base.config.get("initial_scenario", {}) or {})
        if options and "initial_scenario" in options:
            scenario = dict(options["initial_scenario"])
        if scenario.get("mode") == "obfm":
            role = scenario.get("role", "offensive")
            rng = getattr(base, "np_random", None)
            apply_obfm_scenario(
                base,
                role=role,
                separation_m=float(scenario.get("separation_m", OBFM_SEPARATION_M)),
                lateral_offset_m=float(scenario.get("lateral_offset_m", OBFM_LATERAL_OFFSET_M)),
                altitude_m=float(scenario.get("altitude_m", OBFM_ALTITUDE_M)),
                speed_mps=float(scenario.get("speed_mps", OBFM_SPEED_MPS)),
                rng=rng if isinstance(rng, np.random.Generator) else None,
            )
        return self.env.reset(seed=seed, options=options)


__all__ = ["ObfmScenarioWrapper", "apply_obfm_scenario"]
