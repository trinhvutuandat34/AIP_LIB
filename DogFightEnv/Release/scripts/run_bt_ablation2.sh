#!/usr/bin/env bash
# Second ablation pass: the TARGETED cuts, plus the last never-measured pre-existing knob.
# Same N, seed and control as run_bt_ablation.sh, so all arms are paired against
# league_match_base__ship_6000_120_deck__vs__cutoff.csv (N=40, seed 20260909).
#
# bt_deadwood is the CONTROL as much as it is a variant: it removes only nodes the gate trace
# measured as never succeeding, so it should be behaviourally identical to the shipped tree.
# If this arm moves, the ablation harness itself is changing outcomes and every other arm in
# both passes is suspect. Run it first.
#
# Serial for the same reason as pass 1: activate_rule_xml() swaps the live Rule_forTraining.xml.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
COMMON="--ownship-backend vptrack --target-backend cutoff --scenario-mode match_base
        --episodes 40 --seed 20260909 --cutoff-action-repeat 6
        --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120
        --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000"
# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"

run () {
  local name="$1"; shift
  local out="artifacts/eval/ablate_${name}_vs_cutoff.csv"
  if [ -f "$out" ] && [ "$(( $(wc -l < "$out") - 1 ))" -ge 40 ]; then
    echo "[ablate2] $name already at 40, skipping"; return
  fi
  echo "[ablate2] === $name ==="
  "$PY" scripts/eval_vs_cutoff.py $COMMON "$@" --out-csv "$out" \
      > "artifacts/eval/ablate_${name}.log" 2>&1
  echo "[ablate2] $name rc=$?  rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 ))"
  local inits
  inits=$(grep -c "Behavior Tree Initialized" "artifacts/eval/ablate_${name}.log" || true)
  echo "[ablate2] $name  'Behavior Tree Initialized' x $inits  (expect ~2 per episode)"
}

run bt_deadwood          --bt-rule-xml experiments/rule_variants/bt_deadwood.xml
run bt_deadwood_no_notch --bt-rule-xml experiments/rule_variants/bt_deadwood_no_notch.xml
run threatbreak          --bt-rule-xml experiments/rule_variants/gate1_threat_break.xml
run deckttc              --ownship-vptrack-deck-ttc 5
echo "[ablate2] all arms done"
