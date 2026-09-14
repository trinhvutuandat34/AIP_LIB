#!/usr/bin/env bash
# The two BT candidates that target the MEASURED bottleneck, at N=100 against the cutoff.
#
# THE BOTTLENECK, from a full trace (374,744 ticks / 40 episodes, artifacts/gate/adaptive.csv):
#   - we are at Phase-1 RANGE on 15.8% of ticks, but our ATA is > 3 deg for 92.7% of that time
#   - ATA <= 1 deg happens on only 2.1% of ticks, and 49.3% of THOSE are beyond 4000 ft
#   - Gate1_TheBreak wins 60,010 ticks against Gun_Track's 6,577, a 9:1 break-to-track ratio
# So: angle while in range is the constraint, and the tick that could hold a track is usually
# spent extending away at throttle 0.5. Range is NOT the constraint, and the 500 ft dead zone is
# a red herring -- only 0.7% of pointed ticks are inside it.
#
# TWO CANDIDATES, attacking that from opposite ends:
#   bt_break_gated  Task_Evade additionally requires the bandit's own ATA < 60 deg, i.e. stop
#                   breaking when nobody is actually threatening us. Does NOT disable the break;
#                   Gate1_JinkingTurn and Gate1_Notch still cover close threats.
#   bt_gunfar       a SECOND gun-track branch at 914-1219 m, nested BELOW the primary gate so
#                   Phase-1 geometry always wins first. Task_GunTrack biases toward 220 m, so at
#                   1000 m it closes while holding the nose on -- pointed AND closing.
#
# N=100 AND A SAME-SEED CONTROL, both deliberate. N=40 has now misled this project twice:
# standoff220 read bo3 2.15 at N=40 and 1.53 at N=100, and every N=40 standoff arm clustered at
# ~2.1 regardless of setpoint. Sampling alone moves bo3 by 0.2-0.6 at that size.
#
# GATE TRACING IS ON for both arms, because an XML variant whose new nodes never fire is this
# project's most repeated failure (F25, F37, Gate1_DefensiveSpiral). The audit at the end says
# whether the nodes actually ran; without it a null result is uninterpretable.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
SEED=20260911
EPS=100

"$PY" scripts/assert_baseline.py || { echo "[btfinal] baseline dirty; repairing"; \
  "$PY" scripts/assert_baseline.py --repair; \
  "$PY" scripts/assert_baseline.py || { echo "[btfinal] STILL dirty, aborting"; exit 1; }; }

# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"
COMMON="--ownship-backend vptrack --target-backend cutoff --scenario-mode match_base
        --episodes $EPS --seed $SEED --cutoff-action-repeat 6
        --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120
        --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000"

run () {                        # run <name> [--bt-rule-xml path]
  local name="$1"; shift
  local out="artifacts/eval/btf_${name}_vs_cutoff.csv"
  local have=0; [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  if [ "$have" -ge "$EPS" ]; then echo "[btfinal] $name already at $have"; return; fi
  echo "[btfinal] === $name ==="
  rm -f "artifacts/gate/btf_${name}.csv" "artifacts/gate/btf_${name}.csv.nodes.txt"
  AIP_BT_GATE_TRACE="D:\\aip_lib\\DogFightEnv\\Release\\artifacts\\gate\\btf_${name}.csv" \
  AIP_BT_GATE_TRACE_ALL=1 AIP_BT_GATE_TRACE_FIRST=100000 \
  "$PY" scripts/eval_vs_cutoff.py $COMMON "$@" --out-csv "$out" \
      > "artifacts/eval/btf_${name}.log" 2>&1
  echo "[btfinal] $name rc=$? rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 ))" \
       "inits=$(grep -c 'Behavior Tree Initialized' artifacts/eval/btf_${name}.log)"
}

run control
# no_notch FIRST: it is the highest-prior candidate. bt_deadwood (0.77) and bt_deadwood_no_notch
# (1.69) differ by exactly this node, so removing Notch is worth +0.92 bo3 -- and the winning arm
# carries five deletions we now know are harmful. This isolates the gain.
run no_notch    --bt-rule-xml experiments/rule_variants/bt_no_notch.xml
run break_gated --bt-rule-xml experiments/rule_variants/bt_break_gated.xml
run gunfar      --bt-rule-xml experiments/rule_variants/bt_gunfar.xml
# The old tree structure on the current binary. Differs from the shipped XML by exactly the three
# spiral nodes, so it isolates the 2026-09-06 XML change from the C++ repairs that shipped with
# it. ab_head_0908 was meant to settle this and stalled at 17/100. PRE-REGISTERED PREDICTION:
# this LOSES, because Gate1_DefensiveSpiral fires 1,485 times against the cutoff and bt_deadwood,
# which also removed it, collapsed to 0.77. If it WINS, the 09-06 tree change is not paying for
# itself and rollback becomes a live option.
run c0aa0ff_xml --bt-rule-xml experiments/rule_variants/bt_c0aa0ff_xml.xml

echo
echo "[btfinal] ==== did the new nodes actually fire? ===="
"$PY" - <<'PYEOF'
import csv
from collections import Counter
csv.field_size_limit(10_000_000)
WANT = {"no_notch":    ["Gate1_JinkingTurn", "Gate1_TheBreak", "Gate2_Beam_NoseToTail", "Gun_Track"],
        "break_gated": ["Gate1_Break_TgtATA_Lt60", "Gate1_TheBreak", "Gun_Track"],
        "gunfar":      ["GunFar_DistGt914", "GunFar_OwnATA_Lt8", "Gun_Track_Far", "Gun_Track"],
        "c0aa0ff_xml": ["Gate1_JinkingTurn", "Gate1_TheBreak", "Gate1_Notch", "Gun_Track"]}
for arm, names in WANT.items():
    try:
        rows = list(csv.DictReader(open(f"artifacts/gate/btf_{arm}.csv", encoding="utf-8", errors="replace")))
    except FileNotFoundError:
        print(f"  {arm}: no trace"); continue
    win, ev = Counter(), Counter()
    for r in rows:
        for tok in (r.get("winning_path") or "").split("|"):
            if ":" not in tok: continue
            n, s = tok.rsplit(":", 1); ev[n] += 1
            if s in ("S", "R"): win[n] += 1
    print(f"  {arm}:")
    for n in names:
        flag = "" if win[n] else "   <== NEVER SUCCEEDS, result is uninterpretable"
        print(f"     {n:28s} S/R {win[n]:7d} / seen {ev[n]:7d}{flag}")
PYEOF

echo
"$PY" scripts/score_arms.py --control artifacts/eval/btf_control_vs_cutoff.csv \
    "artifacts/eval/btf_*_vs_cutoff.csv"
echo "[btfinal] done"
