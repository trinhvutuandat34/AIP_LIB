# AERIAL COMBAT TACTICS: DETAILED BT MODEL GUIDE
*Technical Reference for AI Fighter Behavior Implementation*

---

## TABLE OF CONTENTS
1. [Basic Fighter Maneuvers](#basic-fighter-maneuvers) — Detailed execution procedures
2. [Offensive Tactics](#offensive-tactics) — Attack geometry and positioning
3. [Defensive Tactics](#defensive-tactics) — Evasion and escape procedures
4. [One-versus-One Maneuvering](#one-versus-one-maneuvering) — Tactical selection logic
5. [Intercept & Pre-Engagement Tactics](#intercept--pre-engagement-tactics) — Approach algorithms
6. [Energy Management Principles](#energy-management-principles) — Mathematical framework
7. [Tactical Decision Framework](#tactical-decision-framework) — BT decision tree logic
8. [Implementation Checklist](#implementation-checklist) — Model verification

---

## BASIC FIGHTER MANEUVERS

### EXECUTION PREREQUISITES
Before executing any maneuver, verify:
- **Altitude Buffer:** Minimum 500 feet AGL for recovery
- **Energy State:** Sufficient speed for G-loading (min 250 knots for most maneuvers)
- **Opponent Awareness:** Visual contact or radar lock maintained
- **Airspace:** Clear of terrain within turn radius
- **Fuel State:** Sufficient for maneuver + recovery + extension

---

### 1. THE BREAK

**Trigger Conditions:**
- Missile warning (SAM, AAM) received
- Enemy gun fire detected
- Attacker closing from 6 o'clock position (less than 3km)
- Sudden defensive requirement (ambush situation)

**Execution Sequence:**

**PHASE 1: Turn Initiation (T0 to T+1.0 sec)**
```
ACTION: Bank aircraft 90° immediately
- Input: Roll command at maximum rate (typically 60-90°/sec depending on aircraft)
- Duration: 1.0 seconds to achieve 90° bank
- Altitude: Maintain current altitude during roll
- Purpose: Present wing planform to threat; reduce closure opportunities
```

**PHASE 2: Rudder Application (T+1.0 to T+2.5 sec)**
```
ACTION: Apply full rudder in direction of break
- Input: Rudder pedal to maximum deflection
- Pitch: Hold level pitch (~0° pitch angle) throughout
- G-Loading: Varies by aircraft, typically 4-6G during turn
- Bank Angle: Maintain 90° or increase to 110° if pursuing threat persists
- Direction: Break AWAY from threat vector; maximize angular separation
```

**PHASE 3: Sustained Turn (T+2.5 to T+5.0 sec)**
```
ACTION: Maintain hard turn until threat response known
- G-Loading: Maximum sustainable turn rate for aircraft
- Pitch Adjustment: If speed dropping below 300 knots, pitch nose down 5-10°
- Visual Scan: Search for threat aircraft; identify turn rate response
- Decision Point at T+5.0 sec:
  - IF threat turning with you → Continue turn, escalate to offensive maneuver
  - IF threat not turning → Break maneuver successful; extend for energy recovery
  - IF multiple threats detected → Assess highest priority threat; shift break direction if needed
```

**PHASE 4: Resolution (T+5.0 sec onward)**
```
IF Threat Following:
- Escalate to HIGH YO-YO or FLAT SCISSORS based on relative position
- Monitor altitude buffer; initiate climb if altitude dropping below 1000 AGL

IF Threat Not Following:
- Roll wings level; reduce G-loading to 2-3G
- Extend at maximum power setting
- Climb to increase energy state
- Distance goal: Achieve 5+ km separation before reassessing
```

**Key Parameters:**
- Break time to 90° bank: 1.0-1.5 seconds
- Sustained break G-loading: 4-8G (aircraft dependent)
- Turn rate during break: 15-25°/sec (varying by aircraft)
- Energy cost: High; plan recovery/extension afterward
- Altitude loss during break: 500-1500 feet typical
- Closure denial: Breaks prevent closure rates >600 knots/sec

**Decision Tree:**
```
IF (Missile Warning) OR (Enemy @ 6-o-clock < 3km) THEN
  Initiate BREAK
  Bank to 90°; apply rudder
  Monitor threat response
  IF (Threat matches break) THEN Escalate maneuver
  IF (Threat doesn't follow) THEN Extend away
END IF
```

---

### 2. HIGH YO-YO

**Tactical Purpose:** Prevent overshoot while maintaining offensive position; regain speed advantage

**Trigger Conditions:**
- Attacker closing on defender
- Closure rate: 300+ knots/sec
- Altitude: 5,000+ feet AGL
- Relative position: 0-30° off defender's 6 o'clock
- Range: 2-5 km behind defender

**Execution Sequence:**

**PHASE 1: Climb Initiation (T0 to T+0.5 sec)**
```
PRECONDITION: Current airspeed ≥ 400 knots
ACTION: Smoothly transition to nose-high pitch
- Pitch Target: 30-45° nose-high attitude
- G-Loading: Initially 5-7G, increasing to 8-9G at peak
- Power: Military power (full afterburner if available)
- Roll Axis: Maintain approximate heading toward defender
- Speed Loss Expectation: -100 to -150 knots during climb
- Duration: 4-8 seconds (until airspeed drops to ~300 knots)

Key: SMOOTH pitch application; avoid sudden G-transitions
```

**PHASE 2: Climb Sustainment (T+0.5 to T+4.0 sec)**
```
ACTION: Continue climb while monitoring defender's position
- Bank Angle: Adjust to keep defender in view; slight turns toward defender acceptable
- G-Loading: Maintain 7-8G; allow speed to bleed predictably
- Visual Reference: Defender should appear to "slow" relative to your nose
- Altitude Gain Target: Gain 2,000-3,000 feet above defender's current altitude
- Speed Target: Allow airspeed to decay to approximately defender's speed (±50 knots)
- Timing: At T+4.0, your airspeed should match or be slightly higher than defender's

CRITICAL: This phase creates CLOSURE RATE REDUCTION
- Your vertical separation increasing → Range increasing
- Your airspeed dropping → Closure rate decreasing  
- Defender may attempt evasive turn; note direction
```

**PHASE 3: Nose Drop (Dive Transition) (T+4.0 to T+6.5 sec)**
```
ACTION: Transition from climb to dive while turning toward defender
- Pitch Input: Push nose down smoothly to -20° to -30° pitch
- Roll Input: Bank to maintain turn toward defender's flight path
- G-Loading: Initially low (1-2G) during transition; increase to 4-5G during turn
- Target Heading: Align with defender's flight path; converge on six o'clock position
- Speed Recovery: Accelerate back to 450+ knots during this phase
- Duration: 2-3 seconds

RESULT: You are now BEHIND and BELOW defender, diving to catch up with superior energy
```

**PHASE 4: Position Refinement (T+6.5 to T+8.5 sec)**
```
ACTION: Fine-tune position for engagement
- Relative Position Goal: 2-3 km behind; 500-1000 feet below defender
- Speed Target: 50-100 knots faster than defender
- Aspect Angle: Defender oriented away from you (~180° aspect angle)
- Altitude Position: Slight altitude advantage emerging
- Weapons Ready: All firing systems prepared

OUTCOME: HIGH YO-YO COMPLETE
- Prevented overshoot ✓
- Gained altitude advantage ✓
- Gained speed advantage ✓
- Maintained offensive position ✓
- Ready for next engagement phase ✓
```

**Mathematical Model:**
```
Closure Rate Reduction = f(Climb angle, Time)
- 45° climb @ 450 knots initial speed = ~-250 knots/sec closure reduction over 4 seconds
- Result: Closure rate of 300 knots/sec reduced to ~50 knots/sec by T+4.0

Energy Conservation:
- Initial E = 0.5*m*V₁² + m*g*h₁
- At climb peak: E mostly converted to altitude (PE >> KE)
- During dive: PE converts back to KE; balanced energy state achieved
```

**Decision Tree for High Yo-Yo:**
```
IF (Attacker closing @ >300 kts/sec) AND 
   (Relative position: 0-30° off 6 o'clock) AND
   (Altitude > 5000 ft AGL) THEN
  
  INITIATE HIGH YO-YO:
    T0-0.5sec: Pitch up 30-45°; apply 7G
    T0.5-4.0sec: Climb while maintaining sight; speed bleeds to match target
    T4.0-6.5sec: Push nose down; bank toward target; accelerate in dive
    T6.5-8.5sec: Refine position; prepare engagement
    
  DECISION POINT @ T+8.5sec:
    IF (Weapons available) THEN Launch attack
    IF (Closure rate still high) THEN Repeat YO-YO
    IF (Too slow) THEN Extended dive for additional speed
    
END IF
```

**Altitude Requirements:**
- Minimum starting altitude: 5,000 feet AGL
- Altitude gain during maneuver: 2,000-3,000 feet
- Peak altitude: 7,000-8,000 feet AGL
- Landing altitude after maneuver: Back to defender's level
- Minimum recovery altitude: 1,500 feet AGL

**Speed Parameters:**
- Minimum starting speed: 400 knots
- Speed at climb peak: 300-350 knots
- Speed at dive exit: 450-500 knots
- Speed advantage at maneuver end: +50 to +100 knots over defender

**G-Force Profile:**
- Initial pitch-up: 5-7G
- Sustained climb: 7-8G
- Dive transition: 1-2G (briefly)
- Dive turn: 4-5G
- Peak G throughout: 8-9G

**Failure Conditions (Don't execute if):**
- Altitude < 5,000 feet AGL (insufficient recovery room)
- Airspeed < 300 knots (insufficient energy for climb)
- Defender already has 500+ feet altitude advantage (relative altitude disadvantage)
- Multiple threats detected in vicinity (concentration risk)
- Fuel state < 20% of capacity (energy recovery essential)

---

### 3. LOW YO-YO

**Tactical Purpose:** Recover speed/energy while pursuing; prevent overshoot when already slow

**Trigger Conditions:**
- Attacker airspeed: 250-350 knots (already slow)
- Current altitude: 3,000-8,000 feet AGL
- Relative position: Within 3km behind defender
- Altitude relative to defender: Approximately same level or slightly higher
- Closure rate: Marginal (100-200 knots/sec)

**Execution Sequence:**

**PHASE 1: Dive Initiation (T0 to T+0.5 sec)**
```
ACTION: Smoothly lower nose toward downward angle
- Pitch Target: -15° to -25° nose-down attitude
- G-Loading: Initially 2-3G; reduce toward 1G (unloaded flight)
- Power: Full throttle; afterburner if available
- Bank Angle: Slight bank (~15-20°) to maintain sight of defender
- Speed Expectation: Speed increasing 100+ knots per second
- Duration: 1-2 seconds to reach dive angle

Key: GENTLE pitch change; avoid sudden G-transitions that cause speed bleed
```

**PHASE 2: Dive Acceleration (T+0.5 to T+3.0 sec)**
```
ACTION: Continue dive while accelerating; maintain curved flight path
- Pitch Angle: Maintain -15° to -20° (not vertical dive)
- G-Loading: 2-4G during banked dive
- Turn Rate: Shallow turn rate (~5-10°/sec) toward defender's flight path
- Speed Target: Accelerate from ~300 knots to 450+ knots
- Altitude Loss: 1,500-2,000 feet during this phase
- Closure Rate: Increase to 300+ knots/sec as you accelerate into defender's path

CRITICAL: Dive angle is curved, not straight-down
- Maintains some G-loading (prevents free-fall feeling)
- Allows lateral maneuver toward defender
- Enables speed gain while tracking defender
```

**PHASE 3: Pull-Up & Turn (T+3.0 to T+5.5 sec)**
```
ACTION: Transition from dive to level flight; bank toward defensive position
- Pitch Input: Smoothly raise nose to level flight (approximately -5° to 0°)
- Bank Input: Increase bank angle to 30-45° toward defender's flight path
- G-Loading: Increase gradually from 2G to 6-7G during this phase
- Speed State: Now at 450+ knots (speed recovered successfully)
- Altitude: Back to approximate defender's altitude level
- Positioning: Converging on position 2-4km behind defender

Key: Pull-up is SMOOTH transition, not abrupt
- Gradual G-loading prevents energy loss
- Allows speed maintenance while maneuvering
```

**PHASE 4: Position Settling (T+5.5 to T+7.0 sec)**
```
ACTION: Establish stable pursuit position behind defender
- Relative Position: 2-4 km behind; same altitude level
- Speed Advantage: +100-150 knots faster than defender (gained from dive)
- G-Loading: Reduce to 3-4G for sustainable turn rate
- Aspect Angle: Defender oriented away (180° aspect)
- Weapons Status: All firing systems active

OUTCOME: LOW YO-YO COMPLETE
- Recovered airspeed successfully ✓
- Maintained pursuit geometry ✓
- Avoided overshoot ✓
- Energy advantage established ✓
```

**Key Differences from High Yo-Yo:**
```
HIGH YO-YO:
- Use when: FAST approaching defender; need to bleed speed
- Mechanism: Climb to lose speed; trade KE for PE
- Altitude change: +2000 to +3000 feet
- Speed change: -100 to -150 knots (slowing)
- Duration: 6-8 seconds
- Preferred altitude range: 5000+ feet

LOW YO-YO:
- Use when: SLOW pursuing defender; need to gain speed
- Mechanism: Dive to gain speed; trade PE for KE
- Altitude change: -1500 to -2000 feet
- Speed change: +100 to +150 knots (accelerating)
- Duration: 5-7 seconds
- Preferred altitude range: 3000-8000 feet
```

**Decision Tree for Low Yo-Yo:**
```
IF (Current airspeed 250-350 knots) AND
   (Altitude 3000-8000 ft AGL) AND
   (Behind defender, closing slowly) THEN
   
  INITIATE LOW YO-YO:
    T0-0.5sec: Pitch down -15° to -25°; reduce G to 1-2G
    T0.5-3.0sec: Maintain dive angle; accelerate; turn slightly toward target
    T3.0-5.5sec: Pull nose up smoothly; bank to intercept track
    T5.5-7.0sec: Settle into pursuit position; stabilize
    
  DECISION POINT @ T+7.0sec:
    IF (Speed now > 450 knots) AND (Position behind target) THEN Attack ready
    IF (Still slow or overshooting) THEN Consider HIGH YO-YO instead
    
END IF
```

---

### 4. LEAD TURN

**Tactical Purpose:** Cut off opponent's intended escape/turn path; force engagement in disadvantageous geometry for opponent

**Trigger Conditions:**
- Defender initiating turn (detected by turn rate onset)
- Relative position: 3-5 km away; partially offset
- Aspect angle: 30-90° (not directly behind)
- Altitude: Similar or slightly lower than defender
- Defender speed: Slower or comparable to yours

**Execution Sequence:**

**PHASE 1: Predict Turn Direction (T0)**
```
ACTION: Analyze defender's control inputs; predict turn vector
- Visual cues:
  * Wing bank angle increasing in specific direction
  * Nose rising (indicates vertical turn component)
  * Turn rate acceleration observed
- Radar cues:
  * Target heading changing in specific direction
  * Range decreasing (implies turn toward you)
  * Aspect angle rate indicating turn sense
  
DECISION: Determine if turn is:
  - Escape attempt (away from you) → Lead the escape vector
  - Evasive turn (toward you) → Lead the evasion completion point
  - Aggressive turn (toward you for engagement) → Lead the 6 o'clock completion
```

**PHASE 2: Lead Vector Calculation (T0 to T+0.5 sec)**
```
ACTION: Calculate intercept point ahead of defender's turn
- Input variables:
  * Defender's current position (X_d, Y_d, Z_d)
  * Defender's predicted turn rate (R_turn, typically 15-25°/sec)
  * Defender's speed (V_d)
  * Your position (X_a, Y_a, Z_a)
  * Your maximum turn rate (R_max)
  * Your speed (V_a)
  
- Calculation:
  * Estimated turn completion time = Turn angle / Turn rate
  * Defender position @ completion = Defender current + (V_d * time) in new heading
  * Required intercept point = Defender position at turn completion
  * Your intercept course = Navigate to intercept point
  
- Validation:
  * IF your turn rate > defender turn rate → Lead is viable
  * IF your turn rate ≈ defender turn rate → Lead is marginal; requires speed advantage
  * IF your turn rate < defender turn rate → Lead will fail; pursue standard maneuver instead
```

**PHASE 3: Lead Turn Execution (T+0.5 to T+3.0 sec)**
```
ACTION: Bank and turn aggressively to intercept predicted position
- Bank Angle: Maximum sustainable bank (typically 30-45°)
- G-Loading: 6-7G sustained turn
- Turn Rate: Your maximum turn rate (typically 18-24°/sec)
- Pitch Adjustment: Climb slightly if altitude advantage helps; descend if needed for closure
- Speed: Maintain military power; afterburner if available
- Visual Reference: Aim nose toward predicted intercept point (not current position)
- Navigation: Bank toward intercept vector

Key: You are turning MORE sharply than defender
- Your turn radius smaller = cutting the corner
- Results in position ahead of defender's turn path
```

**PHASE 4: Position Achievement (T+3.0 to T+4.5 sec)**
```
ACTION: Establish position ahead of defender's flight path
- Relative Position: 1-3 km ahead of defender along predicted new heading
- Altitude: Slightly above defender (potential advantage)
- Weapons: Gun/missile solution developing (depending on distance)
- Aspect Angle: Defender oriented toward you (forward aspect beginning)

OUTCOME: LEAD TURN COMPLETE
- Defender now turning into you = difficult evasion
- You at range advantageous position = attack opportunity
- Forced engagement in your geometry = tactical advantage
```

**Mathematical Model:**
```
Intercept Geometry:

Standard pursuit (following defender's turn):
- You follow defender's arc
- Turn radius comparison critical
- If defender turn radius larger → you gain on curved path

Lead turn (cutting ahead):
- You turn MORE sharply
- You intercept defender's intended path
- Requires accurate prediction of turn completion

Lead turn validity:
- Successful IF: (Your turn rate / Defender turn rate) > 1.1
- Marginal IF: (Your turn rate / Defender turn rate) = 1.0-1.1
- Fails IF: (Your turn rate / Defender turn rate) < 1.0

Lead distance calculation:
- Lead distance = Defender turn radius * (1 - cos(turn angle))
- Example: 15° turn, 5000 ft radius = lead distance ~320 feet
- Lead distance increases with turn angle
```

**Decision Tree for Lead Turn:**
```
IF (Defender initiating turn detected) AND
   (Your turn rate > defender turn rate + 10%) AND
   (Altitude allows safe maneuvering) THEN
   
  INITIATE LEAD TURN:
    T0: Predict turn direction and completion point
    T0-0.5sec: Calculate intercept geometry
    T0.5-3.0sec: Execute aggressive turn toward intercept point
    T3.0-4.5sec: Achieve position ahead of defender's path
    
  DECISION POINT @ T+4.5sec:
    IF (Position achieved) THEN Launch attack from advantage
    IF (Defender turns differently than predicted) THEN Adjust mid-maneuver
    IF (Turn radius insufficient) THEN Fall back to standard pursuit
    
END IF
```

**Failure Modes:**
- Defender turn rate faster than predicted → You end up behind, not ahead
- Altitude insufficient for turn → Can't achieve necessary bank angle
- Turn radius too large → Not enough turning radius available
- Defender changes turn direction → Your lead calculation becomes invalid
- Speed too low → Cannot sustain required G-loading for turn

---

### 5. NOSE-TO-NOSE TURNS (Horizontal)

**Tactical Purpose:** Rapid 90-180° bearing change; aggressive engagement initiation; force opponent into tight maneuvering

**Trigger Conditions:**
- Relative position: Head-on approach (0-30° aspect angle)
- Distance: 5-10 km separation
- Altitude: 3,000+ feet AGL
- Both aircraft have similar turn capabilities
- Engagement desired from advantageous position

**Execution Sequence:**

**PHASE 1: Turn Initiation (T0 to T+1.0 sec)**
```
ACTION: Bank aircraft toward opponent at maximum roll rate
- Bank Angle Target: 60-80° (aggressive bank)
- G-Loading: 4-5G initially; building toward 7-8G
- Pitch: Maintain level pitch during roll (no climb/dive component initially)
- Power: Full throttle; afterburner if available
- Roll Rate: Maximum available (typically 60-90°/sec)
- Duration: 1.0-1.5 seconds to achieve 60° bank

Result: Rapid transition from nose-pointing geometry to side-on approach
```

**PHASE 2: Turn Tightening (T+1.0 to T+3.5 sec)**
```
ACTION: Maintain hard turn; allow G-loading to build to maximum
- Bank Angle: Increase to 85-90° (nearly vertical bank)
- G-Loading: Increase to 8-9G (maximum for extended maneuver)
- Pitch: Monitor pitch angle; apply small adjustments if needed (±5°)
- Turn Rate: Maximum turn rate for aircraft (typically 20-24°/sec in this configuration)
- Heading Change: Approximately 60-90° of turn achieved by end of phase
- Visual Reference: Opponent should be visible from side; their nose rising as they turn

CRITICAL EVALUATION @ T+2.0 sec:
- If opponent turn rate appears FASTER than yours:
  * They may achieve inside position
  * Plan quick transition to next maneuver (vertical maneuver or flat turn)
  
- If opponent turn rate appears SLOWER than yours:
  * You gaining inside advantage
  * Continue aggressive turn to complete advantage

- If opponent appears to NOT turn:
  * Unusual; likely indicates different tactical choice (climbing, diving, extending)
  * Prepare to transition maneuver
```

**PHASE 3: Turn Completion (T+3.5 to T+5.0 sec)**
```
ACTION: Monitor relative position; prepare weapons employment or transition
- Bank Angle: Slight reduction (80-85°) if turn starting to bleed speed excessively
- G-Loading: Maintain 7-8G (sustainable level)
- Heading: Should have turned approximately 90-120° from initial approach heading
- Relative Position Assessment:
  * IDEAL: You have turned inside opponent's arc; slight positional advantage gained
  * MATCHED: Both aircraft in similar turn geometry; relative position unchanged
  * DISADVANTAGED: Opponent has tighter turn; their nose approaching your 6 o'clock

DECISION POINT @ T+5.0 sec:
- IF (Advantage gained) → Transition to lead turn or scissors
- IF (Matched) → Continue turn; escalate G-loading if altitude permits
- IF (Disadvantaged) → Transition to defensive maneuver (break, spiral, etc.)
```

**Turn Radius Calculation:**
```
Turn radius = V² / (g * tan(bank angle))
Where:
- V = velocity (ft/sec)
- g = gravity (32.2 ft/sec²)
- bank angle = aircraft roll angle

Example:
- Speed 450 knots (761 ft/sec)
- Bank angle 85°
- Turn radius = (761)² / (32.2 * tan(85°)) ≈ 4,500 feet

Comparison for similar aircraft:
- Both at 450 knots, 85° bank
- Turn radii should be approximately equal (maybe ±10%)
- Advantage goes to aircraft maintaining bank angle longer (less altitude loss)
```

**Vertical Plane Nose-to-Nose (Special Case):**

**Setup:** Both aircraft climb vertically after head-on pass
```
PHASE 1: Transition to vertical (T0 to T+2.0 sec)
- Both pull up sharply (30-45° pitch angle)
- Turn toward vertical climb path
- Both aircraft decelerating at approximately 50-100 knots/sec

PHASE 2: Vertical climb (T+2.0 to T+5.0 sec)
- Aircraft with lower wing loading (lighter, less engine thrust) climbs better
- Aircraft turns toward centerline; attempts to get nose toward opponent
- Both lose airspeed; separation opens vertically

PHASE 3: Top of climb (T+5.0 to T+7.0 sec)
- Aircraft reaching peak altitude (typically 5000-8000 feet higher)
- Both now extremely slow (150-250 knots typical)
- Aircraft with altitude advantage beginning to dive back down

OUTCOME:
- Tighter-turning aircraft (lighter wing loading) gains slight advantage at turn top
- Advantage is fleeting; must execute next maneuver quickly
- Aircraft with more energy (faster entry, better engine) can extend away
- Low-airspeed zone creates vulnerability for both aircraft
```

**Decision Tree:**
```
IF (Head-on approach detected) AND
   (Distance 5-10 km) AND
   (Altitude sufficient) THEN
   
  INITIATE NOSE-TO-NOSE TURN:
    T0-1.0sec: Bank hard; build G-loading
    T1.0-3.5sec: Continue turn; evaluate relative turn rates
    T3.5-5.0sec: Complete turn; assess position advantage
    
  DECISION POINT @ T+5.0sec:
    IF (Inside turn position achieved) THEN Attack developing
    IF (Turn rates matched) THEN Transition to aggressive maneuvering
    IF (Losing turn competition) THEN Execute break/escape maneuver
    
  SPECIAL: IF (vertical component possible) THEN
    Consider vertical nose-to-nose for maximum aggression
    
END IF
```

**Energy Trade-off Analysis:**
```
Nose-to-nose turn is HIGH-ENERGY maneuver:
- G-loading 8-9G sustained
- Speed bleed: 50-100 knots per maneuver
- Altitude loss: 500-1500 feet typical
- Duration: 5-7 seconds
- Recovery requirement: Dive/acceleration phase needed after

Energy cost vs. benefit:
- BENEFIT: Rapid positional advantage if turn rates favor you
- COST: High energy expenditure; recovery required
- NET: Use only when confident of advantage or forced by engagement

Recovery after maneuver:
- Execute dive turn for speed recovery (High Yo-Yo exit phase)
- Or: Execute unloaded extension if disadvantaged
```

---

### 6. NOSE-TO-TAIL TURNS

**Tactical Purpose:** Pursue opponent in continuous turning fight; maintain separation; avoid overshoot; win through attrition/endurance

**Trigger Conditions:**
- Relative position: Already behind opponent (20-45° off their 6 o'clock)
- Distance: 1-4 km behind
- Altitude: Approximately same level or slightly higher
- Opponent initiating continuous turns (not in straight-line flight)
- Speed: Comparable or slightly faster than opponent

**Execution Sequence:**

**PHASE 1: Turn Matching (T0 to T+2.0 sec)**
```
ACTION: Match opponent's turn rate and direction; maintain separation
- Roll Input: Bank aircraft to match opponent's bank angle (±5°)
- G-Loading: 6-7G to match opponent's turn rate
- Pitch: Monitor pitch angle; maintain level flight through turn (not climbing or descending)
- Speed: Maintain slightly higher airspeed than opponent (+25-50 knots)
- Turn Rate: Match opponent's turn rate (typically 18-24°/sec)
- Distance: Maintain 1-2 km separation during turn

Key observation points:
- Opponent's turn rate can be estimated from visual bank angle
- Faster turn rate in opponent means smaller turn radius
- Your slightly higher speed allows you to "float" outside their turn arc
```

**PHASE 2: Turn Continuation (T+2.0 to T+6.0 sec)**
```
ACTION: Continue nose-to-tail turn; monitor relative position continuously
- Bank Angle: Adjust to maintain turn rate match (typically 25-35° bank)
- G-Loading: Maintain 6-7G; monitor altitude buffer
- Speed Management: Slight speed advantage (50 knots faster) critical for this phase
- Aspect Angle: Opponent's nose remains pointed away from you throughout
- Range: May decrease slightly as you "float" on their turn arc
- Altitude Loss: 100-300 feet per 180° of turn

Tactical assessment every 30 seconds:
- Can you turn inside them? (If yes, transition to overtaking maneuver)
- Are they bleeding airspeed faster than you? (If yes, closing range slowly)
- Are they gaining on you? (If yes, you may be at disadvantage; review assumptions)

Endurance comparison:
- Larger aircraft usually worse endurance at constant G
- Lighter fighters usually better endurance at constant G
- 20-minute endurance scenarios develop based on fuel/turn rate
```

**PHASE 3: Tactical Assessment (T+6.0 to T+9.0 sec)**
```
ACTION: Evaluate situation and plan next maneuver
- Current position: Still behind opponent, 1-2 km separation, same altitude
- Speed advantage: You have +50 knots (maintained from speed management)
- Fuel state: Both aircraft burning significant fuel in sustained 6G turn
- Options analysis:
  
  OPTION A: Continue nose-to-tail indefinitely
  - Use endurance advantage (if any)
  - Opponent eventually runs out of fuel or makes mistake
  - Very long time horizon (20+ minutes)
  - Risk: Both aircraft become threatened; mutual stalemate
  
  OPTION B: Escalate to aggressive maneuver (Flat Scissors)
  - Use current position to transition to offensive maneuver
  - Risk: Gives opponent opportunity for reversal
  
  OPTION C: Break away and reposition
  - Use speed advantage to extend away
  - Recover fuel state; reset engagement
  - Time-consuming but safe
  
  OPTION D: Execute overtaking maneuver
  - Use speed advantage to "cut inside" opponent's turn
  - Aggressive; high risk if failed
```

**PHASE 4: Transition to Next Maneuver (T+9.0 sec onward)**
```
BASED ON DECISION from Phase 3:

TRANSITION A (Flat Scissors approach):
- Initiate slight nose-down pitch (5-10° down)
- Increase G-loading from 6-7G to 8-9G
- Allow speed to increase by ~100 knots
- Transition should be smooth; avoid abrupt input

TRANSITION B (Extend away):
- Roll wings level
- Reduce G-loading to 2-3G
- Maintain maximum throttle
- Gain separation; plan return when advantage clear

TRANSITION C (Overtake maneuver):
- Still in 6-7G turn
- Begin subtle inside-turn maneuver
- Increase turn rate by pressing G-loading
- Risk opponent recognizes and reverses

TRANSITION D (Maintain nose-to-tail):
- Continue current state
- Monitor fuel state continuously
- Look for opponent mistakes/errors
```

**Key Advantages of Nose-to-Tail Turns:**
```
✓ Maintains rear-quarter position (safest position)
✓ Opponent's weapons (guns, missiles) have difficulty targeting you
✓ Allows assessment before committing to aggressive maneuvers
✓ Preserves fuel more than aggressive flat turns
✓ Can transition to offense when advantage clear
```

**Key Disadvantages:**
```
✗ Slow position advantage gain
✗ Opponent may increase turn rate (put you in more disadvantaged position)
✗ Long time horizon; engagement may not conclude quickly
✗ Vulnerable to third-party threats (other enemy aircraft)
✗ Risk of slow-speed flight in adverse environment
```

**Decision Tree:**
```
IF (Positioned behind opponent) AND
   (Opponent in continuous turn) AND
   (Similar turn capabilities) THEN
   
  INITIATE NOSE-TO-TAIL TURN:
    T0-2.0sec: Match turn rate; establish separation
    T2.0-6.0sec: Continue turn; maintain speed advantage
    T6.0-9.0sec: Assess situation; evaluate next options
    T9.0+ sec: Transition to chosen maneuver
    
  DECISION POINT @ T+6.0sec:
    IF (Can overtake) AND (Altitude permits) THEN escalate to Flat Scissors
    IF (Fuel state good) THEN continue nose-to-tail indefinitely
    IF (Tired of waiting) THEN execute break/extend maneuver
    
END IF
```

---

### 7. FLAT SCISSORS

**Tactical Purpose:** Role-reversal maneuver; turn-fight for position advantage; gain behind opponent in sustained turning engagement

**Trigger Conditions:**
- Both aircraft in nose-to-nose or nose-to-tail position
- Altitude: 1,000+ feet AGL (critical; need climb room)
- Speed: Both aircraft 300+ knots
- Engagement continuous (not initial merge)
- Aircraft have similar turn capabilities

**Execution Sequence:**

**PHASE 1: Initial Turn (T0 to T+3.0 sec)**
```
ACTION: First aircraft initiates hard turn toward opponent
- Aircraft A (initiator): Banks 85-90° toward opponent
- G-Loading: 8-9G sustained turn
- Turn Rate: Maximum turn rate (typically 24°/sec)
- Pitch: Level pitch during this initial turn; don't climb or dive
- Duration: 2-3 seconds to achieve nose-on turn toward opponent
- Visual: After 2-3 seconds, aircraft A should have nose pointing back toward opponent
- Result: Aircraft A has turned approximately 90-120° from initial heading

Meanwhile, Aircraft B:
- Should recognize turning threat
- Must also initiate turn to prevent being tailed
- If B doesn't turn → B loses fight quickly
```

**PHASE 2: Opponent Counterattack (T+3.0 to T+5.0 sec)**
```
ACTION: Opponent (B) initiates turn in opposite direction to aircraft A
- Aircraft B: Banks 85-90° opposite to aircraft A's turn
- G-Loading: 8-9G sustained turn
- Turn Rate: Maximum turn rate
- Result: Both aircraft now in hard turns, turning TOWARD each other
- Aspect Angle: Rapidly changing; begins as nose-to-nose, becomes increasingly angular

Critical geometry:
- If both aircraft have EQUAL turn rate:
  * Both aircraft turning at same rate in opposite directions
  * Neither gains positional advantage
  * Both reaching approximate nose-on configuration simultaneously
  
- If Aircraft A has FASTER turn rate:
  * Aircraft A completes turn faster
  * Aircraft A gets nose behind Aircraft B's flight path
  * Aircraft A begins to gain advantage
  
- If Aircraft B has FASTER turn rate:
  * Aircraft B's turn completion faster
  * Aircraft B achieves nose-on position to Aircraft A
  * Aircraft B begins to gain advantage
```

**PHASE 3: Role Reversal Point (T+5.0 to T+7.0 sec)**
```
ACTION: Aircraft achieving nose-on advantage initiates offensive maneuver
- Aircraft A (if ahead in turn): Extends turn for 1-2 more seconds
  * Attempt to get nose completely behind opponent's flight path
  * Begin weapons employment if range permits
  
- Aircraft B (if behind): Initiates sharp reversal turn
  * Bank opposite direction (180° from current bank)
  * Try to catch Aircraft A overshooting
  * Execute "reversal" maneuver

Overshooting dynamics:
- Aircraft with more energy (speed/altitude) tends to overshoot
- Aircraft with lighter wing loading can turn tighter; less overshoot tendency
- Turn rate difference of 3-5°/sec determines winner

CRITICAL POINT: Whoever completes this phase behind the other wins the "scissors"
- Winner achieves 6 o'clock position
- Loser ends up ahead, vulnerable
- Fight outcome often determined here
```

**PHASE 4: Scissors Continuation or Resolution (T+7.0+ sec)**
```
IF (Clear Winner Emerged):
- Winner consolidates 6 o'clock position
- Prepare weapons employment
- Loser has limited escape options
- Engagement likely concluding

IF (No Clear Winner Yet):
- Both aircraft may continue scissors pattern
- Multiple pass-by events occurring
- Each aircraft attempting to get inside opponent's turn
- Pattern may repeat several times

IF (Stalemate Developing):
- Both aircraft matched turn capabilities
- Nose-to-nose pass; reverse maneuvers; repeat
- Pattern can continue indefinitely
- Fight descending to lower altitudes
- Eventually, whoever makes first mistake loses

STALEMATE WARNING:
- Low altitude + slow speed + repeated scissors = DANGER ZONE
- Eventually one aircraft will:
  * Lose control authority (structural limit)
  * Run out of fuel (forced extension)
  * Hit terrain (spatial disorientation)
```

**Flat Scissors Geometry:**
```
Side view of flat scissors:
- Both aircraft in near-horizontal plane
- Bank angles approaching 90°
- Vertical separation minimal (same altitude within 500 feet)
- Turning in opposite directions
- Closure rate decreasing as turning
- Each turn cycle takes 10-15 seconds

Winner characteristics:
- Faster turn rate (higher turn rate capability)
- Better energy state (more speed; less weight)
- Superior aileron authority (can bank faster)
- Pilot skill (smoothness; anticipation)
```

**Decision Tree:**
```
IF (In sustained turning fight) AND
   (Similar altitude) AND
   (Neither clearly ahead) THEN
   
  INITIATE FLAT SCISSORS:
    T0-3.0sec: Aircraft A turns hard toward Aircraft B
    T3.0-5.0sec: Aircraft B turns opposite direction; mutual approach
    T5.0-7.0sec: Role reversal; one aircraft gains advantage
    
  IF (You gain advantage) THEN:
    Complete turn; get behind; prepare attack
  ELSE IF (Opponent gains advantage) THEN:
    Initiate reversal turn; attempt to catch them overshooting
  END IF
    
  IF (Stalemate developing):
    Monitor altitude continuously
    Break off and extend before reaching dangerous altitude
    Reset engagement from higher altitude
    
END IF
```

**Altitude Loss During Scissors:**
```
Per complete scissors cycle (10-15 seconds):
- Altitude loss: 500-1000 feet typical
- Varies by:
  * G-loading sustained (higher G = less altitude loss)
  * Pitch angle maintained (nose-down = more loss)
  * Aircraft weight (heavier = more loss)
  
Minimum safe altitude for flat scissors: 2,000 feet AGL
- Below 1,500 feet AGL: UNSAFE; risk of ground impact
- Below 1,000 feet AGL: CRITICAL; must exit maneuver immediately
```

**Failure Modes:**
```
✗ Opponent turn rate faster → You lose each scissors cycle
✗ Both aircraft slow down excessively → Altitude loss critical
✗ Altitude drops below 500 feet → Unsafe recovery zone
✗ Fuel running low → Can't continue sustained 8-9G turns
✗ Pitch not maintained level → Inadvertent climb/dive develops
✗ Opponent extends vertically → Flat scissors breaks down; transitions to vertical
```

**Recovery from Flat Scissors (if losing):**
```
WHEN TO ABORT FLAT SCISSORS:
- Altitude drops below 1,500 feet AGL
- Opponent gaining clear advantage (3-4 consecutive cycles)
- Fuel state warning
- Any uncertainty about aircraft control

ABORT PROCEDURE:
T0: Roll wings level; nose slightly up (5-10° pitch)
T+1: Reduce G-loading from 8G to 2-3G
T+2: Apply maximum throttle; begin climb at 10-15° pitch
T+3: Gain altitude while slowing
T+4: Evaluate situation from higher, safer altitude
```

---

### 8. VERTICAL SCISSORS

**Tactical Purpose:** Negate speed advantage through gravity effect; defensive maneuver for slower aircraft; extend turn capability at low speed

**Trigger Conditions:**
- Defender significantly slower than attacker
- Defender has altitude buffer (5,000+ feet AGL)
- Attacker attempting high-speed pursuit
- Relative position: Near or in merge phase
- Vertical maneuvering space available

**Execution Sequence:**

**PHASE 1: Vertical Entry (T0 to T+1.5 sec)**
```
ACTION: Defender initiates sharp climb to vertical or near-vertical attitude
- Pitch Input: Nose up sharply to 60-80° pitch angle
- Bank: Roll to near-vertical bank (75-85°) in direction away from attacker
- G-Loading: 6-8G initially during pitch-up
- Speed: Entering at slower speed (350-400 knots)
- Effect: Rapid transition from level flight to climbing spiral

Attacker's situation:
- Coming in at high speed (450+ knots)
- Higher energy state
- Overshooting tendency very strong
```

**PHASE 2: Vertical Climb Phase (T+1.5 to T+5.0 sec)**
```
ACTION: Both aircraft climbing in near-vertical plane; gravity negates speed advantage
- Defender: Maintaining 60-80° pitch; ~5-6G loading
- Defender speed: Decelerating at 80-120 knots/second (gravity pulling back)
- Defender altitude: Gaining 3,000-4,000 feet during this phase
- Defender turn rate: Slow in vertical plane (5-10°/sec)

- Attacker: Following with high speed initially (480+ knots)
- Attacker speed: Decelerating at 100-150 knots/second (higher deceleration due to higher speed and G)
- Attacker pitch: Must also climb steeply to follow (70-80° pitch)
- Attacker G-loading: 6-8G (similar to defender, despite speed difference)

CRITICAL INSIGHT:
- Both aircraft decelerating at approximately same rate (gravity acts equally)
- Speed advantage erased by physics
- Defender's tighter turn capability now becomes advantage
- Defender may get inside opponent's climb arc
```

**PHASE 3: Peak Altitude and Reversal (T+5.0 to T+8.0 sec)**
```
ACTION: Both aircraft reaching peak altitude; situation reversal begins
- Defender altitude: Peak of climb (typically 8,000-12,000 feet higher than entry)
- Defender speed: Critically low (150-200 knots)
- Defender energy: Mostly altitude; very little speed

- Attacker altitude: Slightly lower peak (200-500 feet less)
- Attacker speed: Slightly higher (250-300 knots, but still very slow)
- Attacker energy: Also mostly altitude; very low kinetic energy

At peak: Brief moment where both aircraft are near-vertical attitude, extremely slow

Then REVERSAL occurs:
- Defender with tighter turn radius has nose pointing more toward attacker
- Defender can roll wing level and begin diving away
- Attacker still nose-up; can't immediately follow
- Result: Defender begins descent; can regain speed
```

**PHASE 4: Dive and Escape (T+8.0 to T+12.0 sec)**
```
ACTION: Both aircraft diving for speed recovery; separation developing
- Defender: Nose pointed down 20-40° pitch
- Defender speed: Accelerating 150+ knots/second during dive
- Defender position: Moving away; gaining separation
- Defender altitude: Losing 2,000-3,000 feet during escape

- Attacker: Also diving but from higher initial altitude
- Attacker speed: Accelerating; regaining energy
- Attacker position: Following; attempting to maintain contact
- Attacker catch-up rate: Depends on dive angle and pitch management

OUTCOME:
- Defender successfully negated attacker's speed advantage
- Defender escaped from near merge
- Both aircraft restored to safe energy levels
- Engagement reset from different geometry
```

**Energy Analysis of Vertical Scissors:**
```
Key equation: Both aircraft decelerate at approximately same rate when climbing vertically

Deceleration rate ≈ g * sin(pitch angle)
- At 80° pitch: deceleration ≈ 9.8 m/s² * sin(80°) ≈ 31 ft/sec²
- This is independent of aircraft weight or thrust!

Example:
- Attacker at 480 knots enters vertical climb
- Defender at 320 knots enters same vertical climb
- After 5 seconds of climb:
  * Attacker speed: 480 - (155 ft/sec² * 5 sec) / 1.688 = ~460 knots (slight speed loss only)
  * Defender speed: 320 - (155 ft/sec² * 5 sec) / 1.688 = ~300 knots (minimal loss from gravity)
  
Wait—this math shows speed advantage still there!

Correct analysis:
- Turn radius at slow speeds favors lighter aircraft
- Attacker's heavier airframe has larger turn radius even at same G
- Defender's lighter airframe can turn tighter
- This tighter turn radius in vertical plane allows defender to position inside attack path
```

**Decision Tree:**
```
IF (Significantly slower than attacker) AND
   (Altitude > 5000 ft AGL) AND
   (Merge imminent) THEN
   
  INITIATE VERTICAL SCISSORS:
    T0-1.5sec: Pitch up to 60-80°; initiate vertical climb
    T1.5-5.0sec: Continue climb; both aircraft decelerating together
    T5.0-8.0sec: Peak altitude reached; prepare reversal
    T8.0-12.0sec: Dive away; regain speed; escape
    
  OUTCOME:
    ✓ Negated attacker's speed advantage
    ✓ Escaped from unfavorable merge
    ✓ Energy reset; new engagement geometry
    
END IF
```

**Speed/Altitude Trade Comparison (Vertical Scissors):**
```
Vertical scissors energy state:
- Converts kinetic energy (speed) to potential energy (altitude)
- Defender deliberately trades speed for altitude
- Result: Altitude advantage + slower speeds for both

Why effective:
- Defender's goal: Escape (achieved)
- Defender's cost: Lost altitude for gain in time/distance
- Attacker's cost: Also lost speed; no gain in relative position
- Physics: Gravity acts on all aircraft equally
```

---

### 9. ROLLING SCISSORS

**Tactical Purpose:** Advanced evasion; three-dimensional maneuver; complicate pursuit geometry; extend turn capability

**Trigger Conditions:**
- Flat scissors developing (not wanted)
- Attacker attempting to get inside your turn
- Aircraft with high roll authority
- Altitude: 2,000+ feet AGL
- Speed: 300+ knots

**Execution Sequence:**

**PHASE 1: Scissors Entry with Roll Component (T0 to T+2.0 sec)**
```
ACTION: Initiate flat scissors with simultaneous roll component
- Bank Angle: Begin at 70° bank (flat scissors position)
- Pitch: Level pitch maintained (0°)
- Roll Rate: Begin rolling in either direction at moderate rate (30-40°/sec)
- G-Loading: 6-7G during turn; reduce to 3-4G during roll portions
- Result: Instead of steady-state flat turn, aircraft oscillates between different bank angles
```

**PHASE 2: Roll Oscillation (T+2.0 to T+6.0 sec)**
```
ACTION: Continue scissors pattern but adding roll oscillation
- Bank angle cycles between:
  * 70-80° (high bank flat turn)
  * 40-50° (moderate bank turn)
  * 20-30° (shallow bank turn)
  * Back to 70-80° (high bank)
  
- Cycle period: Each oscillation takes 8-12 seconds
- G-loading: Varies 6-8G during high bank; 2-4G during roll
- Turn rate: Appears to change as bank angle changes; confuses attacker
- Visual appearance: Aircraft appears to oscillate side-to-side while turning
```

**PHASE 3: Three-Dimensional Evasion (T+6.0 to T+10.0 sec)**
```
ACTION: Add vertical component to rolling scissors (full 3D maneuver)
- Pitch: Begin adding small pitch oscillations (±10° around level)
- Result: Aircraft path becomes:
  * Horizontal turn (from flat scissors)
  * Roll oscillation (from rolling component)
  * Small climb/dive oscillation (from pitch component)
  * Complete 3D spiral-turn pattern
  
- Effect: Attacker sees rapidly changing geometry
- Attacker's targeting solution invalid (constantly changing aspect)
- Attacker's turn rate calculation difficult (dynamic angles)
```

**PHASE 4: Maneuver Resolution (T+10.0+ sec)**
```
ACTION: Either continue rolling scissors or transition to next maneuver
- Fuel state: Rolling scissors high-energy; check fuel
- Altitude: Monitor altitude loss (rolling scissors descends 100-200 ft per cycle)
- Attacker status: Evaluate if still in contact
- Options:
  * Continue if advantage apparent
  * Transition to break/extension if fatigued
  * Transition to aggressive counter-attack if opportunity opens
```

**Rolling Scissors Advantages:**
```
✓ Highly dynamic; difficult to predict
✓ Rapidly changing aspect angles confuse missiles
✓ Requires excellent pilot control authority
✓ Uses full 3D airspace; maximizes maneuver options
✓ Provides escape opportunities in chaotic geometry
```

**Rolling Scissors Disadvantages:**
```
✗ Very high fuel consumption (constant maneuvering)
✗ Requires excellent aircraft control authority
✗ Difficult to judge geometry for weapons employment
✗ Risk of spatial disorientation for pilot
✗ Unsustainable for long durations
```

---

### 10. BARREL ROLL ATTACK

**Tactical Purpose:** Prevent overshoot while maintaining offensive tracking; regain speed advantage after close merge

**Trigger Conditions:**
- Defender executing turn to left or right
- Attacker at 2-3 km behind; high closure rate (400+ knots/sec)
- Altitude: 4,000+ feet AGL
- Energy state: Attacker has significant speed (500+ knots)
- Position: Slightly high and behind defender

**Execution Sequence:**

**PHASE 1: Barrel Roll Initiation (T0 to T+0.5 sec)**
```
ACTION: Roll opposite direction from defender's turn; begin climb
- Bank Input: Roll sharply opposite to defender's break turn
- Speed: Entering at high speed (500+ knots)
- G-Loading: Initially 4-5G from roll initiation
- Pitch: Begin nose-up input (20-30° pitch up)
- Result: Aircraft entering barrel roll trajectory
  
Example:
- Defender breaks left → Attacker rolls right while pitching up
- Creates corkscrew path around defender
- Attacker path spirals over the top of defender's turn
```

**PHASE 2: Roll Execution (T+0.5 to T+2.5 sec)**
```
ACTION: Complete barrel roll while maintaining pursuit geometry
- Roll rate: Maximum roll rate (typically 90-120°/sec)
- G-loading: Increase to 7-8G during sustained barrel roll
- Pitch progression: Climb from 20° to 60° pitch over 2 seconds
- Speed: Decreasing due to climb (losing 100-150 knots)
- Turn axis: Maintain approximate heading toward defender

Defender's perspective:
- Defender completing their turn
- Attacker disappears from direct line of sight
- Attacker reappears over the top
- Relative separation opening due to climb
```

**PHASE 3: Roll Completion (T+2.5 to T+4.0 sec)**
```
ACTION: Complete barrel roll; reposition for continued pursuit
- Roll completion: Aircraft rolls 360° back to original bank angle (level wings)
- Pitch: Return to level flight or slight climb (5-15° pitch up)
- Speed: Now slower than at entry (350-400 knots instead of 500)
- Position: Directly above and behind defender

CRITICAL: Altitude advantage now exists
- Defender: At lower altitude; slower speed; turning
- Attacker: Higher altitude; good speed; repositioned
- Result: Energy exchange completed; attacker has altitude advantage
```

**PHASE 4: Sustained Pursuit (T+4.0 to T+6.0 sec)**
```
ACTION: Convert altitude advantage to positional advantage
- Pitch: Nose-down 10-20° to begin gentle dive
- G-loading: Reduce to 3-4G; allow speed to build
- Banking: Light bank toward defender's flight path; maintain pursuit
- Relative position: Begin closure on defender from above and behind

OUTCOME: BARREL ROLL ATTACK COMPLETE
- Prevented overshoot despite high closure rate ✓
- Climbed to gain altitude ✓
- Maintained general pursuit geometry ✓
- Positioned above defender for next maneuver ✓
```

**Barrel Roll Geometry:**
```
Side view of barrel roll:
- Attacker path forms spiral curve around defender
- Defender flying in relatively straight line or shallow turn
- Attacker's path curls up and over defender
- Both aircraft typically moving downrange; defender ahead

Key measurement: Vertical separation
- Start: Attacker at same altitude as defender
- Peak: Attacker 1,000-2,000 feet ABOVE defender
- End: Attacker again near defender's altitude but behind/above
```

**Decision Tree:**
```
IF (High-speed closure toward defender) AND
   (Defender executing turn) AND
   (Altitude > 4000 ft AGL) THEN
   
  INITIATE BARREL ROLL ATTACK:
    T0-0.5sec: Roll opposite to defender's break; pitch up
    T0.5-2.5sec: Execute barrel roll; climb; maintain sight
    T2.5-4.0sec: Complete roll; return to level flight
    T4.0-6.0sec: Dive gently; build speed; prepare next maneuver
    
  OUTCOME:
    ✓ Overshoot prevented
    ✓ Altitude gained
    ✓ Speed preserved relatively
    ✓ Pursuit maintained
    
END IF
```

---

## OFFENSIVE TACTICS

### PURSUIT CURVE VARIANTS

**Pure Pursuit:**
```
Definition: Attacker aims nose directly at target (aiming for current position)

Execution:
- Nose pointed at target's current position
- Continuously update aim point as target moves
- Close on target along pursuit curve

Geometry:
- Creates curved closing path
- Overshoot likely if relative speeds mismatched
- Works well if target stationary or not maneuvering

Problem:
- Target maneuvers → path becomes inefficient
- Overshoot probable against maneuvering target
- Named "pure" because it's geometrically simple but tactically simplistic
```

**Lag Pursuit:**
```
Definition: Attacker aims behind target's current position; maintains approximate distance

Execution:
- Aim nose at point behind and to the side of target
- Maintain 2-3 km distance from target
- Slowly move aim point forward as engagement progresses

Advantage:
- Prevents overshoot naturally
- Maintains distance advantage
- Allows extended engagement

Disadvantage:
- Slower position advantage gain
- Requires patience; not aggressive
- Target may extend away at any time
```

**Lead Pursuit:**
```
Definition: Attacker aims ahead of target's predicted position; intercept geometry

Execution:
- Calculate target's movement vector (direction + speed)
- Predict target position 10-30 seconds in future
- Aim nose at predicted target position
- Converge on predicted intercept point

Advantage:
- Most efficient path to target
- Minimizes distance traveled
- High probability of intercept

Disadvantage:
- Requires accurate speed/heading prediction
- Target maneuvers → prediction becomes invalid
- Complex calculation for real-time execution

Mathematical model:
```
Intercept calculation:
Let:
- P_t = target position
- V_t = target velocity vector
- P_a = attacker position  
- V_a = attacker velocity (max speed toward intercept point)

Intercept occurs when:
P_t + V_t * t_intercept = P_a + V_a * t_intercept

Solving for t_intercept gives time to intercept
Intercept point = P_t + V_t * t_intercept
```

---

### LAG DISPLACEMENT ROLL

**Tactical Purpose:** Gain angular advantage while maintaining distance; efficient counter-maneuver to opponent closing from side

**Trigger Conditions:**
- Opponent attempting to move to your side (90° aspect or approaching it)
- Distance: 2-5 km
- Altitude: Similar level
- Speed: Similar or slightly faster than opponent
- Goal: Prevent opponent from establishing side position

**Execution Sequence:**

**PHASE 1: Recognition (T0)**
```
ACTION: Detect opponent lateral movement
- Radar: Aspect angle changing (moving away from 180° = pursing you)
- Visual: Aircraft moving toward your right or left side
- Turn rate: Opponent's turn rate apparent; direction of turn noted

Decision point: Lag displacement roll is reactive maneuver
- Use only when opponent moving to your side
- Not appropriate for direct pursuit situations
```

**PHASE 2: Roll Initiation (T0 to T+1.0 sec)**
```
ACTION: Roll sharply in direction opposite to opponent's movement
- Bank angle: Roll to 60-70° bank (not full 90°)
- Roll rate: Maximum roll rate (90-120°/sec)
- Pitch: Maintain level or very slight climb (0-5° pitch)
- G-loading: 3-4G during roll
- Direction: Roll AWAY from opponent's approach direction

Example:
- Opponent moving to your left side → You roll right
- Creates immediate angular separation
- Opponent's lateral closing slowed
```

**PHASE 3: Roll Completion (T+1.0 to T+2.0 sec)**
```
ACTION: Complete roll; assess new relative position
- Bank angle: Return to level wings or establish opposite bank
- Speed: Approximately same as before (small speed bleed acceptable)
- Altitude: Approximately same (slight change acceptable)
- Relative position: Opponent's approach path to your side now blocked
- Distance: May increase slightly due to maneuver
```

**PHASE 4: Follow-up Maneuver (T+2.0 onward)**
```
ACTION: Execute next maneuver based on new geometry
- If opponent still closing: Repeat lag displacement roll in same direction
- If opponent changing approach: Transition to appropriate counter-maneuver
- If opponent breaking off: Return to neutral positioning
```

**Lag Displacement Roll Advantages:**
```
✓ Efficient energy use (low G, quick maneuver)
✓ Effective against lateral closing attempts
✓ Can be repeated multiple times
✓ Maintains general offensive/defensive posture
✓ Works against both aircraft types
```

**Lag Displacement Roll Disadvantages:**
```
✗ Limited effectiveness if opponent also maneuvering vertically
✗ Only effective for lateral closing prevention
✗ Not suitable for direct nose-to-tail pursuit
✗ May expose you to other threats
```

---

### SHACKLE MANEUVER (Two-Aircraft)

**Configuration:** Lead aircraft turns one direction; wingman turns opposite direction

**Execution:**
```
Lead aircraft:
- Bank 60-70° left
- Turn rate ~15-20°/sec
- Maintain altitude
- Continue turn for 4-6 seconds

Wingman:
- Bank 60-70° right  
- Turn rate ~15-20°/sec (matching lead if possible)
- Maintain altitude
- Turn in opposite direction simultaneously

Result:
- Two aircraft diverging in a crossing pattern
- Creates weaving pattern with lead ahead and wingman trailing
- Any attacker on lead must also deal with trailing wingman
- Two aircraft creating difficult targeting problem
```

**Effectiveness Against Attacking Aircraft:**
```
Attacker attempting to target lead:
- Must account for both aircraft in formation
- If attacker focuses on lead: wingman can attack
- If attacker focuses on wingman: lead can attack
- Cannot ignore either aircraft
- Creates split decision problem

Defenses:
- Attacker must target one aircraft decisively
- Separated attack reduces effectiveness
- Both fighters providing mutual defense
```

---

### BRACKET MANEUVER (Two-Aircraft)

**Tactical Purpose:** Entrap enemy between two attacking aircraft; eliminate escape options

**Execution:**
```
Formation:
- Aircraft A: Positioned on one side of target (30-45° off nose)
- Aircraft B: Positioned opposite side of target (30-45° off nose on other side)
- Distance from target: Both aircraft 2-4 km away
- Altitude: Similar to target

Attack:
- Both aircraft converge simultaneously
- Target caught between two approaching threats
- Cannot evade both without exposing to other
- One aircraft will likely achieve missile/gun lock

Geometry:
```
        Aircraft A
           /
          /
    Target ----
          \
           \
        Aircraft B
```

**Target's Dilemma:**
```
Option 1: Turn toward Aircraft A
- Moves into better position relative to A
- But exposes rear to Aircraft B
- B can launch rear-aspect missile

Option 2: Turn toward Aircraft B
- Moves into better position relative to B
- But exposes rear to Aircraft A
- A can launch rear-aspect missile

Option 3: Turn into center between them
- Both aircraft gain relative advantage
- Likely loses against both
- Poor option

Option 4: Extend away from both
- Creates distance from both threats
- Only viable escape option
- Requires superior speed/energy
```

**Bracket Effectiveness:**
```
Most effective against:
- Slower targets
- Targets without rear-aspect missile capability
- Targets already engaged with friendly forces (distracted)

Less effective against:
- Fast targets (can out-accelerate both)
- Targets with all-aspect missiles (can fire back at either aircraft)
- Experienced pilots (break between threats; engage one then other)
```

---

### SINGLE-SIDE OFFSET

**Tactical Purpose:** Achieve favorable attack geometry; position for gun/missile employment while limiting target's evasion options

**Execution:**
```
Step 1: Determine target's altitude and heading
- Maintain 3-5 km distance from target
- Observe target's flight path
- Plan offset approach

Step 2: Position to one side
- Select one side (typically based on target's evasion options)
- Move to 30-45° off target's nose (lateral offset)
- Altitude: Slightly higher or lower than target (creates separation options)

Step 3: Close to weapon employment range
- Gradually reduce range from 5 km to 2-3 km
- Maintain lateral offset position
- Adjust altitude as needed for shot geometry

Step 4: Weapons employment
- From this position, present difficult evasion geometry
- Target cannot reverse back without moving toward you
- Target cannot climb/dive without losing speed
- Limited escape options available
```

**Geometry:**
```
Side view:
        Your altitude
             |
        You (offset)
            /
           /
        Target (flying toward/away from page)
           \
            \
        Offset position = 30-45° off nose
        Range = 2-3 km
        Altitude = slightly higher or lower

Top view:
           Target
          /  \
         /    \
        /      \
       /        \
      You----Target
   (offset position)
  
  30-45° lateral offset
  2-3 km range
```

**Advantages:**
```
✓ Target has limited evasion options
✓ Good weapons employment geometry
✓ Can transition to other attacks easily
✓ Maintains separation (safe range)
```

---

### DRAG MANEUVER (Two-Aircraft)

**Tactical Purpose:** Entice enemy to commit to pursuing one aircraft while setting up counter-attack by second aircraft

**Execution Sequence:**

**PHASE 1: Formation Setup (T0)**
```
Formation:
- Lead aircraft (dragger): 1-2 km ahead
- Trailing aircraft (trailer): 1-2 km behind
- Both at same altitude initially
- Formation heading toward friendly territory or defensible position
```

**PHASE 2: Enemy Engagement (T0 to T+10 sec)**
```
Enemy observes:
- Two allied aircraft in formation
- Lead aircraft appears more visible/tempting target
- Dragger running at low altitude, high speed
- Trailer harder to see; maintaining position

Enemy chooses:
- Usually pursues lead (dragger)
- Dragger entices pursuit through maneuvers
- Trailer maintains position; detects enemy approach

Dragger maneuvers:
- Shallow turns; appears to be "running away"
- Makes slight evasive movements
- Acts as bait; appears vulnerable
- Draws enemy focus entirely
```

**PHASE 3: Trap Springing (T+10 to T+15 sec)**
```
Trailer detects committed enemy:
- Enemy fully focused on dragger
- Enemy closing on dragger for attack position
- Trailer now has perfect setup

Trailer action:
- Aggressive maneuver toward enemy
- Rapidly close distance
- Force enemy to choose between dragger and trailer
- Enemy typically cannot engage both

Result:
- If enemy continues chasing dragger: Trailer gets firing pass
- If enemy turns to defend against trailer: Dragger escapes or reverses
- Either way, split attention creates opportunity
```

**Drag Effectiveness:**
```
Most effective against:
- Single attacking aircraft
- Novice pilots (easy to entice into trap)
- Aggressive pilots (follow lead aircraft too closely)

Less effective against:
- Multiple attacking aircraft (can split attacks)
- Cautious enemy (maintains distance; refuses to commit)
- Experienced pilots (detect setup; attack trailer instead)
```

**Communication Requirements (Formation Drag):**
```
CRITICAL: Excellent communication between dragger and trailer
- Dragger must know trailer is positioned
- Trailer must know enemy approach
- Both must time movements together
- Radio callouts essential (if allowed by mission rules)
```

---

### LEAD-AROUND MANEUVER (Two-Aircraft)

**Tactical Purpose:** Create split-targeting problem by separating from wingman; force enemy to choose which aircraft to pursue

**Setup:**
```
Initial formation:
- Lead aircraft ahead
- Trailing aircraft 1-2 km behind (trail formation)
- Both heading toward/away from enemy force
- Speed: High (typically 450+ knots for evasion)
```

**Execution Sequence:**

**PHASE 1: Approach Phase (T0 to T+10 sec)**
```
Situation:
- Lead aircraft detects enemy at predetermined range
- Enemy approaching for intercept
- Closure rate: 400-600 knots/sec combined

Lead action:
- Monitor closure with enemy
- Maintain heading toward predetermined break point
- Brief trailing aircraft via radio callout (if possible)
```

**PHASE 2: Break Point (T+10 to T+12 sec)**
```
Lead breaks away:
- At predetermined range (typically 20-30 km)
- Lead aircraft banks sharply (60-70° bank)
- Turns one direction (left or right)
- Builds lateral separation from original heading
- Creates displacement distance and angle

Trailer action:
- Continues on original heading momentarily
- Watches lead's break turn
- Prepares to continue or follow (depends on mission)
- Maintains altitude if continuing

Result:
- Lead aircraft now offset 5-10 km laterally
- Trailer still on original course
- Enemy must choose which to pursue
```

**PHASE 3: Enemy Decision Point (T+12 to T+15 sec)**
```
Enemy choices:

CHOICE A: Pursue lead aircraft
- Lead has speed advantage (built displacement)
- Trailer now behind enemy's original direction
- Trailer can attack from rear/side

CHOICE B: Continue for trailer
- Lead can reverse and attack from other direction
- Trailer prepared for engagement from front

CHOICE C: Split force
- One fighter pursues lead
- One fighter continues for trailer
- Creates 1v1 engagements instead of 1v2
- Generally reduces combat effectiveness of attacking force
```

**Lead-Around Advantages:**
```
✓ Forces split decision by enemy
✓ Reduces effectiveness of single attacking aircraft
✓ One allied aircraft likely gets advantage
✓ Converts 2-v-1 into 1-v-1 plus reserve aircraft
```

**Decision Tree (Formation Tactics):**
```
IF (Enemy single aircraft closing from behind) AND
   (Formation in trail) AND
   (Sufficient separation between lead/trailer) THEN
   
  EXECUTE LEAD-AROUND:
    T0: Detect enemy; begin approach
    T+10: At predetermined range, lead breaks away
    T+12: Observe enemy choice
    IF (Enemy pursues lead) THEN:
      Trailer attacks enemy from rear position
    ELSE IF (Enemy continues for trailer) THEN:
      Lead reverses; builds attack geometry on enemy's 6
    END IF
    
END IF
```

---

## DEFENSIVE TACTICS

### WEAVE MANEUVER (Two-Aircraft)

**Configuration:**
```
Side-by-side or stepped formation
- Aircraft A at altitude H
- Aircraft B at altitude H + 300-500 feet
- Lateral separation: 500-1000 feet (side by side)
- Both aircraft flying parallel headings
- Both maintaining formation discipline
```

**Weaving Pattern:**
```
Path diagram (top view):

Aircraft A: ~~~~ (weaving path)
Aircraft B: ~~~~ (weaving path, synchronized)

Both aircraft:
- Make coordinated shallow turns (15-25° bank)
- Turn toward each other periodically (every 20-30 seconds)
- Cross flight paths briefly
- Resume parallel formation
- Repeat pattern

Crossing geometry (top view):
    A   B        A   B
     \ /          | |
      X      →     |      →    \ /
     / \          | |            X
    
    (crossing)   (parallel)   (crossing again)
```

**Effectiveness:**
```
Against single attacker:
- Cannot focus on single target (constantly moving)
- Must account for both aircraft
- Attacking one exposes to other
- Both aircraft can defend each other

Against multiple attackers:
- Less effective
- Attackers can split forces
- Each attacker pursues different aircraft
- Weaving provides reduced mutual defense
```

**Weave Timing:**
```
Turn cycle period: 30-45 seconds per complete cycle
- Each aircraft completes approximately 10-15° turn toward each other
- Then returns to parallel course
- Then repeats

Visual appearance:
- From distance: Two aircraft side-by-side
- From close range: Pattern appears as sine-wave path
```

---

### NOTCH MANEUVER

**Tactical Purpose:** Achieve defensive positioning against beam-aspect threat; counteract missile with lateral evasion

**Trigger Conditions:**
- Enemy missile launch detected (rear-aspect missile)
- Enemy at 90° relative position (beam aspect)
- Missile approaching from side

**Execution:**
```
T0: Detect missile launch/warning
- Missile warning system alerts
- Determine missile aspect (from which direction)
- Prepare immediate evasive action

T+0.5 sec: Notch maneuver initiation
- Bank sharply toward missile threat
- Pitch nose slightly up
- Turn to position bandit on your wingline (90° relative)
- Hard turn rate (6-8G)

T+1.0-2.0 sec: Sustained notch position
- Maintain 90° relative bearing to missile source
- Present beam aspect to incoming missile
- Missile has difficulty tracking on beam (reduced RCS)
- Evaluate evasion options

Result:
- Missile forced off beam-aspect intercept
- Missile may miss or detonation angle poor
- Creates survival opportunity
```

**Notch Geometry:**
```
Bird's eye view:

Normal threat approach (90° aspect):
        You (heading →)
         |
        /
       /
    Enemy ← (missile approaching from side)

After notch maneuver (90° relative):
        Enemy ← (now on your wingline)
         |
        You (banked 90°, heading sideways relative to original)
```

---

### PUMP MANEUVER

**Tactical Purpose:** Create separation from threat while maintaining reengagement capability

**Execution:**
```
T0: Threat assessment
- Determine threat bearing
- Assess threat type (aircraft, missile, etc.)
- Decide to disengage temporarily

T+1.0 sec: Initial maneuver
- Bank away from threat bearing
- Increase turn rate (6-7G)
- Begin turning away

T+2.0-5.0 sec: Sustained turn-away
- Continue turning to 180° away from threat
- Create maximum distance
- Build separation

T+5.0 sec: Hold away position
- Maintain course away from threat
- Monitor threat response
- Evaluate threat location

T+10.0+ sec: Reevaluation
- Assess threat position
- Determine if reengagement possible
- Plan next maneuver

Key difference from pure break:
- Pump implies temporary separation (pump = to move in/out)
- Maintains reengagement intention
- Not permanent escape; tactical pause
```

**Pump Advantages:**
```
✓ Creates temporary breathing room
✓ Allows threat assessment
✓ Can reset engagement geometry
✓ Less commitment than full extend
```

**Pump Disadvantages:**
```
✗ Threat can also reposition during pump
✗ Separation may not be maintained
✗ May miss reengagement opportunity if not coordinated
✗ Requires wingman support for awareness
```

---

## ONE-VERSUS-ONE MANEUVERING

### TACTICAL DECISION ALGORITHM

**Input Variables:**
```
Self:
- Current airspeed (V_self)
- Current altitude (Alt_self)
- G-loading capability (G_max)
- Fuel state (F_fuel)
- Weapons state (W_state)
- Current turn rate capability (TR_self)

Opponent:
- Estimated airspeed (V_opp)
- Estimated altitude (Alt_opp)
- Estimated G-capability (G_opp_est)
- Estimated turn rate (TR_opp_est)
- Weapons state observed (W_opp_est)
- Behavior pattern (aggressive, defensive, evasive)

Engagement state:
- Relative range (R)
- Relative aspect angle (Aspect)
- Current relative position (Six, Flank, Beam, Nose, etc.)
- Closure rate (V_closure)
- Time in current maneuver (T_maneuver)
```

**Energy State Calculation:**
```
Energy_self = 0.5 * m * V_self² + m * g * Alt_self
Energy_opp = 0.5 * m_opp * V_opp² + m_opp * g * Alt_opp

Energy ratio = Energy_self / Energy_opp

IF Energy_ratio > 1.2 THEN:
  "YOU ARE ENERGY SUPERIOR"
  Recommendation: ANGLES TACTICS
  
ELSE IF Energy_ratio >= 0.8 AND Energy_ratio <= 1.2 THEN:
  "YOU ARE ENERGY MATCHED"
  Recommendation: ENERGY TACTICS or ANGLES based on skill assessment
  
ELSE IF Energy_ratio < 0.8 THEN:
  "YOU ARE ENERGY INFERIOR"
  Recommendation: ENERGY TACTICS / ESCAPE
END IF
```

### ANGLES TACTICS EXECUTION

**Trigger:** Energy superior OR confidence level high

**Objective:** Minimize turn rate competition time; maximize raw turning advantage

**Execution:**
```
PHASE 1: Initial Turn (T0 to T+3 sec)
- Bank 85-90° in direction toward opponent
- G-loading: 8-9G immediately
- Turn rate: Maximum (24°/sec typical)
- Pitch: Maintain level
- Goal: Get nose pointing toward opponent's projected position

PHASE 2: Aggressive Pursuit (T+3 to T+6 sec)
- Maintain maximum G-loading (8-9G)
- Monitor turn rate comparison
- If opponent turn rate slower: You gaining angular advantage
- If opponent turn rate faster: Reevaluate; consider switching to Energy Tactics
- Monitor altitude: Ensure buffer > 1500 feet AGL

PHASE 3: Position Attainment (T+6 to T+10 sec)
IF (You gaining advantage):
  Continue aggressive turn; aim for 6 o'clock position
  Close distance to 1-2 km
  Prepare weapons employment
ELSE:
  BEGIN TACTICAL TRANSITION (see below)
```

**Transition to Energy Tactics (within Angles maneuver):**
```
DECISION POINT: If 3 consecutive seconds show opponent matching or beating your turn rate

ACTION:
T0: Convert to nose-to-tail turn
- Reduce G-loading from 9G to 6-7G
- Pitch down 5-10° from level (slight descent)
- Relax turn slightly; allow speed to stabilize

T+1 to T+5: Low-G pursuit
- Maintain 6G turn; allow aircraft to accelerate
- Speed increases back toward original
- Altitude decreases but builds speed reserve
- Let opponent gain ~90° heading change

T+5: Climb phase
- Pitch up 15-20° (climb attitude)
- Reduce G-loading to 2-3G (unloaded climb)
- Build altitude advantage
- Speed slowly increasing due to less G constraint

Result: Transitioned from aggressive Angles to Energy management
- Opponent now lower/slower
- You have altitude advantage
- Re-engagement from position of strength

DECISION: Continue energy maneuvers or reset from top
```

---

### ENERGY TACTICS EXECUTION

**Trigger:** Energy inferior OR opponent matching turn rates OR high altitude risk

**Objective:** Preserve energy; maintain escape option; wear opponent down

**Execution:**
```
PHASE 1: Defensive Setup (T0)
- Maintain current heading for 5-10 seconds
- Do NOT turn hard initially
- Monitor opponent's aggressive maneuver
- Prepare counterresponse

PHASE 2: Defensive Turn (T0 to T+2 sec)
- Initiate gentle turn (15-20° bank)
- Low G-loading: 2-3G only
- Pitch: Slightly down (-5° to 0° pitch)
- Speed: Maintain or increase
- Goal: "Soft" response to opponent's aggression

PHASE 3: Sustained Evasion (T+2 to T+5 sec)
- Maintain 2-3G turn; low G-loading crucial
- Allow aircraft to accelerate slowly
- Monitor opponent position
- Turn rate slow; not competitive with aggressive opponent
- INTENT: They cannot catch you if you keep turning

PHASE 4: Energy Building (T+5 to T+10 sec)
- Look for opening to increase altitude
- Begin gentle climb if opponent below you
- Trade speed for altitude gradually
- Build energy margin

PHASE 5: Situation Reassessment (T+10 sec)
- Current altitude vs. starting altitude
- Current speed vs. opponent speed
- Horizontal separation from opponent
- Fuel state remaining

DECISION POINT:
IF (Altitude good) AND (Speed good) AND (Separation > 3 km):
  Continue low-G evasion; wear opponent down
ELSE IF (Altitude dropping dangerously):
  Extend away (increase to max power; reduce turn rate)
ELSE IF (Opponent showing fatigue):
  Prepare transition to aggressive maneuvers (Angles Tactics)
```

**Energy Tactics Key Principles:**
```
1. SPEED IS SURVIVAL
   - Never drop below 300 knots in turning fight
   - Always have throttle available for acceleration

2. ALTITUDE IS INSURANCE
   - 5000+ feet = safety margin
   - Every 1000 feet = extended combat time

3. TURN RATE IRRELEVANT
   - Cannot out-turn opponent; don't try
   - Survival through geometry avoidance

4. TIME IS ALLY
   - Opponent tires; fuel depletes
   - Eventually opponent must disengage or crash

5. ESCAPE ALWAYS POSSIBLE
   - Break maneuver available any time
   - Never trapped if fuel/altitude remaining
```

---

### WEAPON-SPECIFIC TACTICS

#### GUNS ONLY ENVIRONMENT

**Range:** Contact to 1000 meters (0.5 km)

**Tactical Implications:**
```
- Must achieve 6 o'clock position
- Range closure critical
- Turn fight inevitable
- Aggressive maneuvers required

TACTICAL APPROACH:
1. Use aggressive Angles Tactics
2. Get nose on opponent quickly
3. Close to within 500-1000 meters
4. Achieve firing geometry (gun solution)
5. Maneuver to prevent opponent recovery

Gun solution geometry:
- Must lead target for moving gunfire
- Deflection shooting required
- Target angle changes rapidly
- Sustained 6 o'clock preferred
```

**Shooting Parameters:**
```
Effective gun range: 300-1000 meters
- 300 meters: High probability hit
- 600 meters: Medium probability hit
- 1000 meters: Low probability hit

Lead angle requirement:
- Depends on target's turn rate
- Faster turning = larger lead angle
- Calculation required in real-time

Burst length:
- 100-500 rounds typical
- Short bursts (1-3 seconds) sustained
- Long bursts cause gun jamming risk
```

---

#### REAR-QUARTER MISSILES ONLY

**Range:** 5-25 km (depending on missile type)

**Tactical Implications:**
```
- Must maintain behind and below target
- Target has defensive options (hard maneuvers)
- Angles Tactics more suitable
- Extended engagement range

TACTICAL APPROACH:
1. Close to missile firing range (12-18 km typical)
2. Position in rear-quarter (4-6 o'clock area)
3. Achieve radar lock
4. Launch when firing geometry good
5. Defend against counter-attacks

Missile envelope geometry:
- Firing range extends 12-25 km (high altitude)
- Effective range 8-18 km (normal conditions)
- Missile needs 15-30 seconds flight time
- During flight, maintain defensive posture
```

**Tactical Sequence:**
```
T0: Close to firing range
- Establish contact at 25+ km
- Begin gradual closure
- Maintain rear-quarter position

T+300 seconds: Reach firing range (12-18 km)
- Verify radar lock
- Check firing parameters
- Prepare missile system

T+305 seconds: Launch missile
- Single shot or ripple fire (multiple missiles)
- Continue defensive maneuvers during missile flight
- Prepare secondary weapons

T+305 to T+335 sec: Missile in flight (30 second flight time example)
- Maintain defensive posture
- Expect counter-missile launch
- Prepare break maneuver if warning

T+335 sec: Impact expected
- Missile reaches target
- Assess results (hit, miss, near miss)
- Prepare follow-up weapons
```

---

#### ALL-ASPECT MISSILES

**Range:** 10-30+ km (any direction)

**Tactical Game Change:**
```
All-aspect missiles completely change engagement:
- No longer confined to rear-quarter
- Missiles can be fired from any position
- Forward-quarter shots possible
- Initial merge critical

TACTICAL APPROACH:
1. Extended detection range critical
2. Initial merge approach at long range (30+ km)
3. First shot from advantage = usually wins
4. Evasion of all-aspect missiles difficult
5. Energy management essential throughout
```

**Initial Merge Tactics:**
```
T-300 seconds: Target detected at 30+ km
- Determine threat intention
- Begin closure
- Maneuver for advantageous position
- Monitor weapons status

T-100 seconds: 20 km separation
- Threat closing also
- Both aircraft maneuvering for position
- First shot will likely determine fight

T-50 seconds: 10 km separation (merge imminent)
- Final positioning maneuver
- Prepare evasive actions
- High-G maneuvering space needed

T0: Merge event
- Aircraft at same location, similar altitude
- Immediate escape maneuver
- Break hard; increase altitude; execute evasion pattern

T+1 to T+5: Post-merge
- Expect missile launch from initial position
- Aggressive evasion maneuvers
- Break maneuvers critical
```

**All-Aspect Missile Evasion:**
```
When missile launch detected:
1. Hard break turn (6-8G) in direction away from launch bearing
2. Climb to maximum altitude
3. Deploy countermeasures if available (chaff, flares)
4. Unpredictable maneuver pattern
5. Turn rate continuous 6-7G
6. Accept engagement reset after evasion

Missile employment window:
- Typically 10-15 second window from launch
- After 15 seconds, evasion maneuvers reduce missile effectiveness
- Extended evasion can cause missile fuel depletion
```

---

## INTERCEPT & PRE-ENGAGEMENT TACTICS

### INTERCEPT APPROACH GEOMETRY

**Forward Quarter Intercept:**
```
Definition: Approach target from ahead and above

Setup:
- Target altitude at 15,000 feet
- Target heading east
- You positioned north of target
- Target range 30 km

Closure approach:
1. Bank toward target's flight path
2. Close on intercept vector
3. Target approaching your position
4. Relative closure rate: 600-800 knots/sec combined

Advantage:
- You can see target during approach
- Heading toward engagement range
- Tactical advantage possible

Disadvantage:
- Head-on geometry at merge
- Both aircraft high closure rate
- Requires quick tactical decision
```

**Stern Intercept:**
```
Definition: Position behind and below target; approach along flight path

Setup:
- Target altitude 15,000 feet
- Target heading east
- You positioned south, 30 km away
- Target speed approximately 450 knots

Closure approach:
1. Turn to intercept target's flight path
2. Position below and behind
3. Close on target's 6 o'clock line
4. Closure rate depends on speed advantage

Advantage:
- Rear position naturally
- Better weapons employment
- Higher probability of success

Disadvantage:
- Longer time to reach firing range (if slower)
- Target may extend away
- Requires precise positioning calculation
```

### TACTICAL INTERCEPT DECISION MATRIX

```
IF (Contact detected at long range) THEN:

ASSESS:
- Contact altitude vs. your altitude
- Contact heading vs. your position
- Contact speed estimated
- Contact aspect angle

CHOOSE INTERCEPT PATH:

IF (Contact ahead and above):
  FORWARD QUARTER INTERCEPT
  - Direct approach
  - Head-on at merge (plan evasion)
  - Quick time-to-intercept

IF (Contact ahead and level):
  FORWARD/LEVEL INTERCEPT
  - Approach on their flight path
  - Achieve 12 o'clock position
  - Merge at their altitude

IF (Contact ahead and below):
  FORWARD/DESCENDING INTERCEPT
  - Dive to intercept path
  - Gain speed during descent
  - Approach from above

IF (Contact at same level, same heading):
  STERN/CHASE INTERCEPT
  - Follow on their 6 o'clock line
  - Close slowly if similar speed
  - Maintain separation until ready

IF (Contact behind):
  TACTICAL REVERSE
  - 180° turn to reverse roles
  - Position for engagement
  - Approach their stern

END IF
```

---

## ENERGY MANAGEMENT PRINCIPLES

### ENERGY STATE MEASUREMENT

**Specific Energy:**
```
E_s = V²/(2g) + h

Where:
- V = velocity (feet/second)
- g = gravitational acceleration (32.2 ft/sec²)
- h = altitude (feet)

This gives energy per unit weight in feet of altitude

Example calculations:
- 450 knots at 15,000 feet
- 450 knots = 759 ft/sec
- E_s = (759)² / (2*32.2) + 15,000
- E_s = 8,945 + 15,000 = 23,945 feet

Compare to 350 knots at 20,000 feet:
- 350 knots = 590 ft/sec
- E_s = (590)² / (2*32.2) + 20,000
- E_s = 5,410 + 20,000 = 25,410 feet

Second aircraft has higher specific energy (altitude advantage wins here)
```

**Energy Rate of Change:**
```
dE/dt = Rate of energy change

Positive dE/dt = Gaining energy
- Accelerating
- Descending
- Both together

Negative dE/dt = Losing energy
- Decelerating
- Climbing
- Both together
- Hard turn in level flight

Monitoring:
- Continuous monitoring critical
- Airspeed and altitude gauges primary reference
- Attitude indicator secondary reference
- Energy state determines maneuver options
```

---

### SUSTAINED VS. INSTANTANEOUS TURN CAPABILITY

**Instantaneous Turn Rate (ITR):**
```
Definition: Maximum turn rate achievable for brief period

Characteristics:
- Peak turn rate available (typically 24-28°/sec)
- Can be held for 10-20 seconds maximum
- Results in rapid airspeed loss
- Aircraft becomes vulnerable if maneuver must continue

Tactical use:
- Rapid repositioning against closing threat
- Aggressive counter-maneuver initiation
- Quick evasive turn against missile

Limits:
- Speed decreases 100+ knots/sec
- Altitude loss significant
- Unsustainable energy

Calculation:
```
Max turn rate (°/sec) = 3437.75 * tan(bank angle) * g / V

Where:
- bank angle = roll angle (degrees)
- g = gravity (32.2 ft/sec²)
- V = velocity (ft/sec)

Example:
- 450 knots (759 ft/sec), 85° bank
- Turn rate = 3437.75 * tan(85°) * 32.2 / 759
- Turn rate ≈ 24.5°/sec
```

**Sustained Turn Rate (STR):**
```
Definition: Turn rate maintainable without losing altitude

Characteristics:
- Continuous turn capability (hours if fuel permits)
- Turn rate typically 60-70% of ITR
- Speed relatively stable (small decrease acceptable)
- Altitude maintained within ±500 feet
- Energy state stable

Tactical use:
- Nose-to-tail pursuit
- Extended engagement
- Maneuvering space maintenance
- Altitude buffer preservation

Optimal speed:
- Each aircraft has optimal speed for STR
- Typically 250-350 knots (slow fighters)
- Higher speeds reduce available G for turns

Calculation:
```
Sustained G available = (n - 1)

Where n = specific excess power

SPE (Specific Power Excess) = (T - D) / W

Where:
- T = Thrust (pounds)
- D = Drag (pounds)
- W = Weight (pounds)

Example:
- Fighter at 300 knots
- Thrust 25,000 lbs, Drag 5,000 lbs, Weight 35,000 lbs
- SPE = (25000 - 5000) / 35000 = 0.571
- n = 1 + 0.571 = 1.571
- Available G = 1.571 - 1 = 0.571G
- Sustained turn rate at this speed approximately 8-10°/sec
```

---

### CLIMB PERFORMANCE

**Rate of Climb (ROC):**
```
Definition: Vertical speed achievable; how fast altitude can be gained

Measurement: Feet per minute (typically 1,000-6,000 ft/min for fighters)

Characteristics:
- Speed-dependent (decreases with speed increase)
- Power-dependent (full power typically used)
- Decreases with altitude (thinner air)

Tactical significance:
- Directly relates to Yo-Yo maneuver capability
- Altitude advantage build rate
- Energy recovery rate during climb

Example:
- Maximum ROC at 15,000 feet: 4,000 ft/min (67 ft/sec)
- Climbing 2,000 feet takes: 2,000 / 67 = 30 seconds

Calculation (simplified):
```
ROC (ft/min) = 33,000 * (T - D) / W

Where:
- T = Thrust
- D = Drag
- W = Weight
```

**Best Rate of Climb Speed:**
```
Each aircraft has specific speed for maximum ROC
- Example: 350 knots for sustained climb
- Slower or faster reduces ROC
- Varies by aircraft type
- Relates to Yo-Yo maneuver timing
```

---

### ACCELERATION PERFORMANCE

**Acceleration in Level Flight:**
```
Definition: How quickly speed can be increased at constant altitude

Tactical relevance:
- Critical for energy recovery after climbing
- Determines extend-away capability
- Influences engagement reset timing

Measurement: Knots per second (typical 2-5 knots/sec)

Acceleration profile:
- Initially high (low speed = high power available for acceleration)
- Decreases with speed (drag increases)
- Becomes minimal near maximum speed

Calculation:
```
Acceleration (ft/sec²) = g * (T - D) / W

Where:
- T = Thrust (speed-dependent)
- D = Drag (speed-dependent)
- W = Weight
```

---

### DIVE PERFORMANCE

**Dive Angle and Speed Recovery:**
```
Definition: How rapidly speed can be regained through descent

Tactical application:
- Low Yo-Yo primary mechanism
- Speed recovery after slow engagement
- Energy replenishment maneuver

Rate of speed gain:
- Steeper dive angle = faster speed gain
- 30° dive typical (not vertical)
- Speed gain rate 100-150 knots per 30 seconds typical

Calculation:
```
Dive speed gain = acceleration from:
1. Gravity component (down-slope of dive)
2. Engine thrust (if power applied)
```

---

## TACTICAL DECISION FRAMEWORK

### PRE-ENGAGEMENT DECISION TREE

```
START: Contact Detected

STEP 1: THREAT ASSESSMENT
├─ What is threat type? (Aircraft, Missile, Vehicle)
├─ What is threat distance? (km)
├─ What is threat heading? (degrees)
├─ What is threat altitude? (feet)
└─ Can threat reach me? (Yes/No)

STEP 2: CAPABILITY ASSESSMENT
├─ Do I have altitude advantage? (Yes/No)
├─ Do I have speed advantage? (Yes/No)
├─ Do I have range advantage for weapons? (Yes/No)
├─ Do I have fuel for sustained engagement? (Yes/No)
└─ What weapons do I have? (Guns/Missiles/None)

STEP 3: AIRCRAFT MATCH
├─ Is threat aircraft similar type? (Yes/No)
├─ Is threat turn rate similar? (Yes/No)
├─ Is threat speed similar? (Yes/No)
└─ What is threat likely tactic? (Aggressive/Evasive/Unknown)

STEP 4: INITIAL DECISION
├─ ENGAGE? (if advantage clear)
├─ EVADE? (if disadvantage clear)
├─ MANEUVER FOR POSITION? (if matched)
└─ REQUEST SUPPORT? (if heavily disadvantaged)
```

---

### ENGAGEMENT PHASE DECISION TREE

```
PHASE: MERGE (Aircraft within 10 km)

ASSESSMENT:
├─ Current energy state?
│  ├─ Superior → ANGLES TACTICS
│  ├─ Matched → ASSESS OPPONENT
│  └─ Inferior → ENERGY TACTICS
│
├─ Relative position?
│  ├─ Behind opponent → PURSUE (Nose-to-tail or aggressive)
│  ├─ Ahead of opponent → TURN INTO opponent
│  ├─ Beside opponent → HIGH YO-YO or BREAK
│  └─ Head-on approach → NOSE-TO-NOSE TURN or BREAK
│
├─ Weapon employment ready?
│  ├─ Missiles ready (rear-quarter) → POSITION FOR LAUNCH
│  ├─ All-aspect missile → AGGRESSIVE ANGLES
│  ├─ Guns only → CLOSE TO 1 KM; GET BEHIND
│  └─ No weapons → EVADE/EXTEND
│
└─ Altitude buffer safe?
   ├─ > 5000 ft → AGGRESSIVE MANEUVERS AVAILABLE
   ├─ 2000-5000 ft → MANEUVER BUT MONITOR
   └─ < 2000 ft → LIMIT AGGRESSIVE MANEUVERS; PREPARE TO EXTEND UPWARD
```

---

### TACTICAL TRANSITION DECISION

```
TRIGGER: Engagement in progress; decision point arrives

ASSESSMENT:
├─ How long in current engagement? (minutes)
├─ Position advantage achieved? (Yes/No)
├─ Altitude buffer status? (Good/Marginal/Critical)
├─ Fuel state? (Good/Adequate/Low)
├─ Opponent's apparent skill level? (High/Medium/Low)
└─ Can I win from current position? (Yes/No/Maybe)

IF (Can win current maneuver) THEN:
│  Continue to conclusion
│  └─ Press advantage; achieve kill
│
ELSE IF (Matched opponent) AND (Altitude buffer > 2000 ft) THEN:
│  Transition between ANGLES and ENERGY tactics
│  └─ Monitor for advantage appearance
│
ELSE IF (Losing position) THEN:
│  ASSESS THREE OPTIONS:
│  ├─ Option A: Continue but switch tactics
│  │  └─ Transition to defensive maneuvering
│  ├─ Option B: Break away and reset
│  │  └─ Execute escape maneuver; recover altitude/fuel
│  └─ Option C: Surrender if no escape possible
│     └─ Eject if ground unavoidable
│
ELSE IF (Altitude critical < 1500 ft AGL) THEN:
│  IMMEDIATE ACTION: Recover altitude
│  └─ Break maneuver; climb; reduce G-loading
│
ELSE IF (Fuel state critical) THEN:
│  DECISION: Continue fight or extend?
│  └─ If fuel < 10 min: Extend away; prepare to exit engagement area

END IF
```

---

### POST-ENGAGEMENT DECISION

```
TRIGGER: Engagement concluded (kill, escape, or standoff reached)

ASSESSMENT:
├─ Did I win? (Yes/No)
├─ Is threat still active? (Yes/No)
├─ Can I re-engage? (Yes/No)
├─ What is my energy state? (Good/Fair/Critical)
├─ What is my fuel state? (Good/Adequate/Low)
└─ Are there other threats? (Yes/No)

IF (I won engagement) THEN:
│  ├─ Assess remaining threats
│  ├─ Recover altitude for energy
│  └─ Prepare for next engagement or RTB (return to base)
│
ELSE IF (I escaped engagement) AND (Can re-engage) THEN:
│  ├─ Evaluate re-engagement probability
│  ├─ Reset to higher altitude for advantage
│  ├─ Approach from new angle
│  └─ Attempt second engagement
│
ELSE IF (Standoff reached) THEN:
│  ├─ Maintain current position
│  ├─ Monitor opponent
│  └─ Wait for position advantage or support arrival
│
ELSE IF (Multiple threats present) THEN:
│  ├─ Evaluate threat priority
│  ├─ Engage next threat or extend away
│  └─ Request support if overpowered
│
ELSE (Disengagement required) THEN:
│  ├─ Execute extend maneuver
│  ├─ Gain separation and altitude
│  └─ Plan exit from engagement area

END IF
```

---

## IMPLEMENTATION CHECKLIST

### MANEUVER EXECUTION VERIFICATION

**Before executing any maneuver, verify:**

```
□ Altitude buffer sufficient (>1500 ft AGL for recovery)
□ Speed within acceptable range for maneuver (250+ knots min)
□ G-loading capability available (aircraft responsive)
□ Opponent/threat position known (radar or visual)
□ Turn radius calculated/estimated
□ Closure rate assessed
□ Energy state understood
□ Fuel state adequate
□ Weapons status assessed
□ Backup plan prepared
```

### ENERGY STATE MONITORING

```
CONTINUOUS DURING ENGAGEMENT:
□ Airspeed gauge monitored (every 5 seconds)
□ Altitude indicator monitored (every 5 seconds)
□ Attitude indicator showing pitch/bank (continuous)
□ Turn rate assessed visually or numerically
□ G-meter observed for G-loading
□ Fuel gauge monitored (every 30 seconds)
□ Oxygen level checked (if applicable)
```

### TACTICAL DECISION POINTS

```
EVERY 10 SECONDS in engagement:
□ Relative position assessed (6 o'clock, flank, nose, etc.)
□ Opponent's apparent tactic recognized
□ Energy advantage/disadvantage calculated
□ Next maneuver planning begun

EVERY 30 SECONDS in engagement:
□ Overall engagement status assessed
□ Altitude buffer evaluated for safety
□ Fuel state adequacy verified
□ Tactical transition decision made
□ Outcome prediction (win/loss/escape)
```

### SAFETY LIMITS

```
MANDATORY ABORT TRIGGERS:
□ Altitude drops below 500 ft AGL → Recover altitude immediately
□ Airspeed drops below 200 knots → Reduce G; level flight
□ Fuel state reaches 5 minutes → Execute escape/return
□ Spatial disorientation detected → Return to level flight immediately
□ Control authority loss noted → Recover; assess damage
□ G-loading exceeds aircraft limit → Reduce G immediately
□ Opponent generates 2+ km separation → Accept disengagement
□ Multiple superior threats detected → Escape if possible
```

---

## APPENDIX: QUICK REFERENCE MANEUVER SELECTOR

| Tactical Situation | Maneuver | G-Loading | Duration | Altitude Loss | Speed Change |
|---|---|---|---|---|---|
| High-speed closure from 6 | HIGH YO-YO | 7-8G | 6-8 sec | +2000-3000 ft | -100 to -150 kt |
| Slow closure from 6 | LOW YO-YO | 2-4G | 5-7 sec | -1500-2000 ft | +100 to +150 kt |
| Head-on approach | NOSE-TO-NOSE TURN | 8-9G | 5-7 sec | -500-1500 ft | -50-100 kt |
| Opponent to your side | LAG DISPLACEMENT | 3-4G | 2-3 sec | ~0 ft | ~0 kt |
| Behind opponent, matched turn | NOSE-TO-TAIL TURN | 6-7G | Sustained | -100-300 ft | ~0 kt |
| Flat turning fight developing | FLAT SCISSORS | 8-9G | Varies | -500-1000 ft per cycle | -100-200 kt |
| Significant speed disadvantage | VERTICAL SCISSORS | 5-6G climb | 8-12 sec | +3000-4000 ft | -80-120 kt |
| Breaking from merge | THE BREAK | 4-6G | 2-5 sec | -500-1500 ft | ~0 kt |
| Missile launch warning | BREAK + CLIMB | 6-8G | 5-10 sec | Variable | -50 kt |
| Formation defense (2 A/C) | WEAVE | 4-5G | Continuous | ~0 ft | ~0 kt |

---

**Document Purpose:** AI Fighter Behavior Tree Model Training Guide  
**Last Updated:** 2026-07-09  
**Target Application:** AIP_LIB Combat Simulation  
**Confidence Level:** High (based on Shaw's Fighter Combat and 4th Gen analysis)
