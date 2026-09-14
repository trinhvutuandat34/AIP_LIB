#!/usr/bin/env bash
# THE NULL CONTROL. Four BT arms all scored below control, and every one of them was the arms
# that passed --bt-rule-xml; the two that did not (control, standoff220) scored above. That is a
# common-mode artifact signature, not four tactical results.
#
# Two arms separate the two candidate causes:
#   bt_identity_bytes  a byte-identical copy of the shipped XML, loaded through --bt-rule-xml.
#                      If THIS differs from control, the copy path (activate_rule_xml) or the
#                      act of passing the flag is the artifact, and every BT arm is void.
#   bt_identity_hdr    same tree with the leading <!-- ... --> header every variant carries.
#                      If bytes matches control but hdr does not, the header comment before
#                      <root> is what breaks the build.
# Either way the answer is unambiguous, and it decides whether the BT ablation series means
# anything at all. Run before spending any more sim time on tree variants.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"
for v in bt_identity_bytes bt_identity_hdr; do
  echo "[null] === $v ==="
  "$PY" scripts/eval_vs_cutoff.py \
    --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base \
    --episodes 40 --seed 20260909 --cutoff-action-repeat 6 \
    --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
    --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 \
    --bt-rule-xml "experiments/rule_variants/$v.xml" \
    --out-csv "artifacts/eval/ablate_${v}_vs_cutoff.csv" \
    > "artifacts/eval/ablate_${v}.log" 2>&1
  echo "[null] $v rc=$? rows=$(( $(wc -l < artifacts/eval/ablate_${v}_vs_cutoff.csv) - 1 ))"
  grep -c "Behavior Tree Initialized" "artifacts/eval/ablate_${v}.log" | xargs echo "[null] tree inits:"
done
echo "[null] done"
