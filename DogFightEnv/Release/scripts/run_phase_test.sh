#!/usr/bin/env bash
# Does a phase-exploiting opponent actually beat us, and does matching it help?
#
# THE QUESTION. The competition widens its scoring cone at 100 s and 150 s (Sec 6.2). Neither our
# controller nor the organizers' cutoff reads the clock -- the cutoff binary has no RunningTime,
# Phase or ElapsedTime symbol at all. The concern is that a real A-group team does, banking cheap
# Phase 2/3 damage late that a Phase-1-only pilot declines, and taking close timeouts with it.
# 43% of cutoff episodes end on the clock and a timeout is decided purely on damage differential,
# so the mechanism is real even if the opponent is hypothetical.
#
# THREE CELLS, and between them they answer it:
#   ship   vs phased   are we VULNERABLE to a phase exploiter?
#   phased vs phased   does the strategy beat itself (i.e. is the ship column just self-play noise)?
#   phased vs cutoff   does adopting it cost us anything against a Phase-1-only opponent?
#
# N=100 from the start. N=40 was shown on 2026-09-09 not to resolve differences of this size --
# standoff220 read +0.35 bo3 at N=40 and -0.07 at N=100 on the same harness.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
"$PY" scripts/assert_baseline.py || { "$PY" scripts/assert_baseline.py --repair; \
  "$PY" scripts/assert_baseline.py || { echo "[phase] baseline dirty, aborting"; exit 1; }; }
for pass in 1 2 3 4 5 6 7 8 9 10; do
  echo "[phase] ---- pass $pass ----"
  "$PY" scripts/league.py \
      --candidates ship_6000_120_deck standoff200_phased standoff200_gated \
      --archetypes phased cutoff \
      --episodes 100 --chunk-episodes 25 --jobs 3 --seed 20260910 \
      >> artifacts/eval/PHASE_TEST.log 2>&1
  grep -q "every pair has reached 100 episodes" artifacts/eval/PHASE_TEST.log && break
done
"$PY" scripts/matrix_report.py --candidates ship_6000_120_deck standoff200_phased standoff200_gated
echo "[phase] done"
