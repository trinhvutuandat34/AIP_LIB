# AIP TGC 2026 — Project Analysis

> Companion to [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) (maps *where things are*),
> [COMPETITION_RULES.md](COMPETITION_RULES.md) (the official rules/schedule/scoring), and
> [COMPETITION_PLAN.md](COMPETITION_PLAN.md) (the strategy/execution plan built on top of this
> analysis). This file explains *how the system works and why it's built this way*, based on
> reading the actual source (`src/dogfight/**`, `student/**`) plus the reward-design slide deck.
> Where I couldn't verify something from code, it's flagged explicitly in §10 rather than
> asserted.
>
> Note: this file's citations to `Day_2_Lecture_Materials/...` refer to source material that
> produced this analysis but is not present in the current checkout at `D:\AIP\AIP_LIB\` — see
> `PROJECT_STRUCTURE.md`'s header for the full root-migration note.
>
> **Read before trusting §2.3 and §4 below**: a 2026-07-15 accidental full-tree revert undid the
> crash-routing reward fix and the range-based two-circle guard described in those two sections,
> and the team deliberately chose not to restore either (no plug-in hook exists for either one —
> see `PROJECT_STRUCTURE.md`'s dated "Current state" entry and `COMPETITION_RULES.md` §6.3 for the
> full detail). Both sections below are kept as accurate *design* documentation — this is how the
> platform worked from 2026-07-12 through 2026-07-14 and how it would work again if restored — but
> are flagged inline where they no longer describe the platform's current behavior.

## 1. What this actually is

A 1v1 within-visual-range (WVR) F-16 gun-dogfight, simulated in JSBSim, where the
"weapon" is a narrow boresight cone (2° wide, 500–3000 ft range) rather than a missile
model. There's no Pk roll or discrete hit/miss — **damage accrues continuously, every
physics tick you hold a valid firing solution on the opponent.** That single design choice
shapes everything downstream: reward design is about *time spent in a geometric cone*,
not about a sparse "did I hit" event. This is classic BFM (Basic Fighter Maneuvers) —
the "Top Gun" framing is literal, not just branding.

The project has two faces that share almost all code:
- **Training face**: JSBSim + Gymnasium env + Ray RLlib (PPO/SAC), fully local, fast iteration.
- **Competition face**: the same trained policy, swapped into a live Unreal Engine match
  over a custom UDP protocol, fighting other teams' submissions.

The bridge between the two is a single abstraction (`ActionProvider`, §6.2) — understanding
that one class explains most of the architecture.

## 2. The MDP formulation

### 2.1 Observation space

Three built-in observation modes are implemented in `src/dogfight/envs/observation.py`:
`classic12` (12-dim), `relative14` (14-dim), and `tactical16` (16-dim). A fourth path,
`custom`, is supported via `student/my_observation.py`. The manual also names `legacy37`
(37-dim) as a mode, but it is **not implemented in the student distribution** — `observation.py`
has no `legacy37` branch, so that mode silently falls through to `_build_classic12()` (12
dims, wrong shape). `experiments/README.md` confirms it is research-only, lives in the
internal `MyTrainEnv/`, and is not exposed to students. Do not use `legacy37`.

**`tactical16`** is the default recommended example and the only mode fully bounded to
`[-1, 1]`, but the manual explicitly states it is *not* a fixed "right answer" — students
are expected to design their own. The `tactical16` features:

| Idx | Feature | Notes |
|---:|---|---|
| 0–2 | ownship roll, pitch, yaw (norm.) | attitude |
| 3 | ownship speed (KCAS, norm. 0–600) | |
| 4 | ownship altitude (norm. 0–15000 m) | |
| 5 | ownship health (norm. 0–1) | |
| 6–8 | Δn, Δe, Δd to target | relative position, NED |
| 9–10 | ATA, AA (norm. ±180°) | see §3 — the two angles that define "who's behind whom" |
| 11–12 | LOS azimuth, elevation | |
| 13 | target health (norm. 0–1) | |
| 14 | in-WEZ flag (±1) | are you *currently* in firing position |
| 15 | pursuit score (smooth ATA×range gradient, →[-1,1]) | engineered tactical heuristic baked directly into the input |

Index 15 is worth noting: the designers didn't just shape the *reward* with an ATA×range
gradient, they also handed the *policy's input* a precomputed version of that same signal.
The agent doesn't have to learn to derive "am I roughly lined up" from raw geometry — it's
given the answer as a feature. That's a meaningful assist baked into the environment, not
something a student has to discover.

When writing a `custom` observation (`student/my_observation.py`), two optional declarations
expand the contract beyond the required `OBSERVATION_SIZE` + `build_observation(...)`:
`OBSERVATION_LOW` / `OBSERVATION_HIGH` (clip bounds, recorded in bundle metadata) and
`describe_observation()` (documentation function, shown in dry-run output). Neither is
required for training to run, but both are surfaced at inference time.

### 2.2 Action space

`Box([-1,1]^4)` = `[roll, pitch, yaw/rudder, throttle]`. Throttle is remapped internally from
`[-1,1] → [0,1]` (`DogFightEnv._to_sim_action`) — chosen so an **untrained network outputting
~0 still gives throttle ≈ 0.5** instead of idling the engine. Small but deliberate: it means
a freshly-initialized policy doesn't immediately stall/crash before learning anything.

The RL action is held constant for `step_ratio` physics ticks (`sim_hz=60`, default
`step_ratio=6` → one policy decision = 0.1 s of flight, 1/10th of sim rate). This same
`step_ratio` has to be mirrored as `--action-repeat` on the **Unreal inference side**
(`ProviderCommandPolicy.action_repeat`, default 6) — if a team changes one without the
other, the policy sees a different effective control rate at competition time than it
trained on. This is the single easiest cross-environment consistency bug to introduce.

### 2.3 Reward anatomy (`src/dogfight/envs/reward.py`)

| Component | Formula (informal) | Intent |
|---|---|---|
| `survival` | flat bonus/step | curriculum Stage 0 only — "don't crash" before anything else |
| `step` | constant (−0.01 default) | mild time pressure |
| `pursuit` | `pursuit_scale × max(0, 1−ATA/half_angle) × max(0, 1−range/pursuit_range)` | dense gradient toward "nose-on, closing" *before* the agent ever reaches the actual WEZ |
| `damage` | `damage_scale × (target_damage − ownship_damage)`, both phase-aware estimates as of 2026-07-16 (see below) | the WEZ-time-integrated hit/being-hit differential |
| `safety` | penalty below 600 m altitude | hard floor |
| `terminal` | win +100 / loss −100 / draw −30 / guard_fail −50 / **own crash −100, target crash +100** | dominates — by design, so shaping never out-competes the actual win/loss signal |

**Crash routing (fixed 2026-07-12, reverted 2026-07-15, restored in student space only — see the
callout at the top of this file):** a ground impact leaves `HEALTH` at 1.0, so without this fix
crashes fall through the health checks into `draw_reward` — and curriculum stages that set
`draw_reward` positive (defensive survive-to-timeout stages) literally pay the agent to fly into
the ground (real_eagle v3's `obfm_defensive` learned a 100% crash rate at +20/episode from
exactly this). The fix matches crash `end_condition`s *before* the health checks and routes them
to `crash_penalty` / `target_crash_reward` (falling back to `loss_reward` / `win_reward` when a
stage doesn't override them). **Currently this only lives in `student/my_reward.py`** — the
platform's own `src/dogfight/envs/reward.py` was reverted back to the pre-fix version 2026-07-15
and was not restored (no plug-in hook to reach it without crossing the hard boundary). Since
`real_eagle_v4.yaml` points `reward_module` at `student.my_reward`, actual training is unaffected
by the platform-side regression — but any code path that falls back to the platform's own
`compute_reward()` (e.g. a run with no `reward_module` override) will not have this fix.

`pursuit` exists specifically to solve the exploration problem: the real WEZ is a 2°-wide
cone, so a random/untrained policy will essentially never stumble into a positive `damage`
signal. The pursuit gradient gives reward everywhere in a wide funnel leading toward the
cone, long before the agent is actually inside it.

**`damage` is phase-aware too now (fixed 2026-07-16, user-requested):** `target_damage`/
`ownship_damage` above are no longer the raw values `single_agent_env.py` passes in — those are
computed against the platform's flat, non-widening cone (§2.3's WEZ table entry doesn't reflect
the real 3-phase rule, see `COMPETITION_RULES.md` §6.3), and there is no way to correct them from
student space: `update_damage()` mutates health inside the closed FighterSim object the instant it
runs, before any wrapper or reward function ever sees the resulting state. `student/my_reward.py`
now computes its own estimate instead, via two new `student/reward_lib.py` functions —
`match_wez_phase()`/`wez_damage_estimate()` — using the real 3-phase envelope. This fixes what the
reward teaches the policy to do; it does **not** fix episode termination, which still runs on the
platform's flat-cone health value regardless.

`student/my_reward.py` only has to satisfy the same five-argument-in / `(float, dict)`-out
contract — it doesn't have to replicate this whole structure, but this is the reference
implementation the slide deck (§4) is teaching students to reproduce or improve on.

### 2.4 Termination (`src/dogfight/envs/termination.py`)

`terminated`: FDM numerical failure, altitude floor breach (either side), health ≤ 0
(either side), fuel exhaustion (either side), or — curriculum-only — a "two-circle guard"
failure (§5).
`truncated`: `max_engage_time` (300 s) or `episode_step_limit` (18000 steps — exactly
300 s × 60 Hz, so the two limits are designed to coincide).

Outcome (`win/loss/draw/crash/timeout`) is a separate classification layered on top of
`terminated/truncated` for metrics and curriculum advancement — the raw Gymnasium flags
alone don't tell you who won.

## 3. The tactical geometry vocabulary

Everything in §2.3 is built from a small set of geometric quantities, explained in
`Day_2_Lecture_Materials/reward_design_concept_slides.html` (worth opening directly for the
diagrams — summarized here):

| Term | Definition | Reward intuition |
|---|---|---|
| **LOS** | line from ownship to target | the basis every other angle is measured against |
| **ATA** (Antenna Train Angle) | angle between *my nose* and LOS | small = "I'm pointed at them" — `cos(ATA)` is the standard smooth signal |
| **AA** (Aspect Angle) | angle between *target's tail axis* and reverse-LOS | small = "I'm at their nose" (nose-on), large/180° = "I'm at their dead six" (behind them) — verified against `AspectAngleUpdate.cpp`; the native BT's `MyAspectAngle_Degree` uses this convention, opposite to the Python side's `GeoMathUtil._get_aspect_angle()` (see `CLAUDE.md`'s aspect-angle sign trap note) |
| **HCA** (Heading Crossing Angle) | angle between the two nose vectors | ≈0 same-direction (chase), ≈180° head-on, ≈90° crossing |
| **WEZ** | the cone (angle + range band) where weapons land | ATA-small AND range-in-band simultaneously |
| **Closure** | rate of change of range | + closing, − opening; should taper as range shrinks or you overshoot |
| **Energy** | altitude + speed (specific energy) | a resource for future maneuvers, not a reward to chase directly |
| **One-circle / Two-circle** | post-merge turn geometry | same-direction turn rewards smaller turn radius; opposite-direction turn rewards higher turn rate |

The slide deck's own framing of the central design tension is worth repeating verbatim
(paraphrased): reward on ATA and AA *together*, never alone — rewarding ATA alone teaches
"point at them" even as they slide behind you; rewarding energy too strongly teaches
"circle at high altitude forever." Every component in the table in §2.3 exists to avoid one
specific degenerate policy.

## 4. Curriculum learning design (`src/dogfight/ai/curriculum.py`)

15 stages, strictly progressive, each overriding reward weights, episode length, and
opponent behavior:

| # | Stage | Opponent | What it isolates |
|---:|---|---|---|
| 0 | `flight_survival` | none (fixed) | don't crash; throttle/attitude control only (pursuit & damage rewards zeroed) |
| 1 | `target_pursuit` | fixed | point at and close on something |
| 2 | `wez_approach` | loitering (non-threatening) | actually enter the firing cone |
| 3 | `autopilot_pursuit` | moving, non-reactive | pursue a moving but predictable target |
| 4–13 | `two_circle_headon_a{000..180}` | live Behavior-Tree opponent | a 10-step sweep of merge geometry (α = 0°→180°) against a *reactive* adversary, each with a "guard" constraint (below) |
| 14 | `full_dogfight` | live Behavior-Tree opponent | the real task, no scaffolding |

real_eagle runs don't use this built-in list directly: `student/my_curriculum.py`
(`curriculum.stages_module`) composes the 4 skill stages + 2 OBFM asymmetric-start stages +
its own **5-alpha** two-circle ladder (0/45/90/135/180, with `pursuit_range_m` widened to
8 km so the 1–5.5 km spawns sit inside the shaping gradient, plus a small smooth
`advantage` term) + `full_dogfight` extended to 1500 iterations. See the module docstring
for the v1/v3 post-mortem that motivated the rebuild.

This exists because a randomly-initialized policy has ~zero chance of ever winning against
a competent reactive opponent cold — there's no reward gradient to climb. Each stage is a
restricted MDP that's solvable, and `advance_conditions` (rolling-average thresholds over
the last 10 iterations — e.g. `crash_rate_max`, `win_rate_min`, `ep_min_distance_max`) gate
progression to the next one. `wez_approach` is the one exception with an OR-condition
(win rate *or* sustained WEZ contact) rather than requiring all conditions simultaneously.

The α-sweep stages carry a "guard" that terminates the episode as a loss when violated.
**Redesigned 2026-07-12, reverted 2026-07-15, left reverted deliberately (see the callout at the
top of this file)** — the original ATA-limit form (fail when post-merge ATA exceeded 90° at α≤80,
or α+10° at α≤140) was measured **unpassable** across every real run: v1 stages 4–8 and v3 stages
6–13 ended 93–100% of episodes as guard-fail losses with zero wins and ~zero WEZ contact. Two
mechanisms: (1) at the merge pass the LOS sweeps aft faster than any achievable turn rate, so
low-α episodes always died seconds after the mandatory merge whatever the policy did; (2) an
unavoidable discounted terminal penalty rewards whatever *postpones* it, so the guard actively
trained merge **avoidance** (v3's late stages learned to triple episode length with zero win-rate
change — consistent with the historical "closes to WEZ then diverges to 50 km" eval). The fix was
a **range-based disengagement check**: fail only when range exceeds `max_range_m` (default 8 km;
every two-circle spawn is ≤5.5 km) — fighting never triggers it, fleeing triggers it quickly, and
delaying the penalty means *staying engaged*.

**Current state (2026-07-16): `envs/termination.py` is back to the unpassable ATA-limit form
described above** — the accidental 2026-07-15 revert undid this fix, and it wasn't restored
(`termination.py`'s guard check is hardcoded with no plug-in hook, and no bytecode trace of the
fixed version survived the revert to recover from — see `PROJECT_STRUCTURE.md`). Rather than
re-enable a guard known to train avoidance, `student/my_curriculum.py`'s reconstructed two-circle
stages ship with `geometry_guard` **disabled entirely** — weaker than either version (no guard at
all, relying on `max_engage_time`/`episode_step_limit` truncation alone to bound a
runaway-avoidance episode), but doesn't actively train the avoidance behavior the ATA guard did.
Full post-mortem (of the fix, as designed) in `envs/termination.py`'s docstring — read alongside
this note, not as a description of current behavior.

## 5. System architecture: training → submission

```
JSBSim (physics, native)
   ↕  JSBSimAIPLib.dll / FighterSim.py / JSBSimWrapper.py
DogFightEnv (Gymnasium env, src/dogfight/envs/single_agent_env.py)
   ↕  reset()/step(), tactical16 obs, 4-dim action
Ray RLlib (PPO/SAC, new API stack / RLModule)
   ↓ produces
"lightweight bundle" (metadata.json + policy_weights.pkl.gz)
   ↓ loaded by
RLActionProvider  ──┐
BTActionProvider  ──┼── ActionProvider abstraction (shared interface)
HybridActionProvider┘
   ↓ used identically by...
run_local_dogfight.py (local JSBSim validation)        ←  same code path, fast iteration
run_unreal_inference.py / student/my_submission.py     ←  same code path, live competition
   ↕  custom struct-packed UDP protocol (src/dogfight/unreal/protocol.py)
Unreal Engine battle server (DogFightViewer.exe)
```

### 5.1 Why `ActionProvider` is the load-bearing abstraction

One interface — `reset()` / `compute_action(context) -> ActionResult` / `close()` — is
implemented three ways and reused in three contexts:

- **As the training opponent**: `target_action_provider` inside `DogFightEnv`, so the
  built-in BT opponent and a custom/RL opponent are interchangeable during training.
- **For local validation**: `run_local_dogfight.py` wires an `RLActionProvider` (your
  trained bundle) against a `BTActionProvider` (the baseline) outside of RLlib entirely.
- **For competition**: `run_unreal_inference.py` wires the same providers into
  `ProviderCommandPolicy`, which talks UDP to the Unreal server instead of JSBSim.

The practical upshot: whatever you validate locally with `run_local_dogfight.py --save-log`
is running the *exact same inference code* that will run in the live match — only the
state source (JSBSim vs. Unreal-streamed `PlaneInfo`) changes. That's a deliberately
narrow seam, which is good engineering, but it's also exactly where a sim-to-real(-ish)
gap could hide (see §10).

The hybrid provider deserves a specific callout: its `residual` mode computes
`BT_action + scale × RL_action` for roll/pitch/rudder, i.e. **the hand-coded BT is the
safety net and RL only nudges it**. A team unsure of their trained policy's robustness can
submit this instead of pure RL — it's a built-in fallback strategy, not just an
experimental option. Four 2026-07-14 fixes to know about (found after the hybrid lost every
practice match). **Important placement note:** these do NOT live in the stock
`src/dogfight/ai/*` classes — that package is a hard no-edit boundary (§8 / `CLAUDE.md`).
They live in the editable `student/inference_providers.py`, which *subclasses and composes*
the platform: `RemappedRLProvider` (subclass of `RLActionProvider`) and
`StudentHybridProvider`, wired in from the three inference entry scripts. The fixes: (1)
`RemappedRLProvider` restores the training-side `(throttle+1)/2` remap at inference by
running the inherited pre-clip `_compute_module_action()`, remapping, *then* clipping —
before this, RL throttle reached the sim/wire in the wrong unit system on every path (the
stock `clip_action` floored the negative half to idle, so half the output range collapsed to
engine-idle); (2) `StudentHybridProvider`'s residual re-centers the **throttle** channel
around policy-neutral 0.5 (`+ scale × (2·RL_throttle − 1)`) so RL can also *reduce* throttle
below the BT's baseline — added raw, a [0,1] throttle could only ever push up, overriding
maneuvers that deliberately throttle down (e.g. `Task_LagPursuit`'s 0.6 closure control);
(3) `switch` mode gets a real default selector (`switch_by_range`: BT inside 2 km, RL beyond
— matching the BT's own close-combat gates), where the stock class, with no selector ever
wired up anywhere, silently ran 100% pure RL; (4) entry points fail fast at startup if the
loaded bundle's recorded `obs_mode`/`observation_module` don't match the runtime observation
config (`verify_bundle_observation` in `student/inference_providers.py`) — two same-length
modes would otherwise feed wrong features with no error. The stock
`src/dogfight/ai/hybrid_action_provider.py` remains as-is (reverted to original); the
submission path just uses the student composition instead.

### 5.2 The Behavior Tree opponent is native C++, and it's dual-purpose

`AIP_DCS/` (was `Update/BehaviorTree/AIP_DCS/` before the folder reorg — see
`PROJECT_STRUCTURE.md`) is a Visual Studio C++ project compiling into the DLLs
(`AIP_BASE.dll`, `AIP_BASE_target.dll`) used two ways: as the **standard training
adversary** for curriculum stages 4–14, and as a **submittable competition mode**
(`MODE="bt"` in `my_submission.py`) — a team could enter the competition on a tuned BT
rule-set (`Rule_real_eagle.xml`-style) alone, no RL involved, or blend it via Hybrid.

**Confirmed 2026-07-07 — neither the source nor the compiled binaries have real tactics.** Both
shipped rule files (`DogFightEnv/Release/Rule.xml` and `Rule_forTraining.xml`) route every branch
to a `Task_pure` or `Task_Empty` leaf. `AIP_DCS/BehaviorTree/BT_Content/Task/Task_pure.cpp`'s
body is a byte-identical copy of `Task_Empty.cpp` — both just set a virtual aim point 10,000
units straight ahead of the current heading, with no pursuit/attack/evasion logic. Combined with
the missing maneuver-node sources noted in `CLAUDE.md` (`JinkingTurn`, `HighYoYoUp`, `LunchMSL`,
`WeaponSelect`, `JinkingTurnSelector` — present only as stale `.obj` build leftovers, no current
`.cpp`), the checked-in source tree cannot produce a tactically competent BT if rebuilt today.

This was then verified empirically against the *compiled* binaries, not just the source: running
`AIP_BASE.dll` vs `AIP_BASE_target.dll` head-to-head for 90s
(`run_local_dogfight.py --ownship-backend bt --target-backend bt --save-log`) shows both aircraft
merge at ~t=8s and then fly on essentially their original headings for the remaining 77s (yaw
drifts only `0°→14°` / `180°→173°` — a passive drift, not a turn), dealing **zero damage** to
each other over the full engagement. **The compiled DLLs share the same "fly straight" behavior
as the stub source, not a richer earlier snapshot.**

The good news, found while scoping the fix: the control pipeline is a much smaller surface than
"implement a flight controller." `CPPBehaviorTree.cpp`'s `RunCPPBT()`/`Step()` ticks the tree,
reads `BB->VP_Cartesian` (a 3D aim point), and hands it to `Controller.GetStick(...)` —
`Geometry/Controller_CY.cpp`, an existing, already-working low-level guidance controller that
converts "here I am, here's where I want to point" into roll/pitch/rudder. **Task nodes only
ever need to set an aim point, never compute stick values themselves.** `Task_Empty`/
`Task_pure`'s entire defect is one line
(`VP_Cartesian = MyLocation_Cartesian + MyForwardVector * 10000`, i.e. "aim ahead of my own
nose, ignore the target"), and `SelectTarget` has already populated
`BB->TargetLocaion_Cartesian` with the real target position every tick — so a minimal real
pursuit fix is close to a one-line change. Separately, **throttle is hard-coded** —
`RunCPPBT()` sets `Throttle = 1.0f` unconditionally with a comment reading (translated) "throttle
placeholder — plug in the AI's value here"; `CPPBlackBoard` has a `float Throttle` field but
nothing writes it from a Task node and `RunCPPBT()` doesn't read it either. Also: `DECO_BFMCheck`
compares `BB->BFM` against `OBFM`/`DBFM`/`HABFM`/etc., but nothing in the current source ever
assigns `BB->BFM` away from its default `NONE` — it's dead code until a BFM-situation classifier
exists.

**Update 2026-07-07 — `Task_pure` is now a real pursuit node, and two more bugs surfaced fixing
it.** `Task_pure.h`/`.cpp` were repaired (they wrongly declared `Action::Task_Empty` again — a
copy-paste leftover) to implement genuine pure pursuit (`VP_Cartesian = TargetLocaion_Cartesian`),
wired into the build and into `Rule_forTraining.xml`. Getting this far surfaced two independent,
pre-existing problems: **(1)** the project did not compile at all before this fix — the same
`Task_pure.h` declaring `Action::Task_Empty` collided with the real `Task_Empty.h` — so the
shipped `AIP_BASE.dll`/`AIP_BASE_target.dll` must predate that regression; **(2)** the compiled
DLL's Rule XML loader had a hardcoded absolute path into a **second, separate, untouched copy of
this entire project** at `C:\Users\User\Desktop\AIP\AIP_LIB\`, meaning `bt_rule_manager.py`'s
`activate_rule_xml()` — and therefore every documented way of swapping in a team-specific rule
file — was silently having no effect on the compiled DLL at all. Fixed by resolving the path
relative to the DLL's own on-disk location (`GetModuleFileName`), which also turned out to be
necessary for a second reason: a plain relative path failed too, because something in the JSBSim
init path changes the process's working directory before `CreateBehaviorTree()` runs. Verified:
both aircraft now show large, active heading swings (100–270° within single 5s samples) instead
of the previous 0°→14° passive drift. Zero damage still resulted in that test run — expected, not
a failure, since two aircraft running identical pure-pursuit logic against each other is known to
produce an inefficient tail-chase standoff rather than a gun solution.

**Update 2026-07-07, continued — the tail-chase standoff turned out to have a much bigger root
cause than "pure pursuit is geometrically inefficient."** Added a `Task_LeadPursuit` node (aims
at the target's predicted position using its velocity, not just its current position) for the
long-range branch, keeping precise pure pursuit for short range. The first rebuild produced an
*identical* result to before (reward matching to 4 decimal places, trajectories byte-identical
for the first ~28s) — a sign the new branch wasn't actually being exercised, not that the new
code was wrong. Tracing `ChangeData()` (`LibMain.cpp`) and `Step()` (`CPPBehaviorTree.cpp`) found
why: **`BB->Distance`, `BB->MyLocation_Cartesian`, and `BB->TargetLocaion_Cartesian` were mixing
latitude/longitude in degrees with altitude in meters in one Euclidean distance calculation.**
`ChangeData()` packs raw `(lat_deg, lon_deg, alt_m)` into the location fields with no geodetic
conversion; `Step()` *does* properly convert this to true local Cartesian meters via
`LLAtoCartesian()`, but that conversion was silently discarded for both sides — commented out
entirely for the enemy (a raw passthrough was substituted), and computed-but-never-used for
self (the blackboard assignment referenced the original unconverted parameter due to a
`MyInfo`/`Myinfo` case-only variable name collision). Net effect: `BB->Distance` was a
near-meaningless number dominated mostly by altitude delta, not true 3D range, so
`DistanceCheck Greater 2000` almost never fired — and every other node built on relative
position (`AspectAngleUpdate`, `CheckSight`/LOS) inherited the same corruption. This is not
something introduced by this session's changes — it predates all of it. Fixed both sites to use
the properly-converted Cartesian values (same `OriLAT`/`OriLOn` reference origin for both sides).
Result: the same 90s BT-vs-BT test now ends in `end_condition: target destroyed` at ~35s —
the first confirmed kill in this entire investigation, up from zero damage across every prior
run.

**Update 2026-07-08 — throttle wired up, evasion added, and a total absence of altitude-safety
logic discovered and fixed.** Throttle was hardcoded to `1.0f` in `RunCPPBT()`, completely
disconnected from the BT; now reads `BB->Throttle`, which `Task_Pure`/`Task_LeadPursuit` set
per-range. A new `Task_Evade` breaks away when `BB->EnemyInSight_Target` is true. Testing at the
real 200s match length (up from 90s) surfaced something more important than either of those: the
target aircraft crashed (`end_condition: target altitude below min`) via a slow, steady dive from
~10,000 m to ~300 m over 140 seconds — not a glitch, and not something introduced by this
session's changes. **This BT, in every version including the original stub, has never had any
altitude/Hard-Deck safety logic at all** — it only started being able to matter once the tree
could actually turn and dive. Since Hard Deck violation is instant-loss (`COMPETITION_RULES.md`
§5), a new `Task_ClimbToSafeAltitude` node was added as the *first* Fallback priority (ahead of
evasion and pursuit) — self-checks altitude, triggers a climb below 914 m (~3000 ft). Re-verified
at the full 200s length: both aircraft now survive the entire match, minimum altitude reached was
936 m. Full detail: `COMPETITION_PLAN.md` §5.1.2–§5.1.4.

### 5.3 The Unreal wire protocol is intentionally minimal

`src/dogfight/unreal/protocol.py` defines ~10 struct-packed message types (`MT_PlaneInfo`,
`MT_CMD`, `MT_Damage`, `MT_ClientInfo`, …). A client joins with a team name + `AIType`
enum (`RuleBased` / `ReinforcementLearning` / `SupervisedLearning` / `Fusion`), receives
`PlaneInfo` (position/rotation/velocity) for both aircraft each frame, and replies with a
`CMD` (roll/pitch/yaw/throttle). The Unreal server is authoritative for physics during a
live match, the same way JSBSim is authoritative during training — they're not the same
flight model, which is the most important open question in §10.

## 6. Training infrastructure

- **Ray RLlib 2.54.0**, new API stack (`RLModule`-based inference; `rl_action_provider.py`
  falls back to legacy `Policy.set_weights` only for old-API compatibility).
- **PPO and SAC** both supported; SAC is the recommended default starting point.
- **LSTM/recurrent (SAC+LSTM ≈ RNNSAC)** requires a hand-applied patch to Ray's own source
  (`RLLibLstm/tools/apply_rllib_sac_lstm_patch.py`, with before/after trees and a guide) —
  Ray 2.54's new API stack doesn't natively support this combination well. The patch enables
  three modes: `actor_only` (actor uses LSTM+MLP; Q networks remain feedforward), `actor_critic`
  (recurrent Q/twin/target-Q too), and `sequence_v1` (YAML-controlled layer sequencing). When
  loading an LSTM bundle, always check `metadata.json` for three fields: `use_lstm_sac`,
  `lstm_scope`, and `max_seq_len` — these must match between the training run and wherever the
  bundle is loaded (local validation, Unreal submission); mismatch causes silent misbehavior,
  not an error. The README explicitly scopes this as an advanced/optional path, separate from
  the normal student template.
- **YAML experiments** (`scripts/run_experiment.py`) are a reproducibility layer over raw
  CLI flags — algorithm, reward/observation module paths, and checkpoint policy all live
  in one file instead of a remembered command line.
- **Three resume methods, different state preservation** — choosing wrong one corrupts
  experiment comparisons:
  - `--restore-checkpoint <path>`: restores policy + optimizer + replay buffer; for resuming
    the exact same interrupted training run. Submission never needs this.
  - `--init-bundle <path>`: restores policy weights only; for seeding a *new* experiment from
    a good policy. The result is a new run, not a continuation.
  - `--resume`: curriculum resume; progress state is tracked in `curriculum_state.json`.
  - **One-line rule**: never combine `--restore-checkpoint` and `--init-bundle` in the same
    command — weight-only restart misread as checkpoint resume silently diverges in
    optimizer/replay state and makes cross-run comparisons unreliable.

## 7. Observability tooling

- `tools/dashboard.py` unifies a **Training** tab (reward curves etc. from `metrics.jsonl`)
  and a **Replay** tab (Tacview-style CSV trajectory playback) in one browser app. A prior
  PyVista-based 3D viewer was explicitly removed in favor of this.
- **`policy_probe`**: every N iterations, feeds a fixed canned observation through the
  current policy and logs the raw action output (+ LSTM state norm if recurrent). This
  answers "is the network's output even changing?" independent of whether reward is
  informative yet — useful in the early curriculum stages where reward is sparse.
- **`engagement_log`**: periodically runs a short real evaluation episode and writes a
  Tacview-replayable CSV, so you can literally watch the dogfight rather than only read
  numbers. The slide deck's final checklist explicitly warns against trusting reward
  curves alone — "only the actual trajectory shows whether reward and intent agree."
- **Key dashboard scalars** (the manual names these four as the primary diagnostic set):
  `reward_mean` (learning stability trend), `crash_rate` (action aggressiveness proxy),
  `ep_min_distance` (closest approach — diagnoses pursue vs. evade behavior),
  `ep_wez_steps` (steps spent *inside* the firing cone — direct weapons-employment-time
  measure). Win rate alone is explicitly insufficient; read these four together to understand
  *why* an outcome occurred.
- **Reward component naming convention**: keys in the `components` dict returned by
  `compute_reward()` are logged as `ep_reward_<name>` in `metrics.jsonl`. Name them
  descriptively — they appear as individual dashboard scalars alongside the four above.

## 8. What's deliberately out of scope (for students)

- `reward.py` raises `ValueError` if `reward_config["mode"]` isn't `default` — non-default
  modes like `ref_old_1vs1` exist only in an internal `MyTrainEnv/` tree the README
  references but that isn't part of this distribution. The `Release_260529/` codebase is
  an intentionally simplified cut of a larger internal instructor codebase.
- **ONNX inference is described, not implemented**: the README lays out the adapter
  pattern you'd need (train → export ONNX → wrap in an `ActionProvider`) but
  `run_local_dogfight.py`/`run_unreal_inference.py` only natively load RLlib lightweight
  bundles today. Anyone wanting ONNX has real adapter code to write, not a config flag.
- Legacy scenario/reward paths (`ref_old_random`, the hardcoded `REF_OLD_RANDOM_SCENARIOS`
  table in `single_agent_env.py`) are vestiges of that internal lineage, kept for
  backward-compatibility/reference rather than the recommended path.

## 9. Default scenario, concretely

Out of the box (`DEFAULT_ENV_CONFIG`): ownship spawns at `(N=1000, E=0, alt=7000m, hdg=0°,
300 m/s)`, target at `(N=6000, E=0, alt=7000m, hdg=180°, 300 m/s)` — i.e. co-altitude,
~5 km apart, flying directly at each other at ~580 kt closure. That's a head-on merge by
default; the curriculum's α-sweep (§4) is explicitly about generalizing away from this one
fixed geometry toward arbitrary merge angles.

## 10. Open questions / things to verify before relying on them

- ~~**Is the compiled native BT (`AIP_BASE.dll`/`AIP_BASE_target.dll`) actually tactically
  competent?**~~ — **RESOLVED, and not in the hoped-for direction.** See §5.2 above: verified by
  direct 90s head-to-head run that both compiled DLLs just fly straight after the merge and deal
  zero damage. This forces a real decision on the Hybrid/BT strategy — see `COMPETITION_PLAN.md`
  §5.1 for the evidence and the options.
- ~~**Unreal-side state completeness**~~ — **RESOLVED 2026-07-08**, confirmed by static
  analysis, no live server connection needed. `PLANE_INFO_STRUCT = struct.Struct("<iQb3f3f3f")`
  (49 bytes — matches every captured packet in `logs/unreal_packets/` exactly) and the
  `PlaneInfo` dataclass have only `position`/`rotation`/`velocity` — no health or fuel field
  exists anywhere in the wire message. `MT_Damage` is a defined message-type ID with **no
  struct and no handler** in `client.py` (only `_handle_set_plane_id/_init/_game_control/
  _plane_info` exist) — if the server sends it, it's silently dropped. `plane_info_to_state()`
  writes only indices 0–8 into a 51-zero array, full stop. And `_build_tactical16()` reads
  `state[StateIndex.KCAS/ALT/HEALTH]` directly (not derived from the always-populated position/
  velocity fields) — so it's not just HEALTH/FUEL, **ownship speed and altitude break too**,
  even though those are physically present in the packet. Net: 4 of `tactical16`'s 16 features
  (ownship speed, ownship altitude, ownship health, target health) are permanently `0.0` during
  every live match. Possibly not a bug so much as a real protocol limitation — `COMPETITION_RULES.md`
  §4's "Perfect State Information" description says opponent "position/attitude/speed", not
  health, and the wire format matches that exactly. Full detail and the response options:
  `COMPETITION_PLAN.md` §5.2.
- ~~**Competition format itself** (match count, scoring, tournament structure, deadlines)~~ —
  **RESOLVED.** Extracted from the Day 1 kickoff deck and written up in full in
  [COMPETITION_RULES.md](COMPETITION_RULES.md): Swiss-league prelims (min. 3 matches) → top 8 +
  4 wildcards → four groups of 3 (Bo3 round-robin) → round-of-8 single-elimination (Bo5), plus
  the three-phase widening damage cone, the 200s match clock, and the 10,000+ ft head-on
  tie-break. Cross-checked there against this codebase's static single-phase WEZ (§2.3 above)
  and the 300s/18000-step default episode length, both of which don't match the live rules —
  see `COMPETITION_RULES.md` §6.3 and §5 for the specifics and what to override.
- **`AIP_LIB.zip`** (440 MB) and **`교전 뷰어 사용 메뉴얼.pdf`** (Engagement Viewer manual) —
  as of 2026-07-07, neither file exists anywhere in this checkout (confirmed by search), so this
  is moot rather than pending; whatever they contained wasn't carried over into
  `D:\AIP\AIP_LIB\`.
