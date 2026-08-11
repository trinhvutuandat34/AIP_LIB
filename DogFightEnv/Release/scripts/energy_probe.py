"""Does an energy advantage decide self-play episodes?

Deciding question for whether deeper BFM work (energy management, turn-circle geometry) is
worth a C++ rebuild cycle. Every hand-specified positional fix this session came back null,
so this measures FIRST: if winning episodes are not distinguished by energy state, then
energy management is not the lever and the C++ investment should not be made on a hunch.

Specific energy (energy height): Es = h + V^2 / 2g -- metres. The differential Es_own - Es_tgt
is the standard scalar for "who can dictate the vertical".
"""
from __future__ import annotations
import sys, csv, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
from DogFightEnvWrapper import DogFightWrapper
from dogfight.sim.state_schema import StateIndex
from student.match_scenario_wrapper import MatchScenarioWrapper
from run_local_dogfight import build_provider, backend_to_env_mode

G = 9.80665

def es(state) -> float:
    alt = -float(state[StateIndex.D])
    v = float(np.linalg.norm([state[StateIndex.VX], state[StateIndex.VY], state[StateIndex.VZ]]))
    return alt + v * v / (2.0 * G)

def main(episodes=20):
    own = build_provider(side="ownship", backend="vptrack", bundle_dir=None,
                         bt_dll="AIP_BASE.dll", policy_id="default_policy",
                         hybrid_mode="residual", alpha=0.5, residual_scale=0.35)
    tgt = build_provider(side="target", backend="vptrack", bundle_dir=None,
                         bt_dll="AIP_BASE_target.dll", policy_id="default_policy",
                         hybrid_mode="residual", alpha=0.5, residual_scale=0.35)
    env = DogFightWrapper(env_config={
        "observation_mode": "tactical16", "ownship_control_mode": "rl", "target_mode": "rl",
        "max_engage_time": 200.0, "episode_step_limit": 12000, "min_altitude": 300.0,
    }, ownship_action_provider=own, target_action_provider=tgt)
    env = MatchScenarioWrapper(env)

    rows = []
    for ep in range(episodes):
        env.reset(seed=ep, options={"initial_scenario": {"mode": "match_base"}})
        term = trunc = False
        des = []
        while not (term or trunc):
            _o, _r, term, trunc, info = env.step(np.zeros(4, dtype=np.float32))
            b = env.unwrapped
            des.append(es(b._ownship_state) - es(b._target_state))
        dealt = float(info.get("ep_damage_dealt", 0.0) or 0.0)
        hp_o = float(info.get("ownship_health", 1.0)); hp_t = float(info.get("target_health", 1.0))
        diff = hp_t - hp_o          # >0 means we hurt them more: our margin
        rows.append({"ep": ep, "mean_dEs": statistics.mean(des), "final_dEs": des[-1],
                     "max_dEs": max(des), "min_dEs": min(des),
                     "hp_own": hp_o, "hp_tgt": hp_t, "margin": -diff if False else (hp_o - hp_t)})
        print(f"  ep{ep:>2} mean dEs={rows[-1]['mean_dEs']:>9.1f} m  final={rows[-1]['final_dEs']:>9.1f}  "
              f"hp {hp_o:.3f} vs {hp_t:.3f}  margin={rows[-1]['margin']:+.3f}")
    env.close()

    out = Path("artifacts/eval/energy_probe.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    wins = [r for r in rows if r["margin"] > 1e-6]
    losses = [r for r in rows if r["margin"] < -1e-6]
    draws = [r for r in rows if abs(r["margin"]) <= 1e-6]
    print(f"\n  episodes: {len(rows)}  wins {len(wins)} losses {len(losses)} draws {len(draws)}")
    for name, grp in (("WON ", wins), ("LOST", losses), ("DREW", draws)):
        if grp:
            print(f"  {name}: mean dEs {statistics.mean(r['mean_dEs'] for r in grp):>9.1f} m   "
                  f"final dEs {statistics.mean(r['final_dEs'] for r in grp):>9.1f} m")
    if len(wins) > 1 and len(losses) > 1:
        a = [r["mean_dEs"] for r in wins]; b = [r["mean_dEs"] for r in losses]
        pooled = (statistics.pstdev(a + b) or 1e-9)
        print(f"\n  separation between won and lost episodes: "
              f"{(statistics.mean(a) - statistics.mean(b)) / pooled:+.2f} pooled SD")
    print(f"  csv: {out}")

if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20)
