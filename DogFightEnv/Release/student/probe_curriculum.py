"""A 15-iteration stage-0-only curriculum, used only to prove out training telemetry.

Not a training curriculum. Its whole job is to run the real `train_curriculum.py` code path --
same env, same callbacks, same CSV writer -- for long enough to answer one question cheaply:
do the per-episode metrics (`crash_rate`, `ep_wez_steps`, `cb_fired`, ...) actually reach
`artifacts/curriculum/real_eagle/v7_probe/training_log.csv`?

They did not for either v5 or v6: 0 rows out of 4,700 in each. See student/my_callbacks.py.

Stage 0 (`flight_survival`) is deliberate -- it has the curriculum's shortest episodes.

SIZING, and why the first attempt proved nothing (2026-08-06). The probe first ran 15 iterations
against stage 0's stock `episode_step_limit=3600`. At the measured 100 env steps/iteration that
is ~36 iterations per episode, so the run collected 1,581 env steps and closed **zero** episodes
-- every metric read `n/a` for the trivial reason that no episode ever ended, which is
indistinguishable from the bug being probed. `episode_step_limit` is therefore overridden to 300
frames (5 s of sim): an episode closes roughly every 3 iterations, so a 25-iteration probe sees
~8 of them. The episodes are meaningless as training -- they only have to END, which is the one
thing `on_episode_end` needs.
"""

from __future__ import annotations

from dataclasses import replace

from dogfight.ai.curriculum import CurriculumStage
from student.my_curriculum import get_stages as _real_get_stages

PROBE_ITERATIONS = 25
PROBE_EPISODE_STEP_LIMIT = 300   # 5 s of sim -- ~1 episode per 3 iterations


def get_stages() -> list[CurriculumStage]:
    stages = _real_get_stages()
    stage0 = stages[0]
    # Keep every other property of the real stage 0 (including my_curriculum.py's radius fix
    # for the add_random_init_position crash) so the probe exercises the real configuration.
    return [
        replace(
            stage0,
            max_iterations=PROBE_ITERATIONS,
            episode_step_limit=PROBE_EPISODE_STEP_LIMIT,
        )
    ]
