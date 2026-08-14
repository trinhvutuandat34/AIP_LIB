# HANDOFF -- real_eagle (AIP TGC 2026)

Last updated: 2026-08-13. Working dir for every command below: `DogFightEnv/Release/`
(PowerShell, `aip` conda env). This file is the operational critical path; the "why"
lives in `References and Manuals/` (COMPETITION_PLAN.md, PROJECT_ANALYSIS.md, etc.).

> **Updated 2026-08-13.** The 2026-08-11 revision told you the BT fix was pending and to launch
> v8. **The fix is applied** (F25 -> 4.1 F26, commit `5412a79`) and the tactical layer executes
> for the first time in this project's history; **v8 was retired, not resumed.** Every BT-relative
> number recorded before 2026-08-13 is void, and the four geometries that were re-measured are in
> 4.1 F26 -- the rest is listed as still-owed in F26-OWED.

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
| `v7` | **STOPPED 2026-08-11 14:33** at stage 2 / 313 iterations. Its stage results are void (F6). Superseded by v8. |
| `v8` | **RETIRED 2026-08-13, do not resume.** Killed by an unplanned machine reboot (08:24:38, five minutes after its last checkpoint write) at stage 15/16. All 14 completed stages advanced on `max_iterations_reached`, never on their own gate, and all 31 real episodes measured in stage 15 ended in a crash. Treat as pipeline validation, not a policy. **Eight campaigns, still no usable RL bundle.** |
| Rule XMLs | **F25 APPLIED 2026-08-13** (`5412a79`) -- the tactical layer executes for the first time. Still byte-identical to each other. See the section below. |

--------------------------------------------------------------------------------
## Curriculum training -- v7 void, v8 retired, and what a v9 would need

**Status 2026-08-13: no campaign is running and none is scheduled.** v7 was stopped 2026-08-11
(gate bug, F6). v8 ran on the fixed gate and was **retired 2026-08-13** after an unplanned reboot
killed it at stage 15/16 -- but its results were not worth resuming for: **all 14 completed stages
advanced on `max_iterations_reached`, never on their own condition**, and all 31 real episodes in
stage 15 ended in a crash. **Eight campaigns, zero usable bundles.**

**If a v9 is ever launched, two things changed underneath it that matter.** First, the BT opponent
is now genuinely competent (F25 applied 2026-08-13) -- every earlier campaign trained against a
tree that ran two leaf tasks, so the difficulty curve is not comparable to v1-v8. Second, and
against a hard deadline, weigh it against §8 robustness: the DQ workstream has never been started
and can lose the competition regardless of policy quality.

The v7-era gate fixes below still apply and are still correct:
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
## DONE 2026-08-13: the tactical layer is ALIVE (F25 applied)

**This section used to say "PENDING, HELD DELIBERATELY". It is applied.** Commit `5412a79`;
every number and the full detail live in `COMPETITION_PLAN.md` 4.1 **F26**.

`name=` is gone from all 17 control nodes in both rule XMLs. Leaf `Task_*`/`DECO_*` names were
left alone (they work, and they are what `GateTrace.h` reports). Verified by **instrumentation,
not outcomes**: the node inventory shows **zero empty composites**, `Gate2p5_GunSolutionHold`
went 0 -> **4 children**, and **17 nodes across all five gate blocks now win ticks where exactly
two ever had.** Gate 2.5 correctly **fails** `Gun_OwnATA_Lt8` at the merge (91 deg vs <8 deg)
instead of succeeding vacuously and swallowing every tick beneath it.

**What it is worth**, isolated through the peer rig on `match_base`, N=30, vptrack both sides,
varying only the opponent's tree: opponent **with** a working tree -> 9W/14D/7L; opponent
**without** it -> **16W/14D/0L, damage 6.99 / 0.06, zero deaths.**

**v8 was retired, not resumed** -- an unplanned reboot killed it at 08:24:38 on 2026-08-13 and
none of its 14 completed stages had advanced on a real gate. There is still **no usable RL
policy after eight campaigns**, and `MODE="vptrack"` remains the submission.

**Every BT-relative number recorded before 2026-08-13 is VOID**, including rows marked "fixed".
The re-baseline covers `match_base`, `obfm_offensive`, `obfm_defensive` and `two_circle_headon`.
Still un-re-run and still void: **A2, A3, A5, C6, the Gate 3 energy thresholds and the
`Task_Notch` carve-out** (4.1 F26-OWED). F5's and F12's G-ceiling findings are **refuted** --
there was never a control-law ceiling, it was an aircraft not manoeuvring.

Re-verify any time with:
```powershell
$env:AIP_BT_GATE_TRACE="<path>"
python scripts\eval_v5_vs_bt.py --ownship-backend bt --target-backend bt --scenario-mode match_base --episodes 1 --ownship-bt-dll AIP_BASE_gatetrace.dll --target-bt-dll AIP_BASE_gatetrace_target.dll --out-csv <path>.eval.csv
```
Check `<path>.nodes.txt` shows non-zero child counts for every composite. **The deployed
`AIP_BASE*.dll` are the 2026-08-06 build and do NOT contain `GateTrace.h`** -- the instrumented
build is at `bin/debug.x64/AIP_DCS.dll`, copied to `AIP_BASE_gatetrace*.dll`, which is why those
two flags are needed. Those copies are local-only and untracked, the same add-only pattern as
`AIP_BASE_item13.dll`; recreate with
`Copy-Item bin\debug.x64\AIP_DCS.dll DogFightEnv\Release\AIP_BASE_gatetrace.dll` if missing.

--------------------------------------------------------------------------------
## !!! READ BEFORE CHANGING THE BEHAVIOUR TREE

**Never adopt OR reject a BT change on a symmetric measurement.** Both DLLs sit in `Release/` and
read one global `Rule_forTraining.xml`, so an ordinary eval gives BOTH aircraft your change and
systematically inflates it. Score BT changes through `scripts/setup_peer_bt.py` only:

```powershell
python scripts\setup_peer_bt.py --xml experiments\rule_variants\<baseline>.xml
python scripts\eval_v5_vs_bt.py --ownship-backend vptrack --target-backend vptrack --scenario-mode match_base --episodes 30 --target-bt-dll bt_peer/AIP_BASE_target.dll
```

This is not theoretical. A Gate 1 reorder measured **10W/18D/2L -> 21W/8D/1L** the ordinary way
and looked like a large win; through the peer rig it was **6W/11D/13L against a 9W/14D/7L
control**, i.e. losing better than 2:1 on the confirmed competition geometry. Reverted
(4.1 F26-GATE1-REJECTED); variant kept at
`experiments/rule_variants/gate1_break_first_EXPERIMENTAL.xml`. The tell was visible in the
symmetric numbers and is F5's lesson: **wins rose while kills fell 4->1 and damage dealt fell
7.71->4.43.** Report kills and damage differential alongside win rate, always.

Do **not** also pass `--bt-rule-xml` with the peer rig -- `activate_rule_xml()` copies over our
live file and silently restores symmetry.

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

## Open follow-ups, in priority order (rewritten 2026-08-13)

1. **The DQ workstream, and it is now unambiguously first.** It has never been started, it is the
   only item here that loses the competition regardless of how well the aircraft flies (two network
   incidents = DQ), and it needs no compute. Two parts, neither reachable from this repo alone:
   **(a)** a live induced packet-loss / latency rehearsal against a practice or competition server
   -- `student/submission_resilience.py` and `scripts/verify_resilience.py` pass under in-process
   fault injection but **no real UDP server has ever been in the loop**; **(b)** confirm
   `SERVER_IP` with the organizers -- `my_submission.py` has `221.151.77.208`,
   `startup_command.txt` has `10.185.16.247`, and they disagree.
2. **Finish the re-baseline** (4.1 **F26-OWED**). Four geometries were re-measured post-F25;
   **A2, A3, A5, C6, the Gate 3 energy thresholds and the `Task_Notch` carve-out are still void
   and un-re-run** -- every one of them was a verdict on a branch that never executed. B1/B2
   uniquely survive, because `Gate0_ClimbToSafeAltitude` was one of the only two live nodes.
   Score any BT change through the peer rig, never symmetrically.
3. **Re-sweep the champion controller envelope.** 2500 m / 45° / throttle-off was tuned by sweep
   (F2-CHAMPION) against a tree flying a stale aim point, and it is **what ships**. There is no
   reason to assume it is still the optimum now that the BT manoeuvres underneath it. ~8 x N=30.
4. **The defensive role** (4.1 **F26-DEFENSIVE**). `obfm_defensive` is 1W/0D/**29L** with 16
   deaths once the opponent can shoot. `defensive_break` is a measured no-op and the Gate 1
   reorder was rejected on `match_base`; the untested idea is to gate the break on own-ATA > 90 so
   it fires only when the bandit is genuinely behind our 3-9 line. Note the scope: `match_base` is
   the confirmed prelim geometry and we are even there; OBFM presets are unconfirmed (§4 row 6).
5. **A v9 is optional and should be justified against items 1-3.** Eight campaigns have produced
   zero usable bundles. The BT opponent is now genuinely competent, so v1-v8 difficulty is not
   comparable. If launched: `python scripts\run_experiment.py experiments\real_eagle_v8.yaml`
   under a fresh tag, expect ~49 min/stage and ~22 h, and check rows with
   `metrics_age_iters == 0` appear about every 27 iterations with no stage advancing until ten
   exist. **Never point a v7 tag at this curriculum** -- the `match_base` ladder changed the
   meaning of every stage index after the first two-circle stage.

~~Ask the organizers whether each side gets its own rule XML.~~ **RESOLVED 2026-08-11/13.** It is
a local-harness property, not a competition one (F1-BLIND-RESOLVED), and `scripts/setup_peer_bt.py`
now makes per-side rules work locally -- proven across full N=30 runs, see the section above.

~~The ~4 G ceiling (F5).~~ **REFUTED 2026-08-13** (4.1 **F26-G-CEILING**). There was never a
control-law ceiling: it was an aircraft not manoeuvring. Post-fix, BT pitch saturation fell
84% -> 37.8% and G median rose 1.16 -> 2.06 with p95 21.45, against F5's "never exceeds 3.95".

## Guardrails (compliance -- keep it this way)
- `src/dogfight/**` is a hard no-edit boundary. Route new logic through `student/**`,
  `experiments/*.yaml`, or the entry scripts (`train_*.py` / `run_*.py`).
- Never rename/move/delete runtime assets (`AIP_BASE*.dll`, `JSBSimAIPLib.dll`, Rule XMLs,
  `aircraft/`, `engine/`, `scripts/*_cruise.xml`) -- content edits only.
- Preserve `src/dogfight/unreal/protocol.py`'s wire format. Keep `--action-repeat 6`
  (the 1/6 s compute-budget rule) matched to training `step_ratio=6`.
- **"It is in the tree" is not "it is wired in."** Five things have shipped inert:
  `DECO_BFMCheck`, `_recycle_native_bts()` for hybrid, the G limiter, `MatchScenarioWrapper`
  (F8) -- and, for the entire project until 2026-08-13, **the whole behaviour tree below
  Gate 2.5** (F25). Show a call site, or a trace.
- **Parse-check every rule XML edit.** `--` is illegal inside an XML comment and will make the
  tree fail to build; a 2026-08-13 edit hit exactly this and was caught only by an explicit
  `[xml]` parse before the eval ran. That is why existing comments in the file use `;` where an
  arrow or dash would read more naturally. A naive regex for `--` gives false positives on the
  `-->` terminator -- trust the parser.
