#!/usr/bin/env bash
# Follow-on to run_bt_final.sh: the COMBINED candidate, plus a second-seed reproduction of the
# winner. Separate script rather than appended to the running one, because bash reads a script
# incrementally and editing a file mid-execution can make it resume at a corrupted offset.
#
# TWO ARMS, both N=100 against the cutoff, reusing run_bt_final's control (same seed 20260911):
#
#   no_notch_break_gated  the confirmed winner PLUS the break constraint. no_notch measured 1.76
#                         vs a 1.41 control and cut the break by 9,406 ticks as a side effect,
#                         but the break still wins 156,050 to Gun_Track's 16,721. If the surviving
#                         firings are the illegitimate ones, these stack; if they are the
#                         legitimate ones, this costs survivability. Either way it is attributable
#                         because break_gated is also measured alone in run_bt_final.sh.
#
#   no_notch_seed2        the SAME winner on a different seed. The Notch effect has reproduced
#                         three times (+0.32, +0.27, +0.34) but never yet on an independent draw
#                         at N=100 with its own control. standoff220 looked equally good until it
#                         was re-drawn, so this is the check that killed the last false positive.
#                         Its control is run at the same seed, in this script, paired.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
EPS=100
"$PY" scripts/assert_baseline.py || { "$PY" scripts/assert_baseline.py --repair; \
  "$PY" scripts/assert_baseline.py || { echo "[stack] baseline dirty, aborting"; exit 1; }; }
# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"

arm () {   # arm <name> <seed> [flags...]
  local name="$1" seed="$2"; shift 2
  local out="artifacts/eval/btf_${name}_vs_cutoff.csv"
  local have=0; [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  [ "$have" -ge "$EPS" ] && { echo "[stack] $name already at $have"; return; }
  echo "[stack] === $name (seed $seed) ==="
  "$PY" scripts/eval_vs_cutoff.py \
    --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base \
    --episodes "$EPS" --seed "$seed" --cutoff-action-repeat 6 \
    --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
    --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 \
    "$@" --out-csv "$out" > "artifacts/eval/btf_${name}.log" 2>&1
  echo "[stack] $name rc=$? rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 ))"
}

arm no_notch_break_gated 20260911 --bt-rule-xml experiments/rule_variants/bt_no_notch_break_gated.xml
arm control_seed2        20260912
arm no_notch_seed2       20260912 --bt-rule-xml experiments/rule_variants/bt_no_notch.xml

echo; echo "[stack] === seed 20260911 family (control from run_bt_final) ==="
"$PY" scripts/score_arms.py --control artifacts/eval/btf_control_vs_cutoff.csv \
  "artifacts/eval/btf_no_notch_vs_cutoff.csv" "artifacts/eval/btf_break_gated_vs_cutoff.csv" \
  "artifacts/eval/btf_gunfar_vs_cutoff.csv" "artifacts/eval/btf_c0aa0ff_xml_vs_cutoff.csv" \
  "artifacts/eval/btf_no_notch_break_gated_vs_cutoff.csv"
echo; echo "[stack] === seed 20260912 INDEPENDENT REPRODUCTION ==="
"$PY" scripts/score_arms.py --control artifacts/eval/btf_control_seed2_vs_cutoff.csv \
  "artifacts/eval/btf_no_notch_seed2_vs_cutoff.csv"
echo "[stack] done"
