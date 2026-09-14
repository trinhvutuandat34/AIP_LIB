#!/usr/bin/env bash
# Four arms against the cutoff, N=40, seed 20260909 -- the same seed as the
# league_match_base__ship_6000_120_deck__vs__cutoff.csv control, so the comparison is paired.
#
# SERIAL BY NECESSITY, NOT BY CHOICE. bt_rule_manager.activate_rule_xml() copies the chosen XML
# over the live Rule_forTraining.xml for the duration of the run. Two arms with different XMLs
# running at once would clobber each other's tree mid-episode, and per F70 a bad tree load is
# SILENT -- it becomes an all-zero ControlValue that still handshakes at 60 Hz. So: one at a time.
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

run () {                       # run <name> <extra args...>
  local name="$1"; shift
  local out="artifacts/eval/ablate_${name}_vs_cutoff.csv"
  if [ -f "$out" ] && [ "$(( $(wc -l < "$out") - 1 ))" -ge 40 ]; then
    echo "[ablate] $name already at 40, skipping"; return
  fi
  echo "[ablate] === $name ==="
  "$PY" scripts/eval_vs_cutoff.py $COMMON "$@" --out-csv "$out" \
      > "artifacts/eval/ablate_${name}.log" 2>&1
  echo "[ablate] $name rc=$?  rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 ))"
  # F70 guard: a failed Rule XML load is silent, so assert the tree actually came up.
  local inits
  inits=$(grep -c "Behavior Tree Initialized" "artifacts/eval/ablate_${name}.log" || true)
  echo "[ablate] $name  'Behavior Tree Initialized' x $inits  (expect ~2 per episode)"
}

run standoff220  --ownship-vptrack-standoff-m 220
run bt_minimal      --bt-rule-xml experiments/rule_variants/bt_minimal.xml
run bt_no_gate1     --bt-rule-xml experiments/rule_variants/bt_no_gate1.xml
run bt_pursuit_only --bt-rule-xml experiments/rule_variants/bt_pursuit_only.xml
echo "[ablate] all arms done"
