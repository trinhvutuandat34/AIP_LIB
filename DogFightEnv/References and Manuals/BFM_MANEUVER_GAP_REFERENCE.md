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
