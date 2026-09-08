# Session handoff — 2026-09-05

Written at the end of a long session so a fresh session (or a human) can pick this up without
re-deriving anything. **Read this first**, then `COMPETITION_PLAN.md` §4.1 rows F56–F68 for full
narrative detail on any item below — this file is the map, that file is the territory.

Git branch: `tgc/envelope-6000-90-round4-baseline`. Nothing this session was committed — all work
below is sitting in the working tree uncommitted. **No commit was requested; don't commit without
asking.**

## 0. Repo state right now (verified clean at end of session)

- No dangling background processes (checked: 0 python.exe, 0 MSBuild.exe).
- `DogFightEnv/Release/aircraft/f16/f16_init.xml` (the protected spawn preset) is canonical —
  verified via `python scripts/spawn_preset_guard.py`.
- `DogFightEnv/Release/AIP_BASE.dll` / `AIP_BASE_target.dll` are **byte-identical** to the
  pre-investigation backup (**crc32 `4026508473`**, size `2821632`) — i.e. identical to whatever
  was deployed before this session touched anything. They matter enormously (see §4).
  > **Corrected 2026-09-05 (next session).** Two claims in the original line were wrong:
  > (1) the checksum was recorded as `2397216051`, which matches neither crc32 nor adler32 of the
  > actual file — re-verifying against it raises a FALSE drift alarm. The real value is
  > `zlib.crc32` = **`4026508473`**, re-confirmed byte-for-byte against the backup.
  > (2) they are **NOT gitignored** — both are **tracked in git and clean** (`git ls-files` matches
  > them; `git check-ignore` returns nothing; `git diff HEAD` is empty). `git status` stays quiet
  > because they are *unmodified*, not because they are ignored. **Git is the durable backup**, not
  > the prior session's temp-dir copy that the original text implicitly pointed at.
- Full `git status --short` output as of session end:
  ```
  M  .vscode/settings.json
   M AIP_DCS/AIP_DCS.vcxproj
   M AIP_DCS/BehaviorTree/BT_Content/Functions.h
   M AIP_DCS/Geometry/Controller_CY.cpp
   M "DogFightEnv/References and Manuals/COMPETITION_PLAN.md"
   M "DogFightEnv/References and Manuals/COMPETITION_RULES.md"
   M "DogFightEnv/References and Manuals/MATCH_DAY_RUNBOOK.md"
   M "DogFightEnv/References and Manuals/OPPONENTS_ANALYSIS.md"
  M  "DogFightEnv/References and Manuals/startup_command.txt"
   M DogFightEnv/Release/HANDOFF.md
   M DogFightEnv/Release/run_local_dogfight.py
   M DogFightEnv/Release/run_unreal_inference.py
   M DogFightEnv/Release/scripts/eval_v5_vs_bt.py
   M DogFightEnv/Release/scripts/league.py
   M DogFightEnv/Release/scripts/package_release.py
   M DogFightEnv/Release/student/controller_providers.py
   M DogFightEnv/Release/student/match_scenario_wrapper.py
   M SchoolChallenge/MATCH_LOG.md
   M SchoolChallenge/agents/agent.yaml
   M SchoolChallenge/tools/analyze_acmi.py
  ?? DogFightEnv/Release/scripts/spawn_preset_guard.py
  ?? DogFightEnv/Release/scripts/verify_side_symmetry.py
  ?? SchoolChallenge/STARTER_PACK.md
  ?? SchoolChallenge/reference/diag_below_fighting_speed.yaml
  ?? SchoolChallenge/reference/examples/red_basic.yaml
  ?? SchoolChallenge/starter_pack/
  ```
  The `SchoolChallenge/` entries (`STARTER_PACK.md`, `starter_pack/`, `reference/diag_below_fighting_speed.yaml`,
  `reference/examples/red_basic.yaml`, and the modified `MATCH_LOG.md`/`agent.yaml`/`analyze_acmi.py`)
  are **from an earlier, unrelated project in this same repo** (the `ai-combat-core2` school
  challenge, not AIP TGC 2026) and were not touched this session — leave them alone unless asked.
  `.vscode/settings.json` and `startup_command.txt` (both `M `, staged) are also pre-existing,
  not from this session.

## 1. Competition context (why any of this matters)

- **Competition:** AIP TGC 2026 ("AI Pilot Top Gun Challenge"), 288-team national competition.
  Our team ID in code/config: `real_eagle`.
- **Bracket:** we are **진짜보라매 (공군사관학교)**, seeded into **A조** with GoGoSSung (숭실대),
  Fight's on! (연세대), HAnnamAir (한남대). 8강 opponent is D조's 1st or 2nd seed depending on our
  group finish (TrAI Everything is D조's top seed and the stronger team — finishing 2nd in our
  group routes into them).
- **Format (confirmed 2026-09-03, supersedes the original kickoff deck):** group stage 4×4 round
  robin, **BO3**; knockout **BO5**, single elimination. Per game: **start separation cycles by
  game index** (2000/2500/3000/2000/2500... ft), **altitude and speed randomized every game**,
  **Blue/Red alternates every game**. **Head-On 모드** is a **draw-triggered mode** in the
  knockout only (games 1 AND 2 both drawn), not a fixed "round 4" — this superseded an earlier,
  wrong reading of the rules as a 10,000 ft head-on round 4; that wrong reading is fully corrected
  in the docs now (see §2).
- **Submission:** **two artifacts only** — Model 1 (main, plays every standard game) + Model 2
  (used only after Head-On mode triggers). No third artifact, no per-opponent variants, no
  swapping between matches (confirmed explicitly by the user — this is a hard constraint, not a
  preference). Format is `.exe`, no separate library installs, deadline **2026-09-14 12:00 noon**,
  no resubmission after.
- **Selection criterion for Model 1 (F61):** expected BO3 match points (win 3 / draw 1 / loss 0),
  mean across the opponent roster as primary key, worst-case column as a minimax floor, draw rate
  as an explicit tiebreak (draws cost 세트득실차 in groups and hand the opponent the Head-On-model
  option in knockouts).

## 2. Documentation corrections landed this session (all committed to files, not yet git-committed)

All of these are **done and verified**, in `DogFightEnv/References and Manuals/`:

- **`COMPETITION_RULES.md`** — §5.1 rewritten from the 2026-09-03 announcement (supersedes the
  10,000 ft "round 4" reading); new §5.2 "Head-On 모드" section; §7 rebuilt with the real
  group/bracket/scoring structure; new §7.1 documenting the `.exe` submission requirement.
- **`OPPONENTS_ANALYSIS.md`** — finals-format block rewritten to match; new "Prelim standings —
  schedule-adjusted" section (full 16-team OMW/GW/OGW table, with the read that our own 5-1 is
  one of the least-tested records in the field, GoGoSSung is the softest-scheduled of the four
  undefeated teams, HAnnamAir is underrated by its wildcard seed, and TrAI Everything/불나방 are
  the real top of the tournament); GoGoSSung's "counter-tactics" section re-scoped and retitled
  "Design requirements... NOT deployable counters" per the two-artifact constraint, each item
  tagged `[UNIVERSAL]` or `[CHECK]`.
- **`MATCH_DAY_RUNBOOK.md`** — new §7 (match structure + the Head-On switch rule, pre-committed
  rather than judged live: switch iff the separation sweep showed Model 2 beating Model 1 in
  head-on geometry, otherwise never switch — there's a fill-in-blank line for the actual
  decision once Model 2 exists), §8 (`.exe` submission table), §9 (open questions for organizers).
- **`match_scenario_wrapper.py`** (`DogFightEnv/Release/student/`) — docstring re-sourced to the
  2026-09-03 announcement; `TIEBREAK_SEPARATION_M`/`TIEBREAK_LOS_DEG` relabeled as the Head-On
  proxy with the 3,048 m value marked an **assumption** (not a citation) and made overridable via
  `DOGFIGHT_HEADON_SEPARATION_M`; new `MATCH_SEPARATION_SET_M = (609.6, 762.0, 914.4)` constant
  (the real 2000/2500/3000 ft set, uniform sampling deliberately left alone so old F56/F58/F59
  numbers stay comparable); new `MATCH_ALTITUDE_RANGE_M`/`MATCH_SPEED_RANGE_MPS` env-var-driven
  per-episode randomization (default OFF — empty string — so nothing changes unless asked; when
  set, draws happen AFTER heading/side so the RNG stream for existing callers is untouched).
- **`COMPETITION_PLAN.md`** — this is the **primary durable record**. F56 through F68 are all
  landed there (see §5 below for what's in F61–F68 specifically). **Read this file's F-numbered
  rows before doing anything below** — they carry the full reasoning, numbers, and citations that
  this handoff only summarizes.

**Still outstanding, never answered by organizers** (tracked in `MATCH_DAY_RUNBOOK.md` §9):
Head-On mode's actual separation/geometry, the randomized altitude/speed band, how the `.exe`
receives server IP/port, whether a onedir bundle is acceptable, whether group-stage draws also
trigger Head-On, whether the process persists between games, practice-server access.

## 3. Infrastructure built this session (all new/modified scripts)

- **`scripts/spawn_preset_guard.py`** (new). `aircraft/f16/f16_init.xml` is a protected runtime
  asset that `JSBSimWrapper.Fighter.__init__` rewrites on every episode reset (it's the channel
  used to hand initial conditions to the native DLL — not a bug, this is how the write is
  supposed to work). `--check` (default) diffs it byte-for-byte against the confirmed canonical
  preset and exits 1 with a field-by-field diff on drift; `--restore` rewrites it. Wired into
  `scripts/package_release.py` as a hard failure gate. **Run this before every commit or package,
  and after every eval run** — drift after a run is expected and not a bug, just restore it.
- **`scripts/verify_side_symmetry.py`** (new). Tests whether a config plays the same when the
  spawn mirror is flipped. `--from-csv PATTERN` is free (post-hoc split of existing runs by the
  `initial_side` column — needs data logged after 2026-09-04, see below). Default mode is
  decisive: forces `--match-side +1` then `-1` with the same seed, producing an **exact mirror
  pair** (positions don't depend on side, only headings do, and the side is drawn from the RNG
  even when forced so the stream stays aligned) — costs 2N episodes. Reports a win-rate gap in
  sigma using an Agresti-Coull-adjusted binomial estimate (the naive one collapses to 0 at p=0/1
  and falsely reports "infinite sigma" on lopsided small samples — fixed, with a 10-episode/side
  floor below which it reports "INSUFFICIENT" instead of a number). Dispatches to
  `eval_vs_cutoff.py` automatically when `--target-backend cutoff` is used (that archetype needs
  the wrapper; `eval_v5_vs_bt.py` itself rejects `"cutoff"` as an invalid `--target-backend`).
- **`scripts/eval_v5_vs_bt.py`** (modified). New CSV columns: `initial_altitude_m`,
  `initial_speed_mps`, `initial_side` (captured on the **first simulation step**, not at
  `reset()` — the state array reads all-zero at reset, before the FDM has run; this was a real
  bug found and fixed this session, don't regress it). New `--match-side {-1.0,1.0}` CLI flag
  (forces the mirror, see above). New `--episode-offset` and `--append` flags for chunked/resumable
  runs (offset shifts BOTH the seed sequence and the alpha-schedule index, so a chunk starting at
  offset K reproduces exactly what an unbroken run would have done at episodes `[K, K+episodes)`
  — it's not just a label). New `ep_bt_frac`/`ep_bt_steps` columns (F67 diagnosis — see §4) captured
  by extending the existing `VPProbe` wrapper class in this file, **not** by reading
  `info["ctrl_source"]` off `env.step()`'s return (that never arrives there — see §4 for why).
- **`scripts/league.py`** (modified). Ranks candidates on the **F61 criterion** (expected BO3
  points, mean/worst, draw rate) instead of raw damage differential (still reported per-column,
  since it's still the within-episode predictor a timeout adjudicates on). Draws are decomposed
  into `mutual_kill` / `scoreless_nose_on` (closure failure — nose-on but never converting) /
  `scoreless_off_angle` (pointing failure — never got the angle at all) / `traded_even`, via
  `_classify_draw()`. **Resumable chunking**: `--episodes` is now a per-pair TARGET, `--chunk-episodes`
  (default 15) caps how many NEW episodes run per invocation; re-running the identical command
  resumes every pair from wherever its CSV's row count says it is, via `_episodes_done()`. That
  function is **schema-aware**: it checks the CSV header against `_RESUME_SCHEMA_COLUMNS`
  (`initial_altitude_m`, `initial_speed_mps`, `initial_side`) and treats a file missing them as 0
  done rather than silently mixing old-schema and new-schema rows — this caught a real near-miss
  (see §4a). Launch bursts are staggered 2s apart and failed pairs get up to 2 retries (not 1) —
  both added after a `STATUS_DLL_INIT_FAILED` (0xC0000142) failure under 6-way concurrent cold
  starts, believed to be native-DLL-load contention. **`--skip-existing`'s help text now warns
  loudly against combining it with resumption** (after the first chunk every pair's CSV exists,
  so that flag would silently stall the whole matrix).
- **`scripts/package_release.py`** (modified) — now runs the spawn-preset guard as part of its
  verification, refusing to package a drifted preset.
- **`run_local_dogfight.py`** (modified) — **fixed a real, pre-existing bug**: `main()` has read
  `args.{side}_vptrack_hard_deck` since F59, but the CLI never defined those flags, so **every
  invocation of this script has raised `AttributeError` since F59 landed** — the documented local
  sanity-check command was silently broken this whole time. Fixed, and the new `--{side}-vptrack-deck-ttc`
  flag (see below) added alongside.
- **`run_unreal_inference.py`**, **`student/controller_providers.py`** (modified) — new
  time-to-impact deck guard (`deck_ttc_s` / `DECK_TTC_S` / `SHIP_DECK_TTC_S`), finite-differenced
  from `state[D]` (never `state[VZ]` — F46 already established that inverts on the live path).
  **Default OFF everywhere** (`SHIP_DECK_TTC_S = 0.0`) — unmeasured, not yet adopted, exists so it
  CAN be measured. Motivated by the 8-27 trajectory analysis (F62): an uncommanded aircraft's
  spiral-mode divergence crossed the existing 1000 m altitude-only hard deck at 236 m/s of sink
  with zero recovery, because an altitude threshold can't express "how much time is left" the way
  a sink-rate-based one can.

## 4. THE HEADLINE FINDING: a real, large, mirror-side performance asymmetry (F67/F68)

This consumed most of the session's second half. **Bottom line: found, root-caused as far as
time allowed, two fix attempts both measured WORSE than doing nothing, reverted cleanly, team
decision made to ship with it as a known quantity.** Full blow-by-blow in `COMPETITION_PLAN.md`
F67/F68 — this section is the compressed version.

### 4a. The N=150 matrix (F64–F66) — do this part again if the DLL ever changes

Built a chunked, resumable version of `league.py` specifically because **the full N=150 matrix
(15 candidate×archetype pairs) could not survive as one ~7.6h background command** — it died
twice with an external-kill signature (`rc=1073807364`, believed either a sandbox resource
ceiling or native-DLL-load contention under 6-way concurrency) at 20–41 minutes elapsed, with the
correct interpreter both times. The chunked version (§3) completed the full matrix successfully
across ~9 separate ~20–50-minute invocations, surviving a session restart mid-run without losing
data (the chunking design means a kill loses at most one chunk). **Along the way, the
schema-aware resume check caught 10 of 15 files still holding F60's OLD N=50 fixed-condition data
that would otherwise have been silently mixed with new randomized-condition rows** — a near-miss
worth knowing about if this pattern (CSV schema changes, then resuming an old file) ever recurs.

**Result: `ship_6000_120_deck` (the already-shipped config — 6000 m engage range, 120° LOS,
throttle control, 1000 m hard deck) is confirmed under the F61 criterion.** Mean expected BO3
points 1.69, worst-column 1.33 — the only one of three candidates whose floor stays above the
1.0 "always-draw" break-even line, and it loses only the `aggressor` column, narrowly. The other
two candidates (`alt_8000_90_deck`, `prev_6000_90`) each lose three columns decisively. **No
config change indicated by the matrix itself.**

Draw decomposition at real scale: against `sniper` (the GoGoSSung analogue), **69% draw rate,
98% of those closure failures** (nose-on, never converting); against `bt_only`, 76%/100%. This
raises the Head-On-mode reachability estimate against a GoGoSSung-like opponent to ~0.69² ≈ 48%
of knockout matches (up from an earlier ~36% estimate on smaller data).

### 4b. The bug (F67)

The user asked for a decisive side-symmetry check on the shipped config against `cutoff` (the
organizers' own binary, run via `eval_vs_cutoff.py`). Result: **exact mirror pairs, same seeds,
N=50/side — one side wins 48.0%, the mirror-image side wins 22.0%, a 26-point gap at 2.9 sigma**,
independently corroborated by a 3.6-sigma signal in the post-hoc N=150 matrix screen. On the
losing side, median best angle-to-target across the **entire 200-second episode** was 91° — no
better than the spawn geometry — meaning essentially zero angular progress for the whole
engagement in most episodes, not slow convergence.

Root-caused (with help from a background investigation agent) to
`AIP_DCS/Geometry/Controller_CY.cpp::GetStick`, a "SMALL-COMMAND BOOST" whose own comment states
the intent as "counteracts squaring which crushes SMALL corrections" but is implemented as
`if (RollCMD < ROLL_BOOST_THRESHOLD) RollCMD *= 3.0f;` — no `abs()`, so it's true for **every**
negative `RollCMD` regardless of magnitude and only small positive ones: a left roll of −0.5 gets
tripled to −1.5 (clamped to −1.0), an equal right roll of +0.5 is untouched. A real, permanent
~3× roll-authority asymmetry between turn directions.

**Two fix attempts, both measured WORSE, not better:**
1. `std::abs(RollCMD) < ROLL_BOOST_THRESHOLD` (the literal correct reading of the stated intent)
   — gap **widened** to 34.0% (4.1σ), both sides' damage differential went negative.
2. Unconditional `RollCMD = clamp(RollCMD * ROLL_BOOST_GAIN, -1, 1)` (extend the authority to
   both signs instead of removing it from one) — gap still 30.0% (N=20), losing side's
   differential got worse again.

Both DLL rebuilds were deployed only long enough to measure, then **reverted to the checksum-verified
original backup** immediately on each negative result. The **actual mechanism** was found via
cheap Python-side instrumentation rather than a third blind C++ edit: `VPTrackingProvider`
already tags every step with `ctrl_source` ("vptrack" or "bt"), but nothing surfaced it because
`_step_controlled_aircraft()` in `src/dogfight/envs/single_agent_env.py` (a **hard no-edit
boundary**, team policy, do not touch) only reads `result.action` and discards `result.info`.
Captured it instead by extending the `VPProbe` wrapper class already living in `eval_v5_vs_bt.py`
(outside the boundary). **Result: on the original, unmodified DLL, median fraction of the episode
spent under native-BT control is 36.3% on the winning side and 98.8% on the losing side** — the
Python law (confirmed symmetric by direct code inspection) essentially never gets a turn on the
losing side, because LOS never drops under `VPTrackingProvider`'s 120° hand-off threshold. The
roll-boost bug is real but is not the sole lever — it's one piece of a native BT that is already
dominant and already failing on that side; editing it perturbs an already-bad situation. The true
defect most likely lives in the broader tree's tactic selection (~20 `Task_*` nodes deciding a
BVR/long-range approach), which is a substantially larger investigation than one function.

Tested one more low-risk mitigation: widening `VPTrackingProvider`'s own envelope to 180°
(always-engage) cut the gap to 10% (0.9σ, no longer significant) but **collapsed absolute win
rate on both sides** (40%→15%, 20%→5% at N=20) — confirms the mechanism, is not a usable fix
(the Python law isn't competitive outside its tuned range).

**Decision (explicit, from the user): ship as-is, move on.** The F66 matrix numbers already have
this asymmetry baked into them — it's a known, measured quantity, not a hidden one.

### 4c. Current state of the fix attempt (verified clean)

- `AIP_DCS/Geometry/Controller_CY.cpp` — **reverted to the exact original shipped logic**
  (`if (RollCMD < ROLL_BOOST_THRESHOLD) RollCMD = RollCMD * ROLL_BOOST_GAIN;`, no `abs()`). The
  comment block above it now carries the FULL investigation history (both failed fixes, the
  `ep_bt_frac` finding, the ship-as-is decision) so nobody re-discovers this from scratch. This is
  a source-only change (comment + revert-to-original-logic) with **zero behavioral difference**
  from before the session started.
- `AIP_DCS/AIP_DCS.vcxproj` — **kept**, independent of the roll-boost investigation. Fixed two
  real, pre-existing build-system bugs found while trying to rebuild for validation: (1) the
  Release|x64 property-sheet import path was `..\..\PropertySheets\...` (two levels up, resolving
  OUTSIDE this checkout to a nonexistent path) while Debug|x64 correctly used `..\PropertySheets\`
  — **Release had never been buildable directly from this checkout**; (2) Release|x64 additionally
  imported `LDFP_Model.props`, pulling in libraries (`RTVBase.lib` etc.) nothing in this DLL's
  code references, which failed the link once the path was fixed. Also added an explicit
  `RuntimeLibrary=MultiThreaded` (static) override for Release|x64.
- **F68, a separate critical finding surfaced by the above**: `dumpbin /DEPENDENTS` on the
  **currently deployed** `AIP_BASE.dll` (before any change) showed it depends on
  `MSVCP140D.dll`/`VCRUNTIME140D.dll`/`VCRUNTIME140_1D.dll`/`ucrtbased.dll` — **the D-suffixed
  DEBUG runtime** — and carries a `.msvcjmc` (Just My Code) section. **The DLL shipped for this
  entire project has been a Debug build, not Release, likely since it was first built.** A
  from-scratch Debug|x64 build of the unmodified source reproduced this exact dependency set
  byte-for-byte, confirming it. Debug runtime DLLs are not part of the standard, universally
  redistributed VC++ Redistributable — **if the actual competition PC lacks them, `AIP_BASE.dll`
  would fail to load entirely, a hard zero, not a performance issue.** The `.vcxproj` fix above
  (correct path + static runtime) produces a Release build depending on nothing but
  `KERNEL32.dll` — confirmed via `dumpbin` and a `ctypes.LoadLibrary` smoke test (all 9 expected
  exports present: `ChangeData`, `CreateBehaviorTree`, `GetStick`, `GetVP`, `LLAtoCartesian`,
  `RemoveBT`, `Reset`, `SetBehaviorTreeDeltaTime`, `Step`). **This Release/static build was never
  deployed** — the currently-deployed `AIP_BASE.dll`/`AIP_BASE_target.dll` remain the original
  Debug build, checksum-verified unchanged, per the "ship as-is" decision on F67. **F68 is a
  separate, still-open risk from F67** — see §7.
- `AIP_DCS/BehaviorTree/BT_Content/Functions.h` — **kept**, harmless. Corrected a stale comment
  (still described `ShorterTurnDirection` as canonicalizing against `MyRightVector`; the actual
  code, correct since the `c0f3eaf` fix, canonicalizes against `MyForwardVector` — only the header
  comment was never updated). Zero behavioral effect.

## 5. Where the F-numbered register stands (`COMPETITION_PLAN.md` §4.1)

F56–F60 predate this session (config adoption history). This session added/extended:
- **F61**: the two-artifact constraint and its consequences — objective is expected BO3 points
  across a distribution of opponents we can't choose, not per-opponent tuning; the Model 1 vs
  Model 2 decision (both slots used); Model 2 scoped as a much cheaper build (single geometry,
  needs its own separation sweep since Head-On mode's real distance is unpublished); the
  pre-committed switch rule (measured before submission, executed without judgment on the day).
- **F62**: the 8-27 trajectory analysis (uncommanded spiral-mode divergence into the deck) and
  the case for a time-to-impact deck guard over an altitude-only one.
- **F63**: the criterion change (F61) applied retroactively to the OLD F60 data — the previously
  "confirmed" config actually had the worst floor and highest draw rate under the real criterion
  (this was superseded by the real N=150 matrix in F66, which reconfirmed it under the REAL
  condition set — don't cite F63's numbers as final, cite F66's).
- **F64**: the logging/instrumentation additions (start conditions, side, deck guard, chunking
  prerequisites) and the schema-mismatch near-miss.
- **F65**: the full story of why the N=150 matrix needed chunking (two external-kill deaths,
  the numpy-missing red herring, the schema-aware resume fix, the DLL-load-contention retries).
- **F66**: the completed matrix result (§4a above).
- **F67**: the mirror-asymmetry investigation (§4b above) — this is the longest, most detailed
  entry in the whole file. Read it in full before touching `Controller_CY.cpp` again.
- **F68**: the Debug-build discovery (§4c above) — separate open risk, see §7.

## 6. What was explicitly decided, so it isn't re-litigated

- Two artifacts only (Model 1 + Model 2), both used — not "submit one, keep one in reserve."
  Confirmed explicitly by the user after an earlier draft plan wrongly treated Model 2 as
  optional.
- Head-On switch rule is pre-committed via measurement before submission, not judged live on
  match day.
- F67: ship with the known mirror-asymmetry rather than continue iterating — confirmed via an
  explicit AskUserQuestion, "Ship as-is, move on" selected over "one more tuning pass" or "deep
  native investigation."
- Side-swap sweep across all three matrix candidates was requested and completed using the
  existing N=150 data (free post-hoc method) rather than running fresh decisive tests on the two
  non-shipping candidates — reasoned as low marginal value since neither is being shipped.

## 7. Immediate next steps, in priority order

> ### ⚠️ SUPERSEDED 2026-09-05 (next session) — read this box before the list below
>
> The list below is kept for its detail, but its **ordering and two of its premises are wrong**.
> The corrected plan lives at `~/.claude/plans/sprightly-popping-cookie.md`; new register rows
> **F69–F71** carry the evidence. Changes:
>
> - **A fatal bug was found in `HEAD` that this list does not mention: `run_unreal_inference.py`
>   could not start at all** (`NameError: name 'p' is not defined`, `:100`, from commit `c0aa0ff`).
>   It is the command in `startup_command.txt` and `MATCH_DAY_RUNBOOK.md:107`, the only entry point
>   with `--server-ip`, and the subprocess behind `loopback_live_dryrun.py`. **Fixed 2026-09-05 (F69).**
> - **Item 2 (F68) rested on a false premise.** Deploying the Release/static build does **not** close
>   the debug-runtime risk: `JSBSimAIPLib.dll` is organizer-supplied, has no source, loads at import
>   on every run, and needs the **same four debug CRTs** (verified from real PE import tables — F71).
>   **Decision taken: ship the four CRTs beside the binary.** Zero re-validation; the Release swap is
>   now optional hygiene, not the fix.
> - **Item 3 (regression guards) was ranked as if costly. It is ~1 minute total.**
>   **All three re-run and green 2026-09-05**; spawn preset drifted as expected and was restored.
> - **Item 4 (`.exe`) is the only *required* artifact** (`COMPETITION_RULES.md` §7.1 — the head-on
>   model is explicitly *optional*), yet it was ranked last. Good news that changes its cost: the
>   live match path imports **neither `ray` nor `torch`**, so the payload is ~11 MB against a 1 GB
>   limit. **User decision: build the `.exe` after Model 1 and Model 2 are both done** — Model 1 is
>   already finished (F66), so only Model 2 precedes it. Recommended guard rail: Model 2 hard-stops
>   09-09; `.exe` clean-machine-verified by 09-12.
> - **New blocking constraint for any repackaging (F70):** `Rule_forTraining.xml` must sit beside
>   `AIP_BASE.dll`, or the native BT silently returns all-zero stick and throttle while the client
>   still answers at 60 Hz. Build `--console`; assert non-zero, varying commands in the smoke test.

1. **Model 2 (head-on model).** Not started. Per F61: sweep `DOGFIGHT_HEADON_SEPARATION_M` (the
   real separation is unpublished — the 3,048 m constant is an assumption inherited from a
   superseded reading of the rules), since Model 2 only ever plays one geometry and doesn't need
   the full randomized-condition matrix `ship_6000_120_deck` got. Consider running its own
   `verify_side_symmetry.py` paired check before trusting any Model 2 numbers — F67 showed the
   mirror-sensitivity isn't unique to one config's exact parameters.
2. **F68 (Debug-build risk) is still open and unresolved.** The currently-shipped DLL is
   confirmed to depend on debug-only runtime DLLs that may not exist on the competition PC. A
   working, self-contained Release build was produced this session (`bin/Release.x64/AIP_DCS.dll`,
   depends on `KERNEL32.dll` only, all 9 exports verified) but **was never deployed** because
   deploying it would require re-running the regression guards and re-measuring the response-time
   budget against a different binary than everything has been validated against — out of scope
   for the F67 investigation, but a real decision still to make before 9/14. The built artifact
   is at `D:\aip_lib\bin\Release.x64\AIP_DCS.dll` if picked up again (rebuild via
   `MSBuild AIP_DCS/AIP_DCS.sln /p:Configuration=Release /p:Platform=x64 /t:Rebuild` if it's gone).
3. **Regression guards never re-run this session**: `scripts/verify_report_fixes.py`,
   `scripts/verify_match_spawn.py`, `scripts/verify_resilience.py` (per `HANDOFF.md`). Run these
   before trusting anything beyond what was directly measured.
4. **`.exe` packaging** — not started at all. Deadline **2026-09-14 12:00 noon**, i.e. 9 days
   from today. `scripts/package_release.py` handles the ZIP-based submission path (with the
   spawn-preset guard now wired in) but the competition needs a **compiled `.exe`**, which is a
   different packaging problem entirely (PyInstaller or similar) — not attempted this session.
5. **Organizer questions** (`MATCH_DAY_RUNBOOK.md` §9) — still unanswered, still worth chasing:
   Head-On mode's real separation, the altitude/speed randomization band, `.exe` IP/port handoff
   mechanism, practice-server access.

## 8. Things a fresh session should NOT re-do

- Don't re-attempt a third direct edit to `Controller_CY.cpp`'s roll boost without genuinely new
  evidence narrowing which native `Task_*` node is responsible — two attempts already failed,
  and the reasoning for why is fully captured in the code comment itself now.
- Don't re-run the full N=150 matrix unless the DLL or a candidate config actually changes — F66's
  numbers are the current, validated answer for `ship_6000_120_deck` vs the archetype roster.
- Don't treat `F63`'s numbers as final — they were a re-read of OLD (F60-era) data under the new
  criterion, superseded by F66's real-condition-set numbers.
- Don't assume `--target-backend cutoff` works directly on `eval_v5_vs_bt.py` — it doesn't, use
  `eval_vs_cutoff.py` (or anything that dispatches through it, like `league.py` and
  `verify_side_symmetry.py` already do).
- Don't edit `src/dogfight/**` — hard team policy, independent of what the competition rules
  themselves allow.
