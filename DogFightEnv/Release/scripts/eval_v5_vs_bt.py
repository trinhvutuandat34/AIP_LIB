"""Corrected copy of scripts/eval_matchup.py for the real_eagle v5 evaluation.

Only change vs eval_matchup.py: forward the effective observation mode +
observation module into build_provider(), so verify_bundle_observation compares
the bundle's recorded obs_mode ("real_eagle15") against the SAME mode the env
runs with -- instead of the empty string eval_matchup passes, which makes the
guard raise a false "Bundle/runtime observation mismatch" for any bundle that
correctly records its obs_mode. Also runs a bundle-health (NaN/Inf) check first.
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
from student.inference_providers import require_healthy_bundle
from student.obfm_scenario_wrapper import ObfmScenarioWrapper, OBFM_ALTITUDE_M, OBFM_SPEED_MPS
from dogfight.sim.state_schema import StateIndex

ALPHA_SCHEDULE_DEG = (0, 20, 40, 60, 80, 100, 120, 140, 160, 180)

CSV_FIELDS = [
    "episode", "alpha_deg", "outcome", "end_condition",
    "ownship_health", "target_health", "total_reward", "steps",
    "ep_wez_steps", "ep_min_distance", "initial_distance_m",
    "final_ata_deg", "final_aa_deg",
]


def _infer_gate(own_ata, tgt_ata, hca, dist):
    """Approximate reconstruction of Rule_forTraining.xml gate priority to label each step's
    likely active branch. Omits Gate 0 (altitude), energy ratios, Notch/scissors -- it resolves
    only the key question: does the geometry land in Gate 1 (defensive preemption) vs Gate 2.5
    (gun-hold) vs a maneuver. NOT a substitute for the BT's GetAnnotation (not exposed to Python);
    read it as a strong hint, not ground truth."""
    enemy_in_sight = tgt_ata <= 95.7                 # CheckSight.cpp: target's LOS-to-us <= 95.74
    if enemy_in_sight and dist <= 2000.0 and hca < 150.0:
        return "Gate1_threat"                         # jink/break preempt
    if hca > 150.0 and own_ata < 20.0 and tgt_ata < 20.0 and 500.0 < dist < 10000.0:
        return "Gate2_headon"
    if 150.0 < dist < 914.0 and own_ata < 8.0:        # matches the widened gun-hold gate
        return "Gate2p5_gunhold"
    return "maneuver"


def _geom_row(env, step):
    b = env.unwrapped
    own, tgt, geo = b._ownship_state, b._target_state, b._geo_info
    own_ata = abs(float(geo._get_antenna_train_angle(own, tgt, False)))   # proj=False == WEZ convention
    tgt_ata = abs(float(geo._get_antenna_train_angle(tgt, own, False)))
    try:
        hca = abs(float(geo._get_heading_cross_angle(own, tgt, False)))
    except Exception:
        hca = float("nan")
    try:
        aspect = abs(float(geo._get_aspect_angle(own, tgt, False)))
    except Exception:
        aspect = float("nan")
    dist = float(geo._get_distance(own, tgt))
    return {
        "step": step,
        "own_ata": round(own_ata, 3),
        "tgt_ata": round(tgt_ata, 2),
        "hca": round(hca, 2),
        "aspect": round(aspect, 2),
        "dist": round(dist, 1),
        "own_alt": round(float(own[StateIndex.ALT]), 1),
        "tgt_alt": round(float(tgt[StateIndex.ALT]), 1),
        "in_wez": int(bool(getattr(b, "_in_wez", False))),
        "gun_aligned": int(own_ata < 8.0 and 152.4 <= dist <= 914.4),
        "inferred_gate": _infer_gate(own_ata, tgt_ata, hca, dist),
    }


def _dump_trace(rows, path, scenario, backend):
    import csv as _csv, os as _os
    from collections import Counter
    d = _os.path.dirname(path)
    if d:
        _os.makedirs(d, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    n = len(rows)
    pct = lambda c: (100.0 * c / n) if n else 0.0
    min_ata = min(r["own_ata"] for r in rows)
    a8 = sum(1 for r in rows if r["own_ata"] < 8.0)
    a5 = sum(1 for r in rows if r["own_ata"] < 5.0)
    a1 = sum(1 for r in rows if r["own_ata"] <= 1.0)
    rng = sum(1 for r in rows if 152.4 <= r["dist"] <= 914.4)
    wez = sum(1 for r in rows if r["in_wez"])
    shot = [r for r in rows if r["gun_aligned"]]
    gate_shot = Counter(r["inferred_gate"] for r in shot)
    gate_all = Counter(r["inferred_gate"] for r in rows)
    print(f"[trace] {backend} {scenario}: {n} steps -> {path}")
    print(f"[trace] min own_ata={min_ata:.2f} deg | own_ata<8:{pct(a8):.0f}% <5:{pct(a5):.0f}% <=1(WEZ angle):{pct(a1):.0f}%")
    print(f"[trace] in gun range[152-914]:{pct(rng):.0f}% | in_wez(env):{pct(wez):.0f}% ({wez} steps)")
    print(f"[trace] shot available (own_ata<8 AND in range): {len(shot)} steps ({pct(len(shot)):.0f}%)")
    if shot:
        print(f"[trace]   inferred gate WHILE shot available: {dict(gate_shot)}")
        print(f"[trace]   ^ 'Gate1_threat' here = defensive preemption stealing the shot; 'gunhold' = holding it")
    print(f"[trace] inferred gate over ALL steps: {dict(gate_all)}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ownship-backend", choices=["rl", "bt", "hybrid", "fixed"], required=True)
    p.add_argument("--target-backend", choices=["rl", "bt", "hybrid", "fixed"], required=True)
    p.add_argument("--ownship-bundle-dir")
    p.add_argument("--target-bundle-dir")
    p.add_argument("--ownship-bt-dll", default="AIP_BASE.dll")
    p.add_argument("--target-bt-dll", default="AIP_BASE_target.dll")
    p.add_argument("--bt-rule-xml")
    p.add_argument("--ownship-policy-id", default="default_policy")
    p.add_argument("--target-policy-id", default="default_policy")
    p.add_argument("--observation-mode", default="tactical16",
                   choices=["classic12", "relative14", "tactical16", "custom"])
    p.add_argument("--observation-module", default="")
    p.add_argument("--hybrid-mode", choices=["residual", "blend", "switch"], default="residual")
    p.add_argument("--alpha", type=float, default=0.5)
    p.add_argument("--residual-scale", type=float, default=0.35)
    p.add_argument("--episodes", type=int, default=30)
    p.add_argument("--max-engage-time", type=float, default=300.0)
    p.add_argument("--episode-step-limit", type=int, default=18000)
    p.add_argument("--min-altitude", type=float, default=300.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--scenario-mode",
                   choices=["two_circle_headon", "obfm_offensive", "obfm_defensive"],
                   default="two_circle_headon",
                   help="Initial geometry. two_circle_headon varies over the alpha schedule; "
                        "obfm_* uses the fixed ~556 m six-o'clock advantage geometry "
                        "(via ObfmScenarioWrapper; heading randomized per episode).")
    p.add_argument("--out-csv", default="artifacts/eval/matchup.csv")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--trace-geometry", action="store_true",
                   help="Log per-step ATA/HCA/range/altitude + env in_wez + inferred BT gate for "
                        "one episode (rebuild-free instrumentation for the gun-solution root cause).")
    p.add_argument("--trace-episode", type=int, default=0, help="Which episode index to trace.")
    p.add_argument("--trace-out", default="artifacts/eval/geom_trace.csv",
                   help="Per-step geometry trace CSV output path.")
    return p.parse_args()


def main():
    args = parse_args()

    out_csv = Path(args.out_csv)
    alpha_plan = [ALPHA_SCHEDULE_DEG[i % len(ALPHA_SCHEDULE_DEG)] for i in range(args.episodes)]

    observation_hook = load_observation_hook(args.observation_module) if args.observation_module else None
    effective_observation_mode = observation_hook["mode"] if observation_hook else args.observation_mode

    print(f"[eval] {args.ownship_backend} (ownship) vs {args.target_backend} (target)")
    print(f"[eval] episodes={args.episodes}  obs_mode={effective_observation_mode}  obs_module={args.observation_module or '(builtin)'}")
    print(f"[eval] scenario={args.scenario_mode}")
    print(f"[eval] ownship bundle: {args.ownship_bundle_dir}")
    print(f"[eval] alpha schedule (deg): {alpha_plan}")
    print(f"[eval] out-csv: {out_csv}")
    if args.dry_run:
        print("[dry-run] no env constructed, no episodes run.")
        return

    if args.ownship_backend in ("rl", "hybrid") and args.ownship_bundle_dir:
        require_healthy_bundle(args.ownship_bundle_dir, strict=True)

    ownship_provider = build_provider(
        side="ownship", backend=args.ownship_backend, bundle_dir=args.ownship_bundle_dir,
        bt_dll=args.ownship_bt_dll, policy_id=args.ownship_policy_id,
        hybrid_mode=args.hybrid_mode, alpha=args.alpha, residual_scale=args.residual_scale,
        observation_mode=effective_observation_mode, observation_module=args.observation_module,
    )
    target_provider = build_provider(
        side="target", backend=args.target_backend, bundle_dir=args.target_bundle_dir,
        bt_dll=args.target_bt_dll, policy_id=args.target_policy_id,
        hybrid_mode=args.hybrid_mode, alpha=args.alpha, residual_scale=args.residual_scale,
        observation_mode=effective_observation_mode, observation_module=args.observation_module,
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
        # OBFM geometry ("obfm" scenario mode) is not native to single_agent_env.py;
        # it is staged by ObfmScenarioWrapper.reset() via change_init_position(),
        # exactly as train_curriculum.py wraps the env for the obfm_* stages. No-op
        # for two_circle_headon, so only wrap when actually needed.
        if args.scenario_mode.startswith("obfm"):
            env = ObfmScenarioWrapper(env)
        try:
            for episode, alpha_deg in enumerate(alpha_plan):
                if args.scenario_mode == "two_circle_headon":
                    scen = {"mode": "two_circle_headon", "alpha_deg": float(alpha_deg)}
                else:
                    role = "offensive" if args.scenario_mode == "obfm_offensive" else "defensive"
                    scen = {"mode": "obfm", "role": role,
                            "altitude_m": OBFM_ALTITUDE_M, "speed_mps": OBFM_SPEED_MPS}
                env.reset(seed=args.seed + episode, options={"initial_scenario": scen})
                terminated = truncated = False
                total_reward = 0.0
                info: dict = {}
                trace_on = args.trace_geometry and episode == args.trace_episode
                trace_rows = []
                while not (terminated or truncated):
                    _obs, reward, terminated, truncated, info = env.step(zero_action)
                    total_reward += reward
                    if trace_on:
                        try:
                            trace_rows.append(_geom_row(env, len(trace_rows)))
                        except Exception as _e:
                            trace_on = False
                            print(f"[trace] disabled mid-episode (geometry access failed: {_e})")
                if trace_rows:
                    _dump_trace(trace_rows, args.trace_out, args.scenario_mode, args.ownship_backend)

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
                    "final_ata_deg": round(float(info.get("final_ata_deg", 0.0)), 1),
                    "final_aa_deg": round(float(info.get("final_aa_deg", 0.0)), 1),
                })
                fh.flush()
                print(f"[ep {episode:>3}/{args.episodes}] alpha={alpha_deg:>3} -> {outcome:<8} "
                      f"({info.get('end_condition', '')})  own_hp={info.get('ownship_health','?')} "
                      f"tgt_hp={info.get('target_health','?')} wez={info.get('ep_wez_steps','?')} "
                      f"steps={info.get('ep_step_count','?')}")
        finally:
            env.close()

    n = max(args.episodes, 1)
    print("\n[eval] summary")
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
