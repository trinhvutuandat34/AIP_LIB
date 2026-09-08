# BFM Maneuver Gap Reference — Vertical Reversals, Basic Aerobatics, and Undocumented Doctrine

**Scope note:** this file only covers what is *not* already in `BFM_REFERENCE.md` (RoKAF F-16C
Basic Employment Manual extracts, geometry/pursuit/turn-performance, mapped to
`AngleOffUpdate.cpp`/`CheckSight.cpp`/`Task_LeadPursuit` etc.) or
`BFM_ACM_Reward_Engineering_Reference.md` (geometry, pursuit curves, turn performance, energy
maneuverability/Ps, for reward-shaping). Those two already cover aspect angle/HCA/ATA, lead/
pure/lag pursuit, turn rate/radius, corner speed, one-circle/two-circle fights, yo-yo, scissors,
notch, and specific excess power — don't duplicate that search here, go to those files.

Everything below was checked against those two files plus `AERIAL_COMBAT_BT_GUIDE_DETAILED.md`
term-by-term before being added; every item here returned zero hits there. It was also checked
against the actual tree (`Rule_real_eagle.xml`) and the real `Task_*.cpp` source inventory in
`AIP_LIB/AIP_DCS/BehaviorTree/` (22 files, 21 wired into the tree plus the unwired
`Task_Empty.cpp` placeholder) — not inferred from node names.

**Source note:** compiled from reference material provided in chat (transcripts described as
drawn from an "Air Combat Tutorial Library" / "AI Combat Tutorial Library" series; exact
provenance not independently verified by this session). Written here in original wording, same
posture as `BFM_ACM_Reward_Engineering_Reference.md`: the maneuver names and underlying physics
are standard BFM/aerobatics terminology, not treated as copyrighted expression.

---

## 1. Vertical heading-reversal family (Split-S, Sliceback, Pitchback)

Three distinct ways to reverse heading ~180°, differing in how much altitude they cost and how
much airspeed they preserve — a graduated family, not interchangeable:

| Maneuver | Mechanism | Altitude cost | Speed retained | Typical use |
|---|---|---|---|---|
| **Split-S** | Half-roll to inverted, then pull straight down through a half-loop | Highest (fully inverted, nose-low through the vertical) | Lowest (gravity-assisted dive builds speed but the maneuver is slow to complete) | Defensive escape with altitude to spare; offensive lead-turn in the vertical against a bandit passing underneath |
| **Sliceback** | Descending turn at ~135° bank, never fully inverted | Moderate (less than Split-S because the nose never points straight down) | Moderate | Faster reversal than Split-S when altitude is tighter; denies a bandit outside the turn circle their lateral turning room |
| **Pitchback** | Nose-high reversal: lift vector starts above the horizon, ends below it at ~135° bank | Lowest (partially trades to altitude instead of diving away it) | Highest (stays closest to maneuvering airspeed throughout) | Fastest reversal that preserves energy; can out-turn a bandit doing a flat horizontal turn by using a smaller vertical-plane radius |

**→ Project mapping:** none of the three exist as `Task_*` nodes (confirmed against the real
`AIP_DCS/BehaviorTree/` source, not just the XML). The tree's closest existing behavior is
`Task_HighYoYoUp`/`Task_LowYoYo` (out-of-plane closure control, not a heading reversal) and
`Task_Evade` (`Gate1_TheBreak` — a threat-reaction break, not a chosen offensive/defensive
reversal). There is currently no node that trades a specific, chosen altitude/speed cost for a
180° heading change the way this family does. Whether this gap is worth closing is a scope call
for whoever owns `Gate4_OffensiveSelector`/Gate 1 — noting it here as a documented absence, not
a recommendation.

## 2. Basic aerobatic building blocks (airmanship primitives)

These are stick-and-rudder fundamentals, not tactical maneuvers on their own — they're the
building blocks tactical maneuvers get assembled from:

- **Aileron roll** — 360° roll around the longitudinal axis; a slight nose-up entry compensates
  for lift lost as bank angle passes through knife-edge, so the aircraft returns to entry
  altitude. Coordinated with opposite rudder against adverse yaw.
- **Barrel roll** — a helical path: a loop combined with a 360° roll around a point ~45° off the
  nose, crossing all three axes. Precision check: same altitude and heading at exit as entry.
  *(Not the same as this project's `Task_BarrelRollAttack`, which is a tactical closure/angle
  maneuver named after the shape, not a pure-airmanship roll.)*
- **Falling leaf** — power reduced, back pressure increased to the edge of stall; wing drop is
  corrected with rudder only (no aileron), training rudder authority at low airspeed and the
  incipient-spin recovery reflex.
- **Half Cuban eight** — loop continued past inverted to 45° nose-low, then a half-roll upright
  while still diving, then level out. Exits on the reciprocal heading at entry altitude/speed.
- **Immelman turn** — first half of a loop, then a roll to upright at the top. Converts airspeed
  to altitude; exits ~180° off entry heading at higher altitude and lower airspeed. Commonly cited
  as a merge-exit or head-on-pass response when trading speed for altitude is worth it.
- **Lazy eight** — two 180° turns in a figure-eight, continuously varying pitch/bank (climbing
  turn to a 90° peak-bank point, descending back through the second 90°) with no throttle
  change. An energy-management proficiency exercise, not a combat maneuver — included for
  completeness, not as an implementation candidate.

**→ Project mapping:** none exist as `Task_*` nodes. `Task_BarrelRollAttack` shares a name with
#2 above but is a different thing (a tactical closure maneuver, not the pure-airmanship roll
described here) — worth being precise about this distinction if it ever comes up in a design
discussion, since the shared name invites confusion. The Immelman is the one entry here with the
clearest tactical (not just airmanship-training) use case; the rest are lower priority as gap
items since they're proficiency exercises rather than engagement-tested doctrine.

## 3. Doctrine concepts with no current name in project docs

Checked individually against all three existing reference docs — none of the following terms
appear anywhere in them:

- **The three axioms** (lose sight/lose the fight; relativity — maneuver relative to the
  bandit's actual behavior, not a fixed script; energy vs. nose position — energy is a finite
  resource, know when to spend it for angles vs. conserve it). These are framing principles more
  than mechanics — closest existing project analog is the gate-ordering philosophy itself
  (survival first, offense-over-defense reasoning in the Gate 2.5 move), which embodies axiom 3
  without naming it.
- **Control zone / attack window / "the bubble"** — the control zone is the 3D conical region
  behind a defender where an attacker with controlled range/closure cannot be denied a
  positional advantage; the attack window is the specific entry point in space that lands an
  attacker in it; the bubble is the sphere (radius = turn radius) inside which a defender
  physically cannot turn its nose onto an attacker who is already inside. No `DECO_*` check in
  the current tree tests for "inside the control zone" as a composite condition — the closest
  approximations are the individual `DECO_DistanceCheck`/`DECO_LOSCheck` gates in
  `Gate2p5_GunSolutionHold`, which cover the same range/angle band piecemeal without naming the
  zone concept.
- **Bugout, with its measurable success criterion** — max thrust, turn across the bandit's tail,
  unload and dive to accelerate; declared successful specifically at **>1 nm separation and >90°
  remaining on the bandit's turn**. This is a concrete, testable threshold pair that nothing in
  the current tree or docs defines. If a "did we successfully disengage" metric is ever wanted
  (relevant to the open DQ/resilience workstream per `HANDOFF.md`), this is the doctrine
  definition to test against.
- **Redefinition** — the doctrine term for when a defender's action changes the fight's nature
  (e.g. horizontal to vertical). Purely descriptive/framing; no natural single-node mapping.
- **God's G / vertical merge advantage / exclusive-use turning room** — a climbing aircraft at
  the merge gets a faster turn rate from gravity assisting an inverted-plane turn ("God's G");
  at low altitude, being *lower* than the bandit secures turning room the bandit can't contest
  (exclusive use); at high altitude, being *higher* secures an energy reserve instead. **None of
  `Gate2_BeamMerge`/`Gate2_HeadOnMerge`/`Gate2_OffCenterMerge` condition on `alt_gap` at all** —
  they're evaluated as if the merge were always co-altitude. Whether that's a deliberate
  simplification or a real gap depends on how often the actual competition geometry has a
  vertical offset at the merge — not something this session measured, just flagging that the
  gate logic doesn't currently look.

**→ Project mapping:** all of the above are doctrine-level absences, not implementation bugs —
none contradict anything in the tree, they're simply concepts the current gate structure doesn't
name or explicitly test for. Listed here so a future design pass (e.g. whoever eventually revisits
gate structure after the `F25` name-attribute fix lands and the tree runs for the first time) has
this pre-checked against existing docs rather than needing to re-derive it.

## 4. Addendum 2026-09-06 — verified against AETCTTP11-1 (official AETC T-38 IFF manual)

New source, materially different provenance from everything else in this file: **AETCTTP11-1,
31 December 2024**, "T-38C Employment Fundamentals/Introduction to Fighter Fundamentals" — a real,
currently-in-force USAF publication (OPR 19 AF/A3V), not a transcript of uncertain origin. It's a
T-38 (trainer), not F-16, manual, so **treat its hard numbers (speeds, G, KCAS bands) as
illustrative only** — `BFM_REFERENCE.md`'s RoKAF F-16C BEM stays the authority for F-16-specific
numbers. Its *doctrine framework* (axioms, geometry, decision rules) is airframe-general and is
what's extracted below. Read in full: Chapter 2 (mission prep/debrief) and Chapter 4 Sections
4A-4D (BFM concepts through DBFM/HABFM); Section 4E (ACM, multi-aircraft) and 4F (ACF) were not
read, consistent with this project's own multi-aircraft/radar-intercept out-of-scope calls below.

- **BFM Axioms (§4.3)** — item 3's "three axioms" paraphrase is now a verified quote, not a
  guess: *Lose Sight, Lose the Fight* / *Maneuver in Relation to the Bandit* / *Energy versus Nose
  Position*, word-for-word section headers in an official pub. No project-mapping change, just a
  citation upgrade from "framing principle" to "cite §4.3 directly" if this ever surfaces in a
  design doc.

- **Control Zone — now has exact numbers (§4.8):** "the CZ volume is generally defined as
  2,500-4,500 feet behind the bandit, with 25-45° AA, on or near the bandit's turn circle." The
  back edge (4,500 ft) is a *pressure limit* (farthest position from which a transition to WEZ is
  still threatening); the front edge (2,500 ft) is a *reaction/time limit* (closest position that
  still leaves time to react to a bandit defensive move and re-attack). This is a **staging
  position before weapons employment**, not the WEZ itself — don't conflate it with
  `BFM_REFERENCE.md` §6's WEZ range figures (3,500-5,000 ft gunshot ranges), which are a
  different, later phase. **→ Project mapping:** confirmed against the actual XML
  (`Gate2p5_GunSolutionHold`, `Rule_forTraining.xml:130-145`) — the tree's only zone-like check is
  `Gun_DistGt152p4`/`Gun_DistLt914` (500-3,000 ft) + `Gun_OwnATA_Lt8` (8° ATA), which is the WEZ/
  gun-track condition, tighter in angle and range than the doctrine CZ. There is still no
  composite "am I in the Control Zone" state distinct from "am I in the WEZ" — the tree jumps
  straight from Gate ordering to the tighter, later-phase condition. Unchanged conclusion from item
  3, now with citable numbers if a CZ-as-its-own-state node is ever designed.

- **Separation/"Bugout" — replaces the unverified criterion with an official, different one
  (§4.27.8.1):** *"If the Bandit is trending towards 90° of HCA (approximately 45° AOT and 45°
  planform) and greater than 6,000 feet, consider separating."* Trend cue: Bandit apparent size
  shrinking over time, not a single-frame check. This is a **compound, angle-gated** criterion —
  contrast with this project's actual implementation, `Task_Evade.cpp`'s `Maneuver_TheBreak`
  decision point, which is a **pure range check**: extend once `Distance > BREAK_RANGE_TRIGGER_M`
  (3,000 m) past `BREAK_DECISION_S` (5s), release unconditionally at `BREAK_TOTAL_MAX_S` (20s)
  toward a `BREAK_GOAL_SEPARATION_M` (5,000 m) goal, with no HCA/AOT condition anywhere in the
  node. That 5 km figure is sourced from `AERIAL_COMBAT_BT_GUIDE_DETAILED.md`'s own
  provenance-unverified "5+ km separation" line (§1 of that guide) — this AETC citation is the
  first independently-sourced doctrine this project has for a disengagement criterion, and it's
  meaningfully different in shape (angle-gated near-6,000-ft trigger vs. a flat 5,000 m goal), not
  just in units. **Implemented 2026-09-06**: `Task_Evade.cpp`'s extend-phase release now requires
  `MyAngleOff_Degree >= BREAK_SEPARATION_HCA_MIN_DEG` (70°, reusing `Task_Notch`'s own near-90 beam
  band lower bound rather than a new number) in addition to the existing `BREAK_GOAL_SEPARATION_M`
  distance check — that distance goal (5,000 m) already exceeds the doctrine's ~1,829 ft range half
  of the compound criterion, so only the HCA half needed adding. The unconditional
  `BREAK_TOTAL_MAX_S` (20s) cap is unchanged, so a geometry where HCA never opens up still releases
  the node on schedule rather than hanging. Rebuilt (Debug|x64, matching the shipped DLL's own
  debug-CRT configuration — confirmed via `dumpbin /dependents` before rebuilding, not assumed) and
  redeployed to both `AIP_BASE.dll` and `AIP_BASE_target.dll`; verified via a live BT-vs-BT
  `run_local_dogfight.py` run (601 ticks, no crash) plus an `AIP_BT_GATE_TRACE` capture confirming
  the tree still evaluates cleanly tick-by-tick.

- **Reversal — a new, crisp, testable rule not present anywhere else in this project's docs
  (§4.25.3):** a reversal opportunity exists when, at the turn-circle overshoot, **HCA (degrees) is
  roughly ≥ 2 × range (in hundreds of feet)**, inside a turn radius, with high LOSR (defined
  operationally as reaching the turn-circle picture in 1-2 seconds). Worked example given in the
  source: 50° HCA at 2,500 ft (25 × 2 = 50). This is directly codable as a new `DECO_*` ratio check
  if ever wanted — nothing currently in the tree computes an HCA-vs-range ratio; the closest
  existing logic (`Task_Evade`'s reversal-adjacent behavior, scissors nodes) uses flat angle/
  distance thresholds, not this relative rule.

- **"God's G" / exclusive-use turning room — independently confirmed, with a concrete mechanism
  (§4.11, §4.30.4):** AETCTTP11-1's own "exclusive TR" example is functionally identical to what
  item 5 described from the other source (a low-altitude, high-aspect merge where the lower
  fighter can use vertical TR the higher fighter cannot, on pain of hitting the ground). It also
  names the *mechanism* the other source didn't: the **"Energy Atom"** (§4.30.4) — in a vertical
  lead turn, target a slower-than-nominal-rate airspeed when converting high-to-low (gravity will
  add energy through the maneuver) and a faster-than-nominal airspeed when converting low-to-high
  (gravity will remove it), so the *sign of the coming altitude change* should shift the target
  airspeed, not just the turn geometry. **→ Project mapping unchanged from item 5**: still no
  `alt_gap` conditioning anywhere in `Gate2_BeamMerge`/`Gate2_HeadOnMerge`/`Gate2_OffCenterMerge`,
  but this is now the second independent doctrine source describing the same gap with a specific,
  implementable rule (bias target airspeed by vertical-conversion direction) rather than just a
  named concept — raises this from "doctrine absence" to "doctrine absence with a ready-made fix
  shape" if `alt_gap` is ever threaded into a Service.

- **DBFM objective hierarchy (§4.22)** — a clean, official, ordered priority list: **SURVIVE →
  Defeat the Initial Attack → Deny the Control Zone → Deny Subsequent Weapons → Neutralize,
  Separate, or Go Offensive**. This is the formal doctrine backbone behind what item 3 already
  called "the gate-ordering philosophy itself (survival first, offense-over-defense reasoning)" —
  worth citing by this exact list if that gate-ordering rationale is ever written up more formally,
  since it now maps one-to-one onto an official priority sequence rather than an inferred
  principle.

- **Neutral-pass one-circle/two-circle forcing rule (§4.34.4.2.2)** — complements
  `BFM_REFERENCE.md` §7's lateral-spacing-decides-it rule with a *second* decision rule for the
  genuinely-neutral case (no lateral TR either way): **"at 350 KCAS or less, consider forcing a
  one-circle, min radius fight. If >350 knots or with the nose >~15° below the horizon, consider
  forcing a two-circle fight."** The 350 KCAS figure is T-38-specific and not directly portable to
  the F-16 sim, but the *shape* of the rule (let your own energy state break the tie when geometry
  alone doesn't decide the fight type) is new relative to what's in `BFM_REFERENCE.md` or this
  file, and is a second, independent example of the same "last one to turn sets the fight, so don't
  be indecisive" framing already noted there.

## 5. New gap found via this addendum: Defensive Spiral has no `Task_*` node

Cross-referencing this addendum's source material against `BFM_ACM_Reward_Engineering_Reference.md`
surfaced a gap neither existing doc named explicitly. **Defensive Spiral** — a distinct, named BFM
maneuver (steep, tightening diving spiral flown by a slow defender to force a faster attacker to
overshoot, minimizing own acceleration rather than trying to out-turn) — is:
- Explicitly named as its own maneuver (distinct from Split-S/Sliceback/Pitchback, item 1) in the
  F-16 tactical-maneuver material provided alongside this addendum, with its own decision-matrix
  entry ("Slow, bandit in control zone → Defensive Spiral").
- **Already assumed to exist** as a curriculum concept in this project's own
  `BFM_ACM_Reward_Engineering_Reference.md` — Part 6 defines it as a named maneuver and Part 8
  assigns it Stage 5 ("Defensive survival"), including the asymmetric energy-term handling note
  (minimize acceleration rather than maximize Ps, opposite of every other stage).
- **Absent from the actual `Task_*` inventory** in `AIP_DCS/BehaviorTree/BT_Content/Task/` (verified
  against the file list, not inferred) — there is no `Task_DefensiveSpiral`, and nothing in
  `Rule_forTraining.xml` implements "minimize acceleration while close, slow, and defensive" as a
  distinct behavior. `Task_Evade`/"The Break" is a max-G, max-afterburner extension — the opposite
  energy posture from what a defensive spiral calls for.

**→ Project mapping:** this is a case where the RL-side reward-engineering doc already planned for
a maneuver class the BT side never implemented — worth knowing if `Task_Evade`'s always-extend
behavior is ever found to perform poorly specifically in the slow/close/defensive regime the
Defensive Spiral is meant for, since that's a plausible root cause with a named doctrine fix
already half-designed in this project's own docs.

**Implemented 2026-09-06**: `Task_DefensiveSpiral.h`/`.cpp` added under
`AIP_DCS/BehaviorTree/BT_Content/Task/`, registered (`TaskNodes.h`, `CPPBehaviorTree.cpp`) and
added to `AIP_DCS.vcxproj`/`.vcxproj.filters`, with a new `Maneuver_DefensiveSpiral` enum value
(additive, `CPPBlackBoard.h`). Wired into Gate 1's Fallback in both `Rule_forTraining.xml` and
`Rule_real_eagle.xml` (not `Rule.xml` — confirmed that file is the old pre-expansion 9-node
template with no Gate structure at all, unrelated lineage) as `Gate1_DefensiveSpiral`, tried
immediately before `Gate1_TheBreak` and sharing its HCA<150/gun-solution-carve-out gates; the new
node's own internal entry gate (`MySpeed_MS < 154` — the same "slow" line `Task_Evade` already
uses) means it fails through to `Gate1_TheBreak` whenever the defender has enough energy to extend
instead, so it cannot shadow the existing node. Mechanically: one sustained tight-turn-plus-dive
aim-point offset (not an oscillating reversal like the Scissors family) at idle-ish throttle
(0.1), released on threat-gone / altitude-floor (609m) / doctrine's 10-20s duration cap (15s used).
Built (Debug|x64, matching the shipped DLL) and redeployed to both `AIP_BASE.dll` and
`AIP_BASE_target.dll`. Verified: clean compile, a live BT-vs-BT `run_local_dogfight.py` run (601
ticks, no crash, both aircraft at full health at the step limit), and an `AIP_BT_GATE_TRACE`
capture confirming `Gate1_Spiral_HCA_Lt150` evaluates every tick in the correct Fallback position
(between `Gate1_Jink...` and `Gate1_Break...`) and fails correctly on a head-on (HCA≈180°) spawn.
**Not yet exercised**: the default local-dogfight spawn starts both aircraft at 300 m/s, well above
the node's 154 m/s entry gate, so this smoke test did not actually drive the tree into
`Task_DefensiveSpiral::tick()`'s active body — only its (correct) non-trigger path is confirmed
live. A scenario that starts one aircraft slow, close, and threatened would be needed to observe
the maneuver actually fire before relying on its tuning under match conditions.

## 6. F-16-specific quantitative maneuver parameters (secondary source, use with caution)

The F-16 tactical-maneuver reference provided alongside this addendum gives per-maneuver numeric
envelopes (entry/exit KCAS, G-load, AoA, Ps, duration, abort criteria) for High-G Break Turn, High/
Low Yo-Yo, Immelmann, Split-S, Barrel Roll Attack, Flat/Rolling Scissors, and Defensive Spiral —
i.e., F-16-*matched* aircraft type (unlike AETCTTP11-1 above), which is genuinely useful since this
project's aircraft is F-16 (confirmed: `DogFightEnv/Release/aircraft/{f15,f16,fa50}`). **Provenance
caveat, stated by the source document itself**: its combat-BFM parameter table is "derived from
official USAF demonstration manuals (AFMAN 11-246V1), pilot-reported EM diagram analysis, and
tactical BFM doctrine" — AFMAN 11-246V1 is a real, official publication, but it's the **Viper Demo
Team's airshow-maneuver manual**, not a combat-BFM source. The combat-maneuver numbers are an
AI-synthesized estimate cross-checked against general doctrine, not a citation to a specific
page of a combat manual — same evidentiary tier as `BFM_MANEUVER_GAP_REFERENCE.md`'s own
"Air Combat Tutorial Library" material before this addendum, not the tier of AETCTTP11-1 or the
RoKAF BEM. Treat the numbers as **candidate reward-shaping/promotion-criterion targets to sanity-
check against JSBSim's own simulated performance (per `BFM_ACM_Reward_Engineering_Reference.md`
Part 9's own advice), not as verified aircraft data to hardcode.**

That said, two internal-consistency checks passed: its EM-reference corner velocity (~420 KCAS,
9.0G instantaneous) sits right at the top of `BFM_REFERENCE.md` §3's independently-sourced 330-440
KCAS RoKAF corner plateau, and its 9.0G sustained-with-full-fuel structural limit matches
`BFM_REFERENCE.md`'s numbers exactly — no contradiction found between the two F-16 sources where
they overlap.

Its **Gun Fight Decision Matrix** (situation → maneuver) was cross-checked against the live
`Rule_forTraining.xml` Gate 4 offensive-selector Fallback order (`Gate4_HighYoYoUp` →
`Gate4_BarrelRollAttack` → `Gate4_LowYoYo` → `Gate4_NoseToTailTurn` → `Gate4_LagDisplacementRoll` →
`Gate4_OneCircleFight`, lines 344-350) and the Gate 2 neutral-scissors Fallback
(`Gate2_FlatScissors` → `Gate2_VerticalScissors` → `Gate2_RollingScissors`, lines 302-305): the
ordering is consistent with the matrix's offensive guidance (yo-yo/barrel-roll family for overtake
control, scissors family for a nose-to-nose stalemate) — no discrepancy found. The matrix's two
branches with **no implemented counterpart** are "you overshot, bandit reversing → Immelmann or
Split-S" (item 1's vertical-reversal-family gap) and "slow, bandit in control zone → Defensive
Spiral" (item 5 above) — both already flagged, now with the specific tactical trigger context
(post-overshoot reversal; slow defensive close-range) that motivates *when* each would fire if
implemented, which neither existing doc previously stated.

---

## Explicitly out of scope (checked, deliberately excluded)

Two more items from the source material were checked and are being left out on purpose:

- **PAD setup** (the standardized training-entry positioning/tolerance convention: combat
  spread or abeam, ±100 ft/±0.1 nm/±10°/±10 kt tolerances) — this describes how instructors set
  up a *training* engagement's starting geometry. The competition's actual entry geometry is
  fixed by `match_base`/`match_base_wide`/`match_base_close` (per `HANDOFF.md`), so this doesn't
  apply here the way it would in a flexible training syllabus.
- **Stern conversion** (radar/controller-directed vector to a bandit's 6 o'clock) — a
  radar-intercept concept; `BFM_REFERENCE.md` already scopes out multi-aircraft ACM and radar
  intercepts as out of scope for this project's 1v1 guns-only context, and the same reasoning
  applies here.
