#!/usr/bin/env bash
# Build a SHIPPABLE artifact from the c0aa0ff pre-spiral tree, without disturbing the working one.
#
# WHY THIS IS NEEDED AT ALL. c0aa0ff is described everywhere as "the fallback", but no artifact
# for it exists: both ZIPs in submission_exe/ were packaged from the CURRENT DLL (crc32
# 1131281049). Today the fallback is a git revision, not something anyone can submit. This turns
# it into a real, gated ZIP so there is a known-good option that does not depend on the candidate
# search finishing.
#
# WHY IT CANNOT RUN CONCURRENTLY WITH EVALS. It checks c0aa0ff's DLL and Rule XMLs into the live
# Release/ tree, because that is what build_exe.py packages. Any eval running at the same time
# would silently be measured on the WRONG binary -- exactly the class of failure that poisoned
# Rule_forTraining.xml on 2026-09-09. Run it only in a gap.
#
# RESTORE IS TRAPPED. If this script dies at any point -- kill, error, Ctrl-C -- the trap puts the
# current tree back and re-verifies the checksum. A half-finished run must never leave the
# repository on the fallback binary, because the next eval would inherit it without noticing.
set -u
cd "$(dirname "$0")/.."
PY="C:/Users/user/.conda/envs/aip/python.exe"
REPO="$(cd ../.. && pwd)"
FILES="DogFightEnv/Release/AIP_BASE.dll DogFightEnv/Release/AIP_BASE_target.dll
       DogFightEnv/Release/Rule_forTraining.xml DogFightEnv/Release/Rule_real_eagle.xml"
OUT="../submission_fallback"

restore () {
  echo "[fallback] restoring the working tree to HEAD"
  ( cd "$REPO" && git checkout HEAD -- $FILES )
  "$PY" scripts/assert_baseline.py --expect current \
    && echo "[fallback] working tree verified back on the current baseline" \
    || echo "[fallback] !! RESTORE FAILED -- do NOT run any eval until this is fixed"
}
trap restore EXIT INT TERM

echo "[fallback] staging c0aa0ff binaries into the live tree"
( cd "$REPO" && git checkout c0aa0ff -- $FILES ) || { echo "[fallback] checkout failed"; exit 1; }
"$PY" scripts/assert_baseline.py --expect fallback || { echo "[fallback] staged tree is not c0aa0ff"; exit 1; }

# build_exe.py has NO --out-dir: it writes into submission_exe/, which currently holds the only
# gated artifact we possess. Building in place would overwrite the very thing this script exists
# to protect. So the current artifact is moved aside first and put back by the trap, and only
# then is the fallback build promoted to its own directory.
STASH="../submission_exe_current"
promote () {
  if [ -d "$STASH" ]; then
    echo "[fallback] restoring the current submission artifact"
    mkdir -p ../submission_exe
    cp -f "$STASH"/* ../submission_exe/ 2>/dev/null || true
    rm -rf "$STASH"
  fi
}
trap 'promote; restore' EXIT INT TERM

rm -rf "$STASH"; mkdir -p "$STASH"
cp -f ../submission_exe/* "$STASH"/ 2>/dev/null || true
echo "[fallback] current artifact stashed to $STASH ($(ls "$STASH" | wc -l) files)"

echo "[fallback] building from the c0aa0ff tree"
"$PY" scripts/build_exe.py 2>&1 | tail -20

mkdir -p "$OUT"
for f in ../submission_exe/*; do
  case "$f" in *.exe|*.zip|*config.json) cp -f "$f" "$OUT"/ ;; esac
done
rm -f ../submission_exe/*.exe ../submission_exe/*.zip 2>/dev/null || true
echo "[fallback] fallback artifacts:"; ls -la "$OUT" 2>/dev/null
echo "[fallback] done"
