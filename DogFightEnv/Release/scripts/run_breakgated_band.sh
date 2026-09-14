#!/usr/bin/env bash
# break_gated re-tested on the ORGANIZER-CONFIRMED band. 2026-09-12, the last candidate.
#
# WHY IT GETS A RUN AT ALL. It is the only lever with any surviving prior signal: bo3 +0.30 /
# win +7.0 pp at n=100 on seed 20260911 (BTFINAL/BTSTACK), never reproduced on a second seed.
# Every one of those numbers was measured on the wrong spawn band, so it is void the same way
# no_notch's +6.5 pp was -- and no_notch went to EXACTLY zero when re-measured (F85). Prior
# expectation here is therefore ~20%, not 50%.
#
# WHICH VARIANT, AND WHY NOT THE OBVIOUS ONE. The shipped tree is 61 nodes with Gate1_Notch
# already removed, so the single-variable arm is `bt_no_notch_break_gated.xml` (62 nodes, no
# Notch, break gate present). `bt_break_gated.xml` is 64 nodes and still CARRIES Notch -- using
# it would confound the break gate with re-adding a node we deleted.
#
# BOTH SEEDS, deliberately. The one durable lesson of this campaign is that single-seed results
# do not survive: standoff, corner_on and no_notch each looked real on one draw and died on the
# next. A one-seed positive here would not be actionable, so it is not worth running alone.
# Controls already exist at n=100 on both seeds (band_nonotch_s1 / band_nonotch_s2) and are not
# re-run.
#
# SEQUENTIAL. Both arms pass --bt-rule-xml, which copies the variant over the workspace
# Rule_forTraining.xml; two overlapping runs corrupt the shipped tree.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
EPS=100
VARIANT=experiments/rule_variants/bt_no_notch_break_gated.xml

"$PY" scripts/assert_baseline.py || { echo "[bg] baseline dirty, aborting"; exit 1; }
[ -f "$VARIANT" ] || { echo "[bg] missing $VARIANT"; exit 1; }
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"

arm () {   # arm <name> <seed>
  local name="$1" seed="$2"
  local out="artifacts/eval/band_${name}_vs_cutoff.csv"
  local have=0; [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  [ "$have" -ge "$EPS" ] && { echo "[bg] $name already at $have"; return; }
  echo "[bg] === $name seed=$seed n=$EPS === $(date +%H:%M)"
  "$PY" scripts/eval_vs_cutoff.py \
    --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base \
    --episodes "$EPS" --seed "$seed" --cutoff-action-repeat 6 \
    --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
    --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 \
    --bt-rule-xml "$VARIANT" \
    --out-csv "$out" > "artifacts/eval/band_${name}.log" 2>&1
  echo "[bg] $name rc=$? rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 )) $(date +%H:%M)"
  "$PY" scripts/assert_baseline.py > /dev/null || echo "[bg] !! BASELINE DIRTY after $name"
}

arm bgated_s1 20260911
arm bgated_s2 20260912

"$PY" scripts/assert_baseline.py || { "$PY" scripts/assert_baseline.py --repair; \
  "$PY" scripts/assert_baseline.py || echo "[bg] WARNING: baseline still dirty"; }

echo; echo "[bg] === seed 20260911 ==="
"$PY" scripts/score_arms.py --control artifacts/eval/band_nonotch_s1_vs_cutoff.csv \
  artifacts/eval/band_bgated_s1_vs_cutoff.csv
echo; echo "[bg] === seed 20260912 (independent draw) ==="
"$PY" scripts/score_arms.py --control artifacts/eval/band_nonotch_s2_vs_cutoff.csv \
  artifacts/eval/band_bgated_s2_vs_cutoff.csv
echo "[bg] done $(date +%H:%M)"
