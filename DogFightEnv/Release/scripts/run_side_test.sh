#!/usr/bin/env bash
# DECISIVE side-symmetry test: forced-mirror paired mode, N=60 pairs per archetype.
#
# WHY THE FREE TEST IS NOT ENOUGH. Slicing existing runs by logged initial_side compares two
# DIFFERENT engagements, so a gap can be sampling noise. Worse, the side sequence is a function
# of the seed, so all five archetype columns share it -- pooling them looks like 300 samples but
# is ~100 independent draws, and the pooled z is inflated by roughly sqrt(3). Measured that way
# the lean is -9.8% at an apparent z=-1.72, i.e. not significant once the correlation is taken
# into account.
#
# The paired mode is different in kind: apply_match_scenario() draws the baseline heading BEFORE
# the side and positions do not depend on the side at all, so the same seed with --match-side +1
# and -1 is the SAME engagement mirrored. Any outcome gap beyond FDM determinism is real
# laterality, not sampling.
#
# Run against the shooters. sniper/bt_only sit at 95-98% and cannot express a side effect.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
"$PY" scripts/assert_baseline.py || { "$PY" scripts/assert_baseline.py --repair; \
  "$PY" scripts/assert_baseline.py || { echo "[side] baseline dirty, aborting"; exit 1; }; }
# BAND CORRECTED 2026-09-11 (organizer-confirmed). Was "1000,7700"/"150,280"; any CSV in
# artifacts/ older than this date was produced on that band and is NOT comparable across it.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"
"$PY" scripts/verify_side_symmetry.py --episodes 60 \
    --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
    --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 \
    2>&1 | tee artifacts/eval/SIDE_paired.log
echo "[side] done"
