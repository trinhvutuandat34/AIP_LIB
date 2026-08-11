"""Is this aircraft LIFT-limited or COMMAND-limited? The check that decides where to look next.

MOTIVATION. scripts/turn_rate_sweep.py found that in real matches the aircraft never exceeds
~3.95 G at the 95th percentile and typically turns at 0.05-1.35 deg/s, on an airframe rated for
9 G. That single fact explains most of this session's null results: every positional fix was
reallocating a maneuvering budget that was never being spent. Two very different causes:

  LIFT-limited    340 kt is genuinely too slow to pull more. Speed and G are one coupled
                  problem and the fix is energy management.
  COMMAND-limited something in the pitch path never ASKS for more -- the error-proportional
                  law, clip_action, or the FDM's response to a full pitch command. This matters
                  enormously for v7: an RL policy emits through the SAME action interface, so it
                  would inherit the identical ceiling and plateau for the same reason, and no
                  reward shaping could find a way past it.

METHOD. A wings-level maximum pull at a series of trimmed entry speeds -- no bank, so none of
the roll instability that invalidated the first turn-rate sweep (full roll + full pull just
barrel-rolls the aircraft). Command is held for HOLD_S seconds and the peak load factor is
recorded against the speed it occurred at.

Load factor is computed as SPECIFIC FORCE, not from turn rate: a = dv/dt in the N-E-Up frame,
f = a - g_vec, n = |f|/g. Deriving n from omega assumes a level turn and would misreport a
vertical pull, where gravity is not perpendicular to the velocity vector.

BOTH pitch signs are flown, because the env action convention is not documented and cannot be
assumed. Controller_CY emits NEGATIVE PitchCMD for a pull internally, but whether the env's
action vector shares that convention is exactly the sort of thing this project has been bitten
by before (the throttle [-1,1] vs [0,1] remap bug, the aspect-angle sign trap). Whichever sign
produces a climb with positive G is the pull.

READING IT. If peak G climbs with speed and approaches ~9 G somewhere, the aircraft is
lift-limited below that and corner is near where it saturates. If peak G caps at 2-4 G at EVERY
speed, the limit is in the command path and no amount of energy management will fix it.
"""
from __future__ import annotations
import sys, csv, math, io
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
ALT_M = 4572.0
ENTRY_KT = [250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 550.0]
HOLD_S = 4.0


def vel_neu(state):
    """Velocity in N-E-Up. VZ is NED-down, so Up = -VZ."""
    return np.array([float(state[StateIndex.VX]), float(state[StateIndex.VY]),
                     -float(state[StateIndex.VZ])])


def run(env, entry_kt, pitch_cmd, dt, steps):
    base = env.unwrapped
    base.change_init_position("ownship", init_n=0.0, init_e=0.0, init_d=-ALT_M,
                              init_roll=0.0, init_pitch=0.0, init_heading=0.0,
                              init_speed=entry_kt / MPS_TO_KT)
    base.change_init_position("target", init_n=60000.0, init_e=60000.0, init_d=-ALT_M,
                              init_roll=0.0, init_pitch=0.0, init_heading=0.0, init_speed=200.0)
    env.reset(seed=0)

    g_vec = np.array([0.0, 0.0, -G])
    prev_v, peak_n, peak_at_kt, alt0 = None, 0.0, entry_kt, None
    alt_end = None
    for _ in range(steps):
        _o, _r, term, trunc, _i = env.step(np.array([0.0, pitch_cmd, 0.0, 1.0], dtype=np.float32))
        st = base._ownship_state
        v = vel_neu(st)
        alt = -float(st[StateIndex.D])
        if alt0 is None:
            alt0 = alt
        alt_end = alt
        if prev_v is not None:
            a = (v - prev_v) / dt
            n = float(np.linalg.norm(a - g_vec)) / G
            if 0.0 < n < 15.0 and n > peak_n:
                peak_n = n
                peak_at_kt = float(np.linalg.norm(v)) * MPS_TO_KT
        prev_v = v
        if term or trunc:
            break
    return peak_n, peak_at_kt, (alt_end - alt0 if alt0 is not None else 0.0)


def main():
    env = DogFightWrapper(env_config={
        "observation_mode": "tactical16", "ownship_control_mode": "rl", "target_mode": "loiter",
        "max_engage_time": 200.0, "episode_step_limit": 12000, "min_altitude": 300.0,
    })
    base = env.unwrapped
    dt = float(base._delta_t) * int(base._step_ratio)
    steps = max(10, int(HOLD_S / dt))
    print("step %.5f s, holding full pitch for %.1f s (%d steps), wings level" % (dt, HOLD_S, steps))
    print("")

    rows = []
    for sign, label in ((-1.0, "pitch -1"), (+1.0, "pitch +1")):
        print("  === %s ===" % label)
        for kt in ENTRY_KT:
            n, at_kt, dalt = run(env, kt, sign, dt, steps)
            rows.append({"pitch_cmd": sign, "entry_kt": kt, "peak_g": round(n, 2),
                         "peak_at_kt": round(at_kt, 1), "alt_change_m": round(dalt, 1)})
            print("    entry %5.0f kt -> peak %5.2f G at %5.0f kt, altitude %+7.1f m"
                  % (kt, n, at_kt, dalt))
        print("")
    env.close()

    out = ROOT / "artifacts" / "eval" / "g_limit_check.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # The pull is whichever sign climbs; report the verdict from that arm.
    for sign in (-1.0, +1.0):
        arm = [r for r in rows if r["pitch_cmd"] == sign]
        climbed = sum(1 for r in arm if r["alt_change_m"] > 0)
        best = max(arm, key=lambda r: r["peak_g"])
        print("  pitch %+.0f : climbed in %d/%d runs, best %.2f G (entry %.0f kt)"
              % (sign, climbed, len(arm), best["peak_g"], best["entry_kt"]))

    pull = max(rows, key=lambda r: r["peak_g"])
    print("")
    print("  highest load factor anywhere: %.2f G" % pull["peak_g"])
    if pull["peak_g"] >= 7.0:
        print("  -> reaches near the 9 G airframe limit: LIFT-limited at low speed,")
        print("     corner is near where peak G saturates. Energy management is the lever.")
    elif pull["peak_g"] >= 4.5:
        print("  -> partial authority. Neither explanation is clean; inspect the pitch path.")
    else:
        print("  -> caps well below the 9 G airframe rating at EVERY speed: COMMAND-limited.")
        print("     The ceiling is in the action path, not the airframe -- an RL policy emitting")
        print("     through the same interface would inherit it. Fix this before training v7.")
    print("  csv: %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
