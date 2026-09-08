"""Build the two finals submission ZIPs, and refuse to build one that would be rejected.

    python scripts/package_release.py              # verify + build both ZIPs
    python scripts/package_release.py --no-smoke   # skip the flight check (iterating only)

REWRITTEN 2026-09-08. This script used to stage a MIRROR of `Release/` and zip it flat -- the
prelim's deliverable, where the submission was Python sources launched with
`python student\\my_submission.py`. The finals spec (COMPETITION_RULES.md Sec 7.1 / F75) makes
that non-compliant in two independent ways: the artifact must be a single `.exe`, and each ZIP
must contain **exactly two files at its root, no subfolders**, with README, source code and
라이브러리 폴더 explicitly banned. The old script emitted hundreds of files and a dozen folders.
The onedir/mirror logic is not patched here, it is gone; `git log` has it if it is ever wanted.

WHAT IT VERIFIES, AND WHY EACH GATE EXISTS

  1. The exe FLIES (`smoke_exe.py`). This is the only gate that separates a working submission
     from one flying a centred stick: per F70 a failed Rule-XML load inside the DLL is caught in
     C++, printed to `std::cout`, and turned into an all-zero `ControlValue` that the client
     forwards at 60 Hz forever. The previous version of this script "verified" the entry point by
     GREPPING ITS SOURCE TEXT for a substring -- which is exactly how a fatal `NameError` shipped
     in HEAD and went unnoticed (F69/F70). A gate that reads a file proves nothing; this one runs
     the artifact.
  2. The spawn preset is canonical (`spawn_preset_guard.py`). Any eval run rewrites
     `aircraft/f16/f16_init.xml` as a side effect (F57), and a drifted preset bakes the wrong
     initial conditions into the bundle.
  3. The exe was built from the CURRENT runtime assets. A stale exe next to a rebuilt DLL is the
     F8/F57/F59 shape of silent staleness, and nothing else in the pipeline would catch it.
  4. Filenames are pure ASCII and the displayed team name round-trips the wire packer. Two
     DISTINCT fields (F76): `SUBMISSION_NAME` = filenames, English; `TEAM_NAME` = the name shown
     on the engagement server, Korean, `_HeadOn` appended as a SUFFIX for the head-on model
     (`HeadOn_X` is explicitly rejected by the spec).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent                        # DogFightEnv/Release
_EXE_DIR = ROOT.parent / "submission_exe"  # scripts/build_exe.py's --distpath

sys.path.insert(0, str(ROOT))
from scripts.spawn_preset_guard import check as check_spawn_presets  # noqa: E402
from student.my_submission import SUBMISSION_NAME, TEAM_NAME  # noqa: E402

LIMIT_BYTES = 1024 ** 3

# Files whose mtime the exe must not be older than: if any of these changed after the build, the
# bundled copy is stale. `engine/` is walked rather than listed.
#
# `aircraft/` is DELIBERATELY ABSENT despite being bundled. Every eval run rewrites
# `aircraft/f16/f16_init.xml` as a side effect (F57 -- the FDM writes initial conditions back
# through it on reset), and `--restore` then bumps its mtime again. Including it here would make
# this gate fire after literally every eval, including when the file's CONTENT is canonical --
# and a gate that cries wolf is a gate people learn to ignore, which is how F69 shipped. The
# spawn preset is already checked byte-for-byte by `check_spawn_presets` above, which is the
# stronger check anyway: it compares content, not timestamps.
_ASSET_ROOTS = ("AIP_BASE.dll", "AIP_BASE_target.dll", "JSBSimAIPLib.dll",
                "Rule_forTraining.xml", "Rule.xml", "Rule_real_eagle.xml",
                "engine", "student", "src")

VARIANTS = (
    {"model": 1, "exe": f"{SUBMISSION_NAME}.exe",
     "zip": f"{SUBMISSION_NAME}_APTGC2026_main.zip", "team": TEAM_NAME},
    {"model": 2, "exe": f"{SUBMISSION_NAME}_headon.exe",
     "zip": f"{SUBMISSION_NAME}_APTGC2026_headon.zip", "team": f"{TEAM_NAME}_HeadOn"},
)


def _newest_asset_mtime() -> tuple[float, Path]:
    newest, where = 0.0, ROOT
    for name in _ASSET_ROOTS:
        p = ROOT / name
        if p.is_file():
            candidates = [p]
        elif p.is_dir():
            candidates = [f for f in p.rglob("*")
                          if f.is_file() and f.suffix not in (".pyc", ".pyo")]
        else:
            continue
        for f in candidates:
            m = f.stat().st_mtime
            if m > newest:
                newest, where = m, f
    return newest, where


def _check_names(problems: list[str]) -> None:
    for v in VARIANTS:
        for field in ("exe", "zip"):
            if not v[field].isascii():
                problems.append(f"{field} filename is not ASCII: {v[field]!r} "
                                "(the finals spec requires an English FILENAME)")
    # The displayed name is the other field entirely, and it must survive the wire packer.
    try:
        from dogfight.unreal.protocol import AIType, ClientJoinInfo, pack_client_join_info
        for v in VARIANTS:
            raw = v["team"].encode("utf-8")
            if len(raw) > 29:
                problems.append(f"displayed team name {v['team']!r} is {len(raw)} bytes; "
                                "protocol.py:109 truncates on a BYTE boundary at 29 and would "
                                "sever a Hangul character, emitting invalid UTF-8")
            # Round-trip through the REAL packer, not a re-implementation of it: pack, then
            # decode the 30-byte field back and require the exact string. That is what proves
            # the Korean name survives the wire, which is the whole point of the check.
            blob = pack_client_join_info(ClientJoinInfo(v["team"], AIType.RuleBased, 0))
            back = blob[4:34].rstrip(b"\x00").decode("utf-8", errors="replace")
            if back != v["team"]:
                problems.append(f"displayed team name does not round-trip the wire packer: "
                                f"sent {v['team']!r}, got back {back!r}")
    except (ImportError, AttributeError, TypeError) as exc:
        problems.append(f"could not exercise the wire packer to check the team name: {exc!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-smoke", action="store_true",
                    help="skip the flight check. NEVER pass this for a real submission -- it is "
                         "the only gate that can tell a working exe from a zeroed one (F70).")
    ap.add_argument("--out", default=str(_EXE_DIR))
    args = ap.parse_args()

    out = Path(args.out)
    problems: list[str] = []

    print(f"exe dir  : {out}")
    print(f"displayed: {TEAM_NAME!r} / {TEAM_NAME + '_HeadOn'!r}")
    print(f"filenames: {SUBMISSION_NAME}*\n")

    # --- gate 2: spawn preset ------------------------------------------------------------
    drift = check_spawn_presets(ROOT)
    if drift:
        problems.append(f"spawn preset drifted from canonical: {drift}. "
                        "Run `python scripts/spawn_preset_guard.py --restore` (F57).")
    else:
        print("[ok] spawn preset canonical")

    # --- gate 4: names -------------------------------------------------------------------
    _check_names(problems)
    if not problems:
        print("[ok] filenames ASCII, displayed names round-trip the wire packer")

    newest_asset, asset_path = _newest_asset_mtime()

    for v in VARIANTS:
        exe = out / v["exe"]
        if not exe.is_file():
            problems.append(f"{v['exe']} not built -- run `python scripts/build_exe.py` first")
            continue

        # --- gate 3: staleness -----------------------------------------------------------
        if exe.stat().st_mtime < newest_asset:
            problems.append(
                f"{v['exe']} is OLDER than {asset_path.relative_to(ROOT)} -- it was built from "
                "assets that have since changed. Rebuild before packaging.")
            continue
        print(f"[ok] {v['exe']:<32} {exe.stat().st_size/1e6:>6.1f} MB, newer than every asset")

        # --- gate 1: it flies ------------------------------------------------------------
        if args.no_smoke:
            print(f"     !! smoke SKIPPED for {v['exe']}")
        else:
            rc = subprocess.run([sys.executable, str(_HERE / "smoke_exe.py"), str(exe)]).returncode
            if rc != 0:
                problems.append(f"{v['exe']} FAILED the flight check -- see the output above")
                continue
            print(f"[ok] {v['exe']} passed the flight check")

    if problems:
        print("\nFAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1

    cfg = out / "config.json"
    if not cfg.is_file():
        print(f"\nFAIL: {cfg} missing -- scripts/build_exe.py writes it")
        return 1

    print()
    for v in VARIANTS:
        zpath = out / v["zip"]
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
            # EXACTLY two entries, both at the archive root, arcname'd explicitly so no
            # directory component can leak in from the source path.
            zf.write(out / v["exe"], v["exe"])
            zf.write(cfg, "config.json")
        with zipfile.ZipFile(zpath) as zf:
            names = zf.namelist()
        if names != [v["exe"], "config.json"]:
            print(f"FAIL: {zpath.name} contains {names}, expected exactly "
                  f"[{v['exe']!r}, 'config.json']")
            return 1
        size = zpath.stat().st_size
        if size > LIMIT_BYTES:
            print(f"FAIL: {zpath.name} exceeds 1 GB")
            return 1
        print(f"zip      : {zpath.name}  ({size/1e6:.1f} MB)  {names}")

    print("\nPASS -- both ZIPs hold exactly two root files, both exes fly, preset canonical.")
    print("Still needed by hand: 팀명_개인정보수집및활용동의서.zip (one signed PDF/HWP per member).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
