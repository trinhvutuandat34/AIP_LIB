"""Do the match_base stages actually spawn at the competition geometry? End-to-end, real envs.

WHY SEPARATE FROM verify_report_fixes.py. That script's checks are fast and pure-Python; this one
builds real environments through train_curriculum.env_creator() and resets them, which loads
JSBSimAIPLib.dll and takes a minute. It is also the only check that can catch the specific failure
this guards against, because that failure is SILENT: single_agent_env.py has no branch for
initial_scenario.mode "match_base", so before MatchScenarioWrapper was wired into env_creator
(2026-08-11, COMPETITION_PLAN.md 4.1 F8) a stage requesting it would not have errored -- it would
have trained the DEFAULT spawn while its name, its YAML and every log line claimed the match
geometry. Config-level assertions cannot see that; only a real reset can.

It also re-proves the merge trap concretely (4.1 F8-STAGES): DEFAULT_ENV_CONFIG's initial_scenario
carries altitude_m=7000.0 and is merged in AHEAD of a stage's overrides, which is the bug that ran
obfm_offensive at the wrong altitude for weeks and zeroed habfm's LOS. Watch the JSBSim init line
in the output report 7000 m and the measured spawn come back 4572 m -- that is the override
winning where it matters.

    python scripts/verify_match_spawn.py

Exit code 0 = all checks pass. Run before committing compute to a campaign.
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np

import train_curriculum as tc
from dogfight.ai.curriculum import build_stage_env_config
from dogfight.config import DEFAULT_ENV_CONFIG
from dogfight.sim.state_schema import StateIndex
from student.match_scenario_wrapper import (
    MATCH_ALTITUDE_M, MATCH_SEPARATION_MAX_M, MATCH_SEPARATION_MIN_M,
)
from student.my_curriculum import get_stages

_FAILED: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    if not cond:
        _FAILED.append(label)


def _base_config() -> dict:
    cfg = dict(DEFAULT_ENV_CONFIG)
    cfg.update({
        "observation_mode": "custom",
        "observation_module": "student.my_observation_v2",
        "reward_module": "student.my_reward",
        "target_mode": "behavior_tree",
        "target_behavior_dll": "AIP_BASE_target.dll",
    })
    return cfg


def _spawn_of(stage, base) -> tuple[float, float, float]:
    """Build the stage's real env, reset it, and return (separation_m, own_alt, tgt_alt)."""
    env = tc.env_creator(dict(build_stage_env_config(base, stage)))
    try:
        env.reset(seed=0)
        b = env.unwrapped
        own, tgt = b._ownship_state, b._target_state
        sep = float(np.linalg.norm([own[StateIndex.N] - tgt[StateIndex.N],
                                    own[StateIndex.E] - tgt[StateIndex.E]]))
        return sep, -float(own[StateIndex.D]), -float(tgt[StateIndex.D])
    finally:
        try:
            env.close()
        except Exception:
            pass


def main() -> int:
    print("=" * 88)
    print("match_base spawn geometry -- end to end through the real env")
    print("=" * 88)
    base = _base_config()
    stages = {s.name: s for s in get_stages()}
    print(f"\n  curriculum has {len(stages)} stages")

    for name in ("match_base_wide", "match_base_close", "match_base"):
        stage = stages.get(name)
        if stage is None:
            check(f"{name} exists in the curriculum", False)
            continue
        print(f"\n--- {name} (index {stage.index}) ---")
        sep, alt_own, alt_tgt = _spawn_of(stage, base)
        print(f"      measured spawn: separation {sep:.1f} m | "
              f"alt own {alt_own:.0f} m, target {alt_tgt:.0f} m")

        sc = stage.env_overrides["initial_scenario"]
        lo, hi = sc["separation_min_m"], sc["separation_max_m"]
        check(f"separation {sep:.1f} m inside this stage's band [{lo}, {hi}]",
              lo - 1.0 <= sep <= hi + 1.0)
        check(f"separation inside the competition band "
              f"[{MATCH_SEPARATION_MIN_M}, {MATCH_SEPARATION_MAX_M}]",
              MATCH_SEPARATION_MIN_M - 1.0 <= sep <= MATCH_SEPARATION_MAX_M + 1.0)
        check(f"altitude {alt_own:.0f} m is {MATCH_ALTITUDE_M} -- NOT config.py's 7000 m leak",
              abs(alt_own - MATCH_ALTITUDE_M) < 50.0)
        check("both aircraft level with each other", abs(alt_own - alt_tgt) < 50.0)

    # Control: the wrapper must remain a no-op for a stage that does not ask for it. Without this
    # the checks above would still pass if the wrapper repositioned EVERYTHING.
    print("\n--- control: two_circle_headon_a000 must be untouched ---")
    ctrl = stages.get("two_circle_headon_a000")
    if ctrl is None:
        check("two_circle_headon_a000 exists", False)
    else:
        sep, _, _ = _spawn_of(ctrl, base)
        print(f"      measured spawn: separation {sep:.1f} m")
        check(f"two-circle spawn {sep:.1f} m is OUTSIDE the match band "
              f"(wrapper stayed a no-op)",
              not (MATCH_SEPARATION_MIN_M <= sep <= MATCH_SEPARATION_MAX_M))

    print("\n" + "=" * 88)
    if _FAILED:
        print(f"{len(_FAILED)} CHECK(S) FAILED:")
        for f in _FAILED:
            print(f"  - {f}")
        print("A stage may be training a geometry other than the one it names. Do not launch.")
        return 1
    print("All checks passed -- the match_base stages spawn at the competition geometry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
