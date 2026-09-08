"""Detect and repair spawn-preset drift in `aircraft/f16/f16_init.xml` (COMPETITION_PLAN F57).

WHY THIS EXISTS. `aircraft/f16/f16_init.xml` is a **protected runtime asset that the simulator
rewrites on you**, and the two facts together make a trap that no local test catches.

  1. `JSBSimWrapper.Fighter.__init__` (JSBSimWrapper.py ~line 117) uses this file as the CHANNEL
     for handing initial conditions to the native DLL: it parses the XML, overwrites
     latitude/longitude/altitude/psi/phi/gamma/vt with the requested spawn, writes it back, and
     only then calls `JSBSim.Init()`. So **every episode of every local eval leaves its own spawn
     in this file.** This is not JSBSim writing back a result -- it is how the input gets in --
     which is why the fix is not "stop the write". The write is load-bearing.
  2. The file is therefore left holding whatever the LAST episode asked for. F57 caught it
     drifting 15000.047 ft / 656.168 ft/s / psi 103.7 deg -> 22970.531 ft / 969.940 ft/s /
     psi 180.0 deg, i.e. almost exactly back to the pre-F7 numbers that F7 had deliberately
     corrected to the confirmed competition preset.

WHAT GOES WRONG IF NOBODY WATCHES IT. Anyone who runs an eval and then runs
`scripts/package_release.py` ships a spawn preset that is NOT the confirmed one, and `git status`
shows a protected runtime asset as modified for reasons nobody remembers a week later. This is a
**reproducibility trap, not a compliance one** -- COMPETITION_RULES.md Sec 8 protects a runtime
asset's name and location, not its content, so editing the content is rules-legal. It is still
the kind of silent state change that invalidates a measurement campaign.

WHY AN EXACT-BYTES CHECK. The drift is sometimes large (a different altitude and heading) and
sometimes a few metres of jitter. Both are worth catching, because the goal is a working tree
that is unambiguously clean before a measurement run is trusted or a package is built, and
`--restore` makes clearing it a single command. A tolerance would only make "clean" fuzzy.

WHY ONLY THE F16. `Fighter.__init__` sets `self._fighterTypeName` only in the `fighterType ==
0x01` branch, so line 118 raises `AttributeError` for anything else -- the f15 and fa50 init
files are unreachable through this path and have never drifted. If a second airframe is ever
enabled, add its canonical block to CANONICAL below rather than widening the check to files
whose canonical content nobody has verified.

USAGE
    python scripts/spawn_preset_guard.py               # check, exit 1 on drift
    python scripts/spawn_preset_guard.py --restore     # rewrite to canonical, then re-check
    python scripts/spawn_preset_guard.py --root D:\pkg # check a staged package instead

Exit 0 = every guarded preset matches canonical.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The confirmed competition spawn preset (COMPETITION_PLAN.md F7: 15000 ft / 200 m/s, where
# 200 m/s == 656.168 ft/s exactly). Stored as lines rather than one blob so the CRLF endings and
# the absent trailing newline -- both of which the file really has, and which a careless rewrite
# would change -- are explicit rather than accidental.
_F16_INIT_LINES = [
    '<initialize name="cruise">',
    '  <altitude unit="FT">15000.04666279369</altitude>',
    '  <vt unit="FT/SEC">656.168</vt>',
    '  <gamma unit="DEG">0.0</gamma>',
    '  <latitude unit="DEG">37.91085471086443</latitude>',
    '  <longitude unit="DEG">128.18073876934287</longitude>',
    '  <phi unit="DEG">0.0</phi>',
    '  <psi unit="DEG">103.73916652989953</psi>',
    '  <theta unit="DEG">0</theta>',
    '  <beta unit="DEG">0</beta>',
    '  <alpha unit="DEG">0</alpha>',
    '</initialize>',
]

CANONICAL: dict[str, bytes] = {
    "aircraft/f16/f16_init.xml": "\r\n".join(_F16_INIT_LINES).encode("utf-8"),
}


def _summarise(blob: bytes) -> str:
    """One-line digest of the fields that actually identify a spawn, for the drift report."""
    import re

    out = []
    for tag in ("altitude", "vt", "latitude", "longitude", "psi"):
        m = re.search(rf"<{tag}[^>]*>([^<]*)</{tag}>", blob.decode("utf-8", "replace"))
        if m:
            out.append(f"{tag}={m.group(1)}")
    return "  ".join(out) if out else "<unparseable>"


def check(root: Path) -> list[str]:
    """Return a list of human-readable problems; empty means every preset is canonical."""
    problems = []
    for rel, want in CANONICAL.items():
        path = root / rel
        if not path.exists():
            problems.append(f"{rel}: MISSING")
            continue
        got = path.read_bytes()
        if got != want:
            problems.append(
                f"{rel}: DRIFTED ({len(got)} bytes, expected {len(want)})\n"
                f"      found    {_summarise(got)}\n"
                f"      expected {_summarise(want)}"
            )
    return problems


def restore(root: Path) -> list[str]:
    """Rewrite every guarded preset to canonical. Returns the paths actually changed."""
    changed = []
    for rel, want in CANONICAL.items():
        path = root / rel
        if not path.exists() or path.read_bytes() != want:
            path.write_bytes(want)
            changed.append(rel)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="Release root to inspect (default: this checkout)")
    ap.add_argument("--restore", action="store_true",
                    help="rewrite drifted presets to the confirmed competition values")
    ap.add_argument("--quiet", action="store_true", help="only print on failure")
    args = ap.parse_args()

    root = args.root.resolve()

    if args.restore:
        changed = restore(root)
        if changed:
            for rel in changed:
                print(f"  [RESTORED] {rel}")
        elif not args.quiet:
            print("  nothing to restore -- already canonical")

    problems = check(root)
    if problems:
        print("FAIL: spawn preset drifted (COMPETITION_PLAN.md F57)")
        for p in problems:
            print(f"  - {p}")
        print("\n  Fix: python scripts/spawn_preset_guard.py --restore")
        print("  Cause: a local eval left its last episode's spawn in the file. Expected after"
              " any run; just restore before committing or packaging.")
        return 1

    if not args.quiet:
        print(f"PASS -- spawn presets canonical ({len(CANONICAL)} checked, root {root})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
