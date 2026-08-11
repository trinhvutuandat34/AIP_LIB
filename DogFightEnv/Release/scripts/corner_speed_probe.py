"""Are we fighting at corner speed? The measurement the energy probe should have made.

scripts/energy_probe.py tested specific energy Es = h + V^2/2g and found 0.22 pooled SD between
won and lost self-play episodes -- no signal -- and I read that as "energy is not the lever".
That reading was wrong, because Es is the WRONG QUANTITY. Es is conserved as altitude trades
for speed, so by construction it cannot distinguish an aircraft at corner speed from one at the
same energy that is too fast or too slow. BFM says the second aircraft loses: corner is where
turn rate peaks, and rate is what wins an angles fight.

Reference (theaviationist, BFM fundamentals, F-16): optimal merge ~430-450 KTAS / 0.8 M gives a
2500 ft turn radius at 20 deg/sec; sustained fighting speed 0.65-0.75 M at SEP = 0. Note the
match spawns at 200 m/s = 389 KTAS -- BELOW that band -- and 2500 ft = 762 m is almost exactly
the published spawn separation (2000-3000 ft), so the fight opens roughly one turn radius apart
and slower than optimal.

This reports, per episode and split by outcome: airspeed distribution, time spent inside the
corner band, and whether the winner was the one closer to corner. If winners are not
distinguished by time-at-corner either, then speed management is ruled out on the same evidence
that ruled out Es, and the remaining explanation is decision-level (one-circle vs two-circle
commitment), not energy at all.
"""
from __future__ import annotations
import sys, csv, statistics, io
from pathlib import Path

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import numpy as np
from DogFightEnvWrapper import DogFightWrapper
from dogfight.sim.state_schema import StateIndex
from student.match_scenario_wrapper import MatchScenarioWrapper
from run_local_dogfight import build_provider

MPS_TO_KT = 1.94384
CORNER_LO_KT, CORNER_HI_KT = 430.0, 450.0     # from the BFM reference
SPAWN_KT = 200.0 * MPS_TO_KT                   # 388.8 kt


def tas_kt(state) -> float:
    v = float(np.linalg.norm([state[StateIndex.VX], state[StateIndex.VY], state[StateIndex.VZ]]))
    return v * MPS_TO_KT


def main(episodes: int = 20) -> int:
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
        o_kt, t_kt = [], []
        while not (term or trunc):
            _o, _r, term, trunc, info = env.step(np.zeros(4, dtype=np.float32))
            b = env.unwrapped
            o_kt.append(tas_kt(b._ownship_state))
            t_kt.append(tas_kt(b._target_state))
        n = len(o_kt)
        in_corner = lambda xs: sum(1 for x in xs if CORNER_LO_KT <= x <= CORNER_HI_KT) / max(n, 1)
        hp_o = float(info.get("ownship_health", 1.0)); hp_t = float(info.get("target_health", 1.0))
        rows.append({
            "ep": ep,
            "own_mean_kt": statistics.mean(o_kt), "tgt_mean_kt": statistics.mean(t_kt),
            "own_corner_frac": in_corner(o_kt), "tgt_corner_frac": in_corner(t_kt),
            "own_max_kt": max(o_kt), "own_min_kt": min(o_kt),
            "margin": hp_t - hp_o,          # >0 = we hurt them more
        })
        r = rows[-1]
        print(f"  ep{ep:>2} own {r['own_mean_kt']:>6.1f} kt (corner {100*r['own_corner_frac']:>4.1f}%)  "
              f"tgt {r['tgt_mean_kt']:>6.1f} kt (corner {100*r['tgt_corner_frac']:>4.1f}%)  "
              f"margin {r['margin']:+.3f}", flush=True)
    env.close()

    out = ROOT / "artifacts" / "eval" / "corner_speed_probe.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    won = [r for r in rows if r["margin"] > 1e-6]
    lost = [r for r in rows if r["margin"] < -1e-6]
    drew = [r for r in rows if abs(r["margin"]) <= 1e-6]
    print(f"\n  episodes {len(rows)}: won {len(won)}  lost {len(lost)}  drew {len(drew)}")
    print(f"  spawn speed {SPAWN_KT:.1f} kt vs corner band {CORNER_LO_KT:.0f}-{CORNER_HI_KT:.0f} kt")
    allk = [r["own_mean_kt"] for r in rows]
    print(f"  our mean TAS across all episodes: {statistics.mean(allk):.1f} kt "
          f"(min ep {min(allk):.1f}, max ep {max(allk):.1f})")
    print(f"  mean time inside corner band: ours {100*statistics.mean(r['own_corner_frac'] for r in rows):.1f}%  "
          f"theirs {100*statistics.mean(r['tgt_corner_frac'] for r in rows):.1f}%")
    for name, grp in (("WON ", won), ("LOST", lost), ("DREW", drew)):
        if grp:
            print(f"  {name}: corner-time advantage (ours - theirs) "
                  f"{100*statistics.mean(r['own_corner_frac'] - r['tgt_corner_frac'] for r in grp):+.2f} pp")
    if len(won) > 1 and len(lost) > 1:
        a = [r["own_corner_frac"] - r["tgt_corner_frac"] for r in won]
        b = [r["own_corner_frac"] - r["tgt_corner_frac"] for r in lost]
        pooled = statistics.pstdev(a + b) or 1e-9
        print(f"\n  separation between won and lost on corner-time advantage: "
              f"{(statistics.mean(a) - statistics.mean(b)) / pooled:+.2f} pooled SD")
    print(f"  csv: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20))
