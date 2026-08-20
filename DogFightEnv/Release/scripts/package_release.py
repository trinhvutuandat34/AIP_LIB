"""Build the submission package: compliant, complete, and under the 1 GB limit.

WHY THIS EXISTS. Two independent ways to fail on submission day, both silent:

  1. SIZE. `Release/artifacts/` is ~11.7 GB on this box (curriculum 10.3 GB + ray_results
     1.25 GB) -- 12x the organizers' 1 GB limit on its own. Everything the submission actually
     NEEDS totals ~40 MB. None of `artifacts/` is required: `student/my_submission.py` ships
     `MODE = "vptrack"` with `BUNDLE_DIR = None`, so no RL bundle is loaded at all.

  2. COMPLIANCE. COMPETITION_RULES.md Sec8 forbids RENAMING, MOVING or DELETING the runtime
     assets. A hand-pruned zip that drops `Rule.xml` or `engine/` because "we don't seem to use
     it" is a rules violation that no local test would catch. So this script does not just
     exclude -- it ASSERTS every protected asset is present at its exact path afterwards, and
     refuses to produce a package if one is missing.

It also guards the failure this project has already had once, in a different form: shipping code
whose fix is absent. It verifies `student/live_frame_fix.py` is present and imported by both
entry points, because without it the native BT sees a ~110,700x wrong range on the live path
(see LIVE_INFERENCE_FRAME_BUGS.md and scripts/verify_live_frame_fix.py).

USAGE
    python scripts/package_release.py                    # stage + verify, report size
    python scripts/package_release.py --zip              # also write submission_<team>.zip
    python scripts/package_release.py --out D:\pkg       # choose the staging directory

Exit 0 = staged, complete, compliant and under the limit.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT_BYTES = 1024 ** 3  # 1 GB

# Protected runtime assets: must exist, at exactly these names/locations, in the package.
# Source: COMPETITION_RULES.md Sec8 (and the editing-boundaries table in CLAUDE.md).
PROTECTED = [
    "AIP_BASE.dll",
    "AIP_BASE_target.dll",
    "JSBSimAIPLib.dll",
    "Rule_forTraining.xml",
    "Rule.xml",
    "aircraft",
    "engine",
    "scripts/f15_cruise.xml",
    "scripts/f16_cruise.xml",
    "scripts/fa50_cruise.xml",
]

# Needed to actually run the submission.
REQUIRED = [
    "student/my_submission.py",
    "student/live_frame_fix.py",
    "student/controller_providers.py",
    "run_unreal_inference.py",
    "src/dogfight",
]

# Directory names excluded wholesale, at any depth.
EXCLUDE_DIRS = {
    "artifacts",        # 11.7 GB of training/eval output; none of it is needed to run
    "logs",             # captured packet dumps + run logs
    "ray_results",
    "__pycache__",
    ".git",
    ".vs",
    ".vscode",
    ".ipynb_checkpoints",
    "bt_peer",          # local measurement rig (its own docstring: not part of a submission)
}


def _is_disposable_dll(name: str) -> bool:
    """Experiment/backup DLL variants we added -- NOT protected assets, and ~38 MB of noise.

    Protected names are matched exactly in PROTECTED; anything like AIP_BASE_gatetrace.dll or
    AIP_BASE.dll.bak_aug03build is ours, is not referenced by the submission, and is excluded.
    """
    low = name.lower()
    if low in {"aip_base.dll", "aip_base_target.dll", "jsbsimaiplib.dll"}:
        return False
    if ".bak" in low:
        return True
    return low.startswith("aip_base") and low.endswith(".dll")


def should_skip(rel: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return True
    name = rel.name
    if name.endswith((".pyc", ".pyo")):
        return True
    if name.endswith(".dll") and _is_disposable_dll(name):
        return True
    if ".bak" in name.lower():
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT.parent / "submission_package"))
    ap.add_argument("--zip", action="store_true")
    ap.add_argument("--force", action="store_true", help="overwrite an existing staging dir")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        if not args.force:
            print(f"FAIL: {out} already exists. Pass --force to overwrite.")
            return 1
        shutil.rmtree(out)
    out.mkdir(parents=True)

    copied = skipped_bytes = total = 0
    for src in ROOT.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(ROOT)
        try:
            size = src.stat().st_size
        except OSError:
            continue
        if should_skip(rel):
            skipped_bytes += size
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
        total += size

    print(f"staged   : {out}")
    print(f"files    : {copied:,}")
    print(f"size     : {total/1024/1024:.1f} MB   (limit {LIMIT_BYTES/1024/1024:.0f} MB)")
    print(f"excluded : {skipped_bytes/1024/1024/1024:.2f} GB")
    print()

    problems = []

    print("protected runtime assets (COMPETITION_RULES.md Sec8 -- must not be renamed/moved/deleted)")
    for rel in PROTECTED:
        ok = (out / rel).exists()
        print(f"  [{'OK' if ok else 'MISSING'}] {rel}")
        if not ok:
            problems.append(f"protected asset missing: {rel}")

    print()
    print("required to run")
    for rel in REQUIRED:
        ok = (out / rel).exists()
        print(f"  [{'OK' if ok else 'MISSING'}] {rel}")
        if not ok:
            problems.append(f"required file missing: {rel}")

    # The live frame fix must not merely exist -- both entry points must import it, or the
    # live path silently reverts to the broken geometry.
    print()
    print("live-path frame fix wired in")
    for rel in ("student/my_submission.py", "run_unreal_inference.py"):
        p = out / rel
        ok = p.exists() and "live_frame_fix" in p.read_text(encoding="utf-8", errors="replace")
        print(f"  [{'OK' if ok else 'FAIL'}] {rel} imports live_frame_fix")
        if not ok:
            problems.append(f"{rel} does not reference live_frame_fix")

    print()
    if total > LIMIT_BYTES:
        problems.append(f"package is {total/1024/1024:.1f} MB, over the 1 GB limit")

    if problems:
        print("FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1

    if args.zip:
        try:
            from student.my_submission import TEAM_NAME
        except Exception:
            TEAM_NAME = "submission"
        zpath = out.parent / f"submission_{TEAM_NAME}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in out.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(out))
        zmb = zpath.stat().st_size / 1024 / 1024
        print(f"zip      : {zpath}  ({zmb:.1f} MB)")
        if zpath.stat().st_size > LIMIT_BYTES:
            print("FAIL: zip exceeds 1 GB")
            return 1

    print(f"PASS -- {total/1024/1024:.1f} MB, all protected assets present, frame fix wired in.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
