#!/usr/bin/env bash
# Pass 3: confirm and bracket the one arm that moved, then take it to the full roster.
#
# standoff220 came back +12.5 pp earned against the cutoff at N=40, which is only +1.14 SE.
# Three of this session's hypotheses already died on contact with a bigger sample, so this
# pass exists to give that number a chance to disappear before anything is adopted.
#
#   1. standoff220 to N=100 vs cutoff   -- same seed, so the first 40 episodes are the same
#                                          fights; this ADDS 60 rather than replacing them.
#   2. standoff150 / standoff300        -- 220 m was picked because the damage coefficient peaks
#                                          there, not because it was measured. Bracket it.
#   3. full five-archetype roster       -- via league.py, which handles the paired control and
#                                          the _is_selfplay()-corrected minimax floor.
#
# NOTE ON BT VARIANTS AND THE ROSTER. Do NOT put an XML variant on the roster this way. Both
# aircraft read one global Rule XML, so against the vptrack archetypes (mirror/sniper/aggressor)
# and against bt_only the change lands on BOTH sides and cancels exactly. `cutoff` is the only
# archetype that runs its own binary, so it is the only clean asymmetric BT test available
# without the scripts/setup_peer_bt.py rig.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"
# PREFLIGHT. activate_rule_xml() restores the shipped Rule XML from a sibling .bak, and that is
# not safe across a killed or overlapping run -- on 2026-09-09 the backup was found to be
# byte-for-byte bt_minimal.xml, one process exit from becoming the shipped tree. Every arm below
# that does NOT pass --bt-rule-xml reads that file, so a contaminated tree would be measured and
# reported as a configuration result, silently (F70). Refuse to start instead.
"$PY" scripts/assert_baseline.py || { echo "[preflight] baseline is not clean; repairing";   "$PY" scripts/assert_baseline.py --repair;   "$PY" scripts/assert_baseline.py || { echo "[preflight] STILL not clean, aborting"; exit 1; }; }

COMMON="--ownship-backend vptrack --target-backend cutoff --scenario-mode match_base
        --seed 20260909 --cutoff-action-repeat 6
        --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120
        --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000"

arm () {                        # arm <name> <episodes> <extra...>
  local name="$1" eps="$2"; shift 2
  local out="artifacts/eval/ablate_${name}_vs_cutoff.csv"
  local have=0
  [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  if [ "$have" -ge "$eps" ]; then echo "[p3] $name already at $have"; return; fi
  echo "[p3] === $name  ($have -> $eps) ==="
  "$PY" scripts/eval_vs_cutoff.py $COMMON --episodes "$eps" "$@" --out-csv "$out" \
      > "artifacts/eval/ablate_${name}.log" 2>&1
  echo "[p3] $name rc=$? rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 ))"
}

# 1+2. Confirm and bracket. standoff220 is rerun whole at 100 so every row shares one schema.
arm standoff220_n100 100 --ownship-vptrack-standoff-m 220
arm standoff150       40 --ownship-vptrack-standoff-m 150
arm standoff300       40 --ownship-vptrack-standoff-m 300

# 2b. STACKED ARMS. The knobs are independent by construction -- standoff is the aim point in
# the control law, deck-ttc is the hand-back guard, and they touch different code paths -- so if
# both are individually non-negative the combination is the natural candidate. Run them together
# rather than assuming additivity: the deck guard returns None (hands to the BT) and the standoff
# only acts while the control law HAS the stick, so they can interact through that handover.
arm standoff220_deckttc 40 --ownship-vptrack-standoff-m 220 --ownship-vptrack-deck-ttc 5

# 3. Full roster, control included so league scores both under the corrected scorer.
echo "[p3] === full roster ==="
"$PY" scripts/league.py --candidates standoff220_deck ship_6000_120_deck \
  --archetypes cutoff aggressor sniper mirror bt_only \
  --episodes 40 --chunk-episodes 40 --jobs 3 --seed 20260909 \
  > artifacts/eval/ROSTER_standoff_0909.log 2>&1
echo "[p3] roster rc=$?"
echo "[p3] all done"
