# AIP TGC 2026 — Competition Plan

> Companion to [COMPETITION_RULES.md](COMPETITION_RULES.md) (official rules),
> [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) (how the system works), and
> [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) (where things are + current state). This file is
> the living strategy/execution plan — check items off and update assumptions here as work
> progresses; don't let it drift stale the way `PROJECT_STRUCTURE.md` briefly did.

## 1. Status snapshot

As of 2026-07-07 (see `PROJECT_STRUCTURE.md` "Current state" for the verified detail): the `aip`
conda env exists, connectivity to a live Unreal server has already been smoke-tested
(`logs/unreal_packets/`, `logs/native_bt/`, `startup_command.txt`, all dated 2026-05-14 or after),
but **no real trained policy exists yet** — `artifacts/models/real_eagle/*` are placeholder/smoke-test
bundles (every `reward_mean` is `n/a`), and `student/my_reward.py` is still the bare template.
Infrastructure is ready; the competitive model itself is a from-scratch build.

Today is 2026-07-07. Per `COMPETITION_RULES.md` §3, prelims are end of August 2026 — **roughly
7–8 weeks of runway.**

**Update 2026-07-11:** the native BT is no longer the 8-node minimal tree of early July — the full
**BT tactics expansion (Batches A–D, §5.1.6) has landed**: ~20 `Task_*` maneuver nodes + a
5-gate priority structure + an energy-ratio service, all built and frozen into
`AIP_BASE.dll`/`AIP_BASE_target.dll`. Three environment/reward corrections also landed this week:
the initial-spawn geometry now matches the **confirmed real competition presets** (15000 ft /
200 m/s / ~10000 ft HABFM separation — §4 row 6), and a config-merge bug that had silently zeroed
the `position` reward term for all of real_eagle v1's stage 0–8 training was found and fixed (§6).

**Resume-vs-restart decision RESOLVED (2026-07-11): restart, not resume** — see §9 for full detail.
v1 (the original stage-8 run) actually recovered from its Ray/RLlib crash and finished stage 8
cleanly two days late, but was still abandoned in favor of a clean restart (`v2`) once the tree,
spawn geometry, and reward fixes above had all landed — training against the stage-8 checkpoint's
stale assumptions wasn't worth carrying forward. `v2` was deliberately stopped at stage 2 (manual
interrupt, not a crash); `v3` is the current run, **live as of this writing** — past stage 8 already,
into stage 9/17 (`two_circle_headon_a060`, 195 iterations in, 2330 total iterations elapsed across
the run). Re-check `artifacts/curriculum/real_eagle/v3/curriculum_state.json` before assuming this
snapshot is still current.

**Update 2026-07-12 — full-codebase audit; `v3` superseded by `v4`.** An audit of v3's live
metrics (then at stage 13/17) found the run structurally degenerate, and v1 retro-checked
identically:

- **Every two-circle stage in both v1 (stages 4–8) and v3 (stages 6–13) ran at 93–100%
  guard-fail losses, 0 wins, ~0 WEZ steps**, advancing only via `max_iterations`. The ATA-limit
  guard was physically unpassable at the merge, and (worse) its unavoidable discounted terminal
  penalty rewarded *postponing* the fail — i.e. it trained merge **avoidance**; v3's late stages
  measurably learned to stall (episode length 23→177 iterations-mean with zero win-rate change).
- **Crashes paid `draw_reward`** (ground impact leaves health at 1.0, so the terminal routing
  fell through to the draw branch). v3's `obfm_defensive` sets `draw_reward=+20` for
  survive-to-timeout — so the agent was paid +20 to fly into the ground, and duly learned a
  **100% crash rate** (stages 2–5 all ended 90–100% crash).
- **SAC learner metrics (`actor_loss`/`critic_loss`/`alpha`…) logged `n/a` for the entire
  history of v1–v3** — the extractor grabbed `__all_modules__` (counters only) instead of
  `default_policy` from `result["learners"]`. No optimizer-health signal was ever visible.
- Net: across ~7,400 iterations (v1+v3) the agent **never won a single episode** and the damage
  reward never fired meaningfully. Learning infrastructure itself works — policies responded to
  the (wrong) incentives exactly as the gradients dictate.

Fixes landed 2026-07-12 (all verified end-to-end through the real stage-config merge path):
crash→`crash_penalty`/`target_crash_reward` terminal routing (both reward impls + both config
dicts); guard redesigned to a **range-based disengagement check** (>8 km = loss — fleeing is
the one thing it now bans; see `envs/termination.py`); `student/my_curriculum.py` rebuilt
(5-alpha two-circle ladder with 8 km shaping reach + smooth `advantage` term at 0.1,
`full_dogfight` extended to 1500 iterations); `student/my_observation_v2.py` (15 features,
+target speed, live-parity safe — new module so live v3 workers can't import a changed obs
size); SAC metrics extraction fixed; all reward components now in the training CSV; periodic
engagement replays (Tacview) enabled in v4. **`v4` = `experiments/real_eagle_v4.yaml`**;
`scripts/launch_v4_when_free.ps1` (running, detached) auto-starts it as soon as v3's process
tree exits — stop v3 early with `taskkill /PID <run_experiment pid> /T /F` to start v4 sooner.
**Do not `--resume` v3 after this date** (stages module rewritten; state-file indices would
mis-map).

**Update 2026-07-14 — hybrid inference pipeline fixed after 0-win practice matches.** The BT+RL
hybrid lost every practice match vs pure RL and pure BT. Audit found the RL throttle was never
remapped from the policy's [-1,1] training convention to the sim/wire's [0,1] at inference
(engine-idle for half the output range, on every entry path — local validation couldn't catch
it), the hybrid residual could only ever *raise* throttle above the BT baseline, and
`--hybrid-mode switch` silently ran pure RL (no selector existed anywhere). All fixed
2026-07-14, plus a startup guard that refuses to run when a bundle's recorded observation
config mismatches the runtime's (`verify_bundle_observation`). **The fixes live in the
editable `student/inference_providers.py` (subclass + composition of the platform), NOT in
`src/dogfight/**`** — that package was reaffirmed as a hard no-edit boundary the same day, so
the first-pass fixes that had been placed there were reverted and re-homed (see
`PROJECT_STRUCTURE.md` current-state log / `PROJECT_ANALYSIS.md` §5.1). `RemappedRLProvider`
(the remap-before-clip subclass) and `StudentHybridProvider` (throttle-aware residual + real
switch) are wired in from the three inference entry scripts; `student/my_submission.py` now
targets §3's hybrid-residual architecture with the newest post-audit bundle (v4 stage_3) +
`student.my_observation_v2`. **Any pre-2026-07-14 practice-match result involving the RL or
hybrid backend is invalid as a strength signal** — the policy was flying with a corrupted
throttle channel. Re-run practice matches before drawing conclusions; and note v4 training is
stalled at stage 4/17 with no live process (the stage_3 bundle has only learned pursuit, not
combat — resuming v4 remains the highest-leverage action).

**Update 2026-07-15/16 — accidental full-tree revert, then recovered (mostly).** The fix for a
`src/dogfight` boundary violation (a session had edited it directly) was executed as a full
pristine-template overwrite instead of a scoped revert, silently undoing roughly a week of
validated work that happened to share a file path with the original distribution template:
the 2026-07-12 crash-routing fix and range-based guard (§1 above), the 2026-07-08/11 WEZ-phase
widening (§4 row 2), `student/my_reward.py`/`my_curriculum.py` (back to bare templates), and the
entire BT tactics expansion's XML wiring (`Rule_forTraining.xml` back to a 2-branch stub, even
though every `Task_*.cpp` source survived) plus `AIP_BASE.dll`/`AIP_BASE_target.dll` (reverted to
a stale pre-expansion binary). Trained checkpoints, `experiments/real_eagle_v*.yaml`, and the
`Task_*.cpp` sources themselves were untouched (unique paths, no template counterpart to overwrite
them). Five root docs (this one included) moved to `DogFightEnv/References and Manuals/` in the
process — kept there permanently rather than restored to root (§1 continues to live at that new
location going forward).

Recovered 2026-07-15/16: `student/my_reward.py`/`my_curriculum.py`/`reward_lib.py` via
decompiling a stale Python bytecode cache that survived the revert (byte-exact for most content,
reconstructed from `real_eagle_v4.yaml`'s own description for the crash-fix and 5-alpha ladder
specifically, which postdate that cache); `Rule_forTraining.xml` via the surviving design plan
(`~/.claude/plans/...serene-duckling.md`, outside the project dir), rebuilt, and **deployed to
`AIP_BASE.dll`/`AIP_BASE_target.dll`** after fixing two unrelated pre-existing `AIP_DCS` build
breaks found along the way and verifying via two live BT-vs-BT runs.

**Deliberately NOT recovered — the WEZ-phase damage model (§4 row 2) and the range-based guard
(§1's 2026-07-12 fix).** Both are hardcoded platform methods with no plug-in hook, unlike
`reward_module`/`observation_module`/`stages_module`; restoring them means either crossing the
`src/dogfight` hard boundary or adding a hook to the shared trainer scripts, and the team declined
both options when asked directly. **As of 2026-07-16, local training/eval runs against the flat
pre-fix WEZ damage model and a disabled (not re-enabled-and-broken) two-circle guard.** This is a
training-fidelity gap, not a competition-legality one. Full detail:
`PROJECT_STRUCTURE.md`'s dated "Current state" entry, `COMPETITION_RULES.md` §6.3, and memory
(`project_bulk_revert_regression_2026_07_15`, `project_v4_recovery_2026_07_15`,
`project_bt_xml_reconstruction_2026_07_15`).

**Update 2026-08-06 — v6 failed; the controller bypass (D1) scored instead. First wins.**

`v6` completed at 15:07 and was evaluated at 16:40: **18/20 crash, 2/20 timeout, 0 wins, 0 WEZ
steps, 0 damage** (`artifacts/eval/v6_rl_vs_bt.csv`). The dense altitude-floor term did not fix
v5's self-crash. That is six curriculum campaigns with zero wins, and it closes the pure-RL line
of attack for this cycle.

The same day, two things were established that change the plan:

- **The hybrid floor is sound.** BT+RL vs BT, re-run at N=30 with the current post-`MFsum` DLL
  and the v6 bundle (`artifacts/eval/hybrid_v6_postmfsum.csv`): **30/30 timeout, 0 crashes**,
  both aircraft at health 1.0. §3's architecture does what it was designed to do — RL cannot
  drag the aircraft into the ground. It scores nothing (0 WEZ), but 6/30 episodes do reach
  ≤1.0°, just never in-band. This also discharges the owed **D3-c** hybrid end-to-end smoke
  test, which had been blocked by v6 occupying the box.
- **`Controller_CY` was the binding constraint, and replacing it works** (§4.1 **D1-DONE**).
  A student-space VP→stick law took the BT floor from **0/30 wins and 0/30 WEZ-contact episodes
  to 12/30 and 30/30** on identical seeds. These are the project's first wins.
  **But scope it honestly (§4.1 D1-LIMIT):** that 40% is **OBFM_offensive**, a geometry that
  starts the ownship advantaged. On the neutral `two_circle_headon` merge the same backend
  scores **1/30**. The bypass *converts* an offensive position into a kill; it does not *create*
  one, because it only takes the stick inside a ≤1200 m / ≤20° terminal envelope and the native
  BT still loses the neutral merge that would put it there. **Winning the merge is now the
  single remaining gap between here and a competitive submission** — and it is exactly the phase
  §3's RL residual acts on.

Also fixed today, all found while validating the above: **v5 and v6 both trained blind** — the
per-episode metrics were logged 0 times in 9,400 iterations, and every stage in both campaigns
advanced on `max_iterations` rather than its own gate (§4.1 **E2**, now fixed and verified —
stage 0 advanced on `crash_rate=0.0000`, the first live advance condition since v4); unattended
runs were dying at stage advancement on a `UnicodeEncodeError` from an ordinary progress print
(**E3**); and eval CSVs had been logging `initial_distance_m = 0.0` for every v6 row (**E4**).

**Submission direction is unchanged and now better supported:** hybrid residual (§3), with the
residual re-based on the fixed floor (`hybrid_vptrack`). Pure BT stays warm as the fallback, and
that fallback is now materially stronger than it was this morning.

**Update 2026-08-11 — the merge root cause found and patched, the controller benchmarked against a
peer, a G limiter landed, and v7 launched.** Fourteen commits between 09:32 and 13:44 that this
register had not recorded until now; full detail in §4.1 **F**. The headline items:

- **The merge failure has a mechanical root cause, and it is a coverage hole, not a tuning
  problem.** At the official antiparallel beam merge (610 m, HCA 180°, own-ATA ~91°) *no* Gate 0–2.5
  branch matches, so the tree falls through to a lowest-priority default that commands a max-rate
  turn **away** from the target. Both aircraft mirror it to within 0.3°, range grows 610 m → 3278 m
  in 11 s, and the match becomes the 2841 m orbit C6 measured. **That single fact explains every
  positional null in this register.** `Gate2_BeamMerge` now covers it (F1).
- **Every win rate in this document is measured against an opponent that cannot shoot.** The
  per-side controller CLI (F2) finally makes an asymmetric measurement possible, and against a peer
  running the *previous* tuning the current champion scores **80.0 %, zero losses** — while against
  an identical peer it is **7W/16D/7L**. Treat the 73.3 % as the upper bound D1-SELFPLAY already
  said it was.
- **A 10 G limiter now covers every path** including RL training (F4). The sim enforces no
  structural limit and hands out up to 14.86 G against a 9 G airframe.
- **`v7` is live** (launched 13:46:24). It is the first campaign with working telemetry — and the
  first whose telemetry has already exposed a defect in the telemetry itself (F6).

**v7 WAS STOPPED at 14:33 on 2026-08-11, at stage 2 / 313 iterations, and its stage results are
void.** F6: the E2 carry-forward persisted metrics across stage boundaries and the advancement
gate averaged over *rows* rather than episodes, so stage 0 advanced reading `crash_rate=0.2000`
when its true rate was **0.8571**, and stage 1 advanced having closed **zero episodes of its own**.
Fixed the same day (`7b404be`), together with the `reward_mean` carry gap (`d1050db`), the
training-record `KeyError` that had silently suppressed every stage record (`516b6ac`), and the
`MatchScenarioWrapper` training-path gap (`37ec78b`, F8). **Relaunch as v8** — do not resume v7.

**Update 2026-08-13 — the tactical layer was dead code; it is now fixed, and everything BT-related
in this document was re-baselined.** Full detail in §4.1 **F26**. The headlines:

- **F25 is applied** (commit `5412a79`). `name=` dropped from the 17 control nodes, and **17
  maneuver nodes across all five gate blocks now execute where exactly 2 ever had.** Verified by
  instrumentation, not by outcomes.
- **It is worth a shutout.** Isolated through the peer rig, varying only the opponent's tree:
  an opponent **with** the fix fights us even (9W/14D/7L); one **without** it loses **16W/14D/0L**
  and lands **0.06 damage across 30 episodes**.
- **The neutral merge finally moved** — `two_circle_headon` 1/30 → **8/30**, median min-ATA
  9.414° → **0.014°**. THE PATTERN's "positional BFM decides placement" gap was, at root, a tree
  that never ran.
- **Every BT number written above this line is VOID**, including rows marked "fixed". F5's and
  F12's G-ceiling findings are **refuted** (there was no control-law ceiling — it was an aircraft
  not manoeuvring). A2/A3/A5/C6/Gate-3/Notch verdicts are still un-re-run (F26-OWED).
- **New standing rule:** never adopt or reject a BT change on a symmetric measurement — both DLLs
  read one global rule XML. Use the peer rig. A Gate 1 reorder that looked like a large win
  symmetrically was **rejected and reverted** when scored properly (F26-GATE1-REJECTED).
- **v8 retired**, not resumed (killed by an unplanned reboot; no stage had advanced on a real
  gate). There is still **no usable RL policy after eight campaigns**.
- **The defensive role is a real capability hole** — `obfm_defensive` 0W/30D/0L → 1W/0D/**29L**
  once the opponent could actually shoot. Scoped: `match_base` is the confirmed prelim geometry
  and we are even there; OBFM presets remain unconfirmed.

**The remaining runway should go to §8 robustness, not new capability.** The DQ/network workstream
has never been started and can lose the competition independently of how well the aircraft flies.

## 2. Team profile & vision (confirmed 2026-07-07)

| Question | Answer | Implication |
|---|---|---|
| Approach | **Hybrid (residual)** | RL learns a correction on top of the native BT DLL — see §5.1 for a newly-found caveat on how solid that BT floor actually is |
| Time budget | **Near full-time** | Room to be thorough (more curriculum iteration, more validation rounds) — but full-time hours don't remove the compute bottleneck below |
| Target outcome | **Contend for the podium** | Robustness/polish work (network stability, edge cases, the tie-break scenario) isn't optional extra credit — it's load-bearing for a podium result |
| RL/ML background | **Some ML, limited compute** | Default to SAC **MLP only** — skip the `RLLibLstm/` patch path unless MLP hits a measured ceiling; favor sequential, compute-light iteration over parallelism (§7) |

**Net read**: this is a time-rich, compute-poor, high-ambition project. The highest-leverage moves
are the ones that turn team-hours into quality without burning GPU/CPU cycles — reward/curriculum
design, thorough validation, and (if §5.1's check comes back badly) restoring real tactical logic
to the native BT, which is comparatively compute-cheap since BT rollouts need no gradient steps.

## 3. Target architecture: Hybrid (residual) as the submission, BT-only kept warm as insurance

Train an RL policy whose output is a **correction on top of the native BT DLL**
(`HybridActionProvider(mode="residual", ...)`), not a replacement for it:

- The BT baseline (`AIP_BASE.dll`) is assumed to fly without violating hard-deck/safety on its
  own — **this assumption now needs verifying, see §5.1** — so residual RL only has to learn the
  *delta* that beats it, a much smaller learning problem than end-to-end control from scratch.
- It can't regress below "BT alone" quality if training under-converges, *provided the BT floor
  is real* (§5.1).
- This is explicitly the documented intent of `HybridActionProvider`'s residual mode (the BT is
  the safety net, RL only nudges it) — not a new idea being introduced here.
- Keep pure `MODE="bt"` (tuning `Rule_forTraining.xml` → a team-specific `Rule_real_eagle.xml`)
  **actively maintained in parallel the whole time** — but see §5.1: this is currently a much
  bigger lift than "tune some XML thresholds."

- [x] Approach confirmed: Hybrid residual (§2).
- [ ] Revisit if §5.1's verification shows there's no usable BT floor to be residual *on top of*.

## 4. Environment-vs-rules corrections needed

The training environment's defaults don't match the live competition in a few specific,
checkable ways (see `COMPETITION_RULES.md` §6.3 for the cross-check). None of these are
guesswork — each is a concrete diff between `DEFAULT_ENV_CONFIG` and the rules doc.

| # | Rule (source) | Current env default | Correction | Status |
|---|---|---|---|---|
| 1 | 200s matches (§5) | `max_engage_time=300.0`, `episode_step_limit=18000` | Override to 200s / 12000 steps (60Hz) so learned pacing/energy management matches the real clock | - [x] Done 2026-07-08: `full_dogfight` stage's `episode_step_limit` in `src/dogfight/ai/curriculum.py` is now `12000`. Not a YAML/env_config knob for the curriculum path — `run_experiment.py` never forwards `env.max_engage_time`/`episode_step_limit` for `script: train_curriculum` (checked directly), episode length is purely per-`CurriculumStage`. |
| 2 | Three-phase widening WEZ cone, best-phase-wins (§6.2) | Single static Phase-1-only cone (`angle_deg=2.0`, ~152–914 ft) — confirmed by grep, no phase logic anywhere in `src/dogfight/` | Phase 1 is a strict subset so this isn't wrong, but add phase-aware WEZ/reward logic so late-match behavior (t>100s, t>150s) isn't miscalibrated toward disengaging from shots that would actually still count | - [x] Done 2026-07-08, **[ ] REVERTED 2026-07-15, left un-restored (deliberate decision 2026-07-16)**: `DEFAULT_ENV_CONFIG["wez"]["phases"]` (`src/dogfight/config.py`) + phase-matching logic in `single_agent_env.py::update_damage()`/`_match_wez_phase()` were implemented and verified (8-case scripted test incl. the best-phase-wins rule), but an accidental full-tree revert reverted both files back to the flat Phase-1-only state described in the "Current env default" column, and the team chose not to restore it — no plug-in hook exists to reach `update_damage()` without crossing the `src/dogfight` hard boundary. **Current state matches this row's original "Current env default" cell again.** The pursuit-*shaping* term is still phase-aware (`student/reward_lib.py`, survived/re-homed), just not the actual damage/health computation. See `COMPETITION_RULES.md` §6.3. |
| 3 | 6-frame (1/6 s ≈ 166.7 ms) compute-time penalty (§4) | `step_ratio=6` / `--action-repeat 6` already encodes this convention | Measure the trained policy's **actual** inference latency on competition-grade hardware — don't just trust the abstraction | - [ ] Instrumentation landed 2026-07-10 (`time.perf_counter()` p50/p95/max around `ProviderCommandPolicy._compute_provider_action()` in `unreal/policies.py`); still needs a trained policy + competition-grade hardware to produce real numbers (Weeks 4-5). |
| 4 | Head-on tie-break at 10,000+ ft (§7) | Curriculum stages 4–13 (`two_circle_headon_a000..a180`) already target this geometry | Don't let this curriculum block get shortchanged for iteration speed — it's rehearsal for a named, specified tie-break format, not generic diversity | - [ ] BT-side handler now exists: `Task_NoseToNoseTurn` + Gate-2 head-on merge decorators (§5.1.6, Batch C) fire on the 3000–10000 m near-head-on geometry. Still owed a dedicated eval scenario (§8) and the curriculum block must still train against the upgraded tree. |
| 5 | Network-instability = DQ after 2 incidents (§8) | Untested under induced stress | Dedicated robustness workstream (§8 below), independent of model quality | - [ ] |
| 6 | **Initial spawn geometry** — main match (Prelim + Finals rounds 1–3) starts at **2000–3000 ft**, altitude/speed 15000 ft / 200 m/s (viewer presets); **10000 ft+ head-on is the round-4 tie-break ONLY** (confirmed 2026-07-11 from the official kickoff-deck scenario slides; exact distance/alt/speed "released later" per the deck) | `DEFAULT_ENV_CONFIG` used an unverified 7000 m / 250–300 m/s / ~5000 m baseline | Realign `config.py`'s `ownship`/`target` static arrays + `initial_scenario` + `target_autopilot` to the main-match geometry | - [x] Done 2026-07-10, **corrected 2026-07-11**: static spawn now 4572 m / 200 m/s / **762 m (2500 ft) separation** — an interim 3048 m/10000 ft value (from mis-reading the HABFM screenshot as the main-match spawn) was fixed once the official slides clarified HABFM = the round-4 tie-break preset, not rounds 1–3. `two_circle_headon` altitude 4572 m, speed `[175,225]`; its `alpha_deg`/`turn_diameter_ft`/`separation_jitter_ft` progression mechanics left untouched. **OBFM_RED/OBFM_BLUE exact geometry still unconfirmed** (presumably 2000–3000 ft with one side advantaged); capture from the viewer if needed. |

## 4.1 Official-slide audit — consolidated issue register (2026-08-05)

Built from the official kickoff-deck slides (engagement/damage rules, the AIP Behavior Tree
tutorial, and the "Advanced 모델 예시" architecture slide) cross-checked against the code, plus a
measurement session on a fresh Debug|x64 build. **The architecture + BT-tutorial slides are
transcribed in [AIP_OFFICIAL_ARCHITECTURE_AND_BT_SLIDES.md](AIP_OFFICIAL_ARCHITECTURE_AND_BT_SLIDES.md)**
(the C and D rows below cite it); the damage-rule slides are in `COMPETITION_RULES.md` §6. Evidence tags: **[M]** measured this session,
**[D]** already documented elsewhere, **[N]** new from the slides.

### A. Engagement / damage rules

| # | Issue | Evidence |
|---|---|---|
| A1 | **Local env implements Phase 1 only** — flat `angle_deg=2.0` (→ ≤1.0°, 500–3000 ft); no phase logic in `update_damage()`. Phase 2 (2°/3500 ft/0.3, opens 100 s) and Phase 3 (3°/4000 ft/0.1, opens 150 s) absent. | [D] + **[M] fixing it changes nothing** — re-scoring every trace under the full 3-phase rule still yields exactly 0 damage. Deprioritized; not worth the `src/dogfight` boundary fight. |
| A2 | **Damage gradient unexploited — FIXED 2026-08-05 (unvalidated).** `D = (3000−r)/2500` → coefficient **1.0 at 500 ft, 0.0 at 3000 ft**. `Task_GunTrack` had **no range term at all** (pure speed-matcher), so it held whatever range it arrived at. Measured over 2 traces: in-band median range **1825 / 1915 ft → coef 0.47 / 0.43**, closest approach across ~450 in-band steps only **1739 ft** — i.e. **2.1–2.3× of available damage discarded**, never trending toward the high-value edge. Added a bounded range bias toward **220 m (~722 ft, coef ≈0.91)**, floored at 152.4 m so it can only push *away* from the zero-damage zone. Competes with (does not replace) the speed-match term that prevents overshoot. **UNVALIDATED** — harness is bimodal and this node ticks ~100 steps/episode in OBFM, 0 in two-circle. **Exact revert: `GUNTRACK_RANGE_GAIN = 0.0f`** (verified bit-identical to the old behaviour). | [N] → **[M] fixed** |
| A3 | **Gate 2.5's gun gate is 8× looser than Phase 1** (ATA < 8° vs LOS < 1°). | [M] mis-specified but *not currently binding* — tightening to 2° doesn't help, the BT never reaches 2° in-band anyway. |
| A4 | **Range and angle are never simultaneously satisfied**, under *any* phase incl. the most permissive 3°/4000 ft. 400–560 in-band steps per window; best in-band ATA 4.48° / 15° / 37° / 42°. Best alignments (0–3.5°) occur at 4,800–10,700 ft. | **[M] — the core unsolved problem** |
| A5 | **FIXED 2026-08-05.** `r < 500 ft` is a zero-damage dead zone, but Gate 2.5's floor was `Dist > 150` m = 492 ft — an 8 ft sliver where the BT believed it was in the band and damage was 0. Now `Gun_DistGt152p4` / `Distance="152.4"`. XML-only, no rebuild. **NOTE: this edited the LIVE `Rule_forTraining.xml`** (permitted — CLAUDE.md's boundary table allows content edits — but the running v6 job reads that file, so it will pick the change up at its next BT creation). | [N] → **fixed** |

### B. Match rules

| # | Issue | Evidence |
|---|---|---|
| B1 | ~~**Gate 0 surrenders ~2,000 ft of legal fighting room.**~~ **WITHDRAWN 2026-08-05 — measurement refuted it.** Across all 24 eval traces, ownship altitude **never once drops below 914 m** (minimum 2182 m; spawn is 4572 m). The trigger is dormant in the real operating envelope, so lowering it would reclaim nothing and only cut dive-recovery margin. The original entry was an armchair reading of the constant against the rulebook, not a measurement. **No change made.** | [N] → **refuted [M]** |
| B2 | **Overstated — corrected 2026-08-05.** The claim "preempts any diving engagement below ~10,000 ft" was wrong: the trigger requires **both** `alt ≤ 3000 m` **AND** `AltSpeed ≤ −150 m/s` (a genuinely steep dive). Measured conjunction: **3.61%** of steps (4262/118024). Non-trivial — Gate 0 is top priority, so for ~3.6% of a match all tactics are abandoned to climb — but not the emergency described. **No change made**: altering an unvalidatable safety trigger to fix an unconfirmed cost repeats the failure pattern of 2026-08-05's reverted attempts. Worth its own investigation. | [N] → **corrected [M]** |
| B3 | 200 s episode length — already corrected to 12000 steps across all stages. | resolved 2026-08-01 |

### C. Behavior Tree architecture

| # | Issue | Evidence |
|---|---|---|
| C1 | **The official reference tree gates pure pursuit on LOS ≤ 1° — the scoring criterion itself.** Ours gates on ATA < 8° (Gate 2.5), and the tail `Task_Pure` has *no angle gate at all* (`dist < 2000 m` only). The reference aims at what scores; ours aims at a proxy and hopes to converge inside it. | [N], consistent with A4 |
| C2 | **Complexity has not bought performance.** Reference tree = 4 leaves. Ours = ~25 nodes / 6 gates / 23 Task classes → 0 WEZ steps in every configuration tested. | [M] — argues against adding tactical layers (i.e. against the fight-state-memory Tier 2) |
| C3 | **"Task Node = VP 생성" is an architectural ceiling.** Tasks emit only an aim point; `Controller_CY` owns VP→stick. No BT-side change can fix terminal pointing except by displacing VP — the lead-feedforward experiment, already tried and reverted. | [N] — bounds what further BT work can achieve |
| C4 | `DECO_*`/Service inheriting `SyncActionNode` is **correct, not a defect** — the C++ BT collapses Task + Service into a single Action Node ("서비스 노드와 같은 역할 구분이 사라짐"). | [N] — corrects an earlier "semantic mismatch" reading |
| C5 | BlackBoard is the sanctioned home for memory ("기억"), but only `NeutralEngagementStartTime` is genuine cross-tick fight state. | [D] |

### D. System architecture

| # | Issue | Evidence |
|---|---|---|
| D1 | **The project is locked into keeping `Controller_CY` in the loop — and the rules do not require it.** Architecture #1 on the Advanced slide (BT tactics → RL flight control → JSBSIM) has **no controller box**, and the deck states plainly: "무슨 수를 써서라도 접속기에 붙이기만 하면 됩니다." Since the controller is the measured bottleneck, this is the single biggest unexploited option. | **[N] — highest strategic value** |
| D1-**DONE** | **BYPASSED 2026-08-06 — first WEZ contact and first wins in the project's history.** `student/controller_providers.py::VPTrackingProvider` keeps the native BT for tactics, throttle and blackboard state but computes roll/pitch/rudder itself inside a terminal envelope (≤1200 m, ≤20°). **N=30 OBFM, same harness/seeds/opponent as the BT baseline:** wins **0/30 → 12/30 (40.0% ± 8.9%)**; WEZ-contact episodes **0/30 → 30/30**; episodes reaching ≤1.0° **0/30 → 30/30**; damage dealt/taken **0.0/0.0 → 15.594/0.000**; ownship crashes **0**, health 1.0 in every episode; best ATA **4.08–4.45° → 0.0046–0.362°**. **Mechanism (why E1e's five sweeps were all null):** both control authorities vanish together near `UTAngle`=180°, exactly where the stuck mode sits (measured 152–172°) — `Roll_Effect = 1 − clamp(\|UTAngle\|/90,0,1)` is *identically 0* for \|UTAngle\|≥90 and `PitchCMD` is a **product**, so pitch is multiplicatively annihilated; and in that same branch `RollCMD = sin(UTAngle)` **decays to 0 as UTAngle→180**. No gain multiplies a zero into something. The replacement commands roll proportional to the angle itself (maximal at 180°, where the old law gave ~0) and pitch with no multiplicative kill. Traced mean pitch-plane fraction **0.0 → 0.638**. Wired as `vptrack`/`hybrid_vptrack` in both eval scripts, `run_local_dogfight.py` and `run_unreal_inference.py`; live-parity safe (`ownship_state`/`target_state` are populated identically by `unreal/policies.py`). | **[M] fixed** |
| D1-**LIMIT** | **The bypass converts offensive position into kills; it does NOT create offensive position — measured the same day, do not over-read D1-DONE.** The 40% win rate is **OBFM_offensive only**, a geometry that *starts* the ownship advantaged. Re-run at N=30 on **`two_circle_headon`** — the neutral head-on merge, and the geometry closest to the round-4 tie-break — it scores **1/30 wins (3.3% ± 3.3), 1/30 WEZ-contact episodes, median min-ATA 9.41°**. Still strictly better than every alternative in that geometry (`hybrid` 0/30 WEZ; v6 pure RL 0/30 and 18/20 self-crash) and still **0 crashes / 0 damage taken**, but it is not a 40% backend in a neutral fight. **Mechanism:** `VPTrackingProvider` only overrides inside the ≤1200 m / ≤20° terminal envelope; outside it the native BT flies, and the BT does not win a neutral merge — so from two-circle the fight rarely *enters* the envelope. This is the clean division of labour the remaining work should exploit: **something has to win the merge (tactics), and vptrack finishes it (terminal pointing)**. It is the strongest argument yet for §3's residual hybrid, whose RL correction acts precisely during the maneuvering phase the BT loses. | **[M]** |
| D2 | Pure RL (#3/#5) already failed once — v5 was 100 % self-crash, 20/20 into the ground. Must learn tactics *and* control simultaneously. | [D]; v6 retrying with altitude shaping |
| D3 | **Residual hybrid (#4-like) — wiring CHECKED 2026-08-05, comes back clean.** All five entry points (`run_local_dogfight.py`, `run_unreal_inference.py`, `my_submission.py`, both eval scripts via `build_provider`) use `RemappedRLProvider`/`StudentHybridProvider`, never the stock classes. Both construction sites pass `primary=RL, secondary=BT`, so residual = `BT + 0.35×RL` — BT baseline, RL correction, the intended direction. Throttle residual is correctly re-centred (`+= scale*(2*rl−1)`), and `switch_by_range` uses `StateIndex.N/E/D` = NED **metres** (no LLA unit trap) and fails safe to BT. | **[M]** verified |
| D3-a | **Bug found and fixed in the same pass — in E1a's own recycler.** `_recycle_native_bts()` looked for `ai_pilot`/`_registered_fighter_ids` *directly* on the provider; `StudentHybridProvider` has neither (its **secondary** is the BT), so every `--*-backend hybrid` run was **silently skipped**, reinstating the exact cross-episode leak the function exists to remove — with no output saying so. Fixed with a recursive `_iter_bt_providers()` walk over `primary_provider`/`secondary_provider` (cycle-guarded, None-safe; verified finding the BT directly, 1 level deep, and 2 levels deep), plus an up-front topology line so a no-op recycler is now visible instead of silent. | **[M]** |
| D3-b | **Residual authority is one-sided wherever the BT saturates.** `BTActionProvider` clips before the hybrid sees it, and `Controller_CY` can emit rudder up to **±3** pre-clip (`-sin(UTAngle)*clamp(LOS,0,6)`, then `(MFsum/20+RudderCMD)/2`) and pitch up to **1.5**. With BT pinned at ±1, `BT + 0.35×RL` clips away any RL push in the *same* direction — RL can pull back but not push further. Not a defect, but effective residual authority is asymmetric and axis-dependent; account for it when reading a hybrid A/B, and consider logging per-axis clip-saturation fraction. | **[M]** |
| D3-c | **Hybrid end-to-end smoke test still OWED.** Blocked 2026-08-05 by resource contention, not by code: Ray refuses to start alongside the live v6 training run (`object store memory 77.8 MB < minimum 78.6 MB`). Structural verification passed (subclass/recursion asserts) and the BT-only path regressed clean (rate 3/8, attractor 1.0388 sd 0.0027 — matches the 1.0380–1.0388 baseline), but a real hybrid episode has not run. Do this before trusting any hybrid result. | **[M]** |
| D4 | **Throttle is a separate sanctioned RL target (#4) and is unexploited** — every Task node hardcodes throttle constants (0.65 / 0.45 / 0.3 / 1.0 …) with no learning. | [N] |

### E. Cross-cutting — blocks validating everything above

| # | Issue | Evidence |
|---|---|---|
| E1 | **The eval harness is nondeterministic — and the cause is a BIFURCATION, not noise.** Bisected 2026-08-05 with 9 runs of `--episodes 1 --seed 0` on an md5-identical DLL. Results are **strictly bimodal**: ATA-min **1.034–1.041°** (4/9, 12 steps ≤2°) or **4.398–4.406°** (5/9, 0 steps ≤2°), nothing between. Spread *within* a mode ≈0.007°; *between* modes 3.37°. Meanwhile spawn ATA varies by only **0.017°** (σ=0.005°). So a 0.017° input perturbation deterministically decides whether the tracking pass converges. Every control-gain A/B in this project's history — including both of 2026-08-05's reverted attempts — was sampling a coin flip at p≈0.44. | **[M]** |
| E1-cause | Source is **inside `JSBSimAIPLib.dll`'s reset** (the Python reset path is clean — `super().reset(seed=seed)` seeds `np_random` and grep finds no global `np.random`/`random`/`time` use anywhere in the reset chain). That DLL is a protected binary with no source, so **perfect determinism is unachievable; do not chase it.** The correct response is statistical: use success-RATE over N≥30 episodes, never single-episode point comparisons. | **[M]** |
| E1-leaks | **Cross-episode state leaks are real but are NOT the nondeterminism cause** (a single fresh episode is already bimodal). They matter for a different reason: they destroy **sample independence**, which is exactly what the statistical approach above needs. `BtActionProvider.reset()` is a deliberate no-op and the BT is created once per provider, so across episodes these all carry: `RunningTime` (never reset — makes `Task_EnergyTactics`'s `lateMatch = RunningTime > 180` permanently TRUE from episode 2 onward), `PreviousAltitudeForRate` (bogus ±6000 m/s `AltSpeed` on the first tick of each new episode, feeding Gate 0's runaway-descent trigger), `ErrorSum`/`SumCount`/`MF[]`/`FilterIndex`, and `ActiveManeuverID`/`NeutralEngagementStartTime`/`ManeuverCooldownUntil[]`. | **[M]** |
| E1-gap | **The BT is 0.038° from scoring, not 4°.** In the converging mode it reaches a tight attractor of **1.038° (sd 0.0024)** against a **≤1.000°** WEZ criterion — a **3.7%** shortfall, in ~35% of episodes (N=20). This supersedes the earlier reading that the BT "cannot track"; A4's disjointness is real for the *failing* mode, but the converging mode is a near-miss. | **[M]** |
| E1a-done | **Harness fixed for sample independence** (2026-08-05). `scripts/eval_v5_vs_bt.py` gained `_recycle_native_bts()` — `RemoveBT` + clearing `_registered_fighter_ids` between episodes, forcing a fresh blackboard *and* `StickController`. Done from the eval script because `bt_action_provider.py` is inside the `src/dogfight` no-edit boundary. Validated: a 20-episode single-process run reproduces the 9-separate-process distribution within sampling error (35% vs 44%, se≈0.11–0.17). Also added per-episode `ep_min_ata_deg` / `ep_steps_le2_deg` to the CSV — the eval previously logged only *final* ATA, which cannot classify which mode an episode landed in. | **[M]** |
| E1c-null | **BOTH pitch-error knobs are ruled out for the 0.038° gap.** (1) `INTEGRAL_CAP` cannot matter: at the attractor the integral term is `1.038/7.5 = 0.138`, **well under the 0.25 cap**, so it is unclamped — the cap only binds above ~1.9° error. This retro-explains why the 0.25→0.6 attempt and the earlier cap sweep both read as "no effect". (2) `INTEGRAL_DIV` swept 7.5/6.0/5.0/4.5, N=16/arm: attractor 1.0388 / 1.0389 / 1.0377 / 1.0381 — a 67% gain increase moved steady-state ATA by **less than one sd**. | **[M]** |
| E1d-**WIN** | **The `MFsum` integer-truncation fix closed 82% of the pointing gap (2026-08-06).** `GetStick`'s rudder moving-average used an `int` accumulator over `float MF[20]`: `MFsum += MF[i]` truncates on **every** iteration, so for any \|value\| < 1.0 it never left zero (verified: 0.15/0.30/0.52/0.90 → exactly 0), and `MFsum / 20` was integer division on top. At the 1.038° attractor `RudderCMD = -sin(UTAngle)·clamp(LOS,0,6)` is bounded by 1.038, so every sample sat in the dead band — **the line reduced to exactly `RudderCMD = RudderCMD/2`**, the filter contributed nothing, and rudder authority was ~**8.7% of nominal** (0.173 taper × 0.5 halving). Fixed to `float` + float divide. **Measured, N=20/arm:** attractor **1.0380 → 1.0070** (gap +0.0380 → **+0.0070**), converging rate **35% → 40%** (no destabilization), dwell ≤2° 84 → 96 steps. sd ≈0.0025 over 7–8 samples ⇒ SE ≈0.001, so a 0.031 shift is ~30 SE. **This is the first change all session to move the attractor at all** — both pitch knobs moved it < 1 sd. **The residual error is on the LATERAL axis, not pitch.** Still 0 steps ≤1.0° ⇒ still no WEZ; remaining target is 0.007°. | **[M] fixed** |
| E1e-null | **Lateral follow-ups S1–S4 all failed to improve on E1d — the controller is at a local optimum in its scalar gains.** N=20/arm, same harness. **S1** `RollCMD < 0.1` → `abs(...)`: attractor **1.0070 → 1.2116**, ~30 sd WORSE. The sign asymmetry is *load-bearing* — it acts as a 3× boost on all large negative roll commands, so "fixing" it strips real authority. Reverted, and marked DO-NOT-FIX in code. **S2** roll-taper floor {0, 0.25, 0.50}: 1.0052 / 1.0062 / 1.0056 — all within one sd, because `clamp(LOS, FLOOR, 1.0)` with LOS ≈ 1.006 > CEIL returns CEIL for any floor; the taper is simply **inactive** at the operating point (same error class as `INTEGRAL_CAP`). **S3** rudder taper ceiling {6.0, 3.0, 1.5} = {16.8%, 33.5%, 67%} authority: 1.0064 / 1.0540 / 1.1107 — **monotonically worse with more authority**. Combined with E1d (which *doubled* authority and helped), this locates an optimum that the MFsum fix already reached. **S4** moved the `_isnan(LOS)` guard above the roll branch — latent NaN path (LOS was consumed by `if (LOS > 3)` ~45 lines before its guard; `clamp()` propagates NaN unchanged, so only Python's `nan_to_num` was catching it). Behaviour-neutral: 1.0062. **Net: five scalar knobs swept, only the MFsum *correctness bug* moved the attractor favourably. Further gain tuning on `Controller_CY` is unlikely to close the last 0.006° — this strengthens the architectural options (D1 / residual hybrid) over more hand-tuning.** | **[M]** |
| E1c-next | **Next hypothesis (partially CONFIRMED by E1d above — the lateral axis was indeed the problem):** `PitchCMD = ERROR_Effect × Roll_Effect × Horizon_Effect` is a **product**, with `Roll_Effect = 1 − clamp(|UTAngle|/90, 0, 1)`. If the residual error at the attractor lies mostly out of the pitch plane, `Roll_Effect ≈ 0` and no pitch-error gain can move `PitchCMD` — which is exactly the flat response measured. That would relocate the problem to the **roll/yaw path** (`RollCMD`'s `clamp(LOS,0,1)` scaling, its `LOS>3` / `RollCMD<0.1` branches, and the **inert rudder moving-average filter** — `int MFsum` summing `float MF[20]`, then integer `MFsum/20` → 0 for any \|sum\|<20, so that line merely halves rudder authority). **Confirming this requires per-tick C++ logging of `UTAngle`/`RollCMD`/`Roll_Effect`; the Python trace cannot see them.** Do that before spending more effort on the pitch expression. | **[M]** hypothesis |

| E1d-**CORRECTION** | **The "0.038° / 0.007° from scoring" framing was too optimistic — corrected 2026-08-06.** E1d's attractor figure and `s4_final.csv`'s `ep_min_distance` of 551–558 m are two **separate per-episode aggregates**; nothing says they occur on the same step, and an earlier reading here treated them as simultaneous. Traced directly (`artifacts/eval/scratch_20260806/b1_obfm_trace.csv`, N=8 OBFM): the BT holds **413 steps per episode with range inside the 152.4–914.4 m band** — so **range was never the binding constraint** — but the best ATA across all 413 in-band steps is **4.096°**, with `roll_effect` **exactly 0.0** and the VP **86.4–86.8°** off target at every one of the best steps. In two-circle the 18 sub-1° steps that do occur sit at **1399–2266 m**, all beyond the far edge, and are mostly the head-on spawn decaying. **Zero sub-1° steps in-band, in either geometry.** The honest pre-fix gap was **4.1° → 1.0°**, not 0.005°. A4's "range and angle never simultaneously satisfied" therefore stood until D1-DONE. | **[M] corrected** |
| E2 | **Training telemetry was dead for two entire campaigns — FIXED 2026-08-06.** `crash_rate`, `win_rate`, `ep_wez_steps` and `ep_altitude_penalty_steps` were logged **0 times across all 4,700 iterations of v6 and all 4,700 of v5** (v4: 557/1,901 rows). So v6's headline change — the dense altitude-floor term added specifically to fix v5's 100% self-crash — had **no observable signal at all**, and all 26 stages across both campaigns advanced on `max_iterations` because the gate metrics were permanently NaN. **Root cause:** `_extract_custom_metrics` looked every metric up under the `_mean` suffix, the **old** RLlib API stack's naming (`episode.custom_metrics[k]` → `k_mean`/`k_min`/`k_max`). On Ray 2.54's new stack `SingleAgentEpisode` has no `custom_metrics` attribute at all, so the platform callback uses `metrics_logger.log_value(("custom_metrics", k))`, which stores the key **bare** — all 21 lookups missed. Fixed with a suffix-tolerant `_cm_get`. **Second defect:** RLlib's EnvRunner reduces and *clears* its MetricsLogger every sample call, so a value appears only on the exact iterations an episode closes (~1 in 20–120 at 100 env steps/iter) — `window=` does not help; persistence had to move consumer-side (`_carry_forward` + a `metrics_age_iters` column so a carried value is never mistaken for a fresh one). **Verified:** 90% row coverage on a probe run, and stage 0 advanced on **`crash_rate=0.0000`** — the first advance condition to fire since v4. Two earlier hypotheses (empty terminal info; `window=` persistence) were **both measured false** and are left retracted in `student/my_callbacks.py`. | **[M] fixed** |
| E3 | **Unattended runs die at stage advancement on a print — FIXED 2026-08-06.** `train_curriculum.py` prints non-ASCII glyphs (`✓ Stage N advancement`, `→ Final bundle saved`). With stdout **redirected to a file** — which is how every unattended run is launched (`scripts/launch_v4_when_free.ps1`, any `> log 2>&1`) — Python falls back to cp1252 and raises `UnicodeEncodeError`. Measured on a redirected probe: it **killed the run (exit 1) at stage advancement**, after the stage had trained successfully; and the same failure inside the bundle-save `try/except` surfaced as `[WARNING] Final bundle save failed` — a *print* failure masquerading as a lost bundle. `sys.stdout`/`stderr` are now reconfigured to UTF-8 at import, which cannot miss a glyph added later. | **[M] fixed** |
| E4 | **Eval CSVs logged `initial_distance_m = 0.0` for every v6 row — FIXED 2026-08-06.** `scripts/eval_v5_vs_bt.py` discarded `env.reset()`'s return, so the field was read from the *final* step's info; the env only emits it at reset. v5's CSV has real values, v6's are all zero, so the newest eval could not report its own spawn geometry — load-bearing here, since E1 traced the bimodality to a 0.017° spawn perturbation. Verified restored: 1496.8 / 2633.4 m for alpha 0/20, matching v5 exactly. | **[M] fixed** |

| D3-**REBASED** | **The v6 residual subtracts value everywhere it acts — the measured submission is `vptrack` alone (2026-08-06).** Rebasing §3's residual hybrid onto the fixed floor, N=30 per cell, identical seeds. **OBFM:** vptrack alone **12/30** wins / 30 WEZ eps / min-ATA 0.024°; plain residual @0.35 **0/30** / 5 / 2.260°; @0.10 **13/30** / 29 / 0.033°; @0.02 **12/30** / 30 / 0.023°. There is a **cliff between 0.10 and 0.35** — the gate is ≤1.0° and the floor converges to 0.024°, so a 0.35 correction from the (untrained, 0-win) v6 policy is orders of magnitude larger than the precision it perturbs. **`EnvelopeGatedHybridProvider` removes the cliff structurally** (residual during the approach, floor untouched during the shot, gated on the floor's own per-step `ctrl_source`): **13/30 at the same 0.35 that destroys the ungated version**, 30/30 WEZ preserved. **But on `two_circle_headon` the residual is actively harmful in the phase it was supposed to help:** vptrack alone **1/30 wins, median min-ATA 9.414°**; gated **0/30, 14.017°**; plain **0/30, 14.017°**; old-floor hybrid **0/30, 14.017°** — that 14.017° is *byte-identical* across all three residual configs, i.e. during the approach the RL policy dominates the trajectory and the floor beneath it is irrelevant. **Conclusion: every hybrid configuration tested is ≤ `vptrack` alone.** This is a verdict on *the v6 policy*, not on the architecture — gating proves the composition is sound and now safe at full authority, so `hybrid_gated` is the upgrade path the moment a policy exists that is worth composing. | **[M]** |
| D3-**FLOOR** | **`MODE="vptrack"` is a strictly better safe floor than `MODE="bt"`.** It uses no RL bundle at all, so it carries none of the bundle-health risk that motivated the `"bt"` fallback (`require_healthy_bundle`'s NaN-demotion path), and it measures **12/30 wins vs bt's 0/30**. Also measured: **49.6 µs per decision, 0.03% of the 166.7 ms six-frame compute budget** — no latency risk on the live path, which also retires the never-run half of §4 row 3. `student/my_submission.py` now offers `vptrack`/`hybrid_vptrack`/`hybrid_gated`; `MODE` is deliberately left at `"bt"` pending a team decision. | **[M]** |

| D1-**ROLE** | **The bypass is a no-op in the defensive role — measured 2026-08-06, N=30 each.** `obfm_defensive` (enemy starts at OUR six; the other half of the confirmed main-match preset, and never previously evaluated with any backend): BT baseline **0/30 wins, 0 WEZ, 0.00 dmg dealt/taken, median min-ATA 1.995°**; vptrack **0/30, 0 WEZ, 0.00/0.000, 2.275°** — with **identical `ep_min_distance` statistics** (min 87.4 m, median 535.4 m), i.e. the two fly essentially the same trajectory. Expected from the design: when we are the one being chased, ATA to the target is large, so the ≤20°/≤1200 m envelope almost never opens and the controller never takes the stick. All 30 are draws with zero damage either way — but that is only safe because the opponent is our own BT, which cannot point either; **against an opponent that can convert, the defensive role is where we lose.** Full picture across all three geometries: **offensive 12/30 · defensive 0/30 (no-op) · neutral merge 1/30.** One mechanism, one phase — the bypass fixes terminal pointing and nothing else. **Positional BFM (winning the merge, reversing a defensive start) is untouched and is now unambiguously the gap that decides placement.** | **[M]** |

| D1-**TUNED** | **Retuned for the real geometry: 3.3% → 73.3% (2026-08-06).** The engagement envelope had been sized against OBFM, where the fight starts inside 1200 m; on the official beam merge the aircraft cross and separate and the controller sat idle. Swept N=30/config on `match_base`, scored by the competition's own rule (damage differential at timeout, `COMPETITION_RULES.md` §5): BT baseline **1/30 (3.3%)**; 1200 m/20° (as shipped) **5/30 (16.7%)**, min-ATA 1.272°; **2500 m/45° → 22/30 (73.3%)**, 8 kills, 14.29 damage, min-ATA **0.097°**. Range dominates and 2500 m is a plateau (20/30/45° all 22/30), so not a noise spike; beyond it regresses (2800 m and 4000 m both 19/30, 2500 m/60° 16/30). **Confirmed on an independent seed: 22/30, 8 kills, 0 losses — identical.** Zero losses and zero damage taken in all 60 episodes. Remaining 8 draws split into 3 that reached the angle gate but logged 0 WEZ steps (angle without simultaneous range — likely convertible by giving the controller throttle authority) and 5 that never got the angle (the positional gap, which no controller tuning reaches). | **[M] fixed** |
| D1-**SELFPLAY** | **Against an opponent that can actually point, 73.3% becomes 23.3% — the headline number measures our opponent's weakness (2026-08-06).** Every result in this project has been scored against our own BT, which never shoots (0.00 damage taken across 60+ episodes). Self-play, N=30 on `match_base`, identical backends both sides: **7/30 win (23.3%), 3/30 loss, 20/30 draw**, damage **11.85 dealt / 11.86 taken** (symmetric, as expected), median min-ATA 3.062° vs 0.097° against the BT. **Draws are the modal outcome (66.7%) — neither side converts.** Directly decision-relevant to the cutoff: under 제1안 only teams that *beat* the committee model advance, and **a draw does not qualify**. So the binding question is no longer "can we score" (solved) but "can we beat a peer", and on current evidence the answer is: usually not — we tie. Treat every BT-relative number in this register as an upper bound. | **[M]** |

| C6 | **Gate 2 has a measured coverage hole at the match's own operating point — and widening it is a NULL (2026-08-06).** BT-vs-BT on `match_base` settles at **median range 2841 m, median own-ATA 92.2°**, and no Gate 2 branch covers it: `Gate2_HeadOnMerge` needs ATA < 20° on *both* sides (actual ~92°), `Gate2p5_GunSolutionHold` needs 150–914 m, `Gate2_OffCenterMerge` needs 3000–5000 m — 2841 m sits **just below its floor**. So the aircraft orbit abeam in a band the rule set has no branch for and the match times out 0-0. **The hole is real; closing it by threshold is not the fix.** Lowering the re-merge floor 3000 → 950 m: **21/30 vs 22/30** baseline (N=30, inside 1 SE), same 8 kills, same 0 losses, damage 13.94 vs 14.29. Reverted. That branch's maneuver was not written for this regime — `Task_LeadTurn` is registered but has **no XML caller at this geometry**, so closing it properly is a C++/BFM change, not a constant. `Rule_real_eagle.xml` now exists (§3's long-owed team rule file), behaviourally identical to `Rule_forTraining.xml` and carrying this finding inline. | **[M]** |
| **THE PATTERN** | **Six levers tried 2026-08-06; the two that worked both addressed POINTING, and all four that failed addressed POSITION.** Wins: the `Controller_CY` bypass (4.096° → 0.024° in-band) and the engagement-envelope retune (3.3% → 73.3% on the real geometry). Nulls/harms: the RL residual (null at ≤0.10, **destroys** a 40% backend at 0.35), throttle authority (null — and the trace shows why: median closest approach is already 92.8 m, *inside* the 152.4 m dead zone, so range was never the constraint), Gate-2 widening (null), and every attempt to make the bypass help from a neutral or defensive start (1/30 and 0/30 respectively). **Conclusion to plan around: terminal pointing is solved and positional BFM is untouched.** The remaining gap is not reachable from the controller, the residual, or XML thresholds — it is the BT's tactical layer, whose merge repertoire was built for a long-range head-on that occurs only in finals round 4, not the beam merge that decides the prelim and rounds 1–3. | **[M]** |

### F. 2026-08-11 — merge root cause, peer benchmarking, G limiter, v7

Backfilled 2026-08-11 from fourteen commits (09:32 → 13:44) that had been recorded only in commit
bodies and inline XML comments. Same evidence tags as above.

| # | Issue | Evidence |
|---|---|---|
| F1 | **ROOT CAUSE of every positional null: Gate 0–2.5 has no branch for the official merge geometry — FIXED 2026-08-11.** The match starts antiparallel and abeam at 2000–3000 ft, and traced step by step: `Gate1_ThreatReaction` needs HCA < 150 (actual 180), `Gate2_HeadOnMerge` needs BOTH ATAs < 20 (actual ~91), `Gate2p5_GunSolutionHold` needs own ATA < 8 (actual ~91), `Gate2_OffCenterMerge` needs 3000–5000 m (actual 610). The tree falls through to its lowest-priority default, which **saturates roll toward an aimpoint 86° off the target and 118° off its own nose — a max-rate turn AWAY.** Both aircraft mirror it to within 0.3°, so range grows **610 → 3278 m in 11 s**, ATA opens 91 → 128°, and the match becomes C6's 2841 m orbit that times out 0-0. Fix: `Gate2_BeamMerge` (HCA > 120, own ATA 45–150, dist < 2500, bounds taken from the trace) driving `Task_NoseToTailTurn`, placed above `Gate2_HeadOnMerge`. Measured BT-only both sides, same seed, first 10 s: shipped **609.8 → 3084.8 m, ATA 91.3 → 118.0°** (separating) vs this branch **609.8 → 2298.2 m, ATA 91.3 → 79.2°** (closing). Maneuver chosen by A/B, N=30 vs BT: NoseToTail 22/30, LeadTurn 22/30, OneCircle 21/30, NoseToNose 21/30 — all inside noise; NoseToTail kept for the cleanest ATA reversal. **ADOPTED ON MECHANISM, NOT ON A WIN RATE** — see F1-BLIND. | **[M] fixed** |
| F1-**BLIND** | **Neither available benchmark can score F1, and this is structural.** vs our own BT is **saturated** (73.3 %, zero losses — 22/30 with the branch and 22/30 without); self-play is **symmetric**, because both aircraft read the same global rule XML, so the edge cancels exactly (7W/15D/8L with, 7W/16D/7L without). The only opponent a better merge pays against is one that does *not* have it — i.e. the actual competition. **Recorded as a tooling gap:** the rule XML is global to both DLLs, so the two aircraft cannot be given different rules. Worth confirming whether the competition supplies each side its own rule XML; if it does, this limitation is local-harness-only. | **[M]** |
| F1-**BLIND-RESOLVED** | **It IS local-harness-only — answered from the code 2026-08-11, no organizer needed.** The submission entry point `run_unreal_inference.py` constructs **exactly one** action provider and contains **zero** references to `AIP_BASE_target.dll`, a target backend, or any opponent provider: our client flies our aircraft and sends commands over UDP. The local harnesses (`run_local_dogfight.py`, `scripts/eval_v5_vs_bt.py`) are what build **both** providers inside one process, and because `bt_rule_manager.activate_rule_xml()` *copies* the chosen file over the fixed name `Rule_forTraining.xml` in the workspace root — the DLL resolves that name relative to its own on-disk location (§5.1's `GetModuleFileName` fix) — two DLLs sitting in the same `Release/` folder necessarily read the same file. **That is a property of running both sides in one folder, not of the competition.** On match day our rule XML governs our aircraft only, so `Gate2_BeamMerge` (F1) is expected to pay off against an opponent that lacks it, and BT work is **not** structurally unmeasurable — it is only unmeasurable *by self-play in this repo*. **The honest residue:** we still cannot locally A/B a BT change, so the per-side **controller** harness (F2) remains the only asymmetric measurement available and F1 stays adopted-on-mechanism. Whether a given round's opponent is another team's client or the committee model is also still unconfirmed — but neither reads our XML. | **[M] resolved** |
| F2 | **Per-side controller settings on the CLI — the first harness in this project that can measure an edge.** `engage_range_m` / `engage_los_deg` / `throttle_control` plumbed through `build_provider` to `--{ownship,target}-vptrack-{range-m,los-deg,throttle}` in both eval scripts and `run_local_dogfight.py`. Varying the **controller** per side is the one asymmetry available without touching the DLL. **Validated on a known-large gap before being trusted** (self-play, `match_base`, N=30): symmetric both-tuned **7W/16D/7L (23.3 %)**; ours 2500/45 vs theirs 1200/20 **24W/6D/0L (80.0 %)**, damage 15.39/0.00. It resolves the difference decisively, so measurements through it mean something — and it values the envelope retune far better than the vs-BT number could. | **[M]** |
| F2-**CHAMPION** | **The shipped config is at a local optimum, now measured against a peer rather than a saturated benchmark.** Champion = 2500 m / 45° / throttle off. N=30 each, self-play on `match_base`; in a fair fight W and L should balance, and the control does exactly that. Control **7W/16D/7L** (even) · LOS 60° **3W/16D/11L** · throttle ON **5W/14D/11L** (damage taken 11.86 → 13.80) · range 3000 m **4W/17D/9L** (0 kills / 7 deaths). Every challenger loses about twice as often as it wins. **The throttle verdict UPGRADES from "null" to "harmful"**: against the BT it was 70.0 % vs 73.3 % (inside noise); against a peer it is 5W/11L. Closing range hard is free against an opponent that never shoots and punished by one that does. | **[M]** |
| F3 | **Deny-damage lever (defensive break): works as designed, measured NULL, default off.** Kept behind a flag rather than shipped on a hunch. | **[M]** |
| F4 | **10 G load-factor limiter on EVERY path — FIXED 2026-08-11, in three steps.** *Measured first* (`scripts/g_limit_check.py`, `artifacts/eval/g_limit_check.csv`): commanding full pitch wings-level yields **3.97 G at 250 kt rising to 14.86 G at 550 kt**, against a real F-16's 9 G rating — the sim enforces no structural limit at all. Also confirmed `pitch = -1` is PULL (climbed 7/7; +1 descended 0/7), a convention that had only ever been *inferred* from reading `Controller_CY`. Limit set to 10.0 G: above the airframe rating so a legitimate hard pull is never clipped, below what the sim hands out. Derived as specific force `n = |dv/dt − g|/g` from velocity history, not from turn rate (which would misreport a vertical pull). **It is feedback, not feedforward** — sustained load is capped (p95 9.55 → 8.24 at 500 kt) but single-step maxima are unchanged and cannot be, since G is measured one step after the command that produced it. Engages in only 4–7 % of steps in a maximum pull. | **[M] fixed** |
| F4-**INERT** | **It shipped inert, and was caught only by verifying before v7.** `GLimitedProvider` and a `build_provider_g_limited()` factory were added, but every call site kept using the raw builder — grep returned **0 hits** in both eval scripts, `my_submission.py` and `run_unreal_inference.py`. Fixed at the *construction boundaries* rather than by opt-in, so nothing has to remember: `run_local_dogfight.build_provider()` wraps internally (both eval scripts inherit it), and `my_submission.build_action_provider()` / `run_unreal_inference.build_action_provider()` wrap their own builders — **the live competition path would otherwise have stayed unlimited.** A second uncovered path was then found: **RL training has no provider at all** (the policy's action goes straight into `env.step()`), closed by `GLimitWrapper` wired outermost in `train_curriculum.env_creator()`. **This is the third recorded instance of the "feature present, wired into nothing" pattern** — cf. `DECO_BFMCheck` (dead *and* fail-open) and `_recycle_native_bts()` (silently skipped for hybrid, D3-a). Treat "it is in the tree" as unverified until a call site is shown. | **[M] fixed** |
| F5 | **The aircraft never pulls above ~4 G in a match, and this is the new open question.** Three probes, each with its prior hypothesis explicitly retracted. **(1)** `energy_probe.py` measured specific energy `Es = h + V²/2g` at 0.22 SD between won and lost episodes and was read as "energy is not the lever" — **wrong quantity**: `Es` is *conserved* as altitude trades for speed, so by construction it cannot separate an aircraft at corner from one at identical energy that is too slow to turn. **(2)** `corner_speed_probe.py`: we spawn at 388.8 kt and **decelerate**, averaging **339.6 kt** — 90–110 kt below the reference corner band — spending 7.3 % of the match inside it; the opponent does the same (7.2 %), which is exactly why self-play cannot answer whether it matters. Forcing corner (CORNER_HOLD) is **harmful**: 73.1 % win rate but **0 kills and 0.63 damage** vs the champion's 8 kills / 14.29. *Metric lesson worth keeping:* the win RATE held while damage collapsed 96 %, because dealing 0.63 against an opponent dealing zero still scores as a differential win — **win rate alone would have passed this change**. **(3)** `turn_rate_sweep.py`: corner is **NOT located** (the fast bins are 310–1367 samples against 20000+ in the slow ones — we cannot separate "corner is low" from "we never fly fast enough to find out"). **The finding that matters: p95 load factor never exceeds 3.95 G anywhere and median turn rate is 0.05–1.35 deg/s, against an airframe rated for 9 G and an action path that F4 proved delivers 14.86 G.** So the aircraft is neither lift- nor command-limited. **The open question is no longer "what is corner" but "why does this aircraft only pull 2 G" — a control-law question, and one that would bound an RL policy exactly the same way if the limit lives in the action path.** | **[M]** |
| F5-**REFUTED** | The 1.48 G was hypothesised to be `Controller_CY`'s multiplicative kill reintroduced in milder form (`pitch = −K·err_gain·max(cos φ, 0)` is exactly zero past 90° around the nose axis), predicting a `PITCH_FLOOR > 0` would help. **Measured N=30/arm: harmful, and monotonically so from zero** — vs BT floor 0.00 → 73.3 %/8 kills/dmg 14.29 vs floor 0.25 → 73.3 %/15 wez/dmg 13.83; self-play control 23.3 % vs floor 0.35 → **13.3 %, 0 kills, dmg 1.19/3.58**. The gate is *load-bearing*, and differs from the defect it resembles: in `Controller_CY` both authorities died together at UTAngle ≈ 180°, whereas here `align → 0` at φ = 180° is exactly where **roll is maximal**. They are complementary. `PITCH_FLOOR` stays 0.0. | **[M] refuted** |
| F6 | **v7 IS LIVE, and its own telemetry has already exposed a defect in the telemetry — READ THIS BEFORE TRUSTING ANY v7 STAGE RESULT.** Launched 2026-08-11 13:46:24 (`experiments/real_eagle_v7.yaml`, `stages_module: student.my_curriculum`). **Stage 1 advanced having closed ZERO episodes of its own.** All 10 of its rows in `training_log.csv` carry `metrics_age_iters` 8→17, and its `crash_rate=0.0` / `ep_min_distance=733.0756795855237` are **byte-identical to stage 0's final closed episode** (total_iter 187) — yet `curriculum_state.json` records `advance_reason: "ep_min_distance=733.0757, crash_rate=0.0000"`. **Root cause:** E2's consumer-side `_carry_forward` persists metrics *across stage boundaries*, and the advancement gate does not consult `metrics_age_iters` — the very column added so a carried value could never be mistaken for a fresh one. **This is the same failure class E2 fixed, one level up:** v5/v6 advanced on `max_iterations` because gate metrics were NaN; v7 can advance on *another stage's* metrics. **Worse than the stage-1 case alone suggests — the gate was averaging over ROWS, not episodes.** `_carry_forward` repeats the last measured episode on every iteration that closes none, so stage 0's final 10-row window held **8 copies of its single non-crashing episode plus 2 of a crashing one**: the gate read `crash_rate=0.2000`, passed a `crash_rate_max=0.30` threshold, and advanced — while the true rate over that stage's 7 episodes was **0.8571**. It advanced on a 20% crash rate that was really 86%. **FIXED 2026-08-11** (`7b404be`): carry reset at each stage boundary, and the advancement window is now built from rows with `metrics_age_iters == 0`, i.e. one row per closed episode, so `advance_window=10` means an average over 10 measurements. Done caller-side in `train_curriculum.py` (where `_carry_forward` and its `_CM_CARRY`/`_CM_AGE` globals actually live) because `check_advancement()` is inside the `src/dogfight` no-edit boundary. v7 was stopped for this fix. | **[M] fixed** |
| F6-**COST** | **What the F6 fix costs, measured — and why sampling was deliberately NOT changed.** From v7's own telemetry: **101.8 env steps per iteration** (replay buffer 121 → 19,877 over 195 rows), **10.92 s per iteration**, **2,734-step episodes** ⇒ **27 iterations per episode**. So an honest `advance_window=10` gate needs **~270 iterations ≈ 49 min per stage**. **CORRECTED 2026-08-11 — an earlier version of this row stopped there and concluded "~14 h, inside budget", which was right about total wall clock and WRONG about per-stage feasibility, because it never checked `max_iterations`.** Ten of the fifteen gated stages were budgeted at **200** iterations — ~7.4 episodes — so their gates could never be evaluated at all: they would have exited on `max_iterations` with the condition untested, silently, exactly the outcome v5/v6 had and that this whole line of work exists to end. That included **all three `match_base` stages**. Fixed by raising those ten to **400** (~14.8 episodes, a real margin over the 10 needed, equal to `wez_approach`'s existing budget); `scripts/verify_report_fixes.py` now asserts the reachability property so it cannot regress quietly. **Campaign cost is therefore 7,300 iterations ≈ 22 h, not 16 h.** The report's Action 3 proposed raising steps-per-iteration or shortening episodes to close episodes faster; both were **rejected on measurement**. Raising steps/iteration does not reduce the ~27,000 env steps needed for 10 episodes (it only relabels them across fewer, longer iterations) and it changes SAC's **update-to-data ratio**; shortening episodes changes what `flight_survival` *means*, so its crash-rate gate would no longer be comparable to v5/v6/v7. v7 deliberately held every hyperparameter identical to v6, and the one-variable-at-a-time discipline is worth more here than ~5 h of wall clock. **Decision: sampling unchanged.** Revisit only if a stage genuinely fails to reach 10 episodes within `max_iterations`. | **[M]** |
| F8 | **`MatchScenarioWrapper` was never wired into training — FIXED 2026-08-11** (`37ec78b`). It has existed since 2026-08-07 and implements the official geometry (`match_base` = prelim + rounds 1-3 beam merge; `match_tiebreak` = round 4+), but `train_curriculum.env_creator()` applied only the Obfm, Habfm and G-limit wrappers. **The failure mode is the dangerous one:** `single_agent_env.py` has no branch for either match mode, so a stage requesting `match_base` would not have errored — it would have trained the DEFAULT spawn while its name, its YAML and every log line claimed the match geometry. **Fourth instance of the "present in the tree, wired into nothing" pattern** (cf. `DECO_BFMCheck`, `_recycle_native_bts()` for hybrid, the G limiter). Wired in as its own commit *before* any stage is written against it; verified a genuine no-op across all 8 scenario modes the curriculum currently uses, and active for both match modes (separation 804 m, inside the 609.6–914.4 m band). | **[M] fixed** |
| F8-**STAGES** | **The official beam merge is now trained — 2026-08-11** (`b4de80c`). Until this commit, no stage in any campaign had trained the geometry the competition opens with; `real_eagle_v7.yaml` said so in its own header and v7 launched two minutes later regardless. New ladder, inserted between the two-circle block and `full_dogfight` (specific → general, ending on the real preset): **`match_base_wide`** (914.4 m fixed, most time to read the merge) → **`match_base_close`** (609.6 m fixed, tightest turn) → **`match_base`** (609.6–914.4 m sampled — the competition preset). All at 4572 m / 200 m/s / LOS 90°, `advance_conditions` and `advance_window` mirroring the neutral-merge siblings. **Scope: only two-circle alphas 45/90/135/180 were removed** (they spawn at ~3500–5486 m, which no round presents); alphas **0/3/5/8/12 are kept**, because the 2026-08-05 lateral-spacing analysis behind them brackets the ~152 m one-circle/two-circle threshold at ranges the match does produce, and that BFM skill transfers to any merge. Net **17 → 16 stages**. Every key the wrapper reads is set explicitly on each stage — not boilerplate: `build_stage_env_config()` deep-merges into `DEFAULT_ENV_CONFIG`, whose `initial_scenario` carries **`altitude_m=7000.0`**, so omitting it would have trained the ladder at 7000 m instead of 4572 m — the same leak that ran `obfm_offensive` at the wrong altitude for weeks and zeroed `habfm`'s LOS. **Resume hazard:** indices after the first two-circle stage change meaning, so do not `--resume` a pre-2026-08-11 run against this file; start a fresh tag. | **[M] fixed** |
| F6-**CRASHES** | **v7 stage 0 crash behaviour, and a clean correlate.** Of the first 9 closed episodes, **8 ended in a crash**; stage 0 nonetheless advanced legitimately on `crash_rate=0.2000` after 195 iterations, so the rate *is* improving. **`ep_altitude_penalty_steps` correlates perfectly with the outcome**: 193/214/198/249/266/202/233/212 steps on the eight crashed episodes, and **exactly 0** on the single survivor (total_iter 187, also the longest at 3406 steps). Sampled replay windows (400 steps of ~2600–3400) show a persistent nose-down, rolling attitude — roll |161–179°| in stage 0, pitch to −46.2° in stage 1 — with steady altitude loss from the 7000 m spawn. **This is the v5/v6 self-crash family (ground impact), not a new failure mode**, and the altitude-floor term is firing on exactly the episodes that die. The replay windows do not reach termination, so the terminal event itself is [unverified]. | **[M]** |
| F7 | **`f16_init.xml` cruise spawn realigned to the confirmed competition preset.** Altitude 22969.9 → 15000.0 ft, `vt` 911.77 → 656.168 ft/s (= 200 m/s exactly), gamma 10 → 0° and phi 127.6 → 0°, so the aircraft starts wings-level in level flight rather than banked in a climb — matching the preset the student-space scenario wrappers already used (§5.1). Same pass: `.gitignore` gained entries for local build leftovers (`DogFightEnv/Release.zip` is 4.7 GB and would have broken the push, not merely bloated the repo), and the Korean-filename cleanup finished by dropping the rev7 manual `.pptx`. | **[M]** |

**Work order after this session.** F1 is the first real attack on the positional gap THE PATTERN
identified, but F1-BLIND means it cannot be scored locally — so the next moves are (1) fix F6 so v7
stage results mean something, (2) settle the F1-BLIND question with the organizers, (3) F5's "why
only 2 G", which bounds the BT and any future RL policy identically, and (4) the §8 DQ workstream,
still never started.

| F9 | **DQ hardening re-verified under induced faults — 2026-08-11. CORRECTION: this was NOT the first time, and an earlier draft of this row said it was.** `scripts/verify_resilience.py` already existed — committed 2026-08-07 in `e161ae4` — and does exactly this: in-process fault injection against both guards with `time.sleep` stubbed. **It was re-run on 2026-08-11 and passes.** The 2026-08-11 pass duplicated it before finding it, and added three cases the existing script does not cover: a **500-consecutive-failure storm** through `ResilientActionProvider` (0 unusable actions), **8 consecutive `make_client()` CONNECT failures** (the existing script exercises `run()` failures, not failures to connect), and `close()` swallowing an inner exception. Both harnesses agree on everything they share. 28 assertions in the new pass, all passing. **`ResilientActionProvider`** absorbs every fault class it claims to (inner raises, NaN, Inf, wrong shape) without propagating, returns the **last good action** once one exists and a neutral zero-vector before that, clips out-of-range output into `[-1,-1,-1,0]..[1,1,1,1]`, swallows `reset()`/`close()` failures, and survived a **500-consecutive-failure storm** with 0 unusable actions. **`supervise_client`** reconnected across **5 consecutive connection losses** covering both real modes — the receive loop returning silently *and* a raised `OSError` (the ECONNREFUSED case the module was written for) — stopped every client on the way out, survived **8 consecutive connect failures**, capped backoff at 5.0 s, and exits cleanly on Ctrl-C. **SCOPE, and `verify_resilience.py` says the same thing in its own closing note: no real UDP server was involved.** Both harnesses prove the wrappers absorb faults; neither proves competition-day connector behaviour. **So §8's workstream is NOT closed.** Two things remain owed and neither is reachable from this repo: (1) **a live induced packet-loss / latency rehearsal** against a practice or competition server, and (2) **`SERVER_IP`, still unconfirmed** — `my_submission.py:106` = `221.151.77.208` vs `startup_command.txt`'s `10.185.16.247`. Those are now the largest remaining DQ exposure, and both need the organizers, not code. | **[M]** |

| F11 | **Peer re-baseline, and the peer harness is now the primary scoreboard (2026-08-11).** Re-run after the G limiter, `Gate2_BeamMerge` and the per-side CLI all landed, N=30 each on `match_base`, scored on the phased competition model. **Self-play control** (both sides champion 2500 m/45°): **9W/16D/5L = 30.0 %**, damage **13.065 dealt / 12.428 taken**, WEZ-contact 15/30. **Champion vs a peer on the OLD tuning** (1200 m/20°): **24W/6D/0L = 80.0 %**, damage **15.416 / 0.000**, WEZ-contact 24/30. **Both cells reproduce the pre-G-limiter measurements within sampling error** — the register's prior figures were 7W/16D/7L (23.3 %) and 24W/6D/0L (80.0 %, dmg 15.39/0.00). The self-play shift 23.3 % → 30.0 % is **0.80 SE** at n=30 (SE ≈ 8.4 %), i.e. noise, not a change; in a symmetric matchup W and L should balance and 9–5 is an ordinary draw from an even coin. **This confirms the G limiter is free in match conditions** (in-match G ~1.5 against a 10 G cap), which `8a8ec50` predicted from N=4 and this now establishes at N=60. | **[M]** |
| F11-**ZERO-DAMAGE** | **"Zero damage taken" is a property of the opponent, not of our defence — and the peer benchmark is the only one that shows it.** Damage taken across the three benchmarks: **vs our own BT 0.000** · **vs a peer on the old tuning 0.000** · **vs a peer on the SAME config 12.428**. The first two are opponents that cannot point; only the symmetric fight puts a gun on us, and there we take **95 % of what we deal** (12.428 vs 13.065). Every "0 losses, 0 damage taken" headline in this register — including D1-TUNED's 73.3 % and F2's 80.0 % — is therefore a statement about the opponent's weakness, exactly as D1-SELFPLAY warned, and **must not be read as evidence of survivability**. Report kills and damage differential alongside win rate (F5's lesson: a config once held 73.1 % while damage collapsed 96 %). **Retire vs-own-BT as a headline number**; keep it only as a regression tripwire. | **[M]** |
| F11-**HARNESS** | **The eval's early-episode warning is a generic heuristic and was wrong here — check it before acting on it.** The self-play run printed "7/30 episodes ended before t=100 s ... a target that flies itself into the ground ends the episode early ... fix the scenario". Inspected: **all 7 ended in a kill**, not a ground impact — 6 `target destroyed`, 1 `ownship destroyed`, every one at 89–91 s with the loser's health negative *and the winner's health degraded to 0.04–0.23*. They are mutual gun duels that one side won, i.e. the most decisive outcomes in the run, and their phased scores are legitimate. The warning fires on episode length alone and cannot tell a kill from a crash. | **[M]** |

| F12 | **The ~1.5 G ceiling is NOT in either control law — both controllers already command FULL pitch and still get ~1.2 G (2026-08-11).** F5 left the open question as "why does this aircraft only pull 2 G — a control-law question", and the report's Action 9 named the vptrack pitch law's gain/normalization as the next candidate. `scripts/pitch_g_probe.py` instruments commanded pitch against `GLimitedProvider`'s `g_measured`, split by `VPTrackingProvider`'s per-step `ctrl_source`. **Measured, 12 self-play `match_base` episodes, ~266–288k steps across two runs:** pitch command is **saturated (\|cmd\| ≥ 0.99) on 84 % of BT-flown steps and 56–64 % of vptrack-flown steps**, and G median is **1.16 (bt) / 1.15 (vptrack)**. **The correlation runs backwards:** at *low* pitch command (\|cmd\| < 0.5) G is *higher* — bt 1.45, vptrack 1.87 — than at full command (bt 1.17, vptrack 1.23). Commanding more pitch does not produce more G; it produces slightly less. **So no gain, floor, cap or normalisation in either law is the limiter, and Action 9's stated next candidate is refuted.** G is also flat at ~1.1–1.2 median across *every* airspeed band present, so there is no regime where full pitch buys the ~6.7 G `g_limit_check` measured from a trimmed wings-level entry. **Decision-relevant consequence:** the constraint sits DOWNSTREAM of the action, so it would bound an RL policy identically — the question F5 flagged as mattering. Pitch-channel work, by the controller or by a policy, cannot recover it. | **[M] refuted** |
| F12-**OPEN** | **What F12 does NOT establish, and the hypothesis worth testing next.** Holding full aft stick ~80 % of a match is itself the suspicious part: that is a maximum-induced-drag command, and the natural reading is an energy spiral — full stick → high AoA → drag → speed decay → less available G → still full stick. **That mechanism is UNPROVEN here.** The probe records `StateIndex.KCAS`, which reads median 126 / max 273 over the match, but `scripts/corner_speed_probe.py` reports TAS averaging 339.6 kt from the velocity norm; those disagree by roughly 2× and **the discrepancy is unreconciled — do not quote either as the absolute airspeed until it is.** The state vector exposes no AoA field (`state_schema.py` has N/E/D, attitudes, velocities, KCAS, FUEL, SIM_TIME, LAT/LON/ALT, HEALTH), so AoA-limiting cannot be confirmed from Python; it would need a C++ probe or an FDM property read. Note also that F5-REFUTED already showed *more* pitch (`PITCH_FLOOR` > 0) is monotonically harmful — consistent with an energy story, and it makes **energy-aware pitch limiting the untested direction**, not more authority. Also observed: two identical-seed runs put the vptrack share at 5.6 % and 12.0 %, so treat controller shares as approximate (E1 again). | **[M]** |

| F13 | **E1 (harness nondeterminism) and E1-leaks (cross-episode BT state) are formally WON'T FIX — closed 2026-08-11 so they stop being re-opened.** Both are real and both are unreachable. E1's bimodality originates inside `JSBSimAIPLib.dll`'s reset (E1-cause) — a protected binary with no source, so perfect determinism is unachievable, and the register has said "do not chase it" since 2026-08-05. E1-leaks originates in `bt_action_provider.py`'s deliberately-no-op `reset()`, inside the `src/dogfight` hard no-edit boundary. **Both already have working mitigations that are cheaper than a fix:** the N≥30 success-rate protocol, and `_recycle_native_bts()` in the eval script (E1a-done), which was validated as reproducing the 9-separate-process distribution within sampling error. **Cost of leaving them:** measurement resolution of roughly ±8 % at n=30 (F11 measured SE ≈ 8.4 %), and controller-share figures that move run-to-run on identical seeds (F12-OPEN saw 5.6 % vs 12.0 %). That is the price of every A/B in this project and it is already priced in. **Before re-opening, read E1c-null and E1e-null:** five scalar knobs were swept across both axes and only a genuine correctness bug — `MFsum`'s integer truncation, E1d — ever moved the attractor. Effort here has a measured track record of returning nothing. | **[D] won't fix** |

| F14 | **There is no defensive lever. `defensive_break` upgrades from "null" to HARMFUL against a peer — and the reason generalises (2026-08-11).** F3 recorded the deny-damage break as "works as designed, measured null, default off", but that null came from our own BT, an opponent that deals **0.000** damage — a vacuous test for a *deny-damage* feature by construction. Re-run against a peer, N=30 self-play on `match_base`, identical seeds, break enabled on **our side only**: **W-L 9-5 → 6-10**, kills **6 → 3**, damage dealt **13.06 → 7.61 (−42 %)**, damage taken **12.43 → 7.04 (−43 %)**. It *does* cut incoming damage — and cuts our own output by the same proportion. **Breaking off does not buy asymmetry; it suppresses both sides equally and forfeits the exchange.** Second lever to flip null→harmful on moving to the peer benchmark (throttle was the first, F2-CHAMPION); treat every remaining "measured null vs BT" verdict in this register as untested rather than settled. `DOGFIGHT_VPTRACK_DEFENSIVE` stays **off**. | **[M] harmful** |
| F14-**WHY-IT-MATTERS** | **The strategic consequence: win rate cannot be bought defensively, only positionally.** Anatomy of the 30 peer episodes (F11): **draws 16/30 (53 %)** never converge — min-ATA **4.011°**, 17 steps ≤1°, 6 WEZ steps, damage 0.05/0.05 both ways. **Wins 9/30** reach min-ATA **0.012°**; **losses 5/30** reach **0.048°** — we point *just as well when we lose*, and every loss margin is narrow (−0.09, −0.12, −0.17, −0.12, −0.25). So converged fights are near-symmetric 1:1 trades decided by 10-25 %, which is exactly what two identical backends should produce. **Pointing is saturated** (0.012° against a ≤1.0° gate is 80× inside it), so no further controller tuning is available — F2-CHAMPION already showed all three challengers losing ~2:1. **And F14 now closes the defensive axis.** What remains is the 53 % that never converge: the merge. This is THE PATTERN confirmed on the damage axis — terminal pointing is solved, positional BFM decides everything, and against an opponent that *can* shoot the only edge is arriving with an advantage rather than trading evenly from a neutral merge. `Gate2_BeamMerge` (F1) is the one change addressing it, is invisible in self-play because both sides read the same XML, and per F1-BLIND-RESOLVED **should** differentiate in a real match where the opponent lacks it. | **[M]** |

| F15 | **F1-BLIND is BROKEN — BT changes can be A/B'd locally after all (2026-08-11).** F1-BLIND recorded that a BT change cannot be scored here because both DLLs sit in `Release/` and read the same `Rule_forTraining.xml`, so vs-BT is saturated and self-play cancels it exactly; every merge/tactics change since has been adopted "on mechanism". **That was a layout constraint, not a hard one.** Measured: the DLL resolves its rule file relative to **its own on-disk location** (§5.1's `GetModuleFileName` fix), so a copy of the DLL in its own folder reads its own rules — and Windows loads a DLL once per resolved *path*, so the copy also gets separate static state, the same reason `AIP_BASE.dll` and `AIP_BASE_target.dll` are two files. **Proof, twice:** a DLL copy in a subdirectory with no XML beside it reports `Behavior Tree Initialization Failed: XML_ERROR_FILE_NOT_FOUND` and initialises once the XML is added; and inside the real eval path, with the peer's XML removed, exactly **one tree initialises (ours) and one fails (the peer)**, with outcomes changing in 3 of 5 episodes. `scripts/setup_peer_bt.py` builds the rig (`--from-git REV` to run the rule file as of any revision, `--verify` to re-prove resolution); the directory is gitignored — it adds files only, never renames/moves/deletes a runtime asset, so §8 is untouched. **Two silent-failure traps, both in the script's docstring:** do not also pass `--bt-rule-xml` (`activate_rule_xml()` copies over OUR live file and restores symmetry), and re-verify every time — a peer that reads our XML just looks like an ordinary symmetric result. | **[M] capability** |

| F16 | **`Gate2_BeamMerge` measured at last — and it is NULL. The merge gap is not addressed by anything currently in the tree (2026-08-11).** F15's rig made this scoreable for the first time: our side runs the branch, the peer runs the rule file as of `dc3c46c^`, N=30 on `match_base`. **In `vptrack` (what we ship): 9W/16D/5L — the symmetric control's record exactly, with 29 of 30 episodes byte-identical.** Verified not to be a harness artifact: with the peer's tree deliberately broken its BT failed to init 5/5 and outcomes moved in 3 of 5 episodes, so the rig was genuinely in effect. **In BT-vs-BT: 1W/29D/0L, damage 0.055/0.000** — directionally ours (they won nothing and dealt nothing) but a single event and 0.055 damage across 30 episodes is indistinguishable from the 0-0 stalemate C6 already recorded at this geometry. **So `dc3c46c`'s trajectory trace is real but does not survive to an outcome:** the branch genuinely closes rather than separates over the first 10 s (ATA 91.3° → 79.2° vs → 118.0°), and the aircraft still fails to convert. **This retracts F1-BLIND-RESOLVED's inference** that the branch "should differentiate in a real match where the opponent lacks it" — that was reasoning from architecture; measured against an opponent that lacks it, it does not. **Mechanism unexplained and worth knowing before more BT merge work:** the branch's own gate (HCA > 120, own ATA 45–150, dist < 2500) is satisfied at the `match_base` spawn (HCA 180°, ATA ~91°, ~760 m), so it should be firing in `vptrack` too, yet 29/30 episodes are bit-identical. Either it is not firing, or it fires and emits the same stick as the branch it displaced. Settle that before writing another gate. | **[M] null** |

| F17 | **WHICH GATE WINS AT THE MERGE: `Gate1_Notch`. The entire Gate 2 block is shadowed at the geometry it was written for (2026-08-11).** F16 left open why `Gate2_BeamMerge` is inert when its own conditions are satisfied at the spawn. Answer, from the tree order plus `Task_Notch.cpp`: the outer Fallback runs **Gate0 → Gate2.5 → Gate1 → Gate2 → Gate3**, and `Task_Notch` is the **first child of `Gate1_ThreatReaction` with no decorator on it at all**. It returns SUCCESS when `EnemyInSight_Target` **and** `Distance ≤ 2000 m` **and** the target's ATA to us is **70–110°** (`NOTCH_RANGE_TRIGGER_M`, `NOTCH_BEAM_MIN/MAX_DEG`). The official beam merge is **610–914 m at ~90°** — inside both windows — so Notch fires at the spawn, Gate1 succeeds, and **the outer Fallback never reaches Gate 2.** Not just `Gate2_BeamMerge`: `Gate2_HeadOnMerge`, `Gate2_OffCenterMerge` and `Gate2_NeutralFight` are all shadowed there too. `NOTCH_SUSTAIN_S = 1.5 s` then releases and immediately re-claims, so Gate 2 gets roughly one tick per 1.5 s. **This retro-explains C6** (widening `Gate2_OffCenterMerge`'s floor to 950 m measured null — below 2000 m Notch owns the tick) **and F16** (adding a Gate 2 branch cannot help if Gate 2 never runs). **Root cause is an incomplete fix, and the tree says so in its own comment:** on 2026-08-05 `Gate1_JinkingTurn` and `Gate1_TheBreak` were given `HCA < 150` exclusions precisely so a head-on merge defers to Gate 2 — **`Task_Notch`, which sits above both, was not**, and the same comment records "HABFM (Notch fires first regardless, ~90deg beam angle never reaches these two nodes)" without connecting that to the match geometry. **The candidate fix is XML-only, no rebuild:** wrap Notch in the same `HCA < 150` sequence as its two siblings; at the antiparallel merge HCA is 180°, so Notch would defer and Gate 2 would finally run. Under test via F15's rig. | **[M] root cause** |

| F18 | **RETRACTION — the F15 rig works for ONE episode, so F16's "Gate2_BeamMerge is null" is withdrawn (2026-08-11).** Three separate peer tree changes — adding `Gate2_BeamMerge`, gating `Task_Notch`, and **deleting `Gate1_ThreatReaction` outright** — each changed **only episode 0**, in `vptrack` (29/30 identical) *and* in BT-vs-BT (9/10 identical). Deleting an entire gate block cannot plausibly be inert, so the peer's rule file is **not in effect from episode 1 onward**; the eval's `_recycle_native_bts()` re-creates the tree between episodes and the peer's own XML stops being what it builds from. **Why the verification missed it:** `setup_peer_bt.py --verify` runs `--episodes 1`, which is precisely the one episode that *does* work — the check was vacuous for the multi-episode runs it was meant to license. The contrasting broken-XML probe (3 of 5 episodes differing) misled rather than helped: with no XML the BT fails to init *every* episode, a different mechanism from a valid-but-different tree. **Consequences: F15's capability claim is overstated — per-side rules are proven for episode 0 only, not across a recycled eval. F16 is WITHDRAWN entirely; `Gate2_BeamMerge` has NOT been scored, and its 29/30-identical result measured the rig, not the branch.** F17's root cause is unaffected — it rests on tree order, `Task_Notch.cpp`'s thresholds and the tree's own 2026-08-05 comment, none of which depend on this rig — but its notch-gate fix is **untested**, not "under test". **To make the rig real, the recycler must rebuild the peer from the peer DLL each episode; until then trust nothing from it beyond a single episode.** | **[M] retracted** |

| F19 | **CORRECTS F18. The rig was fine; the HARNESS is insensitive to the tree after episode 0 — which means every multi-episode BT experiment in this register measured roughly ONE episode (2026-08-11).** F18 blamed the peer rig for "only episode 0 changes". Wrong diagnosis. The broken-XML probe produced **one `Behavior Tree Initialization Failed` per episode**, so `CreateBehaviorTree` runs and the XML is re-read **every episode** — the rig was delivering per-side rules throughout. The pattern is the harness, not the rig, and it reproduces **with no rig at all**: the `Task_Notch` fix applied to the LIVE `Rule_forTraining.xml`, both aircraft reading it, vs-BT N=30 — again **only episode 0 differed** (`max time out`/0.000 → `target destroyed`/1.390; kills 8→9, WEZ 1328→1471, damage 13.94→15.33, mean min-ATA identical at 0.745°). **Four independent tree changes across three harness configurations, all moving exactly one episode:** add `Gate2_BeamMerge`; gate `Task_Notch`; **delete `Gate1_ThreatReaction` entirely**; and the live notch fix. Deleting a whole gate block moving 1 episode in 10 is not a small effect size — it means **episodes 1+ are insensitive to the behaviour tree**. **Leading candidate, already documented: E1-leaks.** Episode 0 is the only one with clean native-BT state; from episode 1 the carried `RunningTime` / `ErrorSum` / `MF[]` / `ActiveManeuverID` dominate, and `_recycle_native_bts()` evidently does not reset the blackboard even though it clears registrations. **Consequence for the record: every N=30 XML/threshold verdict here — C6's re-merge widening null, A3, A5, the beam-merge null — rests on ~1 episode of tree-sensitive signal plus 29 of leaked-state noise, and should be treated as UNMEASURED, not null.** Fixing the recycler to genuinely reset blackboard state is now the highest-value harness work in the project: without it no BT change can be scored at all. | **[M] corrects F18** |

| F20 | **CORRECTS F19 AND CASTS DOUBT ON F17. The recycler is FINE; and Gate 1 is probably not the shadow either. Stop inferring from outcomes — instrument the tree (2026-08-11).** F19 blamed cross-episode blackboard leakage. **Measured and refuted:** every eval log shows **exactly 60 `Behavior Tree Initialized` for 30 episodes × 2 aircraft, and zero `BT already exists`** — `_recycle_native_bts()` destroys and rebuilds both trees every episode, `UCPPBehaviorTree` is a `shared_ptr` in `BTList` so its blackboard dies with it, and the XML is re-parsed each time. Episodes ARE independent w.r.t. native BT state; E1a-done works as documented. **So the "only episode 0 moves" pattern is not leakage — the tree edits genuinely changed nothing.** Trajectories are **bit-identical in 29/30 episodes across `ep_min_ata_deg_3d`, `ep_min_distance`, `final_ata_deg_3d` and `steps`** (step counts equal to the integer), which is not "similar", it is "no decision changed". **This contradicts F17.** If `Task_Notch` really won the merge tick, gating it would alter every episode's opening — and deleting **all of Gate 1** through the peer rig would have altered more than 1 episode in 10. Neither did. The likeliest reading is that **Gate 1 never wins at the merge in the first place**, so F17's "Notch shadows Gate 2" root cause — derived from tree order, `Task_Notch.cpp`'s thresholds and the tree's own comment, all static — **is not supported behaviourally and should be treated as unproven.** Its remaining untested premise is `EnemyInSight_Target`, which `CheckSight` may leave false at the spawn. **The standing lesson: four attempts to identify the merge gate by perturbing the tree and reading outcomes have produced three wrong conclusions (F16, F18, F19). Outcome-level inference cannot resolve gate selection here. The next step must be DIRECT instrumentation — per-tick logging of the winning branch from C++, which needs a DLL rebuild — and no further BT merge work should be planned on inference until that exists.** | **[M] corrects F19** |

| F21 | **The C++ build path is OPEN and verified on this host — which unblocks the only remaining way to answer the merge question (2026-08-11).** `PROJECT_STATUS_REPORT_2026-08-11.md` listed "builds with 0 errors on this host" as **[unverified]**: the only full MSBuild log was dated 2026-08-03 and referenced `C:\Users\Codemist\Desktop\AIP_forStudent\`, i.e. the original distribution machine, not this one. **Now verified end to end.** Toolchain: MSBuild **18.8.2.30814** (Visual Studio Community **2026**, `C:\Program Files\Microsoft Visual Studio\18\Community`), project toolset **v145** — the retarget from `e5db032`. `msbuild AIP_DCS.sln -t:Rebuild -p:Configuration=Debug -p:Platform=x64` completes in **2 m 13 s with 0 errors and 42 warnings** (all pre-existing `C4244`/`C4305` narrowing and two `C4190` C-linkage notes; none new). Output lands at `bin/debug.x64/AIP_DCS.dll` (2,821,632 bytes), **not** at the deployed `AIP_BASE*.dll` — deployment is a separate manual copy, so building is safe while a campaign is training, and both deployed DLLs were hash-verified unchanged (`524ADC75…`) across the rebuild. **And the artifact works, not just compiles:** loaded via `AIPilot`, `CreateBehaviorTree` reported `Behavior Tree Initialized`, `RemoveBT` clean. **Why this matters now:** F20 established that outcome-level inference cannot resolve gate selection here — four rounds produced three wrong conclusions. Per-tick logging of the winning branch from inside the tree is the one instrument that can, and it requires exactly this rebuild. The path is open. | **[M] verified** |

| F22 | **MEASURED DIRECTLY AT LAST: `Gate2p5_GunSolutionHold` wins EVERY tick at the merge — not Gate 1, not Gate 2. F17 is refuted (2026-08-11).** `AIP_DCS/BehaviorTree/BT_Content/GateTrace.h` subscribes to every node's status change and dumps the winning path per tick; inert unless `AIP_BT_GATE_TRACE` is set, so it is safe to leave in the submission DLL. First trace at the official beam merge (609 m, own ATA 91.0°, target ATA 91.0°, HCA 180.0°): `Gate0_ClimbToSafeAltitude:F → Gate2p5_GunSolutionHold:R → Gate2p5_GunSolutionHold:S`, identically on every tick. **Gate 2.5 sits ABOVE Gate 1 and Gate 2 in the outer Fallback, so Gate 1 is never reached and Gate 2 is never reached.** That explains, in one stroke, why gating `Task_Notch` was inert, why **deleting all of `Gate1_ThreatReaction` was inert**, and why `Gate2_BeamMerge` was inert: every one of those edits was to a branch that never executes. **F17's "Notch shadows Gate 2" is wrong** — its premises all check out (`Distance` 609 ≤ 2000, target ATA 91 ∈ [70,110], and `EnemyInSight_Target` = **1**, the one thing never previously verified), but they are irrelevant because Gate 1 is unreachable. **UNEXPLAINED AND IMPORTANT:** Gate 2.5 succeeds **without any of its four children ticking** — `Gun_DistGt152p4`, `Gun_DistLt914`, `Gun_OwnATA_Lt8`, `Gun_Track` produce no transition at all even with `AIP_BT_GATE_TRACE_ALL=1`, and a node inventory confirms all four exist in the 79-node tree with correct names. Its guard `Gun_OwnATA_Lt8` demands own ATA < 8° against an actual 91°, so it should FAIL. An empty `Sequence` returns SUCCESS immediately in BehaviorTree.CPP, which fits the observation exactly. **Whether the children are orphaned at parse time or the probe misses their transitions is not yet established — settle that before trusting any gate below 2.5.** | **[M] refutes F17** |

| F23 | **Gate 2.5 removal test: it IS load-bearing, and `Gate2_BeamMerge` FAILS its own conditions even when reachable (2026-08-11).** Removing `Gate2p5_GunSolutionHold` and re-tracing: the winner becomes `Tail_LeadPursuit`, reached only after **`Gate1_ThreatReaction:F`, `Gate2_MergeAndNeutralFight:F`, `Gate3_EnergyState:F`, `Gate4_OffensiveSelector:F`** — the tree falls all the way through. **Two conclusions, both independent of any harness question. (a) Gate 2.5 earns its place:** vs BT, N=30, `21W/7D/2L` against `22W/8D/0L` with it — the **first losses recorded against our own BT in any of these runs**, and damage taken goes `0.000 → 0.049`. Offence is untouched (dealt 13.9377 vs 13.9378, identical to 4 dp); what Gate 2.5 provides is *defence*. Restored. **(b) `Gate2_BeamMerge` does not fire at the merge even when it IS reachable.** Its conditions all read satisfied — HCA 180 > 120, own ATA 90.9 ∈ [45,150], distance 608 < 2500 — yet Gate 2 returns FAILURE. Combined with `Gun_OwnATA_Lt8` **passing** at own ATA 91° when it demands < 8°, two independent gates behave opposite to their written conditions. **The likeliest single explanation is that `DECO_AngleOffCheck`/`DECO_LOSCheck`'s `UpDown` comparison sense is inverted relative to how every gate in this XML is written** — which would make a large fraction of the rule file mean the opposite of its authors' intent, and is now the highest-value thing to verify in the tree. **~~Also correcting F22: its "children never tick, so the Sequence may be empty" note is probably wrong — the same missing-children pattern appears under every gate, so it is a limitation of the probe.~~ WITHDRAWN by F25 — that "correction" was itself wrong, and in the more damaging direction. F22's original instinct was RIGHT: the composites really are empty, so there were no child transitions to miss and `GateTrace.h` was reporting accurately the whole time. `Gate1_ThreatReaction` failing with zero children is not "all children tried and failed", it is an empty `Fallback` failing immediately. The probe has no known depth limitation and should be trusted after F25 lands.** Even removing the always-winning gate moved only **2 of 30 episodes**, which again shows how little the BT influences outcomes while `vptrack` holds the terminal envelope. | **[M]** |

| F24 | **THE BEHAVIOUR TREE IS DEAD CODE BELOW GATE 2.5. `Gate2p5_GunSolutionHold` returns SUCCESS unconditionally, without evaluating its guards or running any task (2026-08-11).** Decisive test: `Gun_DistGt152p4` was changed to require `Distance >= 999999 m` against an actual **609 m** — an impossible guard — and **Gate 2.5 still returned SUCCESS**, winning every tick exactly as before. Its guards are never evaluated. Corroborating: `ActiveManeuverID` is `Maneuver_None` on **every** traced tick, i.e. no maneuver task ever claims a phase, and `Task_GunTrack` — the Sequence's own action — never runs. **Gate 2.5 sits above Gate 1, Gate 2, Gate 3, Gate 4 and the tail, so ALL of them are unreachable.** The decorators are innocent: `DECO_LOSCheck.cpp` and `DECO_AngleOffCheck.cpp` implement `Greater`/`Less` exactly as written (`>=` / `<=`), so the earlier inversion hypothesis is refuted — the guards are correct and simply never run. **THIS IS THE ANSWER TO C2.** "Complexity has not bought performance… ~25 nodes / 6 gates / 23 `Task_*` classes → 0 WEZ steps in every configuration tested" is explained: **essentially none of it executes.** The tree is functionally a single node that succeeds and emits nothing, so `VP_Cartesian` is never updated by any task and the aircraft flies a stale aim point. It also explains, at a stroke, every null this register has recorded from XML work — C6's re-merge widening, A3, A5, `Gate2_BeamMerge` (F16), the `Task_Notch` gate (F19/F20) — all were edits to unreachable branches. **And it is confirmed from the other direction:** deleting Gate 2.5 makes the tree fall through to `Tail_LeadPursuit`, a task that *does* set VP — the BT becomes functional, our BT *opponent* gets stronger, and we lose 2 episodes (F23). **MECHANISM NOT YET ESTABLISHED:** why this particular `<Sequence>` has no children attached, when `Gate1_ThreatReaction` returning FAILURE proves nesting works elsewhere in the same file. That is the next question, and it is now the single highest-value item in the project — a working BT is worth more than any tuning, and none of the tree's tuning has ever been live. | **[M] project-defining** |

| F25 | **ROOT CAUSE FOUND: a `name` attribute on a control node makes it build with ZERO children. 17 of the 20 composites in the rule file are empty shells (2026-08-11).** Dumped `childrenCount()` for every composite at build time. Result is absolute: **all 3 anonymous composites have children (1, 8, 9); all 17 NAMED `<Sequence>`/`<Fallback>` nodes have 0.** Confirmed causally — deleting only the `name` attribute from `Gate2p5_GunSolutionHold`'s `<Sequence>`, changing nothing else, gives it its **4 children** back. **This explains every observation exactly, via BehaviorTree.CPP's empty-composite semantics:** an empty `Sequence` returns SUCCESS immediately, an empty `Fallback` returns FAILURE immediately. So `Gate2p5_GunSolutionHold` (Sequence, 0 children) **succeeds unconditionally and wins every tick**; `Gate1_ThreatReaction`, `Gate2_MergeAndNeutralFight`, `Gate3_EnergyState`, `Gate4_OffensiveSelector` (Fallbacks, 0 children) **all fail unconditionally**; `Tail_LeadPursuit` (Sequence, 0 children) succeeds — which is precisely the trace when Gate 2.5 is removed. **The only nodes that have ever executed are `Gate0_ClimbToSafeAltitude` and `Tail_SingleSideOffset`** — the two real `Task_*` leaves sitting directly under the anonymous outer `Fallback`. **Every one of the 23 `Task_*` maneuver classes, all five gate blocks, and every decorator in this tree has NEVER RUN.** This is the mechanical answer to C2, to A4, to every positional null in this register, and to why "~25 nodes / 6 gates" produced 0 WEZ steps in every configuration ever tested. **The fix is XML-only, no rebuild: drop `name=` from the 17 control nodes** (leaf `Task_*`/`DECO_*` names are fine — those nodes work). It is not a tuning change; it turns the tactical layer on for the first time, so it must be re-baselined from scratch and every prior BT measurement in this register should be considered void rather than merely suspect. | **[M] ROOT CAUSE** |

### F26+ — 2026-08-13: F25 APPLIED, and the full post-fix re-baseline

The F25 fix was applied on 2026-08-13 and the tactical layer has now executed for the first time
in this project's history. **Every BT-relative row above this line was produced by a tree running
two leaf tasks and is VOID, not merely suspect** — that includes rows marked "fixed". The rows
below supersede them where they overlap. All figures N=30 on the stated geometry, champion
controller defaults (2500 m / 45°), deployed 2026-08-06 DLLs (the fix is XML-only, so no DLL
change was needed); artifacts under `artifacts/eval/postf25_*` and `artifacts/eval/gate1brk_*`.

| # | Issue | Evidence |
|---|---|---|
| F26 | **F25 APPLIED AND VERIFIED — 17 nodes execute where 2 ever did (2026-08-13, commit `5412a79`).** `name=` dropped from all 17 control nodes in both rule XMLs; leaf `Task_*`/`DECO_*` names untouched (23 + 29 verified intact), files kept byte-identical, UTF-8-no-BOM, Korean comments preserved. v8 was retired rather than resumed — it was killed by an unplanned reboot at 08:24:38, five minutes after its last checkpoint write, and none of its 14 completed stages had advanced on a real gate anyway. **Verified by instrumentation, not outcomes** (four rounds of outcome-inference produced three wrong conclusions, F16–F19): node inventory shows **zero empty composites**, `Gate2p5_GunSolutionHold` went 0 → **4 children** exactly as predicted, and a traced episode shows 17 distinct nodes winning ticks across **all five gate blocks** — `Gate4_OneCircleFight` 362, `Gate2_FlatScissors` 130, **`Gate2_Beam_NoseToTail` 108** (the branch F16 called null), `Tail_LeadPursuit` 32, `Gate4_NoseToTailTurn` 25, `Gate0_ClimbToSafeAltitude` 21, `Gate4_LagPursuit` 17, `Gate1_TheBreak` 12, `Gate3_EnergyTactics` 11, `Tail_Pure` 9, `Gate3_AnglesTactics` 9, `Tail_SingleSideOffset` 6, `Gate4_HighYoYoUp` 5, `Gate4_BarrelRollAttack` 5, `Gate4_LagDisplacementRoll` 3, `Gate1_JinkingTurn` 2, `Gate2_LeadTurn` 1. Gate 2.5 now correctly **fails** `Gun_OwnATA_Lt8` at the merge (91° vs <8°) instead of succeeding vacuously. | **[M] fixed** |
| F26-**WORTH** | **What the fix is worth, on a single isolated variable — the measurement F1-BLIND said was impossible.** Via the F15 peer rig, holding our side constant post-F25 and varying **only the opponent's tree**, `match_base`, vptrack both sides: opponent **with** a working tree → **9W/14D/7L**, damage 5.82/7.46, 5 deaths; opponent **without** it → **16W/14D/0L**, damage 6.99/**0.06**, **0 deaths**. An even fight against a peer that has it, a shutout against one that does not, taking 0.06 damage across 30 episodes. The fix **cannot hurt** — a symmetric matchup must balance, and it does — and is decisive against anyone lacking it. | **[M]** |
| F26-**BT-ALONE** | **BT-vs-BT broke C6's 0-0 orbit stalemate.** WEZ-contact steps **8 → 967** across 30 episodes, first-ever kills **0 → 2**, median min-ATA **1.419° → 0.041°**, damage 0.05 → 2.72. `MODE="bt"` remains far weaker than `vptrack` (2.72 vs 7–14 damage) so it stays the fallback, not the submission — but it is no longer a null. | **[M]** |
| F26-**GEOMETRY** | **Full geometry re-baseline, vptrack vs bt.** `two_circle_headon` (the neutral merge THE PATTERN called the gap that decides placement): **1W/29D/0L → 8W/20D/2L**, WEZ 123 → 407, median min-ATA **9.414° → 0.014°**. D1-LIMIT's "the bypass converts offensive position but cannot create it" was a dead-tree artifact. `obfm_offensive`: 30W/0D/0L → **19W/10D/1L** with kills **12 → 0** — the opponent now evades well enough that we cannot close, though our own pointing improved (0.024° → 0.010°). `match_base` vptrack-vs-bt: 22W/8D/0L → 10W/18D/2L, **but read F26-CONFOUND before quoting that.** | **[M]** |
| F26-**CONFOUND** | **Do not read the vs-own-BT drops as us getting weaker.** Those runs give BOTH aircraft the fix, so they measure the opponent getting stronger: our own BT went from dealing **0.000 damage in every episode ever recorded** to killing us. In the same `match_base` run our own pointing improved ~10x (median min-ATA 0.097° → 0.010°) and steps-within-1° went **12,431 → 40,227**, while WEZ contact fell slightly — we hold ANGLE far better and cannot hold RANGE against something that now evades. **vs-own-BT has stopped being a saturated benchmark and finally carries signal**, which is what F11-ZERO-DAMAGE asked for. | **[M]** |
| F26-**DEFENSIVE** | **The defensive role is a genuine capability hole, and F25 revealed it rather than caused it.** `obfm_defensive`: 0W/30D/0L → **1W/0D/29L, 16 deaths, damage 2.45/27.51**, median min-ATA **174.2°** (pointed away the whole fight). The old 0/30 draws were purely an opponent that could not shoot; D1-ROLE predicted this in writing. **`defensive_break` re-tested here and is a NO-OP** — 1W/0D/29L either way, damage dealt **2.45 identical**, WEZ **624 identical**, deaths 16→17; **F14's "there is no defensive lever" verdict SURVIVES.** Root cause, from a gate trace: the attacker runs `Gun_Track` **300/300 ticks** while we run `Gate1_JinkingTurn` **300/300 ticks with nothing else ever winning** — `Gate1_JinkingTurn` succeeds unconditionally and **starves `Task_Evade` ("The Break")**. **Scope:** `match_base` is the CONFIRMED prelim/rounds-1–3 geometry and we are even there; the OBFM presets remain unconfirmed (§4 row 6), so this is a capability hole, not a confirmed competition exposure. | **[M]** |
| F26-**GATE1-REJECTED** | **A Gate 1 reorder was tried and REVERTED on measurement — and the way it failed is the lesson.** Moving `Task_Evade` above the jink and gating it on a real gun solution (target ATA < 20, dist < 914) fixed the trace (`Gate1_TheBreak` 300/300) and looked excellent measured the usual way: `obfm_defensive` **1W→11W**, deaths 16→9, WEZ 624→1911, median min-ATA 174.2°→**0.007°**; `match_base` **10W/18D/2L → 21W/8D/1L**. **But both of those give BOTH trees the change.** Scored properly through the peer rig — ours reordered vs a peer on F25-only, vptrack both sides — `match_base` came out **6W/11D/13L against a 9W/14D/7L control**, i.e. losing better than 2:1 on the CONFIRMED competition geometry, damage taken 7.46→9.32. **Reverted**; live rule files verified byte-identical to `5412a79`. The tell was visible in the symmetric numbers and is F5's lesson again: wins up (10→21) while **kills fell 4→1 and damage dealt 7.71→4.43**. Variant preserved at `experiments/rule_variants/gate1_break_first_EXPERIMENTAL.xml`. **Obvious refinement, untested:** add an own-ATA > 90 condition so the break fires only when the bandit is genuinely behind our 3-9 line, leaving neutral `match_base` fights to the jink. | **[M] rejected** |
| F26-**RULE** | **STANDING RULE: never adopt OR reject a BT change on a symmetric measurement.** Both aircraft read one global rule XML, so any same-tree-both-sides comparison gives both sides the change and systematically inflates it — that is how F16 recorded a null and how the Gate 1 reorder above briefly looked like a large win. The F15 peer rig is the only valid instrument; its docstring's "KNOWN BROKEN BEYOND EPISODE 0" warning was itself wrong and has been removed (commit `3db61be`) — F20 had already refuted it, and it has now been used across full N=30 runs both to confirm F25 and to reject the Gate 1 reorder. | **[M]** |
| F26-**G-CEILING** | **F5 and F12's G findings are REFUTED — there was never a control-law ceiling.** Re-measured post-fix (12 self-play `match_base` episodes, 255k steps): BT pitch saturation **84% → 37.8%**, BT G median **1.16 → 2.06**, BT G p95 from F5's "**never exceeds 3.95** anywhere" to **21.45**. The low G was **an aircraft not manoeuvring** — holding full aft stick while flying a stale aim point from a dead tree, exactly as section G predicted. **F12's decision-relevant claim that the limit "sits downstream of the action, so it would bound an RL policy identically" is wrong and must not be planned around.** G now scales with airspeed sensibly (250–300 KCAS → median 2.01, p95 7.44). Caveats: G maxima (59.98) are finite-difference artifacts of deriving G from velocity history — trust medians/p95; and one narrower effect survives, `vptrack`'s own full-pitch steps still show G median 1.10, but that is 5.5% of steps inside the close terminal envelope, not F12's universal claim. | **[M] refutes F5, F12** |
| F26-**OWED** | **What the re-baseline did NOT cover.** Only `match_base`, `obfm_offensive`, `obfm_defensive` and `two_circle_headon` were re-measured. Still void and un-re-run: **A2** (`Task_GunTrack` range bias — the node had never executed at all, so "UNVALIDATED" was an understatement), **A3** (gun gate ATA<8 vs the 1° scoring criterion — Gate 2.5's guards were never evaluated), **A5** (the 152.4 m floor fix, which never took effect), **C6** (re-merge floor widening, "null" against a Gate 2 that never ran), the **Gate 3 energy thresholds** (comment says "UNTESTED on this box" — literally true, Gate 3 never ran), and the **`Task_Notch` HCA<150 carve-out** (F17/F19, measured against a dead Gate 1). **B1 and B2 remain VALID** — uniquely, because `Gate0_ClimbToSafeAltitude` was one of the only two nodes that ever executed. **Also owed and higher-value than any of those:** the champion controller envelope (2500 m/45°/throttle-off, F2-CHAMPION) was tuned by sweep against a tree flying a stale aim point, and it is what ships — there is no reason to assume it is still optimal. Re-sweeping is ~8 × N=30. | **[D] owed** |

| F27 | **CORRECTS F9/P8's framing: `SERVER_IP` is not a "which of two values" question — the organizers have not released an address yet, and every candidate value on record is a team member's own personal machine (2026-08-13).** F9 and every doc before it treated `221.151.77.208` vs `10.185.16.247` as two candidates to reconcile. **Confirmed directly with the team: neither is official. Both, plus a third value found this session, are personal IPs used for ad-hoc practice connections between team members' own machines, not a released competition or practice server.** Do not spend effort trying to determine "which one is right" — there is currently no right answer, and none is owed until an organizer announcement. Also found while investigating: `startup_command.txt`'s git history (`git log --follow -p`) shows the only two real connectivity-test commands ever recorded both used **`--server-port 6666`**, not the `9999` hardcoded in `my_submission.py`/`run_unreal_inference.py` — 2026-07-28 baseline used `10.185.16.247:6666`, updated 2026-08-06 (`2cee131`) to `172.30.1.49:6666`. **`COMPETITION_RULES.md` never states a port number at all**, so `9999` has no anchor in the official rules either — it may be an unverified template default. Not confirmed as the correct port; flagged so it isn't missed when the real announcement lands. **Action, once the organizers publish a real address:** confirm both IP and port together, don't assume 9999 carries over from any personal-IP test. | **[D]** |

| F28 | **F26-OWED closed out: four pre-F25 verdicts re-measured against a tree that actually runs (2026-08-13).** Each tested as an isolated threshold change on our own side vs a peer running the unmodified F25-baseline tree, N=30, `match_base`, vptrack both sides. Baseline for comparison (symmetric F25-only control, F26-WORTH): **9W/14D/7L**, damage 5.82/7.46, WEZ 770. Every variant reverted immediately after its own run; the live tree was never left in a modified state (confirmed: `git diff HEAD` on both rule files empty throughout). | |
| F28-**A3** | Gun gate ATA 8°→2° (`Gun_OwnATA_Lt8`): **7W/14D/9L**, 5.16/7.72, WEZ 645. Worse, within 1 SE (±8.4% at N=30). **Confirms A3's original conclusion — tightening doesn't help** — now measured on a tree where Gate 2.5 actually evaluates the guard, not inferred against a dead one. Mechanism: a narrower window gives less dwell time to consolidate before a higher-priority branch can preempt. No change. | **[M] confirms A3** |
| F28-**C6** | Re-merge floor 3000m→950m (`Gate2_Remerge_DistGt3000`): **8W/14D/8L**, 5.43/7.87, WEZ 690. Statistically indistinguishable from baseline. **Confirms C6's original "null" verdict**, now on a live tree. No change. | **[M] confirms C6** |
| F28-**GATE3** | Energy-superior threshold 1.4→1.2 (reverting the 2026-08-01 raise, `Gate3_Ratio_Gt1_4`): **10W/11D/9L**, 7.61/9.25, WEZ 949 (+23%). Win rate flat, but **draws fell 14→11** and both damage figures rose together — a more decisive fight, not a clearly favourable one (losses rose with wins). Not adopted; the draw reduction is worth a second seed before acting on, since draws not qualifying (제1안) makes this the one result here with a plausible upside that a single N=30 can't confirm. | **[M] inconclusive, retest before acting** |
| F28-**NOTCH** | Removing the `Task_Notch` HCA<150 carve-out entirely (bare `Task_Notch`, the pre-F17-fix state): **5W/17D/8L**, 3.84/3.65, WEZ 1135 (highest of all four tests). Win rate 30%→17% (~1.6 SE — borderline, not proven, but the largest and most internally consistent delta measured). WEZ up while damage dealt fell by a third reads as more inconclusive close-in contact, fewer clean shots. **Recommend keeping the carve-out** — do not remove it. | **[M] recommend against removal** |

### G. BFM doctrine ↔ implemented tree, and what to expect after the F25 fix (2026-08-11)

Added because F25 established that **none of the tactical layer has ever executed**, so the
post-fix re-baseline has no prior art to compare against — every BT number in this register was
produced by a tree that ran two leaf tasks. Doctrine-linked expectations are the only thing left
to check the first live run against. Source: a BFM/manoeuvring reference supplied by the team;
mapping verified against the 23 `Task_*` classes on disk.

**The tree is a near one-to-one implementation of standard BFM doctrine.** Whoever built it worked
from this material:

| Doctrine | Implemented class | Ever executed? |
|---|---|---|
| High Yo-Yo / Low Yo-Yo | `Task_HighYoYoUp`, `Task_LowYoYo` | **no** |
| Flat / Rolling / Vertical Scissors | `Task_FlatScissors`, `Task_RollingScissors`, `Task_VerticalScissors` | **no** |
| Lag Displacement Roll | `Task_LagDisplacementRoll` | **no** |
| Break Turn | `Task_Evade` (name kept for history) | **no** |
| Guns Defense / Jink | `Task_JinkingTurn` | **no** |
| Notch | `Task_Notch` | **no** |
| Lead / Pure / Lag pursuit | `Task_LeadPursuit`, `Task_pure`, `Task_LagPursuit` | **no** |
| One-circle / two-circle flow | `Task_OneCircleFight`, `Task_NoseToNoseTurn`, `Task_NoseToTailTurn` | **no** |
| Turn-circle entry | `Task_LeadTurn`, `Task_BarrelRollAttack` | **no** |
| Energy vs. nose position | `Task_EnergyTactics`, `Task_AnglesTactics` | **no** |
| Gun tracking | `Task_GunTrack` | **no** |
| (survival / tail default) | `Task_ClimbToSafeAltitude`, `Task_SingleSideOffset` | **YES — the only two** |

**RATE BAND — the sharpest doctrinal check available.** Doctrine puts maximum *sustained* turn
rate at **430 KCAS with a 400–460 band**, and frames the two failure modes as "excessive speed
prevents tight turns; insufficient speed prevents turning entirely". `scripts/corner_speed_probe.py`
measured us spawning at **388.8 kt and decaying to 339.6 kt average**, inside the band only
**7.3 %** of the match. By this doctrine we fight permanently below the rate band, which is the
same conclusion `scripts/turn_rate_sweep.py` reached from load factor.

**CORRECTS F12.** F12 concluded the ~1.2 G ceiling "sits downstream of the action and would bound
an RL policy identically". That measurement pooled all steps, and **88–94 % of them were BT-flown,
i.e. flying a stale aim point from a tree that never ran a maneuver task** — low G there is not a
control-law limit, it is an aircraft not manoeuvring. The vptrack-flown steps still showed ~1.2 G
at saturated pitch, so a real effect remains, but **the headline figure is contaminated and F12
must be re-measured after F25 lands.**

**REFRAMES F14.** `defensive_break` measured harmful (9W/5L → 6W/10L; kills 6 → 3; damage dealt
and taken both down ~42 %). Doctrine explains the result rather than contradicting it: Jink,
Reversal, Ditch and Radius Defense are responses to **a specific weapon employment**, keyed to
indicators such as "the attacker becomes thinner — they are pulling lead for guns". We tested an
**unconditional** break, which by this doctrine is just bleeding energy for nothing. So the honest
reading is not "the defensive axis is closed" but "we tested the wrong form of it" — and the
conditional form lives in `Task_JinkingTurn` / `Task_Evade`, inside Gate 1, which has never run.

**TRANSFER CAVEAT — do not hard-code these numbers.** The reference is **F/A-18C in DCS**; this
sim is a JSBSim F-16. `corner_speed_probe` already tested an F-16 corner figure and found forcing
it **harmful**: 73.1 % win rate but **0 kills and 0.63 damage**, against the champion's 8 kills /
14.29. Its own note stands — "this JSBSim model's rate may peak near where it already settles".
The *concepts* (rate band, exclusive turning room, flow-type choice, energy vs. nose position)
transfer; the *speeds* are hypotheses to measure. That verdict was also reached with the tactical
layer dead, so it is due a re-run regardless.

**What to check on the first live run**, in order: (1) do maneuver tasks appear in the gate trace
at all, and which; (2) does flow-type selection match the geometry — two-circle on a rate fight,
one-circle on a radius fight; (3) does average airspeed move toward the rate band once
`Task_EnergyTactics` can actually run; (4) only then re-measure F12's G ceiling and F14's
defensive question.

### The through-line

A4 and C1 are the same problem from two sides: the tree optimizes toward a **proxy** (ATA < 8°,
dist < 2000 m) rather than the **scoring condition** (LOS < 1°, 500–3000 ft with a range gradient).
C3 says the BT alone cannot close it. D1 says the rules permit replacing the component that can't.
E1 says none of it can be verified yet.

**Agreed work order (2026-08-05): E1 → D3 wiring check → D1/D3 residual hybrid**, with
**A2 / A5 / B1 / B2** taken opportunistically as cheap XML-and-constants wins that need no
rebuild-plus-validation cycle.

**Update 2026-08-06 — the through-line above is now broken in the right place, and the work
order is spent.** D1 was executed (D1-DONE) and it resolved A4/C1/C3 in one move: the tree no
longer has to converge inside a proxy, because the component that could not point has been
replaced. 12/30 wins, 30/30 WEZ contact, from 0/30 on both counts. E1's bifurcation is *not*
fixed — the JSBSim reset nondeterminism is still there and single-episode comparisons are still
invalid — but it no longer blocks validation, because the effect size (0 → 40% win rate) is
~4.5 SE and does not need a coin-flip-free harness to be legible. **Revised order: (1) hybrid
residual re-based on the new floor (D3/§3's submission architecture, `hybrid_vptrack`);
(2) the DQ-avoidance workstream in §8, which has never been started and is now the largest
un-mitigated risk to a podium result; (3) a v7 campaign only if (1) shows the residual adds
something the fixed floor does not — with telemetry (E2) now live, a v7 would be the first
campaign that can actually be steered.** A2's range bias remains **unvalidated and probably
inert** — every 2026-08-06 probe pins `ep_min_distance` at 551–561 m against its 220 m target.

## 5. Critical risks to verify *before* investing heavily in training

Both of these are cheap, local, and fast to check — and both would materially change the plan
above if they come back badly. Do them first.

### 5.1 CONFIRMED (2026-07-07): the native BT opponent has no real tactics — it just flies straight

**Verified by running the compiled DLLs directly**: `run_local_dogfight.py --ownship-backend bt
--ownship-bt-dll AIP_BASE.dll --target-backend bt --target-bt-dll AIP_BASE_target.dll
--max-engage-time 90 --save-log`. Result, from the saved Tacview CSVs
(`artifacts/logs/2026_7_7_22_11_1_*.csv`):

- The two aircraft merge head-on at ~t=8s (as expected from the ~5km separation / ~600 m/s
  closure), then **both continue on essentially their original headings for the remaining 77s**
  instead of turning back to re-engage. Sampled yaw every 5s: ownship drifts `0.0° → 13.9°`,
  target drifts `180.0° → 173.4°` — a slow, smooth, monotonic drift, not a deliberate turn.
- **Zero damage dealt by either side** over the full 90s
  (`artifacts/logs/2026_7_7_22_11_1_summary.json`: `ownship_health: 1.0`, `target_health: 1.0`,
  `end_condition: "max time out"`).

This matches exactly what the `Task_Empty`/`Task_pure` stub source would produce — both shipped
rule files (`Rule.xml`, `Rule_forTraining.xml`) route every branch to one of these, and
`Task_pure.cpp`'s body is a byte-identical copy of `Task_Empty.cpp` (both just set a virtual aim
point 10,000 units straight ahead of the current heading, every tick, forever). **Both compiled
DLLs (`AIP_BASE.dll` and `AIP_BASE_target.dll`) behave this way — this is not just a
source-tree gap, the binaries actually loaded at runtime confirm it.**

**Consequence for the confirmed strategy (§2, §3): there is currently no BT floor.** Residual RL
on top of this BT would be carrying ~100% of the tactical load — "Hybrid" in name only, since
`BT_action` contributes nothing but "keep flying forward." Pure `MODE="bt"` is not a viable
competitive fallback either, as-is: it would lose to any opponent with even minimal pursuit logic.

- [x] Verified: compiled BT DLLs have no tracking/pursuit/attack behavior (evidence above).
- [x] **Decision (2026-07-07): restore real BT tactics in C++ first**, before investing heavily
      in RL training. Team has some (not expert) C++ experience — see the scoped plan below,
      chosen specifically to keep first-step risk low.

#### 5.1.1 Good news: the fix is much smaller than "implement a flight controller"

Traced the control pipeline in `AIP_DCS/BehaviorTree/CPPBehaviorTree.cpp`
(`RunCPPBT()`/`UCPPBehaviorTree::Step`, around lines 110–216) to find out how much a Task node
actually has to compute. Answer: **not much.**

- Every BT tick, `RunCPPBT()` calls `tree.tickRoot()`, then reads `BB->VP_Cartesian` (a 3D "aim
  point") and passes it to `Controller.GetStick(MyLocation, MyRotation, VP)` — an existing,
  already-working low-level guidance controller (`Geometry/Controller_CY.cpp`) that converts
  "here I am, here's where I want to point" into actual roll/pitch/rudder stick commands. **Task
  nodes never need to compute stick/control values themselves** — they only need to set a
  meaningful aim point.
- `Task_Empty`/`Task_pure`'s entire bug is one line:
  `VP_Cartesian = MyLocation_Cartesian + MyForwardVector * 10000` — aim 10,000 units ahead of
  current heading, ignoring the target entirely. `SelectTarget` (already working) has already
  populated `BB->TargetLocaion_Cartesian` with the real target position every tick.
- **A minimal real pursuit fix is close to a one-line change**: set
  `VP_Cartesian = TargetLocaion_Cartesian` (pure pursuit — aim straight at the target's current
  position) instead of the fixed forward point. That alone should produce visibly different,
  verifiable behavior in the same local test used above.
- Separately, **throttle is hard-coded and disconnected from the BT entirely**:
  `RunCPPBT()` sets `Throttle = 1.0f` directly with a comment reading (translated) "throttle
  placeholder — plug in the AI's value here." `CPPBlackBoard` does have a `float Throttle`
  field, but nothing currently sets it from a Task node, and `RunCPPBT()` doesn't read it either
  — it's two small, separate wiring gaps (one in a new/edited Task node, one in
  `CPPBehaviorTree.cpp` itself), not required for the first pursuit-tracking milestone.
- Also confirmed while reading the Decorators: **`DECO_BFMCheck` is dead code today** — it
  compares `BB->BFM` against `OBFM`/`DBFM`/`HABFM`/etc., but nothing in the current source ever
  assigns `BB->BFM` away from its default `NONE` (no BFM-situation classifier exists yet). Any
  Rule XML branch gated on `CheckBFM` will never fire until one is written.

#### 5.1.2 Step 1 — DONE (2026-07-07): minimal pursuit, verified working

Implemented and verified. What actually happened, vs. the original plan:

- **`Task_pure` was repaired in place instead of adding a new node.** `Task_pure.h`/`.cpp`
  turned out to be dead, uncompiled files (see below) that were clearly *meant* to be a real
  pursuit node (a `registerNodeType<Action::Task_pure>("Task_Pure")` call already existed in
  `CPPBehaviorTree.cpp`) but never finished. Fixed `Task_pure.h`/`.cpp` to declare a real
  `Action::Task_pure` class (was wrongly declaring `Action::Task_Empty` again — a leftover
  copy-paste), implemented `tick()` as `VP_Cartesian = TargetLocaion_Cartesian` (pure pursuit),
  added both files to `AIP_DCS.vcxproj`/`.vcxproj.filters`, and pointed
  `DogFightEnv/Release/Rule_forTraining.xml`'s two branches at `Task_Pure` instead of
  `Task_Empty`.
- **Found two more bugs while getting this to actually build and run:**
  1. The project **did not compile at all** before this fix — `Task_pure.h` redeclaring
     `class Action::Task_Empty` collided with the real `Task_Empty.h` wherever both get
     included together (`TaskNodes.h` includes both). This was a pre-existing break, not
     something introduced here; the shipped `AIP_BASE.dll`/`AIP_BASE_target.dll` must predate it.
  2. **Two complete, separate copies of this whole project exist on this machine** —
     `D:\AIP\AIP_LIB\` (what all of this documentation targets) and
     `C:\Users\User\Desktop\AIP\AIP_LIB\` (apparently untouched). The compiled DLL's Rule XML
     loader had a **hardcoded absolute path** to the Desktop copy
     (`C:\Users\User\Desktop\AIP\AIP_LIB\Rule_forTraining.xml` in
     `CPPBehaviorTree.cpp::init()`), meaning `bt_rule_manager.py`'s `activate_rule_xml()`
     mechanism — and therefore every documented way of swapping in a team-specific Rule XML —
     was silently having **zero effect** on the compiled DLL. Fixed by resolving the path
     relative to the DLL's own on-disk location instead (`GetModuleFileName`-based), which also
     turned out to matter for a second reason: a bare relative path (`"Rule_forTraining.xml"`)
     failed too, because something in the JSBSim init path changes the process's current
     working directory before `CreateBehaviorTree()` runs. The module-relative fix is immune to
     both problems. **The Desktop copy hasn't been touched or deleted — flagging its existence
     for you to decide what to do with it.**
- **Verified via the same 90s BT-vs-BT test as §5.1**: yaw now swings through 100–270° within
  single 5-second samples on both sides (e.g. ownship: `15.9°→126.8°→267.8°→53.8°`), a complete
  change from the pre-fix `0°→14°` passive drift. **Zero damage was still dealt in this run** —
  expected, not a failure: two aircraft running identical pure-pursuit logic against each other
  is known BFM to produce an inefficient tail-chase/circling geometry that doesn't converge to a
  gun solution. That's exactly what Step 2 targets next.
- [x] Step 1 done and verified (evidence above; new logs at
      `artifacts/logs/2026_7_7_22_42_28_*.csv`). Old DLLs backed up to `AIP_BASE.dll.bak` /
      `AIP_BASE_target.dll.bak` in `DogFightEnv/Release/` before overwriting.

#### 5.1.3 Step 2 — DONE (2026-07-07): added lead pursuit, and found the *real* root cause

Added `Task_LeadPursuit` (new node: aims at the target's *predicted* position — current
location plus its velocity times a capped lead time — instead of its current position) and
wired it into `Rule_forTraining.xml`'s `DistanceCheck Greater 2000` branch, keeping the precise
`Task_Pure` (pure pursuit) on the `Less 2000` branch. Registered in `CPPBehaviorTree.cpp`,
added to the vcxproj/filters, same pattern as Step 1.

**First rebuild+retest was suspicious**: identical reward to Step 1 (`-30.4540`, both to 4
decimal places) for the first ~28s, meaning the new `Greater 2000` branch wasn't visibly taking
effect. Diffing the two runs' trajectory CSVs confirmed they were byte-identical until row 1682
— real behavior, not a fluke, but pointing at a deeper bug rather than "the lead pursuit code is
wrong."

**Root cause, traced through `ChangeData()` in `LibMain.cpp` and `Step()` in
`CPPBehaviorTree.cpp`: `BB->Distance` (and every position-derived quantity — `BB->
MyLocation_Cartesian`, `BB->TargetLocaion_Cartesian`, and by extension the AA/LOS calculations
that subtract these) was silently mixing latitude/longitude in **degrees** with altitude in
**meters** in one Euclidean distance formula.** `ChangeData()` packs raw `(lat_deg, lon_deg,
alt_m)` into the `Location` fields with no geodetic conversion. `Step()` *does* properly convert
this to true local Cartesian meters via `LLAtoCartesian()` — but for the **enemy**, that
conversion call was commented out in favor of a raw passthrough, and for **self**, the
properly-converted value was computed into a local variable and then never used — the actual
blackboard assignment used the original, unconverted parameter instead (a `MyInfo`/`Myinfo`
case-only variable name collision). Net effect: `BB->Distance` was a near-meaningless number
dominated by whichever raw component happened to be numerically larger — in practice, mostly the
altitude delta, not true 3D range — so `DistanceCheck Greater 2000` essentially never fired
except when altitude divergence happened to exceed 2000 (raw units), explaining the ~28s partial
match. This bug predates both Step 1 and Step 2 and silently affected `DECO_DistanceCheck`,
`AspectAngleUpdate`, and `CheckSight` (LOS) for as long as the DLL has existed — not something
introduced by this work.

Fixed both sites in `CPPBehaviorTree.cpp`: restored the commented-out `LLAtoCartesian()` call
for the enemy (using the same `OriLAT`/`OriLOn` reference origin as self, so both sides share one
consistent local frame), and pointed the self-side blackboard assignment at the already-computed
converted value instead of the raw parameter.

**Result, same 90s BT-vs-BT test**: `end_condition: target destroyed` at step 2129/5400 (~35s in)
— a real kill, `ownship_health: 0.51`, `target_health: ≤0`, `total_reward: 176.37` (positive,
dominated by the terminal win bonus). This is the first time in this whole investigation the
native BT has dealt any damage at all.

- [x] Step 2 done: `Task_LeadPursuit` added, and the underlying position/distance corruption bug
      (bigger than originally scoped, but a blocking prerequisite) found and fixed. Verified via
      a confirmed kill in the local BT-vs-BT test.
- [x] **Confirmed 2026-07-07, 3 rounds**: two repeats of the same 90s scenario plus one at the
      real competition match length (200s, per `COMPETITION_RULES.md` §5) all produced
      **bit-identical results** — `num_steps=2129`, `total_reward=176.3705`, same health values
      to the exact decimal. Confirms the sim is deterministic here (no hidden randomness in the
      BT logic or reset for this scenario) and the kill is reliably reproducible, not a fluke —
      and that it happens well within the real 200s match length, not just the 90s test window.
      **Caveat**: `run_local_dogfight.py` exposes no seed/scenario-variation flag, so identical
      reruns can't add statistical confidence across *different* geometries — only reproducibility
      of this one. Genuine robustness testing (does this BT still win from other starting
      angles/ranges?) needs varied initial conditions, which the curriculum's own α-sweep stages
      (`two_circle_headon_a000..a180`, see `PROJECT_ANALYSIS.md` §4) will exercise naturally once
      training starts — not necessary to hand-build a separate scenario-variation harness first.
#### 5.1.4 Step 3 — DONE (2026-07-08): throttle, evasion, and an emergent Hard Deck fix

- [x] **Throttle wired up.** `RunCPPBT()` was hardcoding `Throttle = 1.0f` unconditionally,
      completely disconnected from the BT despite `CPPBlackBoard` already having a `float
      Throttle` field (default `0`). Changed it to read `BB->Throttle`; `Task_Pure` now sets
      `0.7` (close range — reduce overshoot risk on tight turns) and `Task_LeadPursuit` sets
      `1.0` (far range — close distance fast).
- [x] **`Task_Evade` added.** Checks `BB->EnemyInSight_Target` itself (returns `FAILURE` if not
      threatened, so the Fallback proceeds to offense); if the enemy has us in front of them, it
      offsets `VP_Cartesian` to extend straight away at full throttle. Wired in above the
      pursuit branches, below Hard Deck avoidance.
- [x] **Unplanned but necessary: `Task_ClimbToSafeAltitude` added.** The first 200s verification
      run (up from the 90s used in Steps 1–2) ended in `end_condition: target altitude below
      min` — the target crashed, not from combat. Checked the altitude trace: a **slow, steady,
      monotonic dive** from ~10,000 m at t=20s to ~300 m at t=160s — not a glitch, a real
      pre-existing gap. This BT (in any version, including the original stub) has **never had
      any altitude-safety logic at all**; it only started mattering once the tree could
      actually turn and dive (Steps 1–2). Since Hard Deck violation is an instant-loss condition
      (`COMPETITION_RULES.md` §5) — strictly worse than any tactical inefficiency — this was
      escalated ahead of general polish rather than left for later. Added as a new node
      (self-checks altitude, `FAILURE`s above 914 m / ~3000 ft so lower-priority branches run;
      below that, aims straight up at full throttle), wired in as the **first** Fallback branch
      (above even evasion — survival before everything else, matching every reference BT
      pattern surveyed earlier in this project). Re-ran the same 200s test: `end_condition: max
      time out`, both aircraft survived at full health, minimum altitude reached was 936 m —
      safely above both the 914 m trigger and the real ~305 m Hard Deck line.
- [ ] Not done (deferred, per original scope): BFM classifier, richer Selector/Fallback tree —
      still polish, not a prerequisite. **Superseded for the maneuvers themselves, see below.**
- [ ] Decide what to do about the Desktop copy (`C:\Users\User\Desktop\AIP\AIP_LIB\`) — leave it,
      sync it, or archive/delete it. Not touched by any of the above.
- [x] Hybrid-residual architecture (§2/§3) is back on solid ground now that there's a real BT
      floor that can actually win engagements *and* survive a full-length match without
      self-inflicted crashes.

#### 5.1.5 BT strategy Q&A (confirmed 2026-07-08)

A fresh BT-vs-BT test against the current (Step 3) build ends in a stalemate — both aircraft
survive at full health, no kill — a real change from Step 2's confirmed, reproducible kill
(before evasion existed). That prompted a deliberate strategy check before committing RL training
compute against this opponent:

| Question | Answer | Implication |
|---|---|---|
| More BT investment before locking it in? | **Restore the missing maneuvers** (`JinkingTurn`, `HighYoYoUp`, `LunchMSL`, `WeaponSelect` — currently only stale `.obj` leftovers, no source) | Not the BFM classifier, not a richer Selector/Fallback tree — those stay deferred as polish. This is the one next BT work item, scoped before curriculum training starts. |
| Freeze the BT before or during RL training? | **Freeze once the maneuvers land** | Lock the DLL as a fixed training opponent/residual base — no moving target once real training starts. Any further BT change after that is a deliberate new version, evaluated for impact, not silent drift. |
| Does the stalemate change confidence in Hybrid residual? | **No — still the plan** | A defensive, non-losing BT is exactly what a safety net should look like; RL's job is to add offense on top, not inherit it. Stalemate floor is a safe floor, not a weak one. |
| Is BT-only (`MODE="bt"`) still a maintained fallback? | **Yes, per the original §3 plan** | Re-validate BT-only (local BT-vs-X test) whenever the BT or Rule XML changes, so it stays submission-ready as insurance independent of RL training outcomes. |

- [x] **Step 4 — DONE (2026-07-08): `Task_JinkingTurn` and `Task_HighYoYoUp` restored, BT
      frozen.** Two research agents first mapped the actual gap and reshaped scope:
  - The orphaned `.obj` files (`JinkingTurn.obj`, `HighYoYoUp.obj`, `LunchMSL.obj`,
    `WeaponSelect.obj`, `JinkingTurnSelector.obj`, plus ~40 more node names) turned out to be from
    a **completely separate, older, abandoned implementation** (different project root
    `D:\AIP_DCS\`, bare naming like `Pure`/`Lead`/`Turn` — not today's `Task_`-prefixed family). No
    logic survives anywhere, only names — "restoration" meant fresh design in the current
    `Task_*` idiom, informed by BFM doctrine, not recovering lost code.
  - **`LunchMSL`/`WeaponSelect` confirmed functionally dead for this competition** — no missile
    mechanic exists anywhere in the scoring/damage/termination/flight-model code
    (`COMPETITION_RULES.md` §4 is guns-only), and even the one piece of DLL↔caller plumbing that
    could carry a launch decision out (`LibMain.cpp::Step()`'s `MSL_Lunch_Possible`/
    `Flare_Lunch_Possible` out-parameters) is declared but never written. **Dropped, not
    implemented.**
  - A separate scope question — `MergeTurn` + 5 merge-check decorators, which look purpose-built
    for the head-on tie-break (`COMPETITION_RULES.md` §7) — was raised and explicitly **deferred**
    as a comparably-sized follow-up, not bundled into this round.
  - Implemented `Task_JinkingTurn` (self-gated on `EnemyInSight_Target` + `Distance < 2000` —
    lateral oscillation via `MyRightVector * sin(RunningTime * freq)` layered on `Task_Evade`'s
    retreat vector, slotted above it in Fallback priority since jinking is for when breaking away
    can't outrun the shot) and `Task_HighYoYoUp` (self-gated on `Distance < 2000` +
    `MySpeed_MS - TargetSpeed_MS` above a crude overtake-risk threshold — the existing
    `Task_LeadPursuit` lead-point formula, pulled up in world altitude via `.Z +=`, mirroring
    `Task_ClimbToSafeAltitude`'s pattern rather than a body-relative up-vector). Both give real
    consumers to `CPPBlackBoard` fields that were computed every tick but previously write-only
    (`MyRightVector`, `RunningTime`, and — via the existing lead-point formula — `MyUpVector` was
    considered but world-Z proved the more robust choice).
  - Clean `AIP_DCS.sln` (Debug|x64) rebuild succeeded with no new errors (only pre-existing-style
    warnings). Deployed to `DogFightEnv/Release/AIP_BASE.dll`/`AIP_BASE_target.dll`, backing up
    the Step 3 DLLs first (`.step3.bak`, alongside the existing `.bak` from before Step 3).
  - **Verified via the same 200s BT-vs-BT local test**: same outcome category as the Step 3
    baseline (`max time out`, both full health, no Hard-Deck violation — no regression), but
    `total_reward` shifted from the exact `-119.9879` seen in every prior run this session to
    `-119.9900`, confirming the new logic is actually being exercised. Trajectory analysis found a
    2.6km altitude excursion during the close-range window (7500m→10177m) — well beyond anything
    the existing pursuit/evade logic could produce on its own — strongly corroborating
    `Task_HighYoYoUp` firing. `Task_JinkingTurn`'s narrower trigger (must be defensively
    threatened, not just close) didn't clearly fire in this particular symmetric matchup, but its
    logic directly mirrors the already-proven `Task_Evade` pattern with one added condition.
  - **BT frozen per the strategy decision above** — superseded same day, see Step 5.

- [x] **Step 5 — DONE (2026-07-08): `Task_OneCircleFight` and `Task_LagPursuit` added, BT
      re-frozen.** Prompted by mining the `ai-combat-sdk-main` reference catalog (a separate
      project, see [[project-aip-tgc-2026-scope]]) for tactical patterns missing from AIP_DCS,
      then re-implementing them fresh as `Task_*` C++ nodes — not porting ai-combat-sdk-main's own
      code or rules, which don't apply here.
  - `Task_OneCircleFight`: self-gated on `Distance < 2000 && Los_Degree > 45°` — a merged,
    off-boresight turning fight, not a clean pursuit setup. Aims at the target's current position
    (not a lead point — over-leading causes overshoot in a tight turn) with throttle cut to 0.5
    (tighter than `Task_Pure`'s 0.7): minimizing speed is the actual mechanism that shrinks turn
    radius and wins a one-circle fight.
  - `Task_LagPursuit`: the complementary case, self-gated on `Distance < 2000 && Los_Degree < 20°`
    — already tracking well, so aim *behind* the target's predicted point (exact mirror of
    `Task_LeadPursuit`'s formula, subtracting instead of adding the motion offset) to avoid
    closing too fast and overshooting.
  - **Correctness note found while implementing**: `MyAngleOff_Degree` (written by
    `AngleOffUpdate.cpp`) is HCA (heading crossing angle between the two nose vectors), not ATA —
    confirmed by reading its source rather than trusting the field name. True ATA (angle between
    ownship's own nose and the LOS to the target) is `Los_Degree`, computed in `CheckSight.cpp`
    via `acos(ForwardVector · LOS_unit_vector)` — already non-negative by construction, no `abs()`
    needed. Both new nodes gate on `Los_Degree`, not `MyAngleOff_Degree`.
  - Deployed after a clean rebuild, backing up the Step 4 DLLs first (`.round1.bak`).
  - **Verification found the single fixed BT-vs-BT test scenario has real blind spots**: the
    initial 200s run produced a reward bit-identical to Step 4's, at first appearing to mean the
    new nodes never fired. A direct ATA computation from the trajectory showed `Task_OneCircleFight`'s
    trigger condition was actually satisfied in ~91% of close-range samples — so a targeted
    diagnostic (temporarily removing `Task_JinkingTurn`/`Task_Evade`, which sit above the new nodes
    and share the broad, easily-satisfied `EnemyInSight_Target` gate) confirmed the real cause: outranked,
    not unreachable. With them removed, the outcome changed completely — a confirmed kill
    (`total_reward: 263.94`, real health loss both sides) instead of the usual stalemate — proving
    `Task_OneCircleFight`/`Task_LagPursuit` are reachable and functionally significant. This also
    retroactively confirms Step 4's `Task_JinkingTurn` was very likely firing substantially in this
    same scenario too (its yaw-oscillation signature just wasn't detected by that round's simpler
    check) — correcting Step 4's "didn't clearly fire" note above. Restored the real Fallback order
    and re-verified it matches the expected baseline exactly before treating this as done.
  - Explicitly deferred again this round: the BFM classifier (bigger, more architecturally
    invasive — would restructure how the tree branches, not just add a leaf) and `MergeTurn` +
    merge-check decorators (from the same catalog, a comparably-sized follow-up).
  - **BT re-frozen**: `AIP_BASE.dll`/`AIP_BASE_target.dll` are the fixed curriculum-training
    opponent again. Fallback order end-to-end: `ClimbToSafeAltitude → JinkingTurn → Evade →
    HighYoYoUp → OneCircleFight → LagPursuit → [dist>2000: LeadPursuit] → [dist<2000: Pure]`.

#### 5.1.6 BT tactics expansion — DONE (Batches A–D, 2026-07-08 → 2026-07-11)

The maneuvers Steps 4–5 explicitly deferred (BFM-adjacent tactics, `MergeTurn` + merge decorators,
Scissors family) were designed and implemented as a full round, converting a BFM tactics reference
(`AERIAL_COMBAT_BT_GUIDE_DETAILED.md`) into ~20 concrete `Task_*` nodes. Scope was confirmed with
the user up front (all ~20 maneuvers, not a subset). Approved plan lives at
`~/.claude/plans/i-have-aerial-combat-bt-guide-detailed-m-serene-duckling.md`; batch-by-batch
file-level state is in `PROJECT_STRUCTURE.md`'s current-state log and `CLAUDE.md`'s node list.

- [x] **The flat 8-branch tree is now a 5-gate nested `Fallback`** (`Rule_forTraining.xml`):
      Gate 0 survival (`ClimbToSafeAltitude`, untouched top priority) → Gate 1 immediate threat
      (`Notch → JinkingTurn → TheBreak`) → Gate 2 merge & neutral-fight detection
      (head-on merge → `NoseToNoseTurn`; off-center → `LeadTurn`; sustained close-in neutral →
      Scissors family) → Gate 3 energy-ratio guard (offense only) → Gate 4 offensive selector →
      Tail pursuit fallback. Priority order of the pre-existing safety/defensive branches was
      preserved.
- [x] **Batch A** — `EnergyStateUpdate` service (`Es`/`EnergyRatio` for both aircraft each tick) +
      6 shared decorators (`DECO_AspectAngleCheck`/`AltitudeCheck`/`SpeedCheck`/`EnergyRatioCheck`/
      `ClosureRateCheck`, plus revived `LOSCheck`/`AngleOffCheck`); `Task_Notch`,
      `Task_FlatScissors`, `Task_AnglesTactics`, `Task_EnergyTactics`.
- [x] **Batch B** — `Task_Evade` reimplemented in place as "The Break" (phased break-turn),
      `Task_HighYoYoUp` refined, `Task_LowYoYo`, `Task_VerticalScissors`, `Task_RollingScissors`,
      `Task_NoseToTailTurn`. A `Task_VerticalScissors` runaway-dive bug (re-claiming the same
      geometry back-to-back into a net descent) was found by bisection testing and fixed with a
      release cooldown.
- [x] **Batch C** — Gate 2 merge handling: `Task_NoseToNoseTurn` (also the Finals head-on
      tie-break handler, §4 row 4) + `Task_LeadTurn` + the merge-check decorator Sequences. This is
      the `MergeTurn` follow-up Step 5 earmarked — built as decorator-driven guard Sequences, not a
      standalone node, matching the tree's existing idiom.
- [x] **Batch D (2026-07-10/11)** — `Task_BarrelRollAttack`, `Task_LagDisplacementRoll`,
      `Task_SingleSideOffset`. Reviewed by an adversarial multi-agent pass (4 lenses + independent
      verification) before landing; it caught one real bug — `Task_SingleSideOffset` lacked the
      unconditional time-cap release its Gate-4 siblings have, so it could monopolize its Fallback
      slot against an opponent that never let range close under 2000 m — fixed with a 15 s cap,
      rebuilt clean.
- [x] **Hard `SyncActionNode` constraint respected throughout**: every node returns `SUCCESS`/
      `FAILURE`, never `RUNNING` (verified against `action_node.cpp` — `SyncActionNode` throws on
      `RUNNING`). Multi-second phased maneuvers track elapsed time via a blackboard-timestamp
      pattern (`ClaimManeuverPhase`/`ReleaseManeuverPhase` in `Functions.h`) instead.
- [!] **ROOT CAUSE OF THE 0-WEZ SYMPTOM, FOUND 2026-08-05 — the BT's gun gate is 8× looser than
      the env's actual scoring criterion.** `envs/observation.py:193` scores WEZ as
      `ata_abs <= wez_config["angle_deg"]/2.0` with `angle_deg=2.0` (`config.py:37`) — i.e. **ATA
      ≤ 1.0°**. Gate 2.5's `Gun_OwnATA_Lt8` admits **ATA < 8°**. Range is fine (gate 150–914 m vs
      WEZ 152.4–914.4 m); the **angle** is the whole problem. Measured, not inferred, on a fresh
      Debug|x64 build over 20 BT-vs-BT episodes:
      - `two_circle_headon` (10 eps): 10/10 timeout, 0 WEZ. Range-band and alignment are cleanly
        **disjoint** — in-band steps never go below **15.0°** ATA; aligned steps (<8°) never come
        closer than **1253 m**. Gate 2.5 therefore never ticked at all in that scenario.
      - `obfm_offensive` (10 eps, starts ~556 m on the six at ~4.6° ATA): 10/10 timeout, 0 WEZ —
        but here Gate 2.5 **did** fire, for exactly the 100 steps that satisfied its gate.
        `Task_GunTrack` held the track as designed and still scored nothing, because it held at
        ~4.5° ATA (episode min 3.4°) against a 1.0° requirement.
      **This means the 2026-08-05 widening of `Gun_OwnATA_Lt8` from 5°→8° moved the wrong way**:
      its stated rationale was more dwell to "grind ATA toward the 1.0-deg WEZ", but the trace
      shows the node latches and *holds* whatever alignment it entered with rather than converging
      to 1°, so widening only lets it settle on a definitively non-scoring line. Repro:
      `python scripts/eval_v5_vs_bt.py --ownship-backend bt --target-backend bt --scenario-mode obfm_offensive --episodes 10 --episode-step-limit 12000 --trace-geometry`

      **Two further fixes were then tried and BOTH FAILED to produce WEZ contact — record them so
      nobody re-runs them:**
      1. *Tighten the gate* `Gun_OwnATA_Lt8` 8° → 2° (XML-only, isolated copy under
         `Release/bt_probe/`). Result: still 0 WEZ in both scenarios, because **the BT never
         reaches ATA ≤ 2° at all** when close — the gate threshold was never the binding
         constraint. Tightening only made Gate 2.5 unreachable and pushed 1600 more steps into
         `Gate1_threat`. Not applied to the live XML.
      2. *Fix a real integral bug in* `Controller_CY::GetLOSErrorSUM` (**applied, kept**): the
         constructor pre-fills `ErrorSum` with 60 zeros, then the function `push_back`-ed 59 MORE
         before switching to cyclic writes — the buffer grew to **119**, indices 60–118 froze with
         first-second samples forever, and the sum over all 119 was divided by **60**. That is a
         permanent ≈4.5 constant bias in the OBFM start geometry. Genuinely wrong and now fixed
         (cyclic write from call 1, divide by true size, `ERROR_SUM_WINDOW` constant). **But it
         did not fix 0-WEZ**: the only consumer is
         `clamp(GetLOSErrorSUM(LOS)/7.5, 0, 0.25)`, which saturates for any error above ~1.875°,
         so at a ~4° residual the frozen-bias version and the correct rolling mean emit the same
         clamped 0.25. Kept as a strict correctness fix (same rationale as the int→float fix
         above), **not** as a validated performance win — measured A/B was mixed: OBFM ATA-min
         3.40°→4.15°, ATA-p1 7.51°→5.49°, WEZ 0→0.

      **THE EVAL HARNESS IS NONDETERMINISTIC — read this before trusting ANY A/B in this file.**
      Discovered 2026-08-05 while sweeping the integral cap. Byte-identical DLL, identical
      `--seed 0`, identical `--episodes 4`, two consecutive runs of `eval_v5_vs_bt.py` produced
      episode-0 ATA minima of **1.033°** and **4.403°** — a 4× spread on identical inputs, far
      larger than any effect being measured. Repro:
      `for i in 1 2; do python scripts/eval_v5_vs_bt.py --ownship-backend bt --target-backend fixed --ownship-bt-dll <dll> --scenario-mode obfm_offensive --episodes 4 --seed 0 --trace-geometry --trace-out t$i.csv; done`
      then compare `min(own_ata)` across `t1.csv`/`t2.csv`.
      **Consequence**: every control-gain A/B decision in this project's history — the 0.25→0.6
      widening and its revert, the int→float truncation assessment, and the sweep above — was
      measured on this harness and must be treated as **unproven**, not as evidence. This very
      plausibly explains the confusing "fix helps / fix doesn't help / revert" history around
      `Controller_CY`. Prime suspects: `StickController` state surviving across episodes
      (`SumCount`/`ErrorSum`/`MF[]`/`FilterIndex` are per-instance and nothing resets them between
      episodes — `LibMain::Reset()` clears the BT map but not these), and/or JSBSim re-init
      nondeterminism. **Fixing harness repeatability is now the highest-value next task**: no
      tuning work here can be validated until it is done.

      **What IS robust** (held across ~12 separate runs, every configuration tried): **0 WEZ
      contact, always** — BT-vs-BT mirror, BT-vs-BT with a tightened gate, and critically
      **BT vs a NON-MANEUVERING target**. That last one matters: it rules out "mirror stalemate is
      expected" (§9 below) as the explanation, because a target that never defends should be
      trivially convertible. Something in our own tracking/geometry pipeline cannot close the last
      ~1° — but the *shape* of that failure could not be characterised, because of the harness
      nondeterminism above.

      **Also found, NOT fixed** (same int-truncation class, in `GetStick`'s rudder path):
      `int MFsum = 0; for(...) MFsum += MF[i]; RudderCMD = (MFsum/20 + RudderCMD)/2;` — `MF[]` is
      `float[20]`, so each add truncates, and `MFsum/20` is integer division that yields 0 for any
      |sum| < 20. The rudder moving-average filter is therefore inert and the line just halves
      rudder authority. Left alone deliberately: unlike the two above it would change control
      behavior, and there is no validated baseline to change it against yet.
- [x] **BFM classifier (`DECO_BFMCheck`) stays dead**, per the standing decision — new maneuvers
      get concrete per-node Decorator guards, not a situational classifier. (Note: the
      HABFM/OBFM/DBFM names *do* reappear at the match-spawn layer — §4 row 6 — but that's the
      viewer positioning aircraft at t=0, unrelated to reviving the in-BT classifier.)
      **Decision re-affirmed 2026-08-05** after a full re-read of the tree: a classifier would be a
      second source of truth able to disagree with the per-node gates it sits above, so the
      rationale holds. But auditing it turned up that the node was dead *and fail-OPEN* — its
      unrecognized-string branch returned `NONE`, the permanent value of `BB->BFM`, so a **typo'd**
      `CheckBFM` returned SUCCESS while a correctly-spelled one returned FAILURE. Fixed with a
      `BFM_Unknown` sentinel so it fails closed; the node stays dead, the trap is gone. Source-only
      — **requires a DLL rebuild to take effect**. See `CLAUDE.md`'s Decorator bullet for detail.
- [x] **Aspect-angle sign trap documented**: the native BT's `MyAspectAngle_Degree` (180° = six
      o'clock) and the Python side's `GeoMathUtil._get_aspect_angle` (0° = six o'clock) use
      *opposite* conventions — the two halves of the codebase disagree. Recorded in `CLAUDE.md` so
      future work verifies against the source it's actually reading, not the field name.
- [x] **Resolved 2026-07-11**: `AIP_BASE.dll`/`AIP_BASE_target.dll` were re-dropped from the
      Batch-D build (Batch-A-C DLLs kept as `.batchC.bak`), and **curriculum has since been
      restarted (`v2`→`v3`) against the upgraded tree** — see §9. A 20-episode `eval_matchup.py`
      BT-vs-BT sweep (alpha 0–180°, post-Batch-D tree, §8) confirmed the symmetric-standoff pattern
      quantitatively: 20/20 timeout, 0 WEZ-contact episodes, but real close-in engagement (range
      down to 270–511 m, ATA down to 0.1–1.0°) — the tree fights hard, it just can't convert a
      mirror-identical merge into a kill. Assessed as expected behavior for symmetric self-play
      against a defensively-competent BT, not a bug — the RL side isn't mirror-identical to the BT
      so it can create the asymmetry a gun solution needs, and real opponents won't be mirror
      copies either.

### 5.2 Unreal-side state completeness — CONFIRMED (2026-07-08), no live server needed

Resolved by static analysis of `protocol.py` + `policies.py` + `client.py` — a captured packet
log from `logs/unreal_packets/` gave the ground-truth wire bytes to check the struct definition
against, so no live/practice server connection was needed (deliberately avoided one, given no
confirmation either server is currently up, and connecting is the kind of network action worth
being conservative about).

**Confirmed: `StateIndex.HEALTH` (45), `ALT` (44), `KCAS` (12), and `FUEL` (23) are permanently
`0.0` throughout every live Unreal match — this isn't a maybe, it's structural:**

1. `PLANE_INFO_STRUCT = struct.Struct("<iQb3f3f3f")` in `protocol.py` — 49 bytes, matching every
   captured `MT_PlaneInfo` packet's `size_bytes` exactly. The `PlaneInfo` dataclass has exactly
   three fields: `position`, `rotation`, `velocity`. **There is no health or fuel field
   anywhere in the wire message.**
2. `MT_Damage = 3` exists as a message-type ID in the protocol enum, but has **no struct
   definition and no handler anywhere** — grepped `client.py`'s four `_handle_*` methods
   (`_handle_set_plane_id`, `_handle_init`, `_handle_game_control`, `_handle_plane_info`); no
   `_handle_damage` exists. If the server ever sends `MT_Damage`, this client silently ignores it.
3. `plane_info_to_state()` (`policies.py`) allocates a 51-zero array and writes indices 0–8
   (position ×3, rotation ×3, velocity ×3) — full stop, no further computation, no fallback.
4. `_build_tactical16()` (`observation.py` lines 170–186) reads `state[StateIndex.KCAS]`,
   `state[StateIndex.ALT]`, `state[StateIndex.HEALTH]` (×2, ownship+target) **directly from
   those dedicated indices** — not derived from the always-populated position/velocity fields.
   So it's not just HEALTH/FUEL that break; **ownship speed and ownship altitude break too**,
   even though position.z and velocity are physically present in every packet — they're just
   never copied into the `ALT`/`KCAS` slots specifically.

**Net effect: 4 of `tactical16`'s 16 observation features (indices 3, 4, 5, 13 — ownship speed,
ownship altitude, ownship health, target health) are live and meaningful during JSBSim training,
and permanently zero during every live competition match.** A policy trained to rely on these
signals will see a real, severe distribution shift the moment it goes live — invisible in
`run_local_dogfight.py`, which always runs through JSBSim and never touches this code path.

**Reframing worth noting**: this may not be a "bug to patch" so much as a genuine limitation of
what the wire protocol provides. `COMPETITION_RULES.md` §4's own description of "Perfect State
Information" says your AI receives the opponent's "position/attitude/speed" — it does **not**
mention health. The wire format matches that description exactly (position/rotation/velocity
only). Health telemetry may simply never be part of what the real server sends, by design.

- [x] Confirmed via static protocol/code analysis — no live connection attempted.
- [x] **Decided and implemented 2026-07-08**: `student/my_observation.py` is now a real
      tactical16-equivalent (14-D, was an 8-D toy example) — derives ownship speed from
      `norm(state[6:9])` (velocity; frame differs training-vs-live but magnitude doesn't) and
      altitude from `-state[D]`, both correct in training and live; drops ownship/target health
      entirely (no live source, no fake constant) rather than leaving them meaningful-in-training/
      always-zero-live. `compute_reward()` still reads real `HEALTH` for terminal win/loss logic —
      that's sim-engine state, not the wire-limited policy-input observation, so it's unaffected.

## 6. Reward design plan

`student/my_reward.py` is currently just `step_penalty + terminal` (win/loss/draw). Start from
the reference reward anatomy already used for the (placeholder) `student_sac_baseline` run,
recorded in `artifacts/records/real_eagle/student_sac_baseline/training_record.md`:

```
step_penalty: -0.01        damage_scale: 20.0           pursuit_scale: 0.3
pursuit_half_angle_deg: 30  pursuit_range_m: 3000        low_altitude_penalty: 0.1
win_reward: 100            loss_reward: -100            draw_reward: -30
```

- [x] Done 2026-07-08: ported (survival + step + pursuit + damage + safety + terminal +
      guard_fail) into `student/my_reward.py`.
- [x] Recalibration against §4 landed at the source instead of in reward.py: phase-aware WEZ
      coefficients live in `update_damage()`, so `compute_reward()`'s `damage` term automatically
      sees the already-discounted differential — no reward-side change needed. 200s pacing is a
      `full_dogfight`-stage property (§4 item 1), independent of reward code.
- [x] Added ATA+AA together: a new `position` component (AA-based, mirrors `pursuit`'s ATA-based
      gradient) so pursuit+position only both peak when nose-on *and* behind them — not on a
      fleeting head-on pass. **Found and fixed a real bug while verifying this**: GeoMathUtil's 3D
      aspect-angle mode (`proj=False`) has a matrix singularity exactly at 180° (head-on) that
      silently returns 0° instead of 180° — confirmed empirically (own_yaw/tgt_yaw sweep), would
      have made `position` (and the built-in `tactical16`/`relative14` AA feature, which had the
      same bug) blind to exactly the geometry it exists to catch. Fixed by using `proj=True` (2D,
      no singularity, matches `single_agent_env.py`'s own `final_aa_deg` convention) in
      `student/my_reward.py`, `student/my_observation.py`, and — since no trained policy exists
      yet to be affected by the behavior change — the built-in `src/dogfight/envs/observation.py`
      too (`_build_relative14`/`_build_tactical16`). Verified via scripted checks, not just
      inline reasoning.
- [x] **Found & fixed 2026-07-10: the `position` term was silently inert for all of stage 0–8
      training.** `position_scale`/`position_half_angle_deg` were defined only in
      `MY_REWARD_CONFIG`, never mirrored into `DEFAULT_ENV_CONFIG["reward"]` — and
      `train_curriculum.py`'s `env_creator()` does `cfg.setdefault("reward", reward_config)`, a
      no-op whenever `"reward"` is already present (always true, since `build_stage_env_config()`
      starts from a `DEFAULT_ENV_CONFIG` copy). So the keys never reached `compute_reward()`, and
      `my_reward.py`'s own `.get("position_scale", 0.0)` fallback zeroed the term. The
      aspect-angle-singularity fix above was, in effect, fixing a term that wasn't contributing to
      the trained policy. Fixed by adding the keys to `DEFAULT_ENV_CONFIG["reward"]`; verified
      end-to-end by reproducing `env_creator`'s merge against real curriculum stages. **This is a
      material input to the §9 resume-vs-restart decision** — stages 0–8 trained without positional
      shaping actually active.
- [x] **New `student/reward_lib.py` (2026-07-10, trimmed 2026-07-11)** — SI-unit-corrected port of
      an external BFM/ACM reward reference (`D:\AIP\reward_function_skeleton.py`), aspect-angle
      sign fixed to this project's convention. Only `positional_advantage()` is wired into
      `my_reward.py`, as an `advantage_scale`-weighted term **defaulting to 0.0** (overlaps with
      the existing `pursuit`+`position` terms — a deliberate A/B knob, not stacked on by default).
      A `/ponytail-review` then trimmed the file 213→57 lines: the energy(`Ps`)/geometry/closure
      terms were deleted rather than kept as dead code (each needs state this project doesn't
      expose yet — closure rate, load factor, live turn-direction-at-merge — and re-porting a
      formula from the skeleton in SI is a few lines when that state exists).
- [x] **WEZ-phase-aware pursuit shaping landed 2026-07-11** (§4 row 2 / §6 follow-up). The pursuit
      shaping term's `pursuit_range_m`/`pursuit_half_angle_deg` were fixed for the whole match; now
      they widen late-match tracking the WEZ cone's own time-gated widening, via new
      `config.wez_pursuit_multipliers(phases, elapsed_s)` — 1.0 while only Phase 1 is active (**early
      match unchanged, no regression to the one shaping term that was actually active during stage
      0–8**), widening to 3500 m / 60° at Phase 2 (t>100 s) and 4000 m / 90° at Phase 3 (t>150 s),
      derived straight from the existing `_WEZ_PHASES` 2/4/6° + 3000/3500/4000 ft numbers (no new
      constants). Originally wired into both `student/my_reward.py` and `src/dogfight/envs/reward.py`
      (kept in sync); `elapsed_s` from `StateIndex.SIM_TIME` (verified resets per-episode). Verified
      end-to-end (same off-envelope geometry → 0 pursuit at t=50 s, positive at t=170 s).
      **Watch item**: the 90° Phase-3 half-angle is aggressive (rewards fairly loose late-match
      tracking) — faithful to the phase ratio and shaping-only, but a candidate to clamp if
      training shows it hurts tracking precision.
      **Update 2026-07-15/16**: the 2026-07-15 revert took out `src/dogfight/config.py`'s
      `wez_pursuit_multipliers()` and the underlying `_WEZ_PHASES`/damage-model phase-awareness
      entirely (see §1's dated entry and §4 row 2) — deliberately left un-restored. The shaping
      term above survives **only** via `student/reward_lib.py`'s re-homed
      `WEZ_PHASES`/`wez_pursuit_multipliers()` copy, wired into `student/my_reward.py`. It no
      longer stays "in sync" with a platform copy, because there isn't one anymore.

## 7. Training plan (compute-conscious — see §2)

- [x] **STARTED 2026-07-08**: `train_curriculum.py`'s built-in 15-stage curriculum
      (`flight_survival` → `full_dogfight`), not single-stage `train_rllib.py` — cold RL against a
      competent reactive BT opponent has ~zero win probability without staged scaffolding. Running
      via `experiments/real_eagle_v1.yaml` (SAC MLP [256,256], custom 14-D obs
      `student.my_observation`, ported `student.my_reward`). **Blocker found & fixed at launch**:
      `single_agent_env.py::add_random_init_position()` called `np_random.integers(0, bound)` on
      every axis, which raises `ValueError: high <= 0` for any 0-valued range — and stage 0
      (`flight_survival`) deliberately sets `radius: 0.0` (fixed start, jittered attitude). So the
      built-in curriculum's randomization path had **never been runnable**; guarded each axis
      (`bound <= 0` → no jitter) so a 0 range just means "don't randomize that axis." Verified
      in-process (`env.reset()` × 5 seeds, clean 14-D obs) before relaunch.
- [x] Measure real wall-clock per training iteration early (SAC MLP, default rollout workers) to
      calibrate what's actually achievable on this team's hardware before committing to a
      curriculum-stage schedule. **Measured 2026-07-08 (stage 0, 2 env runners): ~12.7 s/iter**
      after a one-time ~46s startup (Ray ~14s + `Trainable.setup` 31.6s) — in line with the
      earlier ~12s/iter calib; the custom obs/reward add no meaningful overhead. Later stages
      (esp. `full_dogfight` at 200s/12000-step episodes) will be slower per iter.
- [ ] Default to **SAC MLP only**; treat `RLLibLstm/` as explicitly out of scope unless MLP
      demonstrably plateaus below what the podium ambition requires. It's flagged as advanced/
      optional with its own silent-mismatch failure mode (`metadata.json`'s
      `use_lstm_sac`/`lstm_scope`/`max_seq_len` must match between training and load time) —
      not worth the compute or the risk unless MLP is the proven bottleneck.
- [ ] Prefer sequential experimentation over parallel if compute (not calendar time) is the
      binding constraint — lean on the available full-time *days*, not on parallelizing past
      what the hardware supports.
- [ ] Judge every stage by the dashboard's four named diagnostics together — `reward_mean`,
      `crash_rate`, `ep_min_distance`, `ep_wez_steps` — not win rate alone.
- [ ] Once `full_dogfight` is solid against the raw BT opponent, shift evaluation to the
      **Hybrid residual wrapper specifically** (§3) — that's the actual submission artifact.

## 8. Validation & robustness checklist

- [x] `run_local_dogfight.py --save-log` continuously during training — same inference code
      path as competition (per `PROJECT_ANALYSIS.md` §5.1), cheapest place to catch bugs. **Paid
      off immediately 2026-07-09**: first post-training eval run hit a `size mismatch` loading the
      custom-obs bundle — `RLLibInferenceEnv` didn't know how to size a custom `observation_module`
      and silently rebuilt a 12-D space instead of 14-D. Fixed (§9 Weeks 2-3 row has detail). Keep
      running this after every stage/tag going forward, not just once at the end.
- [x] **`scripts/eval_matchup.py` built 2026-07-10, BT-vs-BT baseline run for real 2026-07-11** —
      the §8 hybrid-mismatch benchmark harness: loops N episodes of any backend pairing
      (`bt|rl|hybrid`) across the curriculum's two-circle-headon alpha schedule, writes per-episode
      outcome to CSV, prints win/loss/draw/timeout + WEZ-contact aggregation. Reuses
      `run_local_dogfight.py`'s provider construction; varies geometry per-episode via
      `reset(options=...)` on one reused env (no DLL reload). First real run (20 episodes, BT vs.
      BT, alpha 0–180°, post-Batch-D tree): `artifacts/eval/bt_vs_bt_fixed.csv` — 20/20 timeout,
      0 WEZ-contact episodes, but real close-in engagement (range down to 270–511 m). Confirms the
      BT-alone baseline row of §3's benchmark matrix. **Standalone-RL and hybrid-residual rows still
      pending** a post-`v3` checkpoint, per §3's "evaluate the mismatch first" decision.
- [ ] Dedicated test of the head-on tie-break scenario (10,000+ ft, face-to-face merge) as its
      own case, not just aggregate curriculum score. BT-side handler now exists (`Task_NoseToNoseTurn`,
      §5.1.6 Batch C); `eval_matchup.py`'s alpha-0 episodes are close but a dedicated
      face-to-face-at-altitude case is still owed.
- [ ] Resolve §5.2 (Unreal state completeness) before trusting any live-match result.
- [ ] Deliberate network-stability dry runs against a live/practice server — confirm
      `UnrealAIPilotUDPClient`'s reconnect/heartbeat behavior under induced packet loss. 2
      instability incidents on competition day is elimination; this needs rehearsal, not
      first-contact discovery during prelims.
- [ ] Keep the BT-only fallback validated and submission-ready at all times (§3) — once §5.1's
      restoration steps land, re-run the same local verification to confirm it's still tracking
      correctly whenever the Rule XML or Task nodes change.
- [ ] Confirm which server IP is live/practice vs. production before relying on either —
      `startup_command.txt` uses `10.185.16.247` (private/LAN), `student/my_submission.py` has
      `221.151.77.208` hardcoded. Don't assume either is still current without checking the
      latest organizer announcement.

## 9. Milestones (against the ~7–8 week runway to end-of-August prelims)

Given podium ambition + limited compute, verification came first (§5) and already paid off —
§5.1 found (and scoped a fix for) a real gap before any training time was spent on it.

| When | Focus | Status |
|---|---|---|
| Day 1–2 | ~~Verify BT competence (§5.1) and Unreal state completeness (§5.2) before anything else~~ | **Both done.** §5.1: BT confirmed non-functional, then fixed. §5.2: confirmed via static analysis (no live server needed) that 4/16 `tactical16` features are permanently zero live. |
| Days 2–5 | ~~BT restoration Steps 1–3 (§5.1.2–§5.1.4: pursuit, lead pursuit, throttle, evasion, Hard Deck avoidance)~~ | **All done.** Confirmed kill in local testing, survives the full 200s match length without crashing. Along the way: the project didn't compile at all beforehand; the compiled DLL's Rule XML path was hardcoded to a separate, untouched project copy on this machine (`C:\Users\User\Desktop\AIP\`); a foundational bug mixed lat/lon degrees with altitude meters in every position-derived calculation; and a 200s test run exposed a total absence of altitude-safety logic (fixed same day, ahead of schedule, since Hard Deck violation is instant-loss). |
| Week 1–2 | ~~Reward/observation design (§6); episode-length + phase corrections (§4)~~ | **Reward, WEZ-phase, and observation corrections done 2026-07-08** — see §4/§5.2/§6 above. New runnable config: `experiments/real_eagle_v1.yaml` (built-in 15-stage curriculum, no `stages_module` override — see §7). Desktop copy (§5.1.4) still undecided — low priority, not blocking anything technical. |
| Weeks 2–3 | Curriculum run to `full_dogfight` against the now-real, now-lethal, now-survivable BT opponent | **`v1` run: crashed 2026-07-09 at stage 8/15** (`two_circle_headon_a080`, 2288 total iterations across stages 0-8, all via `--resume`/user-driven run — see below). Root cause: a Ray/RLlib 2.54.0 **internal** assertion (`single_agent_episode.py::concat_episode`, `self.t == other.t_started`) inside SAC's inherited DQN off-policy training loop — traceback is 100% Ray-internal frames, not project code; likely an env-runner-restart/episode-fragment race, not deterministic (stages 4-7 ran the same scenario type cleanly first). Emergency bundle+checkpoint saved automatically, nothing lost. **Training signal through stage 8 was weak**: crash rate collapsed 92%→6% by stage 3 (real learning, and SAC's `alpha` auto-tuned down 0.09→0.006 across stages 0-3 exactly as expected, then correctly re-expanded on each new stage 4+ scenario) — but **no stage ever met its own `advance_conditions`**; every one of the 8 completed stages hit `max_iterations_reached` only, and **win_rate was 0.0% in every single stage**. A live local eval (latest bundle vs. fixed BT, full 200s match) confirmed this qualitatively: ownship closes to 328 m (inside Phase-1 WEZ range) at t≈60s but deals zero damage, then the two aircraft diverge to ~50 km apart / 12 km altitude separation and never re-engage — `end_condition: max time out`, both at full health. Policy can find the merge, hasn't learned to convert it or re-engage after. **Separately found & fixed while running that eval** (§8): `RLLibInferenceEnv` (the shared class both local eval AND the live submission path reconstruct bundles through) didn't know how to size a custom `observation_module` — silently rebuilt any custom-obs bundle with `classic12`'s 12-D space instead of the real 14-D, corrupting weight loading (`size mismatch ... torch.Size([256, 14])` vs `[256, 12]`). Would have broken submission, not just this eval. Fixed in [`src/dogfight/ai/inference_env.py`](DogFightEnv/Release/src/dogfight/ai/inference_env.py) — now consults `load_observation_hook()` when `observation_module` is set, mirroring the training-side `env_creator`. `v1` was later resumed and actually **finished stage 8 cleanly** (200/200 iterations, completed 2026-07-11T09:26) — the crash wasn't fatal to that run, just delayed it.<br><br>**Resume-vs-restart decision RESOLVED 2026-07-11: restart.** Once the BT tactics expansion (Batches A-D), the spawn-geometry fix, and the `position`-reward fix had all landed on top of `v1`'s stale stage-0-8 assumptions, a clean restart was judged more reliable than resuming from a checkpoint trained against an opponent/reward/geometry that no longer exists. `v2` (started 15:06) was a clean restart from stage 0 against the fully-fixed BT — deliberately stopped at stage 2 (manual interrupt, not a crash). `v3` (started 15:27) is the **current, live run**: stages 0-8 all completed, now in stage 9/17 (`two_circle_headon_a060` — 2 extra OBFM stages were spliced into the original 15-stage curriculum), 195 iterations into that stage, 2330 total iterations elapsed as of 2026-07-11T22:53. Check `artifacts/curriculum/real_eagle/v3/curriculum_state.json` for the current live status before assuming this snapshot still holds.<br><br>**2026-07-12: `v3` superseded by `v4` after the full-codebase audit** (§1's 2026-07-12 update has the detail): every v1/v3 two-circle stage was 93–100% guard-fail-degenerate (unpassable ATA guard that trained merge avoidance), crashes paid `draw_reward` (+20 in `obfm_defensive` → learned 100% suicide rate), and SAC learner metrics had logged `n/a` all run. `v4` (`experiments/real_eagle_v4.yaml`) carries the fixed guard/reward/curriculum/observation and auto-launches via `scripts/launch_v4_when_free.ps1` once v3's process tree exits. v3's per-stage bundles remain on disk but inherit the degenerate incentives — treat them as diagnostic artifacts, not warm-start candidates. |
| Weeks 4–5 | Hybrid residual training/tuning (§3, §7) now that there's a real BT floor; first live-server connectivity + stability dry runs — informed by §5.2's finding on what state is actually available live | **Superseded, not done as written.** Hybrid tuning was overtaken by events: every residual configuration measured ≤ `vptrack` alone (D3-REBASED), no usable RL bundle exists after eight campaigns (v1–v7 void, v8 retired 2026-08-13), and §3's premise — that the BT is a floor worth being residual on top of — turned out to be false until F25 landed. **Live-server dry runs were never started and remain the largest un-mitigated risk (§8, F9).** |
| Weeks 6–7 | Head-on tie-break polish, network robustness hardening (§8), dashboard-driven fixes | **Not done.** Superseded by the merge/positional investigation (F1 → F25) that consumed 2026-08-11 and 2026-08-13, and which was the right call — it found that the entire tactical layer was dead code. Tie-break polish is moot until the post-F25 re-baseline extends past the four geometries in F26-GEOMETRY. Network hardening still un-started. |
| Week 8 (buffer) | Freeze, full validation matrix, submission dry-run identical to how it'll run live | - [ ] **This is where the project now is, and the buffer is gone.** Status 2026-08-13: the submission (`MODE="vptrack"`, no RL bundle, G-limited) is safe and re-baselined post-F25; the validation matrix is **partial** (four geometries done, see F26-OWED for what is still void); and the live-identical dry run **has never been performed** — no real UDP server has ever been in the loop and `SERVER_IP` is still unconfirmed. Prelims are end of August. |

**Reality check added 2026-08-13.** The July milestone table above was written against a plan
whose central assumption — hybrid RL on a working BT floor — did not survive contact. What
actually happened: seven RL campaigns produced nothing usable and an eighth was retired; the
submission became a hand-written controller (`vptrack`, D1-DONE); and on 2026-08-11 the BT's
tactical layer was found to have **never executed at all** (F25), which retroactively voided
every BT measurement in this register. The fix landed 2026-08-13 (F26) and the tactical layer now
runs. **The remaining runway should go to §8 robustness, not to new capability** — a DQ on
network instability loses the competition regardless of how well the aircraft flies, and it is
the one item on this plan that has never been started.

## 10. Open / unresolved (re-check against organizer updates, don't hard-code assumptions)

- Exact cutoff mechanism and prelim starting parameters — both explicitly "to be decided/
  released later" in the source kickoff deck per `COMPETITION_RULES.md` §9.
- The competition Discord link in `COMPETITION_RULES.md` §9 is likely expired — find the current
  one before relying on it for schedule/environment-change notices.
- Which of `BattleServer_V0.2/` vs `Windows/` is the current/intended packaged build
  (`PROJECT_STRUCTURE.md` §2) — unconfirmed.
- Whether `221.151.77.208` (hardcoded in `my_submission.py`) is still the correct production
  server address.
- Whether the compiled BT DLLs predate the source-tree gaps found in §5.1, or share them.
