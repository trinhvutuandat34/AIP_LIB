# -*- coding: utf-8 -*-
"""v11 residual-training curriculum: same stages as student.my_curriculum, damage_scale raised
on the match-relevant stages only (2026-08-19, 4.1 F34/F35).

WHY THIS EXISTS. v9 (residual_scale=0.35) trained a policy that actively destroyed itself --
27% self-crash at its own composition. v10 (residual_scale=0.10) fixed that completely (0
self-crashes) but the resulting policy achieved ZERO WEZ contact across 30 evaluation episodes,
against the unmodified BT's 967 -- it survives by contributing nothing, not by contributing
usefully. Two systematic attempts now bracket "too much authority" and "no incentive to use
what authority it has" without ever finding a middle that helps.

THE HYPOTHESIS THIS TESTS (not a re-derivation of F31 -- a different mechanism). Read
student/my_reward.py's compute_reward(): `pursuit` (ATA x range) and `position` (aspect x
range) are DENSE per-step shaping terms computed purely from resulting geometry -- they pay out
whenever the aircraft happens to be positioned well, with NO dependency on whether the residual
did anything to get there. Since the unmodified BT already achieves decent geometry on its own
(967 WEZ-contact steps out of ~theta), a policy that perturbs nothing can still collect most of
that shaping reward for free, while risking crash-penalty exposure for any authority it actually
uses. `damage_scale` (the WEZ-phase damage estimate term) is the one component that specifically
requires converting a position, not just holding one -- and unlike pursuit_scale/position_scale
(already dialed 0.3->0.2 for these stages, see _TWO_CIRCLE_V4_REWARD_OVERRIDES) and advantage_
scale (already turned on at 0.1 for exactly this reason), damage_scale was NEVER adjusted for
residual training. It sits at the same 20.0 default used by every non-residual campaign.

THE CHANGE: damage_scale 20.0 -> 60.0 (3x), on stages 6-15 ONLY -- habfm_beam_merge through
full_dogfight, i.e. every stage that inherits _TWO_CIRCLE_V4_REWARD_OVERRIDES and therefore
already has pursuit/position dialed back and advantage_scale enabled. Stages 0-5
(flight_survival through obfm_defensive) are left BYTE-IDENTICAL to student.my_curriculum --
those stages train flight and basic tracking, not conversion, and both v9 and v10 got through
them without incident, so there is no reason to touch what already works. residual_scale stays
at 0.10 (v10's proven-stable value, unchanged) -- this experiment changes ONE variable
(damage_scale) relative to v10, exactly as v10 changed one variable (residual_scale) relative to
v9, per this project's own standing discipline (4.1 F26-RULE) of never testing two things at once.

HOW THIS IS IMPLEMENTED: calls the canonical student.my_curriculum.get_stages() (so any future
edit to the base curriculum, e.g. a new stage or a budget change, is inherited automatically
rather than silently diverging) and uses dataclasses.replace() on exactly the targeted stages'
reward_overrides -- CurriculumStage is an ordinary (non-frozen) dataclass, but replace() is used
rather than in-place mutation to avoid aliasing the base module's dict objects across imports,
matching the idiom student/my_curriculum.py itself already uses for full_dogfight_v4.

CONFIDENCE, STATED HONESTLY: this is a reasoned hypothesis built from reading the actual reward
code, not a re-test of an existing measurement the way v10's scale change was (D3-REBASED had
already shown the 0.10/0.35 cliff before v10 ever ran). There is no prior measurement showing
damage_scale=60 helps. If v11 also produces near-zero WEZ contact, that argues the free-rider
explanation is wrong or incomplete, not that the multiplier was too small -- do not simply try a
larger number next without new evidence for why.
"""
from __future__ import annotations

import dataclasses

from student.my_curriculum import get_stages as _get_base_stages

# Stages 6-15: habfm_beam_merge, two_circle_headon_a000..a012 (5), match_base_wide/close/base,
# full_dogfight. All inherit _TWO_CIRCLE_V4_REWARD_OVERRIDES in student/my_curriculum.py.
_MATCH_RELEVANT_STAGE_INDICES = frozenset(range(6, 16))

_NEW_DAMAGE_SCALE = 60.0  # was 20.0 (the MY_REWARD_CONFIG default, never overridden for these
# stages until now)


def get_stages() -> list:
    stages = _get_base_stages()
    out = []
    for s in stages:
        if s.index in _MATCH_RELEVANT_STAGE_INDICES:
            s = dataclasses.replace(
                s, reward_overrides={**s.reward_overrides, "damage_scale": _NEW_DAMAGE_SCALE}
            )
        out.append(s)
    return out


if __name__ == "__main__":
    # Sanity print: exactly stages 6-15 should show 60.0, everything else unchanged from base.
    base = {s.index: s.reward_overrides.get("damage_scale", 20.0) for s in _get_base_stages()}
    new = {s.index: s.reward_overrides.get("damage_scale", 20.0) for s in get_stages()}
    for i in sorted(new):
        flag = " <-- CHANGED" if new[i] != base[i] else ""
        print(f"stage {i:2d}: base={base[i]:5.1f}  v11={new[i]:5.1f}{flag}")
    changed = sorted(i for i in new if new[i] != base[i])
    assert changed == sorted(_MATCH_RELEVANT_STAGE_INDICES), (
        f"expected exactly stages {sorted(_MATCH_RELEVANT_STAGE_INDICES)} to change, got {changed}"
    )
    print("OK: exactly the intended stages changed, nothing else.")
