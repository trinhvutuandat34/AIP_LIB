"""Round-robin league: every candidate config against every opponent archetype.

WHY THIS EXISTS. Every configuration decision in this project has been taken against ONE
opponent at a time -- the cutoff binary, or a mirror of ourselves -- and that has misled us
twice. F37 rejected the wide envelope on the peer rig while the cutoff column liked it; F48
adopted hybrid_gated's ranking from a cutoff run that F54 then voided entirely. A config tuned
against a single benchmark is tuned against that benchmark's quirks.

WHAT IT MEASURES -- REVISED 2026-09-04 for the 본선 format (COMPETITION_PLAN.md F61).

Damage differential is still the right WITHIN-GAME predictor: the competition adjudicates a
timeout on `dealt - taken` (COMPETITION_RULES.md Sec 5), and it stays the per-column metric.
But it is no longer the ranking key, for two reasons the finals format made concrete:

  * **Group advancement is scored in POINTS, not damage** -- 승 3 / 무 1 / 패 0 over a BO3
    round robin, top 2 of 4 advance. A config that wins narrowly more often beats one that
    wins hugely less often, and differential cannot see that distinction.
  * **We can ship only ONE model** (F61), which plays every opponent. So the ranking is over
    a distribution we cannot choose, with a floor under the worst column -- not a peak.

So the primary key is **expected BO3 match points, averaged across the roster**, computed from
each pair's per-game W/D/L rates; the minimax tiebreak survives as **worst-case** expected
points; and **draw rate is an explicit third key**, because draws cost 세트득실차 (the third
standings key) and, in the knockout, two of them hand the opponent the option to switch to
their 헤드온 모델.

WHY DRAWS ARE DECOMPOSED. "Draw" was one number hiding three unrelated failures, and they need
different fixes. Measured on the F60 champion at `match_base`, essentially every draw is
SCORELESS -- zero damage in both directions -- but for two different reasons:

  * vs `sniper`/`mirror`/`bt_only`: we hold ATA <= 2 deg for LONGER than in our wins
    (median 5,885 steps ~ 98 s vs 3,534 in wins) and still score nothing, with a closest
    approach of 615 m against 143 m in the wins. That is a **closure** failure -- nose on,
    never converted.
  * vs `cutoff`/`aggressor`: min-ATA medians of 91 deg and 23 deg, zero steps under 2 deg.
    That is a **pointing** failure -- we never got the nose there at all.

`scoreless_nose_on` vs `scoreless_off_angle` separates them. The per-episode CSV cannot say
whether the nose-on time and the closest approach coincide, so it cannot settle whether the
first bucket is an angle/range overlap problem or a WEZ-accounting subtlety -- that needs
per-step logs. What it CAN do is stop the two being averaged together.

WHAT IT REUSES. Nothing here is new machinery:
  * parallel dispatch + failed-arm relaunch  -- the pattern from sweep_vs_cutoff.py
  * per-side controller config                -- eval_v5_vs_bt.py's --{side}-vptrack-* flags
  * scoring on the competition's own scale    -- summarize_h2h.py / summarize_cutoff.py

    python scripts/league.py --episodes 50 --jobs 6
    python scripts/league.py --summarize

CAVEAT ON THE ARCHETYPES. `sniper` is a GoGoSSung ANALOGUE built from broadcast footage of five
of its wins, not a replica -- see OPPONENTS_ANALYSIS.md. A row reading "beat sniper 60%" must
never be read as "beat GoGoSSung 60%". As of 2026-09-08, `sniper` is ALSO the low-confidence
analogue for HAnnamAir (3-1 sample, guaranteed A조 opponent) and `aggressor` is ALSO the
low-confidence analogue for Fight's on! (4-1 sample, guaranteed A조 opponent) -- two different
real teams now sit behind each of those two rows. The caveat applies doubly: "beat sniper 60%"
is not evidence about GoGoSSung OR HAnnamAir specifically, same for aggressor/Fight's on!.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_PY = sys.executable
# Output root. Overridable via DOGFIGHT_LEAGUE_OUT_DIR (2026-09-05) -- default unchanged, so
# every existing command writes exactly where it always did.
#
# WHY THIS EXISTS. The head-on separation sweep needs one league run PER separation value, but
# separation is NOT part of the CSV filename (_csv_path keys on scenario/candidate/archetype
# only) and it is NOT a league axis -- it reaches the child only as DOGFIGHT_HEADON_SEPARATION_M
# in the environment. Without a per-value output root, run 2 of the sweep would see run 1's CSVs
# sitting at the same paths with the same schema, count their rows as progress, and APPEND a
# different geometry's episodes into them -- silently averaging two separations into one number.
# That is the exact failure _RESUME_SCHEMA_COLUMNS was added to prevent for a different cause,
# and the schema guard cannot catch it because the schema is identical. Keep them in separate
# directories instead. See scripts/sweep_headon_separation.py.
_OUT = Path(os.environ.get("DOGFIGHT_LEAGUE_OUT_DIR") or (_ROOT / "artifacts" / "eval"))

# ---- Randomised start conditions -- ORGANIZER-CONFIRMED 2026-09-11 --------------------
# The band is no longer a proxy. The organizers stated it directly: the 2000/2500/3000 ft
# settable in the viewer is the DISTANCE BETWEEN AIRCRAFT at engagement start, and initial
# speed and altitude are drawn at random every round --
#
#     초기 속력 : 200~300 m/s,  초기 고도 : 2000ft ~ 30000ft
#
# 2,000 ft = 609.6 m and 30,000 ft = 9,144.0 m. The separations (609.6 / 762.0 / 914.4 m in
# student/match_scenario_wrapper.py) are confirmed correct by the same message.
#
# WHAT THIS INVALIDATES. The previous proxy was "1000,7700" / "150,280" (F61 matrix,
# 2026-09-04), and EVERY CSV in artifacts/ predating 2026-09-11 was produced under it. Those
# runs are not comparable with anything measured after this line changed:
#   - ~37% of the real spawn space was never sampled: below 1,000 m (4.6% of the altitude
#     band) and 7,700-9,144 m (16.9%), plus 280-300 m/s (20% of the speed band).
#   - ~38% of the old speed draws (150-200 m/s) sit BELOW the real minimum and sampled a
#     regime that never occurs.
#
# THE LOW END IS THE ONE THAT BITES. The old floor of 1,000 m was chosen to sit just above
# Gate 0's 914 m trigger and to avoid gifting spawn-deaths. The real floor is 609.6 m, which
# is BELOW SHIP_HARD_DECK_M (1,000 m) -- and below the deck _tracking_stick returns None and
# hands the aircraft to the BT (student/controller_providers.py:801). So ~4.6% of real rounds
# begin with the tuned controller switched off through the merge, a case the old band made
# structurally impossible to observe. Model 2 is unaffected (hard_deck_m = 0.0).
DEFAULT_ALTITUDE_RANGE_M = "609.6,9144"
DEFAULT_SPEED_RANGE_MPS = "200,300"

# ---- Candidates: what we might ship. Ownship side. ------------------------------------
# Flags mirror the SHIP_* constants in student/controller_providers.py; `ship` is the current
# adopted config (F59) and is the control every other row is read against.
#
# STALE AS OF 2026-09-12: the SHIP_* constants moved ahead of this row. `adaptive300_deckttc`
# below (standoff 300, adaptive-range on, deck-ttc 5) is now what SHIP_STANDOFF_M /
# SHIP_ADAPTIVE_RANGE / SHIP_DECK_TTC_S actually build, confirmed on two independent N=100
# seeds vs cutoff (pooled win 53.5% vs 45.5%, n=200 each) -- see the comment there. Left
# UNCHANGED here rather than edited, because `aggressor` below is asserted byte-identical to
# this exact flag set (is_self_play()'s minimax-floor exclusion depends on that), and reworking
# both together this close to the deadline is not worth the risk for a measurement-harness
# label. Read this row as "Model 1, pre-2026-09-12", not as the current ship default.
CANDIDATES: dict[str, list[str]] = {
    "ship_6000_120_deck": ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000"],
    "alt_8000_90_deck":   ["--ownship-vptrack-range-m", "8000", "--ownship-vptrack-los-deg", "90",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000"],
    "prev_6000_90":       ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90",
                           "--ownship-vptrack-throttle", "1"],
    # MODEL 2 CANDIDATE, added 2026-09-05 for the head-on sweep only (F74).
    #
    # `prev_6000_90` + the hard deck. F59 tested exactly this combination in match_base and
    # rejected it -- the SHIP_HARD_DECK_M comment records that the deck "applied to 6000/90
    # (which never crashed) it measured slightly WORSE". That reasoning does NOT transfer to
    # head-on geometry, because its premise is false here: at 3,048 m nose-to-nose,
    # `prev_6000_90` self-crashes ("ownship altitude below min") 11/300 overall and **5/60
    # against the cutoff**, its floor-defining column, versus 1/60 for the shipped config.
    # A guard that costs a little when it never fires may pay when it fires 8% of the time.
    # Measure it rather than inheriting a verdict from a different scenario.
    "m2_6000_90_deck":    ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "90",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000"],

    # ---- RANGE IS SATURATED. DO NOT SWEEP IT AGAIN. (measured 2026-09-08) ----------------
    #
    # `wide_8000_120_deck` and `wide_12000_120_deck` were run against the cutoff and produced
    # rows BYTE-IDENTICAL to `ship_6000_120_deck` -- not similar, identical, episode for episode.
    # `_tracking_stick` defers to the BT when `rng > engage_range_m`, and these fights spawn at
    # 610-880 m and close to a median of 20 m; they never approach 6 km. So 6000, 8000 and 12000
    # are the SAME SETTING and the shipped config already sits past the point where the range
    # axis does anything.
    #
    # CUTOFF_MODEL_REFERENCE.md Sec 9's 2500 -> 4000 -> 6000 progression (66.7% -> 100%) is real,
    # but it had already flattened by 6000 -- reading it as "range is the axis with headroom" and
    # sweeping upward was a wasted campaign. The candidates are kept here, commented out, so the
    # next person does not repeat it.
    #
    #   "wide_8000_120_deck":  [... "--ownship-vptrack-range-m", "8000"  ...]   # == ship
    #   "wide_12000_120_deck": [... "--ownship-vptrack-range-m", "12000" ...]   # == ship
    #
    # THE BINDING GATE IS LOS. `alt_8000_90_deck` differs from the three above only in los_deg
    # (90 vs 120) and was the one row that moved: 29.4% vs 70.6% against the cutoff at N=17. So
    # 120 is much better than 90, and the unexplored band is ABOVE 120 -- but note `los_deg = 180`
    # (always engage) was already measured and COLLAPSED both sides (40->15%, 20->5%, F67 note in
    # Controller_CY.cpp). 140 is one modest step, not a leap.
    "los140_deck":        ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "140",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000"],

    # ---- ROLL TAPER: the knob built for the measured defect, never once switched on -----------
    #
    # ROLL_TAPER_DEG (student/controller_providers.py) addresses a measured authority INVERSION:
    # `phi = atan2(az, el)` carries direction but not magnitude, so as the solution converges both
    # az and el vanish and atan2 returns an essentially arbitrary angle. Measured over 20,914
    # in-envelope steps, mean |roll| is 0.481 at 0.0-0.5 deg of error but only 0.045 at 15-60 deg
    # -- roll authority is largest exactly when the error is smallest. Inside the scoring window
    # (152.4-914.4 m AND LOS <= 1.0 deg): 375 steps, mean |roll| 0.561, 18.9% at near-full scale.
    # The aircraft throws the gun line around at the moment it must hold the pipper.
    #
    # That is the direct candidate mechanism for this project's signature failure -- excellent
    # minimum ATA (0.011 deg median in wins) with poor DWELL -- and for the fact that 23 of 44
    # cutoff losses deal ZERO damage despite reaching 71 m and 0.85 deg, against an opponent with
    # no defensive layer at all. The knob defaults to 0.0 = OFF, which is what every register
    # measurement was taken at.
    "taper5_deck":        ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-roll-taper", "5"],
    "taper15_deck":       ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-roll-taper", "15"],

    # ---- THE LAST THREE NEVER-MEASURED KNOBS THAT ALREADY HAVE CLI FLAGS (2026-09-08) --------
    #
    # After F80 closed range, LOS and roll-taper, these are what is left that can be swept with
    # no new plumbing. All three default OFF, which is what every register number was measured
    # at, so each is a single-knob delta from the shipped config and attributable on its own.
    #
    #   corner  -- hold ~440 KTAS for peak turn rate. RATIONALE CORRECTED 2026-09-09: the spawn
    #              is 389 kt, but the aircraft does not stay there. corner_speed_probe.py on the
    #              current DLL reports mean TAS **506.4 kt** (min episode mean 374.2), i.e. we
    #              fight ~66 kt ABOVE the 430-450 band, not below it. So this knob DECELERATES,
    #              and being above corner widens the turn radius -- a candidate mechanism for the
    #              measured overshoot (median ep_min_distance 19.9 m against a 152.4 m
    #              zero-damage floor; 80/100 episodes go inside that floor vs the cutoff).
    #              MEASURED 2026-09-09 AND REJECTED, N=40/cell vs the N=100 shipped control.
    #              WEZ-entry falls on all three archetypes: cutoff 60.0 -> 47.5 (z=-1.35),
    #              aggressor 72.0 -> 65.0 (z=-0.82), sniper 91.0 -> 65.0 (z=-3.75). Damage
    #              differential vs cutoff -0.078 -> -0.191. The radius mechanism is REFUTED
    #              too: below-floor moved only 80.0% -> 82.5% vs the cutoff, and against
    #              `sniper` -- the archetype we do NOT overshoot into -- slowing made it WORSE
    #              (median min range 242 -> 102 m, below-floor 35% -> 55%). Speed is not what
    #              puts us at 20 m. The untested lever is the AIM POINT: see STANDOFF_M.
    #              Note student/controller_providers.py's own comment still cites 339.6 kt from
    #              2026-08-07; that predates the 6000/120 envelope, the deck and three rebuilds.
    #   defensive -- break off when losing the gun duel. NOTE its blind spot: _losing_gun_duel()
    #              requires 152.4 <= rng, and our median closest approach is 20 m, so it cannot
    #              fire in the geometry we actually fly -- range discipline is a prerequisite.
    #              Parked at F26-DEFENSIVE with the note
    #              "worth re-testing against an opponent that out-shoots us". We now HAVE that
    #              measurement: against `aggressor` we die 31 times to their 23, and against the
    #              cutoff damage taken (0.549) exceeds dealt (0.471). That is the condition the
    #              node was parked waiting for.
    #   deckttc -- time-to-impact deck guard, built in F62 SO IT COULD BE MEASURED and then
    #              never measured. 5 s: F62's own worked example is 914 m at 236 m/s of sink =
    #              3.9 s, and an inverted recovery needs more than that. We still lose 5/100 to
    #              our own floor against the cutoff WITH the altitude deck already on, which is
    #              exactly the failure an altitude threshold cannot express.
    "corner_on":          ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-corner", "1"],
    "defensive_on":       ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-defensive", "1"],
    "deckttc_on":         ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-deck-ttc", "5"],

    # ---- AIM-POINT STANDOFF (2026-09-09) -- the first lever aimed at the overshoot ------------
    #
    # THE DEFECT: median ep_min_distance 19.9 m against a 152.4 m zero-damage floor, with 80/100
    # episodes inside that floor vs the cutoff. We hold <=1 deg for a mean of 173.5 steps but
    # only 62.6 of them are inside the scoring band. The first gate trace says the same from the
    # tree's side: Gun_DistLt914 passes on 1,056 of 15,611 ticks, Gun_Track runs on 0.2%.
    #
    # WHY THIS AND NOT THE TWO EXISTING RANGE MECHANISMS: both are THROTTLE-only
    # (Task_GunTrack.cpp's GUNTRACK_TARGET_RANGE_M and TARGET_RANGE_M, the latter already ON in
    # the shipped config) and throttle cannot arrest a merge. STANDOFF_M is the first thing that
    # biases the AIM POINT, which is what decides whether the flight path intersects the target.
    # corner_on above already ruled out the energy explanation, so this is the remaining one.
    #
    # 220 m is where the damage coefficient peaks and what both existing mechanisms target, so
    # all three would finally agree. 400 m brackets it from the long side.
    "standoff220_deck":   ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-standoff-m", "220"],
    "standoff400_deck":   ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-standoff-m", "400"],

    # GATED STANDOFF, 2026-09-09. The standoff knob was rewritten after the phase analysis: it
    # now stands down whenever a Phase-1 shot is already in hand (range 500-3000 ft AND LOS
    # < 1 deg). Rationale: Phase 1 is 92.6% of all expected damage, its angle is a BINARY gate
    # while range is only a smooth multiplier, so nudging the aim point off-target to gain range
    # can score zero instead of 1.0. The ungated version lost its N=100 confirmation (bo3 1.53
    # vs 1.60) after looking strong at N=40, and this is the mechanism that best explains it.
    #
    # 200 m = 656 ft sits nearer the damage peak than 220 m did: the Phase-1 curve is
    # 1.0 * (3000 - r_ft)/2500, so 656 ft pays 0.937 against 722 ft's 0.911, and the floor at
    # 500 ft pays 1.00 but is the edge of a zero-damage cliff. 200 m keeps a margin above it.
    "standoff200_gated":  ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-standoff-m", "200"],

    # TIME-PHASED ACCEPTANCE. Same gated standoff, but the window it stands down for widens with
    # the match clock exactly as the server's scoring cone does (Sec 6.2: LOS 1/2/3 deg and
    # 3000/3500/4000 ft at t=0/100/150 s). Early: hold ~200 m and only break off for a Phase-1
    # solution. Late: accept the wider, longer shots that now actually score rather than
    # manoeuvring away from them. 43% of cutoff episodes end on the clock and a timeout is
    # decided purely on damage differential, so 0.1-coefficient hits that currently score zero
    # can flip one. Acceptance only ever WIDENS, so a 1.0 solution is never displaced.
    "standoff200_phased": ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-standoff-m", "200",
                           "--ownship-vptrack-phased-window", "1"],

    # ADAPTIVE RANGE. Range multiplies the angular differential rather than creating it, so the
    # right separation depends on who is out-angling whom -- measured dealt/taken is 0.86 vs the
    # cutoff, 0.96 vs aggressor, 1.42 vs mirror, i.e. no single fixed standoff can be right for
    # all three. Extend while they hold the tighter angle, close when we do. 300 m rather than
    # 200 m because our measured range-holding scatter is large (median closest approach 65 ft,
    # 80% of episodes inside the 500 ft dead zone), and the damage-optimal setpoint moves OUTWARD
    # as scatter grows: ~620 ft at +/-50 ft of control, ~1040 ft at +/-400 ft.
    "adaptive300":        ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-standoff-m", "300",
                           "--ownship-vptrack-adaptive-range", "1"],
    # The same policy stacked with the deck guard, which is the only arm so far to move the
    # dominant failure mode (nopoint 35% -> 20%, WEZ entry 72.5% -> 85%).
    "adaptive300_deckttc":["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-standoff-m", "300",
                           "--ownship-vptrack-adaptive-range", "1",
                           "--ownship-vptrack-deck-ttc", "5"],

    # STACKED. The two knobs touch different code paths (aim point in the control law vs the
    # hand-back guard), so if both are individually non-negative this is the natural candidate.
    # They can still interact through the handover: deck_ttc returns None and gives the stick to
    # the BT, and the standoff only acts while the control law HAS the stick.
    "standoff220_deckttc": ["--ownship-vptrack-range-m", "6000", "--ownship-vptrack-los-deg", "120",
                           "--ownship-vptrack-throttle", "1", "--ownship-vptrack-hard-deck", "1000",
                           "--ownship-vptrack-standoff-m", "220", "--ownship-vptrack-deck-ttc", "5"],
}

# ---- Archetypes: who we might face. Target side. --------------------------------------
# See OPPONENTS_ANALYSIS.md "Archetype roster" for what each one represents and why these five
# span the axis that actually decides our matches: willingness to trade damage.
ARCHETYPES: dict[str, list[str]] = {
    # Extend-and-clock. The real independent opponent; declines the re-merge and banks the clock.
    # NOTE: `cutoff` is NOT a valid --target-backend on eval_v5_vs_bt.py (choices are rl/bt/
    # vptrack/hybrid*/fixed/autopilot/loiter) -- it is injected by the eval_vs_cutoff.py wrapper.
    # launch() dispatches this archetype there instead; passing it through the normal path exits
    # rc=2 on argparse before a single episode runs.
    "cutoff":    ["--cutoff-action-repeat", "6"],
    # A peer at our level -- the previously shipped config.
    "mirror":    ["--target-backend", "vptrack",
                  "--target-vptrack-range-m", "6000", "--target-vptrack-los-deg", "90",
                  "--target-vptrack-throttle", "1"],
    # GoGoSSung ANALOGUE (low confidence -- see module docstring). Narrow envelope reproduces
    # "engages rarely, retains health"; nothing we have reproduces its salvo behaviour.
    # Also the HAnnamAir analogue as of 2026-09-08 (3-1 sample) -- reproduces HAnnamAir's
    # near-untouchable defense, not its 80-100s grind-to-kill offense. Two different real teams,
    # one row: neither result generalizes to the other.
    "sniper":    ["--target-backend", "vptrack",
                  "--target-vptrack-range-m", "2500", "--target-vptrack-los-deg", "45",
                  "--target-vptrack-throttle", "1"],
    # Forces decisive merges and trades freely. Deck guard on, or it just flies into the ground.
    # Also the Fight's on! analogue as of 2026-09-08 (4-1 sample, low confidence) -- reproduces
    # its commit-once-merged finishing behaviour, not its long scoreless opening patience.
    "aggressor": ["--target-backend", "vptrack",
                  "--target-vptrack-range-m", "6000", "--target-vptrack-los-deg", "120",
                  "--target-vptrack-throttle", "1", "--target-vptrack-hard-deck", "1000"],
    # Rule-based floor. Never shoots (HANDOFF.md), so it is a sanity check, not a real opponent.
    "bt_only":   ["--target-backend", "bt"],

    # THE PHASE-EXPLOITER (2026-09-09). The threat model we could not otherwise test: an opponent
    # that widens what it accepts as a shot with the match clock, exactly as the server's scoring
    # cone widens (Sec 6.2), and so banks cheap Phase 2/3 damage late that a Phase-1-only pilot
    # declines. If such an opponent beats the shipped config, adopting the same behaviour is
    # justified; if it does not, the phased window is not worth shipping.
    #
    # NOTE what the scouting actually supports. OPPONENTS_ANALYSIS.md records that an earlier
    # read of this project credited a real team with a "Battle Phase gate" that turned out to be
    # the competition's own widening -- every team gets those phases. Teams ARE observed landing
    # late Phase-3 hits (MotherGoose: 3 hits at t~190 s), but no opponent binary examined so far
    # contains a clock-reading gate; the organizers' own cutoff has no RunningTime symbol at all.
    # So this archetype is a HYPOTHESIS about an opponent, not a replica of a measured one.
    "phased":    ["--target-backend", "vptrack",
                  "--target-vptrack-range-m", "6000", "--target-vptrack-los-deg", "120",
                  "--target-vptrack-throttle", "1", "--target-vptrack-hard-deck", "1000",
                  "--target-vptrack-standoff-m", "200", "--target-vptrack-phased-window", "1"],
}


def _flag_map(flags: list[str], side: str) -> dict:
    """The vptrack settings in a flag list, keyed by knob name and side-agnostic."""
    out: dict[str, str] = {}
    it = iter(flags)
    for a in it:
        if not a.startswith("--"):
            continue
        key = a.replace(f"--{side}-vptrack-", "")
        if key == a:            # not a vptrack flag (e.g. --target-backend)
            next(it, None)
            continue
        out[key] = next(it, "")
    return out


def _is_selfplay(cand: str, arch: str) -> bool:
    """True when this archetype is the candidate's OWN configuration on the target side.

    Not a hypothetical: `aggressor` is identical to `ship_6000_120_deck`, and `mirror` is
    identical to `prev_6000_90`. Such a column is a symmetry check, not an opponent -- see the
    comment at the ranking key for why it must not define the minimax floor.
    """
    if cand not in CANDIDATES or arch not in ARCHETYPES:
        return False
    if "--target-backend" in ARCHETYPES[arch] and "vptrack" not in ARCHETYPES[arch]:
        return False            # bt_only / cutoff are not our controller at all
    return _flag_map(CANDIDATES[cand], "ownship") == _flag_map(ARCHETYPES[arch], "target")


def _csv_path(cand: str, arch: str, scenario: str) -> Path:
    return _OUT / f"league_{scenario}__{cand}__vs__{arch}.csv"


# Columns that any CSV counted toward a chunked resume MUST have, or its rows are from a schema
# the current code cannot interpret as "the same kind of episode". Added 2026-09-04 after F65:
# ten of the fifteen real matrix files were still F60's pre-randomisation N=50 data (no
# initial_altitude_m/speed/side columns at all) when the chunked resume was about to run against
# them -- naive row-counting would have banked 50 FIXED-SPAWN episodes as progress and then
# appended 100 RANDOMISED-SPAWN ones after them in the same file, contaminating the one thing
# this matrix exists to measure. Update this set whenever CSV_FIELDS gains a column the resume
# logic depends on being present in every counted row.
# RESUME SCHEMA GUARD -- WIDENED 2026-09-08. This used to be a hand-listed set of three column
# names, and that was not enough. `eval_v5_vs_bt.py` writes its header ONLY on a fresh file
# (`--append` suppresses it), so a resume appends rows positionally against whatever header is
# already there. The three-name check passes any file that happens to contain those three names,
# no matter how many other columns differ -- and it was passing right now: the 15 live
# `league_match_base__*.csv` are 28-column files from 2026-09-04, while CSV_FIELDS has since
# grown to 30 (`ep_bt_frac`, `ep_bt_steps`). One `--episodes 151` would have written 30 values
# under a 28-name header and shifted every column from `ep_wez_steps` rightward by two on the
# appended rows, silently: csv.DictReader drops the overflow into the None key and every reader
# here uses `.get(...) or 0`.
#
# So compare the WHOLE header against the writer's own CSV_FIELDS instead of a curated subset.
# The list is imported, not copied, so adding a column to eval_v5_vs_bt.py can never again leave
# this guard behind.
from eval_v5_vs_bt import CSV_FIELDS as _WRITER_FIELDS  # noqa: E402


def _episodes_done(path: Path) -> int:
    """How many episode rows a pair's CSV already has toward a CURRENT-SCHEMA resume.

    0 if the file does not exist, is empty, OR its header is not exactly the writer's current
    `CSV_FIELDS` -- the last case treats a stale-schema file as needing a fresh start rather than
    silently mixing its rows in as if they were the same kind of episode. `launch()` then omits
    `--append` when done_n is 0, so eval_v5_vs_bt.py naturally overwrites the stale file; nothing
    here deletes it, and nothing is lost if it was needed -- F60's own data lives on in
    `artifacts/eval/f60_baseline/` regardless.
    """
    if not path.exists():
        return 0
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return 0
            if list(reader.fieldnames) != list(_WRITER_FIELDS):
                missing = [c for c in _WRITER_FIELDS if c not in reader.fieldnames]
                extra = [c for c in reader.fieldnames if c not in _WRITER_FIELDS]
                print(f"[league] {path.name}: STALE SCHEMA (missing {missing}, extra {extra}) -- "
                      f"treating as 0 done, will be overwritten fresh", flush=True)
                return 0
            return sum(1 for _ in reader)
    except (OSError, csv.Error):
        return 0


def run(args: argparse.Namespace) -> None:
    _OUT.mkdir(parents=True, exist_ok=True)
    cands = args.candidates or list(CANDIDATES)
    archs = args.archetypes or list(ARCHETYPES)
    pairs = [(c, a) for c in cands for a in archs if c in CANDIDATES and a in ARCHETYPES]
    if args.skip_existing:
        pairs = [(c, a) for c, a in pairs
                 if not _csv_path(c, a, args.scenario_mode).exists()]

    # RESUMABLE CHUNKING (2026-09-04). Two attempts to run the full N=150 matrix as one
    # background command (~7.6 h) both died with the same external-kill signature
    # (rc=1073807364) at 20-41 min elapsed, with jobs=6, using the correct interpreter both
    # times -- see COMPETITION_PLAN.md F65. Rather than keep betting on one long command
    # surviving, each invocation of THIS SAME COMMAND now advances every pair by at most
    # `--chunk-episodes` toward the `--episodes` TARGET, reading how many rows each pair's CSV
    # already has to compute what remains. Re-run the identical command until it prints
    # "matrix already complete" -- each invocation is a bounded, safe unit of progress, and a
    # kill mid-invocation loses at most one chunk's worth of work, not the whole campaign.
    targets = {}
    for cand, arch in pairs:
        done_n = _episodes_done(_csv_path(cand, arch, args.scenario_mode))
        remaining = max(0, args.episodes - done_n)
        targets[(cand, arch)] = (done_n, min(remaining, args.chunk_episodes))
    pairs = [p for p in pairs if targets[p][1] > 0]

    if not pairs:
        print(f"[league] matrix already complete: every pair has >= {args.episodes} episodes "
              f"in scenario={args.scenario_mode}. Nothing to do.", flush=True)
        return

    total_done = sum(d for d, _ in targets.values())
    total_target = len(targets) * args.episodes
    print(f"[league] {len(pairs)}/{len(targets)} pairs need more episodes "
          f"({total_done}/{total_target} episodes banked so far), "
          f"scenario={args.scenario_mode}, chunk={args.chunk_episodes}, "
          f"target={args.episodes}, jobs={args.jobs}", flush=True)
    print(f"[league] start conditions: altitude={args.altitude_range or 'FIXED'} m, "
          f"speed={args.speed_range or 'FIXED'} m/s, separation swept per episode, "
          f"side drawn per episode", flush=True)

    queue = list(pairs)
    running: list[tuple[tuple[str, str], subprocess.Popen, object]] = []
    started: dict[tuple[str, str], float] = {}
    relaunch_count: dict[tuple[str, str], int] = {}
    done: list[tuple[str, str, int, float]] = []

    def launch(pair: tuple[str, str]) -> None:
        cand, arch = pair
        out = _csv_path(cand, arch, args.scenario_mode)
        done_n, this_chunk = targets[pair]
        # The cutoff opponent lives behind its own wrapper (see ARCHETYPES["cutoff"]).
        entry = "eval_vs_cutoff.py" if arch == "cutoff" else "eval_v5_vs_bt.py"
        cmd = [
            _PY, str(_HERE / entry),
            "--ownship-backend", "vptrack",
        ] + (["--target-backend", "cutoff"] if arch == "cutoff" else []) + [
            "--scenario-mode", args.scenario_mode,
            "--episodes", str(this_chunk),
            "--episode-offset", str(done_n),
            "--seed", str(args.seed),
            "--out-csv", str(out.relative_to(_ROOT)),
        ] + (["--append"] if done_n > 0 else []) + CANDIDATES[cand] + ARCHETYPES[arch]
        log = out.with_suffix(".log").open("w", encoding="utf-8")
        # The bands reach the child through the environment because match_scenario_wrapper reads
        # them at import time; each pair is its own process, so this is per-run configuration
        # rather than global state. Empty string = randomisation off, which is the default
        # everywhere else and keeps older runs reproducible.
        child_env = dict(os.environ)
        child_env["DOGFIGHT_MATCH_ALTITUDE_RANGE_M"] = args.altitude_range
        child_env["DOGFIGHT_MATCH_SPEED_RANGE_MPS"] = args.speed_range
        proc = subprocess.Popen(cmd, cwd=str(_ROOT), stdout=log, stderr=subprocess.STDOUT,
                                env=child_env)
        started[pair] = time.time()
        running.append((pair, proc, log))
        print(f"[league] start {cand} vs {arch}  "
              f"(episodes {done_n}..{done_n + this_chunk - 1} of {args.episodes} target)",
              flush=True)

    # Stagger cold starts (2026-09-04). A chunk pass died twice on `STATUS_DLL_INIT_FAILED`
    # (rc=3221225794, 0xC0000142 -- the Windows loader's own code for a DllMain that failed to
    # initialize), both times with a ZERO-BYTE log: the crash happened before Python printed
    # ANYTHING, i.e. at the OS loader, not in our code. Both failures landed inside a fresh
    # 6-way burst where every slot cold-starts and calls LoadLibrary on the same AIP_BASE.dll /
    # JSBSimAIPLib.dll at nearly the same instant, while every sibling in that same burst that
    # DIDN'T collide loaded fine -- consistent with loader/AV contention on simultaneous native
    # DLL loads, not a broken DLL. Spacing cold starts out reduces how often that many loads land
    # in the same instant; it does not touch anything already running.
    _LAUNCH_STAGGER_S = 2.0
    # Two retries (three attempts total), up from one: the immediate relaunch after the first
    # failure hit the IDENTICAL rc in 0.1 min, because the requeued pair re-entered the same
    # crowded polling tick its sibling had just failed in. More attempts, spread over the
    # existing 5s poll cadence, give the race more chances to land in a quiet moment.
    _MAX_RELAUNCHES = 2

    while queue or running:
        while queue and len(running) < args.jobs:
            launch(queue.pop(0))
            if queue and len(running) < args.jobs:
                time.sleep(_LAUNCH_STAGGER_S)
        time.sleep(5)
        for entry in list(running):
            pair, proc, log = entry
            if proc.poll() is None:
                continue
            running.remove(entry)
            log.close()
            el = time.time() - started[pair]
            # Relaunch (up to _MAX_RELAUNCHES times): a crashed arm otherwise vanishes from the
            # matrix with only a non-zero rc in a log tail (this is how env_r8000_l90 became a
            # 6-episode row).
            if proc.returncode != 0 and relaunch_count.get(pair, 0) < _MAX_RELAUNCHES:
                relaunch_count[pair] = relaunch_count.get(pair, 0) + 1
                print(f"[league] FAILED {pair[0]} vs {pair[1]} rc={proc.returncode} "
                      f"-- relaunching (attempt {relaunch_count[pair] + 1}/"
                      f"{_MAX_RELAUNCHES + 1})", flush=True)
                # Re-derive the chunk from the CSV rather than reusing the stale one: --append
                # means a crash partway through the child's OWN run can leave a partial chunk
                # already on disk (the writer flushes per episode -- see fh.flush() in the
                # episode loop), and relaunching with the ORIGINAL offset would duplicate those
                # rows instead of continuing past them.
                done_n = _episodes_done(_csv_path(pair[0], pair[1], args.scenario_mode))
                remaining = max(0, args.episodes - done_n)
                if remaining <= 0:
                    print(f"[league] {pair[0]} vs {pair[1]} reached target during the failed "
                          f"run despite rc={proc.returncode} -- not relaunching", flush=True)
                else:
                    targets[pair] = (done_n, min(remaining, args.chunk_episodes))
                    queue.append(pair)
                continue
            done.append((pair[0], pair[1], proc.returncode, el))
            print(f"[league] done  {pair[0]} vs {pair[1]} rc={proc.returncode} "
                  f"in {el/60:.1f} min", flush=True)

    print("\n[league] chunk pass finished")
    for c, a, rc, el in done:
        print(f"  {c:<22} vs {a:<10} rc={rc} {el/60:>6.1f} min")
    bad = [(c, a) for c, a, rc, _ in done if rc != 0]
    if bad:
        print(f"\n  !! {len(bad)} pair(s) still failing after one relaunch: {bad}")
        print("     Treat a non-zero rc as a real result to investigate, not noise.")
    still_short = sum(1 for pr in targets
                      if _episodes_done(_csv_path(pr[0], pr[1], args.scenario_mode)) < args.episodes)
    if still_short:
        print(f"\n[league] {still_short} pair(s) below target -- RE-RUN THE SAME COMMAND to "
              f"continue (each pair resumes from its own episode count, nothing repeats).")
    else:
        print(f"\n[league] every pair has reached {args.episodes} episodes.")


# Altitude-floor adjudication, imported rather than restated so league.py and
# summarize_cutoff.py cannot drift apart on what counts as a win (they already had -- see
# _load). summarize_cutoff.py's module docstring carries the full rationale and the caveat that
# a margin made of the opponent's self-crashes is not a margin we own.
sys.path.insert(0, str(_HERE))
from summarize_cutoff import _OWNSHIP_LOST, _TARGET_LOST  # noqa: E402

# A draw episode falls in exactly one of these, checked in this order. See the docstring for
# why the two scoreless buckets are separated rather than summed.
DRAW_KINDS = ("mutual_kill", "scoreless_nose_on", "scoreless_off_angle", "traded_even")

# Fraction of the episode spent inside 2 deg ATA above which a scoreless draw counts as
# "nose on". 10% is well clear of both observed populations -- the nose-on archetypes sit at
# 40-60% of the episode, the off-angle ones at exactly 0 -- so the classification is not
# sensitive to this number.
_NOSE_ON_FRAC = 0.10


def _classify_draw(r: dict) -> str:
    """Which kind of draw is this episode? Assumes the caller already found it to be a draw."""
    own = float(r.get("ownship_health") or 0)
    tgt = float(r.get("target_health") or 0)
    dealt = float(r.get("ep_damage_dealt") or 0)
    taken = float(r.get("ep_damage_taken") or 0)
    if own <= 1e-6 and tgt <= 1e-6:
        return "mutual_kill"
    if dealt <= 1e-9 and taken <= 1e-9:
        steps = float(r.get("steps") or 0)
        le2 = float(r.get("ep_steps_le2_deg_3d") or 0)
        frac = (le2 / steps) if steps > 0 else 0.0
        return "scoreless_nose_on" if frac >= _NOSE_ON_FRAC else "scoreless_off_angle"
    return "traded_even"


def _match_outcome_probs(pw: float, pd: float, pl: float, best_of: int) -> tuple[float, float, float]:
    """(P win, P draw, P loss) for a best-of-N match, from i.i.d. per-game rates.

    First to `best_of//2 + 1` wins takes the match immediately; if the distance is played out
    without either side getting there -- which drawn games make possible -- the side with more
    game wins takes it, and equal wins is a drawn MATCH (1 point each, COMPETITION_RULES Sec 7).

    i.i.d. is an approximation: the real start separation cycles 2,000/2,500/3,000 ft by game
    index, so game 3 is not drawn from the same distribution as game 1. Once the matrix is run
    per separation, feed the per-separation rates in game order instead of one pooled rate.
    """
    need = best_of // 2 + 1

    def rec(game: int, w: int, l: int, prob: float) -> tuple[float, float, float]:
        if w >= need:
            return (prob, 0.0, 0.0)
        if l >= need:
            return (0.0, 0.0, prob)
        if game == best_of:
            if w > l:
                return (prob, 0.0, 0.0)
            if w < l:
                return (0.0, 0.0, prob)
            return (0.0, prob, 0.0)
        out = [0.0, 0.0, 0.0]
        for p, dw, dl in ((pw, 1, 0), (pd, 0, 0), (pl, 0, 1)):
            if p <= 0.0:
                continue
            for i, v in enumerate(rec(game + 1, w + dw, l + dl, prob * p)):
                out[i] += v
        return tuple(out)

    return rec(0, 0, 0, 1.0)


def _load(path: Path, legacy: bool = False) -> dict | None:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    if not rows:
        return None
    n = len(rows)
    w = l = d = kills = free = wez_entry = 0
    dealt = taken = 0.0
    draws = {k: 0 for k in DRAW_KINDS}
    for r in rows:
        ph = (r.get("phased_outcome") or "").strip().lower()
        end = (r.get("end_condition") or "").strip()
        dealt += float(r.get("ep_damage_dealt") or 0)
        taken += float(r.get("ep_damage_taken") or 0)
        if end == "target destroyed":
            kills += 1
        # WEZ ENTRY. The strictly necessary condition for a kill: measured over the F66 matrix,
        # 0 of 487 episodes that never entered the WEZ produced one. It moves before win rate
        # does and separates at far lower N, so it is the right screening metric for a sweep.
        if float(r.get("ep_wez_steps_phased") or r.get("ep_wez_steps") or 0) > 0:
            wez_entry += 1

        if not legacy and end in _TARGET_LOST:
            # COMPETITION_RULES Sec 5: below the floor is processed as a crash/loss, and the
            # rule is symmetric. `_classify_outcome` is not -- it returns "crash" when WE go
            # below it but falls through to "draw" when the TARGET does, because the target
            # still had health. summarize_cutoff.py has adjudicated this correctly since it was
            # written; league.py did not, so the two disagreed on 73 episodes of the shipped
            # matrices (17 of 150 in ship_6000_120_deck vs cutoff alone, worth +11 points of
            # BO3 match win rate). Same import, same semantics, one place to change.
            w += 1
            free += 1
        elif not legacy and end in _OWNSHIP_LOST:
            # Closes the other half: `phased_outcome == "crash"` fell into the `else` below and
            # was scored as a DRAW. Reproducing F74's published head-on table requires exactly
            # that bug, and fixing it reverses which Model 2 candidate wins the mean.
            l += 1
        elif ph == "win":
            w += 1
        elif ph == "loss":
            l += 1
        else:
            d += 1
            draws[_classify_draw(r)] += 1

    pw, pd, pl = w / n, d / n, l / n
    mw3, md3, _ = _match_outcome_probs(pw, pd, pl, 3)
    mw5, _, _ = _match_outcome_probs(pw, pd, pl, 5)
    return {"n": n, "w": w, "d": d, "l": l, "kills": kills, "free": free,
            "wez_entry": wez_entry, "wez_rate": wez_entry / n,
            "dealt": dealt / n, "taken": taken / n, "diff": (dealt - taken) / n,
            "draw_rate": pd, "draws": draws,
            # 승 3 / 무 1 / 패 0 over the group-stage BO3
            "bo3_points": 3.0 * mw3 + 1.0 * md3,
            "bo5_win": mw5}


def summarize(args: argparse.Namespace) -> None:
    archs = list(ARCHETYPES)
    rows: dict[str, dict[str, dict]] = {}
    for path in sorted(_OUT.glob(f"league_{args.scenario_mode}__*.csv")):
        stem = path.stem[len(f"league_{args.scenario_mode}__"):]
        if "__vs__" not in stem:
            continue
        cand, arch = stem.split("__vs__", 1)
        got = _load(path, legacy=getattr(args, "legacy_scoring", False))
        if got:
            rows.setdefault(cand, {})[arch] = got

    if not rows:
        print("no league CSVs found -- run without --summarize first")
        return

    present = [a for a in archs if any(a in v for v in rows.values())]

    # MIXED-N GUARD (2026-09-04). These CSVs are overwritten in place, one pair at a time, so a
    # matrix run that is still in flight -- or that died partway -- leaves some pairs holding the
    # PREVIOUS campaign's rows at the previous episode count. Summarising that silently averages
    # an N=150 column against an N=50 one and reports it as a single ranking. This project has
    # been bitten repeatedly by exactly this shape of silent staleness (F8, F57, F59 phase 0), so
    # it is called out loudly rather than left for the reader to notice.
    _ns = sorted({g["n"] for per in rows.values() for g in per.values()})
    if len(_ns) > 1:
        print()
        print(f"!! MIXED EPISODE COUNTS ACROSS PAIRS: {_ns}")
        print("!! Some pairs are stale or the run is still in flight. Per-pair N:")
        for cand in sorted(rows):
            bits = "  ".join(f"{a}={rows[cand][a]['n']}" for a in present if a in rows[cand])
            print(f"!!   {cand:<22} {bits}")
        print("!! Ranking below mixes them. Re-run the short pairs before trusting it.")
        print()

    # Primary key (F61): mean expected BO3 points; minimax on the worst column; draw rate breaks
    # remaining ties, lower being better.
    ranked = []
    for cand, per in rows.items():
        # SELF-PLAY COLUMNS ARE EXCLUDED FROM THE MINIMAX FLOOR (2026-09-08).
        #
        # `aggressor` is parameter-for-parameter IDENTICAL to `ship_6000_120_deck` -- 6000 m,
        # 120 deg, throttle on, hard deck 1000 -- just on the target side. So for the shipped
        # candidate that column is self-play, and a symmetric matchup CANNOT exceed ~50% by
        # construction. Measured: 32W/35D/33L, which is exactly the coin flip it has to be.
        #
        # That mattered because the adoption gate was "mean up AND minimax floor not down", and
        # `min(pts)` always landed on that pinned column. Every sweep was being graded partly on
        # a criterion no config can satisfy, which is a defect in the harness, not in the
        # aircraft. `mirror` (6000/90) has the same shape against the PREVIOUS shipped config.
        #
        # The column is still measured and still printed -- a symmetric matchup is a genuinely
        # useful check (it should sit near 50%, and a large deviation means a side-dependent bug,
        # which is how F67 was found). It just cannot be the floor.
        # NOTE the asymmetry: only WORST drops the self-play column. MEAN keeps every column, so
        # it stays directly comparable to every mean in the F-register. That is safe because a
        # pinned ~1.3 column adds the same constant to every candidate and cannot reorder them;
        # WORST is different, because `min()` selects that column for everyone and the criterion
        # then measures nothing.
        selfplay = {a for a in present if a in per and _is_selfplay(cand, a)}
        floor_cols = [a for a in present if a in per and a not in selfplay] or list(per)
        pts = [per[a]["bo3_points"] for a in present if a in per]
        floor_pts = [per[a]["bo3_points"] for a in floor_cols]
        diffs = [per[a]["diff"] for a in present if a in per]
        draws = [per[a]["draw_rate"] for a in present if a in per]
        mean_pts = sum(pts) / len(pts) if pts else float("nan")
        worst_pts = min(floor_pts) if floor_pts else float("nan")
        mean_draw = sum(draws) / len(draws) if draws else float("nan")
        mean_diff = sum(diffs) / len(diffs) if diffs else float("nan")
        worst_diff = min(diffs) if diffs else float("nan")
        ranked.append({"cand": cand, "per": per, "selfplay": selfplay,
                       "mean_pts": mean_pts, "worst_pts": worst_pts,
                       "mean_draw": mean_draw, "mean_diff": mean_diff, "worst_diff": worst_diff})
    ranked.sort(key=lambda x: (x["mean_pts"], x["worst_pts"], -x["mean_draw"]), reverse=True)

    head = f"{'candidate':<22}" + "".join(f"{a:>13}" for a in present) + f"{'MEAN':>9}{'WORST':>9}"

    # ASCII only in PRINTED output. A Korean literal here dies with UnicodeEncodeError the
    # moment stdout is a cp949 console or a redirect -- the F40 failure mode, which killed the
    # live entry point before its reconnect loop was ever armed. Docstrings are fine (argparse
    # here has no description=, so this module's docstring is never written to stdout).
    if getattr(args, "legacy_scoring", False):
        print("\n!! LEGACY SCORING -- altitude-floor episodes booked as draws for BOTH sides.")
        print("!! Reproduces the register up to F76. Not the competition rule. See --help.")
    else:
        _free = sum(g.get("free", 0) for per in rows.values() for g in per.values())
        print(f"\nScoring: COMPETITION_RULES Sec 5 altitude floor adjudicated for both sides "
              f"({_free} opponent floor-outs counted as wins). --legacy-scoring for the old table.")

    print(f"\nEXPECTED BO3 MATCH POINTS (win 3 / draw 1 / loss 0) -- scenario={args.scenario_mode}")
    print("Primary ranking key. 3.00 = wins every match, 1.00 = draws every match.")
    print(head)
    print("-" * len(head))
    for row in ranked:
        line = f"{row['cand']:<22}"
        for a in present:
            line += f"{row['per'][a]['bo3_points']:>13.2f}" if a in row["per"] else f"{'--':>13}"
        print(line + f"{row['mean_pts']:>9.2f}{row['worst_pts']:>9.2f}")
    print("-" * len(head))
    print("Ranked on MEAN points; WORST is the minimax floor -- no opponent can be avoided,")
    print("so a config that peaks on three columns and collapses on one is worse than a flat one.")
    _sp = {c: sorted(r["selfplay"]) for c in [x["cand"] for x in ranked]
           for r in ranked if r["cand"] == c and r["selfplay"]}
    if _sp:
        print()
        for cand, cols in _sp.items():
            print(f"!! {cand}: {', '.join(cols)} is SELF-PLAY (identical config on the target "
                  f"side).")
        print("!! Those columns are EXCLUDED from WORST: a symmetric matchup is pinned near 50%")
        print("!! by construction, so it cannot be a floor. They are still shown, and are a")
        print("!! useful side-symmetry check -- a large deviation from ~1.3 pts means a")
        print("!! side-dependent bug, which is how F67 was originally found.")

    print(f"\nDAMAGE DIFFERENTIAL (dealt - taken, per episode) -- within-game predictor, not the key")
    print(head)
    print("-" * len(head))
    for row in ranked:
        line = f"{row['cand']:<22}"
        for a in present:
            line += f"{row['per'][a]['diff']:>+13.3f}" if a in row["per"] else f"{'--':>13}"
        print(line + f"{row['mean_diff']:>+9.3f}{row['worst_diff']:>+9.3f}")
    print("-" * len(head))

    # WEZ ENTRY RATE. Fraction of episodes that got inside the weapons envelope at least once.
    # This is the funnel's binding constraint, not closure: across the F66 matrix 100% of
    # episodes came inside 914.4 m at some point, and against `sniper` the 113 episodes that
    # never entered the WEZ still had a median minimum ATA of 0.01 deg -- both conditions met,
    # never simultaneously. Screen sweeps on this column; it moves before bo3_points does.
    print(f"\nWEZ ENTRY RATE (episodes reaching the weapons envelope at least once)")
    print("Necessary condition for a kill: 0 of 487 never-entered episodes produced one.")
    print(head)
    print("-" * len(head))
    for row in ranked:
        line = f"{row['cand']:<22}"
        vals = []
        for a in present:
            if a in row["per"]:
                v = row["per"][a]["wez_rate"]
                vals.append(v)
                line += f"{v:>12.1%} "
            else:
                line += f"{'--':>13}"
        mean_w = sum(vals) / len(vals) if vals else float("nan")
        print(line + f"{mean_w:>8.1%} {min(vals) if vals else float('nan'):>8.1%}")
    print("-" * len(head))

    print(f"\nW/D/L, kills, and BO5 win probability (knockout)")
    for row in ranked:
        parts = [f"{a}: {row['per'][a]['w']}/{row['per'][a]['d']}/{row['per'][a]['l']}"
                 f" ({row['per'][a]['kills']}k, bo5 {row['per'][a]['bo5_win']:.0%})"
                 for a in present if a in row["per"]]
        print(f"  {row['cand']:<22} " + "  ".join(parts))

    print(f"\nDRAW DECOMPOSITION -- draw rate, then what the draws actually were")
    print("  mutual_kill        both aircraft destroyed")
    print("  scoreless_nose_on  no damage either way, but >=10% of the episode inside 2 deg ATA"
          " -- a CLOSURE failure")
    print("  scoreless_off_angle no damage either way, never pointed -- a POINTING failure")
    print("  traded_even        damage in both directions, adjudicated even")
    for row in ranked:
        print(f"  {row['cand']:<22} mean draw rate {row['mean_draw']:.0%}")
        for a in present:
            if a not in row["per"]:
                continue
            g = row["per"][a]
            if not g["d"]:
                print(f"      {a:<12} no draws")
                continue
            kinds = "  ".join(f"{k}={g['draws'][k]}" for k in DRAW_KINDS if g["draws"][k])
            print(f"      {a:<12} {g['d']:>2}/{g['n']} draws  {kinds}")

    floor = [(row["cand"], a) for row in ranked for a in present
             if a in row["per"] and row["per"][a]["l"] > row["per"][a]["w"]]
    if floor:
        print(f"\nFLOOR VIOLATIONS (losses exceed wins -- F61 says these cannot be shipped around)")
        for cand, a in floor:
            print(f"  {cand} loses its {a} column")
    print("\nNOTE: `sniper` is a GoGoSSung/HAnnamAir ANALOGUE, `aggressor` is a Fight's on! "
          "ANALOGUE -- not replicas. Do not read these rows as results against those teams.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", type=int, default=50,
                   help="TARGET episode count per pair (not per-invocation). Re-running this "
                        "same command resumes each pair from however many episodes its CSV "
                        "already has, up to this target.")
    p.add_argument("--chunk-episodes", type=int, default=15,
                   help="Max NEW episodes to run per pair in a single invocation (default 15, "
                        "~2.4 pipelined rounds at 15 pairs/jobs=6, ~30 min wall-clock -- sized "
                        "to survive after two unchunked N=150 runs both died with the same "
                        "external-kill signature at 20-41 min. Re-invoke the command to "
                        "continue; see COMPETITION_PLAN.md F65.")
    p.add_argument("--jobs", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--scenario-mode", default="match_base",
                   choices=["match_base", "match_tiebreak"])
    p.add_argument("--candidates", nargs="*", default=None)
    p.add_argument("--archetypes", nargs="*", default=None)
    p.add_argument("--altitude-range", default=DEFAULT_ALTITUDE_RANGE_M,
                   help='Per-episode start-altitude band "lo,hi" in metres, or "" to disable '
                        f'(default "{DEFAULT_ALTITUDE_RANGE_M}" -- a PROXY, the real band is '
                        f'unpublished; see the constant for the evidence behind it).')
    p.add_argument("--speed-range", default=DEFAULT_SPEED_RANGE_MPS,
                   help='Per-episode start-speed band "lo,hi" in m/s, or "" to disable '
                        f'(default "{DEFAULT_SPEED_RANGE_MPS}").')
    p.add_argument("--skip-existing", action="store_true",
                   help="Skip pairs whose CSV already exists, however many rows it has. DO NOT "
                        "use this to avoid re-touching completed pairs in a chunked/resumed run "
                        "-- resumption is automatic (every pair below --episodes target is "
                        "topped up, pairs at target are left alone) and does not need this flag. "
                        "After the FIRST chunk, every pair's CSV exists, so this flag would skip "
                        "ALL of them and silently stall the matrix at whatever it reached. Only "
                        "for starting a genuinely fresh sweep without clobbering unrelated CSVs "
                        "left over from a different candidate/archetype experiment.")
    p.add_argument("--summarize", action="store_true")
    p.add_argument("--legacy-scoring", action="store_true",
                   help="Score the way league.py did before 2026-09-08: the target's altitude "
                        "floor booked as a draw and our own self-crash booked as a draw too. "
                        "Wrong under COMPETITION_RULES Sec 5, but every register number up to "
                        "F76 was computed this way -- keep it so old results stay reproducible.")
    args = p.parse_args()
    summarize(args) if args.summarize else run(args)


if __name__ == "__main__":
    main()
