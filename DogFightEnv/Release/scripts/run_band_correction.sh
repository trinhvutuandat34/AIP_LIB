#!/usr/bin/env bash
# Re-measure on the ORGANIZER-CONFIRMED spawn band, and answer the three things that keep
# Model 1 from being competitively settled. 2026-09-11.
#
# WHY SEQUENTIAL. The first version ran phase 1 two arms at a time and was MEASURED at 62 s
# per episode aggregate, against ~34 s sequential (the old single-arm baseline, adjusted for
# today's ~16% longer episodes). Two-way parallelism is more than 2x WORSE on this machine --
# the arms contend rather than scale. Running everything one at a time also removes the
# Rule-XML hazard by construction: activate_rule_xml copies a variant over the single
# workspace Rule_forTraining.xml, and the corruption scripts/assert_baseline.py's header
# documents needs two runs overlapping. One at a time, that cannot happen.
#
# THE QUEUE IS IN VALUE ORDER. If it has to be cut short, cut from the bottom.
#
#   PHASE A (400 eps)  Does removing Gate1_Notch still win on the correct band? It shipped on
#                      +6.5 pp pooled (~1.3 SE) measured entirely on the wrong one. This is
#                      the only thing here that can change the artifact: if it loses, revert
#                      commit 5147886, restore _NODE_COUNT to 63, rebuild, repackage.
#
#   PHASE B (180 eps)  The hard deck, measured where it actually applies. The real spawn floor
#                      is 609.6 m and SHIP_HARD_DECK_M is 1,000 m, so ~4.6% of rounds begin
#                      with _tracking_stick returning None and the BT flying the merge alone.
#                      Sampling that from the full band gives ~5 episodes per arm -- useless.
#                      So this phase CLAMPS the band to 609.6-1000 m and every episode is the
#                      case of interest. It is a CONDITIONAL measurement, not a match
#                      simulation: read it as "given a sub-deck spawn, which setting is best",
#                      then weight it by the 4.6% of rounds that actually start there.
#
#   PHASE C (220 eps)  Two things the band change legitimately re-opens.
#                      C1: deck 600 on the FULL band, to check the deck change does not hurt
#                          the other ~95%. The deck also fires on in-flight descents, not only
#                          at spawn, so a conditional win in phase B is not sufficient.
#                      C2: the engagement envelope. F80 closed LOS at 120 ("stop sweeping the
#                          envelope") -- but it closed it on the WRONG BAND, and the speed band
#                          moved UP by 50 m/s, which changes corner speed and turn radius
#                          directly. That verdict is re-based, so 90 and 140 get one honest
#                          re-test each against the phase-A control. If 120 still wins, F80
#                          stands and the envelope is closed for good.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
CTL_XML=experiments/rule_variants/bt_notch_restored.xml

"$PY" scripts/assert_baseline.py || { echo "[band] baseline dirty, aborting"; exit 1; }
[ -f "$CTL_XML" ] || { echo "[band] missing control XML $CTL_XML"; exit 1; }

# The corrected band. 2000 ft = 609.6 m, 30000 ft = 9144 m. Phase B overrides ALT.
BAND_ALT="609.6,9144"
BAND_SPD="200,300"

arm () {   # arm <name> <episodes> <seed> [extra flags...]
  local name="$1" eps="$2" seed="$3"; shift 3
  local out="artifacts/eval/band_${name}_vs_cutoff.csv"
  local have=0; [ -f "$out" ] && have=$(( $(wc -l < "$out") - 1 ))
  [ "$have" -ge "$eps" ] && { echo "[band] $name already at $have"; return; }
  echo "[band] === $name  n=$eps seed=$seed  alt=[$BAND_ALT] spd=[$BAND_SPD] === $(date +%H:%M)"
  DOGFIGHT_MATCH_ALTITUDE_RANGE_M="$BAND_ALT" \
  DOGFIGHT_MATCH_SPEED_RANGE_MPS="$BAND_SPD" \
  "$PY" scripts/eval_vs_cutoff.py \
    --ownship-backend vptrack --target-backend cutoff --scenario-mode match_base \
    --episodes "$eps" --seed "$seed" --cutoff-action-repeat 6 \
    --ownship-vptrack-range-m 6000 --ownship-vptrack-throttle 1 \
    "$@" --out-csv "$out" > "artifacts/eval/band_${name}.log" 2>&1
  echo "[band] $name rc=$? rows=$(( $(wc -l < "$out" 2>/dev/null || echo 1) - 1 )) $(date +%H:%M)"
  "$PY" scripts/assert_baseline.py > /dev/null || echo "[band] !! BASELINE DIRTY after $name"
}

SHIP="--ownship-vptrack-los-deg 120 --ownship-vptrack-hard-deck 1000"

echo "[band] ########## PHASE A -- does no_notch survive the correct band? ##########"
arm nonotch_s1 100 20260911 $SHIP
arm ctl63_s1   100 20260911 $SHIP --bt-rule-xml "$CTL_XML"
arm nonotch_s2 100 20260912 $SHIP
arm ctl63_s2   100 20260912 $SHIP --bt-rule-xml "$CTL_XML"

echo; echo "[band] === A: seed 20260911 ==="
"$PY" scripts/score_arms.py --control artifacts/eval/band_ctl63_s1_vs_cutoff.csv \
  artifacts/eval/band_nonotch_s1_vs_cutoff.csv
echo; echo "[band] === A: seed 20260912 (independent draw) ==="
"$PY" scripts/score_arms.py --control artifacts/eval/band_ctl63_s2_vs_cutoff.csv \
  artifacts/eval/band_nonotch_s2_vs_cutoff.csv

echo; echo "[band] ########## PHASE B -- sub-deck spawns ONLY (609.6-1000 m) ##########"
BAND_ALT="609.6,1000"
arm sub_deck1000 60 20260913 --ownship-vptrack-los-deg 120 --ownship-vptrack-hard-deck 1000
arm sub_deck600  60 20260913 --ownship-vptrack-los-deg 120 --ownship-vptrack-hard-deck 600
arm sub_deck0    60 20260913 --ownship-vptrack-los-deg 120 --ownship-vptrack-hard-deck 0
BAND_ALT="609.6,9144"

echo; echo "[band] === B: given a sub-deck spawn, which deck setting wins? ==="
"$PY" scripts/score_arms.py --control artifacts/eval/band_sub_deck1000_vs_cutoff.csv \
  artifacts/eval/band_sub_deck600_vs_cutoff.csv artifacts/eval/band_sub_deck0_vs_cutoff.csv

echo; echo "[band] ########## PHASE C -- collateral check, then the re-opened envelope #####"
arm deck600_full 100 20260911 --ownship-vptrack-los-deg 120 --ownship-vptrack-hard-deck 600
arm los90        60  20260911 --ownship-vptrack-los-deg 90  --ownship-vptrack-hard-deck 1000
arm los140       60  20260911 --ownship-vptrack-los-deg 140 --ownship-vptrack-hard-deck 1000

echo; echo "[band] === C: everything against the shipped config on the correct band ==="
"$PY" scripts/score_arms.py --control artifacts/eval/band_nonotch_s1_vs_cutoff.csv \
  artifacts/eval/band_deck600_full_vs_cutoff.csv \
  artifacts/eval/band_los90_vs_cutoff.csv artifacts/eval/band_los140_vs_cutoff.csv

echo; echo "[band] === the sub-deck subset inside the full-band arms (cross-check) ==="
"$PY" scripts/band_subset_report.py
echo "[band] done $(date +%H:%M)"
