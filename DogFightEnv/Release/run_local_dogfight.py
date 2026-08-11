from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent   # Release/ 루트
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from DogFightEnvWrapper import DogFightWrapper
from dogfight.ai.bt_action_provider import BTActionProvider
from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.ai.rllib_utils import build_algorithm_from_bundle
from dogfight.ai.student_hooks import load_observation_hook

# RemappedRLProvider/StudentHybridProvider (not the stock RLActionProvider/HybridActionProvider):
# restores the training-time throttle remap at inference (see student/inference_providers.py's
# module docstring). Fixed 2026-07-14, lost in the 2026-07-15 accidental revert, restored here --
# without this, local validation exercises different (buggy) behavior than the actual submission.
from student.inference_providers import (
    RemappedRLProvider,
    StudentHybridProvider,
    verify_bundle_observation,
)
from student.controller_providers import (
    EnvelopeGatedHybridProvider,
    GLimitedProvider,
    VPTrackingProvider,
)
from student.g_limiter import G_LIMIT


def parse_args():
    parser = argparse.ArgumentParser(description="Run local dogfight simulation between two inference backends.")
    parser.add_argument("--ownship-backend", choices=["rl", "bt", "vptrack", "hybrid", "hybrid_vptrack", "hybrid_gated", "fixed"], required=True)
    parser.add_argument("--target-backend", choices=["rl", "bt", "vptrack", "hybrid", "hybrid_vptrack", "hybrid_gated", "fixed"], required=True)
    parser.add_argument("--ownship-bundle-dir")
    parser.add_argument("--target-bundle-dir")
    parser.add_argument("--ownship-bt-dll", default="AIP_BASE.dll")
    parser.add_argument("--target-bt-dll", default="AIP_BASE_target.dll")
    parser.add_argument("--bt-rule-xml", help="Optional Rule.xml source to activate while the simulation runs.")
    parser.add_argument("--ownship-policy-id", default="default_policy")
    parser.add_argument("--target-policy-id", default="default_policy")
    parser.add_argument("--observation-mode", default="tactical16", choices=["classic12", "relative14", "tactical16", "custom"])
    parser.add_argument("--observation-module", default="", help="Optional custom observation module.")
    parser.add_argument("--hybrid-mode", choices=["residual", "blend", "switch"], default="residual")
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--residual-scale", type=float, default=0.35)
    parser.add_argument("--max-engage-time", type=float, default=300.0)
    parser.add_argument("--episode-step-limit", type=int, default=18000)
    parser.add_argument("--min-altitude", type=float, default=300.0)
    parser.add_argument("--save-log", action="store_true", help="Save tacview CSV log after the episode.")
    return parser.parse_args()


def _verify_bundle_if_present(bundle_dir: str, observation_mode: str, observation_module: str) -> None:
    metadata_path = Path(bundle_dir) / "metadata.json"
    if metadata_path.exists():
        bundle_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        verify_bundle_observation(bundle_payload, observation_mode, observation_module)


def _vptrack_kwargs(range_m, los_deg, throttle, defensive=None, corner=None) -> dict:
    """Per-side overrides for VPTrackingProvider, omitting any left as None.

    Added 2026-08-06 to make ASYMMETRIC evaluation possible. Both aircraft read one global
    Rule XML, so BT-side changes cannot be given to one side only -- which means a symmetric
    benchmark (self-play) cancels any improvement exactly, and our only other benchmark (vs
    the stock BT) is saturated at 73.3% with zero losses. Neither can measure an edge. Varying
    the CONTROLLER per side is the one asymmetry available without touching the DLL, so it is
    how "tuned vs untuned" gets a number at all.
    """
    kw: dict = {}
    if range_m is not None:
        kw["engage_range_m"] = float(range_m)
    if los_deg is not None:
        kw["engage_los_deg"] = float(los_deg)
    if throttle is not None:
        kw["throttle_control"] = bool(throttle)
    if defensive is not None:
        kw["defensive_break"] = bool(defensive)
    if corner is not None:
        kw["corner_hold"] = bool(corner)
    return kw


def _build_provider_raw(
    side: str,
    backend: str,
    bundle_dir: str | None,
    bt_dll: str,
    policy_id: str,
    hybrid_mode: str,
    alpha: float,
    residual_scale: float,
    observation_mode: str = "",
    observation_module: str = "",
    vptrack_range_m: float | None = None,
    vptrack_los_deg: float | None = None,
    vptrack_throttle: bool | None = None,
    vptrack_defensive: bool | None = None,
    vptrack_corner: bool | None = None,
):
    if backend == "fixed":
        return None
    if backend == "bt":
        return BTActionProvider(dll_name=bt_dll)
    if backend == "vptrack":
        # Native BT for tactics/throttle, student-space control law for terminal pointing.
        # See student/controller_providers.py for the measured defect this bypasses.
        return VPTrackingProvider(dll_name=bt_dll, **_vptrack_kwargs(
            vptrack_range_m, vptrack_los_deg, vptrack_throttle, vptrack_defensive, vptrack_corner))
    if backend in ("hybrid_vptrack", "hybrid_gated"):
        # hybrid_vptrack: plain residual on the fixed floor. MEASURED 2026-08-06 to be strictly
        #   WORSE than the floor alone (0/30 wins vs 12/30) -- the residual's magnitude dwarfs
        #   the sub-degree precision the terminal solution needs. Kept only as the A/B control.
        # hybrid_gated: residual during the approach, floor untouched during terminal tracking.
        if not bundle_dir:
            raise ValueError(f"--{side}-bundle-dir is required when {side}-backend={backend}")
        _verify_bundle_if_present(bundle_dir, observation_mode, observation_module)
        rl_provider = RemappedRLProvider(bundle_dir=bundle_dir, algorithm_factory=build_algorithm_from_bundle, policy_id=policy_id)
        hybrid_cls = (
            EnvelopeGatedHybridProvider if backend == "hybrid_gated" else StudentHybridProvider
        )
        return hybrid_cls(
            primary_provider=rl_provider,
            secondary_provider=VPTrackingProvider(dll_name=bt_dll, **_vptrack_kwargs(
                vptrack_range_m, vptrack_los_deg, vptrack_throttle, vptrack_defensive, vptrack_corner)),
            mode=hybrid_mode,
            alpha=alpha,
            residual_scale=residual_scale,
        )
    if backend == "rl":
        if not bundle_dir:
            raise ValueError(f"--{side}-bundle-dir is required when {side}-backend=rl")
        _verify_bundle_if_present(bundle_dir, observation_mode, observation_module)
        return RemappedRLProvider(bundle_dir=bundle_dir, algorithm_factory=build_algorithm_from_bundle, policy_id=policy_id)
    if backend == "hybrid":
        if not bundle_dir:
            raise ValueError(f"--{side}-bundle-dir is required when {side}-backend=hybrid")
        _verify_bundle_if_present(bundle_dir, observation_mode, observation_module)
        rl_provider = RemappedRLProvider(bundle_dir=bundle_dir, algorithm_factory=build_algorithm_from_bundle, policy_id=policy_id)
        bt_provider = BTActionProvider(dll_name=bt_dll)
        return StudentHybridProvider(
            primary_provider=rl_provider,
            secondary_provider=bt_provider,
            mode=hybrid_mode,
            alpha=alpha,
            residual_scale=residual_scale,
        )
    raise ValueError(f"Unsupported backend: {backend}")


def build_provider(*args, **kwargs):
    """Build a provider with the 10 G load-factor limiter applied.

    THE LIMITER IS APPLIED HERE, at the single construction boundary, deliberately. It was first
    written as a separate opt-in factory and every call site kept using the raw builder, so the
    limiter shipped INERT -- present in the tree, wired into nothing. Defaulting it on at the one
    place providers are made means eval, run_local_dogfight and the live submission all inherit
    it without each having to remember.

    Why it is needed: the sim enforces no structural limit and hands out up to 14.86 G against a
    9 G airframe (scripts/g_limit_check.py). Anything that exploits that locally behaves
    differently against a server that clamps. See student/g_limiter.py.

    Pass g_limit=None to opt out (e.g. to reproduce a pre-limiter measurement).
    """
    limit = kwargs.pop("g_limit", G_LIMIT)
    provider = _build_provider_raw(*args, **kwargs)
    if provider is None or limit is None:
        return provider
    return GLimitedProvider(provider, limit_g=float(limit))


def backend_to_env_mode(backend: str) -> str:
    if backend == "fixed":
        return "fixed"
    return "rl"


def main():
    args = parse_args()
    observation_hook = load_observation_hook(args.observation_module) if args.observation_module else None
    effective_observation_mode = observation_hook["mode"] if observation_hook else args.observation_mode

    ownship_provider = build_provider(
        side="ownship",
        backend=args.ownship_backend,
        bundle_dir=args.ownship_bundle_dir,
        bt_dll=args.ownship_bt_dll,
        policy_id=args.ownship_policy_id,
        hybrid_mode=args.hybrid_mode,
        alpha=args.alpha,
        residual_scale=args.residual_scale,
        observation_mode=effective_observation_mode,
        observation_module=args.observation_module,
    )
    target_provider = build_provider(
        side="target",
        backend=args.target_backend,
        bundle_dir=args.target_bundle_dir,
        bt_dll=args.target_bt_dll,
        policy_id=args.target_policy_id,
        hybrid_mode=args.hybrid_mode,
        alpha=args.alpha,
        residual_scale=args.residual_scale,
        observation_mode=effective_observation_mode,
        observation_module=args.observation_module,
    )

    with activate_rule_xml(args.bt_rule_xml, ROOT):
        env = DogFightWrapper(
            env_config={
                "observation_mode": effective_observation_mode,
                "observation_module": args.observation_module,
                "ownship_control_mode": backend_to_env_mode(args.ownship_backend),
                "target_mode": backend_to_env_mode(args.target_backend),
                "max_engage_time": args.max_engage_time,
                "episode_step_limit": args.episode_step_limit,
                "min_altitude": args.min_altitude,
            },
            observation_fn=observation_hook["build_observation"] if observation_hook else None,
            observation_size=observation_hook["size"] if observation_hook else None,
            observation_low=observation_hook["low"] if observation_hook else None,
            observation_high=observation_hook["high"] if observation_hook else None,
            ownship_action_provider=ownship_provider,
            target_action_provider=target_provider,
        )

        try:
            observation, info = env.reset()
            terminated = False
            truncated = False
            total_reward = 0.0
            while not (terminated or truncated):
                observation, reward, terminated, truncated, info = env.step(np.zeros(4, dtype=np.float32))
                total_reward += reward

            print("simulation finished")
            print(f"end_condition: {info.get('end_condition', '')}")
            print(f"terminated: {terminated} truncated: {truncated}")
            print(f"total_reward: {total_reward:.4f}")
            print(f"ownship_health: {info.get('ownship_health', 'n/a')}")
            print(f"target_health: {info.get('target_health', 'n/a')}")

            if args.save_log:
                env.make_tacviewLog()
                print("tacview log saved")
        finally:
            env.close()


if __name__ == "__main__":
    main()
