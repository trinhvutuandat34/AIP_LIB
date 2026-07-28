# COMMAND.md

Every command line this project actually uses, in one place, with what each one does. Two kinds
of entries appear here:

- **real_eagle (this team's setup)** — exact, working invocations for our actual bundles/configs.
  Paths and flags here are real, not placeholders — copy-paste them as-is.
- **Generic template reference** — the platform's own `student_*.yaml` / `team01` examples from
  `DogFightEnv/Release/README.md`, kept here so the whole command surface is in one file. These
  use placeholder names (`team01`, `v1`) — swap in real values before running.

All commands assume: PowerShell, `conda activate aip`, and `cd D:\AIP\AIP_LIB\DogFightEnv\Release`
(the working directory every entry script's relative paths resolve against). See
`CLAUDE.md`/`PROJECT_STRUCTURE.md` for why that's the working directory and what lives where.

---

## 1. Environment setup

```powershell
conda activate aip
```
Activates the `aip` conda env — the only interpreter this project is tested against
(`ray[rllib]==2.54.0`, `torch>=2.3,<3.0`, `gymnasium>=1.0,<2.0`, `numpy==2.2.6`, `pymap3d`,
`PyYAML`). Every command below assumes this is active; if you see `ModuleNotFoundError:
pymap3d`-style errors, this step was skipped.

```powershell
python -m pip install -r requirements.txt
```
One-time (or after a `requirements.txt` change) dependency install into the active env.

---

## 2. Verification / dry-run (do these before any real run)

```powershell
python -m py_compile train_rllib.py train_curriculum.py scripts\run_experiment.py student\my_reward.py student\my_observation.py student\my_observation_v2.py student\my_curriculum.py student\reward_lib.py student\obfm_scenario_wrapper.py student\habfm_scenario_wrapper.py student\inference_providers.py
```
Syntax-checks every student-space + entry-point file without running anything. Catches typos/
import errors in seconds; run this after editing any `student/*.py` file before launching a real
(possibly hours-long) training job.

```powershell
python scripts\run_experiment.py experiments\real_eagle_v4.yaml --dry-run
```
Resolves a YAML into the exact `train_curriculum.py`/`train_rllib.py` CLI invocation it would run
and prints it — **no training starts**. Always run this after touching an `experiments/*.yaml`
file or any module it points at (`reward_module`, `observation_module`, `stages_module`) to catch
config errors (missing keys, bad paths) before committing to a real run.

```powershell
python -m student.reward_lib
```
Runs `reward_lib.py`'s own `__main__` smoke test: sign/symmetry/saturation regression guards for
`positional_advantage()` and `energy_advantage()`. Run this after editing `reward_lib.py` — it
takes under a second and would have caught, e.g., a flipped energy sign convention immediately.

---

## 3. Training — real_eagle v4 (this project's actual run)

```powershell
python scripts\run_experiment.py experiments\real_eagle_v4.yaml
```
**The one command to (re)launch this team's actual training.** Reads `experiments/real_eagle_v4.yaml`
(`output.tag: v4`, `algo.name: sac`, `env.reward_module: student.my_reward`,
`env.observation_module: student.my_observation_v2`, `curriculum.stages_module:
student.my_curriculum`, `runtime.num_env_runners: 0`) and dispatches to `train_curriculum.py`.
Because the yaml has `runtime.resume: true` baked in, this **same command both starts a fresh run
and resumes a paused one** — it checks `artifacts/curriculum/real_eagle/v4/curriculum_state.json`
and picks up from the last completed stage/iteration if that file exists, or starts stage 0 fresh
if it doesn't. Do not add `--resume` yourself; it's already implied by the yaml.

Progress: watch `artifacts\curriculum\real_eagle\v4\curriculum_state.json` (current
stage/iteration) and `training_log.csv` (per-iteration metrics) directly — PowerShell
block-buffers this script's stdout when piped/redirected, so console output can lag real progress
by minutes. Stop with Ctrl+C; native checkpoints save every 10 iterations
(`checkpoint_interval`), so an interrupt loses at most that much.

```powershell
python train_curriculum.py --algorithm sac --output-name real_eagle --output-tag v4 --reward-module student.my_reward --observation-mode custom --observation-module student.my_observation_v2 --stages-module student.my_curriculum --num-env-runners 0 --resume
```
A **partial** manual equivalent — hits the same reward/observation/curriculum modules and resumes
the same run, but omits the yaml's algo hyperparameters (`--lr 3e-4 --gamma 0.99
--train-batch-size 256 --minibatch-size 256 --tau 0.005 --target-entropy auto
--replay-buffer-capacity 100000 --model-fcnet-hiddens 256,256 ...`) and the policy-probe/
engagement-log settings, so it would train with RLlib's SAC defaults for those instead of v4's
tuned values. Only use this form for a quick one-off flag override you don't want to touch the
yaml for; run the `--dry-run` below first and copy its full printed argv if you need the exact
equivalent.

```powershell
python scripts\run_experiment.py experiments\real_eagle_v4.yaml --dry-run
```
Confirms the resolved argv before a real launch — see §2. Cheap, always safe to run first.

---

## 4. Training — generic template reference (student_*.yaml / team01 examples)

Six starter YAMLs ship in `experiments/`: `student_sac_mlp.yaml`, `student_ppo_mlp.yaml`,
`student_sac_lstm.yaml`, `student_ppo_lstm.yaml`, `student_mixed_initial_sac_mlp.yaml`,
`student_mixed_initial_sac_lstm.yaml`. All use `script: train_rllib` (single-stage, not
curriculum).

```powershell
python scripts\run_experiment.py experiments\student_sac_mlp.yaml --dry-run
python scripts\run_experiment.py experiments\student_sac_mlp.yaml
```
Dry-run then launch the plain SAC-MLP starting point — the generic first thing to try before
building a team-specific curriculum like `real_eagle_v4.yaml`.

```powershell
python train_rllib.py --algorithm sac --iterations 50 --observation-mode tactical16 --target-mode behavior_tree --target-behavior-dll AIP_BASE_target.dll --output-name team01 --output-tag single_stage_v1
```
Single-stage training with the platform's default reward/observation — no student modules
injected. Good for a from-scratch sanity check that the env/DLL/JSBSim stack works before adding
any custom code.

```powershell
python train_rllib.py --algorithm sac --iterations 50 --reward-module student.my_reward --observation-mode tactical16 --target-mode behavior_tree --target-behavior-dll AIP_BASE_target.dll --output-name team01 --output-tag reward_v1
```
Same, but injects `student/my_reward.py`'s `compute_reward()` — the minimal way to test a reward
change in isolation.

```powershell
python train_rllib.py --algorithm sac --iterations 50 --observation-mode custom --observation-module student.my_observation --reward-module student.my_reward --output-name team01 --output-tag observation_v1
```
Adds a custom observation vector (`student/my_observation.py`) on top of the custom reward.
Changing observation size breaks compatibility with any existing checkpoint/bundle trained on a
different size — expect to start a fresh `--output-tag` whenever `OBSERVATION_SIZE` changes (this
is exactly why `real_eagle` uses a separate `my_observation_v2.py` file rather than editing the v1
one in place).

```powershell
python train_curriculum.py --algorithm sac --reward-module student.my_reward --stages-module student.my_curriculum --output-name team01 --output-tag curriculum_v1
```
Generic staged-curriculum training (built-in 15-stage progression, or your own via
`--stages-module`) instead of a single fixed stage.

```powershell
python student\my_train.py --iterations 50
```
The optional simple wrapper (`student/my_train.py`) — use only if you want a thin script instead
of a YAML-driven run. The team's actual recommended path is YAML (`run_experiment.py`), not this.

---

## 5. Checkpoint resume / bundle restart

Two independent save formats, controlled separately:

| Format | Contains | Use for |
|---|---|---|
| **Native checkpoint** | Full RLlib state (weights + optimizer + replay buffer) | Resuming the *same* training run |
| **Lightweight bundle** | `metadata.json` + `policy_weights.pkl.gz` only | Submission/inference, or warm-starting a *different* run from these weights |

```powershell
python train_rllib.py --algorithm sac --iterations 50 --lightweight-bundle-frequency 10 --save-native-checkpoint --native-checkpoint-frequency 10 --output-name team01 --output-tag v1
```
Trains while saving both formats periodically (every 10 iterations here).

```powershell
python train_rllib.py --algorithm sac --iterations 50 --restore-checkpoint artifacts\checkpoints\team01\v1\checkpoint_000010 --output-name team01 --output-tag v1_resume
```
Resumes the *exact same* training state (optimizer, replay buffer included) from a native
checkpoint, under a new tag.

```powershell
python train_curriculum.py --algorithm sac --output-name team01 --output-tag curriculum_v1 --resume
```
Curriculum-specific resume: continues an interrupted/paused curriculum run from
`curriculum_state.json` — this is the flag baked into `real_eagle_v4.yaml`'s `runtime.resume:
true` (see §3). Prefer `--resume` over `--restore-checkpoint` for curriculum runs; use
`--restore-checkpoint` only to start a *new* curriculum run seeded from a specific old checkpoint.

```powershell
python train_rllib.py --algorithm sac --iterations 50 --init-bundle artifacts\models\team01\v1 --output-name team01 --output-tag bundle_restart_v1
```
Starts a brand-new run (fresh optimizer/replay buffer) with policy weights initialized from an
existing lightweight bundle — use this to warm-start a differently-configured experiment from
previously-trained weights, not to continue the same run.

In YAML, the equivalent keys live under `runtime`:
```yaml
runtime:
  save_lightweight_bundle: true
  lightweight_bundle_frequency: 0   # 0 = final only
  save_native_checkpoint: true
  native_checkpoint_frequency: 10
  resume: true                     # train_curriculum only
  restore_checkpoint: <path>       # mutually exclusive with init_bundle
  init_bundle: <path>
```

---

## 6. LSTM / recurrent network templates (advanced — not part of real_eagle's current setup)

Team strategy memory: real_eagle uses **SAC MLP only**, no LSTM — this section is reference for
if that changes, not something currently in use.

```powershell
python scripts\run_experiment.py experiments\student_sac_lstm.yaml --dry-run
python scripts\run_experiment.py experiments\student_ppo_lstm.yaml --dry-run
python scripts\run_experiment.py experiments\student_mixed_initial_sac_mlp.yaml --dry-run
python scripts\run_experiment.py experiments\student_mixed_initial_sac_lstm.yaml --dry-run
```
Dry-run every recurrent/mixed-scenario template. Requires `RLLibLstm/`'s patch to be applied to
the conda env's installed `ray` package first (see `RLLibLstm/README.md`) — SAC has no native
LSTM support in Ray 2.54.0, this project vendors a patch for it.

```powershell
python train_rllib.py --algorithm sac --iterations 10 --use-lstm-sac --lstm-cell-size 64 --max-seq-len 8 --debug-io --output-name team01 --output-tag sac_lstm_smoke
```
Actor-only recurrent SAC smoke test (critic stays MLP). `--debug-io` prints `seq_lens`/recurrent
state/Q-concat order for verifying the LSTM plumbing — turn it off for real long runs, the output
is verbose.

```powershell
python train_rllib.py --algorithm sac --iterations 30 --train-batch-size 64 --rollout-fragment-length 8 --use-lstm-sac --lstm-scope actor_critic --lstm-cell-size 64 --max-seq-len 8 --debug-io --output-name team01 --output-tag sac_lstm_actor_critic
```
Full recurrent actor+critic (`actor_critic` scope) — mimics the older Ray 1.9.2 RNNSAC structure
under Ray 2.54's New API.

---

## 7. Monitoring — dashboard

```powershell
python tools\dashboard.py --training-logdir artifacts\dashboard --logdir logs --port 7860
```
Launches the unified web dashboard at `http://127.0.0.1:7860` — **Training** tab reads
`metrics.jsonl`-style training curves, **Replay** tab reads Tacview-format CSV pairs from
engagement logs. This is the standard way to watch a run instead of parsing CSVs by hand.

```powershell
python tools\dashboard.py --default-tab replay --logdir artifacts\curriculum\real_eagle\v4\engagement_replays --port 7860
```
real_eagle-specific: opens straight to the Replay tab pointed at v4's own periodic engagement
replays (`engagement_log.enabled: true` in `real_eagle_v4.yaml`, saved every 100 iterations, 400
steps/episode) — the trajectory-level view that catches behavior (e.g. a crash-suicide pattern)
that stage-level win/loss aggregates alone can hide.

Full flag reference (`--env-root`, `--training-logdir`, `--logdir`/`--replay-logdir`, `--mesh`,
`--default-tab {training,replay}`, `--host`, `--port`) is in
`tools/dogfight_dashboard/server.py::parse_args()`.

---

## 8. Local engagement verification (before any live-server run)

Backends for `--ownship-backend`/`--target-backend`: `rl` | `bt` | `hybrid` | `fixed`.

```powershell
python run_local_dogfight.py --ownship-backend hybrid --ownship-bundle-dir artifacts\curriculum\real_eagle\v4\stage_3_autopilot_pursuit\final_bundle --observation-mode custom --observation-module student.my_observation_v2 --target-backend bt --save-log
```
**real_eagle's actual local sanity-check command** (from `student/my_submission.py`'s own
docstring) — runs one episode of the team's current hybrid provider (BT + residual RL, scale
0.35) against a plain BT opponent, entirely locally (no Unreal server, no network). `--save-log`
writes matched-timestamp ownship/target Tacview CSVs + a summary JSON (`end_condition`, `outcome`,
both sides' Health) to `logs/` — the standard pre-submission replay-review procedure. Not a crash
dump: an unhandled exception, `KeyboardInterrupt`, or failed reset/build skips this write.

```powershell
python run_local_dogfight.py --ownship-backend rl --ownship-bundle-dir artifacts\models\team01\observation_v1 --target-backend bt --observation-mode custom --observation-module student.my_observation
```
Generic template version (RL-only ownship, no logging) — swap in real bundle/module paths for
actual use.

Full flag list: `--ownship-bundle-dir`, `--target-bundle-dir`, `--ownship-bt-dll` (default
`AIP_BASE.dll`), `--target-bt-dll` (default `AIP_BASE_target.dll`), `--bt-rule-xml`,
`--ownship-policy-id`/`--target-policy-id`, `--observation-mode {classic12,relative14,tactical16,custom}`,
`--observation-module`, `--hybrid-mode {residual,blend,switch}`, `--alpha`, `--residual-scale`,
`--max-engage-time`, `--episode-step-limit`, `--min-altitude`, `--save-log`.

---

## 9. Matchup evaluation (batch benchmark, not single-episode)

```powershell
python scripts\eval_matchup.py --ownship-backend hybrid --ownship-bundle-dir artifacts\curriculum\real_eagle\v4\stage_3_autopilot_pursuit\final_bundle --observation-mode custom --observation-module student.my_observation_v2 --target-backend bt --episodes 30 --out-csv artifacts\eval\hybrid_vs_bt.csv
```
Runs N episodes (default: varying the two-circle head-on `alpha` 0/20/.../180 across episodes,
same schedule the curriculum ladder uses) of one backend pairing and writes per-episode outcomes
to CSV — the intended way to compare standalone-RL vs. hybrid-residual vs. BT-alone on identical
starting geometry, per `COMPETITION_PLAN.md` §8's decision criteria. Reuses
`run_local_dogfight.py`'s provider construction; only run this when nothing else is training (each
episode spins up its own JSBSim instance, competing for CPU with any active training job).

Full flag list mirrors §8 plus: `--episodes`, `--out-csv`, `--seed`, `--dry-run` (prints the
resolved config without running episodes).

---

## 10. Live Unreal inference / competition submission

```powershell
python student\my_submission.py
```
**The actual submission entry point.** Reads the hardcoded config at the top of
`student/my_submission.py` (currently: `TEAM_NAME="real_eagle"`, `MODE="hybrid"`,
`BUNDLE_DIR="artifacts/curriculum/real_eagle/v4/stage_3_autopilot_pursuit/final_bundle"`,
`BT_DLL="AIP_BASE.dll"`, `BT_RULE_XML="Rule_forTraining.xml"`, `HYBRID_MODE="residual"`,
`RESIDUAL_SCALE=0.35`, `SERVER_IP="221.151.77.208"`, `SERVER_PORT=9999`) and connects to the
competition server over UDP. **Update `SERVER_IP` from the latest official announcement before
running** — the value in the file is marked not-yet-confirmed as of this writing (differs from
`startup_command.txt`'s `10.185.16.247`, believed to be a private/practice network address, not
the competition server). Also note: `BUNDLE_DIR` currently points at stage 3
(`autopilot_pursuit`) — the newest available `final_bundle` — because v4's stage 4
(`obfm_offensive`, the first adversarial stage) was still in progress as of this writing; update
this path once a later stage's `final_bundle` exists.

Equivalent direct CLI (bypassing `my_submission.py`, useful for one-off overrides):

```powershell
python run_unreal_inference.py --mode hybrid --bundle-dir artifacts\curriculum\real_eagle\v4\stage_3_autopilot_pursuit\final_bundle --observation-mode custom --observation-module student.my_observation_v2 --bt-dll AIP_BASE.dll --bt-rule-xml Rule_forTraining.xml --hybrid-mode residual --residual-scale 0.35 --team-name real_eagle --server-ip <server-ip> --server-port 9999 --action-repeat 6
```
Hybrid mode (BT + 0.35-scaled RL residual) — the team's confirmed competition strategy.

```powershell
python run_unreal_inference.py --mode bt --bt-dll AIP_BASE.dll --bt-rule-xml Rule_forTraining.xml --team-name real_eagle --server-ip <server-ip>
```
BT-only (no RL model needed) — useful as a fallback / for isolating whether an issue is in the RL
side or the connection/BT side.

```powershell
python run_unreal_inference.py --mode rl --bundle-dir artifacts\curriculum\real_eagle\v4\stage_3_autopilot_pursuit\final_bundle --observation-mode custom --observation-module student.my_observation_v2 --team-name real_eagle --server-ip <server-ip> --server-port 9999
```
RL-only — not the team's chosen strategy, but useful for isolating RL-specific behavior.

**`--action-repeat 6` matters**: must match training's `step_ratio: 6` (each policy action holds
for 6 physics ticks) — using a different value here than what the bundle was trained under is a
live train/inference mismatch, not just a performance tweak.

Full flag reference: `--mode {rl,bt,hybrid}` (required), `--server-ip`, `--server-port`,
`--team-name`, `--simulation-state`, `--heartbeat-sec`, `--command-delay-sec`, `--recv-timeout-sec`,
`--action-repeat`, `--debug-action-repeat`, `--packet-monitor`,
`--packet-monitor-interval-sec`, `--observation-mode {classic12,relative14,tactical16,custom}`,
`--observation-module`, `--ownship-force-side`, `--target-force-side`, `--bt-dll`,
`--bt-rule-xml`, `--bundle-dir`, `--policy-id`, `--explore`, `--hybrid-mode
{residual,blend,switch}`, `--alpha`, `--residual-scale`, `--ai-type {rule,rl,sl,fusion,etc}`.

---

## 11. Tests

```powershell
cd tools\web_log_viewer
python -m pytest tests\test_log_data.py::LogDataTest::test_pair_discovery_and_replay_math
```
The only test suite in the project (`tools/web_log_viewer/tests/` and
`tools/dogfight_dashboard/tests/`) — there is no test suite for the core `src/dogfight` package
itself. Run from inside `tools\web_log_viewer` as shown.

---

## Quick reference: the 5 commands you'll actually run day to day (real_eagle)

```powershell
conda activate aip
cd D:\AIP\AIP_LIB\DogFightEnv\Release

# 1. After editing any student/*.py file
python -m py_compile student\my_reward.py student\my_curriculum.py student\reward_lib.py

# 2. After editing experiments/real_eagle_v4.yaml or a module it points at
python scripts\run_experiment.py experiments\real_eagle_v4.yaml --dry-run

# 3. Launch / resume the actual training run (auto-resumes if paused)
python scripts\run_experiment.py experiments\real_eagle_v4.yaml

# 4. Watch progress
python tools\dashboard.py --training-logdir artifacts\dashboard --logdir logs --port 7860

# 5. Before touching the live server, sanity-check locally
python run_local_dogfight.py --ownship-backend hybrid --ownship-bundle-dir artifacts\curriculum\real_eagle\v4\stage_3_autopilot_pursuit\final_bundle --observation-mode custom --observation-module student.my_observation_v2 --target-backend bt --save-log
```
