"""Where is the ~1.5 G ceiling imposed -- the vptrack pitch law, or the native BT?

scripts/turn_rate_sweep.py (2026-08-11) measured p95 load factor never exceeding 3.95 G in real
matches, and ~1.48 G at the 340 kt this aircraft fights at, while scripts/g_limit_check.py showed
full pitch delivers ~6.7 G at that speed. It left the open question as "why does this aircraft
only pull 2 G -- a control-law question", which matters because a limit living in the action path
would bound an RL policy exactly the same way.

But that sweep sampled EVERY step of both aircraft, and the vptrack controller only holds the
stick inside its terminal envelope (<=2500 m, <=45 deg); outside it the native BT flies. So the
figure pools two different controllers and cannot attribute the ceiling to either. This probe
splits them.

It needs no new instrumentation: GLimitedProvider already publishes info["g_measured"] (specific
force n = |dv/dt - g|/g, the same computation g_limit_check uses) and VPTrackingProvider already
publishes info["ctrl_source"] per step. This records both alongside the commanded pitch.

WHAT WOULD FALSIFY THE "control-law ceiling" READING: if vptrack-flown steps show the same low G
as BT-flown steps AND rarely saturate pitch, the law is the limit. If vptrack-flown steps pull
substantially harder, or saturate pitch when it does pull, then the pooled 1.48 G is a statement
about the BT flying most of the match, not about the controller -- and the analytic prediction
below should hold.

ANALYTIC PREDICTION (from student/controller_providers.py's own constants):
    pitch_cmd = -K_PITCH * err_gain * max(cos(phi), PITCH_FLOOR),  K_PITCH = 1.0, PITCH_FLOOR = 0
    err_gain  = clamp(los_deg/6.0 + clamp(integral, 0, 0.25), 0, 1.5)
Pitch saturates (|cmd| = 1) only when err_gain * cos(phi) >= 1, i.e. with the integral at its cap
and the error in the pull plane, at los_deg >= ~4.5 deg. A well-tracking controller sits at
los_deg ~1 deg, where err_gain ~0.42 and the commanded pull is ~0.4 -- by design, not by defect.
So low G while TRACKING is expected; the question is what happens while MANEUVERING.

Usage (from DogFightEnv/Release):
    python scripts\\pitch_g_probe.py [episodes]
"""
from __future__ import annotations
import sys, csv, statistics
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
from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult
from dogfight.sim.state_schema import StateIndex
from student.match_scenario_wrapper import MatchScenarioWrapper
from run_local_dogfight import build_provider

MPS_TO_KT = 1.94384
SATURATED = 0.99          # |pitch_cmd| at or above this is a full commanded pull
OUT_CSV = ROOT / "artifacts" / "eval" / "pitch_g_probe.csv"


class Recorder(ActionProvider):
    """Passthrough that captures what the wrapped provider actually commanded each step."""

    def __init__(self, inner: ActionProvider):
        self._inner = inner
        # (ctrl_source, pitch_cmd, g, kcas)
        self.samples: list[tuple[str, float, float, float]] = []

    def reset(self, context: ActionContext | None = None) -> None:
        return self._inner.reset(context)

    def compute_action(self, context: ActionContext) -> ActionResult:
        result = self._inner.compute_action(context)
        info = result.info or {}
        g = info.get("g_measured")
        own = context.ownship_state
        if g is not None and own is not None:
            self.samples.append((
                str(info.get("ctrl_source", result.source)),
                float(np.asarray(result.action).reshape(-1)[1]),
                float(g),
                float(own[StateIndex.KCAS]),
            ))
        return result

    def close(self) -> None:
        return self._inner.close()

    def __getattr__(self, name):        # let the BT recycler see through
        return getattr(self._inner, name)


def _stats(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    s = sorted(vals)
    return {
        "n": len(s),
        "median": statistics.median(s),
        "p95": s[min(len(s) - 1, int(0.95 * len(s)))],
        "max": s[-1],
    }


def main(episodes: int = 12) -> int:
    own = Recorder(build_provider(side="ownship", backend="vptrack", bundle_dir=None,
                                  bt_dll="AIP_BASE.dll", policy_id="default_policy",
                                  hybrid_mode="residual", alpha=0.5, residual_scale=0.35))
    tgt = Recorder(build_provider(side="target", backend="vptrack", bundle_dir=None,
                                  bt_dll="AIP_BASE_target.dll", policy_id="default_policy",
                                  hybrid_mode="residual", alpha=0.5, residual_scale=0.35))
    env = DogFightWrapper(env_config={
        "observation_mode": "tactical16", "ownship_control_mode": "rl", "target_mode": "rl",
        "max_engage_time": 200.0, "episode_step_limit": 12000, "min_altitude": 300.0,
    }, ownship_action_provider=own, target_action_provider=tgt)
    env = MatchScenarioWrapper(env)

    for ep in range(episodes):
        env.reset(seed=ep, options={"initial_scenario": {"mode": "match_base"}})
        term = trunc = False
        while not (term or trunc):
            _o, _r, term, trunc, _i = env.step(np.zeros(4, dtype=np.float32))
        print(f"  episode {ep + 1}/{episodes} done", flush=True)

    samples = own.samples + tgt.samples
    by_source: dict[str, list[tuple[float, float]]] = {}
    for src, pitch, g, _kcas in samples:
        by_source.setdefault(src, []).append((pitch, g))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ctrl_source", "pitch_cmd", "g_measured", "kcas"])
        for src, pitch, g, kcas in samples:
            w.writerow([src, f"{pitch:.6f}", f"{g:.6f}", f"{kcas:.2f}"])

    total = len(samples)
    print(f"\n=== pitch / G by controller, {episodes} self-play match_base episodes ===")
    print(f"total steps sampled (both aircraft): {total}\n")
    print(f"{'ctrl_source':<14}{'steps':>9}{'share':>8}"
          f"{'|pitch| med':>13}{'|pitch| p95':>13}{'sat %':>8}"
          f"{'G med':>8}{'G p95':>8}{'G max':>8}")
    for src in sorted(by_source):
        rows = by_source[src]
        pit = [abs(p) for p, _ in rows]
        gs = [g for _, g in rows]
        ps, gstat = _stats(pit), _stats(gs)
        sat = 100.0 * sum(1 for p in pit if p >= SATURATED) / len(pit)
        print(f"{src:<14}{len(rows):>9}{100.0 * len(rows) / total:>7.1f}%"
              f"{ps['median']:>13.3f}{ps['p95']:>13.3f}{sat:>7.1f}%"
              f"{gstat['median']:>8.2f}{gstat['p95']:>8.2f}{gstat['max']:>8.2f}")

    # G vs SPEED, at saturated pitch only. If full aft stick yields little G at the speed this
    # aircraft actually fights at, the ceiling is an ENERGY limit, not a command limit -- and no
    # control-law or policy change on the pitch channel can recover it.
    sat_rows = [(k, g) for _s, p, g, k in samples if abs(p) >= SATURATED]
    if sat_rows:
        print(f"\n=== G vs airspeed, FULL commanded pitch only ({len(sat_rows)} steps) ===")
        print(f"{'KCAS band':<14}{'steps':>9}{'G med':>9}{'G p95':>9}")
        bins = [(0, 200), (200, 250), (250, 300), (300, 350), (350, 400), (400, 450), (450, 9999)]
        for lo, hi in bins:
            gs = [g for k, g in sat_rows if lo <= k < hi]
            if not gs:
                continue
            st = _stats(gs)
            label = f"{lo}-{hi}" if hi < 9999 else f"{lo}+"
            print(f"{label:<14}{st['n']:>9}{st['median']:>9.2f}{st['p95']:>9.2f}")
        ks = sorted(k for k, _ in sat_rows)
        print(f"  airspeed at full pitch: median {ks[len(ks) // 2]:.0f} KCAS, "
              f"p05 {ks[int(0.05 * len(ks))]:.0f}, p95 {ks[int(0.95 * len(ks))]:.0f}")

    vp = by_source.get("vptrack", [])
    if vp:
        hard = [g for p, g in vp if abs(p) >= SATURATED]
        print(f"\nvptrack steps commanding FULL pitch: {len(hard)} "
              f"({100.0 * len(hard) / len(vp):.1f}% of vptrack steps)")
        if hard:
            h = _stats(hard)
            print(f"  G on those steps: median {h['median']:.2f}, p95 {h['p95']:.2f}, "
                  f"max {h['max']:.2f}")
            print("  -> if this is well above the pooled figure, the ceiling is NOT the pitch law;")
            print("     the pooled number is dominated by the BT flying the rest of the match.")
    print(f"\ncsv: {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 12))
