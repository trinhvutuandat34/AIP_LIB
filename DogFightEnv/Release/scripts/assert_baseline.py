"""Preflight: refuse to run an eval unless the tree and binary on disk are the expected ones.

    python scripts/assert_baseline.py            # expect the CURRENT (rebuilt) tree
    python scripts/assert_baseline.py --expect fallback   # expect the c0aa0ff pre-spiral tree
    python scripts/assert_baseline.py --repair   # restore Rule_forTraining.xml from git HEAD

WHY THIS EXISTS (2026-09-09, and it already happened). `bt_rule_manager.activate_rule_xml()`
copies the chosen XML over `Rule_forTraining.xml` and restores it from a sibling `.xml.bak` in a
`finally`. That is safe once. It is NOT safe across a run that dies, or two runs that overlap:
the second run backs up the FIRST run's variant as if it were the original, and from then on the
"restore" writes a variant back over the shipped tree. Caught in the act -- the backup file was
byte-for-byte `bt_minimal.xml`, a tree with 14 of the 63 named nodes, and it was one process exit
away from becoming the shipped `Rule_forTraining.xml`.

The damage that would have done is silent and total: every later eval that does NOT pass
`--bt-rule-xml` reads whatever is in that file, so the standoff arms and the whole league matrix
would have been measured on a crippled tree and reported as configuration results. Per F70 a bad
tree does not announce itself -- it is caught in C++ and turned into commands that still answer
at 60 Hz.

So: assert before measuring. Cheap, and it converts a silent catastrophe into a loud refusal.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zlib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# The rebuilt tree that ships today (2026-09-08, commit c282d56).
CURRENT = {
    "AIP_BASE.dll": 1131281049,
    "AIP_BASE_target.dll": 1131281049,
}
# The pre-spiral fallback, commit c0aa0ff. Kept as the Track A safety net.
FALLBACK = {
    "AIP_BASE.dll": 4026508473,
    "AIP_BASE_target.dll": 4026508473,
}
# Named nodes in each baseline's Rule XML. These DIFFER, and hardcoding one number broke the
# fallback build on 2026-09-10: c0aa0ff predates Gate1_DefensiveSpiral and its two guards, so it
# carries 60 where the current tree carries 63. The guard refused a legitimate checkout and the
# trap correctly rolled it back -- a safe failure, but a failure. Keep these tied to the baseline.
# 2026-09-11: current drops 63 -> 61, Gate1_Notch and its HCA guard removed from the shipped
# tree. `--repair` restores from the Rule_real_eagle.xml twin whenever the twin matches this
# number, so it stays correct against an UNCOMMITTED tree; the git-HEAD blob is only the
# fallback, and HEAD still carries 63.
_NODE_COUNT = {"current": 61, "fallback": 60}


def crc(p: Path) -> int:
    return zlib.crc32(p.read_bytes())


def named_nodes(p: Path) -> int:
    import re
    b = re.sub(rb"<!--.*?-->", b"", p.read_bytes(), flags=re.S)
    return len(re.findall(rb'name="([^"]+)"', b))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", choices=["current", "fallback"], default="current")
    ap.add_argument("--repair", action="store_true",
                    help="restore Rule_forTraining.xml from git HEAD and delete stale .bak files")
    a = ap.parse_args()
    want = CURRENT if a.expect == "current" else FALLBACK
    bad = []

    for name, expected in want.items():
        p = _ROOT / name
        got = crc(p)
        ok = got == expected
        print(f"  {'OK ' if ok else 'BAD'}  {name:22s} crc {got:>11}  expected {expected:>11}")
        if not ok:
            bad.append(name)

    rule = _ROOT / "Rule_forTraining.xml"
    want_nodes = _NODE_COUNT[a.expect]
    n = named_nodes(rule)
    ok = n == want_nodes
    print(f"  {'OK ' if ok else 'BAD'}  {'Rule_forTraining.xml':22s} {n} named nodes, "
          f"expected {want_nodes} for the {a.expect} baseline")
    if not ok:
        bad.append("Rule_forTraining.xml")
        head = rule.read_text(encoding="utf-8", errors="replace").lstrip()[:80].replace("\n", " ")
        print(f"       ^ starts with: {head!r}")

    stale = list(_ROOT.glob("*.xml.bak"))
    for s in stale:
        m = named_nodes(s)
        flag = "OK " if m == want_nodes else "BAD"
        print(f"  {flag}  {s.name:22s} {m} named nodes  (a leftover backup restores THIS)")
        if m != want_nodes:
            bad.append(s.name)

    if a.repair:
        rel = "DogFightEnv/Release/Rule_forTraining.xml"
        blob = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=_ROOT.parent.parent)
        # git stores LF; the working tree is CRLF. Rule_real_eagle.xml is the clean CRLF twin.
        twin = _ROOT / "Rule_real_eagle.xml"
        rule.write_bytes(twin.read_bytes() if named_nodes(twin) == want_nodes else blob)
        for s in stale:
            s.unlink()
        print(f"\n  repaired Rule_forTraining.xml ({named_nodes(rule)} nodes), "
              f"removed {len(stale)} stale backup(s)")
        return 0

    if bad:
        print(f"\nFAIL: {', '.join(sorted(set(bad)))} is not the expected {a.expect} baseline.")
        print("Do NOT measure against this. Re-run with --repair, or check out the intended")
        print("revision, then re-run this check.")
        return 1
    print(f"\nOK: on the expected {a.expect} baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
