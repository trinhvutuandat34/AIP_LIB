#!/usr/bin/env bash
# CONFIRMATION PASS. N=100 per cell, because N=40 has now been shown not to resolve differences
# of the size we are chasing.
#
# THE EVIDENCE FOR THAT, measured 2026-09-09 and the reason this script exists:
#   ship_6000_120_deck  N=40  bo3 1.80   |  standoff220  N=40  bo3 2.15
#   ship_6000_120_deck  N=100 bo3 1.60   |  standoff220  N=100 bo3 1.53
# Same configs, different samples, bo3 moving 0.2-0.6. The +0.35 that made standoff220 look like
# the best candidate of the session was sampling noise, and it reversed on confirmation. The
# harness is fine -- a first-40 vs first-40-of-100 check agreed on 39 of 40 episodes -- so this
# is sample size, not determinism.
#
# So: only two candidates are carried forward, and only at N=100.
#   deckttc_on            the most mechanistically convincing arm of the session: own-floor
#                         crashes 8% -> 0%, WEZ entry 72.5% -> 85%, nopoint 35% -> 20%, damage
#                         dealt 0.462 -> 0.635, and the only arm with a positive net differential.
#                         Cost: deaths 8% -> 15%. Worth resolving properly.
#   bt_deadwood_no_notch  removes the measured-dead nodes plus Gate1_Notch, which succeeded on
#                         7,660 of 15,695 traced ticks while holding no maneuver phase claim.
#                         BT variant, so it can only be measured against `cutoff` -- every other
#                         archetype reads the same global Rule XML and the change cancels.
#
# Everything else is closed: corner_on and defensive_on measured negative both directions;
# taper5/15, los140 and the wide range arms closed earlier; bt_minimal / bt_deadwood /
# bt_pursuit_only are large, real regressions; threatbreak measured exactly neutral (its gate
# fires on ~0.05% of ticks); standoff220 failed its own confirmation above.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"

"$PY" scripts/assert_baseline.py || { echo "[confirm] baseline dirty; repairing"; \
  "$PY" scripts/assert_baseline.py --repair; \
  "$PY" scripts/assert_baseline.py || { echo "[confirm] STILL dirty, aborting"; exit 1; }; }

# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"

# 1. deckttc across the whole roster at N=100. It is a --ownship-* flag, so unlike a BT variant
#    it IS measurable against every archetype.
for pass in 1 2 3 4 5 6 7 8 9 10 11 12; do
  echo "[confirm] ---- roster pass $pass ----"
  "$PY" scripts/league.py --candidates deckttc_on adaptive300_deckttc ship_6000_120_deck \
      --archetypes cutoff mirror sniper aggressor bt_only \
      --episodes 100 --chunk-episodes 25 --jobs 3 --seed 20260910 \
      >> artifacts/eval/CONFIRM_roster.log 2>&1
  grep -q "every pair has reached 100 episodes" artifacts/eval/CONFIRM_roster.log && break
done

# 2. The BT arm, cutoff only, N=100, against a same-seed control run the same way.
for arm in "bt_deadwood_no_notch:--bt-rule-xml experiments/rule_variants/bt_deadwood_no_notch.xml" \
           "standoff200_gated:--ownship-vptrack-standoff-m 200" \
           "adaptive300:--ownship-vptrack-standoff-m 300 --ownship-vptrack-adaptive-range 1" \
           "control:"; do
  name="${arm%%:*}"; flags="${arm#*:}"
  out="artifacts/eval/confirm_${name}_vs_cutoff.csv"
  have=0; [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  [ "$have" -ge 100 ] && { echo "[confirm] $name already at $have"; continue; }
  echo "[confirm] === $name N=100 ==="
  "$PY" scripts/eval_vs_cutoff.py \
    --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base \
    --episodes 100 --seed 20260910 --cutoff-action-repeat 6 \
    --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
    --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 \
    $flags --out-csv "$out" > "artifacts/eval/confirm_${name}.log" 2>&1
  echo "[confirm] $name rc=$? rows=$(( $(wc -l < "$out") - 1 ))"
done

"$PY" scripts/score_arms.py --control artifacts/eval/confirm_control_vs_cutoff.csv \
    "artifacts/eval/confirm_*_vs_cutoff.csv"
"$PY" scripts/matrix_report.py --candidates deckttc_on ship_6000_120_deck
echo "[confirm] done"
