# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Competition context — read these first

This project targets **AIP TGC 2026** ("AI Pilot Top Gun Challenge") — a real, ministry-backed
competition (288 teams). Four companion docs carry the load-bearing context and should be read
before making strategic decisions here; this file only covers code structure/commands, not
competition rules or system design:

- **[COMPETITION_RULES.md](COMPETITION_RULES.md)** — official rules, scoring, schedule, damage
  model, DQ risks. Single source of truth for anything competition-format-related.
- **[PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md)** — how the system works: MDP formulation, reward
  anatomy, curriculum design, the `ActionProvider` abstraction, and known open risks (e.g. a
  possible train/competition state mismatch on the Unreal side).
- **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** — file/directory map, plus a running "current
  state" log of what's actually been done vs. still templated.
- **[COMPETITION_PLAN.md](COMPETITION_PLAN.md)** — the living strategy/execution plan (target
  architecture, milestones, open risks) with checkboxes to update as work progresses.
- **[COMMAND.md](COMMAND.md)** — every command line the project uses (setup, dry-run, training,
  checkpoint resume, dashboard, local verification, live Unreal inference/submission), each with
  an explanation of what it does. This file's own "Common commands" section below is the short
  version; COMMAND.md is the exhaustive one.

**Location, permanently (decided 2026-07-16):** all four live in
`DogFightEnv/References and Manuals/`, not the repo root. They used to live at
`D:\AIP\AIP_LIB\` root; a 2026-07-15 incident (see callout below) moved them, and the team decided
to keep them there rather than restore them to root — treat `References and Manuals/` as their
permanent home, not a temporary relocation. Keep these four in sync with reality as work
progresses — they're maintained docs, not one-off snapshots.

> **2026-07-15 incident, read before trusting any "done"/"✅" claim in these four docs about
> `src/dogfight/**`, `student/my_reward.py`, `student/my_curriculum.py`, or
> `Rule_forTraining.xml`:** a fix for a `src/dogfight` boundary violation was executed as a full
> pristine-template overwrite instead of a scoped revert, silently undoing roughly a week of
> validated fixes (WEZ-phase damage model, the range-based two-circle guard, reward
> crash-routing, the whole BT tactics expansion's XML wiring, `AIP_BASE.dll`/`AIP_BASE_target.dll`
> reverted to a stale 9-node pre-expansion build). Recovered 2026-07-15/16 via decompiling stale
> Python bytecode caches (`student/my_reward.py`, `my_curriculum.py`, `reward_lib.py`) and a
> surviving off-repo design plan (`Rule_forTraining.xml`, rebuilt+redeployed, verified via live
> BT-vs-BT runs) — full detail in memory (`project_bulk_revert_regression_2026_07_15`,
> `project_v4_recovery_2026_07_15`, `project_bt_xml_reconstruction_2026_07_15`). The revert also
> put `student/my_submission.py` (+ `run_unreal_inference.py`/`run_local_dogfight.py`) back onto
> the stock `RLActionProvider`/`HybridActionProvider`, reintroducing the throttle-remap bug from
> `project_hybrid_inference_fixes_2026_07_14`, and wiped `state_schema.py`'s `velocity_xyz()`
> helper (used by `my_observation_v2.py`) the same way it wiped the WEZ-phase functions — both
> re-fixed 2026-07-16 and verified with a live `run_local_dogfight.py --ownship-backend hybrid
> --target-backend bt` run, not just a compile check. **One thing was
> NOT restored, deliberately**: `src/dogfight/config.py`'s WEZ-phase widening and
> `envs/termination.py`'s range-based guard have no plug-in hook (unlike reward/observation/
> curriculum), so fixing them requires either crossing the hard boundary below or editing the
> shared trainer scripts — the team declined both, so local training/eval currently runs against
> the flatter pre-fix damage model and a disabled two-circle guard. This is a training-fidelity
> gap only, not a competition-legality issue (the live Unreal server scores independently).

## Editing boundaries (derived from `COMPETITION_RULES.md` §8)

The only hard rule is: don't **rename, move, or delete** runtime assets. Content edits are fine
— that's the intended customization surface. Full reasoning: `COMPETITION_RULES.md` §8.

| Status | Files / dirs |
|---|---|
| 🔒 Keep name & location (edit content freely) | `DogFightEnv/Release/{AIP_BASE.dll,AIP_BASE_target.dll,JSBSimAIPLib.dll}`; `DogFightEnv/Release/Rule_forTraining.xml`, `Rule.xml` (+ any `Rule_real_eagle.xml` you add); `DogFightEnv/Release/aircraft/`; `DogFightEnv/Release/engine/`; `DogFightEnv/Release/scripts/{f15_cruise.xml,f16_cruise.xml,f16_cruise,fa50_cruise.xml}` |
| 🔒 Preserve wire format (code replaceable) | `src/dogfight/unreal/protocol.py`'s struct-packed message types |
| ⚠️ Naming collision, NOT protected | `DogFightEnv/Release/scripts/run_experiment.py` — same folder as the protected cruise-script XML, but an ordinary Python tool |
| ✅ The intended customization surface | `student/*.py`; all of `AIP_DCS/` (C++ source + `.vcxproj`/`.vcxproj.filters` — only the *compiled* DLL is a protected runtime asset, not its source); Rule XML *contents*; `experiments/*.yaml` |
| 🚫 Hard no-edit boundary (team policy, 2026-07-14) | `src/dogfight/**` — `COMPETITION_RULES.md` §8 still doesn't restrict this area (unchanged fact); the team has separately decided to treat it as off-limits regardless, on top of the rules. Route new logic through `student/`-visible wrappers or the entry scripts (`train_*.py`, `run_*.py`) instead. Supersedes the older "convention only, students generally don't edit" framing in `PROJECT_STRUCTURE.md` — that was a soft habit, this is a hard stop. |
| 🚫 Out of scope entirely | `D:\ai-combat-sdk-main\` — separate, unrelated system |

## Repository shape

This directory (`AIP_LIB/`, not a git repository) is a mixed C++/Python/Unreal monorepo for an
F-16 1v1 dogfight AI course/competition ("AIP"). Three components interoperate at runtime but are
built/run completely independently:

1. **`AIP_DCS/`** — C++ DLL, native behavior-tree dogfight AI ("DCS" = Decision & Control
   System). Built with Visual Studio/MSBuild.
2. **`DogFightEnv/Release/`** — Python Gymnasium + Ray/RLlib environment for training RL
   policies against the native BT AI (or against each other). This is where student/RL work
   happens, and the default working directory for most sessions.
3. **`BattleServer_V0.2/`** and **`Windows/`** — pre-packaged (cooked) Unreal Engine
   builds of `DogFightViewer.exe`, the 3D visualization/live-inference client. **Binaries only, no
   engine source** — do not attempt to edit these as if they were UE source trees.

`bin/`, `PropertySheets/` (26 `.props` files for Bullet/DIS/JSBSim/MAK RTI HLA1516(E)/etc.) and
`.vs/` are legacy MSBuild plumbing for a larger sibling-library ecosystem that isn't actually
present in this checkout. Only relevant if you're touching `AIP_DCS`'s build configuration;
otherwise ignore.

Most student-facing docs/manuals (`DogFightEnv/Release/README.md`, `experiments/README.md`,
`DogFightEnv/References and Manuals/**/*.html`) are written in Korean — match that when editing
them. (That folder name is itself the English rendering used on disk; don't go looking for a
Korean-named `참고자료 및 매뉴얼/` — it doesn't exist in this checkout.)

## AIP_DCS (native behavior-tree DLL)

`AIP_DCS.sln` is a **single-project** solution (`AIP_DCS.vcxproj` only) — build via Visual Studio
or `msbuild AIP_DCS.sln /p:Configuration=Debug /p:Platform=x64`. There is no top-level CMake build;
only `Geometry/CMakeLists.txt` exists (an `OBJECT` lib for Vector3/Matrix3/Quaternion/etc.), and
it's vestigial — the real build is 100% the `.vcxproj`.

Structure:
- `LibMain.cpp` — the entire DLL surface. All exports are `extern "C" __declspec(dllexport)`:
  `CreateBehaviorTree`, `Step` (the per-tick decision call: takes own+other `oPlaneData`, returns
  stick/throttle + missile/flare launch flags), `GetStick`, `GetAnnotation`, `ChangeData`,
  `SetTarget`, `SetACM_Mode`, `SetBehaviorTreeDeltaTime`, `LLAtoCartesian`, `GetVP`, `Reset`,
  `RemoveBT`. `dllmain.cpp` is an empty stub — don't look there for logic.
- `BehaviorTree/` — a vendored/embedded copy of BehaviorTree.CPP v3 (`behavior_tree.cpp`,
  `bt_factory.cpp`, `controls/`, `decorators/`, `tinyxml2.*`, etc.).
- `BehaviorTree/BT_Content/` — the actual air-combat BT node implementations, split by node type.
  As of the BT tactics expansion (Batches A-D, landed 2026-07-08 through 2026-07-10 — see
  `PROJECT_STRUCTURE.md`'s current-state log for the batch-by-batch detail):
  - `Decorator/`: `DECO_BFMCheck` (dead — see below), `DECO_DistanceCheck`, `DECO_LOSCheck`,
    `DECO_AngleOffCheck`, `DECO_AspectAngleCheck`, `DECO_AltitudeCheck`, `DECO_SpeedCheck`,
    `DECO_EnergyRatioCheck`, `DECO_ClosureRateCheck` — all 9 are `registerNodeType`'d, including
    `DECO_BFMCheck` itself; it's still functionally dead because nothing assigns `BB->BFM` away
    from `NONE`, so its match condition can never be true, and it has no caller anywhere in
    `Rule_forTraining.xml`. Of the live ones, `DECO_SpeedCheck` has no XML caller yet — compiles
    and works, just unused so far.
  - `Service/`: `AngleOffUpdate`, `AspectAngleUpdate`, `CheckSight`, `DirectionVectorUpdate`,
    `DistanceUpdate`, `SelectTarget`, `EnergyStateUpdate` (Batch A — computes `Es`/`EnergyRatio`
    for both aircraft each tick).
  - `Task/`: `Task_Empty` (placeholder, never referenced from either Rule XML), `Task_pure`,
    `Task_LeadPursuit`, `Task_Evade` (implements "The Break," class/file name kept for history —
    see comment at the top of `Task_Evade.cpp`), `Task_ClimbToSafeAltitude`, `Task_JinkingTurn`,
    `Task_HighYoYoUp`, `Task_OneCircleFight`, `Task_LagPursuit`, `Task_Notch`, `Task_FlatScissors`,
    `Task_AnglesTactics`, `Task_EnergyTactics`, `Task_LowYoYo`, `Task_VerticalScissors`,
    `Task_RollingScissors`, `Task_NoseToTailTurn`, `Task_NoseToNoseTurn`, `Task_LeadTurn`,
    `Task_BarrelRollAttack`, `Task_LagDisplacementRoll`, `Task_SingleSideOffset` — all
    live/registered except `Task_Empty`.
  - `BlackBoard/`: `CPPBlackBoard.h` — additive-only `ManeuverID` enum + phase-tracking fields
    (`ActiveManeuverID`/`ActiveManeuverStartTime`/etc.) back every multi-second maneuver above,
    since `SyncActionNode` (every node's base class) throws if `tick()` ever returns `RUNNING` —
    see `Functions.h`'s `ClaimManeuverPhase`/`ReleaseManeuverPhase` for the actual pattern before
    writing a new phased node.
  **Historical note, resolved 2026-07-08:** `Debug/*.obj` build leftovers under
  `JinkingTurn`/`HighYoYoUp`/`LunchMSL`/`WeaponSelect`/`JinkingTurnSelector` (plus ~40 more names)
  turned out to be from a **separate, older, abandoned implementation** (different project root,
  bare naming, no relation to today's `Task_`-prefixed family) — not a trimmed version of this
  tree, no logic recoverable from them. `LunchMSL`/`WeaponSelect` were confirmed functionally dead
  for this guns-only competition and intentionally not implemented — no missile mechanic exists
  anywhere in the scoring/damage/flight-model code, and the one DLL export that could carry a
  launch decision out is declared but never written. **Angle-field naming trap**:
  `MyAngleOff_Degree` (`AngleOffUpdate.cpp`) is HCA (heading crossing angle between the two nose
  vectors), not ATA — true ATA is `Los_Degree`, computed in `CheckSight.cpp`. **Aspect-angle sign
  trap**: `MyAspectAngle_Degree` (native BT) is 180°=target's six o'clock/behind them, 0°=nose-on
  — but the Python side's `GeoMathUtil._get_aspect_angle()` (`DogFightEnv/Release/GeoMathUtil.py`)
  uses the OPPOSITE convention (0°=behind them). The two halves of this codebase disagree with
  each other on this; verify against the actual source you're reading, not the field name or an
  assumption carried over from the other language.
- `Geometry/` — math support library (Vector3/4, Matrix3/4, Quaternion, EulerAngle,
  CoordinateConverter, Controller_CY, Angle/AxisAngle).

BT rule XML (`Rule_forTraining.xml`, `Rule.xml`) that parameterizes a compiled tree lives under
`DogFightEnv/Release/`, not under `AIP_DCS/`. The compiled DLL is consumed by the Python env as
`AIP_BASE.dll` / `AIP_BASE_target.dll` (see below) — there's no automated copy step, it's a manual
build artifact drop.

## DogFightEnv/Release (Python RL training env)

Run everything from `DogFightEnv/Release/` (the primary working directory) using the `aip` conda env
(`C:\Users\USER\anaconda3\envs\aip\python.exe`). Install deps with
`pip install -r requirements.txt` (`ray[rllib]==2.54.0`, `torch>=2.3,<3.0`, `gymnasium>=1.0,<2.0`,
`numpy==2.2.6`, `pymap3d`, `PyYAML`).

Note: docs reference an internal `DogFightEnv/MyTrainEnv/` sibling used for research-only reward
modes and comparison YAMLs — **it does not exist in this checkout**, only `Release/` does. Don't
chase references to it.

### Common commands

Syntax/dry-run smoke check:
```powershell
python -m py_compile train_rllib.py train_curriculum.py scripts\run_experiment.py student\my_reward.py student\my_observation.py student\my_train.py student\my_curriculum.py
python scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run
```

Run a YAML experiment (preferred entry point):
```powershell
python scripts\run_experiment.py experiments\student_sac_mlp.yaml
```

Direct single-stage / curriculum training (what `run_experiment.py` dispatches to based on a
YAML's `script:` field — `train_rllib` | `train_curriculum` | `student/my_train`):
```powershell
python train_rllib.py --algorithm sac --iterations 50 --observation-mode tactical16 --target-mode behavior_tree --target-behavior-dll AIP_BASE_target.dll --output-name real_eagle --output-tag v1
python train_curriculum.py --algorithm sac --output-name real_eagle --output-tag curriculum_v1 --resume
```

Local 1v1 sanity check between any two backends (`rl|bt|hybrid|fixed`):
```powershell
python run_local_dogfight.py --ownship-backend rl --ownship-bundle-dir artifacts\models\real_eagle\v1 --target-backend bt --save-log
```

Live Unreal inference (talks UDP to `DogFightViewer.exe` in `BattleServer_V0.2/`/`Windows/`):
```powershell
python run_unreal_inference.py --mode hybrid --bundle-dir artifacts\models\real_eagle\v1 --bt-dll AIP_BASE.dll --bt-rule-xml Rule_real_eagle.xml --team-name real_eagle --server-ip <IP> --server-port 9999 --action-repeat 6
```

Unified dashboard (training metrics + Tacview replay):
```powershell
python tools\dashboard.py --training-logdir artifacts\dashboard --logdir logs --port 7860
```

### Tests

No test suite for the core `dogfight` package. The only tests are in `tools/web_log_viewer/tests/`
and `tools/dogfight_dashboard/tests/`. Run a single test from `Release/`:
```powershell
cd tools\web_log_viewer
python -m pytest tests\test_log_data.py::LogDataTest::test_pair_discovery_and_replay_math
```

### Architecture

`src/dogfight/` is the core package (needs `Release/` and `Release/src` on `sys.path`, which the
entry scripts set up):
- `envs/single_agent_env.py` — the Gymnasium `DogFightEnv`, wiring JSBSim FDM state
  (`JSBSimWrapper.py`/`FighterSim.py` wrapping `JSBSimAIPLib.dll`) into observation/reward/
  termination.
- `envs/observation.py`, `envs/reward.py`, `envs/termination.py`, `config.py` — observation modes
  (`classic12`/`relative14`/`tactical16`/`custom`), `compute_reward(...)`, episode-end logic, and
  `DEFAULT_ENV_CONFIG`.
- `ai/curriculum.py` — ordered `CurriculumStage` list used by `train_curriculum.py`:
  `flight_survival → target_pursuit → wez_approach → autopilot_pursuit → two_circle_headon(×N) →
  full_dogfight`.
- `ai/action_provider.py` + `bt_action_provider.py` / `hybrid_action_provider.py` /
  `rl_action_provider.py` — **the key abstraction**: every backend (RL policy, native BT via
  `ai/native_bt.py`'s `AIPilot`, or a residual/blend/switch hybrid of both) implements the same
  `ActionProvider.compute_action()` contract. Local sim, live Unreal inference, and RLlib rollout
  workers all consume providers through this one interface — new inference backends (e.g. an ONNX
  adapter) should plug in here rather than special-casing call sites.
- `unreal/client.py` + `protocol.py` — UDP client used by `run_unreal_inference.py` to drive
  `DogFightViewer.exe`.
- `ai/checkpoint_io.py` — the two save formats have different purposes: **lightweight bundle**
  (`metadata.json` + `policy_weights.pkl.gz`, weights only — for submission/inference/warm-starting
  new runs) vs **native checkpoint** (full RLlib state incl. optimizer/replay buffer — for resuming
  the *same* training run). Controlled independently via
  `runtime.save_lightweight_bundle`/`save_native_checkpoint` in YAML.

`student/` is the customization surface — each file's contract:
- `my_reward.py`: `MY_REWARD_CONFIG: dict`, `compute_reward(ownship_state, target_state,
  ownship_damage, target_damage, geo_info, wez_config, reward_config, terminated, truncated,
  end_condition) -> tuple[float, dict]`
- `my_observation.py`: `OBSERVATION_MODE`, `OBSERVATION_SIZE`, `build_observation(ownship_state,
  target_state, geo_info, wez_config=None)`, `describe_observation()`. `my_observation_v2.py` is
  the same contract with 15 features (+ target-speed norm), used by v4+ runs — it's a separate
  file because changing `OBSERVATION_SIZE` under a live run crashes its workers at the next
  stage transition; see its docstring for why closure rate is deliberately NOT a feature
  (train/live velocity-frame mismatch).
- `my_curriculum.py`: `get_stages() -> list[CurriculumStage]`
- `my_submission.py` — sets `BUNDLE_DIR`/`TEAM_NAME`/`SERVER_IP`(+`BT_DLL`/`BT_RULE_XML` for
  BT/hybrid) and wraps `run_unreal_inference.py` for competition submission.
- `reward_lib.py` — SI-unit reward/geometry primitives, imported by `my_reward.py`.
  `positional_advantage()` (zero weight by default) and `energy_advantage()` (added 2026-07-16,
  `E_s = h + V^2/2g` differential, enabled at 0.05 on the neutral-merge stages only — habfm +
  two_circle + full_dogfight) are both wired in; turn-rate/radius and one-circle/two-circle
  classification are not yet ported — see the module's own docstring for per-function wiring
  status before assuming any of it is live. Also holds `WEZ_PHASES`/`wez_pursuit_multipliers()`
  (added 2026-07-15) — a student-space copy of the phase-widening data/logic re-homed here after
  `src/dogfight/config.py`'s own copy was reverted and deliberately left un-restored (see the
  2026-07-15 incident callout above); only feeds `my_reward.py`'s pursuit-shaping term, does not
  affect the platform's actual damage/health computation.

`experiments/*.yaml` are the unit of experiment config, dispatched by `scripts/run_experiment.py`;
`env.reward_module`/`env.observation_module` inject the `student.*` dotted module paths above.
Output artifacts land under `artifacts/{logs,models,checkpoints,records,dashboard,curriculum}/
<output.name>/<output.tag>/`.

`RLLibLstm/` is a vendored, opt-in patch set for Ray 2.54.0 RLlib's SAC implementation adding
actor/critic LSTM support (`RLLibLstm/tools/apply_rllib_sac_lstm_patch.py` patches the installed
conda env's `ray` package in place). Only relevant when working on recurrent-policy training —
see `RLLibLstm/README.md` / `SAC_LSTM_FULL_GUIDE.md` before touching it.
