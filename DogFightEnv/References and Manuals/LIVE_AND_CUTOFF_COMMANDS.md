# Live modes + cutoff model — every command (2026-08-21)

Flags verified against the actual argparse blocks on this date, not from memory.
`COMMAND.md` is the exhaustive project-wide list; this file covers **live inference** and the
**cutoff model** only.

---

## 0. Prerequisites (both sections)

```powershell
cd D:\AIP1\AIP\AIP_LIB\DogFightEnv\Release
```

**`python` must be the `aip` conda env.** Plain `python` is anaconda3 *base* and has no
`pymap3d` — it dies on import.

```powershell
C:\Users\Administrator\anaconda3\envs\aip\python.exe        # or: conda activate aip
```

---

## ⚠ 1. THE TRAP: `run_unreal_inference.py --mode vptrack` is NOT the shipping config

`_build_action_provider_raw` builds a bare `VPTrackingProvider(dll_name=...)`, so it takes the
module defaults — **2500 m / 45° / throttle OFF**. That is the pre-F29/F39 config that scores
**13.3 %** against the cutoff. The shipping config (**4000 m / 60° + throttle**, 100 % vs cutoff,
N=100) is set *explicitly* only in `student/my_submission.py`.

**For a real match, run `my_submission.py`.** If you must use `run_unreal_inference.py`, force the
envelope with env vars first:

```powershell
$env:DOGFIGHT_VPTRACK_THROTTLE = "1"
$env:DOGFIGHT_VPTRACK_RANGE_M  = "4000"
$env:DOGFIGHT_VPTRACK_LOS_DEG  = "60"
```

---

## 2. LIVE — the shipping submission (this is what competes)

No CLI flags; configured by module constants + env vars.

```powershell
$env:DOGFIGHT_SERVER_IP  = "<announced IP>"
$env:DOGFIGHT_SERVER_PORT = "<announced port>"
python student\my_submission.py
```

Already correct inside it: `MODE="vptrack"`, `BUNDLE_DIR=None`, `throttle_control=True`,
`engage=4000m/60deg`, `ACTION_REPEAT=1`, live frame fix, G-limiter, resilience + silence
watchdog. The packet monitor is **on** by default here.

---

## 3. LIVE — `run_unreal_inference.py`, all five modes

Common flags: `--server-ip <IP> --server-port <PORT> --team-name real_eagle
--action-repeat 1 --packet-monitor`

Modes are exactly: `bt` | `vptrack` | `rl` | `hybrid` | `hybrid_vptrack`.

```powershell
# --- bt : native behaviour tree only -------------------------------------------------
python run_unreal_inference.py --mode bt --team-name real_eagle `
  --server-ip <IP> --server-port <PORT> --action-repeat 1 --packet-monitor

# --- vptrack : BT tactics + terminal pointing law (SET THE ENV VARS IN 1 FIRST) -------
python run_unreal_inference.py --mode vptrack --team-name real_eagle `
  --server-ip <IP> --server-port <PORT> --action-repeat 1 --packet-monitor

# --- rl : pure policy (needs a bundle + matching observation config) ------------------
python run_unreal_inference.py --mode rl --team-name real_eagle `
  --server-ip <IP> --server-port <PORT> --action-repeat 1 --packet-monitor `
  --bundle-dir artifacts\curriculum\real_eagle\v12_standalone\stage_15_full_dogfight\final_bundle `
  --observation-mode custom --observation-module student.my_observation_v2

# --- hybrid : BT + scale*RL (residual | blend | switch) -------------------------------
python run_unreal_inference.py --mode hybrid --hybrid-mode residual --residual-scale 0.10 `
  --team-name real_eagle --server-ip <IP> --server-port <PORT> --action-repeat 1 --packet-monitor `
  --bundle-dir artifacts\curriculum\real_eagle\v10_residual\stage_15_full_dogfight\final_bundle `
  --observation-mode custom --observation-module student.my_observation_v2

# --- hybrid_vptrack : vptrack as the secondary instead of raw BT ----------------------
python run_unreal_inference.py --mode hybrid_vptrack --hybrid-mode residual --residual-scale 0.10 `
  --team-name real_eagle --server-ip <IP> --server-port <PORT> --action-repeat 1 --packet-monitor `
  --bundle-dir artifacts\curriculum\real_eagle\v10_residual\stage_15_full_dogfight\final_bundle `
  --observation-mode custom --observation-module student.my_observation_v2
```

**`rl` and `hybrid*` are measured WORSE than doing nothing** (F36-HYBRID-VERDICT, F43). They are
listed for diagnostics, not for competing. The observation flags are mandatory for them —
`verify_bundle_observation` refuses a mismatch rather than feeding the policy wrong features.

Other useful flags: `--ai-type rule|rl|sl|fusion|etc`, `--heartbeat-sec`, `--recv-timeout-sec`,
`--packet-monitor-interval-sec`, `--debug-action-repeat`,
`--server-silence-warn-sec N` (default 5, 0=off), `--server-silence-reconnect-sec N`
(default 0 = warn only; see the runbook before enabling).

---

## 4. Watching it live

- **Terminal**: `--packet-monitor` renders RX/TX counters, plane validity and last packets.
  Healthy looks like `MT_CMD ≈ MT_PlaneInfo / 2` (one command per own/enemy pair at
  `--action-repeat 1`).
- **3D**: `D:\BattleServer_V0.3_Full\DogFightViewer.exe` — **must be launched by hand from the
  unlocked physical console.** It fails with a D3D11 swap-chain error from any
  automation/non-interactive context (F40-VIEWER-D3D11).
- **Replays**: `python tools\dashboard.py --training-logdir artifacts\dashboard --logdir logs --port 7860`

---

## 5. CUTOFF — running the organizers' binary

Binary: `D:\AIP1\AIP\unreal_bt_client.exe` (fallback copy under `컷오프모델-…\컷오프모델\`).

```powershell
D:\AIP1\AIP\unreal_bt_client.exe --server-ip 127.0.0.1 --server-port 9999 `
  --team-name EasyModeCutoff --server-timeout-sec 5
```

Its full flag set: `--server-ip --server-port --team-name --server-timeout-sec --ai-type
--simulation-state --heartbeat-sec --command-delay-sec --recv-timeout-sec --action-repeat
--ownship-force-side --target-force-side --debug-action-repeat --help`.

`--ai-type rl|fusion` only changes an int in the heartbeat — **it has no learned component at
all**. `--server-timeout-sec` is warn-only, which is why our silence watchdog defaults the same
way.

---

## 6. CUTOFF — scoring against it locally (headless, no server)

```powershell
# single config, N=30 -- shipping config vs the cutoff
python scripts\eval_vs_cutoff.py --ownship-backend vptrack --target-backend cutoff `
  --scenario-mode match_base --episodes 30 --seed 0 `
  --ownship-vptrack-throttle 1 --ownship-vptrack-range-m 4000 --ownship-vptrack-los-deg 60 `
  --out-csv artifacts\eval\cutoff_ship_4000_60.csv

# tail-to-tail instead of the default beam merge
#   NOTE: alpha_deg is a SEPARATION sweep in match_base, NOT an angle. Use --match-los-deg.
python scripts\eval_vs_cutoff.py --ownship-backend vptrack --target-backend cutoff `
  --scenario-mode match_base --episodes 30 --match-los-deg 180 `
  --ownship-vptrack-throttle 1 --ownship-vptrack-range-m 4000 --ownship-vptrack-los-deg 60 `
  --out-csv artifacts\eval\cutoff_ship_tailtotail.csv

# every backend/variant in parallel
python scripts\sweep_vs_cutoff.py --episodes 30 --jobs 4
python scripts\sweep_vs_cutoff.py --episodes 30 --jobs 4 --only env_r4000_l60 vptrack_throttle bt

# rank results against the organizers' bar
python scripts\summarize_cutoff.py "artifacts/eval/cutoff_*.csv"
```

Cutoff-specific extras: `--cutoff-action-repeat N` (default 6, its competition default; pass 1 to
remove the decision-rate asymmetry), `--cutoff-exe PATH`, `--cutoff-no-g-limit` (off by default —
our side is G-limited, so leaving the opponent unlimited would let it pull G we are denied).

Sweep job names: `bt`, `vptrack_2200_35`, `vptrack_2000_45`, `vptrack_throttle`,
`vptrack_defensive`, `vptrack_corner`, `thr_corner`, `thr_defensive`, `thr_corner_def`,
`thr_2200_35`, `thr_2000_45`, `env_r4000_l60`, `env_r6000_l90`, `env_r4000_l45`, `env_r2500_l90`,
`rl_v10`, `hybrid_v10`, `hybridvp_v10`, `hybridgated_v10`.

**Reading `summarize_cutoff`:** `env%` is the env's own verdict; `rule%` re-adjudicates the
altitude floor the way RULES Sec 5 states it (the env books a *target* below-floor as a draw but
*ours* as a crash, so it under-reports wins against a crash-prone opponent); `earned%` counts only
kills we actually made. **`rule%` is the number to read against the organizers' bar; `earned%` is
the honest one.**

---

## 7. Local 1v1 without any server

```powershell
# quick sanity check between two backends
python run_local_dogfight.py --ownship-backend vptrack --target-backend bt --save-log

# statistical eval (backends: rl|bt|vptrack|hybrid|hybrid_vptrack|hybrid_gated|fixed)
python scripts\eval_v5_vs_bt.py --ownship-backend vptrack --target-backend bt `
  --scenario-mode match_base --episodes 30 --seed 0 `
  --ownship-vptrack-throttle 1 --ownship-vptrack-range-m 4000 --ownship-vptrack-los-deg 60 `
  --out-csv artifacts\eval\ship_matchbase.csv
```

Scenario modes: `match_base` | `match_tiebreak` | `two_circle_headon` | `obfm_offensive` |
`obfm_defensive`.

**Never adopt or reject a BT change on a symmetric run** — score it through the peer rig:

```powershell
python scripts\setup_peer_bt.py --from-git HEAD        # peer = unmodified tree
python scripts\setup_peer_bt.py --verify
python scripts\eval_v5_vs_bt.py ... --target-bt-dll bt_peer\AIP_BASE_target.dll
```

---

## 8. Support commands

```powershell
# DQ / reconnect rehearsal against a real socket (start the loopback server first)
python scripts\_dq_loopback_server.py --port 9999 --duration-sec 90 `
  --silence-every-sec 20 --silence-for-sec 8          # real outages, no firewall needed
python scripts\live_dq_rehearsal.py --server-ip 127.0.0.1 --server-port 9999 `
  --duration-sec 60 --silence-warn-sec 5 --silence-reconnect-sec 0
#   --induce-faults is a NO-OP on loopback (Windows Firewall does not filter 127.0.0.1).

# which BT nodes actually execute
$env:AIP_BT_GATE_TRACE = "artifacts\eval\trace.csv"
python scripts\eval_v5_vs_bt.py --ownship-backend bt --target-backend bt `
  --scenario-mode match_base --episodes 2 `
  --ownship-bt-dll AIP_BASE_gatetrace.dll --target-bt-dll AIP_BASE_gatetrace_target.dll `
  --out-csv artifacts\eval\trace_result.csv
python scripts\audit_unreachable_nodes.py artifacts\eval\trace.csv

# build + verify the submission package
python scripts\package_release.py --zip --out D:\pkg --force

# guards
python scripts\verify_resilience.py
python scripts\verify_report_fixes.py
python scripts\verify_match_spawn.py
python scripts\verify_live_frame_fix.py
```
