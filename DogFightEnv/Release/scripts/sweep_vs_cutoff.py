"""Run every ownship backend (and the vptrack tuning variants) against the cutoff, in parallel.

Each job is an independent process: its own JSBSim DLL load, its own cutoff binary on its own
ephemeral loopback port. Two things ARE shared, though, and the original "nothing is shared"
claim here was wrong:

  1. Rule_forTraining.xml -- activate_rule_xml() copies over the single live file that BOTH
     aircraft read, which is why no job here passes --bt-rule-xml.
  2. aircraft/f16/f16_init.xml -- JSBSimWrapper rewrites it on EVERY env construction, from a
     module-relative path, so cwd isolation does not help. Its FileLock serialises our own
     writes but not the handle the native DLL holds past Init(). At --jobs 6 this lost the
     env_r8000_l90 arm at episode 7/50 (OSError 22). JSBSimWrapper now retries that write, and
     failed jobs are relaunched once below -- but treat a non-zero rc as a real result to
     investigate, not noise.

Note also that running any job REWRITES that init file in the working tree, undoing F7's
confirmed competition spawn preset. Check `git status DogFightEnv/Release/aircraft/` afterwards.

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
# v12_standalone completed 2026-08-21 (status=completed, 16/16 stages, 7,298 iters). It is the
# only campaign ever trained STANDALONE against the live F25-fixed tree, so it is the right
# bundle for the `rl` mode; v10 above was trained as a residual and is the right one for the
# hybrid modes. (The comment above predates v12 and describes v11 as the newest -- superseded.)
_BUNDLE_V12 = "artifacts/curriculum/real_eagle/v12_standalone/stage_15_full_dogfight/final_bundle"
_OBS = ["--observation-module", "student.my_observation_v2"]
# Residual scale is a property of the BUNDLE, not a sweep knob: v10_residual was trained at
# 0.10 and v12_standalone is not a residual at all. `--residual-scale` defaults to 0.35, so
# every hybrid job here was scoring v10 off-label until 2026-08-22 (F48). Pass it explicitly.
_SCALE_V10 = ["--residual-scale", "0.10"]

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

    # PUSH THE GRADIENT (2026-09-03, F56). The envelope sweep never turned over: damage dealt
    # goes 2500/45 -> 0.000, 4000/45 -> 0.000, 2500/90 -> 0.014, 4000/60 -> 0.122,
    # 6000/90 -> 0.282, and 6000/90 was simply the widest thing anyone had tried. These three
    # find the actual optimum instead of a boundary. LOS past 90 deg means the controller
    # engages targets in its REAR hemisphere -- physically odd, which is exactly why it is
    # worth a measurement rather than an assumption. No clamp exists on either field.
    "env_r8000_l90":          ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "8000", "--ownship-vptrack-los-deg", "90"],
    "env_r6000_l120":         ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120"],
    "env_r8000_l120":         ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "8000", "--ownship-vptrack-los-deg", "120"],

    # PARKED KNOBS, RE-TESTED AT THE ADOPTED ENVELOPE (2026-09-03, F56). defensive_break and
    # corner_hold were both measured as nulls -- but at 2500/45, an envelope that deals 0.000
    # damage, so those verdicts measured nothing and are void. F26-DEFENSIVE parked the break
    # with the words "worth re-testing against an opponent that out-shoots us"; the corrected
    # cutoff now deals 0.278/ep against 6000/90, and F58 found we LOSE round 4 on accumulated
    # damage despite out-killing it. This is that re-test.
    "env6000_90_def":         ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90",
                               "--ownship-vptrack-defensive", "1"],
    "env6000_90_corner":      ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90",
                               "--ownship-vptrack-corner", "1"],
    "env6000_90_def_corner":  ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90",
                               "--ownship-vptrack-defensive", "1", "--ownship-vptrack-corner", "1"],

    # HARD-DECK GUARD (2026-09-03). The 120 deg arms produced the best damage differential this
    # project has measured (+0.023 / +0.030) and threw it away flying into the ground 6-7 times
    # in 50, because the controller owns the stick inside the envelope and has no altitude term,
    # so Gate 0 never gets to climb. These re-run the same arms with the guard at 1000 m (just
    # above Gate 0's own 914 m trigger). env_r6000_l90_deck is the CONTROL: the shipped config
    # takes zero altitude-floor losses today, so the guard can only cost it -- measure that.
    "env_r8000_l120_deck":    ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "8000", "--ownship-vptrack-los-deg", "120",
                               "--ownship-vptrack-hard-deck", "1000"],
    "env_r6000_l120_deck":    ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                               "--ownship-vptrack-hard-deck", "1000"],
    "env_r8000_l90_deck":     ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "8000", "--ownship-vptrack-los-deg", "90",
                               "--ownship-vptrack-hard-deck", "1000"],
    "env_r6000_l90_deck":     ["--ownship-backend", "vptrack", "--ownship-vptrack-throttle", "1",
                               "--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90",
                               "--ownship-vptrack-hard-deck", "1000"],

    "rl_v10":                 ["--ownship-backend", "rl", "--ownship-bundle-dir", _BUNDLE] + _OBS,
    "hybrid_v10":             ["--ownship-backend", "hybrid", "--ownship-bundle-dir", _BUNDLE] + _OBS + _SCALE_V10,
    "hybridvp_v10":           ["--ownship-backend", "hybrid_vptrack", "--ownship-bundle-dir", _BUNDLE] + _OBS + _SCALE_V10,
    "hybridgated_v10":        ["--ownship-backend", "hybrid_gated", "--ownship-bundle-dir", _BUNDLE] + _OBS + _SCALE_V10,

    # v12_standalone (2026-08-21, completed 16/16). Added because _BUNDLE above is v10_residual,
    # which was trained AS A RESIDUAL -- running it in standalone `rl` mode is off-label, and
    # every mode deserves the bundle actually trained for it. v12 is the only completed campaign
    # trained standalone against the live F25-fixed tree, so it is the correct bundle for `rl`.
    # Expect it to lose: F43 measured it at 0W / 20-of-30 self-crash / 0 WEZ steps vs our own BT.
    # It is here so "all modes vs the cutoff" is actually all modes, not so it might win.
    "rl_v12":                 ["--ownship-backend", "rl", "--ownship-bundle-dir", _BUNDLE_V12] + _OBS,
    "hybridgated_v12":        ["--ownship-backend", "hybrid_gated", "--ownship-bundle-dir", _BUNDLE_V12] + _OBS,
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
    relaunched: set[str] = set()

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
            # Relaunch a failed arm ONCE. A crashed job used to vanish from the results table
            # with only a non-zero rc in the tail of the log to show for it, which is how
            # env_r8000_l90 came back as a 6-episode row in a N=50 sweep.
            if proc.returncode != 0 and name not in relaunched:
                relaunched.add(name)
                print(f"[sweep] FAILED {name} rc={proc.returncode} after {elapsed/60:.1f} min "
                      f"-- relaunching once", flush=True)
                queue.append(name)
                continue
            done.append((name, proc.returncode, elapsed))
            print(f"[sweep] done  {name} rc={proc.returncode} in {elapsed/60:.1f} min", flush=True)

    print("\n[sweep] all finished")
    for name, rc, elapsed in done:
        print(f"  {name:<24} rc={rc} {elapsed/60:>6.1f} min")


if __name__ == "__main__":
    main()
