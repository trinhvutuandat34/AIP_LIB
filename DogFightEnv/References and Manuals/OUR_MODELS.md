# Our models — the two submitted configurations, and everything measured about them

**As of 2026-09-09.** Companion to `CUTOFF_MODEL_REFERENCE.md` (which documents the *opponent*
binary) and `OPPONENTS_ANALYSIS.md`. This file is a **summary with provenance**, not a source of
truth: the authoritative places are

| thing | authority |
|---|---|
| the constants themselves | `DogFightEnv/Release/student/controller_providers.py` |
| every measurement and its caveats | `COMPETITION_PLAN.md` §4.1, register rows F59–F81 |
| what to do on match day | `MATCH_DAY_RUNBOOK.md` §7.3 |
| current state / what is in flight | `SESSION_HANDOFF_2026-09-08.md` |

If this file and any of those disagree, **they win** — and fix this file.

---

## 0. One-line status

**Model 1 is decided, re-scored three ways, and still stands. Model 2 is built, packaged and
gated, but the measurement that chose its parameters was scored by a buggy scorer and is formally
re-opened.**

---

## 1. What a "model" is in this project

Not a checkpoint. Per `controller_providers.py:181`:

> A "model" here is nothing but a set of controller constants over the **same code** and the
> **same DLLs**.

There is no second build, no bundle, no RL weights on the live path — `MODE = "vptrack"`,
`BUNDLE_DIR = None`. The live path imports only numpy, gymnasium, pymap3d, yaml and filelock;
neither `ray` nor `torch` is reachable from it. The finals accept two artifacts, so "a model" is
one row in `MODEL_PROFILES`, and adopting a different one is a one-dict change.

Model 1's profile is **built from** the `SHIP_*` constants rather than copying them
(`controller_providers.py:196`), so the F44 single-source-of-truth guarantee holds and the two
cannot silently drift apart.

---

## 2. The two models, side by side

| parameter | **Model 1** `ship_6000_120_deck` | **Model 2** `prev_6000_90` |
|---|---|---|
| `engage_range_m` | 6000.0 | 6000.0 |
| `engage_los_deg` | 120.0 | **90.0** |
| `throttle_control` | True | True |
| `hard_deck_m` | 1000.0 | **0.0 (OFF)** |
| `deck_ttc_s` | 0.0 | 0.0 |
| defined at | `controller_providers.py:162` (`SHIP_*`) → `:196` | `controller_providers.py:226` |
| league candidate | `scripts/league.py:111` | `scripts/league.py:115` |
| role | every standard game; **required** | head-on only; **optional** |
| adopted | 2026-09-03 (F59/F60), confirmed 2026-09-08 | 2026-09-05 (F74) — **re-opened**, see §4 |

**The single differing knob that matters is LOS.** 120° hands the controller the stick early,
which pays in the offset beam merge every standard game starts from, and is exactly wrong
nose-to-nose at 3 km. Both configs are correct — for different geometries. That is the entire
reason the rules allow two artifacts.

Runtime selection is `DOGFIGHT_MODEL_PROFILE` → `get_model_profile()`
(`controller_providers.py:235`), which falls back to Model 1 on any unrecognised value **rather
than raising**: on match day an operator's typo must not take the process down, and a Model 2 that
silently becomes Model 1 loses at most the head-on edge.

---

## 3. Model 1 — `ship_6000_120_deck`

### Role

Plays every standard game. It is what qualifies us: Head-On mode is **결선라운드 only** (F75), so
**Model 1 alone must survive the entire group stage.**

### Provenance

Adopted on the F66 matrix: 15 pairs × N=150 = **2,250 episodes**, `match_base`, separation swept,
altitude randomised 1,000–7,700 m, speed 150–280 m/s, side randomised.

### Scores — read the scoring convention before quoting a number

| scoring | mean | minimax floor | note |
|---|---:|---:|---|
| F66, as published (legacy scorer) | 1.69 | 1.33 | only candidate whose worst column clears the 1.0 always-draw break-even |
| F78, corrected scorer (2026-09-08) | **1.75** | **1.35** | opponent ground impact = win, own crash = loss |
| 2026-09-08 A/B, fixed tree, N=100×5 | 2.18 | 1.34 | **control arm not landed — do not cite as established** |
| F81, self-play column excluded | unchanged by design | **1.60** | the pinned `aggressor` column (~1.34) was the floor in every table above; excluding it promotes the `cutoff` column, a real opponent. MEAN deliberately still includes self-play so every mean in the register stays comparable. See §5.1–5.2 |

Against the organizers' own cutoff binary, the scorer fix alone moved the record from
**53W/57D/40L → 70W/40D/40L** and the BO3 match win rate from **43.9% → 55.0%**, clearing the
organizers' stated >50% bar without running a single new episode.

Comparators from the same F66 matrix, for why the other two configs are not the main model:
`alt_8000_90_deck` 1.39 / 0.94 and `prev_6000_90` 1.39 / 0.98 — each loses three columns
decisively, where Model 1 loses only `aggressor`, narrowly (47W/54D/49L).

**This is the one decision in the project that no re-scoring has moved.** It wins the mean *and*
the floor under flat scoring, phased scoring, and both crash-bucketing conventions.

### Known leaks, quantified

- **Closure, not pointing.** vs `sniper`: nose-on ≤2° in 148/150 episodes, ever in the WEZ in
  37/150, 127 timeouts. vs `bt_only`: 150/150 nose-on, 31/150 WEZ. The draw decomposition says the
  same thing — vs `sniper` 69% draws of which 101/103 are `scoreless_nose_on`; vs `bt_only` 76%
  draws, 114/114 closure failures. **We win the angle fight ~99% of the time and reach weapons
  range ~25%.**
- **Side asymmetry (F67), now narrowed.** It reproduces against `cutoff` **and only** `cutoff`
  (−22.3 points, z = −2.80); the other four archetypes sit between z = −1.75 and +1.26 with
  inconsistent signs, and the pooled split shows no gap. So it is an extend-and-clock-specific
  leak, **not** "we fly the bad side in half of every match". Two direct fixes have already
  measured worse — do not reopen it.
- **Draw rates (corrected scorer, `match_base`):** `sniper` 68.0%, `mirror` 41.3%,
  `aggressor` 35.3%, `cutoff` 26.7%. These drive the Head-On reachability maths in §6.

---

## 4. Model 2 — `prev_6000_90` (adopted 2026-09-05, **parameter choice re-opened**)

### Role

Reachable **only** after games 1 *and* 2 both draw in a 결선라운드 BO5. Switching is optional,
one-way within that match, and the next match restarts on Model 1. Per the spec, submitting only
the main model is also legal — so Model 2 is a contingency, never the thing that qualifies us.

### What it was adopted on (F74)

The project's first head-on measurement at the organizer-confirmed **3,048 m** separation (F72):
4 candidates × 5 archetypes × N=60 = **1,200 episodes**, `--scenario-mode match_tiebreak`.

Expected BO3 points, mean / worst — **legacy scoring, see the correction below**:

| candidate | mean | worst |
|---|---:|---:|
| `prev_6000_90` | **1.64** | **1.18** |
| `m2_6000_90_deck` | 1.62 | 1.02 |
| `ship_6000_120_deck` (Model 1's config) | 1.57 | 0.44 |
| `alt_8000_90_deck` | 1.54 | 0.84 |

Decisive column was the cutoff: **19W/17D/24L (32% BO5)** against Model 1's config at
**11W/10D/39L (7%)**, loss-rate difference z = −2.74.

Two supporting results from the same campaign:

- **The hard deck was tested here, worked, and still lost.** `m2_6000_90_deck` cut self-crashes
  11/300 → 3/300 (and 5/60 → 1/60 against the cutoff) and scored *worse* on the legacy scorer.
  Read at the time as: those crashes were not free losses — the aircraft reaching the deck were
  already losing, and the guard also fires where the controller would have recovered.
- **Side symmetry cleared.** Paired forced-mirror run vs cutoff, N=25/side, same seeds:
  8/6/11 vs 9/6/10, gap −4.0% = **0.3σ**. (The *free post-hoc split* F74 also cited is worthless
  here — `initial_side` is numerical noise at LOS 0, proven by a forced `+1` run logging
  `+1:17 / −1:8`. Paired mode only, per F78.)

### What has since undermined it — three things, all from 2026-09-08

1. **The scorer that chose it had two bugs (F78).** `league.py` booked our own self-crash as a
   draw. F74's table above **reproduces only under `--legacy-scoring`** — verified byte for byte.
   Scored the way flying into the ground actually resolves, **`m2_6000_90_deck` takes the mean
   (1.62 vs 1.61) and the floor gap closes to noise.** So both supporting claims fail: *wins both
   ranking keys*, and *the hard deck was rejected on evidence* — the guard was rejected on a metric
   that scored the crashes it prevented as draws. **Status: re-decide on the corrected scorer.
   This is a re-scoring of episodes already in the repo, not a new campaign.**
2. **Its ranking floor was partly self-play (F81).** `ARCHETYPES['mirror']` is 6000/90 — the same
   relationship to `prev_6000_90` that `aggressor` has to Model 1. A symmetric matchup is pinned
   near 50% by construction. `_is_selfplay()` now excludes such columns from WORST.
3. **It has never been measured on the binary it would fly.** All 1,200 episodes ran on
   `AIP_BASE.dll` crc32 `4026508473` / 2,821,632 B. The shipped DLL is now crc32 `1131281049` /
   2,885,632 B (§5.3).

Related, and worth knowing before anyone treats 6000/90 as historically dominant: **the
"100/100 vs cutoff" in `CUTOFF_MODEL_REFERENCE.md` §9 does not reproduce (F80).** Re-run at that
exact fixed spawn on the current tree and the corrected scorer, `prev_6000_90` scores **18% win /
4% earned**. That number was a property of a materially different program.

---

## 5. The measurement basis — read this before trusting any table above

### 5.1 The roster has exactly one independent opponent

`league.py:211`. Of five archetypes, **only `cutoff` and `bt_only` are not our own controller**,
and `bt_only` never shoots. So there is one genuinely independent opponent, and it is the one we
almost never play.

| archetype | what it is | independent? |
|---|---|---|
| `cutoff` | the organizers' extend-and-clock binary | **yes** |
| `mirror` | 6000/90 — i.e. Model 2's config, on the target side | no (self-play for Model 2) |
| `sniper` | 2500/45 narrow envelope; GoGoSSung *and* HAnnamAir analogue, low confidence | no |
| `aggressor` | 6000/120 + deck — i.e. Model 1's config, on the target side | no (self-play for Model 1) |
| `bt_only` | rule-based floor, never shoots | no — sanity check only |

Read "beats `sniper` 94/100" as *a wide envelope beats a narrow one*, not as evidence about
GoGoSSung.

### 5.2 Two scorer bugs and three measurement defects were fixed on 2026-09-08

- Opponent ground impact booked as a draw (73 episodes across the shipped matrices) — fixed.
- Our own self-crash booked as a draw (68 episodes) — fixed. **This is the one that decided
  Model 2.**
- Spawn draw happened *before* the RNG was seeded, so 54 of 150 episode indices differed per file
  and common-random-numbers pairing held for only 64% of episodes — fixed and verified live
  (100 distinct spawn tuples across 5 archetypes = perfect pairing).
- Resume guard compared three column *names*, not the schema — fixed.
- Minimax floor was a self-play column (§5.1) — fixed via `_is_selfplay()`.

`--legacy-scoring` reproduces the old tables byte-for-byte, so every register number up to F76
stays checkable.

### 5.3 Which binary produced which number

| crc32 | size | date | what it is | scored? |
|---|---:|---|---|---|
| `4026508473` | 2,821,632 | ≤2026-09-05 | the tree every F66 and F74 episode was measured on | yes — all of §3–§4 |
| `1647762966` | 2,884,096 | 2026-09-06 | `Task_DefensiveSpiral` + compound HCA release gate, added with **no register row** | **never** |
| `1131281049` | **2,885,632** | 2026-09-08 | four BT defects fixed; **this is what is tracked in the repo today** | A/B in flight |

The 2026-09-08 fixes: `Task_Evade`'s unconditional cap and cooldown were dead code
(`BREAK_STALE_S == BREAK_TOTAL_MAX_S == 20.0`, so `elapsed > 20.0` was never true) → 18.0;
`Task_DefensiveSpiral` could not produce a spiral (`ShorterTurnDirection` flips sign exactly at
the node's own design geometry) → direction latched on the blackboard; the spiral's altitude floor
was dead code below Gate 0's 914 m → 1000 m; plus a degenerate cross-product guard at the shared
root.

**Swap the DLL and the Rule XML together.** The old DLL against the new XML hits an unregistered
`Task_DefensiveSpiral`, and per F70 that failure is caught in C++, printed to `std::cout`, and
turned into an **all-zero `ControlValue` that still handshakes and answers at 60 Hz** — a dead
submission and a healthy one are indistinguishable from outside.

### 5.4 One retained assumption, stated every time

The randomisation band **1,000–7,700 m / 150–280 m/s** is a **team decision, not an organizer
answer** (F76). The organizers confirmed only *that* altitude and speed are randomised. Both model
selections were measured entirely inside it. If the real band turns out materially different, the
thing to re-check is the *rankings*, not the individual numbers.

---

## 6. Match day — when to actually fly Model 2

Full procedure in `MATCH_DAY_RUNBOOK.md` §7.3, revised 2026-09-08. Summary:

**The 2026-09-05 "always switch" rule is withdrawn.** Same 1,200 episodes, correct scoring.
Probability of taking the match from games 3–5 once games 1 and 2 have both drawn:

| opponent | keep Model 1 | switch to `prev_6000_90` | switch to `m2_6000_90_deck` |
|---|---:|---:|---:|
| `cutoff` | 14.4% | 40.1% (**+25.8**) | 36.5% (+22.1) |
| `sniper` | 55.0% | 50.0% (−5.0) | 52.5% (−2.5) |
| `aggressor` | 45.6% | 41.4% (−4.1) | 50.0% (+4.4) |
| `mirror` | 52.9% | 42.9% (−9.9) | 36.5% (**−16.4**) |

**And the trigger self-selects against the one opponent switching helps.** Head-On needs two
draws, and our draw rates give P(two draws) = `sniper` 46%, `mirror` 17%, `aggressor` 13%,
`cutoff` **7%**. Bayes with a uniform prior:

> **P(opponent | Head-On triggered) = `sniper` 55.8% · `mirror` 20.6% · `aggressor` 15.1% ·
> `cutoff` 8.6%**

Under that weighting **every Model 2 candidate is negative** (−2.2 to −4.8 points). Without the
prior: switching pays only if P(cutoff-like | two draws) > **17–19%**, and our own draw rates put
it near **9%**.

So §7.3 is now a pre-specified conditional on **one observable**, decided before the day, not a
judgement call on it:

- **Switch** if the opponent declined the merge and banked the clock — long separation held, low
  closure, almost no gun passes, both aircraft near full health. That is the extend-and-clock
  signature, the one case where Model 1 collapses to 14.4%.
- **Do not switch** if the two draws were contested — merges happened, angles traded, damage on
  both sides, just not finished.
- **Ambiguous → do not switch.** The posterior sets that default.

**Prior expectation against all three A조 teams: do not switch.** GoGoSSung, Fight's on! and
HAnnamAir all finish by kill; none shows a clock-banking signature.

---

## 7. How the models ship

Both artifacts are one codebase, one DLL set, two baked-in constants.

| | Model 1 | Model 2 |
|---|---|---|
| exe | `JinjjaBoramae.exe` | `JinjjaBoramae_headon.exe` |
| ZIP | `JinjjaBoramae_APTGC2026_main.zip` | `JinjjaBoramae_APTGC2026_headon.zip` |
| displayed team name | `진짜보라매` | `진짜보라매_HeadOn` (suffix) |
| `DOGFIGHT_MODEL_PROFILE` | `1` | `2` |

**The two names are different fields and must never be interchanged** (F75/F76): the *displayed*
name is the registered team name verbatim, Korean retained; the "use English" clause governs
**filenames only**, which is what `SUBMISSION_NAME = "JinjjaBoramae"` is for. Verified: `진짜보라매`
(15 B) and `진짜보라매_HeadOn` (22 B) both round-trip the real 29-byte wire field.

Each ZIP holds **exactly two files at the root** — `<name>.exe` + `config.json`, no subfolders, no
library folders (onefile is mandatory, F75). Network config is fixed at `127.0.0.1:9999` and comes
from `config.json`; resolution order is env var → `config.json` beside the exe → the default.

The head-on exe cannot receive environment variables — an operator double-clicks it — so its two
distinguishing values are baked into a generated shim via `setdefault`, which still leaves a
manual override possible on the day (`scripts/build_exe.py:72`).

To rebuild:

```
python scripts/build_exe.py          # both models, then smokes each one
python scripts/package_release.py    # re-verifies, then writes both ZIPs
```

`package_release.py` refuses to package an exe older than any runtime asset, or a drifted spawn
preset — so "rebuild after changing the tree" is enforced, not remembered. Its old gate verified
the entry point by **grepping its source text**, which is exactly how F69's fatal `NameError`
shipped in `HEAD` unnoticed; it now launches the exe against a replay server and asserts
per-channel non-zero, varying commands.

**Do not skip `smoke_exe.py`** — see the all-zero failure mode in §5.3. Last verified on the real
binaries (F79): 600/600 frames answered, worst latency **20.9 ms** against a 166.7 ms budget,
**596 distinct commands of 600**, roll/pitch/rudder all varying per channel,
`Behavior Tree Initialized` present, both names round-tripping the real wire packer, and the two
exes genuinely flying different profiles.

---

## 8. Measured and rejected — do not re-sweep these

| knob / config | verdict | evidence |
|---|---|---|
| `engage_range_m` above 6000 | **saturated — identical, not similar** | 8000 and 12000 produce byte-identical rows to 6000: fights spawn at 610–880 m and close to a median of 20 m, so they never approach 6 km (F80) |
| `engage_los_deg` | **120 is the peak, bracketed both sides** | 90 → 29.4%, 140 → 36.4% (earned rate 0.0%), 180 known catastrophic (40→15%, 20→5%); control 54.5% (F80) |
| `ROLL_TAPER_DEG` | **worse at both values tested** | 5° → 21.2% (z = −2.97), 15° → 24.2% (z = −2.65); dwell 98.2 → 87.9 → 59.8 steps and damage **taken rises**. The roll-authority inversion is load-bearing, not a defect to suppress (F80) |
| `PITCH_FLOOR` | **harmful, monotonically from zero** | self-play 23.3% → 13.3% at floor 0.35, 6 kills → 0. Pulling at `cos(phi) < 0` pulls away from the solution |
| hard deck for **Model 2** | **worked and still lost** | 11/300 → 3/300 self-crashes, scored worse — but see §4, this verdict depends on the buggy scorer and is re-opened |
| hard deck for **Model 1** | **keep it on** | at 120° Gate 0 never climbs: 6/50 self-crashes → zero, damage dealt 0.341 → 0.394 (F59) |
| throttle control | measured null, kept on | vs BT 73.3% → 70.0%, self-play 23.3% → 26.7% |
| F67 roll boost | **do not reopen** | two direct fixes already measured worse |

---

## 9. Open items on the models

1. **Land the 2026-09-08 A/B and decide the tree.** Adoption gate: mean up **and** minimax floor
   not down, on the corrected scorer. If it does not clear, `git checkout HEAD --` the four files
   and freeze on the measured binary — that is a result, not a failure. Then rebuild both exes
   from whichever binary wins.
2. **Re-decide Model 2's candidate** — `prev_6000_90` vs `m2_6000_90_deck` — on the corrected
   scorer. Re-scoring only; the episodes exist.
3. **Screen future knob sweeps on WEZ-entry rate, not win rate.** It is the strictly necessary
   condition (0 kills in 487 episodes without it) and separates at far lower N.
   `league.py --summarize` prints it.
4. **The 3,000 ft start separation has never been evaluated** (F78) — α=0 and α=180 collapse to the
   same fraction, so 914.4 m never occurs and 609.6 m is double-weighted. One-line fix that
   invalidates cross-run comparison, so land it *with* a sweep.
5. **Get the real altitude/speed band from the organizers** (§5.4). Cheapest thing that could still
   move any number.

---

## 10. Change log

| date | change | row |
|---|---|---|
| 2026-09-03 | Model 1 adopted: 6000/120 + deck 1000 | F59, F60 |
| 2026-09-04 | randomisation added to the matrix | F65 |
| 2026-09-05 | F66 N=150 matrix confirms Model 1; **Model 2 = `prev_6000_90` adopted**; team-name split resolved | F66, F74, F76 |
| 2026-09-06 | BT changed (`Task_DefensiveSpiral` + HCA gate) with **no register row** — invalidated 3,450 measured episodes | F77 |
| 2026-09-08 | four BT defects fixed and rebuilt; two scorer bugs and three measurement defects fixed; both exes built and gated; **Model 2's selection re-opened**; switch rule reversed to conditional | F77–F81 |
