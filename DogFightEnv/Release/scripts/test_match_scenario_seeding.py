"""Self-check for the two 2026-09-08 spawn-reproducibility fixes in match_scenario_wrapper.py.

    python scripts/test_match_scenario_seeding.py

No framework, no fixtures -- asserts against a stub env, so it runs in under a second and needs
neither JSBSim nor a DLL. Both checks fail loudly against the pre-fix code, which is the point:

  1. SPAWN DETERMINISM. reset(seed=S) must produce the same spawn no matter how many episodes
     ran before it. Pre-fix, apply_match_scenario() drew from base.np_random BEFORE
     env.reset(seed=S) ever seeded it, so the spawn depended on the previous episode's leftover
     RNG state -- and the first episode of every process drew from OS entropy. Measured across
     the 15 same-seed F66 CSVs: 54 of 150 episode indices had 15 different spawn tuples.

  2. BAND PARSING. A non-empty but malformed band must RAISE, not silently disable
     randomisation. league.py sets these on every child process, so one typo would have turned a
     whole 15-pair matrix into fixed-spawn episodes that look identical to randomised ones.
"""
from __future__ import annotations

import sys
from pathlib import Path

import gymnasium as gym
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from student.match_scenario_wrapper import MatchScenarioWrapper, _parse_band  # noqa: E402


class _StubEnv(gym.Env):
    """Minimal stand-in: records change_init_position() calls and, like the real env, consumes
    RNG draws during reset() so leftover-state contamination is reproducible."""

    def __init__(self, mode="match_base"):
        self.config = {"initial_scenario": {
            "mode": mode,
            "altitude_range_m": (1000.0, 7700.0),
            "speed_range_mps": (150.0, 280.0),
        }}
        self.spawns: list[tuple] = []
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (1,), dtype=np.float32)
        self.action_space = gym.spaces.Box(-1.0, 1.0, (1,), dtype=np.float32)

    def change_init_position(self, who, **kw):
        self.spawns.append((who, round(kw["init_n"], 6), round(kw["init_e"], 6),
                            round(kw["init_d"], 6), round(kw["init_heading"], 6),
                            round(kw["init_speed"], 6)))

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.np_random.uniform(size=5)   # the real env randomises during reset too
        return np.zeros(1, dtype=np.float32), {}

    def step(self, action):
        return np.zeros(1, dtype=np.float32), 0.0, True, False, {}


def _spawn_at(seed: int, history: list[int]) -> list[tuple]:
    """Spawn produced by reset(seed=seed) after replaying `history` episodes first."""
    env = _StubEnv()
    wrapped = MatchScenarioWrapper(env)
    for s in history:
        wrapped.reset(seed=s)
    env.spawns.clear()
    wrapped.reset(seed=seed)
    return list(env.spawns)


def main() -> None:
    # 1. Same seed, different history -> identical spawn.
    fresh = _spawn_at(7, [])
    assert fresh, "stub recorded no spawn -- wrapper did not apply the scenario"
    for history in ([1], [1, 2, 3], [9, 9, 9, 9, 9]):
        got = _spawn_at(7, history)
        assert got == fresh, (
            f"spawn for seed=7 depends on episode history {history}:\n"
            f"  fresh   {fresh}\n  after   {got}\n"
            "match_scenario_wrapper.reset() is drawing before it seeds."
        )

    # ...and different seeds still give different spawns (guards against seeding it to a constant).
    assert _spawn_at(8, []) != fresh, "seed is being ignored -- every episode spawns identically"

    # 2. Band parsing fails loudly instead of silently disabling randomisation.
    assert _parse_band("") is None
    assert _parse_band("1000,7700") == (1000.0, 7700.0)
    for bad in ("1000", "1000,", "abc,7700", "7700,1000", "500,500"):
        try:
            _parse_band(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"_parse_band({bad!r}) returned instead of raising -- "
                                 "a typo would silently disable randomisation")

    # 3. Separation must be the three DISCRETE competition values, equally weighted.
    #    COMPETITION_RULES Sec 5.1 cycles start separation with the game index:
    #    2,000 -> 2,500 -> 3,000 ft. Before 2026-09-08 the eval derived it from the alpha
    #    schedule as a smooth sweep, and because that schedule contains both 0 and 180 (which
    #    map to the same fraction) it produced nine values of which only 609.6 m was a real game
    #    distance -- double-weighted -- while 2,500 ft and 3,000 ft NEVER occurred. Two of every
    #    three games in a BO3 were being flown at separations we had never evaluated.
    from student.match_scenario_wrapper import MATCH_SEPARATION_SET_M as SEPS  # noqa: E402

    assert SEPS == (609.6, 762.0, 914.4), f"separation set drifted: {SEPS}"
    assigned = [SEPS[e % len(SEPS)] for e in range(120)]
    counts = {s: assigned.count(s) for s in SEPS}
    assert set(counts.values()) == {40}, f"separations are not equally weighted: {counts}"
    for ft, m in ((2000, 609.6), (2500, 762.0), (3000, 914.4)):
        assert m in assigned, f"{ft} ft ({m} m) is a real game separation and is never sampled"

    print("OK: spawn is a pure function of the seed; malformed bands raise; "
          "separation covers 2000/2500/3000 ft equally.")


if __name__ == "__main__":
    main()
