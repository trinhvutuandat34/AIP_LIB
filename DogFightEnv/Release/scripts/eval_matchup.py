"""Hybrid-mismatch benchmark harness (COMPETITION_PLAN.md / BT plan §8).

Loops N episodes of one backend pairing (bt|rl|hybrid|fixed vs. the same),
varying the two-circle head-on start geometry across the same alpha schedule
the curriculum's two_circle_headon stages use, and writes each episode's
outcome to a CSV. The point is to compare, on identical geometry, standalone-RL
vs. hybrid-residual (the actual submission path: action = BT + 0.35*RL) vs.
BT-alone -- run this script once per config, then diff the win/WEZ rates per
the plan's §8 decision criteria.

Reuses run_local_dogfight.py's provider construction verbatim; the only new
machinery here is the episode loop, per-reset geometry variation, and CSV/
summary aggregation. Deliberately drives both sides through ActionProviders and
reuses ONE env across episodes (reset(options=...) re-applies geometry and
resets the providers) rather than reloading the DLL/bundle each episode.

Example (run AFTER curriculum training frees the CPU workers -- each episode
spins up its own JSBSim, so don't run this concurrently with a training job):

    python scripts\\eval_matchup.py --ownship-backend hybrid \\
        --ownship-bundle-dir artifacts\\models\\real_eagle\\v1 \\
        --target-backend bt --episodes 30 --out-csv artifacts\\eval\\hybrid_vs_bt.csv
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]   # Release/ root (scripts/ is one below)
SRC = ROOT / "src"
for _p in (ROOT, SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from DogFightEnvWrapper import DogFightWrapper
from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.ai.student_hooks import load_observation_hook
from run_local_dogfight import build_provider, backend_to_env_mode

# Same alpha schedule as ai/curriculum.py's _build_two_circle_headon_stages.
ALPHA_SCHEDULE_DEG = (0, 20, 40, 60, 80, 100, 120, 140, 160, 180)

# info-dict keys captured per episode (all set by single_agent_env.py's step()).
#
# ANGLE CONVENTION (2026-08-06): the two angle columns are suffixed `_2d` because the platform
# computes them with proj=True -- horizontal azimuth, elevation discarded, signed. The WEZ damage
# gate tests a CONE (proj=False: arccos of the body-frame LOS, unsigned), so these two are a
# DIFFERENT QUANTITY from the gate and can disagree with it by tens of degrees. Reading the old
# unsuffixed `final_ata_deg` as "how close to a firing solution" silently understates the miss.
# This harness has no per-step tracking, so it cannot emit the 3D counterpart -- if you need
# angles you can compare against the gate (or phase-aware WEZ scoring), use the maintained
# superset harness scripts/eval_v5_vs_bt.py instead, which reports both conventions explicitly.
CSV_FIELDS = [
    "episode", "alpha_deg", "outcome", "end_condition",
    "ownship_health", "target_health", "total_reward", "steps",
    "ep_wez_steps", "ep_min_distance", "initial_distance_m",
    "final_ata_deg_2d", "final_aa_deg_2d",
]


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ownship-backend", choices=["rl", "bt", "hybrid", "fixed"], required=True)
    p.add_argument("--target-backend", choices=["rl", "bt", "hybrid", "fixed"], required=True)
    p.add_argument("--ownship-bundle-dir")
    p.add_argument("--target-bundle-dir")
    p.add_argument("--ownship-bt-dll", default="AIP_BASE.dll")
    p.add_argument("--target-bt-dll", default="AIP_BASE_target.dll")
    p.add_argument("--bt-rule-xml", help="Optional Rule.xml source to activate for the run.")
    p.add_argument("--ownship-policy-id", default="default_policy")
    p.add_argument("--target-policy-id", default="default_policy")
    p.add_argument("--observation-mode", default="tactical16",
                   choices=["classic12", "relative14", "tactical16", "custom"])
    p.add_argument("--observation-module", default="", help="Optional custom observation module.")
    p.add_argument("--hybrid-mode", choices=["residual", "blend", "switch"], default="residual")
    p.add_argument("--alpha", type=float, default=0.5, help="HybridActionProvider blend alpha (blend/switch modes).")
    p.add_argument("--residual-scale", type=float, default=0.35, help="Hybrid residual scale (submission default 0.35).")
    p.add_argument("--episodes", type=int, default=30)
    p.add_argument("--max-engage-time", type=float, default=300.0)
    p.add_argument("--episode-step-limit", type=int, default=18000)
    p.add_argument("--min-altitude", type=float, default=300.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-csv", default="artifacts/eval/matchup.csv")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the resolved matchup plan and exit before constructing any env/JSBSim.")
    return p.parse_args()


def main():
    args = parse_args()

    out_csv = Path(args.out_csv)
    alpha_plan = [ALPHA_SCHEDULE_DEG[i % len(ALPHA_SCHEDULE_DEG)] for i in range(args.episodes)]

    print(f"[eval_matchup] {args.ownship_backend} (ownship) vs {args.target_backend} (target)")
    print(f"[eval_matchup] episodes={args.episodes}  hybrid_mode={args.hybrid_mode} "
          f"residual_scale={args.residual_scale}")
    print(f"[eval_matchup] alpha schedule (deg): {alpha_plan}")
    print(f"[eval_matchup] out-csv: {out_csv}")
    if args.dry_run:
        print("[dry-run] no env constructed, no episodes run.")
        return

    observation_hook = load_observation_hook(args.observation_module) if args.observation_module else None

    ownship_provider = build_provider(
        side="ownship", backend=args.ownship_backend, bundle_dir=args.ownship_bundle_dir,
        bt_dll=args.ownship_bt_dll, policy_id=args.ownship_policy_id,
        hybrid_mode=args.hybrid_mode, alpha=args.alpha, residual_scale=args.residual_scale,
    )
    target_provider = build_provider(
        side="target", backend=args.target_backend, bundle_dir=args.target_bundle_dir,
        bt_dll=args.target_bt_dll, policy_id=args.target_policy_id,
        hybrid_mode=args.hybrid_mode, alpha=args.alpha, residual_scale=args.residual_scale,
    )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    outcomes: Counter[str] = Counter()
    wez_contact_episodes = 0
    zero_action = np.zeros(4, dtype=np.float32)

    with activate_rule_xml(args.bt_rule_xml, ROOT), open(out_csv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()

        env = DogFightWrapper(
            env_config={
                "observation_mode": observation_hook["mode"] if observation_hook else args.observation_mode,
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
            for episode, alpha_deg in enumerate(alpha_plan):
                # Per-episode geometry: two_circle_headon at this alpha (leaves the
                # geometry_guard OFF so episodes end on real combat outcomes, not a
                # training-only turn-execution guard). Deep-merges over the config's
                # initial_scenario defaults, so altitude/speed stay at the corrected
                # competition values from config.py.
                env.reset(
                    seed=args.seed + episode,
                    options={"initial_scenario": {"mode": "two_circle_headon", "alpha_deg": float(alpha_deg)}},
                )
                terminated = truncated = False
                total_reward = 0.0
                info: dict = {}
                while not (terminated or truncated):
                    _obs, reward, terminated, truncated, info = env.step(zero_action)
                    total_reward += reward

                outcome = info.get("outcome", "unknown")
                outcomes[outcome] += 1
                if float(info.get("ep_wez_steps", 0)) > 0:
                    wez_contact_episodes += 1

                writer.writerow({
                    "episode": episode,
                    "alpha_deg": alpha_deg,
                    "outcome": outcome,
                    "end_condition": info.get("end_condition", ""),
                    "ownship_health": info.get("ownship_health", ""),
                    "target_health": info.get("target_health", ""),
                    "total_reward": round(total_reward, 4),
                    "steps": info.get("ep_step_count", ""),
                    "ep_wez_steps": info.get("ep_wez_steps", ""),
                    "ep_min_distance": round(float(info.get("ep_min_distance", 0.0)), 1),
                    "initial_distance_m": round(float(info.get("initial_distance_m", 0.0)), 1),
                    # info's values are proj=True (2D azimuth) -- see the CSV_FIELDS note.
                    "final_ata_deg_2d": round(float(info.get("final_ata_deg", 0.0)), 1),
                    "final_aa_deg_2d": round(float(info.get("final_aa_deg", 0.0)), 1),
                })
                fh.flush()
                print(f"[ep {episode:>3}/{args.episodes}] alpha={alpha_deg:>3} -> {outcome:<8} "
                      f"({info.get('end_condition', '')})")
        finally:
            env.close()

    n = max(args.episodes, 1)
    print("\n[eval_matchup] summary")
    print(f"  episodes: {args.episodes}")
    for name in ("win", "loss", "draw", "timeout"):
        c = outcomes.get(name, 0)
        print(f"  {name:<8}: {c:>3}  ({c / n:.1%})")
    other = {k: v for k, v in outcomes.items() if k not in ("win", "loss", "draw", "timeout")}
    if other:
        print(f"  other   : {dict(other)}")
    print(f"  wez-contact episodes: {wez_contact_episodes} ({wez_contact_episodes / n:.1%})")
    print(f"  csv: {out_csv}")


if __name__ == "__main__":
    main()
