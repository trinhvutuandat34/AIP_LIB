#!/usr/bin/env bash
# Sweep the hard deck ABOVE 1,000 m on the corrected band. 2026-09-12.
#
# WHY THIS AND NOT SOMETHING ELSE. On the corrected band, n=200 of the shipped config vs cutoff:
#   47.5% max time out | 17.0% ownship destroyed | 17.0% target destroyed
#   11.5% target ground strike | 7.0% OWNSHIP GROUND STRIKE
# We lose the aircraft in 24% of episodes against killing theirs in 17%. The 7% ground strike is
# the only loss mode with no opponent in it at all -- a pure own-goal -- and bucketing by spawn
# altitude shows it is NOT a spawn artifact: 0% below 1,000 m (the deck already catches those,
# handing to the BT which climbs) and a flat 6.7-8.3% at EVERY band above it. So those come from
# combat descents, which is exactly what a deck is for.
#
# THE TREND IS MONOTONIC AND WE HAVE ONLY EVER TESTED ITS LOWER HALF:
#     deck 0    -> 60% ground strikes (sub-deck arm)
#     deck 600  -> 25% (full band, F85)
#     deck 1000 ->  7-9% (shipped)
#     deck >1000 -> NEVER TESTED.
#
# THE TRADE-OFF, stated up front so the result is read honestly. Below the deck `_tracking_stick`
# returns None and hands the aircraft to the BT, which is weak offensively (`bt_only` never
# shoots at all). Raising the deck therefore buys survival with offense, and it also raises the
# share of rounds that START on the BT: P(spawn below deck) is 4.6% at 1,000 m, 9.3% at 1,400,
# 16.3% at 2,000. 1,400 and 2,000 bracket the plausible range; if 1,400 wins, refine between.
#
# WATCH `deck` AND `dealt` TOGETHER. A deck that cuts ground strikes while collapsing damage
# dealt is the corner_on failure again -- a knob that moved its target metric and lost anyway.
#
# Control is band_nonotch_s1 (deck 1000, same seed, same band, n=100) -- not re-run.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
EPS=100
SEED=20260911

"$PY" scripts/assert_baseline.py || { echo "[deck] baseline dirty, aborting"; exit 1; }
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"

arm () {   # arm <name> <hard-deck-m>
  local name="$1" deck="$2"
  local out="artifacts/eval/band_${name}_vs_cutoff.csv"
  local have=0; [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  [ "$have" -ge "$EPS" ] && { echo "[deck] $name already at $have"; return; }
  echo "[deck] === $name  hard-deck=$deck  n=$EPS === $(date +%H:%M)"
  "$PY" scripts/eval_vs_cutoff.py \
    --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base \
    --episodes "$EPS" --seed "$SEED" --cutoff-action-repeat 6 \
    --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
    --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck "$deck" \
    --out-csv "$out" > "artifacts/eval/band_${name}.log" 2>&1
  echo "[deck] $name rc=$? rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 )) $(date +%H:%M)"
  "$PY" scripts/assert_baseline.py > /dev/null || echo "[deck] !! BASELINE DIRTY after $name"
}

arm deck1400 1400
arm deck2000 2000

echo; echo "[deck] === vs the shipped deck 1000, same seed and band ==="
"$PY" scripts/score_arms.py --control artifacts/eval/band_nonotch_s1_vs_cutoff.csv \
  artifacts/eval/band_deck1400_vs_cutoff.csv artifacts/eval/band_deck2000_vs_cutoff.csv
echo "[deck] done $(date +%H:%M)"
