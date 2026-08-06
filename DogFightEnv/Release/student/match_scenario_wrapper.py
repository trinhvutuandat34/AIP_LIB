# -*- coding: utf-8 -*-
"""The two OFFICIAL competition starting geometries, from the kickoff-deck scenario slides.

SOURCE (slides transcribed 2026-08-06):

  * PRELIM -- "교전 시나리오 룰(예선)": ONE round (단판), the two aircraft drawn at
    **2000ft ~ 3000ft** separation, "AlphaDogFight 의 교전 방식을 채용".
    Exact figures (시작거리/고도/속력) are "차후 공개".
  * FINALS -- "교전 시나리오 룰(본선)": rounds 1-3 use that SAME 2000-3000 ft setup;
    round 4+ is the tie-break, entered only if 3 rounds are level, and is described
    explicitly as **"서로 마주본 상태에서 정면 교전 수행"** at **10000ft 이상**.

GEOMETRY, and a correction worth reading. The rounds-1-3 diagram shows the two aircraft
pointing in OPPOSITE directions with the separation arrow drawn BETWEEN them, i.e. the
headings are antiparallel and the line of sight runs across them -- a **beam merge**,
each aircraft's LOS ~90 deg off its own nose. It is NOT a nose-to-nose pass. Only the
round-4 tie-break is a true head-on, which is why that slide is the only one that says
"정면". An earlier reading here modelled rounds 1-3 as nose-to-nose and was wrong; a
nose-to-nose spawn at 610-914 m starts BOTH aircraft with a firing solution already
inside the WEZ band, which produces immediate mutual damage and is a completely
different (and fictitious) problem.

`los_deg` IS DELIBERATELY A PARAMETER, because the slide art supports two readings and
they imply different opening tactics:
    los_deg = 90   -> antiparallel and abeam (a beam merge; the reading taken as default,
                      and the one matching habfm_scenario_wrapper's confirmed
                      symmetric-91-deg signature)
    los_deg = 180  -> antiparallel and nose-away (tail-to-tail, diverging)
Both are cheap to evaluate; do not assume, measure. Confirm against the viewer when a
practice server is available.

Relationship to the existing wrappers: this is the same placement math as
`habfm_scenario_wrapper.apply_habfm_scenario` (both aircraft on a randomized baseline,
each heading rotated `los_deg` off it, mirrored by a random side), re-parametrized for
the deck's separation band. HABFM itself is the same shape pinned at 496 m / 91 deg from
a captured screenshot; this module is the officially-published band. `obfm_*` is a
different family entirely -- it stages a six-o'clock ADVANTAGE, which the rules never
grant, so obfm results do not predict match performance.

PROVISIONAL: the deck pins only the SEPARATION. `altitude_m` 4572 (15000 ft) and
`speed_mps` 200 are carried from the confirmed viewer presets (COMPETITION_PLAN.md
Sec 4 row 6) and must be rechecked when the organizers publish exact figures.

Boundary: `src/dogfight/**` untouched -- same idiom and reason as the OBFM/HABFM wrappers.
"""
from __future__ import annotations

import math

import gymnasium as gym
import numpy as np


# Rounds 1-3 and the prelim: 2000 ft and 3000 ft exactly, in metres.
MATCH_SEPARATION_MIN_M = 609.6
MATCH_SEPARATION_MAX_M = 914.4
# Beam merge: each aircraft's LOS to the other, off its own nose. See the docstring --
# 180.0 is the competing reading of the same slide.
MATCH_LOS_DEG = 90.0

# Round 4+ tie-break: "10000ft 이상", true head-on ("정면").
TIEBREAK_SEPARATION_M = 3048.0
TIEBREAK_LOS_DEG = 0.0

# PROVISIONAL -- not pinned by the deck ("차후 공개").
MATCH_ALTITUDE_M = 4572.0
MATCH_SPEED_MPS = 200.0


def _wrap_heading(deg: float) -> float:
    return deg % 360.0


def apply_match_scenario(
    env,
    separation_m: float | None = None,
    separation_range_m: tuple[float, float] = (
        MATCH_SEPARATION_MIN_M,
        MATCH_SEPARATION_MAX_M,
    ),
    los_deg: float = MATCH_LOS_DEG,
    altitude_m: float = MATCH_ALTITUDE_M,
    speed_mps: float = MATCH_SPEED_MPS,
    rng: np.random.Generator | None = None,
) -> None:
    """Stage the official match geometry for the next `env.reset()`.

    Both aircraft are placed `separation_m` apart on a randomized baseline axis, each
    heading rotated `los_deg` off that axis and mirrored by a random side -- which puts
    BOTH aircraft's own nose `los_deg` off its LOS to the other (symmetric, as the slide
    shows). `separation_m=None` samples the 2000-3000 ft band per episode.

    The baseline is randomized over the full compass so nothing overfits an absolute
    heading; the deck pins relative geometry only.
    """
    rng = rng if rng is not None else np.random.default_rng()
    if separation_m is None:
        lo, hi = float(separation_range_m[0]), float(separation_range_m[1])
        separation_m = float(rng.uniform(lo, hi)) if hi > lo else lo

    heading_deg = float(rng.uniform(0.0, 360.0))
    side = float(rng.choice([-1.0, 1.0]))

    heading_rad = math.radians(heading_deg)
    forward = (math.cos(heading_rad), math.sin(heading_rad))
    half_sep = float(separation_m) / 2.0

    own_n = -half_sep * forward[0]
    own_e = -half_sep * forward[1]
    target_n = half_sep * forward[0]
    target_e = half_sep * forward[1]

    # los_deg=0 -> both noses down the baseline at each other (round-4 head-on).
    # los_deg=90 -> both noses across it, antiparallel and abeam (rounds 1-3 beam merge).
    own_heading = _wrap_heading(heading_deg + side * los_deg)
    target_heading = _wrap_heading(heading_deg + 180.0 + side * los_deg)

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


class MatchScenarioWrapper(gym.Wrapper):
    """Applies `apply_match_scenario()` before reset() for
    `initial_scenario.mode in ("match_base", "match_tiebreak")`.
    Transparent no-op for every other scenario mode.
    """

    _MODES = {
        # rounds 1-3 + prelim
        "match_base": (MATCH_LOS_DEG, MATCH_SEPARATION_MIN_M, MATCH_SEPARATION_MAX_M),
        # round 4+ tie-break
        "match_tiebreak": (TIEBREAK_LOS_DEG, TIEBREAK_SEPARATION_M, TIEBREAK_SEPARATION_M),
    }

    def reset(self, *, seed=None, options=None):
        base = self.unwrapped
        scenario = dict(base.config.get("initial_scenario", {}) or {})
        if options and "initial_scenario" in options:
            scenario = dict(options["initial_scenario"])
        mode = scenario.get("mode")
        if mode in self._MODES:
            default_los, default_min, default_max = self._MODES[mode]
            rng = getattr(base, "np_random", None)
            sep = scenario.get("separation_m")
            apply_match_scenario(
                base,
                separation_m=(float(sep) if sep is not None else None),
                separation_range_m=(
                    float(scenario.get("separation_min_m", default_min)),
                    float(scenario.get("separation_max_m", default_max)),
                ),
                los_deg=float(scenario.get("los_deg", default_los)),
                altitude_m=float(scenario.get("altitude_m", MATCH_ALTITUDE_M)),
                speed_mps=float(scenario.get("speed_mps", MATCH_SPEED_MPS)),
                rng=rng if isinstance(rng, np.random.Generator) else None,
            )
        return self.env.reset(seed=seed, options=options)

    def make_tacviewLog(self):
        # This Gymnasium version's gym.Wrapper has no __getattr__ forwarding, so callers
        # holding this wrapper as "the env" cannot reach the base env's make_tacviewLog()
        # without this -- same note as the HABFM wrapper.
        return self.unwrapped.make_tacviewLog()
