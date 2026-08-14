# -*- coding: utf-8 -*-
"""Train the RL policy as a RESIDUAL ON TOP OF the native BT, instead of standalone.

THE GAP THIS CLOSES. Every campaign v1-v8 trained a STANDALONE policy: the action from
env.step() went straight to the simulator, so the network had to learn flight, survival AND
tactics from a blank initialisation. "Hybrid" was only ever an INFERENCE-time construction --
student/inference_providers.py::StudentHybridProvider algebraically blends a finished policy's
output with the BT's (`BT + scale*RL`) at match time. Nothing in src/dogfight/envs/ or
train_curriculum.env_creator() has ever composed the two DURING training; grep for
"residual" under src/dogfight/ returns exactly one file, hybrid_action_provider.py, which is
inference-side. So every bundle we ever tried to compose was optimised for a job it was never
asked to do, which is a plausible part of why D3-REBASED measured every hybrid configuration
as <= vptrack alone.

Residual policy learning is a strictly easier problem than standalone control: the policy only
has to learn a CORRECTION to an already-competent baseline. That baseline only became competent
on 2026-08-13 (4.1 F26 -- before the F25 fix the BT ran two leaf nodes and was nearly inert), so
this approach was not worth building until now.

WHAT IT DOES. Wraps the env so that on every step:

    final_action = BT_action + residual_scale * policy_action

The policy still sees the same observation and still emits [-1,1]^4; the BT contribution is
computed live from the same native DLL the opponent uses. The composition MIRRORS
StudentHybridProvider EXACTLY, including its throttle re-centering -- if these two ever diverge,
the policy trains for one composition and deploys into another, which is the
train/deploy-divergence class this project has been bitten by twice (the throttle [-1,1] vs
[0,1] remap, the aspect-angle sign flip). The mirrored line is marked below; change both or
neither.

THROTTLE, precisely. env.step() takes throttle in [-1,1] and single_agent_env._to_sim_action
maps it to [0,1] via (x+1)/2. The BT's native throttle is already [0,1]. So to hand the base env
a correctly-composed action in ITS convention, the BT throttle is first converted BACK to [-1,1]
(2*t-1) and the policy's [-1,1] residual is added there. That yields exactly the same physical
throttle as StudentHybridProvider computes in [0,1] space, without the wrapper having to know
about _to_sim_action at all.

ORDERING. This wrapper must sit INSIDE GLimitWrapper (i.e. be wrapped BY it), so the G limiter
sees the FINAL composed action. Limiting the raw policy residual before the BT term is added
would clamp the wrong quantity entirely. env_creator applies it accordingly.

SCALE. residual_scale is the SAME knob as inference. Note the measured inference-time cliff
(D3-REBASED, on the v6 policy): 0.02 -> 12/30, 0.10 -> 13/30, 0.35 -> 0/30. That cliff was
measured with a policy that had NOT been trained as a residual -- a trained residual should
tolerate more authority, but do not assume it; sweep the deployed scale against the trained one
rather than trusting either number.

WHAT THIS DOES NOT DO. It does not touch src/dogfight/** (hard no-edit boundary): it is a
gym.Wrapper in student space, same pattern as GLimitWrapper. It does not change the observation,
the reward, or the action space, so a residual bundle stays loadable by the existing inference
path -- deploy it with MODE="hybrid_vptrack" or "hybrid" at the scale it was trained with.
It creates its OWN AIPilot instance for the ownship BT; the opponent's BT is separate and
untouched.
"""
from __future__ import annotations

import gymnasium as gym
import numpy as np

from dogfight.ai.action_provider import ActionContext
from dogfight.ai.bt_action_provider import BTActionProvider

DEFAULT_RESIDUAL_SCALE = 0.35


class ResidualBTWrapper(gym.Wrapper):
    """Composes the policy action as a residual on the native BT's action.

    Args:
        env: the env to wrap (apply BEFORE GLimitWrapper so G limiting sees the composite).
        dll_name: ownship BT DLL. Deliberately defaults to the ownship-side name, NOT the
            target's -- Windows loads a DLL once per resolved path, so sharing one file with
            the opponent would also share its static blackboard state.
        residual_scale: authority given to the policy. Same meaning as inference.
    """

    def __init__(
        self,
        env,
        dll_name: str = "AIP_BASE.dll",
        residual_scale: float = DEFAULT_RESIDUAL_SCALE,
    ):
        super().__init__(env)
        self.residual_scale = float(residual_scale)
        self._bt = BTActionProvider(dll_name=dll_name)
        # Diagnostics -- surfaced through info so the training log can show whether the BT
        # baseline is actually being computed, rather than silently failing to a zero vector.
        self.bt_steps = 0
        self.bt_failures = 0
        self._last_bt_action = np.zeros(4, dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        self._last_bt_action = np.zeros(4, dtype=np.float32)
        return self.env.reset(seed=seed, options=options)

    def _bt_action(self) -> np.ndarray | None:
        """Ask the native BT what IT would do from the current state. None on any failure."""
        base = self.unwrapped
        sim = getattr(base, "_sim", None)
        target_sim = getattr(base, "_target_sim", None)
        own = getattr(base, "_ownship_state", None)
        tgt = getattr(base, "_target_state", None)
        if sim is None or target_sim is None or own is None or tgt is None:
            return None
        try:
            context = ActionContext(
                sim=sim,
                opponent_sim=target_sim,
                ownship_state=own,
                target_state=tgt,
                observation=None,
            )
            result = self._bt.compute_action(context)
            action = np.asarray(result.action, dtype=np.float32).reshape(-1)
            if action.shape != (4,) or not np.all(np.isfinite(action)):
                return None
            return action
        except Exception:
            # A BT hiccup must degrade to pure-policy control for one step, never kill training.
            return None

    def step(self, action):
        if action is None:
            return self.env.step(action)

        policy = np.asarray(action, dtype=np.float32).reshape(-1).copy()
        bt = self._bt_action()
        self.bt_steps += 1

        if bt is None:
            self.bt_failures += 1
            # No BT baseline this step: pass the policy action through unmodified rather than
            # compositing against a zero vector, which would be a silent hard-left/idle command.
            return self.env.step(policy)

        self._last_bt_action = bt

        # --- MIRRORS StudentHybridProvider.compute_action's residual branch EXACTLY. ---
        # Inference composes in the SIM's [0,1] throttle space:
        #     sim[:3] = bt[:3] + scale*rl[:3]
        #     sim[3]  = bt[3]  + scale*(2*rl_remapped[3] - 1)
        # and since RemappedRLProvider feeds it rl_remapped[3] = (policy[3]+1)/2, that throttle
        # term reduces exactly to  bt[3] + scale*policy[3].
        #
        # This wrapper composes in the ENV's [-1,1] space, because the base env applies its own
        # (x+1)/2 to the throttle channel afterwards. THE FACTOR OF 2 ON THE THROTTLE RESIDUAL IS
        # LOAD-BEARING, DO NOT "SIMPLIFY" IT: converting the BT throttle up via 2*t-1 doubles the
        # range, so the base env's (x+1)/2 halves whatever residual is added here. Without the 2x
        # the policy would train with HALF the throttle authority it gets at inference -- a silent
        # train/deploy divergence of the same class as the original [-1,1] vs [0,1] remap bug.
        # Verify:  ((2*bt-1) + 2*scale*p + 1)/2  ==  bt + scale*p.  <- matches inference exactly.
        # scripts/verify_residual_wrapper.py proves this numerically and CAUGHT this exact bug.
        composed = np.empty(4, dtype=np.float32)
        composed[:3] = bt[:3] + self.residual_scale * policy[:3]
        composed[3] = (2.0 * bt[3] - 1.0) + 2.0 * self.residual_scale * policy[3]
        composed = np.clip(composed, -1.0, 1.0)

        obs, reward, terminated, truncated, info = self.env.step(composed)
        if isinstance(info, dict):
            info["residual_bt_action"] = bt
            info["residual_composed_action"] = composed
            info["residual_scale"] = self.residual_scale
            info["residual_bt_failure_rate"] = (
                self.bt_failures / self.bt_steps if self.bt_steps else 0.0
            )
        return obs, reward, terminated, truncated, info

    def make_tacviewLog(self):
        # This Gymnasium version's gym.Wrapper has no __getattr__ forwarding -- same note as
        # GLimitWrapper and the scenario wrappers.
        return self.unwrapped.make_tacviewLog()

    @property
    def bt_failure_rate(self) -> float:
        return self.bt_failures / self.bt_steps if self.bt_steps else 0.0

    def close(self):
        try:
            self._bt.close()
        except Exception:
            pass
        return self.env.close()
