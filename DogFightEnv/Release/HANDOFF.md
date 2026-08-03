# HANDOFF -- real_eagle (AIP TGC 2026)

Last updated: 2026-08-01. Working dir for every command below: `DogFightEnv/Release/`
(PowerShell, `aip` conda env). This file is the operational critical path; the "why"
lives in `References and Manuals/` (COMPETITION_PLAN.md, PROJECT_ANALYSIS.md, etc.).

--------------------------------------------------------------------------------
## TL;DR -- do these three, in order
1. **Rebuild the BT DLL and redeploy it** (mandatory -- see the coupling warning below).
2. **Run v5** (`experiments/real_eagle_v5.yaml`) and babysit with the early-tells checklist.
3. **Validate** BT + hybrid locally once v5 yields a stable bundle, then repoint the submission.

Nothing here has been validated by a training run or sim yet (it was all built on a Mac
with no torch/ray and no Windows DLLs). Everything is *correct-by-construction* -- compiles,
parses, name-consistent, compliant -- but the proof is this run on your box.

--------------------------------------------------------------------------------
## !!! PRECONDITION: rebuild before ANYTHING that loads the BT
`Rule_forTraining.xml` now references a NEW C++ node, `Task_GunTrack`. The currently
deployed `AIP_BASE*.dll` (built 2026-07-15) does NOT know that node. Loading the current
DLL against the new XML makes `bt_factory` throw "unknown node" during tree construction ->
the BT opponent fails to load. This breaks BOTH:
  - v5 training (the target BT opponent won't construct), AND
  - a BT-only submission (`MODE="bt"`).
So the rebuild is universal. Do it first.

--------------------------------------------------------------------------------
## STEP 1 -- Rebuild AIP_DCS and redeploy the DLLs

Build (VS "Build Solution" on Debug|x64, or):
```
msbuild ..\..\AIP_DCS\AIP_DCS.sln /p:Configuration=Debug /p:Platform=x64
```
Build output: `AIP_LIB\bin\debug.x64\AIP_DCS.dll` (DynamicLibrary; default project name --
confirm the exact path from the build log's final "->" line). It builds `Task_GunTrack.cpp`
now (added to the .vcxproj + .filters this session).

Deploy = manual copy over BOTH consumer names, backing up first (the project's convention):
```
copy DogFightEnv\Release\AIP_BASE.dll        DogFightEnv\Release\AIP_BASE.dll.bak
copy DogFightEnv\Release\AIP_BASE_target.dll DogFightEnv\Release\AIP_BASE_target.dll.bak
copy AIP_LIB\bin\debug.x64\AIP_DCS.dll       DogFightEnv\Release\AIP_BASE.dll
copy AIP_LIB\bin\debug.x64\AIP_DCS.dll       DogFightEnv\Release\AIP_BASE_target.dll
```
Sanity: a BT-vs-BT smoke run must now construct the tree without a `bt_factory` error:
```
python run_local_dogfight.py --ownship-backend bt --target-backend bt --save-log --max-engage-time 90
```
If it errors on an unknown node, the rebuild/deploy didn't take -- fix before Step 2.

What the rebuild activates (both at once):
  - `Task_GunTrack` -- gun-solution hold: pure-pursuit aim + speed-matching throttle, so the
    jet settles in the 150-914 m WEZ band instead of `Task_Pure`'s fixed-0.7 sailing through.
  - H1 energy-guard threshold `1.2 -> 1.4` (Gate 3) -- a marginal energy edge now uses the
    Gate 4 offensive selector instead of committing to a flat angles turn.

--------------------------------------------------------------------------------
## STEP 2 -- Run v5

```
python scripts\run_experiment.py experiments\real_eagle_v5.yaml --dry-run   # validate wiring
python scripts\run_experiment.py experiments\real_eagle_v5.yaml            # the real run
```
- v5 is a **fresh tag** (v4 is NaN-poisoned and unresumable). **Do NOT `--resume` v4.**
- Fixes carried in code (not YAML): `grad_clip=1.0`/global_norm in `train_curriculum.py`
  (THE NaN fix); reward finite-guard + 150 clamp in `student/my_reward.py`; two-circle
  episode length `18000 -> 12000` in `student/my_curriculum.py`.
- Curriculum (13 stages): 0 flight_survival, 1 target_pursuit, 2 wez_approach,
  3 autopilot_pursuit, 4 obfm_offensive, 5 obfm_defensive, 6 habfm_beam_merge,
  7-11 two_circle_headon a000/a045/a090/a135/a180, 12 full_dogfight (1500 iters).
- Progress source of truth: `artifacts/curriculum/real_eagle/v5/training_log.csv` and
  `curriculum_state.json` (they flush every iter; the console lags due to buffering).
- Expect multi-day wall-clock (single-process `num_env_runners=0`; full_dogfight is the long tail).

--------------------------------------------------------------------------------
## STEP 3 -- Babysit: early-tells checklist (decide fast)
Read `training_log.csv`. Tick these:
- [ ] Stages 0-2 complete cleanly in ~1-2 h (win ~1.0). If stage 0 misbehaves, suspect the rebuild/opponent.
- [ ] **Stage 3 `ep_min_distance` stays physical** (hundreds-thousands of m, NO million-meter
      blow-up). This is the clearest "numerical instability fixed" signal.
- [ ] **Stage 4 passes iter ~250 with a finite `reward_mean`** (v4 went `nan` here). This confirms
      the NaN is dead -- the headline win.
- [ ] **First `win_rate > 0` at stage 4+.** If win rate is stuck at 0.0 through stages 4-6, the
      two-circle wall (7-11) will be brutal -- intervene early (see follow-ups).
Judge every stage on the four diagnostics together, not win rate alone:
`reward_mean`, `crash_rate`, `ep_min_distance`, `ep_wez_steps`.

--------------------------------------------------------------------------------
## STEP 4 -- Validate (once v5 has a stable bundle)
Pick the latest stage whose bundle looks healthy (finite, decent crash/win), e.g.
`artifacts/curriculum/real_eagle/v5/stage_<N>_<name>/final_bundle`.

BT (new tree) vs the RL policy -- the real test that the BT gun-track + XML edits help:
```
python run_local_dogfight.py --ownship-backend bt --target-backend rl ^
  --target-bundle-dir <stable_v5_bundle> ^
  --observation-mode custom --observation-module student.my_observation_v2 --save-log
```
-> `ep_wez_steps` should RISE vs the pre-edit tree (that is the gun-track fix paying off).

Hybrid (the actual submission artifact) vs BT:
```
python run_local_dogfight.py --ownship-backend hybrid --ownship-bundle-dir <stable_v5_bundle> ^
  --observation-mode custom --observation-module student.my_observation_v2 ^
  --target-backend bt --save-log
```

--------------------------------------------------------------------------------
## STEP 5 -- Wire the submission (`student/my_submission.py`)
- After validation, set `BUNDLE_DIR` to the chosen stable v5 bundle. It currently still points
  at `v4/stage_3_autopilot_pursuit/final_bundle` (a **100%-crash** policy -- placeholder only).
- Strategy is set: `MODE="hybrid"`, `HYBRID_MODE="residual"`, `RESIDUAL_SCALE=0.35` (BT ~65% / RL ~35%).
- **Interim, before a stable v5 bundle exists: submit `MODE="bt"`** (after the rebuild).
  WARNING: the bundle-health gate only blocks NaN/Inf weights (stages 4-7). The stage_3 bundle
  is finite-but-degenerate, so the gate PASSES it and would fly a 100%-crash residual. Do not
  run rl/hybrid submission until BUNDLE_DIR points at a validated bundle.
- Confirm the live server IP with the organizers before submitting (`SERVER_IP` currently
  `221.151.77.208`; `startup_command.txt` shows `10.185.16.247`). Network instability x2 = DQ.

--------------------------------------------------------------------------------
## What changed this session (inventory + how to revert)
| File | Change | Rebuild? | Revert |
|---|---|---|---|
| `train_curriculum.py` | `grad_clip=1.0`/global_norm after `build_algorithm_config` | no | delete the one `config.training(...)` line |
| `student/my_reward.py` | reward finite-guard + 150 clamp + `reward_clip` knob | no | `reward_clip: 0.0` disables the clamp; guard is harmless |
| `student/my_curriculum.py` | two-circle `episode_step_limit 18000 -> 12000` | no | change back to 18000 |
| `experiments/real_eagle_v5.yaml` | new stability-corrected run config | no | delete file |
| `student/inference_providers.py` | `verify_bundle_health` / `require_healthy_bundle` | no | additive; unused unless called |
| `student/my_submission.py` | health-gate wiring, `STRICT_BUNDLE_HEALTH`, corrected comment | no | remove the `require_healthy_bundle` block |
| `Rule_forTraining.xml` | Gate 2.5 GunSolutionHold; H1 energy `1.2 -> 1.4` | see below | delete the Gate 2.5 Sequence; set Ratio back to 1.2 |
| `AIP_DCS/.../Task_GunTrack.{h,cpp}` + 5 wiring edits | new BT node | **YES** | remove node + registration + Gate 2.5 caller |

Note: `Rule_forTraining.xml` and the `Task_GunTrack` C++ node are a **matched pair** -- the XML
won't load without the rebuilt DLL. If you want to run WITHOUT rebuilding, revert Gate 2.5 to
`<Task_Pure name="Gun_TrackPure" BB="{BB}"/>` (the H1 threshold change is fine on the old DLL).

## Known-broken -- do NOT use
- `artifacts/curriculum/real_eagle/v4/**` bundles: stages 0-2 trivial-opponent-only, stage 3
  100% crash, stages 4-7 NaN-diverged. None competition-usable. Diagnostic artifacts only.
- Do not `--resume` v4 (status "failed", NaN state).

## Open follow-ups (queued levers, not yet applied)
- **If stage 3 still shows elevated crash** after grad_clip: enable the energy term on the
  built-in pursuit stages in `student/my_curriculum.py` (counters the idle-throttle stall).
  Held back deliberately -- one variable at a time this round.
- **If the two-circle stages (7-11) stall** below win_rate 0.70: loosen `grad_clip` toward ~10,
  and/or reconsider the disabled two-circle geometry guard.
- Further BT tuning is empirical -- validate each change against a NON-mirror opponent
  (BT-vs-RL or asymmetric OBFM starts), never BT-vs-BT symmetric score (it is a mirror artifact).

## Guardrails (compliance -- keep it this way)
- `src/dogfight/**` is a hard no-edit boundary. Route new logic through `student/**`,
  `experiments/*.yaml`, or the entry scripts (`train_*.py` / `run_*.py`).
- Never rename/move/delete runtime assets (`AIP_BASE*.dll`, `JSBSimAIPLib.dll`, Rule XMLs,
  `aircraft/`, `engine/`, `scripts/*_cruise.xml`) -- content edits only.
- Preserve `src/dogfight/unreal/protocol.py`'s wire format. Keep `--action-repeat 6`
  (the 1/6 s compute-budget rule) matched to training `step_ratio=6`.
