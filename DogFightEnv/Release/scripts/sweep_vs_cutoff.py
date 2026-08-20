"""Run every ownship backend (and the vptrack tuning variants) against the cutoff, in parallel.

Each job is an independent process: its own JSBSim DLL load, its own cutoff binary on its own
ephemeral loopback port. Nothing is shared, so jobs are safe to run concurrently -- with one
exception, which is why no job here passes --bt-rule-xml: activate_rule_xml() copies over the
single live Rule_forTraining.xml that BOTH aircraft read, so a job that switched rules would
change every other job running at the time.

    python scripts/sweep_vs_cutoff.py --episodes 30 --jobs 4
    python scripts/summarize_cutoff.py "artifacts/eval/cutoff_*.csv"
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PY = sys.executable
_OUT = _ROOT / "artifacts" / "eval"

# Bundle-backed modes run on the best RL result on disk: real_eagle v10_residual, the newest
# curriculum run with status=completed at stage 15 of 15. (v11_residual is newer but its
# curriculum_state.json reads status=failed at stage 3; v9_residual also completed but is older.)
# The bundle declares obs_mode real_eagle15 / observation_module student.my_observation_v2, and
# `verify_bundle_observation` rejects a mismatch, so the module has to be passed explicitly.
_BUNDLE = "artifacts/curriculum/real_eagle/v10_residual/stage_15_full_dogfight/final_bundle"
_OBS = ["--observation-module", "student.my_observation_v2"]

JOBS: dict[str, list[str]] = {
    "bt":                     ["--ownship-backend", "bt"],
    "vptrack_2200_35":        ["--ownship-backend", "vptrack",
                               "--ownship-vptrack-range-m", "2200", "--ownship-vptrack-los-deg", "35"],
    "vptrack_2000_45":        ["--ownship-backend", "vptrack",
                               "--ownship-vptrack-range-m", "2000", "--ownship-vptrack-los-deg", "45"],
    "vptrack_throttle":       ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1"],
    "vptrack_defensive":      ["--ownship-backend", "vptrack", "--ownship-vptrack-defensive", "1"],
    "vptrack_corner":         ["--ownship-backend", "vptrack", "--ownship-vptrack-corner", "1"],
    # throttle_control was measured (2026-08-19, N=19 partial) at 11 kills vs the shipping
    # config's 2 on the identical BT, so every combination below holds it ON and varies the rest.
    "thr_corner":             ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-corner", "1"],
    "thr_defensive":          ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-defensive", "1"],
    "thr_corner_def":         ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-corner", "1", "--ownship-vptrack-defensive", "1"],
    "thr_2200_35":            ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "2200", "--ownship-vptrack-los-deg", "35"],
    "thr_2000_45":            ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "2000", "--ownship-vptrack-los-deg", "45"],

    # ENVELOPE WIDENING (2026-08-20). Diagnosis of the N=100 draws: mean ep_min_distance equals
    # the initial separation exactly, i.e. closest approach was t=0 and the pair never re-merged.
    # _tracking_stick defers to the BT whenever `rng > engage_range_m or los_deg > engage_los_deg`,
    # so the whole non-closing phase is flown by the BT -- which EnvelopeGatedHybridProvider's
    # docstring already records as the thing that "loses the neutral merge". Narrowing the envelope
    # (2200/35, 2000/45) measured WORSE than the 2500/45 default, so the gradient points at
    # widening. These four separate the two axes: range-only, LOS-only, and both together.
    "env_r4000_l60":          ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "4000", "--ownship-vptrack-los-deg", "60"],
    "env_r6000_l90":          ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90"],
    "env_r4000_l45":          ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "4000", "--ownship-vptrack-los-deg", "45"],
    "env_r2500_l90":          ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "2500", "--ownship-vptrack-los-deg", "90"],

    "rl_v10":                 ["--ownship-backend", "rl", "--ownship-bundle-dir", _BUNDLE] + _OBS,
    "hybrid_v10":             ["--ownship-backend", "hybrid", "--ownship-bundle-dir", _BUNDLE] + _OBS,
    "hybridvp_v10":           ["--ownship-backend", "hybrid_vptrack", "--ownship-bundle-dir", _BUNDLE] + _OBS,
    "hybridgated_v10":        ["--ownship-backend", "hybrid_gated", "--ownship-bundle-dir", _BUNDLE] + _OBS,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", nargs="*", default=None, help="Subset of job names to run.")
    ap.add_argument("--cutoff-action-repeat", type=int, default=6)
    args = ap.parse_args()

    _OUT.mkdir(parents=True, exist_ok=True)
    names = args.only or list(JOBS)
    queue = [n for n in names if n in JOBS]
    running: list[tuple[str, subprocess.Popen, object]] = []
    done: list[tuple[str, int, float]] = []
    started: dict[str, float] = {}

    def launch(name: str) -> None:
        cmd = [
            _PY, str(_HERE / "eval_vs_cutoff.py"),
            "--target-backend", "cutoff",
            "--scenario-mode", "match_base",
            "--episodes", str(args.episodes),
            "--cutoff-action-repeat", str(args.cutoff_action_repeat),
            "--out-csv", f"artifacts/eval/cutoff_{name}.csv",
        ] + JOBS[name]
        log = (_OUT / f"cutoff_{name}.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=log, stderr=subprocess.STDOUT)
        started[name] = time.time()
        running.append((name, proc, log))
        print(f"[sweep] start {name}", flush=True)

    while queue or running:
        while queue and len(running) < args.jobs:
            launch(queue.pop(0))
        time.sleep(5)
        for entry in list(running):
            name, proc, log = entry
            if proc.poll() is None:
                continue
            running.remove(entry)
            log.close()
            elapsed = time.time() - started[name]
            done.append((name, proc.returncode, elapsed))
            print(f"[sweep] done  {name} rc={proc.returncode} in {elapsed/60:.1f} min", flush=True)

    print("\n[sweep] all finished")
    for name, rc, elapsed in done:
        print(f"  {name:<24} rc={rc} {elapsed/60:>6.1f} min")


if __name__ == "__main__":
    main()
