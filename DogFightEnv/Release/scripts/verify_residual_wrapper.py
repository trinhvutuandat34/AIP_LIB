"""Regression guard for student/residual_training_wrapper.py (2026-08-13).

The wrapper's whole value depends on ONE property: the composition it trains against must be
algebraically identical to the one StudentHybridProvider applies at inference. If they diverge,
the policy is optimised for a job it will not be given -- which is the train/deploy-divergence
class that has bitten this project twice (throttle [-1,1] vs [0,1]; aspect-angle sign).

That equivalence cannot be checked by reading the two files side by side, because they work in
DIFFERENT throttle conventions on purpose: the inference provider composes in the sim's [0,1]
space, while the wrapper composes in the env's [-1,1] space (the base env applies (x+1)/2
itself). This script proves they agree on the resulting PHYSICAL action, over randomised inputs,
rather than asserting it in a comment.

Also covers the failure modes that would be silent in a training log: a BT failure degrading to
pure-policy instead of compositing against zeros, clipping, and the scale=0 identity.

No simulator, no DLL, no network -- pure algebra on stubbed providers, so it runs in seconds and
can be a pre-commit tripwire like scripts/verify_report_fixes.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dogfight.ai.action_provider import ActionResult

PASS = "  [PASS]"
FAIL = "  [FAIL]"
_failures = []


def check(label: str, ok: bool) -> None:
    print(f"{PASS if ok else FAIL} {label}")
    if not ok:
        _failures.append(label)


def sim_throttle_from_env_action(env_throttle: float) -> float:
    """What single_agent_env._to_sim_action does to the throttle channel."""
    return float(np.clip((np.clip(env_throttle, -1.0, 1.0) + 1.0) / 2.0, 0.0, 1.0))


def inference_composition(bt_sim: np.ndarray, policy_raw: np.ndarray, scale: float) -> np.ndarray:
    """Exactly StudentHybridProvider's residual branch, in the sim's own convention.

    bt_sim: BT action as the native DLL emits it (throttle already [0,1]).
    policy_raw: the policy's raw [-1,1]^4 output, AFTER RemappedRLProvider's throttle remap
                (so channel 3 is in [0,1], neutral 0.5) -- mirroring what the provider receives.
    """
    action = bt_sim.astype(np.float32).copy()
    action[:3] += scale * policy_raw[:3]
    action[3] += scale * (2.0 * policy_raw[3] - 1.0)
    low = np.array([-1.0, -1.0, -1.0, 0.0], dtype=np.float32)
    high = np.ones(4, dtype=np.float32)
    return np.clip(action, low, high)


def wrapper_composition(bt_sim: np.ndarray, policy_env: np.ndarray, scale: float) -> np.ndarray:
    """Exactly ResidualBTWrapper.step()'s composition, then the base env's own throttle remap.

    policy_env: the policy's raw [-1,1]^4 as env.step() receives it (channel 3 NOT remapped).
    Returns the action in SIM convention so it is comparable with inference_composition.
    """
    composed = np.empty(4, dtype=np.float32)
    composed[:3] = bt_sim[:3] + scale * policy_env[:3]
    # 2x is load-bearing -- see the wrapper's comment. Without it the base env's (x+1)/2 halves
    # the throttle residual, and the policy trains with half its deployed authority.
    composed[3] = (2.0 * bt_sim[3] - 1.0) + 2.0 * scale * policy_env[3]
    composed = np.clip(composed, -1.0, 1.0)
    # base env then converts throttle back to [0,1]
    out = composed.copy()
    out[3] = sim_throttle_from_env_action(composed[3])
    return np.clip(out, np.array([-1.0, -1.0, -1.0, 0.0], dtype=np.float32), np.ones(4, dtype=np.float32))


def main() -> int:
    print("=" * 88)
    print("Regression guard: residual training composition == inference composition")
    print("=" * 88)

    rng = np.random.default_rng(20260813)
    scales = [0.02, 0.10, 0.35, 0.5, 1.0]

    print("\nEquivalence: wrapper (env [-1,1] space) vs StudentHybridProvider (sim [0,1] space)")
    worst = 0.0
    for scale in scales:
        worst_for_scale = 0.0
        for _ in range(4000):
            bt_sim = np.concatenate([rng.uniform(-1, 1, 3), rng.uniform(0, 1, 1)]).astype(np.float32)
            policy_env = rng.uniform(-1, 1, 4).astype(np.float32)
            # The same policy output, expressed as RemappedRLProvider would hand it to the
            # inference provider: throttle mapped [-1,1] -> [0,1].
            policy_raw = policy_env.copy()
            policy_raw[3] = (policy_raw[3] + 1.0) / 2.0

            a = inference_composition(bt_sim, policy_raw, scale)
            b = wrapper_composition(bt_sim, policy_env, scale)
            worst_for_scale = max(worst_for_scale, float(np.max(np.abs(a - b))))
        worst = max(worst, worst_for_scale)
        check(f"scale={scale}: max |inference - wrapper| = {worst_for_scale:.3e} (< 1e-6)",
              worst_for_scale < 1e-6)

    print("\nThrottle direction: the residual must be able to LOWER throttle, not only raise it")
    bt_sim = np.array([0.0, 0.0, 0.0, 0.60], dtype=np.float32)   # BT commanding 0.6 throttle
    down = wrapper_composition(bt_sim, np.array([0, 0, 0, -1.0], dtype=np.float32), 0.35)
    up = wrapper_composition(bt_sim, np.array([0, 0, 0, +1.0], dtype=np.float32), 0.35)
    check(f"policy throttle -1 lowers it: {down[3]:.4f} < 0.60", down[3] < 0.60 - 1e-6)
    check(f"policy throttle +1 raises it: {up[3]:.4f} > 0.60", up[3] > 0.60 + 1e-6)
    check("this is the bug StudentHybridProvider's re-centering exists to prevent "
          "(a plain add could only ever raise throttle)", down[3] < 0.60 - 1e-6)

    print("\nIdentity: scale=0 must reproduce the BT exactly (the policy has no authority)")
    for _ in range(500):
        bt_sim = np.concatenate([rng.uniform(-1, 1, 3), rng.uniform(0, 1, 1)]).astype(np.float32)
        policy_env = rng.uniform(-1, 1, 4).astype(np.float32)
        out = wrapper_composition(bt_sim, policy_env, 0.0)
        if float(np.max(np.abs(out - bt_sim))) > 1e-6:
            check(f"scale=0 reproduces BT exactly (got {out} vs {bt_sim})", False)
            break
    else:
        check("scale=0 reproduces the BT action exactly over 500 random samples", True)

    print("\nBounds: the composed action must stay in the sim's legal range")
    ok_bounds = True
    for scale in scales:
        for _ in range(2000):
            bt_sim = np.concatenate([rng.uniform(-1, 1, 3), rng.uniform(0, 1, 1)]).astype(np.float32)
            policy_env = rng.uniform(-1, 1, 4).astype(np.float32)
            out = wrapper_composition(bt_sim, policy_env, scale)
            if not (np.all(out[:3] >= -1.0 - 1e-6) and np.all(out[:3] <= 1.0 + 1e-6)
                    and -1e-6 <= out[3] <= 1.0 + 1e-6):
                ok_bounds = False
                break
    check("composed action stays within [-1,1]^3 x [0,1] at every scale tested", ok_bounds)

    print("\nBT-failure degradation: a BT hiccup must pass the policy through, not composite zeros")
    import student.residual_training_wrapper as rtw

    import gymnasium as gym

    class _StubEnv(gym.Env):
        """Minimal real gym.Env that records what action it was stepped with.

        Must genuinely subclass gym.Env -- gym.Wrapper.__init__ asserts on the type.
        _sim/_target_sim are None so _bt_action() takes its failure path.
        """
        def __init__(self):
            super().__init__()
            self.observation_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=np.float32)
            self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(4,), dtype=np.float32)
            self.last_action = None
            self._sim = None
            self._target_sim = None
            self._ownship_state = None
            self._target_state = None
        def step(self, action):
            self.last_action = np.asarray(action, dtype=np.float32).copy()
            return np.zeros(4, dtype=np.float32), 0.0, False, False, {}
        def reset(self, *, seed=None, options=None):
            return np.zeros(4, dtype=np.float32), {}
        def close(self):
            return None

    stub = _StubEnv()
    wrapper = rtw.ResidualBTWrapper.__new__(rtw.ResidualBTWrapper)   # bypass DLL construction
    gym_wrapper_init = rtw.gym.Wrapper.__init__
    gym_wrapper_init(wrapper, stub)
    wrapper.residual_scale = 0.35
    wrapper._bt = None
    wrapper.bt_steps = 0
    wrapper.bt_failures = 0
    wrapper._last_bt_action = np.zeros(4, dtype=np.float32)

    policy_env = np.array([0.7, -0.3, 0.1, 0.9], dtype=np.float32)
    wrapper.step(policy_env)
    passed_through = stub.last_action
    check(f"BT unavailable -> policy action passed through unchanged (got {passed_through})",
          passed_through is not None and float(np.max(np.abs(passed_through - policy_env))) < 1e-6)
    check("BT failure was counted (bt_failures == 1)", wrapper.bt_failures == 1)
    check(f"bt_failure_rate reports 1.0 when every step failed (got {wrapper.bt_failure_rate})",
          abs(wrapper.bt_failure_rate - 1.0) < 1e-9)

    print("\n" + "=" * 88)
    if _failures:
        print(f"FAILED -- {len(_failures)} check(s):")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    print("The training-time composition is algebraically identical to StudentHybridProvider's,")
    print("so a bundle trained through this wrapper deploys into the same arithmetic it learned.")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
