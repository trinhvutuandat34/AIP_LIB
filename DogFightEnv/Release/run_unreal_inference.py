from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Force UTF-8 on stdout/stderr (2026-08-06). THIS FILE IS THE COMPETITION ENTRY POINT and it
# prints Korean status text on every start-up path. When stdout is a UTF-8 console that is fine,
# but when it is REDIRECTED TO A FILE -- which is how an unattended competition run is launched --
# Python falls back to the Windows ANSI codepage (cp1252) and the very first status print raises
# UnicodeEncodeError, killing the process BEFORE supervise_client's reconnect loop is ever armed.
# A submission that dies at start-up never connects, and not connecting is a DQ path
# (COMPETITION_RULES Sec 8). Demonstrated 2026-08-06 by running build_action_provider() with
# output redirected: UnicodeEncodeError on the mode-selection print.
import io as _io
for _stream in ("stdout", "stderr"):
    try:
        getattr(sys, _stream).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, _io.UnsupportedOperation):
        pass


ROOT = Path(__file__).resolve().parent   # Release/ 루트
SRC = ROOT / "src"
RELEASE_ROOT = ROOT
DEFAULT_BT_DLL = RELEASE_ROOT / "AIP_BASE.dll"
DEFAULT_BT_RULE_XML = RELEASE_ROOT / "Rule_forTraining.xml"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dogfight.ai.bt_action_provider import BTActionProvider
from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.ai.rllib_utils import build_algorithm_from_bundle
from dogfight.ai.student_hooks import load_observation_hook
from dogfight.unreal import AIType, ProviderCommandPolicy, UnrealAIPilotUDPClient

# RemappedRLProvider/StudentHybridProvider (not the stock RLActionProvider/HybridActionProvider):
# restores the training-time throttle remap at inference (see student/inference_providers.py's
# module docstring). Fixed 2026-07-14, lost in the 2026-07-15 accidental revert, restored here.
from student.inference_providers import (
    RemappedRLProvider,
    StudentHybridProvider,
    verify_bundle_observation,
)
# DQ hardening (2026-08-05): reconnect supervisor + never-throw provider wrapper. See the
# module docstring for the two client fragilities this guards against (COMPETITION_RULES Sec8).
from student.controller_providers import GLimitedProvider, VPTrackingProvider
from student.live_frame_fix import LiveVerticalFrameProvider
from student.g_limiter import G_LIMIT
from student.submission_resilience import ResilientActionProvider, supervise_client

# python run_unreal_inference.py --mode rl --bundle-dir artifacts\models\team01\v1 --team-name team01
# python run_unreal_inference.py --mode bt --team-name team01

def parse_args():
    parser = argparse.ArgumentParser(description="Run RL/BT/Hybrid inference and communicate with the Unreal AI server over UDP.")
    parser.add_argument("--mode", choices=["rl", "bt", "vptrack", "hybrid", "hybrid_vptrack"], required=True, help="Inference backend to use.")
    parser.add_argument("--server-ip", default="192.168.10.115", help="Unreal server IP address.")
    parser.add_argument("--server-port", type=int, default=9999, help="Unreal server UDP port.")
    parser.add_argument("--team-name", default="FDSA", help="Client team name sent to the Unreal server.")
    parser.add_argument("--simulation-state", type=int, default=1, help="Heartbeat simulation state value.")
    parser.add_argument("--heartbeat-sec", type=float, default=1.0, help="Heartbeat interval in seconds.")
    parser.add_argument("--command-delay-sec", type=float, default=0.0, help="Delay before replying with CMD after both PlaneInfo packets are ready.")
    parser.add_argument("--recv-timeout-sec", type=float, default=0.2, help="UDP socket receive timeout.")
    parser.add_argument(
        "--action-repeat",
        type=int,
        default=6,
        help=(
            "Number of completed own/enemy PlaneInfo pairs to hold each action. "
            "Use 6 to match Release training step_ratio=6; use 1 for per-packet policy calls."
        ),
    )
    parser.add_argument(
        "--debug-action-repeat",
        action="store_true",
        help="Print action-repeat counter, frame indices, update/hold state, and action values.",
    )
    parser.add_argument("--packet-monitor", action="store_true", help="Render live RX/TX packet values in the terminal.")
    parser.add_argument("--packet-monitor-interval-sec", type=float, default=0.2, help="Refresh interval for the live packet monitor.")
    parser.add_argument("--observation-mode", default="tactical16", choices=["classic12", "relative14", "tactical16", "custom"], help="Observation mode for RL inference.")
    parser.add_argument("--observation-module", default="", help="Optional custom observation module.")
    parser.add_argument("--ownship-force-side", type=int, default=1, help="Force side to use for the ownship in BT inference.")
    parser.add_argument("--target-force-side", type=int, default=2, help="Force side to use for the enemy in BT inference.")
    parser.add_argument(
        "--bt-dll",
        default=str(DEFAULT_BT_DLL),
        help="Behavior tree DLL path for BT inference.",
    )
    parser.add_argument(
        "--bt-rule-xml",
        default=str(DEFAULT_BT_RULE_XML),
        help=(
            "Rule XML source to activate while the client runs. "
            "Use Rule_forTraining.xml by default, or pass a team file such as "
            "Rule_team01.xml."
        ),
    )
    parser.add_argument("--bundle-dir", help="Lightweight RL bundle directory created by train_rllib.py.")
    parser.add_argument("--policy-id", default="default_policy", help="RLlib policy id to load from the lightweight bundle.")
    parser.add_argument("--explore", action="store_true", help="Enable stochastic action sampling for RL inference.")
    parser.add_argument("--hybrid-mode", choices=["residual", "blend", "switch"], default="residual", help="Hybrid action composition strategy.")
    parser.add_argument("--alpha", type=float, default=0.5, help="Blend weight for hybrid blend mode.")
    parser.add_argument("--residual-scale", type=float, default=0.35, help="Residual scaling factor for hybrid residual mode.")
    parser.add_argument(
        "--ai-type",
        choices=["rule", "rl", "sl", "fusion", "etc"],
        default="rl",
        help="AI type announced to the Unreal server in ClientJoinInfo.",
    )
    return parser.parse_args()


def build_action_provider(args, effective_observation_mode: str):
    """Live inference provider, wrapped in the 10 G limiter (see student/g_limiter.py).

    The sim enforces no structural limit and hands out up to 14.86 G against a 9 G airframe, so
    anything tuned against that locally diverges from a server that clamps.
    """
    # LiveVerticalFrameProvider is INSIDE the limiter: it corrects the context the provider
    # reads (Unreal sends state[2] as up-positive altitude, every consumer indexes it as NED
    # Down), whereas the limiter post-processes the action. See student/live_frame_fix.py.
    return GLimitedProvider(
        LiveVerticalFrameProvider(
            _build_action_provider_raw(args, effective_observation_mode)
        ),
        limit_g=G_LIMIT,
    )


def _build_action_provider_raw(args, effective_observation_mode: str):
    if args.mode == "bt":
        return BTActionProvider(dll_name=args.bt_dll)

    # vptrack: native BT tactics/throttle + the student-space terminal-pointing law.
    # Live-parity safe -- it reads ownship_state/target_state, which unreal/policies.py
    # populates on the live path exactly as single_agent_env.py does locally.
    if args.mode == "vptrack":
        return VPTrackingProvider(dll_name=args.bt_dll)

    if args.bundle_dir is None:
        raise ValueError("--bundle-dir is required for rl and hybrid modes")

    metadata_path = Path(args.bundle_dir) / "metadata.json"
    if metadata_path.exists():
        bundle_payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        verify_bundle_observation(bundle_payload, effective_observation_mode, args.observation_module)

    rl_provider = RemappedRLProvider(
        bundle_dir=args.bundle_dir,
        algorithm_factory=build_algorithm_from_bundle,
        policy_id=args.policy_id,
        explore=args.explore,
    )

    if args.mode == "rl":
        return rl_provider

    bt_provider = (
        VPTrackingProvider(dll_name=args.bt_dll)
        if args.mode == "hybrid_vptrack"
        else BTActionProvider(dll_name=args.bt_dll)
    )
    return StudentHybridProvider(
        primary_provider=rl_provider,
        secondary_provider=bt_provider,
        mode=args.hybrid_mode,
        alpha=args.alpha,
        residual_scale=args.residual_scale,
    )


def parse_ai_type(value: str) -> AIType:
    mapping = {
        "rule": AIType.RuleBased,
        "rl": AIType.ReinforcementLearning,
        "sl": AIType.SupervisedLearning,
        "fusion": AIType.Fusion,
        "etc": AIType.etc,
    }
    return mapping[value]


def main():
    args = parse_args()
    observation_hook = load_observation_hook(args.observation_module) if args.observation_module else None
    effective_observation_mode = observation_hook["mode"] if observation_hook else args.observation_mode
    with activate_rule_xml(args.bt_rule_xml, ROOT):
        # DQ hardening: wrap the provider so a runtime hiccup/NaN cannot crash the no-edit
        # client, and supervise client.run() so a transient network error reconnects instead
        # of ending the session (a disconnect = DQ risk). See student/submission_resilience.py.
        action_provider = ResilientActionProvider(
            build_action_provider(args, effective_observation_mode)
        )
        command_policy = ProviderCommandPolicy(
            action_provider=action_provider,
            observation_mode=effective_observation_mode,
            observation_fn=observation_hook["build_observation"] if observation_hook else None,
            ownship_force_side=args.ownship_force_side,
            target_force_side=args.target_force_side,
            action_repeat=args.action_repeat,
            debug_action_repeat=args.debug_action_repeat,
        )

        def make_client():
            return UnrealAIPilotUDPClient(
                command_policy=command_policy,
                server_ip=args.server_ip,
                server_port=args.server_port,
                team_name=args.team_name,
                ai_type=parse_ai_type(args.ai_type),
                simulation_state=args.simulation_state,
                heartbeat_interval_sec=args.heartbeat_sec,
                command_delay_sec=args.command_delay_sec,
                recv_timeout_sec=args.recv_timeout_sec,
                enable_terminal_monitor=args.packet_monitor,
                terminal_monitor_interval_sec=args.packet_monitor_interval_sec,
            )

        try:
            supervise_client(make_client)
        finally:
            action_provider.close()


if __name__ == "__main__":
    main()
