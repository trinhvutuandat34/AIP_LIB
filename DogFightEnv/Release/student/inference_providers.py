# -*- coding: utf-8 -*-
"""Inference-time provider helpers that live OUTSIDE the common platform.

`src/dogfight/**` is a hard no-edit boundary (team policy, see CLAUDE.md's editing
table). The inference-time fixes that would otherwise have gone into
`src/dogfight/ai/{action_provider,rl_action_provider,hybrid_action_provider,checkpoint_io}.py`
are re-homed here instead, in the editable student surface.

Nothing here EDITS the platform: `RemappedRLProvider` *subclasses* the stock
`RLActionProvider` (reuse, not modification) and `StudentHybridProvider` composes
stock providers. Both are wired in from the entry scripts
(`run_unreal_inference.py`, `run_local_dogfight.py`, `my_submission.py`).

What this fixes:
  1. Throttle remap. The policy's action space is [-1,1]^4; the sim expects
     throttle in [0,1]. Training applies (throttle+1)/2 in
     single_agent_env.py::_to_sim_action, but the stock RLActionProvider does
     not -- it clips throttle to [0,1], FLOORING every negative raw output to 0
     (engine idle) and halving the usable throttle range. The remap has to
     happen BEFORE that clip, so a wrapper around the provider can't do it
     (it only sees post-clip output). A subclass calling the inherited,
     pre-clip _compute_module_action() can. That's RemappedRLProvider.
  2. Hybrid residual throttle. Stock residual is secondary + scale*primary.
     With primary throttle re-mapped to [0,1] (neutral 0.5), a plain add can
     only ever RAISE throttle above BT's baseline, never lower it -- so it
     fights BT maneuvers that deliberately throttle down (Task_LagPursuit=0.6,
     YoYo/BarrelRoll completion phases). StudentHybridProvider re-centers the
     throttle residual to [-1,1] so RL can pull throttle down too.
  3. Switch mode. Stock HybridActionProvider's switch branch falls back to
     "primary" when no selector is passed, and no call site ever passed one --
     so --hybrid-mode switch silently ran 100% RL. StudentHybridProvider uses
     switch_by_range as an explicit, observable default (annotated in info).
"""
from __future__ import annotations

from typing import Callable

import numpy as np

from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult, clip_action
from dogfight.ai.rl_action_provider import RLActionProvider


DEFAULT_SWITCH_CLOSE_RANGE_M = 2000.0


def remap_policy_throttle(action) -> np.ndarray:
    """Undo training's [-1,1] throttle convention (mirrors single_agent_env.py::_to_sim_action)."""
    action_array = np.array(action, dtype=np.float32, copy=True)
    action_array[3] = (action_array[3] + 1.0) / 2.0
    return action_array


class RemappedRLProvider(RLActionProvider):
    """RLActionProvider with the training-time throttle remap restored at inference.

    Overrides compute_action to run the inherited (pre-clip) _compute_module_action,
    apply the throttle remap, THEN clip -- the ordering the stock class can't give us
    because its clip floors throttle before any caller can see the raw output.
    """

    def compute_action(self, context: ActionContext) -> ActionResult:
        observation = context.observation
        if observation is None:
            if self.obs_builder is None:
                raise ValueError("observation is required when obs_builder is not configured")
            observation = self.obs_builder(context)

        action = self._compute_module_action(observation)   # raw [-1,1], pre-clip
        action = remap_policy_throttle(action)              # throttle (x+1)/2 BEFORE clip
        action = clip_action(action)

        return ActionResult(
            action=action,
            source="rl",
            confidence=self.confidence,
            info={"policy_id": self.policy_id, "explore": self.explore, "throttle_remapped": True},
        )


def _context_distance_m(context: ActionContext) -> float | None:
    own = getattr(context, "ownship_state", None)
    tgt = getattr(context, "target_state", None)
    if own is None or tgt is None:
        return None
    own = np.asarray(own, dtype=np.float64)
    tgt = np.asarray(tgt, dtype=np.float64)
    if own.shape[0] < 3 or tgt.shape[0] < 3:
        return None
    return float(np.linalg.norm(tgt[:3] - own[:3]))


def switch_by_range(
    context: ActionContext,
    primary_result: ActionResult,
    secondary_result: ActionResult,
    close_range_m: float = DEFAULT_SWITCH_CLOSE_RANGE_M,
) -> str:
    """Default switch selector: BT inside close_range_m, RL beyond it.

    A tunable heuristic, not a proven tactic: the native BT's BFM maneuvers are
    strongest in the close-in knife-fight; RL handles the longer approach/positioning
    phase. Falls back to BT (the reliable baseline) when range is unavailable, rather
    than silently defaulting to RL the way the stock class did.
    """
    distance = _context_distance_m(context)
    if distance is None:
        return "secondary"
    return "secondary" if distance <= close_range_m else "primary"


class StudentHybridProvider(ActionProvider):
    """Hybrid RL+BT composition with throttle-aware residual and a working switch mode.

    Expects `primary_provider` to be a RemappedRLProvider (throttle already in [0,1],
    neutral 0.5) and `secondary_provider` to be a BTActionProvider (throttle in [0,1]).
    """

    def __init__(
        self,
        primary_provider: ActionProvider,
        secondary_provider: ActionProvider,
        mode: str = "residual",
        alpha: float = 0.5,
        residual_scale: float = 0.35,
        selector: Callable[[ActionContext, ActionResult, ActionResult], str | bool] | None = None,
        close_range_m: float = DEFAULT_SWITCH_CLOSE_RANGE_M,
        confidence: float = 0.95,
    ):
        self.primary_provider = primary_provider
        self.secondary_provider = secondary_provider
        self.mode = mode
        self.alpha = alpha
        self.residual_scale = residual_scale
        self.selector = selector
        self.close_range_m = close_range_m
        self.confidence = confidence

    def reset(self, context: ActionContext | None = None) -> None:
        self.primary_provider.reset(context)
        self.secondary_provider.reset(context)

    def compute_action(self, context: ActionContext) -> ActionResult:
        primary_result = self.primary_provider.compute_action(context)
        secondary_result = self.secondary_provider.compute_action(context)

        if self.mode == "switch":
            selector = self.selector or (
                lambda ctx, p, s: switch_by_range(ctx, p, s, self.close_range_m)
            )
            decision = selector(context, primary_result, secondary_result)
            use_primary = decision if isinstance(decision, bool) else decision != "secondary"
            chosen = primary_result if use_primary else secondary_result
            return ActionResult(
                action=clip_action(chosen.action),
                source="hybrid",
                confidence=self.confidence,
                info={
                    "mode": self.mode,
                    "selected": chosen.source,
                    "primary": primary_result.info,
                    "secondary": secondary_result.info,
                },
            )

        primary = np.asarray(primary_result.action, dtype=np.float32)
        secondary = np.asarray(secondary_result.action, dtype=np.float32)

        if self.mode == "blend":
            # Both throttles are already [0,1], so a convex combination stays valid.
            action = self.alpha * primary + (1.0 - self.alpha) * secondary
        else:  # residual
            action = secondary.copy()
            action[:3] += self.residual_scale * primary[:3]          # roll/pitch/rudder: signed [-1,1]
            action[3] += self.residual_scale * (2.0 * primary[3] - 1.0)  # throttle: re-centered [0,1]->[-1,1]

        return ActionResult(
            action=clip_action(action),
            source="hybrid",
            confidence=self.confidence,
            info={
                "mode": self.mode,
                "alpha": self.alpha,
                "residual_scale": self.residual_scale,
                "primary_source": primary_result.source,
                "secondary_source": secondary_result.source,
            },
        )

    def close(self) -> None:
        self.primary_provider.close()
        self.secondary_provider.close()


def verify_bundle_observation(
    bundle_payload: dict | None,
    observation_mode: str,
    observation_module: str = "",
) -> None:
    """Fail fast when the runtime observation config differs from the bundle's training config.

    Two same-length observation modes (e.g. relative14 vs real_eagle14) feed the policy a
    same-shaped but semantically wrong vector with no error at all -- the failure looks like
    "the model is just bad" instead of a config mismatch. Compare the bundle's recorded
    obs_mode/observation_module against what the entry script is about to run with, and raise
    before any packet is sent. Keys absent from old bundles (pre-observation_module era) are
    warned about, not enforced. observation_mode must be the EFFECTIVE mode: the custom
    module's own mode string when a module is configured, the CLI literal otherwise.
    """
    meta = (bundle_payload or {}).get("metadata") or {}
    recorded_mode = meta.get("obs_mode")
    recorded_module = meta.get("observation_module")
    problems = []
    if recorded_mode is not None and str(recorded_mode) != str(observation_mode):
        problems.append(
            f"obs_mode: bundle trained with {recorded_mode!r}, runtime configured {observation_mode!r}"
        )
    if recorded_module is not None and str(recorded_module) != str(observation_module or ""):
        problems.append(
            f"observation_module: bundle trained with {recorded_module!r}, "
            f"runtime configured {observation_module!r}"
        )
    if problems:
        raise ValueError(
            "Bundle/runtime observation mismatch -- the policy would receive features it was "
            "not trained on:\n  " + "\n  ".join(problems)
            + "\n  Fix --observation-mode/--observation-module (or point at the right bundle)."
        )
    if recorded_mode is None:
        print(
            "[DogFightEnv][WARN] bundle metadata records no obs_mode; observation config "
            f"cannot be verified (runtime: mode={observation_mode!r}, "
            f"module={observation_module!r})."
        )
