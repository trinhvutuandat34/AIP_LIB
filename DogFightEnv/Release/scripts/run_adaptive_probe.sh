#!/usr/bin/env bash
# Reachability + outcome for bt_adaptive, in one run.
#
# The static estimate from artifacts/gate/trace.csv said Gate1A fires on 0.30% of ticks and
# Gate1B on 0.05%, which would make both dead on arrival. But that trace logs the first 1200
# ticks per tree plus ONLY path changes, so it over-samples the merge and cannot be read as a
# steady-state rate. This run settles it: gate tracing is ON for the whole arm, so
# audit_unreachable_nodes.py can say NEVER-EVALUATED / NEVER-SUCCEEDS about the two new nodes
# directly, on the geometry they were designed for, while the CSV gives the outcome.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"
export AIP_BT_GATE_TRACE="D:\aip_lib\DogFightEnv\Release\artifacts\gate\adaptive.csv"
export AIP_BT_GATE_TRACE_ALL=1
export AIP_BT_GATE_TRACE_FIRST=100000
rm -f artifacts/gate/adaptive.csv artifacts/gate/adaptive.csv.nodes.txt
"$PY" scripts/eval_vs_cutoff.py \
  --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base \
  --episodes 40 --seed 20260909 --cutoff-action-repeat 6 \
  --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
  --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 \
  --bt-rule-xml experiments/rule_variants/bt_adaptive.xml \
  --out-csv artifacts/eval/ablate_bt_adaptive_vs_cutoff.csv \
  > artifacts/eval/ablate_bt_adaptive.log 2>&1
echo "[adaptive] rc=$? rows=$(( $(wc -l < artifacts/eval/ablate_bt_adaptive_vs_cutoff.csv) - 1 ))"
echo "[adaptive] tree inits: $(grep -c 'Behavior Tree Initialized' artifacts/eval/ablate_bt_adaptive.log)"
"$PY" scripts/audit_unreachable_nodes.py artifacts/gate/adaptive.csv 2>&1 | tail -25
echo "[adaptive] done"
