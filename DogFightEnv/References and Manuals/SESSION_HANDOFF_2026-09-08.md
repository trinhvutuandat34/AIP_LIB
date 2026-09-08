# Session handoff — 2026-09-08

**This supersedes `SESSION_HANDOFF_2026-09-05_EVENING.md`.** That file's §3 priority list is now
done or obsolete: its item 1 (the `.exe`) is **built and gated**, and its item 2 (Model 1
improvement) has a new and much larger lever than the one it names.

Git branch: `tgc/envelope-6000-90-round4-baseline`. **Nothing was committed.** All work below sits
in the working tree.

**6 days to the deadline: 2026-09-14 12:00 noon.**

---

## 0. The one-line summary

**The `.exe` exists, both submission ZIPs are built and pass an executable gate, and the critical
path has moved from packaging to measurement.** Two scorer bugs and four behavior-tree defects
were found and fixed; the fixed tree cleared its A/B and is what ships.

## 0b. Read this before you tune anything — four sweeps produced nothing, and here is why

Later in the same session, four attempts to raise the cutoff column all failed, and the last
finding explains part of the pattern:

- **The minimax floor was a self-play column (F81).** `aggressor` is parameter-for-parameter
  identical to the shipped `ship_6000_120_deck`. A symmetric matchup is pinned near 50% by
  construction — measured 32W/35D/33L — and `worst = min(pts)` selected it for every candidate.
  **The standing adoption gate therefore contained a criterion no config can satisfy.** Fixed:
  `_is_selfplay()` excludes such columns from WORST (MEAN keeps them, so register means stay
  comparable). The shipped floor moves 1.34 → **1.60**.
- **Of five archetypes, only `cutoff` and `bt_only` are not our own controller**, and `bt_only`
  never shoots. There is exactly **one** independent opponent in the roster, and it is the one we
  never play. Read "beat `sniper` 94/100" as "a wide envelope beats a narrow one", not as evidence
  about GoGoSSung.
- **Range is saturated above 6000 m** — 8000 and 12000 produce *byte-identical* episodes (F80).
- **LOS 120 is bracketed by worse on both sides** (90 → 29%, 140 → 36%, 180 → known catastrophic).
- **`ROLL_TAPER_DEG` is worse at both values tested** (z = −2.97 / −2.65). The documented "roll
  authority inversion" is **load-bearing, not a defect** — damping it cuts dwell and *raises*
  damage taken (F80).
- **The historical 100% vs cutoff does not reproduce** (F80): at the original fixed spawn the
  shipped config scores 46%, *worse* than the 50% it scores with randomisation on. The
  randomisation band is not what costs us.

**Both randomisation ceilings (7,700 m and 280 m/s) trace to one trajectory that F62 itself
describes as an uncommanded spiral in which "the aircraft was never flown."** Getting the real
band from the organizers is the cheapest thing that could still move any number.

---

## 1. Read this before you trust any number in this repo

**Every benchmark predating 2026-09-08 was scored by a scorer with two bugs, and every benchmark
predating 2026-09-06 14:58 was measured on a different binary.** Both are now recorded as F77/F78.
Concretely:

- `league.py` booked **the opponent flying into the ground as a draw** (73 episodes across the
  shipped matrices) and **our own self-crash as a draw** (68 episodes). Fixed.
  `--legacy-scoring` reproduces the old table byte-for-byte, so old rows stay checkable.
- The spawn draw happened **before** the RNG was seeded, so 54 of 150 episode indices had a
  different spawn in every file and paired comparison held for only 64% of episodes. Fixed and
  verified live: the new 500-episode arm holds **exactly 100 distinct spawn tuples across 5
  archetypes**, i.e. perfect pairing, with the altitude/speed/separation distributions unchanged.
- The resume guard compared three column *names*, not the schema, and the live matrix files are
  28-column against a 30-column writer. One `--episodes 151` would have shifted every column
  right of `ep_wez_steps` by two, silently. Fixed; it now fires on those files.

**What survived all of it:** Model 1 = `ship_6000_120_deck` is still the right main model. It wins
the mean **and** the minimax floor under flat scoring, phased scoring, and both crash-bucketing
conventions. That is the one decision in this project that no re-scoring has moved.

**What did not:** Model 2's candidate. F74's "prev_6000_90 wins both ranking keys" and its "the
hard deck was tested and rejected on evidence" **both require the self-crash bug**. Corrected,
`m2_6000_90_deck` takes the mean and the floor gap closes to noise. **Re-decide it — that is a
re-scoring of data we already have, not a new measurement.**

---

## 2. The `.exe` — done, and how to rebuild it

```
python scripts/build_exe.py          # both models, then smokes each one
python scripts/package_release.py    # re-verifies, then writes both ZIPs
```

Output in `DogFightEnv/submission_exe/`:
`JinjjaBoramae_APTGC2026_main.zip` and `JinjjaBoramae_APTGC2026_headon.zip`, each **exactly two
files at the root** (`<name>.exe` + `config.json`).

Verified on the real binaries, not the source path: **600/600 frames answered, worst latency
20.9 ms** against a 166.7 ms budget, 596 distinct commands of 600, per-channel roll/pitch/rudder
all varying, `Behavior Tree Initialized` present, `진짜보라매` / `진짜보라매_HeadOn` round-tripping
the real wire packer, and the two exes genuinely flying different profiles.

**Four things that each would have been a silent or total failure on the day** (detail in F79):
`native_bt.py`'s four-level `__file__` walk landing in `%TEMP%` when frozen; no `config.json`
reader existing anywhere; PyInstaller emitting a *warning* for the missing `ffi.dll` and then
producing an exe that died on `_ctypes`; and the head-on exe having no channel to receive its
model profile or its `_HeadOn` name.

**`package_release.py` was rewritten.** Its old gate verified the entry point by **grepping its
source text** — which is exactly how F69's fatal `NameError` shipped in `HEAD` unnoticed. It now
launches the exe against a replay server and asserts per-channel non-zero, varying commands.

**Do not skip `smoke_exe.py`.** Per F70 a failed Rule-XML load is caught in C++, printed to
`std::cout`, and turned into an all-zero `ControlValue` that still handshakes and answers at
60 Hz. A dead submission and a healthy one are indistinguishable from outside.

---

## 3. The behavior tree — four defects fixed, rebuilt, A/B in flight

The 2026-09-06 change (`Task_DefensiveSpiral` + a compound HCA release gate in `Task_Evade`) went
in with **no register row** and invalidated all 3,450 measured episodes. Reviewing it at source
found two S1 defects (full detail in F77):

1. **`Task_Evade`'s unconditional cap and cooldown were dead code.** `BREAK_STALE_S ==
   BREAK_TOTAL_MAX_S == 20.0`, and `ClaimManeuverPhase` can return at most `staleAfterSeconds`, so
   `elapsed > 20.0` was never true — at any tick rate, for any geometry. **The 2026-09-06 gate's
   own comment names that cap as its safety net.** Fixed: `18.0`.
2. **`Task_DefensiveSpiral` could not produce a spiral.** `ShorterTurnDirection` flips sign when
   `toTarget · MyRightVector` crosses zero, and the node is only reachable at own ATA > 90° with
   its doctrinal case at dead six, where that product is exactly zero. Fixed by latching the
   direction on the blackboard at claim time (`CPPBlackBoard::ManeuverTurnDir`,
   `BTFunc::LatchedTurnDirection`). `Task_Evade`'s break turn now uses it too.

Plus the spiral's altitude floor (dead code below Gate 0's 914 m; raised to 1000 m) and a
degenerate-cross-product guard fixed at the shared root.

**`verify_shorter_turn_direction.cpp` gained case set C** — its four existing cases were all
forward-hemisphere, which is why nothing caught this. C3 walks the bandit across dead six one
metre at a time and asserts the flip is real (measured: full LEFT at −1 m, full RIGHT at +1 m).
Its documented `g++` build line does not work here; an MSVC line is now in the header, and note
the include path must **not** contain `Geometry/`, or `<cmath>` resolves to `Geometry/Math.h`.

Rebuilt DLL: crc32 **`1131281049`** / 2,885,632 B.
MSBuild lives at `C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\`.

### The A/B, and the result to be careful about

Model 1's config, five archetypes, `match_base`, N=100 per cell, run twice — once on the rebuilt
DLL, once on `HEAD`'s — into `artifacts/eval/ab_fixed_0908/` and `artifacts/eval/ab_head_0908/`.
Both arms are re-run rather than compared against F66, because the reseed fix changes the spawn
draw.

**The fixed arm came back far stronger than F66, and that needs the control before anyone acts on
it:** mean expected BO3 points **2.18**, floor **1.34**, WEZ-entry rate **85.2%** against F66's
1.75 / 1.35 / 49.6%. Draws essentially vanished — vs `sniper` 94W/2D/4L where F66 had
36W/103D/11L. The episodes are not degenerate (median 176–185 s, 52–54 kills vs the passive
archetypes, real damage both ways), the spawn distribution is unchanged, and the opponent did not
get weaker (damage taken vs `sniper` 0.086 → 0.084 while damage dealt went 0.189 → 0.821).

**The mechanistic hypothesis, which the control arm tests directly:** the dead break cap is
pre-existing, so it was in `HEAD` too — a `Task_Evade` that could never release held Gate 1
indefinitely and flew extend-away at throttle 0.5 instead of converting. That would explain F66's
long-standing puzzle ("we win the angle fight in ~99% of episodes and reach the weapons envelope
in 25%") with a one-constant answer. **Do not write that up as established until the `HEAD` arm
lands** — if `HEAD` also returns ~2.18, the cause is something else and must be found.

**Swap the DLL and the Rule XML together.** The old DLL against the new XML hits an unregistered
`Task_DefensiveSpiral`, and per F70 that failure is silent. Both arms' binaries are staged in the
session scratchpad; `git show HEAD:` regenerates them.

**Adoption gate:** mean up **and** minimax floor not down, on the corrected scorer. If it does not
clear, `git checkout HEAD --` the four files and freeze on the measured binary. That is a result.

---

## 4. Head-on switching — the pre-commit was wrong, and `MATCH_DAY_RUNBOOK.md` §7.3 is rewritten

F61/F74 pre-committed to *always switch to Model 2 when Head-On mode triggers*. Re-derived from
the same 1,200 head-on episodes under the corrected scorer, **switching pays against `cutoff`
only** (+22–26 points of match win probability) and **loses 2–16 against everything else**.

And the trigger self-selects against the one opponent it helps: Head-On needs two drawn games, and
Model 1's draw rate is `sniper` 68.0% vs `cutoff` 26.7%, so P(two draws) is 46% vs **7%**. Bayes
gives **P(opponent | Head-On triggered) = sniper 55.8%, mirror 20.6%, aggressor 15.1%, cutoff
8.6%**, under which every Model 2 candidate is negative. Without the prior: **switching pays only
if P(cutoff-like | two draws) > 17–19%, and our own draw rates put it near 9%.**

§7.3 is now a pre-specified conditional on one observable — did the opponent decline the merge and
bank the clock, or were the two draws contested — defaulting to **do not switch**. On current
scouting the default answer against all three A조 teams is *do not switch*: GoGoSSung, Fight's on!
and HAnnamAir all finish by kill, and none shows a clock-banking signature.

---

## 5. What is left, in priority order

1. **Land the A/B and decide the tree.** Then rebuild the exes from whichever binary wins —
   `package_release.py` refuses to package an exe older than any runtime asset, so this is
   enforced, not remembered.
2. **Re-decide Model 2's candidate** on the corrected scorer (F78). Re-scoring, no new episodes.
3. **The knob sweep, gated on the exe.** `ROLL_TAPER_DEG` is the one that targets the measured
   defect directly and it **already has a CLI flag** (`--ownship-vptrack-roll-taper`);
   `PITCH_FLOOR`, `TARGET_RANGE_M` and `THROTTLE_AUTHORITY` are env-var-only and would need either
   new flags or the per-value output-root pattern `sweep_headon_separation.py` already uses.
   **Screen on WEZ-entry rate, not win rate** — it is the strictly necessary condition (0 kills in
   487 episodes without it) and separates at far lower N. `league.py --summarize` now prints it.
4. **The 3,000 ft start separation has never been evaluated** (F78) — α=0 and α=180 collapse to
   the same fraction, so 914.4 m never occurs and 609.6 m is double-weighted. One-line fix, but it
   invalidates cross-run comparison, so land it *with* a sweep.
5. **Team admin:** 개인정보수집및활용동의서 — separate ZIP, one signed PDF/HWP per member.

## 6. Do NOT re-do these

- **Don't reopen F67's roll boost.** Two direct fixes already measured worse. Newly narrowed
  though: the asymmetry reproduces against `cutoff` and only `cutoff` (−22.3 points, z = −2.80;
  the other four archetypes sit between z = −1.75 and +1.26 with inconsistent signs, and the
  pooled split shows no gap at all). It is an extend-and-clock-specific leak, not "half of every
  match".
- **Don't use `verify_side_symmetry.py --from-csv` on head-on data** — `initial_side` is numerical
  noise at LOS 0, proven by a forced `+1` run logging `+1:17 / -1:8`. Paired mode only.
- **Don't run an eval without `python scripts/spawn_preset_guard.py --restore` afterward.** Drift
  is expected (F57), and `package_release.py` refuses to package a drifted preset.
- **Don't edit `src/dogfight/**`.**

## 7. Operational notes

- Interpreter: **`C:\Users\user\.conda\envs\aip\python.exe`**. PyInstaller is installed there now.
- Long runs get externally killed; drive league in a loop of passes — re-running the identical
  command resumes. `run_arm.sh` in the session scratchpad does this.
- `smoke_exe.py` **must** drain the child's stdout on a thread. The submission prints a packet
  counter every frame; at 60 Hz that fills the 64 KB pipe in seconds and the exe blocks inside its
  own `print`, looking exactly like a hung client. `loopback_live_dryrun.py` reads stdout only
  after `terminate()` and would deadlock the same way against this child.
