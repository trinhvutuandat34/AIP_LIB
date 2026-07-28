# BFM/ACM Concept & Data Reference for Dogfight RL Reward Engineering

**Purpose:** A working reference for observation design, reward shaping, and evaluation metrics in a SAC-based F-16/FA-50 dogfight agent (JSBSim environment).

**Source note:** The concepts below are standard air-combat-maneuvering (ACM) theory — the same core ideas appear across military flight-test literature, USAF/USN training doctrine, and multiple public texts. This reference was built while consulting Robert L. Shaw's *Fighter Combat: Tactics and Maneuvering* (1985) for structure, but everything here is written in original wording as a technical synthesis for your project — not a reproduction of the book's text. Treat the physics/formulas as general aviation engineering knowledge; treat the maneuver names as standard BFM terminology, not copyrighted expression.

---

## Part 1 — Geometry Fundamentals (Observation Space Candidates)

These are the raw geometric relationships between two aircraft that most BFM concepts are built from. All are directly computable from JSBSim state (own position/velocity + target position/velocity), which makes them natural observation or reward-shaping terms.

| Term | Definition | Range | Notes for RL use |
|---|---|---|---|
| **Aspect Angle (AA)** / Target-Aspect Angle (TAA) | Angle between the *target's* velocity vector and the line of sight (LOS) from target back to shooter | 0°–180° | 0° = target flying straight at you; 180° = target flying straight away (you're at its 6 o'clock) |
| **Angle-Off (AOT, "angle off the tail")** | Angle between the *shooter's* velocity vector and the target's velocity vector (i.e., how misaligned the two flight paths are) | 0°–180° | 0° = you're pointed the same direction as the target (ideal gun tracking); 180° = head-on |
| **Track-Crossing Angle (TCA)** | The angular difference between the two aircraft's velocity vectors at a given instant — effectively the same measurement as angle-off, used specifically when describing merges/passes | 0°–180° | Useful as a scalar to classify "merge geometry" at each pass |
| **Line of Sight (LOS) & LOS rate** | The bearing from shooter to target, and its rate of change | — | High LOS rate = hard to track/aim; central to gun-tracking-solution reward terms |
| **Closure rate** | Rate of change of range between the two aircraft (range-rate, negative = closing) | — | Direct reward/shaping signal for "gaining on target" vs "overshoot risk" |
| **Range** | Straight-line distance between aircraft | — | Gate for weapons-envelope / kill-probability reward terms |

**Relationship worth encoding directly:** an offensive position is generally characterized by *low AOT + you're near the target's 6 o'clock (high TAA from the target's perspective) + closing or stable range*. A single combined "advantage" scalar (e.g., a weighted function of AOT, TAA, and range) is a common approach in academic ACM-RL papers and maps cleanly onto this book's descriptive framework.

---

## Part 2 — Pursuit Curves (Attack-Geometry Primitives)

Pursuit type is defined by where the attacker points the nose (velocity vector) relative to the target — ahead, directly at, or behind:

- **Lead pursuit** — nose placed *ahead* of the target. Maximizes closure rate; used to close range or to generate a firing solution with lead. Downside: increases AOT over time, which erodes rear-hemisphere positional advantage, and can cause the attacker to overshoot the target's flight path if closure isn't managed.
- **Pure pursuit** — nose held *directly on* the target. Moderate closure, slower AOT growth than lead pursuit, minimizes the attacker's presented frontal area (harder for the defender to see/track).
- **Lag pursuit** — nose placed *behind* the target's position. Used to control/reduce closure while holding or reducing AOT — the standard technique for stabilizing in the target's rear hemisphere without overshooting, especially when the attacker is faster than the target.

**Reward-engineering angle:** these three regimes map naturally to a *discrete pursuit-mode auxiliary signal* — you can classify the agent's current pursuit geometry each timestep (lead/pure/lag, by sign and magnitude of nose-target angular offset relative to LOS) and shape reward toward lag/pure pursuit when closure is excessive and lead pursuit when closure is insufficient, rather than only rewarding raw angle-off.

---

## Part 3 — Turn Performance (Maneuver-Quality Metrics)

### Core variables
| Symbol | Name | Units |
|---|---|---|
| n | Load factor | G |
| TR | Turn rate | °/sec |
| RT | Turn radius | ft |
| V | True airspeed | ft/sec |
| Vc | Corner velocity ("corner speed") | knots/ft/sec |

### Simplified relationships (high-G regime approximation used in the source text)
```
Turn radius:  RT ∝ V² / n
Turn rate:    TR ∝ n / V
```
i.e., **turn radius is minimized, and turn rate is maximized, by pulling high G at low speed.**

### More precise level-turn formulas (standard aviation physics, useful for direct implementation)
```
Turn radius:  R  = V² / (g·√(n² − 1))
Turn rate:    ω  = g·√(n² − 1) / V
```
where g = 32.2 ft/sec². These can be computed every timestep directly from JSBSim's own airspeed and load-factor state — no external table needed.

### Corner velocity (Vc)
The airspeed at which the aircraft's max-G structural limit and its max-lift (aerodynamic) limit intersect on a V-n diagram. At Vc the aircraft achieves its best **instantaneous** turn performance (tightest radius *and* fastest rate simultaneously). Below Vc, turn performance is lift-limited; above Vc, it's structurally G-limited. This makes Vc a natural normalization reference for a "how close to optimal-turn-speed am I" reward term.

### Instantaneous vs. sustained turn
- **Instantaneous turn** — max turn capability at a single moment; bleeds energy (speed/altitude) because it typically exceeds the available thrust-to-drag balance.
- **Sustained turn** — the max turn (rate/radius) the aircraft can hold indefinitely at a given altitude/speed without losing energy (i.e., where thrust = drag, so specific excess power Ps = 0).
- Rule of thumb from the source: **minimum sustained turn radius is generally found around 1.4–1.5× power-on stall speed** — slower than the speed for best sustained turn *rate*, which sits closer to the specific-excess-power peak speed.

---

## Part 4 — Energy Maneuverability (Ps / Es) — Core Reward Signal Candidates

These two quantities (from E-M theory, originally developed by John Boyd) are probably the single most useful reward-shaping primitives for a dogfight agent, since they cleanly separate "position" from "energy state," and both are trivially computable from JSBSim state each step.

### Specific energy (Es)
```
Es = h + V² / (2g)
```
h = altitude, V = true airspeed, g = 32.2 ft/sec². Represents total mechanical energy per unit weight — altitude and airspeed are interchangeable via zoom climbs/dives, so Es is a better fitness measure than altitude or speed alone.

### Specific excess power (Ps)
```
Ps = (T − D)·V / W  =  dEs/dt
```
T = thrust, D = drag, W = weight, V = true airspeed. Ps > 0 means the aircraft is gaining energy (can climb and/or accelerate); Ps < 0 means it's bleeding energy. The **Ps = 0 contour** on an altitude-vs-Mach ("H-M") diagram defines the aircraft's sustained (steady-state) performance envelope boundary.

**Direct RL application:** `Ps` (or its sign/derivative) is a natural per-step reward/penalty term for "energy discipline" — penalizing maneuvers that bleed energy without tactical payoff, independent of the positional (angle-off/AOT) reward terms. Many published ACM-RL reward functions use a weighted sum of a positional-advantage term and an energy term; Es/Ps give you the energy half directly.

### Illustrative H-M-diagram reference points (generic supersonic fighter example from the source — **not** real F-16/FA-50 numbers, just a sanity-check shape)
| Point | Meaning | Example value |
|---|---|---|
| a | Min. sustained Mach at any altitude | 0.3 M at sea level |
| b | Max. sustained subsonic altitude | 56,000 ft at 0.9 M |
| c | Max. sustained altitude at any speed | 67,000 ft at 1.95 M |
| d | Max. sustained Mach at any altitude | 2.2 M at 55,000 ft |
| e | Max. sustained Mach at sea level | 1.35 M |

Use these only as a shape check for whatever Ps=0 envelope your own JSBSim-derived aircraft model produces — **do not use them as substitutes for actual F-16/FA-50 performance data** (see Part 9).

---

## Part 5 — Fight Geometry Archetypes: One-Circle vs. Two-Circle Equivalents

The source book doesn't use the modern "one-circle / two-circle fight" terminology directly — it describes the same geometry as **nose-to-nose** and **nose-to-tail turns**, which map onto those terms exactly:

| Modern term | Source's term | Geometry | Which parameter dominates advantage |
|---|---|---|---|
| **Two-circle fight** | Nose-to-nose turn | Both aircraft turn *toward* each other at the merge, each tracing its own circle, repeatedly re-merging head-on | **Turn radius** is the dominant factor — the tighter-radius aircraft generates flight-path separation it can convert into a lead-turn advantage. Turn *rate* matters much less here. |
| **One-circle fight** | Nose-to-tail turn | Both aircraft turn the *same direction*, sharing a single circle | **Turn rate** is the dominant factor — equal radius + higher rate wins; a radius advantage alone does little unless combined with a lead turn before the merge. |

**Reward-engineering implication:** since which turn-performance parameter (radius vs. rate) actually confers advantage depends on which geometry the fight has fallen into, a reward function that's purely "minimize your turn radius" or purely "maximize turn rate" will be miscalibrated in one of the two regimes. Detecting one-circle vs. two-circle geometry (e.g., via the sign of relative turn direction / heading-crossing pattern at merge) as an auxiliary observation, and conditioning the reward weighting on it, mirrors how the underlying tactics actually work.

---

## Part 6 — Named BFM Maneuvers (Discrete Tactic / Auxiliary-Reward Building Blocks)

These are less useful as continuous reward terms and more useful as **labeled behavior patterns** — either for curriculum design, for auxiliary classification heads, or for evaluating whether the trained policy has "rediscovered" recognizable doctrine.

| Maneuver | Trigger condition | What it does | Geometric signature |
|---|---|---|---|
| **Lead/lag/pure pursuit roll** | Excess closure with the attacker inside the defender's turn | Attacker rolls wings-level, pulls out of plane to bleed closure while preserving energy | Out-of-plane pull; net effect ≈ increasing AOT temporarily to prevent overshoot |
| **High Yo-Yo** | Moderate AOT (~30°–60°), attacker co-speed and closing too fast in-plane | Roll out of the target's maneuver plane, pull up to kill closure/AOT, then roll back down | Altitude gain, then descent back toward target's 6 o'clock |
| **Low Yo-Yo** | Attacker lacks in-plane turn rate to close on target | Pull nose down/inside the turn to use gravity assist for extra horizontal turn rate | Altitude *loss*, nose-low cut inside the circle |
| **Lead Turn** | Forward-quarter (near head-on) pass, attacker turns *before* passing the target | Converts early turn initiation + flight-path separation into a large angular advantage after the pass | Turn commenced pre-merge rather than post-merge |
| **Flat Scissors** | Slow-speed, low-vertical-displacement overshoot in a roughly level plane | Repeated nose-to-nose turns + reversals in the same horizontal plane; rewards the slower/tighter-turning aircraft | Oscillating crossing pattern, roughly constant altitude |
| **Rolling Scissors** | High-speed or high-to-low overshoot | Same idea as flat scissors but executed in the vertical plane via barrel-roll-like exchanges; rewards slow-speed sustained-turn/acceleration performance | Oscillating crossing pattern with significant altitude excursions |
| **Defensive Spiral** | Close-range rear-hemisphere threat at low defender speed | Very tight rolling scissors taken straight down; defender minimizes acceleration (idle power/drag) to force the faster attacker to overshoot | Steep, tightening descending spiral |

---

## Part 7 — Suggested Reward-Signal Summary

A practical starting decomposition for a JSBSim dogfight reward function, mapping each geometric/energy concept above to a role:

1. **Positional-advantage term** — function of AOT + TAA (e.g., reward being low-AOT while target has high TAA relative to you: the classic "get behind them, stay pointed at them" signal).
2. **Range/closure shaping term** — penalize being outside weapons envelope range; shape closure rate toward the pursuit mode (lead/pure/lag) appropriate to current range.
3. **Energy term** — Ps (or ΔEs per step) as a soft penalty/bonus independent of position, so the agent doesn't learn to win angles purely by bleeding all its energy.
4. **Turn-performance-vs-geometry term (optional, more advanced)** — condition turn-rate vs turn-radius emphasis on detected one-circle/two-circle geometry, rather than rewarding a single fixed turn metric everywhere.
5. **Terminal/sparse term** — actual kill/death/timeout, as usual in these setups, to anchor the shaped terms to the real objective.

---

## Part 8 — Curriculum-Stage Breakdown

Named BFM maneuvers (Part 6) form a natural difficulty ladder: each one isolates a specific sub-skill that later maneuvers assume you already have. This maps cleanly onto a staged curriculum, where opponent behavior and reward-term weighting both progress together. Stage weights below are *relative emphasis*, not literal values — tune magnitudes empirically, but keep the emphasis pattern, since it mirrors which sub-skill each stage is meant to isolate.

| Stage | Focus maneuver(s) (Part 6) | Opponent setup | Reward-term emphasis (Part 7 #s) | Promotion criterion |
|---|---|---|---|---|
| **0 — Control primitives** | *(prerequisite, not a BFM maneuver)* | None — single-agent flight | Pure control shaping only (AOA/G-limit compliance, altitude/airspeed hold); none of the dogfight terms active yet | Sustains controlled flight (no departure/stall/overspeed) for full episode |
| **1 — Pursuit-curve control** | Lead/pure/lag pursuit roll | Straight-and-level or gently-turning scripted target | **#1 Positional (high)**, **#2 Range/closure (high)**, #3 Energy (low) | Reaches and holds stable rear-hemisphere AOT band within a target time window |
| **2 — Yo-Yo energy trading** | High Yo-Yo, Low Yo-Yo | Constant-rate turning scripted target (single plane) | #1 Positional (high), **#3 Energy/Ps (raised)**, #4 Geometry (introduced, low) | Holds offensive AOT band while keeping Ps ≥ 0 on average across the engagement |
| **3 — Merge & lead-turn** | Lead Turn | Scripted head-on merges, randomized offset/closure | #1 Positional (high), **#4 Geometry (raised — one-circle/two-circle classification now matters)** | Positive post-merge angle advantage across randomized merge geometries |
| **4 — Scissors (close-in, slow-speed)** | Flat Scissors, Rolling Scissors | Reactive scripted defender or frozen self-play checkpoint | **#3 Energy (highest weight — scissors is fundamentally an energy contest)**, #1 Positional (tightened AOT tolerance) | Wins scissors exchanges vs. a fixed-skill scripted opponent within episode budget |
| **5 — Defensive survival** | Defensive Spiral | Self-play, asymmetric start (agent placed defensive, opponent has initial rear-hemisphere advantage) | **#5 Terminal/survival (raised)**; energy term sign/target flipped for the defender role (see note below) | Survives from disadvantaged starts above a target rate, or forces attacker overshoot |
| **6 — Free-play league** | All of the above, unlabeled | Self-play league (pool of past checkpoints) | Anneal shaping terms (#1–#4) down, **#5 Terminal win/loss/timeout dominant** | Win-rate vs. a fixed baseline/heuristic bot at or above your target threshold |

**Note on Stage 5's asymmetric energy term:** everywhere else in this curriculum, positive Ps (gaining energy) is treated as good. In the Defensive Spiral regime specifically, the historically correct defensive tactic is to *minimize acceleration* (i.e., deliberately stay energy-negative) to force a faster attacker to overshoot. If you keep a single fixed-sign energy reward across all stages, Stage 5 will fight your reward function. Handle this either by (a) making the energy-term sign role-conditional (attacker wants Ps↑, defender wants controlled Ps↓ while behind the attacker's nose), or (b) simply not including the energy term at full weight during Stage 5 and leaning on the terminal/survival term instead — the second option is simpler and often sufficient.

**General curriculum practice worth keeping:** advance a stage only after a rolling win-rate/success-rate threshold is met over N evaluation episodes (not just N training episodes) against that stage's opponent, and keep a small replay fraction of earlier-stage scenarios mixed in during later stages to avoid catastrophic forgetting of basic pursuit/energy skills once the agent is deep into scissors/free-play stages.

---

## Part 9 — On Real Aircraft Performance Numbers

Worth flagging directly: Shaw's book, written in 1985, deliberately avoids publishing real classified/sensitive aircraft performance tables (turn rate vs. Mach for specific jets, actual Ps contours for the F-16, etc.) — its Appendix uses **generic, illustrative "typical fighter" example diagrams** (V-n diagrams, H-M diagrams) rather than real named-aircraft data tables. So there isn't a data table in this source to extract for actual F-16/FA-50 numbers.

For your JSBSim reward functions, the actual aircraft-specific performance data you need (real turn rate/radius vs. speed/altitude, real thrust/drag curves) will come from:
- **JSBSim's own aircraft XML configs** (aerodynamic tables, engine deck) — you can compute n, TR, RT, Es, Ps directly from simulated state each step using the formulas in Part 3–4 above, which is actually more accurate than any static table.
- Publicly available unclassified performance data (e.g., NASA technical reports, USAF unclassified flight manuals where available) if you want independent validation numbers.

The formulas above are the reusable part; the numbers should come from your simulation, not from this book.
