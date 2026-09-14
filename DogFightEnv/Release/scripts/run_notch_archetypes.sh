#!/usr/bin/env bash
# no_notch coverage against the two vptrack archetypes (2026-09-09).
#
# READ THIS BEFORE TRUSTING THE OUTPUT. This is NOT a clean A/B and cannot be made into one.
# `bt_rule_manager.activate_rule_xml()` copies the variant over the single workspace
# `Rule_forTraining.xml`, and BOTH aircraft's BT DLLs read that one file. `aggressor` and
# `sniper` are our own vptrack controller on the target side, so the variant applies to the
# opponent too. Only `cutoff` is a clean arm, because it runs its own binary.
#
# WHAT EACH ARCHETYPE CAN STILL TELL US:
#   aggressor  parameter-for-parameter identical to our ownship config, so the XML change is
#              near-symmetric and the NULL EXPECTATION IS ZERO DELTA. Its job is to catch a
#              catastrophic regression (deaths, deck strikes, nopoint%), not to confirm a gain.
#   sniper     2500 m / 45 deg, so the sniper side falls through to the BT far more often than
#              we do and receives MORE of the change than we do. If removing Notch is genuinely
#              good, our win rate here should DROP. A drop is evidence FOR, not against.
#
# ORDER MATTERS AND IS NOT AN OPTIMISATION DETAIL. Two overlapping runs with different XML
# corrupt the shipped tree permanently -- see scripts/assert_baseline.py's header, where it
# already happened once. So:
#   Phase 1: both CONTROL arms in parallel. Neither passes --bt-rule-xml, so neither writes the
#            file; they only read it. Safe to overlap.
#   Phase 2: each VARIANT arm alone, one after the other. activate_rule_xml is safe exactly once
#            at a time. Never overlap these, with each other or with Phase 1.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
EPS=100
SEED=20260913
VARIANT=experiments/rule_variants/bt_no_notch.xml

"$PY" scripts/assert_baseline.py || { echo "[notch] baseline dirty, aborting"; exit 1; }

# Same start-condition bands as run_bt_final/run_bt_stack, so these are comparable with the
# cutoff arms rather than a third set of conditions.
# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"

OWN="--ownship-backend vptrack --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
     --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000"
AGG="--target-backend vptrack --target-vptrack-range-m 6000 --target-vptrack-los-deg 120 \
     --target-vptrack-throttle 1 --target-vptrack-hard-deck 1000"
SNI="--target-backend vptrack --target-vptrack-range-m 2500 --target-vptrack-los-deg 45 \
     --target-vptrack-throttle 1"

arm () {   # arm <name> <target-flags> [extra...]
  local name="$1" tgt="$2"; shift 2
  local out="artifacts/eval/na_${name}.csv"
  local have=0; [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  [ "$have" -ge "$EPS" ] && { echo "[notch] $name already at $have"; return; }
  echo "[notch] === $name ==="
  "$PY" scripts/eval_v5_vs_bt.py --scenario-mode match_base \
    --episodes "$EPS" --seed "$SEED" $OWN $tgt "$@" --out-csv "$out" \
    > "artifacts/eval/na_${name}.log" 2>&1
  echo "[notch] $name rc=$? rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 ))"
}

echo "[notch] --- phase 1: controls, parallel, shipped XML untouched ---"
arm control_agg "$AGG" &
arm control_sni "$SNI" &
wait

"$PY" scripts/assert_baseline.py || { echo "[notch] baseline dirty after phase 1, aborting"; exit 1; }

echo "[notch] --- phase 2: variants, STRICTLY SEQUENTIAL ---"
arm nonotch_agg "$AGG" --bt-rule-xml "$VARIANT"
arm nonotch_sni "$SNI" --bt-rule-xml "$VARIANT"

# The restore is activate_rule_xml's finally block; verify it actually happened rather than
# assuming. --repair pulls Rule_forTraining.xml back from git HEAD if it did not.
"$PY" scripts/assert_baseline.py || { "$PY" scripts/assert_baseline.py --repair; \
  "$PY" scripts/assert_baseline.py || echo "[notch] WARNING: baseline still dirty"; }

echo; echo "[notch] === aggressor (null expectation: no delta) ==="
"$PY" scripts/score_arms.py --control artifacts/eval/na_control_agg.csv artifacts/eval/na_nonotch_agg.csv
echo; echo "[notch] === sniper (opponent gets MORE of the change than we do) ==="
"$PY" scripts/score_arms.py --control artifacts/eval/na_control_sni.csv artifacts/eval/na_nonotch_sni.csv
echo "[notch] done"
