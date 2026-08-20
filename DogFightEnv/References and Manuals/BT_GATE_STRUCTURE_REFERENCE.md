# BT Gate Structure Reference — `Rule_real_eagle.xml` Walked Top-to-Bottom

**What this file is for:** a structural companion to the other four BT references, organized by
**tree execution order** instead of by doctrine concept or issue history. Read this to answer
"what does the tree actually try, in what order, and why" in one pass. For depth, go to:

- **`COMPETITION_PLAN.md` §4.1 section G** — doctrine-concept → `Task_*` class → executed-or-not
  table, plus the doctrinal corrections it drove (F12, F14) and the rate-band check. This file
  and section G describe the same tree from two different organizing principles; neither repeats
  the other's detail.
- **`BFM_REFERENCE.md`** — geometry/pursuit-curve doctrine, mapped to the `.cpp` service files
  (`AngleOffUpdate.cpp` etc.) that compute the blackboard fields this file's gates read.
- **`BFM_ACM_Reward_Engineering_Reference.md`** — the same geometry, framed for reward/observation
  design rather than the BT.
- **`BFM_MANEUVER_GAP_REFERENCE.md`** — maneuvers and doctrine concepts with **no** node in this
  tree at all (Split-S, sliceback, pitchback, the three axioms, control zone/bubble, bugout,
  vertical-merge/God's-G).

---

## Status (updated 2026-08-20): the fix below landed 2026-08-13 and the tree runs

**Superseded — kept for history.** This section originally warned the tree described below did
not execute at all. **`COMPETITION_PLAN.md` 4.1 F25 (2026-08-11, ROOT CAUSE, fixed 2026-08-13,
commit `5412a79`):** BehaviorTree.CPP builds a control node (`<Sequence>`/`<Fallback>`) with
**zero children** whenever it carries a `name=` attribute. 17 of the 20 composite nodes in this
file were named and therefore built empty; only the 3 anonymous ones (children counts 1/8/9) built
correctly, so the only nodes confirmed to have ever executed pre-fix were
`Gate0_ClimbToSafeAltitude` and `Tail_SingleSideOffset`. **The fix (dropping `name=` from the 17
control nodes, XML-only) is applied and verified by gate-trace instrumentation**: all 17 maneuver
nodes across all five gate blocks now execute where exactly 2 ever had. Every gate described below
is therefore live, current behavior, not a forward-looking description — with one further update
since: Gate 1's Jink branch gained an own-ATA<90° carve-out on 2026-08-20 (see below), fixing a
capability hole F25 revealed (`Task_Evade` was starved).

**F23's inverted-`UpDown`-sense hypothesis (open as of the original writing) is refuted, not
confirmed.** The `Gate2_BeamMerge` FAILURE it observed was a symptom of the F25 bug (the gate's own
wrapper was one of the 17 empty-building nodes), not an inverted comparison operator — F25's root
cause fully explains the observation without needing to invert any gate's meaning. Treat threshold
directions below as written and confirmed-correct.

---

## 0. Every tick, before any gate: the blackboard update chain

Both aircraft run this `Sequence` first, unconditionally — it is one of the 3 anonymous
(therefore working) composites:

```
SelectTarget → DirectionVectorUpdate → DistanceUpdate → CheckSight
  → AngleOffUpdate → AspectAngleUpdate → EnergyStateUpdate
```

This populates `BB` (the blackboard) with everything the gates below read: target selection,
range, line-of-sight/ATA (`CheckSight`), HCA (`AngleOffUpdate` — misleadingly named
`MyAngleOff_Degree`, see `BFM_REFERENCE.md` §1's angle-field naming trap), aspect angle
(`AspectAngleUpdate`), and `Es`/energy ratio (`EnergyStateUpdate`). Only after this chain
completes does the tree evaluate the big `Fallback` that Gates 0 through Tail live inside.

## Gate 0 — Survival (`Task_ClimbToSafeAltitude`)

Bare leaf, absolute top priority, unchanged since the original tree. Self-gates internally (no
XML-level distance/altitude decorator) — claims the tick only when altitude demands it, fails
through otherwise. **Confirmed working** — one of only two nodes proven to have executed.

## Gate 2.5 — Gun-solution hold (`Gate2p5_GunSolutionHold`)

```
DECO_DistanceCheck  Greater  152.4 m   (physical gun range floor)
DECO_DistanceCheck  Less     914 m     (WEZ max)
DECO_LOSCheck       Less     8°  Own ATA   (widened from 5° on 2026-08-05, pseudo-hysteresis)
Task_GunTrack                             (PD-controller tracking, not a discrete-branch aim)
```

**Position history matters here.** Originally sat between Gate 2 and Gate 3. Moved directly under
Gate 0 on 2026-08-06 after measuring that the old position meant Gate 1 (threat reaction)
preempted it on essentially every tick a gun solution was live — 0/20 WEZ contact in BT-vs-BT and
BT-vs-autopilot, min ATA 4.4° reached but never converted. The file's own header comment
cites the doctrine principle directly ("offense beats defense... removing unnecessary defensive
branches made the tree stronger") while flagging that the specific thresholds it's compared
against come from a different competition (12° WEZ cone vs. this one's 1°) and must not be
copied blind. **Per F23, this gate is empirically load-bearing** — an A/B removal test (with the
F25 fix simulated) showed BT-vs-BT going from 22W/8D/0L to 21W/7D/2L and damage taken 0.000→0.049
when it's removed, i.e. it is the tree's only source of *defense*, not offense (dealt damage was
identical either way).

## Gate 1 — Immediate threat reaction (`Gate1_ThreatReaction`, a `Fallback`)

Three sequences, checked in this order, each self-gating its trigger internally in C++ (no XML
decorator on the base condition) but wrapped in two XML-level carve-outs added after real
competition-scenario audits:

```
Gate1_Notch_NotHeadOn:        HCA < 150°  →  Task_Notch
Gate1_JinkingTurn_NotHeadOn:  HCA < 150°, own ATA ≥ 8°, own ATA < 90°  →  Task_JinkingTurn
Gate1_TheBreak_NotHeadOn:     HCA < 150°, own ATA ≥ 8°  →  Task_Evade  ("The Break")
```

**Why the HCA<150° carve-out (2026-08-05/07):** without it, `Task_Notch`'s own C++ gate (any
enemy within 2000 m at 70–110° aspect) fires on literally the opening beam-merge geometry for
*both* aircraft simultaneously, which shadows all of Gate 2 before it ever gets evaluated — a
genuine near-head-on merge now defers to Gate 2 instead.

**Why the ATA≥8° carve-out on Jink/Break (2026-08-05):** without it, Gate 1 sits above Gate 2.5
with no angular awareness, so the instant a maneuvering defender's nose sweeps through the
attacker's forward hemisphere, Gate 1 yanks the nose off an in-hand gun shot. `Task_Evade`'s
class name is kept for history — it implements "The Break," not a generic evade.

**Why the own-ATA<90° carve-out on Jink only (2026-08-20, `Gate1_Jink_NotDefensive_OwnATA_Lt90`):**
`Task_JinkingTurn` (`AIP_DCS/BehaviorTree/BT_Content/Task/Task_JinkingTurn.cpp`) has no exit
condition beyond sight/range — it always returns `SUCCESS` once triggered — so as the first live
branch above it always won this Fallback whenever both Jink and Break were eligible, and
`Task_Evade` was structurally unreachable in that overlap. Measured on `obfm_defensive` (opponent
at our six, i.e. own ATA→180°): **1W/0D/29L, 27.51 damage taken, median min-ATA 174.2°**
(`COMPETITION_PLAN.md` 4.1 F26-DEFENSIVE) — pointed away from the threat the whole fight because
Jink, not Break, was flying it. A broader fix (reordering Break above Jink, gated on the
*target's* ATA/range) was tried and reverted — it fixed this but lost `match_base` 2:1 on the peer
rig (F26-GATE1-REJECTED). This carve-out is that postmortem's named refinement instead: gate Jink
on **our own** ATA. At own ATA ≥ 90° the bandit is outside our forward hemisphere — genuinely
behind our 3-9 line — so Jink's Sequence now fails there and the Fallback drops through to the
unchanged `Gate1_TheBreak` Sequence below. Below ATA=90° (neutral/offensive fights), Jink is
unaffected — same priority as before. Verified via the peer rig, shipping (`throttle_control=True`)
config: `obfm_defensive` win+draw share 3.3%→40.0%, damage taken −40%; `match_base` unchanged
within noise (13W/11D/6L vs a 14W/11D/5L control) — see F37-GATE1-DEFENSIVE-FIX for full numbers.

## Gate 2 — Merge & neutral-fight detection (`Gate2_MergeAndNeutralFight`, a `Fallback`)

```
Gate2_BeamMerge:      HCA > 120°, own ATA ∈ (45°,150°), dist < 2500 m         → Task_NoseToTailTurn
Gate2_HeadOnMerge:    HCA > 150°, own ATA < 20°, tgt ATA < 20°, 500–10000 m   → Task_NoseToNoseTurn
Gate2_OffCenterMerge: AA ∈ (30°,90°), dist 3000–5000 m, closing               → Task_LeadTurn
Gate2_NeutralFight:   dist < 2000 m, own ATA > 45°, tgt ATA > 45°            → scissors family*
```
\* nested `Fallback`: `Task_FlatScissors` → `Task_VerticalScissors` → `Task_RollingScissors`

`Gate2_BeamMerge` is the newest branch (2026-08-06) — added specifically because the official
match spawns antiparallel and abeam at 610–914 m, a geometry **none** of the other three
sub-branches or Gate 1 covers (Gate 1 needs HCA<150 and gets 180; HeadOnMerge needs both ATAs<20
and gets ~91; OffCenterMerge needs 3000–5000 m and gets 610). Without it the tree's lowest-
priority default saturated roll toward an aimpoint 86° off target — a max-rate turn *away* from
the bandit. Adopted on a measured mechanism (turns toward the bandit instead of away — traced
range closing 610→2298 m instead of 610→3085 m over 10 s) rather than a win-rate delta, because
self-play cancels any one-sided edge and vs-own-BT was already saturated. **Per F23, this branch's
own conditions read satisfied at the merge yet Gate 2 still returns FAILURE** — see the open
`UpDown`-inversion hypothesis above; do not assume this branch fires correctly yet.

## Gate 3 — Energy-state guard (`Gate3_EnergyState`, a `Fallback`)

```
Gate3_EnergySuperior:  EnergyRatio > 1.4   → Task_AnglesTactics
Gate3_EnergyInferior:  EnergyRatio < 0.8   → Task_EnergyTactics
(0.8–1.4 "matched" band falls through unchanged to Gate 4)
```

Scoped narrowly in front of the offensive branches only — deliberately doesn't touch the
survival/defensive priority order above it. The superior threshold was raised from 1.2 to 1.4 on
2026-08-01 after finding that a ~20% energy edge was enough to commit to `Task_AnglesTactics` and
shadow all of Gate 4 (including `Task_HighYoYoUp`, the better answer when close and overtaking) —
reserving commitment for a clearer ~40% edge. The inferior threshold (0.8) was deliberately left
untouched: it gates a survival behavior (`Task_EnergyTactics`, extend/survive when disadvantaged),
judged not worth weakening blind.

## Gate 4 — Offensive maneuver selector (`Gate4_OffensiveSelector`, a bare `Fallback`)

```
Task_HighYoYoUp → Task_BarrelRollAttack → Task_LowYoYo → Task_NoseToTailTurn
  → Task_LagDisplacementRoll → Task_OneCircleFight → Task_LagPursuit
```

Bare children, same idiom as Gate 1's individual triggers: each phased node self-gates its own
distance/speed/altitude entry internally in C++ on a fresh claim, rather than being wrapped in an
XML-level `DECO_*Check` Sequence. `Task_OneCircleFight`/`Task_LagPursuit` are the original,
pre-tactics-expansion pursuit nodes and sit last in this list as the within-gate fallback.

## Tail — final default pursuit (bare children + 2 sequences)

```
Tail_SingleSideOffset                          (bare Task_SingleSideOffset — confirmed working)
Tail_LeadPursuit:  dist > 2000 m  →  Task_LeadPursuit
Tail_Pure:         dist < 2000 m  →  Task_pure
```

`Task_SingleSideOffset` is deliberately **not** wrapped in a distance decorator, per its own C++
comment: a 3000–5000 m XML gate would cut it off mid-maneuver exactly when distance drops below
3000 during its own "close" phase, which needs to keep running to the 2000 m handoff — it
self-gates its entry internally instead, on a fresh claim, the same idiom `Task_HighYoYoUp`/
`Task_LowYoYo`/`Task_Evade` already use.

---

## What to check once the F25 fix lands (from `COMPETITION_PLAN.md` §4.1 section G)

In order: (1) do maneuver tasks appear in the gate trace at all, and which; (2) does flow-type
selection match the geometry — two-circle on a rate fight, one-circle on a radius fight; (3) does
average airspeed move toward the doctrinal rate band once `Task_EnergyTactics` can actually run;
(4) only then re-measure F12's G-ceiling number and F14's defensive-axis question — both were
measured against a tree running two leaf tasks and are flagged in the register as needing a
re-run. Every BT-relative number recorded anywhere in this project's docs before the fix lands
should be treated as **void**, not merely suspect, once it does.
