# -*- coding: utf-8 -*-
"""real_eagle curriculum = the built-in 15-stage curriculum + two OBFM stages
+ one HABFM stage, with the two-circle ladder rebuilt for v4.

RECOVERED 2026-07-15: the 2026-07-15 accidental full-tree revert (see
memory/project_bulk_revert_regression_2026_07_15.md) overwrote this file back
to the bare starter template. The OBFM portion below is recovered byte-exact
from a stale __pycache__/my_curriculum.cpython-313.pyc (compiled 2026-07-12
03:36 by a different interpreter than the active `aip` env, so it survived the
revert) via bytecode disassembly -- that snapshot is real_eagle_v3-era: OBFM
stages present, two-circle ladder still the untouched 10-alpha builtin.

Adds the asymmetric offensive/defensive-BFM starts the built-in neutral
curriculum lacks. The competition's OBFM_RED/OBFM_BLUE presets spawn one
aircraft ~556 m directly behind the other, already near a gun solution
(geometry confirmed 2026-07-11 from the viewer, LOS ~4.6 deg attacker / ~175 deg
defender); see memory/project_competition_initial_scenarios.md. The neutral
starts (fixed/loiter/two_circle) never hand either side an edge, so BT-vs-BT
stalemates with 0 WEZ contact -- these OBFM stages give a clean
convert-the-advantage (offensive) and survive-the-disadvantage (defensive)
signal instead.

v4 two-circle rebuild (described in real_eagle_v4.yaml's header comment, never
captured in a surviving bytecode cache -- rebuilt fresh here from that
description, not decompiled): 5-alpha ladder (0/45/90/135/180, down from the
builtin's 10) with pursuit_range_m widened to 8 km and advantage_scale raised
to 0.1 so spawn separation lands inside the shaping gradient; full_dogfight
extended to 1500 iterations with the freed budget, and (fixed 2026-07-16)
episode_step_limit corrected to 12000 (200s @ 60Hz) -- the builtin stage's
18000 (300s) didn't match COMPETITION_RULES.md's actual 200s match length.

KNOWN GAP -- geometry_guard left DISABLED for the two-circle stages:
v4.yaml's fix #2 replaced the two-circle guard's algorithm itself (ATA-limit ->
range-based disengagement, "leave the fight beyond 8 km = loss") inside
src/dogfight/envs/termination.py. That file is a hard no-edit boundary (team
policy since 2026-07-14), and no bytecode cache of the fixed version survived
the revert -- termination.cpython-313.pyc did survive, but decompiling it shows
the pre-fix, still-ATA-only guard, so there's nothing to recover here, only to
avoid reproducing. The builtin ATA-only guard is the one the 2026-07-12 audit
found "physically unpassable" (100pct guard-fail losses trained merge
avoidance); turning it on here would reintroduce that bug. Leaving it off means
these stages rely on max_engage_time/episode_step_limit alone to end a
runaway-avoidance episode -- weaker than the real fix. Flagged for the user
rather than guessed at; revisit once termination.py's fix can be re-applied
through whatever process the team settles on for that boundary.

ADDED 2026-07-16: habfm_beam_merge, spliced right after obfm_defensive (before
the two-circle ladder) -- the fourth confirmed real competition starting
geometry (see memory/project_bt_headon_merge_fix_2026_07_16.md), ~496 m
separation with a symmetric ~91 deg LOS off BOTH aircraft's nose (unlike
OBFM's asymmetric 4.6/175.4 deg, neither side starts ahead here). Had no
dedicated stage before this -- full_dogfight's randomized spawn might produce
something similar by chance but nothing deliberately trained it. Uses a new
"habfm" initial_scenario.mode, implemented in
student/habfm_scenario_wrapper.py (same wrapper idiom as
obfm_scenario_wrapper.py: single_agent_env.py has no plug-in hook for a new
mode and is a hard no-edit boundary) -- NOT a revert casualty like OBFM was,
this mode simply never existed before. Inserted at index 6 (after
obfm_defensive at index 5, unchanged), pushing two_circle_v4/full_dogfight_v4
to indices 7-12 -- safe for v4's already-in-progress run because
_init_or_load_state()'s resume path (train_curriculum.py) now backfills any
stage index missing from a loaded curriculum_state.json, and indices 0-5
(the only ones with real training history) are untouched.

Wired via `curriculum.stages_module: student.my_curriculum` (see
experiments/real_eagle_v4.yaml). The built-in src/dogfight/ai/curriculum.py is
imported and left UNMODIFIED so in-progress runs that use it directly keep
resuming cleanly -- this file only reorders/extends a fresh copy.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dogfight.ai.curriculum import CurriculumStage, get_stages as _builtin_get_stages
from student.obfm_scenario_wrapper import OBFM_ALTITUDE_M, OBFM_SPEED_MPS
from student.habfm_scenario_wrapper import HABFM_ALTITUDE_M, HABFM_LOS_DEG, HABFM_SPEED_MPS
from student.match_scenario_wrapper import (
    MATCH_ALTITUDE_M,
    MATCH_LOS_DEG,
    MATCH_SEPARATION_MAX_M,
    MATCH_SEPARATION_MIN_M,
    MATCH_SPEED_MPS,
)


_OBFM_OFFENSIVE_REWARD = {
    "survival_bonus": 0.0,
    "pursuit_scale": 0.3,
    "pursuit_half_angle_deg": 30.0,
    "pursuit_range_m": 3000.0,
    "position_scale": 0.3,
    "position_half_angle_deg": 30.0,
    "damage_scale": 20.0,
    "low_altitude_penalty": 0.1,
    "win_reward": 100.0,
    "loss_reward": -100.0,
    "draw_reward": -30.0,
}

_OBFM_DEFENSIVE_REWARD = {
    "survival_bonus": 0.02,
    "pursuit_scale": 0.1,
    "pursuit_half_angle_deg": 30.0,
    "pursuit_range_m": 3000.0,
    "position_scale": 0.1,
    "position_half_angle_deg": 30.0,
    "damage_scale": 20.0,
    "low_altitude_penalty": 0.2,
    "win_reward": 100.0,
    "loss_reward": -100.0,
    "draw_reward": 20.0,
}

# Energy-state shaping weight for the neutral-merge stages (habfm + two_circle +
# full_dogfight), enabled 2026-07-16. Deliberately half the un-gated
# advantage_scale (0.1) below: energy_advantage returns [-1,1] and, like
# advantage, is NOT range-gated, so it accrues every step -- a conservative
# starting weight for a brand-new, never-trained axis, per
# reward_lib.energy_advantage()'s zoom-and-run caution. Tune UP after watching
# engagement replays if the policy isn't using the vertical; tune DOWN (or add
# the documented range-gate) if it starts hoarding energy / disengaging.
# Deliberately NOT applied to the OBFM stages (position-dominated close-in
# drills) or the in-progress stage 4 -- see this session's memory.
_ENERGY_SCALE = 0.05

# v4 two-circle rebuild: down-weight pursuit/position when advantage_scale is
# raised, per reward_lib.positional_advantage()'s own docstring warning against
# stacking all three positional terms at full weight simultaneously.
_TWO_CIRCLE_V4_REWARD_OVERRIDES = {
    "pursuit_range_m": 8000.0,
    "advantage_scale": 0.1,
    "pursuit_scale": 0.2,
    "position_scale": 0.2,
    "energy_scale": _ENERGY_SCALE,
}


def _obfm_stage(
    name: str, description: str, role: str, reward: dict, advance: dict
) -> CurriculumStage:
    return CurriculumStage(
        index=0,
        name=name,
        description=description,
        target_mode="behavior_tree",
        episode_step_limit=12000,
        max_iterations=300,
        checkpoint_interval=10,
        reward_overrides=reward,
        randomization={"enabled": False},
        advance_conditions=advance,
        advance_window=10,
        env_overrides={
            # altitude_m/speed_mps set explicitly (not left to the wrapper's own
            # defaults): DEFAULT_ENV_CONFIG's initial_scenario dict already has
            # its own altitude_m=7000/speed_mps_range=[250,300] (meant for
            # two_circle_headon) merged in ahead of this override, so
            # ObfmScenarioWrapper's scenario.get("altitude_m", OBFM_ALTITUDE_M)
            # was silently finding THAT leftover key instead of falling back --
            # obfm_offensive had been training at 7000m/uncontrolled speed
            # instead of the confirmed real preset (4572m/200 m/s) this whole
            # time. Found 2026-07-16 while adding habfm_beam_merge.
            "initial_scenario": {
                "mode": "obfm",
                "role": role,
                "altitude_m": OBFM_ALTITUDE_M,
                "speed_mps": OBFM_SPEED_MPS,
            },
        },
    )


def _build_two_circle_v4(start_index: int) -> list[CurriculumStage]:
    """9-alpha ladder (builtin ships 10, v4 cut it to 5, 2026-08-05 re-added 4 low
    alphas) with a widened shaping gradient so spawn separation falls inside
    pursuit_range_m -- geometry_guard intentionally omitted, see the module
    docstring's KNOWN GAP note.

    LOW-ALPHA STAGES (3/5/8/12 deg), added 2026-08-05, closing BFM_REFERENCE.md
    Sec10's open question "does the spawn generator vary lateral offset, or only
    alpha_deg?". Answer: it CANNOT vary it independently. single_agent_env.py's
    _apply_two_circle_headon_initial_scenario() gives both aircraft the SAME
    init_e (=center_e) and exactly antiparallel headings (side*alpha vs
    180+side*alpha), so the perpendicular distance between the two flight paths
    collapses to a value fully determined by alpha:

        lateral_offset = separation_m * sin(alpha)
        separation_m   = (2*turn_diameter_ft*sin(alpha) + jitter_ft) * 0.3048

    There is no per-aircraft East knob, and src/dogfight is a hard no-edit
    boundary, so lateral offset can only be reached THROUGH alpha. That matters
    because doctrine's decision threshold is lateral spacing, not alpha:
    BFM_REFERENCE.md Sec7 quotes "lateral spacing greater than 500 feet will give
    the edge to the fighter that turned two-circle" -- i.e. ~152 m. The old
    (0,45,90,135,180) ladder sampled lateral offset at 0 m, then 2476-3122 m,
    then 4572-5486 m: it jumped from a perfect zero-offset head-on straight to
    16-20x past the threshold, so the one-circle/two-circle discrimination was
    never actually presented as a decision. (The builtin's 10-alpha ladder does
    not fix this either -- its alpha=20 stage is already 740-1053 m.)

    These four alphas bracket the 152 m threshold at realistic ranges:

        alpha   spawn range      lateral offset
          3 deg  1106-2020 m       58-106 m   (one-circle favored)
          5 deg  1233-2148 m      107-187 m   (STRADDLES 152 m)
          8 deg  1423-2338 m      198-325 m   (just above)
         12 deg  1675-2589 m      348-538 m   (two-circle favored)

    HIGH ALPHAS REMOVED 2026-08-11. The ladder was (0, 3, 5, 8, 12, 45, 90, 135,
    180); it is now (0, 3, 5, 8, 12), and the four high alphas are replaced by
    _build_match_base_ladder() -- the OFFICIAL geometry. Reason: 45/90/135/180
    spawn at roughly 3500-5486 m, which no competition round presents. The real
    prelim and rounds 1-3 are an antiparallel BEAM merge at 609.6-914.4 m
    (COMPETITION_RULES.md Sec5.1), and the round-4 tie-break is a head-on at
    3048 m -- covered by alpha=0's 914-1829 m and by habfm_beam_merge, not by a
    4-5 km two-circle setup. The five low alphas are KEPT precisely because of
    the 152 m analysis above: that one-circle/two-circle decision is real BFM
    skill at ranges the match actually produces, and it transfers to any merge.

    Index cost: the ladder went 5 -> 9 (2026-08-05) and back to 5 (2026-08-11),
    with three match_base stages added after it, so the block is 5 + 3 = 8 where
    it was 9. Indices are reassigned by get_stages()'s final enumerate(), so
    nothing here is hardcoded -- but the MEANING of the indices after the first
    two_circle stage has changed. train_curriculum.py's _init_or_load_state()
    setdefaults any index missing from curriculum_state.json (count-agnostic),
    but it canNOT fix an index whose meaning changed under a stage already
    marked completed. **So do not --resume a pre-2026-08-11 run against this
    file; start a fresh tag.** v7 was stopped at index 2 and is void for
    unrelated reasons (F6), so nothing in flight is affected.
    """
    stages = []
    for offset, alpha_deg in enumerate((0, 3, 5, 8, 12)):
        stages.append(
            CurriculumStage(
                index=start_index + offset,
                name=f"two_circle_headon_a{alpha_deg:03d}",
                description=(
                    f"Two-circle head-on curriculum at alpha={alpha_deg} deg "
                    "(v4 5-alpha ladder)."
                ),
                target_mode="behavior_tree",
                # 12000 = 200s @ 60Hz (COMPETITION_RULES.md Sec5 match length).
                # Was 18000 (300s) -- the one v4 stage the 2026-07-16 episode-length
                # correction missed while every sibling (obfm/habfm/full_dogfight)
                # already used 12000; training the tie-break rehearsal at 300s teaches
                # pacing/energy management against the wrong match clock. Fixed 2026-08-01.
                episode_step_limit=12000,
                max_iterations=200,
                checkpoint_interval=10,
                reward_overrides=dict(_TWO_CIRCLE_V4_REWARD_OVERRIDES),
                randomization={"enabled": False},
                advance_conditions={"win_rate_min": 0.70, "crash_rate_max": 0.30},
                advance_window=10,
                env_overrides={
                    "initial_scenario": {
                        "mode": "two_circle_headon",
                        "alpha_deg": float(alpha_deg),
                        # Set EXPLICITLY rather than inherited. These two values are
                        # the only other inputs to the lateral-offset formula in the
                        # docstring above, and DEFAULT_ENV_CONFIG's own
                        # initial_scenario dict is merged in AHEAD of this override --
                        # the same leak that silently trained obfm_offensive at 7000 m
                        # instead of 4572 m for weeks (see _obfm_stage's comment). These
                        # restate today's config.py defaults exactly, so no existing
                        # stage's geometry changes; they just stop a future default
                        # edit from silently moving every alpha's lateral offset.
                        "turn_diameter_ft": 6000.0,
                        "separation_jitter_ft": [3000.0, 6000.0],
                    },
                },
            )
        )
    return stages


# Copies _TWO_CIRCLE_V4_REWARD_OVERRIDES, so it inherits energy_scale too (habfm
# is a neutral merge -- an energy-fight stage by the same logic as two_circle).
_HABFM_REWARD = dict(_TWO_CIRCLE_V4_REWARD_OVERRIDES)

# Same reasoning again: match_base is a neutral merge, so it takes the neutral
# reward shape rather than OBFM's position-dominated one.
_MATCH_REWARD = dict(_TWO_CIRCLE_V4_REWARD_OVERRIDES)


def _build_match_base_ladder(start_index: int) -> list[CurriculumStage]:
    """The OFFICIAL prelim / rounds 1-3 geometry: an antiparallel BEAM merge.

    Added 2026-08-11, replacing two_circle alphas 45/90/135/180. Until now NO
    stage trained the geometry the competition actually opens with. From
    COMPETITION_RULES.md Sec5.1 and student/match_scenario_wrapper.py: both
    aircraft 609.6-914.4 m apart (2000-3000 ft) at 4572 m / 200 m/s, each nose
    90 deg off its LOS to the other -- symmetric, neither side advantaged. The
    wrapper randomizes the baseline heading over the full compass and mirrors
    the side, so nothing overfits an absolute heading.

    Three stages, ending on the real thing:
        match_base_wide   914.4 m fixed  -- most time to read the merge
        match_base_close  609.6 m fixed  -- least time, tightest turn
        match_base        609.6-914.4 m  -- the competition preset, sampled

    EVERY key the wrapper reads is set EXPLICITLY, for the reason _obfm_stage()
    and _habfm_stage() both document at length: DEFAULT_ENV_CONFIG's own
    initial_scenario dict is merged in AHEAD of these overrides, so a leftover
    key silently wins over the wrapper's fallback. That is not hypothetical
    here -- config.py's initial_scenario carries altitude_m=7000.0, so omitting
    altitude_m would train this ladder at 7000 m instead of the confirmed
    4572 m, exactly the bug that ran obfm_offensive at the wrong altitude for
    weeks. separation_min_m/separation_max_m/los_deg have no leftover to
    collide with today, but are stated anyway so a future config.py edit cannot
    move this geometry silently.

    NOTE: these stages only do anything because MatchScenarioWrapper is wired
    into train_curriculum.env_creator() (2026-08-11, COMPETITION_PLAN.md 4.1
    F8). Before that it was applied in the eval scripts only, and a stage asking
    for match_base would have trained the DEFAULT spawn while claiming this
    geometry. If that wiring is ever reverted, these stages go silently wrong
    rather than failing -- single_agent_env.py has no branch for this mode.
    """
    specs = (
        ("match_base_wide", 914.4, 914.4,
         "Beam merge at the far edge of the band (3000 ft) -- most time to read the merge."),
        ("match_base_close", 609.6, 609.6,
         "Beam merge at the near edge of the band (2000 ft) -- least time, tightest turn."),
        ("match_base", MATCH_SEPARATION_MIN_M, MATCH_SEPARATION_MAX_M,
         "The official prelim / rounds 1-3 preset: beam merge sampled across 2000-3000 ft."),
    )
    stages = []
    for offset, (name, sep_min, sep_max, description) in enumerate(specs):
        stages.append(
            CurriculumStage(
                index=start_index + offset,
                name=name,
                description=description,
                target_mode="behavior_tree",
                # 12000 = 200s @ 60Hz -- COMPETITION_RULES.md Sec5 match length.
                episode_step_limit=12000,
                max_iterations=200,
                checkpoint_interval=10,
                reward_overrides=dict(_MATCH_REWARD),
                randomization={"enabled": False},
                # Mirrors the neutral-merge siblings (two_circle, habfm): this is a
                # symmetric geometry, not an advantage/disadvantage split like OBFM.
                advance_conditions={"win_rate_min": 0.70, "crash_rate_max": 0.30},
                advance_window=10,
                env_overrides={
                    "initial_scenario": {
                        "mode": "match_base",
                        "separation_min_m": sep_min,
                        "separation_max_m": sep_max,
                        "los_deg": MATCH_LOS_DEG,
                        "altitude_m": MATCH_ALTITUDE_M,
                        "speed_mps": MATCH_SPEED_MPS,
                    },
                },
            )
        )
    return stages


def _habfm_stage() -> CurriculumStage:
    """Beam/high-aspect merge: ~496 m separation, ~91 deg LOS off BOTH
    aircraft's nose (symmetric -- unlike OBFM's asymmetric 4.6/175.4 deg,
    neither side starts with an advantage here). One of the four confirmed
    real competition starting geometries (see
    memory/project_bt_headon_merge_fix_2026_07_16.md); previously untrained
    -- closest existing coverage was full_dogfight's fully randomized spawn,
    which might produce something similar by chance but nothing deliberately
    trained it. Reward/advance thresholds mirror the two-circle ladder
    (neutral geometry, not an advantage/disadvantage split like OBFM).
    """
    return CurriculumStage(
        index=0,
        name="habfm_beam_merge",
        description=(
            "Beam/high-aspect merge: ~496 m separation, ~91 deg LOS off both "
            "aircraft's own nose -- symmetric, neither side starts ahead."
        ),
        target_mode="behavior_tree",
        episode_step_limit=12000,   # 200s @ 60Hz -- COMPETITION_RULES.md match length
        max_iterations=200,
        checkpoint_interval=10,
        reward_overrides=_HABFM_REWARD,
        randomization={"enabled": False},
        advance_conditions={"win_rate_min": 0.70, "crash_rate_max": 0.30},
        advance_window=10,
        env_overrides={
            # altitude_m/speed_mps/alpha_deg set explicitly -- see _obfm_stage()'s
            # comment for the altitude_m/speed_mps hazard. alpha_deg has the same
            # problem in a more severe form: DEFAULT_ENV_CONFIG's initial_scenario
            # leftover alpha_deg=0.0 (meant for two_circle_headon) was silently
            # winning over HabfmScenarioWrapper's own alpha_deg default, zeroing
            # out the entire LOS offset -- own_heading pointed dead at the
            # target (LOS=0) instead of the intended ~91 deg. Caught by an
            # explicit position/heading verification (env_creator + reset),
            # not by the earlier OBFM-style distance-only check.
            "initial_scenario": {
                "mode": "habfm",
                "alpha_deg": HABFM_LOS_DEG,
                "altitude_m": HABFM_ALTITUDE_M,
                "speed_mps": HABFM_SPEED_MPS,
            },
        },
    )


def get_stages() -> list[CurriculumStage]:
    base = list(_builtin_get_stages())

    # Fix a latent builtin crash: stage 0 flight_survival ships
    # randomization={"enabled": True, "radius": 0.0, ...}, so the env's
    # add_random_init_position() calls np_random.integers(0, radius) and raises
    # "high <= 0" on the very first reset (never hit before -- no full training
    # run had reached it). radius=1.0 keeps the intended zero position offset
    # (integers(0, 1) always returns 0) while being a valid bound. src/ is
    # no-edit, so patch the base stage list here.
    base = [
        replace(s, randomization={**s.randomization, "radius": 1.0})
        if s.randomization.get("enabled") and float(s.randomization.get("radius", 0)) <= 0.0
        else s
        for s in base
    ]

    # Fix the autopilot target's altitude SIGN. FighterSim.step_autopilot() documents
    # altitude_cmd as "meter (NED, Down direction +)" and computes
    # `-altitude_cmd * METER_TO_FEET`, so commanding 7000 m of ALTITUDE requires passing
    # -7000. src/dogfight/config.py's default is +7000.0, which resolves to -22966 ft: an
    # order to fly far BELOW sea level.
    #
    # Measured 2026-08-06 (A/B in scripts/eval_v5_vs_bt.py, bt ownship vs autopilot target,
    # OBFM geometry, identical seed):
    #     altitude_cmd=+7000 -> target descends ~120 m/s from 4572 m, hits the 300 m floor,
    #                           episode ends at ~24 s on "target altitude below min"
    #     altitude_cmd=-7000 -> target climbs to the setpoint and holds the full 200 s
    #
    # So stage 3, whose own description is "pursue a moving target with fixed heading,
    # ALTITUDE, and speed", has been training against a target power-diving into the ground.
    # That is the shape of the documented v4 stage-3 outcome (100% crash rate, min-distance
    # 4.8 km "approach failure") which had been read as RL instability / idle-throttle stall.
    # Applies to any autopilot-target stage, not just index 3, so a reordered curriculum keeps
    # the fix. Only altitude_cmd is overridden -- curriculum.py::_deep_update merges nested
    # dicts recursively, so heading_cmd/speed_cmd keep whatever the stage or base config set.
    # src/ is no-edit, so patch the base stage list here (same idiom as the radius fix above).
    base = [
        replace(s, env_overrides={
            **s.env_overrides,
            "target_autopilot": {
                **s.env_overrides.get("target_autopilot", {}),
                "altitude_cmd": -abs(float(
                    s.env_overrides.get("target_autopilot", {}).get("altitude_cmd", 7000.0)
                )),
            },
        })
        if s.target_mode == "autopilot" else s
        for s in base
    ]

    obfm_stages = [
        _obfm_stage(
            name="obfm_offensive",
            description=(
                "Offensive BFM: start ~556 m behind the BT opponent, on its six "
                "(LOS ~5 deg) -- convert the advantage into WEZ contact / a kill."
            ),
            role="offensive",
            reward=_OBFM_OFFENSIVE_REWARD,
            advance={"win_rate_min": 0.5, "crash_rate_max": 0.3},
        ),
        _obfm_stage(
            name="obfm_defensive",
            description=(
                "Defensive BFM: start ~556 m ahead with the BT opponent on your "
                "six (LOS ~175 deg) -- survive, spoil the shot, force an overshoot."
            ),
            role="defensive",
            reward=_OBFM_DEFENSIVE_REWARD,
            advance={"loss_rate_max": 0.4, "crash_rate_max": 0.3},
        ),
    ]

    insert_at = next(
        (i + 1 for i, s in enumerate(base) if s.name == "autopilot_pursuit"), None
    )
    if insert_at is None:
        insert_at = next(
            (i for i, s in enumerate(base) if s.target_mode == "behavior_tree"),
            len(base),
        )

    neutral_head = base[:insert_at]
    tail = base[insert_at:]

    # v4: drop the builtin's 10-alpha two-circle ladder + its full_dogfight, replace with
    # the 5-alpha rebuild (0/3/5/8/12 -- see _build_two_circle_v4's docstring for why the
    # high alphas were dropped again on 2026-08-11), the match_base ladder, and a
    # full_dogfight extended to 1500 iters.
    old_full_dogfight = next((s for s in tail if s.name == "full_dogfight"), None)
    tail = [
        s
        for s in tail
        if not s.name.startswith("two_circle_headon_a") and s.name != "full_dogfight"
    ]

    two_circle_v4 = _build_two_circle_v4(start_index=0)  # reindexed below

    if old_full_dogfight is not None:
        # episode_step_limit=12000 (200s @ 60Hz): the builtin stage's 18000 (300s)
        # doesn't match COMPETITION_RULES.md Sec5's actual 200s match length -- found
        # 2026-07-16 while auditing competition-readiness, confirmed not yet trained
        # against (v4 is stalled at stage 4/12, obfm_offensive), fixed here rather than
        # left for whenever training reaches this stage.
        # reward_overrides: the builtin's is {} (pure base config, energy_scale 0).
        # Enable the energy term here (neutral full engagement -- energy fighting
        # decides it), keeping every other base value by merging just this one key.
        full_dogfight_v4 = replace(
            old_full_dogfight,
            max_iterations=1500,
            episode_step_limit=12000,
            reward_overrides={**old_full_dogfight.reward_overrides, "energy_scale": _ENERGY_SCALE},
        )
    else:
        full_dogfight_v4 = CurriculumStage(
            index=0,
            name="full_dogfight",
            description="Full engagement against active behavior-tree opponent.",
            target_mode="behavior_tree",
            episode_step_limit=12000,
            max_iterations=1500,
            checkpoint_interval=10,
            reward_overrides={"energy_scale": _ENERGY_SCALE},
            randomization={
                "enabled": True,
                "radius": 2000.0,
                "r_roll": 15.0,
                "r_pitch": 10.0,
                "r_heading": 180.0,
            },
            advance_conditions={},
        )

    # match_base ladder (2026-08-11) sits between the two-circle block and the fully
    # randomized full_dogfight: specific -> general. It is the only block that trains the
    # geometry the competition actually opens with, and it goes LAST among the fixed
    # geometries so the policy arrives at full_dogfight having most recently practised it.
    match_base_stages = _build_match_base_ladder(start_index=0)  # reindexed below

    merged = (
        neutral_head
        + obfm_stages
        + [_habfm_stage()]
        + tail
        + two_circle_v4
        + match_base_stages
        + [full_dogfight_v4]
    )
    return [replace(stage, index=i) for i, stage in enumerate(merged)]


__all__ = ["get_stages"]
