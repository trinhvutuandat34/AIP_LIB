# AIP TGC 2026 — Project Structure

> 2026 AI Pilot Top Gun Challenge: a reinforcement-learning competition where teams
> train an RL agent to fly an F-16 in 1v1 dogfights (JSBSim flight dynamics + Ray
> RLlib), validate locally, then connect the trained policy to a live Unreal Engine
> battle server to compete against other teams. See [COMPETITION_RULES.md](COMPETITION_RULES.md)
> for the official rules/schedule/scoring and [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) for how
> the system works internally (MDP, reward, curriculum, architecture). This file maps *where
> things are*.

> **Root moved.** This project originally lived at `D:\AIP_TGC_2026\`; it now lives at
> `D:\AIP\AIP_LIB\`. Mappings from the old layout: `Update\BehaviorTree\AIP_DCS\` → `AIP_DCS\`;
> `Update\BattleViewer\...\BattleServer_V0.2\` → `BattleServer_V0.2\`;
> `Update\Reinforcement_learning_environment\Release_260529\` → `DogFightEnv\Release\` (the
> date suffix was dropped). **Not present in this checkout**: `Day_1_Lecture_Materials\`,
> `Day_2_Lecture_Materials\`, `AIP_LIB.zip`, `Update LOG.xlsx`, and
> `교전 뷰어 사용 메뉴얼.pdf` — these were the original source materials `COMPETITION_RULES.md`
> and `PROJECT_ANALYSIS.md` were extracted from, but none of them are on disk here. Where those
> two files cite a path under `Day_1_Lecture_Materials/` or `Day_2_Lecture_Materials/`, treat it
> as a citation to source material, not a path that resolves on this machine.

> **A second, separate full copy of this project also exists** at
> `C:\Users\User\Desktop\AIP\AIP_LIB\` — discovered 2026-07-07 while tracing a hardcoded path in
> the native BT DLL's source (see `PROJECT_ANALYSIS.md` §5.2 / `COMPETITION_PLAN.md` §5.1.2). It
> has not been touched by any work described in these docs; `D:\AIP\AIP_LIB\` remains the one
> being actively edited. Worth deciding whether to sync, archive, or delete the Desktop copy so
> the two don't silently diverge further.

> **These five docs moved off the repo root, permanently, 2026-07-15/16.** They now live at
> `DogFightEnv/References and Manuals/`, not `D:\AIP\AIP_LIB\` root — see the "Current state"
> entry dated 2026-07-16 below for why (a boundary-violation fix was executed as a full
> pristine-template overwrite, which moved/lost the root copies; the team decided to keep
> `References and Manuals/` as the permanent home rather than restore root copies). The top-level
> layout diagram immediately below reflects the CURRENT (post-move) reality, not the older
> root-anchored layout these docs originally described. **A sixth doc, `COMMAND.md`, joined the
> set later on 2026-07-16** — it was authored directly in `References and Manuals/`, not moved
> there, so it isn't part of the move history above, but it's part of the same doc set now.

## Top-level layout (current, `D:\AIP\AIP_LIB\` — verified 2026-07-16)

```
AIP_LIB\
├── Anaconda3-2025.12-2-Windows-x86_64.exe, VSCodeUserSetup-x64-1.127.0.exe,
│   Visual Studio Installer.lnk  <- installers, not project content
├── AIP_DCS\                     <- native C++ BT DLL source (§3)
├── DogFightEnv\
│   ├── Release\                 <- main RL codebase (§4); Rule_forTraining.xml lives here (§4.1)
│   └── References and Manuals\  <- the six root docs (CLAUDE.md, COMPETITION_RULES.md,
│                                    PROJECT_ANALYSIS.md, PROJECT_STRUCTURE.md,
│                                    COMPETITION_PLAN.md, COMMAND.md) PLUS the Korean reference
│                                    manuals, HTML/docx (§1). Permanent home as of 2026-07-16
│                                    (COMMAND.md added later the same day), not root.
├── BattleServer_V0.2\            <- packaged Unreal battle viewer/server build (§2)
├── Windows\                      <- a second packaged Unreal build (§2)
├── bin\, PropertySheets\          <- legacy MSBuild plumbing for a broader library ecosystem
│                                    mostly absent from this checkout (see CLAUDE.md)
└── .vs\, .vscode\                 <- IDE state, not source
```

**No longer at root** (moved 2026-07-15/16, see the dated "Current state" entry below):
`CLAUDE.md`, `COMPETITION_RULES.md`, `PROJECT_ANALYSIS.md`, `PROJECT_STRUCTURE.md` (this file),
`COMPETITION_PLAN.md`, `Rule_forTraining.xml` (the loose top-level copy — the runtime copy at
`DogFightEnv\Release\Rule_forTraining.xml` is unaffected and is the one that matters, §4.1),
`startup_command.txt`, `reward_function_skeleton.py`. All of these now live under
`DogFightEnv\References and Manuals\` instead — see §1.

`startup_command.txt` records the last real connectivity test:
```
cd 'D:\AIP\AIP_LIB\DogFightEnv\Release'
conda activate aip
python run_unreal_inference.py --mode bt --team-name TestLaptop --server-ip 10.185.16.247 --server-port 9999
```
The server IP here (`10.185.16.247`, a private/LAN address) differs from the one hardcoded in
`student/my_submission.py` (`221.151.77.208`) — treat the former as a local/practice server and
the latter as presumed-production. **Don't assume either is current** without checking the
latest organizer announcement.

## 1. `DogFightEnv\References and Manuals\`

The on-disk counterpart to what earlier notes called `Day_2_Lecture_Materials/` — **and, since
2026-07-16, also the permanent home of this doc set itself** (`CLAUDE.md`, `COMPETITION_RULES.md`,
`PROJECT_ANALYSIS.md`, `PROJECT_STRUCTURE.md`, `COMPETITION_PLAN.md`, `COMMAND.md`). Contains
HTML/docx manuals, several markdown reference docs, and no `.pptx`/`.pdf` originals in this
checkout:

| File | Description |
|---|---|
| `COMMAND.md` | Every command line the project uses (setup, dry-run, training, checkpoint resume, dashboard, local verification, live Unreal inference/submission), each with an explanation of what it does — added 2026-07-16 |
| `2026_aip_rl_manual_rev8.html`, `2026_aip_rl_manual_rev9.html` (under `AIP RL 매뉴얼/`) | Main RL environment manual, two revisions |
| `student_manual_rev0.html`, `student_manual_rev1.html` (under `STUDENT 스크립트 매뉴얼/`) | Student manual (file-authoring contracts), two revisions |
| `reward_design_concept_slides.html` (under `보상함수 설계 매뉴얼/`) | Reward-shaping design concepts (LOS/ATA/AA/WEZ) |
| `tutorial_release_student_sac_local_viewer_manual.html` (under `로컬 뷰어 매뉴얼/`) | Tutorial: release + student SAC + local viewer |
| `engagement_log_dashboard_guide.html` (under `교전 대시보드 매뉴얼/`) | Engagement-log dashboard guide |
| `AIP_경진대회_매뉴얼_rev7.md` | Day 2 deck content, extracted to markdown — workflow guide, not rules (confirmed by reading in full) |
| `Release_매뉴얼.docx`, `DogFightEnv_Log_Check_CLI_YAML_Guide.docx` | Release usage + log/dashboard CLI guides |
| `AI_pilot_challenge.md`, `AERIAL_COMBAT_BT_GUIDE_DETAILED.md`, `BFM_ACM_Reward_Engineering_Reference.md` | Competition overview + BT tactics design reference + BFM/ACM reward-engineering reference (source material behind the BT tactics expansion and `student/reward_lib.py`) |
| `260708_RL_Environment_patch_note.md` | Custom-observation bundle-restore patch note |
| `GeoMathUtil.py`, `Rule_forTraining.xml`, `reward_function_skeleton.py`, `startup_command.txt`, `README.md` | Reference copies — the ones that actually matter at runtime are the `DogFightEnv/Release/` copies, not these |

The original `Day_1_Lecture_Materials/` (kickoff deck + videos) and the rest of
`Day_2_Lecture_Materials/` (the screenshot, `tools.zip`) are **not present anywhere in this
checkout** — `COMPETITION_RULES.md` and `PROJECT_ANALYSIS.md` were written from them, but treat
their citations as historical rather than browsable unless someone re-adds those source files.
Confirmed 2026-07-15 by searching the whole drive for `*.pptx`/`*.mp4` — zero hits.

## 2. `BattleServer_V0.2\` and `Windows\` — packaged Unreal builds

Both are packaged (cooked) Unreal Engine output — `DogFightViewer.exe` + `Engine\Binaries` +
`Engine\Config`, no engine source in either. They have near-identical contents (same
`DogFightViewer.exe`/`Engine` layout, same `Manifest_*Files_Win64.txt` pattern); which one is
the current/intended build for competition use hasn't been confirmed — check file timestamps or
ask the organizers before assuming either is stale.

## 3. `AIP_DCS\` (native BT DLL source)

Native C++ Visual Studio project (`AIP_DCS.sln` / `.vcxproj`, single-project solution) — source
for the **Behavior Tree DLL**, i.e. the rule-based (non-RL) opponent/baseline AI. See
`CLAUDE.md` for the detailed breakdown: exported functions (`Step`, `CreateBehaviorTree`, etc.),
the `BehaviorTree\BT_Content\` node layout (`Decorator\`/`Service\`/`Task\`/`BlackBoard\`), and a
known gap where several maneuver node `.cpp` files (`JinkingTurn`, `HighYoYoUp`, `LunchMSL`,
`WeaponSelect`) are missing from source while their `.obj` build leftovers remain.

Builds into `AIP_BASE.dll` / `AIP_BASE_target.dll`, consumed by `DogFightEnv\Release\` as the
default BT opponent (training) and the BT-only submission path (`Rule_forTraining.xml`).

## 4. `DogFightEnv\Release\` — the core workspace

### 4.1 Root

| Item | Role |
|---|---|
| `train_rllib.py` | Single-stage PPO/SAC training entry point |
| `train_curriculum.py` | Staged curriculum training entry point |
| `run_local_dogfight.py` | Local 1v1 validation (no Unreal needed) — supports `--save-log` for Tacview-style replay CSVs |
| `run_unreal_inference.py` | Connects a trained policy / BT / hybrid to a live Unreal server (competition submission path) |
| `DogFightEnvWrapper.py`, `FighterSim.py`, `JSBSimWrapper.py`, `GeoMathUtil.py` | Simulation/env wrapper glue around JSBSim |
| `AIP_BASE.dll`, `AIP_BASE_target.dll` | Compiled BT opponent DLLs (from `AIP_DCS\`) |
| `JSBSimAIPLib.dll` | JSBSim flight-dynamics engine binding |
| `Rule_forTraining.xml`, `Rule.xml`(`.bak`) | BT rule configs (team-specific rules go in sibling `Rule_real_eagle.xml`-style files) |
| `aircraft\` | JSBSim aircraft configs: `f15\`, `f16\`, `fa50\` (XML + systems defs) |
| `engine\` | JSBSim engine configs (`F100-PW-229`, `F404-GE-402`, etc.) |
| `assets\` | 3D meshes (`meshes\f16`) |
| `scripts\` | JSBSim cruise scripts (`f16_cruise.xml`, etc.), **not** `scripts\run_experiment.py` |
| `RLLibLstm\` | Patch set to add LSTM/RNNSAC support to Ray 2.54 RLlib (advanced/optional path) |
| `requirements.txt` | `ray[rllib]==2.54.0`, `torch>=2.3,<3.0`, `gymnasium>=1.0,<2.0`, `numpy==2.2.6`, `pymap3d==3.1.0`, `PyYAML>=6.0,<7.0`, `filelock==3.18.0`, `cloudpickle==3.1.1` |
| `README.md` | Full usage manual (Korean) — training, curriculum, checkpoints, dashboard, submission |
| `artifacts\` | **Exists now, but placeholder-only** — see "Current state" below |

### 4.2 `src/dogfight/` — shared library code (students generally don't edit)

```
src/dogfight/
├── config.py
├── envs/
│   ├── single_agent_env.py     <- the Gymnasium env (DogFightWrapper)
│   ├── observation.py          <- built-in observation modes (e.g. tactical16)
│   ├── reward.py                <- default/base reward implementation
│   └── termination.py          <- episode end-condition logic
├── ai/
│   ├── curriculum.py            <- built-in 15-stage curriculum (flight_survival → full_dogfight)
│   ├── action_provider.py, rl_action_provider.py, bt_action_provider.py, hybrid_action_provider.py
│   ├── bt_rule_manager.py, native_bt.py
│   ├── rllib_utils.py, checkpoint_io.py, callbacks.py
│   ├── student_hooks.py        <- loads student reward/observation/curriculum modules
│   ├── dashboard_logger.py, policy_probe_logger.py, engagement_replay_logger.py, training_record.py
│   └── training/config_io.py
├── sim/state_schema.py          <- StateIndex — field layout for aircraft state vectors
└── unreal/
    ├── client.py                 <- UnrealAIPilotUDPClient
    ├── protocol.py, policies.py  <- wire protocol + ProviderCommandPolicy
```

### 4.3 `student/` — **files students are meant to edit**

| File | Contract |
|---|---|
| `my_reward.py` | Define `MY_REWARD_CONFIG` (dict) + `compute_reward(...) -> (total_reward, components)` |
| `my_observation.py` | Optional. Define `OBSERVATION_SIZE` + `build_observation(...)` for a custom obs vector |
| `my_curriculum.py` | Optional. Custom curriculum stages |
| `my_train.py` | Optional thin training wrapper (YAML path via `scripts/run_experiment.py` is the recommended route) |
| `my_submission.py` | Competition submission entry point — sets `TEAM_NAME`, `BUNDLE_DIR`, `SERVER_IP`, and `MODE` (`rl`/`bt`/`hybrid`) |

### 4.4 `experiments/` — YAML experiment configs (student-facing)

`student_sac_mlp.yaml`, `student_ppo_mlp.yaml`, `student_mixed_initial_sac_mlp.yaml`,
`student_sac_lstm.yaml`, `student_ppo_lstm.yaml`, `student_mixed_initial_sac_lstm.yaml` — run
via `scripts/run_experiment.py <yaml> [--dry-run]`. MLP variants are the normal starting point;
LSTM variants need the `RLLibLstm/` patch applied.

### 4.5 `tools/` — dashboards

- `dashboard.py` — unified server: `Training` tab (reads `metrics.jsonl`) + `Replay` tab
  (Tacview-style CSV replay)
- `dogfight_dashboard/`, `training_dashboard/`, `web_log_viewer/` — component implementations
  behind the unified dashboard

---

## Competition pipeline (how the pieces connect)

```
1. Edit student/my_reward.py (+ optionally my_observation.py / my_curriculum.py)
2. Configure experiments/*.yaml (or CLI flags on train_rllib.py / train_curriculum.py)
3. Train  →  python scripts/run_experiment.py experiments/student_sac_mlp.yaml
              outputs: artifacts/models/<name>/<tag>, artifacts/logs/..., artifacts/checkpoints/...
4. Inspect →  tools/dashboard.py (Training metrics + Replay viewer)
5. Validate locally → run_local_dogfight.py --ownship-backend rl --ownship-bundle-dir <bundle> --target-backend bt --save-log
6. Submit  →  student/my_submission.py (or run_unreal_inference.py) connects the bundle/BT/hybrid
              to the live Unreal server (DogFightViewer.exe / BattleServer) for competition matches
```

## Current state (verified 2026-07-16 — supersedes conflicting claims below about
`src/dogfight/**`, `student/my_reward.py`, `student/my_curriculum.py`, and `Rule_forTraining.xml`)

- ⚠️➡️✅ **2026-07-15: accidental full-tree revert, then recovered — but not 100% back to the
  2026-07-14 state.** A session was found to have edited `src/dogfight/**` directly, violating the
  hard no-edit boundary (team policy, not a `COMPETITION_RULES.md` requirement). The user's fix for
  that violation was executed as a **wholesale pristine-template overwrite** rather than a scoped
  revert of just the offending edits: every file whose *path* exists in the original Release
  distribution template got silently overwritten back to template content (one bulk mtime), while
  files that only exist because the team added them (unique names, no template counterpart)
  survived untouched. This clobbered roughly a week of unrelated, validated work that happened to
  share a path with the template — not just the one violation.
  - **Confirmed reverted**: `src/dogfight/config.py` (WEZ phase-widening → back to a flat single
    cone), `src/dogfight/envs/reward.py` (crash-routing fix gone), `src/dogfight/envs/termination.py`
    (range-based two-circle guard → back to the unpassable ATA-limit guard), `student/my_reward.py`
    / `my_curriculum.py` / `my_observation.py` / `my_train.py` / `my_submission.py` (all back to
    bare starter templates), `DogFightEnv/Release/Rule_forTraining.xml` (back to the 2-branch
    `Task_Empty` stub — wiring the entire BT tactics expansion out of the active tree even though
    every `Task_*.cpp` source file survived), `AIP_BASE.dll`/`AIP_BASE_target.dll` (reverted to a
    stale pre-expansion binary registering only 9 of the ~30 node types the current source has),
    and the five root docs (moved to `References and Manuals/`, see the note near the top of this
    file).
  - **Confirmed safe**: `experiments/real_eagle_v1–v4.yaml`, `artifacts/models/real_eagle/`,
    `artifacts/curriculum/real_eagle/` (trained weights/checkpoints intact), `student/reward_lib.py`
    / `my_observation_v2.py` / `inference_providers.py` (uniquely-named, no template counterpart to
    overwrite them), and every `AIP_DCS/BehaviorTree/BT_Content/Task/Task_*.cpp` source file
    (`AIP_DCS/` was never in scope of the revert — see `CLAUDE.md`).
- ✅ **2026-07-15/16: recovered what could be recovered, deliberately left the rest.**
  - `student/my_reward.py`, `my_curriculum.py`, `reward_lib.py` — reconstructed via **decompiling
    stale Python bytecode caches**: `__pycache__/*.cpython-313.pyc` survived the revert because the
    `aip` training env is 3.11 and only ever writes `cpython-311` caches, so a one-off run with a
    different interpreter (anaconda base env, 3.13) left an untouched snapshot dated 2026-07-12
    03:36. Most content recovered byte-exact (disassembled with `dis`/`marshal`, no working
    decompiler exists for 3.13 bytecode yet); the crash-routing fix and the v4 5-alpha two-circle
    ladder rebuild postdate that snapshot, so those were reconstructed fresh from
    `real_eagle_v4.yaml`'s own header-comment description instead. Verified via
    `python -m py_compile` + a clean `run_experiment.py --dry-run` against `real_eagle_v4.yaml`.
  - `Rule_forTraining.xml` — XML has no bytecode-equivalent, so this was rebuilt from the surviving
    design plan (`~/.claude/plans/i-have-aerial-combat-bt-guide-detailed-m-serene-duckling.md` —
    outside the project directory, so the revert never touched it), cross-checked against every
    surviving `Task_*.cpp`/`DECO_*.cpp` file's own design-intent comments (which independently
    reference the same Gate 0–4 structure by name). Rebuilding + testing this surfaced two more,
    **unrelated, pre-existing** `AIP_DCS` build breaks (not caused by the revert or by this
    reconstruction): `CPPBehaviorTree.h`/`.cpp` called a nonexistent `IsInitialized()` (looked like
    abandoned WIP — fixed by adding the flag properly with real exception handling, which also
    fixes a latent bug where a bad Rule XML threw a C++ exception straight across the DLL boundary
    uncaught), and `AIP_DCS.vcxproj`/`.vcxproj.filters` were missing ~54 file entries (every new
    node's `.cpp` existed on disk and compiled standalone, but was never added to the project, so
    the linker never saw it — both files share a telltale mtime ~17 min after the main revert,
    distinct from every organically-timestamped `AIP_DCS` file). Built clean, **verified via two
    live `run_local_dogfight.py` BT-vs-BT runs** (once against a test-named DLL copy, once against
    the actually-deployed `AIP_BASE.dll`/`AIP_BASE_target.dll` post-deploy) — both completed the
    full episode with no crashes. **Deployed** to `AIP_BASE.dll`/`AIP_BASE_target.dll` 2026-07-15
    (user-confirmed) — the full BT tactics expansion is live again.
  - `student/my_submission.py` (+ `run_unreal_inference.py`/`run_local_dogfight.py`, which share
    its provider-construction code) — the revert had put all three back onto the stock
    `RLActionProvider`/`HybridActionProvider`, silently reintroducing the throttle-remap bug
    `project_hybrid_inference_fixes_2026_07_14` had already fixed once (RL throttle never
    remapped `[-1,1]→[0,1]` at inference). Rewired onto
    `RemappedRLProvider`/`StudentHybridProvider`/`verify_bundle_observation`
    (`student/inference_providers.py`, which survived the revert untouched) and retargeted from
    the blank team01/v1 placeholder to real_eagle's actual
    `artifacts/curriculum/real_eagle/v4/stage_3_autopilot_pursuit/final_bundle`. Verifying this
    live surfaced a second, previously-undiscovered revert casualty of the same shape:
    `src/dogfight/sim/state_schema.py` had also lost `StateIndex.VX/VY/VZ` and its
    `velocity_xyz()` function (imported by `student/my_observation_v2.py`) — recovered byte-exact
    via the same bytecode-decompilation technique used for the WEZ-phase functions below. Both
    fixes verified together with a live 30-second `run_local_dogfight.py --ownship-backend hybrid
    --target-backend bt` run (full 1800 steps, no errors, tacview log saved), not just a compile
    check.
  - **Deliberately NOT restored (decision made 2026-07-16, don't re-raise without checking this
    first)**: `src/dogfight/config.py`'s `_WEZ_PHASES`/`wez_pursuit_multipliers()` and
    `envs/termination.py`'s range-based guard. Root cause: both are hardcoded platform methods with
    no plug-in hook — unlike `reward_module`/`observation_module`/`stages_module`, there's no
    `damage_module`/equivalent a student file can override, and the only way to reach them is
    either the hard `src/dogfight` boundary itself or the shared trainer scripts
    (`train_rllib.py`/`train_curriculum.py`'s `env_creator`). Checked for a Gymnasium-`Wrapper`
    composition alternative reaching training via a small new optional hook in `env_creator`
    (mirroring the existing `reward_module` pattern, ~6 lines, off by default) — the team declined
    it too, so **local training/eval's actual damage/health computation and the two-circle guard
    both still run the flat/disabled pre-fix logic** (not re-enabling the known-broken ATA guard;
    relies on `max_engage_time` truncation alone to bound a runaway-avoidance episode). This is a
    training-fidelity gap, not a competition-legality one — the live Unreal server scores
    independently of our local `update_damage()`.
  - **2026-07-16, later the same day — the reward side of this got a real partial fix.** Asked
    directly whether the real WEZ could be applied at all, investigation found the actual blocker:
    `update_damage()` calls `self._sim.deduct_health()` on the closed FighterSim object the instant
    it runs, mutating health before any student-space code sees the result — so win/loss *timing*
    is genuinely unfixable without crossing the boundary (confirmed, not just assumed). What *is*
    fixable: `student/my_reward.py`'s damage reward term no longer trusts the platform's flat-cone
    `ownship_damage`/`target_damage` — it now computes its own phase-aware estimate via two new
    `student/reward_lib.py` functions, `match_wez_phase()`/`wez_damage_estimate()` (reconstructed
    fresh from this doc's own Sec6.2 rule text, since no bytecode of the platform's equivalent
    survived, unlike `WEZ_PHASES` itself). An approximation in one more way beyond the boundary
    limit: `update_damage()` accumulates true per-tick damage across `step_ratio` (6) physics ticks
    per env step, but `compute_reward()` only ever sees the end-of-block state, so the estimate
    treats the whole 6-tick block as one `delta_t` at the final geometry. Verified via unit tests on
    every phase boundary (incl. the narrowest-qualifying-phase-wins rule) plus a live
    `run_local_dogfight.py` rollout. Both `WEZ_PHASES`/`wez_pursuit_multipliers()` (pursuit-shaping)
    and the new damage estimate now push the policy toward realistic WEZ play — only the platform's
    own damage/health number and the two-circle guard remain unfixed.
  - **2026-07-16, real competition scenario audit (user-shared screenshots confirming the actual
    Prelims/Finals/OBFM/HABFM spawn geometries) found two more revert casualties, both fixed the
    same day.** (1) `Rule_forTraining.xml`'s Gate 1 (`Task_JinkingTurn`/`Task_Evade`) had no
    angular awareness and was preempting Gate 2's purpose-built `Task_NoseToNoseTurn` for any
    close-range head-on merge, including the real Prelims starting range (2000-3000ft) — the most
    common opening in the whole competition. Fixed with a same-threshold (HCA<150°) exclusion on
    both nodes plus lowering `Task_NoseToNoseTurn`'s distance floor from 3000m to 500m — XML-only,
    no rebuild needed, verified live. (2) `single_agent_env.py`'s `_apply_obfm_initial_scenario()`
    (added 2026-07-11, after whatever point the revert's rollback target was pinned to) had been
    silently missing this whole time — `student/my_curriculum.py`'s `obfm_offensive` stage had
    already run 248 iterations against a neutral default spawn instead of the real 556m six-o'clock
    setup. No recoverable bytecode cache this time (both survivors postdate the revert). Fixed via
    a student-space Gymnasium Wrapper (`student/obfm_scenario_wrapper.py`, wired into
    `train_curriculum.py::env_creator()`) reconstructing the geometry from confirmed parameters
    rather than editing `src/dogfight/**` — verified end-to-end through the real `env_creator()`
    to produce 557.82m/4.63°/175.37°, matching the original confirmed numbers almost exactly.
  - **2026-07-16, later still — the fourth confirmed scenario (HABFM, ~496m/~91°/~91° symmetric
    beam merge) got its own curriculum stage, `habfm_beam_merge`.** It's mathematically the same
    family the surviving `_apply_two_circle_headon_initial_scenario()` already implements
    (`own_heading=side*alpha`, `target_heading=180+side*alpha` gives LOS=alpha on both sides for
    any alpha) — rather than back-solving that function's indirect `turn_diameter_ft`/`sin(alpha)`
    formula to hit exactly 496m, built a dedicated `student/habfm_scenario_wrapper.py` (same
    wrapper idiom as `obfm_scenario_wrapper.py`) parametrized directly by named real-world
    constants. New stage spliced into `student/my_curriculum.py::get_stages()` at index 6 (right
    after `obfm_defensive`, before the two-circle ladder) — 13 stages total now, up from 12.
    Verified end-to-end via `env_creator()` + `reset()`: 496.00m, 91.00°/91.00° LOS both sides,
    4572m/200 m/s, matching the confirmed screenshot numbers to the decimal.
    - Building it surfaced two real bugs, both fixed the same session. **(1) Wrapper-stacking
      AttributeError**: stacking the new wrapper around the already-wired
      `ObfmScenarioWrapper` broke `reset()` for **every stage, every mode** (not just habfm) —
      both wrappers read `self.env.config` unconditionally, which only worked for `Obfm` by
      accident of being the innermost wrapper; this Gymnasium version has no
      `Wrapper.__getattr__` forwarding, so `self.env` on the outer wrapper raised immediately
      instead of drilling through. Fixed both wrappers to use `self.unwrapped` (stack-order
      independent) instead of `self.env`. **(2) Leftover-config-key shadowing**: `obfm_offensive`
      (the stage paused mid-training, 248 iterations already run) had been spawning at
      `altitude_m=7000`/uncontrolled speed instead of the confirmed real preset
      (4572m/200 m/s) **since OBFM was first added on 2026-07-11** — `DEFAULT_ENV_CONFIG`'s
      `initial_scenario` dict carries generic leftover keys (meant for `two_circle_headon`) that
      the wrapper's `scenario.get(key, MY_DEFAULT)` was silently finding instead of falling back
      to its own default; the same bug zeroed out HABFM's entire LOS offset (`alpha_deg` leftover
      = 0.0) until caught by this session's own geometry verification. Fixed by having both
      `_obfm_stage()`/`_habfm_stage()` in `my_curriculum.py` set every key their wrapper reads
      explicitly, sourced from the wrappers' own constants — no longer trusting a fallback default
      to win against the base config's leftovers.
    - Inserting a stage mid-list (rather than appending) is safe for the already-in-progress v4
      run specifically because `curriculum_state.json`'s `current_stage` and per-stage status are
      keyed by **index**, and indices 0-5 (the only ones with real training history) are
      unchanged by this insertion — verified via a dry-run replay of the real (unmodified)
      `curriculum_state.json`. The one gap that didn't paper over: the old state file has no
      entry for the new highest index (`full_dogfight_v4` shifted from 11 to 12), which would
      `KeyError` on resume — fixed generally in `train_curriculum.py::_init_or_load_state()`'s
      resume branch, which now backfills a fresh `"pending"` entry for any `self.stages` index
      missing from the loaded state, making future stage insertions safe too, not just this one.
  - **2026-07-16, same session — the energy-aware reward term (flagged as a gap during this
    session's competition-readiness assessment) landed.** `student/reward_lib.py` gained two new
    functions: `specific_energy()` (`E_s = altitude_m + speed_mps^2/(2*9.80665)`) and
    `energy_advantage(...)` — a stateless, tanh-bounded [-1,1] differential of ownship's vs.
    target's specific energy. A rate-based `P_s` (dE_s/dt)
    term was considered and rejected: `compute_reward()` is a stateless per-step function with no
    env handle, so a rate would need a module-level "previous energy" that Ray's interleaved
    multi-worker envs would corrupt; the differential needs no cross-step state and is learnable
    from the existing 15-feature observation (ownship alt+speed, target speed, relative altitude
    already let the policy reconstruct both E_s values). Wired into `student/my_reward.py` as a
    new `"energy"` component, config keys `energy_scale`(default 0.0)/`energy_ref_m`(default
    1000.0) — inert by default, exactly like the existing `advantage_scale` pattern. Enabled at
    `energy_scale=0.05` (user's choice, via `_ENERGY_SCALE` in `my_curriculum.py`) on the
    neutral-merge stages only — `habfm_beam_merge` (6), the two-circle ladder (7-11), and
    `full_dogfight` (12) — left inert on the OBFM stages (position-dominated close-in drills) and
    the in-progress stage 4. Verified end-to-end through the real training path
    (`reward_module: student.my_reward`, exactly as `real_eagle_v4.yaml` sets it): OBFM stages
    resolve `energy_scale=None` → energy component `0.0`; the six enabled stages resolve
    `energy_scale=0.05` → nonzero, correctly-signed, purely-additive energy component.
  - **2026-07-16, same session — `COMMAND.md` created** (see §1) consolidating every command line
    the project uses (README.md's + this session's real_eagle-specific ones) with an explanation
    of what each does; `CLAUDE.md` updated to reference it and to fix a now-stale claim that only
    `positional_advantage()` was wired into `reward_lib.py` (it now also documents
    `energy_advantage()`).
  - Full detail in memory: `project_bulk_revert_regression_2026_07_15`,
    `project_v4_recovery_2026_07_15`, `project_bt_xml_reconstruction_2026_07_15`,
    `project_bt_headon_merge_fix_2026_07_16`, `project_habfm_curriculum_stage_2026_07_16`,
    `project_energy_reward_term_2026_07_16`.

## Current state (verified 2026-07-08 — supersedes the snapshot below)

- ✅ **2026-07-14 hybrid-inference bug hunt after 0-win practice matches** (BT+RL hybrid lost
  every practice match vs pure RL and pure BT; deep audit of the inference pipeline found and
  fixed four issues — details in `PROJECT_ANALYSIS.md` §5.1's callout). **Re-homed the same day
  to respect the `src/dogfight/**` hard no-edit boundary** (see the editing-boundaries note
  below and `CLAUDE.md`): the fixes originally landed in `src/dogfight/ai/*` were reverted to
  original and re-implemented in editable space — new `student/inference_providers.py` (which
  *subclasses/composes* the platform, never edits it) plus small wiring changes in the three
  inference entry scripts. Current homes:
  1. **Throttle unit-system bug (root-cause candidate)**: the stock `RLActionProvider` never
     applied training's `(throttle+1)/2` remap (`single_agent_env._to_sim_action`), so RL
     throttle hit the sim/wire raw — and its own `clip_action` floored every raw output ≤0 to
     engine-idle 0. Fixed by `RemappedRLProvider` (`student/inference_providers.py`), a
     **subclass** that calls the inherited pre-clip `_compute_module_action()`, applies
     `remap_policy_throttle()`, *then* clips — the ordering a wrapper couldn't achieve (the
     stock clip destroys the negative half before any wrapper sees it). Identical on all three
     entry paths, so local validation could never have caught the original bug.
  2. **Residual throttle re-centered**: `StudentHybridProvider` residual adds
     `scale × (2·RL_throttle − 1)` on the throttle channel (policy-neutral 0.5 = leave BT's
     throttle alone) instead of raw addition that could only push throttle up.
  3. **Switch mode had no selector anywhere** → the stock class silently ran pure RL;
     `StudentHybridProvider` uses `switch_by_range` (BT inside 2 km, RL beyond; falls back to BT
     when range is unavailable, never silently RL) as an explicit default.
  4. **Bundle/runtime observation guard**: `verify_bundle_observation()`
     (`student/inference_providers.py`) called from `run_unreal_inference.py`,
     `run_local_dogfight.py` (both sides) and `student/my_submission.py` — raises before
     connecting when the bundle's recorded `obs_mode`/`observation_module` disagree with the
     runtime config; legacy bundles without those keys warn instead. `student/my_submission.py`
     retargeted: `MODE="hybrid"`, `BUNDLE_DIR` → v4 `stage_3_autopilot_pursuit/final_bundle`
     (newest post-audit bundle; the old top-level `v1` default predates every 2026-07-12 fix),
     `OBSERVATION_MODULE="student.my_observation_v2"`, `AI_TYPE=Fusion`. All four fixes
     re-verified after re-homing (remap-before-clip ordering, throttle-down residual, real
     switch selection, guard raise/warn) plus import-chain + v4 dry-run.
     Caveat: stage_3 has only trained pursuit-type stages — real competitiveness still needs
     v4 to progress (it sits at stage 4/17, no live process). Known remaining gap, not fixed:
     local sim hands the *target-side* provider the ownship's observation (`pre_obs`) — only
     matters for RL-vs-RL local eval, and lives in `src/dogfight/**` so it's out of bounds to
     touch directly.

- ✅ **2026-07-14 ponytail refactor (no behavior change)** — deduplicated the C++ BT tactics:
  new `BTFunc::PredictedTargetTravel` / `BTFunc::ShorterTurnDirection` helpers
  (`AIP_DCS/BehaviorTree/BT_Content/Functions.h/.cpp`) replace the identical lead-time and
  shorter-turn blocks copy-pasted across 9 `Task_*.cpp` files; `Task_LeadTurn.cpp` now uses
  `BT_Geometry::DEGTORAD` instead of its own constant (Debug x64 rebuild verified clean — the
  `Release/` runtime DLLs were NOT redropped, behavior is identical). Python:
  `add_common_training_args()` — originally placed in `src/dogfight/ai/rllib_utils.py`, but
  **reverted from there and moved to the editable `train_common.py` (Release root) during the
  same-day `src/dogfight/**` boundary cleanup** — defines the 44 CLI flags
  `train_rllib.py`/`train_curriculum.py` previously declared twice (per-script defaults for
  algorithm/output-name/output-tag preserved via `set_defaults`; parsed defaults verified
  identical pre/post); merged `_sync_lstm_args_from_init_bundle`'s duplicated SAC/non-SAC
  branches and inlined the `_apply_bundle_weights` pass-through (`train_curriculum.py`);
  deleted the dead `sys.path` bootstrap from `student/my_reward.py`/`my_curriculum.py` (every
  entry point already sets ROOT+SRC; `my_observation*.py` never had one). ~330 lines removed.

- ✅ **2026-07-12 full-codebase audit + v4 restart** (newest entry; `COMPETITION_PLAN.md` §1's
  2026-07-12 update carries the full post-mortem). Findings: the two-circle ATA guard was
  unpassable and trained merge avoidance (v1+v3: 93–100% guard-fail losses, 0 wins ever, ~0 WEZ
  time in ~7,400 iterations); crashes were paid `draw_reward` (+20 in `obfm_defensive` → learned
  100% suicide); SAC learner metrics logged `n/a` for all of v1–v3 (extractor read
  `__all_modules__` instead of `default_policy`). Fixes landed and verified: crash terminal
  routing (`crash_penalty`/`target_crash_reward` in `student/my_reward.py`,
  `src/dogfight/envs/reward.py`, both config dicts), range-based disengagement guard
  (`src/dogfight/envs/termination.py`, `max_range_m=8000`), rebuilt `student/my_curriculum.py`
  (5-alpha two-circle ladder, 8 km shaping reach, `advantage_scale=0.1`, `full_dogfight`
  1500 iters), new `student/my_observation_v2.py` (15 features, +target-speed norm; separate
  module so the then-live v3 couldn't import a changed obs size), fixed SAC metrics extraction +
  full reward-component CSV columns (`train_curriculum.py`), env.step latency summary in
  `run_local_dogfight.py`. New run: `experiments/real_eagle_v4.yaml` (engagement replays
  enabled); `scripts/launch_v4_when_free.ps1` auto-starts it when v3's process tree exits.
  v3 must not be `--resume`d after this date (stages module rewritten).

- ✅ Team identifier renamed `team01` → `real_eagle` throughout (`student/my_submission.py`,
  `student/my_train.py`, the `artifacts/{dashboard,models,logs,records}/real_eagle/` folders and
  their internal metadata, `experiments/real_eagle_curriculum_v2.yaml`). Generic multi-team
  examples in `README.md`/`run_unreal_inference.py`/the standard `experiments/student_*.yaml`
  templates were deliberately left alone — those are placeholder patterns for any team, not this
  team's config.
- ⚠️ Along the way, found `experiments/real_eagle_curriculum_v2.yaml` (formerly
  `team01_curriculum_v2.yaml`) references a "v3" `student/my_curriculum.py` (16 stages) and
  `student/my_reward.py` (tuned pursuit/position/WEZ scales) that **do not exist in this
  checkout** — both files are still the bare minimal templates — and describes a
  `curriculum_v1` postmortem (a policy that learned a "BT-crash exploit") with no
  `artifacts/checkpoints/` or `artifacts/curriculum/` data to back it up. Provenance unclear;
  flagged in the file itself. Not currently runnable as-is.
- ✅ `aip` conda environment exists (`C:\Users\USER\anaconda3\envs\aip`).
- ✅ Real connectivity has been exercised: `logs\unreal_packets\` and `logs\native_bt\` contain
  captured sessions dated 2026-05-14, and `startup_command.txt` records a real `--mode bt`
  launch against a private-IP practice server.
- ✅ `student/my_reward.py` now ports the reference reward anatomy (survival + step + pursuit +
  damage + safety + terminal + guard_fail) plus a new `position` component (AA-based, mirrors
  `pursuit`'s ATA-based gradient — `PROJECT_ANALYSIS.md` §3's "reward ATA and AA together"
  warning). While verifying it, found and fixed a real bug: `GeoMathUtil.py`'s 3D aspect-angle
  mode (`proj=False`) silently returns 0° instead of 180° exactly at head-on geometry (matrix
  singularity, confirmed empirically) — affected the new `position` component AND the built-in
  `src/dogfight/envs/observation.py`'s `tactical16`/`relative14` AA feature. Fixed by switching
  to `proj=True` (2D, no singularity) everywhere AA is computed for policy-facing use; no trained
  policy existed yet to be affected by the behavior change. `student/my_curriculum.py` is
  deliberately still the bare 2-stage toy example — `train_curriculum.py` defaults to the
  built-in 15-stage `src/dogfight/ai/curriculum.py` with no `--stages-module` override, zero
  authoring cost; see `COMPETITION_PLAN.md` §7/§9.
- ✅ Environment-vs-rules corrections (`COMPETITION_PLAN.md` §4) applied at the source: WEZ is
  now phase-aware (`DEFAULT_ENV_CONFIG["wez"]["phases"]` in `src/dogfight/config.py` +
  `update_damage()`/`_match_wez_phase()` in `single_agent_env.py`, verified via an 8-case
  scripted best-phase-wins test), and the built-in curriculum's `full_dogfight` stage now uses
  `episode_step_limit=12000` (200s, was 18000/300s) — not a YAML knob for the curriculum path,
  `run_experiment.py` never forwards episode-length overrides to `train_curriculum`.
- ✅ `student/my_observation.py` is now a real tactical16-equivalent (14-D, was an 8-D toy
  example) with train/live parity for ownship speed/altitude (derived from velocity/position,
  not the live-always-zero KCAS/ALT slots) — see `COMPETITION_PLAN.md` §5.2.
- ✅ New runnable experiment config: `experiments/real_eagle_v1.yaml` (`train_curriculum`, built-in
  stages, the corrections above, SAC MLP). `experiments/real_eagle_curriculum_v2.yaml` remains a
  reference-only draft (its v3 `my_curriculum.py`/`my_reward.py` still don't exist as such).
- ✅ `AIP_BASE.dll`/`AIP_BASE_target.dll` in `DogFightEnv/Release/` were rebuilt from `AIP_DCS/`
  across five rounds (2026-07-07/08), **now frozen** as the fixed curriculum-training opponent
  (`COMPETITION_PLAN.md` §5.1.5) — previously both just flew straight and never dealt damage.
  Rounds 1-3: a real pure-pursuit node (`Task_Pure`) and a lead-pursuit node
  (`Task_LeadPursuit`) for far range; a fix to a foundational lat/lon-vs-meters unit bug in the
  position pipeline (this was the actual blocker preventing any damage at all); a working
  throttle control (was hardcoded to 1.0 and disconnected from the BT entirely); a simple
  evasion node (`Task_Evade`); and a Hard-Deck-avoidance node (`Task_ClimbToSafeAltitude`) added
  after a 200s test run showed the pre-fix tree had **no altitude safety logic at all** and
  could fly itself into the ground over a long enough engagement — confirmed a kill in local
  BT-vs-BT testing at this point. Round 4: `Task_JinkingTurn` (close-range defensive jink) and
  `Task_HighYoYoUp` (pull-up-and-out overtake management) added; `LunchMSL`/`WeaponSelect`
  investigated and intentionally dropped (confirmed functionally dead for a guns-only
  competition). Round 5: `Task_OneCircleFight` (turn-radius management via throttle when
  off-boresight close in) and `Task_LagPursuit` (aim-behind-the-lead-point energy management when
  already tracking well) added, mining tactical patterns from the separate `ai-combat-sdk-main`
  project's reference strategies but implemented fresh as native `Task_*` nodes under
  `COMPETITION_RULES.md`. Found along the way: `MyAngleOff_Degree` is HCA, not ATA — true ATA is
  `Los_Degree` (`CheckSight.cpp`) — confirmed by reading source, not the field name. **Note**:
  after round 3's evasion+Hard-Deck logic landed, a symmetric BT-vs-BT matchup (identical tree vs.
  itself) ends in a stalemate (both survive at full health) rather than round-2's kill — expected,
  not a regression: two equally-matched, equally-defensive aircraft aren't required to produce a
  kill, and the round-2 kill capability itself wasn't removed (a round-5 diagnostic — temporarily
  removing `Task_JinkingTurn`/`Task_Evade` — reproduced a full kill again, confirming the newer
  nodes are reachable and functional, just usually outranked by the broader defensive gate in this
  one fixed symmetric test scenario). Now survives the full 200s competition match length without
  crashing in every round (see `COMPETITION_PLAN.md` §5.1). Pre-rebuild binaries preserved as
  `AIP_BASE.dll.bak` (pre-round-1), `AIP_BASE.dll.step3.bak` (pre-round-4), and
  `AIP_BASE.dll.round1.bak` (pre-round-5) — same naming for the `_target` variant. Build output
  lands at `D:\AIP\AIP_LIB\bin\debug.x64\AIP_DCS.dll` (Debug|x64) before being copied into
  `DogFightEnv/Release/` under the two runtime names.
- ✅ Confirmed (static code analysis, no live server needed): 4 of `tactical16`'s 16 observation
  features (ownship speed/altitude/health, target health) are permanently `0.0` during every
  live Unreal match — the wire protocol never transmits health/fuel at all, and altitude/speed
  are technically present in the packet but never copied into the dedicated state slots
  `_build_tactical16()` reads from. See `COMPETITION_PLAN.md` §5.2.
- ⚠️➡️✅ **Found and fixed a real bug, 2026-07-10**: `student/my_reward.py`'s `position_scale`/
  `position_half_angle_deg` (the AA-based rear-hemisphere term) were only ever defined in
  `MY_REWARD_CONFIG`, never mirrored into `src/dogfight/config.py`'s `DEFAULT_ENV_CONFIG["reward"]`.
  `train_curriculum.py`'s `env_creator()` does `cfg.setdefault("reward", reward_config)`, which
  no-ops whenever `"reward"` is already present in `cfg` — true for every curriculum run, since
  `build_stage_env_config()` always starts from a deep copy of `DEFAULT_ENV_CONFIG`. So the extra
  keys never reached `compute_reward()`, and `reward_config.get("position_scale", 0.0)` silently
  zeroed the whole position term — **meaning it was very likely inert for all of real_eagle v1's
  stage 0-8 training (4493 iterations) despite being deliberately designed and verified** (the
  aspect-angle-singularity fix above was in service of a term that wasn't actually contributing to
  the trained policy). Fixed by adding `position_scale`/`position_half_angle_deg`/`guard_fail_penalty`
  to `DEFAULT_ENV_CONFIG["reward"]` with matching values; verified end-to-end (reproduced
  `env_creator`'s exact merge logic against real curriculum stages, confirmed `position_scale`
  now reaches `compute_reward()` and produces a nonzero `position` component). **This is a new,
  material input to the pending "resume curriculum from stage 9 vs. restart" decision** — stages
  0-8 trained without positional shaping actually active.
- ✅ **Initial spawn defaults corrected to match real competition presets, 2026-07-10** — confirmed
  via the DogFightViewer's in-game scenario-setup screen (HABFM/OBFM_RED/OBFM_BLUE presets,
  `Speed(m/s)=200.0`, `Alt(ft)=15000.0`, HABFM separation ≈10000ft/3048m). Previously
  `DEFAULT_ENV_CONFIG["ownship"]`/`["target"]` (the static spawn used by stages 0-3 and
  `full_dogfight`) and `initial_scenario.altitude_m`/`speed_mps_range` (used by the
  `two_circle_headon` stages) used an unverified 7000m altitude / 300 m/s / 5000m-separation
  baseline. Now: 4572m altitude, 200 m/s, 762m (=2500ft) separation for the static spawn
  (corrected 2026-07-11 from a mistaken 3048m/10000ft — the official kickoff-deck slides clarified
  the main match is 2000-3000ft and 10000ft is the round-4 head-on tie-break only);
  `initial_scenario.altitude_m=4572.0`, `speed_mps_range=[175.0, 225.0]` (recentered, same
  ±25 spread as before) for `two_circle_headon`. `target_autopilot`'s commanded altitude/speed
  (stage 3's scripted target) updated to match. The `two_circle_headon` stages' own
  `alpha_deg`/`turn_diameter_ft`/`separation_jitter_ft` geometry-progression mechanics were left
  untouched — deliberate curriculum design, separate from matching one specific preset.
  OBFM_RED/OBFM_BLUE's exact geometry (vs. HABFM's, which is now reflected above) is still
  unconfirmed — no readable config exists in the packaged Unreal builds (checked directly), would
  need capturing empirically from the viewer the same way HABFM's was.
- ✅ New `DogFightEnv/Release/student/reward_lib.py` — SI-unit-corrected port of an external BFM/
  ACM reward-shaping reference (`D:\AIP\reward_function_skeleton.py` / `BFM_ACM_Reward_Engineering_
  Reference.md`), with the aspect-angle sign convention corrected to match this project's actual
  `GeoMathUtil` (the external reference assumed the opposite — standard-doctrine — convention;
  verified by hand-tracing a concrete example). Only `positional_advantage()` is wired into
  `my_reward.py` so far, as a new `advantage_scale`-weighted term defaulting to **0.0** (inert —
  it overlaps with the existing `pursuit`+`position` terms, don't run all three at meaningful
  weight without a reason). **Trimmed 2026-07-11 (`/ponytail-review`, 213→57 lines)**: the
  ported-but-unwired energy(`Ps`)/geometry/closure/turn-rate functions were deleted rather than
  kept as dead code — each needs state this project doesn't expose yet, and re-porting from the
  external skeleton (`D:\AIP\reward_function_skeleton.py`) in SI is a few lines when that state
  exists; a docstring pointer records where to re-port from.
- ✅ **OBFM asymmetric-start scenario + curriculum, 2026-07-11** — new `obfm`
  `initial_scenario.mode` + `_apply_obfm_initial_scenario()` in `single_agent_env.py` reproduces
  the competition's OBFM_RED/OBFM_BLUE preset (556 m, attacker on the defender's six, LOS
  ~4.6°/175.4° — geometry-verified against a viewer capture). `role: offensive|defensive` picks
  ownship's seat. Two curriculum stages (`obfm_offensive` win-rate-gated, `obfm_defensive`
  survival-weighted) live in `student/my_curriculum.py` (spliced after `autopilot_pursuit`; the
  built-in `curriculum.py` is left untouched so the in-progress v2 run resumes cleanly). Run via
  new `experiments/real_eagle_v3.yaml`. These give the clean convert-the-advantage / survive signal
  the neutral stages lack (where BT-vs-BT stalemates, 0 WEZ contact).
- ✅ **WEZ-phase-aware pursuit shaping, 2026-07-11** — new
  `config.wez_pursuit_multipliers(phases, elapsed_s)` widens the pursuit term's range/ATA-angle
  gradient late-match (1.0 while only Phase 1 active → 3500m/60° at t>100s → 4000m/90° at t>150s),
  derived from the existing `_WEZ_PHASES` numbers, so the RL side gets a stronger late-match
  gradient toward the looser positioning that still scores damage then. Wired into both
  `student/my_reward.py` and `src/dogfight/envs/reward.py`; `elapsed_s` from `StateIndex.SIM_TIME`.
  Early-match shaping deliberately unchanged (no regression). Watch item: the 90° Phase-3
  half-angle is aggressive, may need clamping if training shows it rewards sloppy tracking.
- ✅ **Batch D landed, 2026-07-10/11** — the last 3 planned `Task_*` nodes now exist:
  `Task_BarrelRollAttack` (Gate 4, high-closure overshoot case), `Task_LagDisplacementRoll`
  (Gate 4, single-shot abeam/not-yet-tracked reposition), `Task_SingleSideOffset` (TAIL,
  pre-merge approach pattern). All three registered, wired into `Rule_forTraining.xml`, and built
  cleanly (`AIP_DCS.vcxproj -> D:\AIP\AIP_LIB\bin\debug.x64\AIP_DCS.dll`). `Task_SingleSideOffset`
  is deliberately wired as a **bare** node rather than the plan's original `DECO_DistanceCheck`-
  wrapped Sequence sketch — an XML-level Range-3000-5000 decorator would cut it off exactly when
  Distance drops below 3000m mid-maneuver, before its own "close" sub-phase (which needs to keep
  running from 3000m down to its 2000m handoff) ever gets to run; every other phased node with a
  distance-based entry gate in this tree has the same shape, checking entry distance internally
  only on a fresh claim. An adversarial code-review pass (multi-agent, 5 reviewers across
  plan-conformance/BT-idiom/geometry-math/wiring lenses + independent verification of each finding)
  found and a fix landed for one real bug before this was called done: `Task_SingleSideOffset` had
  no unconditional time-cap release like its Gate-4 siblings (`Task_HighYoYoUp`/`Task_LowYoYo`/
  `Task_BarrelRollAttack` each have one) — its only exit was `Distance<2000m`, not guaranteed
  against an opponent that never lets range close that far, and `ClaimManeuverPhase`'s stale-claim
  self-heal resets elapsed back to 0 every 20s rather than forcing a release. Fixed by adding a
  15s unconditional cap, rebuilt clean. `AIP_BASE.dll`/`AIP_BASE_target.dll` re-dropped from this
  build (previous Batch-A-C DLLs preserved as `.batchC.bak`). A fresh BT-vs-BT self-test after the
  drop still ends in `max time out` with both aircraft at full health — same stalemate class as
  after Batch A-C, which is expected (Batch D refines Gate 4/TAIL's offensive approach, not the
  Gate 0-3 priority/detection logic that decides whether an offensive branch is ever reached in a
  symmetric mutual-standoff) — but the flight profile is qualitatively different again: this run
  stayed in a lower, tighter altitude band (~900-2400m) throughout rather than the big ~11-12km
  vertical excursion Batch A-C's self-test showed, consistent with Gate 4's closer-range nodes
  now capturing more of the engagement. Not yet triaged further.

<details><summary>Superseded snapshot, as of 2026-06-16 (kept for history)</summary>

- ❌ No `aip` conda environment created yet (only `base` existed)
- ❌ `torch` / `ray[rllib]` not installed anywhere detected
- ❌ No training had been run — `artifacts/` did not exist
- ✅ Templates in place: `student/my_reward.py` (basic only), `student/my_submission.py`
  (pre-filled with server IP, needed team/bundle confirmed)
- ❓ `AIP_LIB.zip` and the PDF manual not yet opened/inspected — as of 2026-07-07, neither file
  is present in this checkout at all, so this is now moot rather than pending.

</details>
