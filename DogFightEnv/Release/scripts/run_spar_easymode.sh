#!/usr/bin/env bash
# Spar against 이준서's reconstructed cutoff DLL ("EasyMode / Cut Off Model V.Easy"), 2026-09-11.
#
# PROVENANCE, AND THE LINE THIS DOES NOT CROSS. The DLL is a reconstruction of the organizers'
# `unreal_bt_client.exe`, built from a Ghidra decompilation of that binary, plus a ground-crash
# guard (`PreventLandCrash`). His own validation: 7 recorded sessions, 16,421 frame pairs, zero
# mismatch against the exe on all four channels (max 5e-5, float rounding).
# **Nothing reverse-engineered goes into the submission.** This is a sparring partner only. The
# DLL and its tree stay OUTSIDE the repo; nothing here writes to Release/.
#
# HOW THE ISOLATION WORKS, and why no repo file changes.
#   * `AIPilot.__init__` does `os.path.join(lib_path, filename)`, and os.path.join returns the
#     second argument when it is absolute -- so an absolute --target-bt-dll loads from anywhere.
#   * The DLL reads its Rule XML from its OWN directory, so it uses its own tree
#     (Rule_forTraining.xml, the one that was embedded in the exe) and never reads ours.
#   * --bt-rule-xml is deliberately NOT passed. Passing it would make bt_rule_manager copy a
#     variant over the workspace Rule_forTraining.xml; omitting it means source == target and
#     activate_rule_xml yields without writing anything.
#
# DO NOT RUN THIS WHILE run_band_correction.sh IS GOING. Its ctl63 arms rewrite the workspace
# Rule XML that OUR ownship reads, so an overlapping match would silently use whichever tree
# happened to be in place.
#
# READ THE RESULT WITH THIS CAVEAT. Over the wire the real cutoff exe only ever sees position,
# attitude, speed and force side (`StepWithPlaneData`). This DLL, run as a local `bt` target,
# gets the full local FDM state every tick -- so it is ADVANTAGED relative to the exe it
# reproduces. A worse result for us here is therefore NOT evidence that PreventLandCrash made
# the opponent stronger; the input asymmetry alone could explain it.
# See scripts/cutoff_provider.py's "Approximate, and it matters when reading results".
#
# WHAT WE ACTUALLY WANT OUT OF IT:
#   1. Does the target self-crash rate collapse? Against the real exe it is 12-16% of episodes,
#      and every one of those scores as a DRAW, which suppresses our win rate rather than
#      inflating it. PreventLandCrash should drive it toward 0.
#   2. With those draws removed, does our measured win rate move the way the arithmetic says it
#      should? Excluding self-crash episodes, the shipped tree scores ~45% vs ~40% overall.
#   3. An independent check on his "reproduces the exe" claim, at the level of aggregate
#      outcomes rather than per-frame commands.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
DLL="C:/Users/user/AppData/Local/Temp/claude/D--aip-lib/b5150d8f-ee17-44a9-8215-a2a0051ea64a/scratchpad/junseo/EasyMode_DLL/AIP_DCS.dll"
EPS=60
SEED=20260911

[ -f "$DLL" ] || { echo "[spar] DLL not found: $DLL"; exit 1; }
"$PY" scripts/assert_baseline.py || { echo "[spar] baseline dirty -- is the band queue still running?"; exit 1; }

# Same corrected band as every post-2026-09-11 arm.
export DOGFIGHT_MATCH_ALTITUDE_RANGE_M="609.6,9144"
export DOGFIGHT_MATCH_SPEED_RANGE_MPS="200,300"

R="$(pwd)"
SANDBOX="$(dirname "$DLL")"
OUT="$R/artifacts/eval/spar_easymode_dll.csv"

# WE MUST RUN FROM THE SANDBOX, and that is a finding in itself. His DLL resolves its Rule XML
# from the CURRENT WORKING DIRECTORY (verified: chdir to the sandbox and CreateBehaviorTree
# prints "Behavior Tree XML : ./Rule_forTraining.xml"), whereas the original it reconstructs
# uses GetThisModuleDirectory() -- CPPBehaviorTree.cpp:142, hardcoded filename, working
# directory ignored because JSBSim chdir()s away. Run from Release/ his DLL reads OUR Rule.xml,
# whose node vocabulary its library does not have, and CreateBehaviorTree throws.
#
# Running from the sandbox is safe for our side because every one of our loaders is
# module-relative: AIPilot joins lib_path, JSBSimWrapper loads from its own directory, and
# activate_rule_xml takes an explicit root. JSBSim is the exception -- it reads scripts/*.xml,
# aircraft/ and engine/ from the CWD -- so the sandbox carries COPIES of those (257 KB total).
# Copies, never moves: the originals stay put, and a spawn-preset drift lands on the copy
# instead of on ours.
[ -f "$SANDBOX/aircraft/f16/f16.xml" ] || cp -r "$R/aircraft" "$R/engine" "$SANDBOX/" 2>/dev/null
mkdir -p "$SANDBOX/scripts"
for f in f15_cruise.xml f16_cruise.xml fa50_cruise.xml f16_cruise; do
  [ -f "$SANDBOX/scripts/$f" ] || cp "$R/scripts/$f" "$SANDBOX/scripts/" 2>/dev/null
done

echo "[spar] === shipped config vs EasyMode DLL  n=$EPS seed=$SEED === $(date +%H:%M)"
( cd "$SANDBOX" && "$PY" "$R/scripts/eval_v5_vs_bt.py" --scenario-mode match_base \
  --episodes "$EPS" --seed "$SEED" \
  --ownship-backend vptrack --ownship-vptrack-range-m 6000 --ownship-vptrack-los-deg 120 \
  --ownship-vptrack-throttle 1 --ownship-vptrack-hard-deck 1000 \
  --target-backend bt --target-bt-dll "$DLL" \
  --out-csv "$OUT" ) > artifacts/eval/spar_easymode_dll.log 2>&1
echo "[spar] rc=$? rows=$(( $(wc -l < "$OUT" 2>/dev/null || echo 1) - 1 )) $(date +%H:%M)"

"$PY" scripts/assert_baseline.py || echo "[spar] !! BASELINE DIRTY -- investigate before trusting anything"

echo; echo "[spar] === did PreventLandCrash remove the opponent's self-kills? ==="
"$PY" - <<'PYEOF'
import csv, collections, os
rows = {}
for label, f in (("vs real cutoff exe", "artifacts/eval/band_nonotch_s1_vs_cutoff.csv"),
                 ("vs EasyMode DLL",    "artifacts/eval/spar_easymode_dll.csv")):
    if not os.path.exists(f):
        print(f"{label:22s} -- no CSV"); continue
    r = list(csv.DictReader(open(f)))
    if not r: continue
    c = collections.Counter(x["end_condition"] for x in r)
    key = "phased_outcome" if "phased_outcome" in r[0] else "outcome"
    crash = c.get("target altitude below min", 0)
    rest = [x for x in r if x["end_condition"] != "target altitude below min"]
    w = sum(1 for x in r if x[key] == "win")
    wr = sum(1 for x in rest if x[key] == "win")
    print(f"{label:22s} n={len(r):3d}  target self-crash {crash:3d} ({100*crash/len(r):4.1f}%)  "
          f"win {w:3d} ({100*w/len(r):4.1f}%)  win-excl-selfcrash {wr}/{len(rest)} "
          f"({100*wr/max(1,len(rest)):4.1f}%)")
PYEOF
echo "[spar] done $(date +%H:%M)"
