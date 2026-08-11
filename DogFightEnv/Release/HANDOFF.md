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
Seven curriculum campaigns (v1-v6 complete, v7 running) have produced **zero wins and zero
competition-usable bundles**. What scores is `MODE="vptrack"` -- the native BT keeps tactics,
throttle and blackboard state, and `student/controller_providers.py::VPTrackingProvider` takes
roll/pitch/rudder inside a terminal envelope, replacing `Controller_CY`'s VP->stick law.

Measured, N=30, identical seeds, vs the same BT opponent:

| | wins | WEZ-contact eps | damage dealt/taken |
|---|---|---|---|
| `MODE="bt"` | 0/30 | 0/30 | 0.00 / 0.000 |
| `MODE="vptrack"` | 12/30 | 30/30 | 15.59 / 0.000 |

On the official beam-merge geometry (`match_base`) the retuned envelope scores **22/30 (73.3 %)**
with 8 kills and zero losses. **But read the calibration**: against a *peer* running the same
backend it is **7W/16D/7L (23.3 %)**, and draws do not qualify under the 제1안 cutoff. Every
BT-relative number in the docs is an upper bound -- our own BT never shoots.

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
| `v7` | **RUNNING** since 2026-08-11 13:46:24. See the warning below before reading its results. |

--------------------------------------------------------------------------------
## !!! v7 is live -- do not trust its stage results yet

A curriculum campaign is running (`experiments/real_eagle_v7.yaml`). Two things to know:

1. **Stage 1 advanced on stage 0's metrics** (COMPETITION_PLAN.md 4.1 **F6**). The E2 carry-forward
   persists values across stage boundaries and the advancement gate never checks
   `metrics_age_iters`, so stage 1 closed **zero episodes of its own** and still advanced. Any
   stage whose rows all show `metrics_age_iters > 0` advanced on stale data.
2. **Episode closure is ~1 per 27 iterations**, so every gate metric is effectively a
   single-episode estimate.

Progress source of truth: `artifacts/curriculum/real_eagle/v7/training_log.csv` and
`curriculum_state.json` (both flush every iteration; the console lags due to buffering).
**Check `metrics_age_iters` on every row before believing a number.**

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
1. **Fix F6** (stale-metric stage advancement) before any v7 stage result is used.
2. **Ask the organizers whether each side gets its own rule XML.** If yes, `Gate2_BeamMerge` and
   every future BT change becomes locally measurable; if no, they can only be adopted on mechanism
   (4.1 **F1-BLIND**).
3. **The ~4 G ceiling** (4.1 **F5**): the aircraft never exceeds 3.95 G p95 though the action path
   delivers 14.86 G. It bounds the BT and would bound any RL policy identically.
4. **The DQ workstream has never been started** and is the largest un-mitigated risk to a podium
   result. `student/submission_resilience.py` exists but has never been stress-tested.
5. **`match_base` stages are not in the curriculum.** `student/match_scenario_wrapper.py` exists
   and is used only by eval scripts; `student/my_curriculum.py` trains on `obfm_*` and
   `two_circle_headon`, **neither of which is the competition geometry**.

## Guardrails (compliance -- keep it this way)
- `src/dogfight/**` is a hard no-edit boundary. Route new logic through `student/**`,
  `experiments/*.yaml`, or the entry scripts (`train_*.py` / `run_*.py`).
- Never rename/move/delete runtime assets (`AIP_BASE*.dll`, `JSBSimAIPLib.dll`, Rule XMLs,
  `aircraft/`, `engine/`, `scripts/*_cruise.xml`) -- content edits only.
- Preserve `src/dogfight/unreal/protocol.py`'s wire format. Keep `--action-repeat 6`
  (the 1/6 s compute-budget rule) matched to training `step_ratio=6`.
- **"It is in the tree" is not "it is wired in."** Three features have shipped inert
  (`DECO_BFMCheck`, `_recycle_native_bts()` for hybrid, the G limiter). Show a call site.
