"""Find THIS JSBSim model's corner speed by measuring turn rate against airspeed.

WHY. Corner speed is where turn rate peaks: below it you are lift-limited (cannot pull the G),
above it the same G buys less turn because omega = g*sqrt(n^2-1)/V falls with V. It is the most
useful airframe number in an angles fight, and this project has never measured it. 430-450 KTAS
was taken from a published real-F-16 figure, and forcing the aircraft to hold it measured
HARMFUL: 0 kills and 0.82 damage against the champion's 8 and 14.29 (see the CORNER_HOLD note in
student/controller_providers.py). scripts/corner_speed_probe.py also showed this airframe settles
naturally at ~340 kt, 100 kt below that figure. So either it is fighting badly, or the published
number does not describe this model at this weight and altitude. This measures which.

METHOD -- and why the obvious one does not work. The textbook approach is a sustained max-G level
turn, sweeping entry speed. That was tried first and FAILED: raw stick driven open-loop cannot
hold a coordinated banked turn. Full roll plus full pull barrel-rolls the aircraft -- measured
roll spinning through 360 deg, yaw oscillating about zero, TAS climbing 486 -> 585 kt while
altitude fell -- because the lift vector rotates with the roll and the pull averages into a
descending spiral. Every speed bin came back at 1.00 G and ~0.05 deg/s. Holding a genuine max-G
turn needs an autopilot this project does not have.

So the curve is HARVESTED from flight that is already known good: real self-play matches on the
competition geometry, where both aircraft maneuver at their limits under the controller that
demonstrably flies well. Every step contributes a (TAS, turn rate) pair from BOTH aircraft;
binning by TAS and taking a high percentile of rate per bin traces the achievable rate-vs-speed
envelope, whose peak is corner. This measures the airframe as it is actually flown, which is the
number that matters here anyway.

Turn rate is the angular rate of the VELOCITY VECTOR (not heading), so it counts the whole turn
including the vertical component -- what BFM means by turn rate. Load factor is derived as
n = sqrt((omega*V/g)^2 + 1) and samples above the F-16 structural limit are dropped as artifacts:
a 16 G sample is a numerical transient, not turn performance.

CAVEAT ON READING THE RESULT. This is an envelope of what the CURRENT controller achieves, not a
pure airframe limit. If the controller never flies fast, the fast bins are thin and their peak is
underestimated. Check the sample counts per bin before trusting a peak.
"""
from __future__ import annotations
import sys, csv, math, io
from collections import defaultdict
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

MPS_TO_KT = 1.94384
G = 9.80665
BIN_KT = 20.0
EPISODES = 12
PCTL = 95        # high percentile, not max: a 60 Hz max is dominated by transients
G_SANITY = 9.5   # F-16 structural limit; anything above is an artifact
MIN_BIN = 200    # thin bins are noise


def vel(state):
    return np.array([float(state[StateIndex.VX]), float(state[StateIndex.VY]),
                     float(state[StateIndex.VZ])])


def harvest(env, episodes, dt):
    base = env.unwrapped
    samples = []
    for ep in range(episodes):
        env.reset(seed=ep, options={"initial_scenario": {"mode": "match_base"}})
        prev = {"own": None, "tgt": None}
        term = trunc = False
        before = len(samples)
        while not (term or trunc):
            _o, _r, term, trunc, _i = env.step(np.zeros(4, dtype=np.float32))
            for who, st in (("own", base._ownship_state), ("tgt", base._target_state)):
                v = vel(st)
                sp = float(np.linalg.norm(v))
                pv = prev[who]
                prev[who] = v
                if pv is None or sp <= 1.0:
                    continue
                dot = max(-1.0, min(1.0, float(np.dot(pv / np.linalg.norm(pv), v / sp))))
                omega = math.degrees(math.acos(dot)) / dt
                if omega <= 0.0:
                    continue
                n = math.sqrt(max(0.0, (math.radians(omega) * sp / G) ** 2 + 1.0))
                if n > G_SANITY:
                    continue
                samples.append((sp * MPS_TO_KT, omega, n))
        print("  ep%2d: %6d samples" % (ep, len(samples) - before), flush=True)
    return samples


def main():
    from run_local_dogfight import build_provider
    from student.match_scenario_wrapper import MatchScenarioWrapper

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
    base = env.unwrapped
    dt = float(base._delta_t) * int(base._step_ratio)
    print("step = %.5f s, harvesting %d self-play matches on match_base" % (dt, EPISODES))
    print("")

    samples = harvest(env, EPISODES, dt)
    env.close()

    bins = defaultdict(list)
    for kt, omega, n in samples:
        bins[round(kt / BIN_KT) * BIN_KT].append((omega, n))

    rows = []
    for kt in sorted(bins):
        pairs = bins[kt]
        if len(pairs) < MIN_BIN:
            continue
        rates = sorted(p[0] for p in pairs)
        idx = min(len(rates) - 1, int(len(rates) * PCTL / 100))
        cutoff = rates[idx]
        rows.append({"tas_kt": kt, "p95_rate_deg_s": round(cutoff, 2),
                     "median_rate_deg_s": round(rates[len(rates) // 2], 2),
                     "p95_g": round(max(p[1] for p in pairs if p[0] <= cutoff), 2),
                     "samples": len(rates)})

    if not rows:
        print("no bin reached %d samples" % MIN_BIN)
        return 1

    out = ROOT / "artifacts" / "eval" / "turn_rate_sweep.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print("")
    print("  %7s  %9s  %7s  %6s  %7s" % ("TAS kt", "p95 deg/s", "median", "p95 G", "n"))
    for r in rows:
        print("  %7.0f  %9.2f  %7.2f  %6.2f  %7d  %s" % (
            r["tas_kt"], r["p95_rate_deg_s"], r["median_rate_deg_s"], r["p95_g"],
            r["samples"], "#" * int(r["p95_rate_deg_s"] * 3)))

    corner = max(rows, key=lambda r: r["p95_rate_deg_s"])
    print("")
    print("  CORNER (peak achievable turn rate): %.0f kt at %.2f deg/s (%.2f G)" % (
        corner["tas_kt"], corner["p95_rate_deg_s"], corner["p95_g"]))
    print("  published real-F-16 reference      : 430-450 kt at ~20 deg/s")
    print("  where this aircraft actually fights: ~340 kt mean")
    print("  csv: %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
