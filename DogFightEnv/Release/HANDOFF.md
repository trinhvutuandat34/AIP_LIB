# HANDOFF -- real_eagle (AIP TGC 2026)

Last updated: 2026-08-11. Working dir for every command below: `DogFightEnv/Release/`
(PowerShell, `aip` conda env). This file is the operational critical path; the "why"
lives in `References and Manuals/` (COMPETITION_PLAN.md, PROJECT_ANALYSIS.md, etc.).

> **Rewritten 2026-08-11.** The previous revision was dated 2026-08-01 and told you to rebuild the
> DLL and run v5. Both are long done and v5 is known-dead. Everything below reflects the tree as it
> actually stands.

--------------------------------------------------------------------------------
## Where the project actually is

**The submission is a BT + hand-written controller. There is no usable RL policy.**
Seven curriculum campaigns (v1-v6 complete, v7 stopped and void) have produced **zero wins and
zero competition-usable bundles**. What scores is `MODE="vptrack"` -- the native BT keeps tactics,
throttle and blackboard state, and `student/controller_providers.py::VPTrackingProvider` takes
roll/pitch/rudder inside a terminal envelope, replacing `Controller_CY`'s VP->stick law.

Measured, N=30, identical seeds, vs the same BT opponent:

| | wins | WEZ-contact eps | damage dealt/taken |
|---|---|---|---|
| `MODE="bt"` | 0/30 | 0/30 | 0.00 / 0.000 |
| `MODE="vptrack"` | 12/30 | 30/30 | 15.59 / 0.000 |

On the official beam-merge geometry (`match_base`) the retuned envelope scores **22/30 (73.3 %)**
with 8 kills and zero losses. **But read the calibration** (re-measured 2026-08-11, N=30 each,
4.1 F11): against a *peer* running the same backend it is **9W/16D/5L (30.0 %)** with damage
**13.07 dealt / 12.43 taken**, and draws do not qualify under the 제1안 cutoff.

**"Zero damage taken" is a property of the opponent, not our defence.** Damage taken: vs our own
BT **0.000**, vs a peer on the old tuning **0.000**, vs a peer on the same config **12.43**. Only
the symmetric fight puts a gun on us, and there we take 95 % of what we deal. Every BT-relative
number in these docs is an upper bound -- our own BT never shoots.

--------------------------------------------------------------------------------
## Current state of the moving parts

| Thing | State |
|---|---|
| `student/my_submission.py` | `MODE="vptrack"`, `TEAM_NAME="real_eagle"`. Loads **no RL bundle**. G-limited at 10 G. |
| `BUNDLE_DIR` | **`None`** (set 2026-08-11). Was a placeholder path to `v4/stage_3`, a **100 %-crash** policy that the health gate passes because it is finite-but-degenerate. Selecting any `rl`/`hybrid*` mode now **raises** instead of silently arming it. Replace with a validated bundle path when one exists. |
| `SERVER_IP` | `221.151.77.208` -- **unconfirmed**, differs from `startup_command.txt`'s `10.185.16.247`. Confirm with organizers. Two network incidents = DQ. |
| `AIP_BASE.dll` / `AIP_BASE_target.dll` | Built 2026-08-06 15:08, newer than every `AIP_DCS` source (newest `Controller_CY.cpp`, 14:26). **No rebuild owed.** |
| `Rule_forTraining.xml` / `Rule_real_eagle.xml` | **Byte-identical** (MD5 `5C5979DB...`). Both carry `Gate2_BeamMerge`. `my_submission.py` loads `Rule_forTraining.xml`. |
| G limiter | Active on **every** path -- eval, `run_local_dogfight`, live submission, and RL training (`GLimitWrapper`). |
| `v7` | **STOPPED 2026-08-11 14:33** at stage 2 / 313 iterations. Its stage results are void (F6). Relaunch as **v8**; do not resume v7. |

--------------------------------------------------------------------------------
## !!! v7 is void -- relaunch as v8

v7 was stopped 2026-08-11 14:33 at stage 2 / 313 iterations. Its stage advances were invalid
(COMPETITION_PLAN.md 4.1 **F6**): the advancement gate averaged over ROWS rather than episodes, so
stage 0 advanced reading `crash_rate=0.2000` when its true per-episode rate was **0.8571**, and
stage 1 advanced having closed **zero episodes of its own**. Fixed 2026-08-11. **Do not `--resume`
v7** -- start a fresh `v8` tag so no stage carries a checkpoint earned under the broken gate.

What changed, and what it costs:
- Advancement now consumes **one row per closed episode**, so `advance_window=10` means an average
  over 10 real episodes. Measured cost: **~27 iterations per episode ⇒ ~270 iterations ≈ 49 min
  per stage**. Sampling was deliberately left unchanged (F6-COST).
- **Stage budgets raised 200 → 400 on ten stages** so those gates can actually be reached. A stage
  budgeted at 200 closes only ~7.4 episodes and can never evaluate a 10-episode window -- it exits
  on `max_iterations` with the condition untested, silently. That hit ten of the fifteen gated
  stages, including all three `match_base` ones. Campaign is now **7,300 iterations ≈ 22 h**.
- Carried metrics are **reset at every stage boundary**, so a stage starts reporting `n/a` until
  it measures something itself.
- `reward_mean` / `ep_len_mean` are carried with the custom metrics under one shared
  `metrics_age_iters` instead of going `nan` on ~84 % of rows.

Progress source of truth: `artifacts/curriculum/real_eagle/<tag>/training_log.csv` and
`curriculum_state.json` (both flush every iteration; the console lags due to buffering).
**`metrics_age_iters == 0` marks a row backed by an episode that actually closed** -- those are
the only rows the gate now counts, and the only ones worth averaging by hand.

--------------------------------------------------------------------------------
## Submission -- the path that matters

```powershell
python student\my_submission.py
```

Before a real slot: confirm `SERVER_IP` with the organizers, and leave `MODE="vptrack"` alone
unless a bundle exists that has been shown to beat `vptrack` alone. Latency is not a concern --
49.6 us per decision, 0.03 % of the 166.7 ms six-frame budget.

`hybrid_gated` (`EnvelopeGatedHybridProvider`) is the upgrade path the moment such a bundle
exists: it removes the residual cliff structurally and holds 13/30 at the full 0.35 scale that
destroys the ungated version. It is a config change, not a rebuild.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------
## !!! PENDING, HELD DELIBERATELY: the behaviour tree is dead code below Gate 2.5

**Do this first when v8 finishes.** `COMPETITION_PLAN.md` 4.1 **F25**: a `name` attribute on a
control node makes BehaviorTree.CPP build it with **zero children**. Measured at build time via
`childrenCount()`: all 3 anonymous `<Sequence>`/`<Fallback>` nodes have children (1, 8, 9); **all
17 named ones have 0.** An empty `Sequence` returns SUCCESS immediately and an empty `Fallback`
returns FAILURE immediately, so:

- `Gate2p5_GunSolutionHold` (Sequence, 0 children) **succeeds unconditionally and wins every
  tick**, blocking Gates 1/2/3/4 and the tail
- every other gate block fails or succeeds vacuously

**The only nodes that have ever executed are `Gate0_ClimbToSafeAltitude` and
`Tail_SingleSideOffset`.** All 23 `Task_*` maneuver classes, all five gate blocks and every
decorator have never run. This is the mechanical explanation for C2, A4, and every positional null
in the register.

**Fix: drop `name=` from the 17 control nodes in `Rule_forTraining.xml` / `Rule_real_eagle.xml`.**
XML-only, no rebuild. Leaf `Task_*` / `DECO_*` names must STAY -- those nodes work and the names
are what `GateTrace.h` reports.

**Why it is held:** this is not a tuning change, it switches the tactical layer on for the first
time. v8 is training against `AIP_BASE_target.dll` and reaches its first BT stage (index 4,
`obfm_offensive`) at iteration 1600; changing the tree before then would swap its opponent
mid-campaign. Apply after v8 completes, then **re-baseline from scratch** -- every prior BT
measurement in the register is void once this lands, not merely suspect.

Verify with: `AIP_BT_GATE_TRACE=<path> python scripts\eval_v5_vs_bt.py --ownship-backend bt
--target-backend bt --scenario-mode match_base --episodes 1` and check the `.nodes.txt` dump shows
non-zero child counts for the gate composites.

--------------------------------------------------------------------------------
## Regression guards -- run these before committing compute or submitting

There is no CI and no test suite for the core package, so these are the tripwires. All three exit
0 on success and name the register row each check protects.

```powershell
python scripts\verify_report_fixes.py    # ~seconds, no sim: gate/telemetry/curriculum/v8 config
python scripts\verify_match_spawn.py     # ~1 min, real envs: match_base stages spawn correctly
python scripts\verify_resilience.py      # ~seconds: DQ guards under injected faults
```

Run the first two after touching `train_curriculum.py`, `student/my_curriculum.py` or an
`experiments/*.yaml`; the third before any submission. They exist because every defect they cover
**failed silently** -- a stage advancing on stale metrics, a metric reading `nan`, a record that
never saved, a wrapper that was never wired in. None of those show up in a training log.

## Local verification

BT-vs-BT smoke (tree constructs, DLL healthy):
```powershell
python run_local_dogfight.py --ownship-backend bt --target-backend bt --save-log --max-engage-time 90
```

The controller vs the BT, on the real match geometry:
```powershell
python scripts\eval_v5_vs_bt.py --ownship-backend vptrack --target-backend bt --scenario match_base --episodes 30
```

Per-side controller settings -- **the only harness that can measure an edge** (both aircraft read
one global rule XML, so BT-side changes cannot be given to one side only):
```powershell
python scripts\eval_v5_vs_bt.py --scenario match_base --episodes 30 ^
  --ownship-vptrack-range-m 2500 --ownship-vptrack-los-deg 45 ^
  --target-vptrack-range-m 1200 --target-vptrack-los-deg 20
```

**Never compare on a single episode.** The harness is bimodal from a 0.017 deg spawn perturbation
inside `JSBSimAIPLib.dll`'s reset (COMPETITION_PLAN.md 4.1 **E1**) -- use N>=30 success rates, and
report kills/damage alongside win rate (a config once held 73.1 % while damage collapsed 96 %).

--------------------------------------------------------------------------------
## Known-broken -- do NOT use
- `artifacts/curriculum/real_eagle/v4/**`: stage 3 = 100 % crash, stages 4-7 NaN-diverged,
  stages 0-2 trivial-opponent-only. Diagnostic artifacts only; do not `--resume` v4.
- `v5` (100 % self-crash) and `v6` (18/20 crash, 0 wins, 0 WEZ). Both trained blind -- their gate
  metrics were logged **zero times** across 4,700 iterations each (E2, fixed 2026-08-06).
- Any pre-2026-07-14 practice-match result involving the RL or hybrid backend: the policy was
  flying with a corrupted throttle channel.

## Open follow-ups, in priority order
1. **Launch v8.** The config exists -- `experiments/real_eagle_v8.yaml`, dry-run clean, 16 stages:
   ```powershell
   python scripts\run_experiment.py experiments\real_eagle_v8.yaml
   ```
   Then check the first stage behaves: rows with `metrics_age_iters == 0` should appear about
   every 27 iterations, no stage should advance until ten of them exist, and a stage's first rows
   should read `n/a` rather than the previous stage's numbers. Expect **~49 min per stage, ~22 h total**. **Never point a v7 tag at this curriculum** -- the match_base ladder changed the
   meaning of every stage index after the first two-circle stage.
2. **Ask the organizers whether each side gets its own rule XML.** If yes, `Gate2_BeamMerge` and
   every future BT change becomes locally measurable; if no, they can only be adopted on mechanism
   (4.1 **F1-BLIND**).
3. **The ~4 G ceiling** (4.1 **F5**): the aircraft never exceeds 3.95 G p95 though the action path
   delivers 14.86 G. It bounds the BT and would bound any RL policy identically.
4. **The DQ workstream has never been started** and is the largest un-mitigated risk to a podium
   result. `student/submission_resilience.py` exists but has never been stress-tested.
5. ~~`match_base` stages are not in the curriculum.~~ **DONE 2026-08-11** (F8, F8-STAGES): the
   wrapper is wired into training and the ladder exists -- `match_base_wide` → `match_base_close`
   → `match_base`, replacing two-circle alphas 45/90/135/180. **v8 is the first campaign that will
   train the geometry the competition actually opens with.** Watch those three stages first.

## Guardrails (compliance -- keep it this way)
- `src/dogfight/**` is a hard no-edit boundary. Route new logic through `student/**`,
  `experiments/*.yaml`, or the entry scripts (`train_*.py` / `run_*.py`).
- Never rename/move/delete runtime assets (`AIP_BASE*.dll`, `JSBSimAIPLib.dll`, Rule XMLs,
  `aircraft/`, `engine/`, `scripts/*_cruise.xml`) -- content edits only.
- Preserve `src/dogfight/unreal/protocol.py`'s wire format. Keep `--action-repeat 6`
  (the 1/6 s compute-budget rule) matched to training `step_ratio=6`.
- **"It is in the tree" is not "it is wired in."** Three features have shipped inert
  (`DECO_BFMCheck`, `_recycle_native_bts()` for hybrid, the G limiter). Show a call site.
