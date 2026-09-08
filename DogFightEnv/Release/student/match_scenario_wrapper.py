# -*- coding: utf-8 -*-
"""The two OFFICIAL competition starting geometries, from the kickoff-deck scenario slides.

SOURCE, in precedence order:

  * **본선 운영 안내 -- organizing-committee announcement, 2026-09-03. AUTHORITATIVE.**
    Finals 2026-09-17, 16 teams. Group stage: 4 groups x 4 teams, round robin, **BO3**.
    Knockout: 8강/4강/결승, single elimination, **BO5**. Per game:
      - **초기 고도와 속도는 랜덤** -- altitude AND speed are RANDOMIZED every game.
        The band is NOT published (asked 2026-09-03; see the PROVISIONAL note below).
      - **시작 상대거리 cycles with the game index**: 1경기 2,000 ft -> 2경기 2,500 ft
        -> 3경기 3,000 ft -> 4경기 2,000 ft -> 5경기 2,500 ft ... A three-value cycle,
        not a uniform band -- and **game 4 is 2,000 ft**, so there is no long-range
        fourth round.
      - Blue/Red **alternates every game** (game 1: the bracket's left-hand team is Blue).
      - **Head-On 모드 is a DRAW-TRIGGERED MODE, not a round number.** In the knockout
        rounds, if games 1 AND 2 are both draws, every subsequent game of that match is
        played head-on. Its separation was NOT published.
  * **SUPERSEDED** -- kickoff-deck scenario slides (transcribed 2026-08-06). They put
    rounds 1-3 in a 2000-3000 ft band and made **"round 4+" a tie-break at 10000ft 이상**,
    head-on ("서로 마주본 상태에서 정면 교전 수행"). **That round does not exist.** The
    head-on GEOMETRY survived the change; the 10,000 ft separation and the round number
    did not. `match_tiebreak` below is kept as the head-on proxy, with its separation now
    marked as an assumption rather than a citation.

GEOMETRY, and a correction worth reading. The rounds-1-3 diagram shows the two aircraft
pointing in OPPOSITE directions with the separation arrow drawn BETWEEN them, i.e. the
headings are antiparallel and the line of sight runs across them -- a **beam merge**,
each aircraft's LOS ~90 deg off its own nose. It is NOT a nose-to-nose pass. The only
nose-to-nose geometry in this competition is **Head-On 모드**, and the 2026-09-03
announcement makes that a draw-triggered mode rather than a round -- so the beam merge is
what gets played in EVERY game of EVERY match, and head-on is reached only after two
drawn games of a knockout tie. An earlier reading here modelled rounds 1-3 as
nose-to-nose and was wrong; a
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

PROVISIONAL -- and now known to be WRONG AS A FIXED VALUE. `altitude_m` 4572 (15000 ft)
and `speed_mps` 200 are single viewer presets (COMPETITION_PLAN.md Sec 4 row 6). The
2026-09-03 announcement makes BOTH random per game, and does not publish the band. So any
result measured at one altitude/speed pair is a point sample, not a match prediction:
sweep instead of assuming. `DOGFIGHT_MATCH_ALTITUDE_M` overrides altitude -- the ~600 m
regime seen in real server packets is the one that decides whether Gate 0 eats the tree
(F38) -- and `speed_mps` is a call parameter. Band requested from the organizers
2026-09-03 (ORGANIZER_QUESTIONS_20260821.md).

Boundary: `src/dogfight/**` untouched -- same idiom and reason as the OBFM/HABFM wrappers.
"""
from __future__ import annotations

import math
import os

import gymnasium as gym
import numpy as np


# Every game of every match. The start separation cycles 2,000 -> 2,500 -> 3,000 ft with
# the game index (announcement 2026-09-03), so these are the ends of a THREE-VALUE SET,
# not of a continuous band.
MATCH_SEPARATION_MIN_M = 609.6   # 2,000 ft -- games 1, 4
MATCH_SEPARATION_MAX_M = 914.4   # 3,000 ft -- game 3
# The actual set. `apply_match_scenario()` still samples UNIFORMLY over [min, max] when
# `separation_m is None`, deliberately: switching to a discrete draw here would silently
# change the spawn distribution underneath the F56/F58/F59 numbers, which are all
# uniform-band measurements. Re-measure against this set as its own pass, then switch.
MATCH_SEPARATION_SET_M = (609.6, 762.0, 914.4)  # 2,000 / 2,500 / 3,000 ft
# Beam merge: each aircraft's LOS to the other, off its own nose. See the docstring --
# 180.0 is the competing reading of the same slide.
MATCH_LOS_DEG = 90.0

# HEAD-ON MODE. Kept under the `TIEBREAK_*` / `match_tiebreak` names so the eval scripts,
# the league runner and the existing F58/F59 artifacts keep resolving -- the NAMES are
# historical, the MEANING changed on 2026-09-03.
#
# STILL SOURCED: the mode is nose-to-nose ("정면"), so LOS 0 deg stands.
#
# SEPARATION: 3,048 m (10,000 ft) -- **CONFIRMED BY THE ORGANIZERS**, relayed by the team
# 2026-09-05 (F72). This value was previously carried here as an unsourced ASSUMPTION: it
# originated in the superseded "round 4+ = 10000ft 이상" slide, and the 2026-09-03 announcement
# that replaced that slide gave Head-On mode no separation at all, so the number was left
# standing on nothing. The organizers' answer has now re-established it independently of the
# slide it came from. Provenance recorded deliberately, because the figure coinciding with the
# superseded reading is exactly the kind of thing a future session would otherwise "correct"
# back to an assumption.
#
# TWO CONSEQUENCES, both good:
#   * The F58 head-on numbers were measured at the RIGHT range after all -- they transfer.
#   * The training curriculum's alpha-sweep (`two_circle_headon_a000`...`a180`), built for the
#     old 10,000 ft head-on round, is not just the right FAMILY for Head-On mode (as
#     COMPETITION_RULES.md 7 already said) but the right SEPARATION too.
# Still overridable via `DOGFIGHT_HEADON_SEPARATION_M` for robustness sweeps -- see
# `scripts/sweep_headon_separation.py`.
TIEBREAK_SEPARATION_M = float(os.environ.get("DOGFIGHT_HEADON_SEPARATION_M", "3048.0"))
TIEBREAK_LOS_DEG = 0.0

# PROVISIONAL -- not pinned by the deck ("차후 공개").
#
# OVERRIDABLE VIA DOGFIGHT_MATCH_ALTITUDE_M (added 2026-08-20), because this number being an
# ASSUMPTION rather than a measurement turns out to matter enormously. Real MT_PlaneInfo captured
# from an actual server (logs/unreal_packets/, 13,708 airborne frames) reports altitudes of
# 0-1067 m, median 604 m -- NOT 4572 m. That band sits almost entirely BELOW
# Task_ClimbToSafeAltitude's SAFE_ALTITUDE_TRIGGER_M of 914 m, and that node is Gate 0, the
# outer Fallback's top priority: when it fires it aims +5000 m straight up, firewalls the
# throttle, returns SUCCESS, and every tactical gate beneath it is never evaluated. 65% of those
# real airborne frames are below the trigger.
#
# Local eval has never been able to see this, because every local scenario spawns at 4572-7000 m
# where Gate 0 simply never fires. Set this env var to reproduce the real altitude regime:
#     DOGFIGHT_MATCH_ALTITUDE_M=600 python scripts/eval_v5_vs_bt.py --scenario-mode match_base ...
# See LIVE_INFERENCE_FRAME_BUGS.md and COMPETITION_PLAN.md 4.1 F38.
MATCH_ALTITUDE_M = float(os.environ.get("DOGFIGHT_MATCH_ALTITUDE_M", "4572.0"))
MATCH_SPEED_MPS = 200.0

# PER-EPISODE RANDOMISATION of the start altitude and speed (added 2026-09-04). The 본선
# randomises both every game and does not publish the band (COMPETITION_RULES.md 5.1), so this
# is a knob to sweep, not a reproduction of a known rule.
#
# DEFAULT OFF -- both bands empty -- so the RNG stream and every existing measurement are
# unchanged unless a band is asked for. When a band IS set the draws happen AFTER the heading
# and side draws, so turning it on does not shift those either.
#
# The band we can actually justify today, from three independent observations: 4,572 m (the F7
# viewer preset), 0-1,067 m with median 604 m (real captured server packets, F38), and 7,703 m
# (the 8-27 trajectory, F62). So the observed spread is roughly 300 m to 7,700 m, and the
# 600 m regime is the one that decides whether Gate 0 eats the tree. Sweep it; do not assume it.
MATCH_ALTITUDE_RANGE_M = os.environ.get("DOGFIGHT_MATCH_ALTITUDE_RANGE_M", "")
MATCH_SPEED_RANGE_MPS = os.environ.get("DOGFIGHT_MATCH_SPEED_RANGE_MPS", "")


def _parse_band(text: str) -> tuple[float, float] | None:
    """"lo,hi" -> (lo, hi); empty -> None (randomisation off).

    A NON-EMPTY value that does not parse, or whose hi <= lo, RAISES rather than returning None.
    It used to return None, which silently disabled randomisation: a typo in
    DOGFIGHT_MATCH_ALTITUDE_RANGE_M produced a full campaign of fixed-spawn episodes that looked
    exactly like a randomised one, and league.py sets these two variables on every child
    (league.py:273-275) so one bad flag would have hit all 15 pairs at once. Someone who set the
    variable meant to randomise; failing loudly is the only reading that cannot mislead.
    """
    if not text:
        return None
    try:
        lo, hi = (float(x) for x in text.split(","))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"band must be 'lo,hi' floats, got {text!r}") from exc
    if hi <= lo:
        raise ValueError(f"band 'lo,hi' needs hi > lo, got {text!r}")
    return (lo, hi)


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
    side: float | None = None,
    altitude_range_m: tuple[float, float] | None = None,
    speed_range_mps: tuple[float, float] | None = None,
) -> None:
    """Stage the official match geometry for the next `env.reset()`.

    Both aircraft are placed `separation_m` apart on a randomized baseline axis, each
    heading rotated `los_deg` off that axis and mirrored by a random side -- which puts
    BOTH aircraft's own nose `los_deg` off its LOS to the other (symmetric, as the slide
    shows). `separation_m=None` samples the 2000-3000 ft band per episode -- uniformly,
    which approximates the real 2,000/2,500/3,000 ft cycle; pass `separation_m` explicitly
    (or draw from `MATCH_SEPARATION_SET_M`) to reproduce a specific game index.

    The baseline is randomized over the full compass so nothing overfits an absolute
    heading; the deck pins relative geometry only.

    `side` FORCES the mirror instead of drawing it (+1 / -1; None keeps the random draw).
    This exists for the side-symmetry test: positions do not depend on `side` -- only the two
    headings do, each by `side * los_deg` about the baseline -- so the SAME SEED run twice with
    side=+1 and side=-1 produces an exact mirror-image pair of engagements. A config with no
    left/right bias must score the same on both within sampling error. Added 2026-09-04 because
    Blue/Red alternates every game in the 본선 (COMPETITION_RULES.md 5.1) and this project has
    already shipped one laterality bug (`ShorterTurnDirection` picking by fore/aft instead of
    left/right, c0f3eaf), which nothing in the eval harness could have caught.

    NOTE the draw order matters for reproducibility: the baseline heading is drawn BEFORE the
    side, so forcing the side leaves the heading draw untouched and the pair really is a mirror
    rather than two unrelated engagements.
    """
    rng = rng if rng is not None else np.random.default_rng()
    if separation_m is None:
        lo, hi = float(separation_range_m[0]), float(separation_range_m[1])
        separation_m = float(rng.uniform(lo, hi)) if hi > lo else lo

    # Drawn AFTER separation and BEFORE heading/side would shift the stream, so both bands are
    # drawn last: with no band set, not a single extra number is consumed and every prior
    # measurement reproduces exactly.
    heading_deg = float(rng.uniform(0.0, 360.0))
    # Draw the side even when it is forced, so the RNG stream stays aligned between a forced
    # run and a random one at the same seed -- otherwise every downstream draw shifts and the
    # two runs stop being comparable for reasons that have nothing to do with laterality.
    drawn_side = float(rng.choice([-1.0, 1.0]))
    side = drawn_side if side is None else float(side)

    if altitude_range_m is not None:
        altitude_m = float(rng.uniform(float(altitude_range_m[0]), float(altitude_range_m[1])))
    if speed_range_mps is not None:
        speed_mps = float(rng.uniform(float(speed_range_mps[0]), float(speed_range_mps[1])))

    heading_rad = math.radians(heading_deg)
    forward = (math.cos(heading_rad), math.sin(heading_rad))
    half_sep = float(separation_m) / 2.0

    own_n = -half_sep * forward[0]
    own_e = -half_sep * forward[1]
    target_n = half_sep * forward[0]
    target_e = half_sep * forward[1]

    # los_deg=0 -> both noses down the baseline at each other (Head-On 모드).
    # los_deg=90 -> both noses across it, antiparallel and abeam (the every-game merge).
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
        # the beam merge -- every game of every match
        "match_base": (MATCH_LOS_DEG, MATCH_SEPARATION_MIN_M, MATCH_SEPARATION_MAX_M),
        # Head-On 모드 (name historical; separation is an assumption -- see the constant)
        "match_tiebreak": (TIEBREAK_LOS_DEG, TIEBREAK_SEPARATION_M, TIEBREAK_SEPARATION_M),
    }

    def reset(self, *, seed=None, options=None):
        base = self.unwrapped
        scenario = dict(base.config.get("initial_scenario", {}) or {})
        if options and "initial_scenario" in options:
            scenario = dict(options["initial_scenario"])
        mode = scenario.get("mode")
        if mode in self._MODES:
            # RESEED BEFORE THE DRAW (2026-09-08). apply_match_scenario() below draws the spawn
            # from base.np_random, but the only thing that ever seeded that generator was the
            # `self.env.reset(seed=seed)` at the END of this method. So the spawn for episode i
            # was drawn from whatever state episode i-1's env left behind, and the FIRST episode
            # of every process drew from an unseeded, OS-entropy generator.
            #
            # Measured consequence across the 15 same-seed F66 match_base CSVs: 54 of 150 episode
            # indices had 15 DIFFERENT spawn tuples -- one per file -- and they are exactly the
            # first episode of every chunked child process (0, 9, 10, 12, 13, 15, 24, ...). So the
            # common-random-numbers pairing that makes candidate columns comparable held for only
            # 96/150 of them, and re-running the identical command did not reproduce the rest.
            # That is why N=50 ranked the candidates differently from N=150.
            #
            # Seeding here with the same value reset() is about to use makes the spawn a pure
            # function of the seed. reset() then re-seeds the generator to the identical state, so
            # the env's OWN randomisation is bit-for-bit what it always was -- only the spawn draw
            # changes. This does invalidate cross-run comparison against pre-2026-09-08 CSVs; it
            # lands with a re-baseline, not between two halves of one campaign.
            if seed is not None:
                base.np_random = np.random.default_rng(seed)
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
                side=(float(scenario["side"]) if scenario.get("side") is not None else None),
                altitude_range_m=(scenario.get("altitude_range_m")
                                  or _parse_band(MATCH_ALTITUDE_RANGE_M)),
                speed_range_mps=(scenario.get("speed_range_mps")
                                 or _parse_band(MATCH_SPEED_RANGE_MPS)),
            )
        return self.env.reset(seed=seed, options=options)

    def make_tacviewLog(self):
        # This Gymnasium version's gym.Wrapper has no __getattr__ forwarding, so callers
        # holding this wrapper as "the env" cannot reach the base env's make_tacviewLog()
        # without this -- same note as the HABFM wrapper.
        return self.unwrapped.make_tacviewLog()
