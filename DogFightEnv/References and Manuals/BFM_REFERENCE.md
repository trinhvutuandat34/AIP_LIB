# BFM Reference — F-16 Basic Employment Manual (RoKAF 2005)

Notes extracted from `D:\AIP\pdf\Basic-Employment-Manual-F-16C-RoKAF_2005.pdf` (Korean AF TTP
3-3, Volume 5, "Korean AF BEM" — a real USAF/RoKAF F-16C tactics manual, 598 pages). This file
keeps only what's useful for reasoning about this project's BT/RL dogfight modeling — not a full
summary of the source. Chapter 4 (Air-to-Air) §4.3–4.6 was read in full; §4.7 (multi-aircraft ACM)
and §4.8 (radar intercepts) were skipped as out of scope for 1v1 guns-only. Page-mapping note for
anyone going back to the source: document page "4-X" = physical PDF page (X + 122).

Each section below ends with **→ Project mapping**, connecting the real doctrine to the actual code
in this repo, verified this session by reading the source directly (not inferred from names).

---

## 1. Positional geometry — the four core measurements

- **Range** — distance between the two aircraft.
- **Aspect Angle (AA)** — the attacker's position *relative to the target*, **independent of the
  attacker's own heading**. Measured from the target's tail to the attacker's position. 0° = you're
  at their nose, 180° = you're at their six.
- **HCA (Heading Crossing Angle)** — the angular difference between the two aircraft's
  longitudinal axes (nose-to-nose direction), independent of position. ~0° = co-flowing/chase,
  ~90° = crossing, ~180° = head-on.
- **ATA (Antenna Train Angle)** — how far off *your own* boresight the defender currently is.
- Key relationship: **whenever the attacker is pointing at the defender, AA and HCA (angle-off)
  are the same value** — a useful sanity check when reasoning about geometry.

**→ Project mapping**: `AngleOffUpdate.cpp`'s `MyAngleOff_Degree` computes HCA (angle between
forward vectors), not ATA — confirmed against this exact definition. `CheckSight.cpp`'s
`Los_Degree` is true ATA. `AspectAngleUpdate.cpp`'s `MyAspectAngle_Degree` matches the AA
definition above (0°=nose-on, 180°=six o'clock) — this is the doctrine-standard convention. The
Python side's `GeoMathUtil._get_aspect_angle()` uses the **opposite** convention (0°=six o'clock) —
already flagged in `CLAUDE.md` as a cross-language sign trap; this reading confirms the *native BT
side is the one using standard doctrine convention*, not the Python side.

---

## 2. Pursuit curves

Three attack courses, defined by where the attacker's nose points relative to the defender:
**lead** (ahead of the defender — used for an actual gunshot), **pure** (directly at the defender),
**lag** (behind the defender). Outside the defender's plane of motion, the attacker's lift-vector
placement (not nose position) determines the course.

Important dynamic: **an attacker in lead pursuit can be forced into lag pursuit** if he doesn't
have enough turn rate available to maintain lead — pursuit curve isn't purely a choice, it's
sometimes a physics-imposed outcome.

**→ Project mapping**: `Task_LeadPursuit` / `Task_pure` / `Task_LagPursuit` implement exactly these
three, gated by range in `Rule_forTraining.xml`'s Tail branch. `Task_LeadTurn` implements the
"cut the corner" lead-turn concept, gated on a computed turn-rate-ratio check
(`Task_LeadTurn.cpp:34-35`, `9.81·tan(roll)/speed`). None of the BT nodes model the
"insufficient-turn-rate forces lead→lag" transition explicitly — a task either is `Task_LeadPursuit`
or it isn't; there's no node that starts in lead and degrades to lag mid-maneuver based on realized
turn-rate deficit.

---

## 3. Turn performance physics

- `Turn Radius (ft) = V² / (g × G_radial)`, `Turn Rate (deg/s) = (G_radial × 1091) / V_KTAS`
  (V in knots true airspeed).
- The F-16 does **not** have a single "corner velocity" — it has a **corner plateau between 330 and
  440 KCAS** where turn rate is roughly maximized and fairly flat, due to the flight control system.
  Turn radius is roughly constant from 170–330 KCAS, increases slightly 330–440, increases sharply
  above 440.
- **TC shrink** (turn circle shrink): a real quantified example from a 180° break turn — 450→250
  KCAS, radius shrinks 3,200ft → 1,800ft (down to 59% of the original) as energy bleeds off over the
  turn. The turn's center of rotation also migrates toward the aircraft, it isn't a fixed pivot.

**→ Project mapping**: no part of this codebase's Python/BT layer computes or exposes a turn-radius
value directly — geometry is derived from raw position/attitude each tick. Whether the underlying
JSBSim F-16 FDM actually reproduces the real 330–440 KCAS corner-plateau shape (vs. a smoother or
different curve) hasn't been checked this session — would need direct FDM testing (fixed-bank turns
at a sweep of airspeeds, measure realized turn rate) to verify simulation fidelity here.

---

## 4. Energy vocabulary — sharper than "energy management"

- **Instantaneous rate**: the highest turn rate available *right now*, usually implies negative Ps
  (spending energy).
- **Sustained rate**: the rate achievable while *holding* airspeed and altitude (zero Ps) — this is
  the rate you can hold indefinitely.
- **Bleed rate**: how much energy (effectively airspeed) is lost per second at a given G level.
- Best sustained turn-rate airspeed band: **325–375 knots** (F-16, level turn, per the source's
  worked numbers). Best sustained-rate window for gameplan purposes: 330–440 KCAS. Tightest radius
  window: 130–329 KCAS.

**→ Project mapping**: this is the precise vocabulary for what Gate 3's `EnergyRatio` branch is
actually doing. `EnergyRatio > 1.2` → `Task_AnglesTactics` is a deliberate choice to operate near
**instantaneous** rate (spend the surplus, reduced throttle to tighten radius). `EnergyRatio < 0.8`
→ `Task_EnergyTactics` is trying to hold near **sustained** rate (conserve, throttle floor-protected
at 154 m/s). **Known gap, not yet closed**: `student/my_reward.py` has no reward term that reads
`EnergyRatio` or otherwise rewards spending/conserving energy correctly — RL has never been taught
this distinction via the reward signal, even though the raw ingredients (speed, altitude) are in the
15-feature observation. See `PROJECT_ANALYSIS.md` §2.3 for the fuller writeup of this gap.

---

## 5. Turning room

The separation between two aircraft, outside both turn radii, that can be spent to accelerate, close
range, or reduce angles. Available **laterally** (in the opponent's plane of motion) or **vertically**
(out of it) — this is the actual justification for why yo-yo maneuvers exist: they reach for
*vertical* turning room specifically when lateral room is constrained or already spent.

**→ Project mapping**: `Task_HighYoYoUp` (pulls up/out-of-plane to bleed excess overtake) and
`Task_LowYoYo` (dives to trade altitude for speed when under-energized) are exactly this — using
the vertical plane because the lateral (in-plane) turn alone can't solve the current geometry
problem.

---

## 6. WEZ / gun employment

- WEZ is defined by **range + aspect + ATA + closure** together, not range and angle alone.
- High-aspect gunshot: open fire ~4,000–5,000ft, aspects up to 90°; expect to lose ~2,000ft of
  range converting to lead.
- Low-aspect gunshot: aspect 45–55°, range 3,500–4,500ft is the trigger to transition to lead
  pursuit.
- **Closure-rate rule of thumb, not modeled anywhere in this project**: never let closure rate
  exceed roughly half of current range — e.g. 150 kt closure at 3,000ft, 100 kt at 2,000ft, 50 kt at
  1,000ft — otherwise you're accepting an overshoot risk with nothing to show for it.
- High-aspect shots are explicitly **not permitted above 135° AA** per this manual's own training
  rules (too fleeting/risky to be realistic training value) — separate from whether a shot is
  physically possible.

**→ Project mapping**: this project's own (currently-disabled-in-platform, reward-only-since-2026-07-16)
WEZ model is a simplified range+angle cone with 3 time-based phases (500-3000/3500/4000ft,
1-3° half-angle) — a reasonable digitization of the "range+aspect+ATA" idea, but it deliberately
drops the **closure** dimension entirely; nothing in `update_damage()`, `reward_lib.py`, or any BT
task checks closure rate as part of a valid gun solution. `DECO_ClosureRateCheck` exists and is used
twice in `Rule_forTraining.xml` (Gate 2's off-center-merge gating), but only as a binary
opening/closing check, not the quantified "closure vs. range" ratio this doctrine describes. This is
a real, previously-unflagged simplification worth knowing about if WEZ fidelity work continues.

---

## 7. One-circle vs. two-circle fight theory

This is the richest, most directly-relevant section — and the one with a concrete, checkable claim.

- **What actually determines one-circle vs. two-circle is lateral spacing at the merge, not just
  who "wants" which fight.** Quantified rule: a fighter wanting two-circle should maximize
  horizontal offset at the pass; a fighter wanting one-circle should minimize it (pass as close as
  training rules allow). **"Turning single-circle when there is significant lateral distance
  (greater than 500 feet) will give the edge to the fighter that turned two-circle."** Spacing, not
  intent, decides who gets the advantage if the "wrong" fight type is flown.
- Altitude delta at the merge = an energy advantage for the higher aircraft (only the *relative*
  altitude between the two matters).
- **Winning/losing cues are trend-based, read across the turn, not instantaneous**: in a one-circle
  fight, compare who points at whom first after ~90°/120° of turn and watch LOS drift direction
  across the horizon (not canopy drift, which is noisy/irrelevant). In a two-circle fight, compare
  relative turn-rate lag after ~180°. "The last one to turn sets the one-circle or two-circle
  geometry" at each subsequent pass — every pass is a new decision point, not just the first merge.
- **Explicit plan-switching mid-fight**: "if you are losing the radius fight, switch to rate" — i.e.,
  abandon a losing one-circle commitment and force a reversal into two-circle, or vice versa. This is
  a conscious, diagnosed strategy change, not a fixed commitment.
- **Opponent-archetype gameplans** (Plan A / Plan B per archetype): a *power-limited* adversary
  (weak thrust, decent short-term rate) gets out-turned via two-circle rate pressure over multiple
  passes; a *turn-limited* adversary (poor G/lift, e.g. carrying heavy stores) is beatable either way.
  Diagnosing which archetype you're facing, from behavior observed over 1-2 passes, changes which
  plan to run.

**→ Project mapping**: the curriculum's `two_circle_headon_a{000,045,090,135,180}` stages vary
`alpha_deg` — a heading-crossing-angle-like spawn parameter — per `student/my_curriculum.py`. **Open
question, not yet checked this session**: does the scenario/spawn generator also vary *lateral
offset* at the merge? Per this doctrine, lateral spacing (not HCA alone) is what actually determines
whether a one-circle or two-circle outcome is even achievable — if the spawn logic only varies
heading angle, the curriculum may not be presenting the full geometric variable that real doctrine
says matters most. Worth checking the scenario-generation code (`env_overrides.initial_scenario`
handling) directly before concluding either way.

**The bigger architectural point** (see §9 below): none of this multi-pass, trend-watching,
plan-switching, opponent-archetype-diagnosing behavior exists in the BT tree as implemented. Gate 2
picks `Task_NoseToNoseTurn` or `Task_LeadTurn` off a single tick's geometry snapshot and that's it —
there's no persistent "which fight type am I in, and am I winning it" state carried across a turn or
across multiple merges.

---

## 8. Defensive BFM

- **Mindset**: survive first, exploit attacker errors second, effective jinks are the last resort.
- **Initial break turn, four simultaneous elements**: reduce power to sub-afterburner (not idle
  necessarily, but never AB — AB defeats IR countermeasures), lift vector slightly *low* (denies
  IR missile background), maximum sustainable G, IRCM (chaff/flare) concurrently.
- **Reading the attacker's pursuit course is the core defensive skill.** A pure-pursuit attacker who
  maintains turn direction post-merge will solve HCA/AA using his turn-rate advantage — the correct
  counter is usually a **reversal**, exploiting your only real edge (smaller turn radius from being
  slower). A pure-pursuit attacker who gets his turn *reversed* on him quickly moves forward of your
  3/9 line.
- **High-aspect guns defense denies POM, not range or lead** — at high aspect you cannot deny the
  attacker's range or required lead angle (pulling harder actually reduces his required lead), so
  the only lever left is a brief (1-2s) lift-vector roll of 45-60° to displace your plane of motion
  outside where he can solve for it before the merge.
- **Deep lag pursuit** (attacker turned too late, ends up far out the back) is defended differently
  from a close pure-pursuit pass — usually by continuing the same turn direction rather than
  reversing, since reversing here would hand the attacker a fresh, high-aspect WEZ.

**→ Project mapping**: `Task_Notch` (beam the LOS), `Task_Evade`/"The Break" (hard turn away,
tapering to reduced-throttle extension), and the scissors family are the BT's defensive/neutral-fight
toolkit. What's missing relative to doctrine: the BT's defensive tasks are triggered by
instantaneous distance/ATA thresholds, not by *diagnosing the attacker's pursuit course* (pure vs.
lead vs. lag) and picking a specifically-matched counter the way §4.5.19-4.5.24 describes. There's
no BT logic that reads "is the attacker holding pure pursuit" and chooses reversal vs.
continue-the-turn accordingly — it's threshold-gated, not diagnostic.

---

## 9. The core architectural gap (most important takeaway)

Real BFM, as this manual describes it, is fundamentally an **adaptive, multi-pass, trend-watching,
opponent-modeling strategy** — pilots explicitly track whether they're winning or losing a
*specific fight type* across a turn, switch plans consciously when a diagnosis changes, and adjust
their approach based on what kind of adversary (power-limited, turn-limited, equal) they've
inferred they're facing over 1-2 passes.

This project's native BT is a **reactive, mostly-memoryless, single-tick geometry-threshold tree**.
Every tick it re-evaluates Gates 0-4 fresh off instantaneous ATA/AA/distance/`EnergyRatio` — there's
no state anywhere tracking "am I winning this one-circle fight," "have I diagnosed this opponent as
power-limited," or "which pass number is this." `ActiveManeuverID`/`ActiveManeuverStartTime` track
phase *within* a single already-committed maneuver (e.g. the climb-then-refine phases of
`Task_HighYoYoUp`), not fight-level state that persists across merges.

This isn't a flaw to "fix" so much as a real, honest description of what kind of tactical agent
this is: a fast, correct, doctrinally-grounded *reflex* system, not a *strategist*. It explains why
the tree performs coherently within any single engagement geometry (verified live, BT-vs-BT) while
having no mechanism to notice "I've lost the last three passes of this two-circle fight, time to
force a reversal" the way the doctrine describes real pilots doing.

---

## 10. Open questions worth investigating (not yet checked this session)

1. **Does the scenario/spawn generator vary lateral offset at the two-circle merge**, or only
   `alpha_deg` (heading angle)? Per §7, lateral spacing is what doctrine says actually determines
   one-circle vs. two-circle outcome — check `env_overrides.initial_scenario` handling for the
   `two_circle_headon` mode.
2. **Does the JSBSim F-16 FDM reproduce the real 330-440 KCAS corner-plateau turn-rate shape**
   (§3), or a different curve? Relevant to whether BT/RL throttle-for-radius behavior is tuned
   against realistic aircraft performance or an FDM-specific one.
3. **Could RL ever learn trend-based fight-type diagnosis** (winning/losing cues read across a
   turn, §7) given the current single-tick, 15-feature observation with no temporal memory? This
   would likely need frame-stacking or a recurrent policy (the codebase has `RLLibLstm/`, a vendored
   SAC-LSTM patch set, already available but not currently used by `real_eagle`'s stages) — not
   something the current MLP architecture can represent regardless of training duration, tying back
   to the "training longer doesn't fix a structural gap" point from two turns ago.
