"""Episode-metric callbacks that actually reach the training CSV.

WHY. Across v6's 4,700 iterations and v5's 4,700 iterations, `crash_rate`, `win_rate`,
`ep_wez_steps` and `ep_altitude_penalty_steps` were logged **0 times** -- not rarely, never.
v4 logged them in 557/1,901 rows, so this is a regression, not a long-standing gap. Two full
campaigns therefore trained blind: v6's headline change (the dense altitude-floor term, added
specifically to fix v5's 100% self-crash) had no observable signal at all, and the curriculum's
`advance_conditions` gates stayed inert so every stage advanced on `max_iterations`.

Meanwhile RLlib's own `episode_return_mean` still appeared in ~3.5% of rows, which is the tell:
the learner and the env are fine, it is specifically the per-episode metrics *this project*
computes that never arrive.

ROOT CAUSE -- and it is NOT in this file. `train_curriculum.py::_extract_custom_metrics` looked
every metric up under the `_mean` suffix (`cm.get("crash_mean")`), which is the OLD RLlib API
stack's convention: `episode.custom_metrics[k] = v` was auto-aggregated into `k_mean`/`k_min`/
`k_max`. On Ray 2.54's NEW stack `SingleAgentEpisode` has no `custom_metrics` attribute at all,
so the platform callback falls to `metrics_logger.log_value(("custom_metrics", k), reduce="mean")`
-- which stores the key **bare**. All 21 lookups missed and every row wrote "n/a". Fixed in
`train_curriculum.py::_cm_get`, which accepts both names. v4 predates the stack switch, which is
why its rows were fine.

**RETRACTED (2026-08-06): the two hypotheses this module was originally built on were both
wrong.** They are left visible rather than deleted, per this project's convention:

1. ~~"The terminal info comes back empty, so `on_episode_end` returns early."~~ **False.**
   Measured with `DOGFIGHT_CALLBACK_TRACE` on the probe run: `on_episode_end` fired 9 times for
   9 completed episodes, always with a real `MetricsLogger`, and `cb_empty_info` reads **0.0** in
   every row -- `_last_info` never once failed. The step-wise info capture below is therefore
   belt-and-braces, not a fix. It costs one dict copy per step and makes the callback robust to a
   future RLlib API change, so it stays.
2. ~~"Logging with an explicit `window=` makes a value persist across iterations where no episode
   closed."~~ **False.** RLlib's EnvRunner reduces and clears its MetricsLogger every sample call,
   so the window never spans iterations -- measured as a strict alternating present/absent pattern
   in the CSV. Persistence had to move to the consumer side instead
   (`train_curriculum.py::_carry_forward`, which also reports `metrics_age_iters` so a carried
   value is never mistaken for a fresh one).

What this module *does* contribute is the diagnosis itself: the `cb_fired` / `cb_empty_info` /
`cb_no_info_at_all` counters. Without them the CSV could not distinguish "callback never ran"
from "callback ran but wrote nowhere" from "no episode ended this iteration" -- and that
ambiguity is precisely what let the bug survive 9,400 iterations across two campaigns.

Boundary: `src/dogfight/**` is untouched (team policy, 2026-07-14). This subclasses the platform
callbacks and is registered from `train_curriculum.py`, an entry script -- the sanctioned route
per CLAUDE.md's boundary table, same idiom as `student/inference_providers.py`.
"""

from __future__ import annotations

import os

from dogfight.ai.callbacks import DogFightCallbacks

# Episodes close ~once per 20-120 iterations at 100 env steps/iter, so the window is in EPISODES,
# not iterations: 20 episodes is a few hundred iterations of persistence. Large enough that the
# CSV always carries a live value, small enough to still track a real behavioural change.
METRIC_WINDOW = 20


class StudentDogFightCallbacks(DogFightCallbacks):
    """`DogFightCallbacks` + terminal-info capture + windowed persistence."""

    # ── Terminal-info capture ─────────────────────────────────────────────
    def on_episode_step(self, *, episode, **kwargs):
        super().on_episode_step(episode=episode, **kwargs)
        # Stash the freshest non-empty info. on_episode_end's own lookup is API-version
        # sensitive; this is read from the same episode object one step earlier, when the
        # terminal info is unambiguously present.
        try:
            info = episode.get_infos(-1)
        except Exception:
            return
        if info:
            self._episode_data(episode)["last_info"] = dict(info)

    # ── Recording ─────────────────────────────────────────────────────────
    def on_episode_end(self, *, episode, metrics_logger=None, **kwargs):
        # Set DOGFIGHT_CALLBACK_TRACE=<path> to prove whether this fires at all and whether a
        # metrics_logger is supplied. The CSV alone cannot distinguish "callback never ran" from
        # "callback ran but had nowhere to write", and that ambiguity is what let the dead
        # telemetry survive 9,400 iterations.
        _trace = os.environ.get("DOGFIGHT_CALLBACK_TRACE")
        if _trace:
            try:
                with open(_trace, "a", encoding="utf-8") as fh:
                    fh.write(
                        f"on_episode_end fired; metrics_logger={type(metrics_logger).__name__}; "
                        f"episode={type(episode).__name__}; kwargs={sorted(kwargs)}\n"
                    )
            except Exception:
                pass

        info = self._last_info(episode)
        used_fallback = False
        if not info:
            info = self._episode_data(episode).get("last_info") or {}
            used_fallback = True

        self._log(metrics_logger, "cb_fired", 1.0)
        self._log(metrics_logger, "cb_empty_info", 1.0 if used_fallback else 0.0)
        if not info:
            # Both sources dry. Emit the marker anyway so this is visible in the CSV rather
            # than looking identical to "no episode ended this iteration".
            self._log(metrics_logger, "cb_no_info_at_all", 1.0)
            return

        super().on_episode_end(episode=episode, metrics_logger=metrics_logger, **kwargs)

    # ── Helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _log(metrics_logger, key: str, value: float) -> None:
        if metrics_logger is None:
            return
        try:
            metrics_logger.log_value(
                ("custom_metrics", key), float(value), reduce="mean", window=METRIC_WINDOW
            )
        except Exception:
            pass

    @staticmethod
    def _record_metric(episode, metrics_logger, key: str, value: float) -> None:
        """Override: same contract as the base, but windowed so the value survives the many
        iterations in which no episode closes. The base class logs with no window, so a value
        reduced in one iteration is not carried into the next -- which is why even correctly
        recorded metrics would still have read `n/a` in ~95% of rows."""
        if hasattr(episode, "custom_metrics"):
            episode.custom_metrics[key] = value
            return
        if metrics_logger is None:
            return
        try:
            metrics_logger.log_value(
                ("custom_metrics", key), float(value), reduce="mean", window=METRIC_WINDOW
            )
        except Exception:
            pass
