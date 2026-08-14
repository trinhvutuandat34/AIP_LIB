"""Give the two aircraft DIFFERENT rule XMLs, so a BT change can finally be A/B'd locally.

THE DEADLOCK THIS BREAKS. COMPETITION_PLAN.md 4.1 F1-BLIND recorded that a BT change cannot be
scored here: vs our own BT is saturated (73.3 %, zero losses) and self-play is symmetric, because
both DLLs sit in DogFightEnv/Release/ and therefore read the SAME Rule_forTraining.xml. Every
merge/tactics change since -- Gate2_BeamMerge included -- had to be adopted "on mechanism", with
no win rate behind it.

THE MECHANISM. Measured 2026-08-11: the DLL resolves its rule file relative to ITS OWN on-disk
location (the GetModuleFileName fix in Sec 5.1), not relative to cwd or to Release/. Proof, run
through the real eval path: with a DLL copy in a subdirectory and NO Rule_forTraining.xml beside
it, exactly one tree initialised (ours) and one reported "Behavior Tree Initialization Failed"
(the peer); with the XML restored, both initialised. So a copy of the DLL in its own folder reads
its own rules, and the aircraft can be given different trees.

Windows loads a DLL once per resolved PATH, so the copy also gets its own static state -- which
is the same reason AIP_BASE.dll and AIP_BASE_target.dll are two files rather than one.

COMPLIANCE. This only ADDS files in a new directory. It never renames, moves or deletes a runtime
asset, which is the actual rule (COMPETITION_RULES.md Sec 8); the originals are untouched. The
peer directory is a local measurement rig and is gitignored -- it is not part of a submission.

USAGE
    # peer runs the rule file as of some git revision (e.g. before a change landed)
    python scripts/setup_peer_bt.py --from-git dc3c46c^
    # or peer runs an explicit XML
    python scripts/setup_peer_bt.py --xml experiments/rule_variants/no_beam_merge.xml
    # then, in any eval, point the TARGET at it:
    python scripts/eval_v5_vs_bt.py --ownship-backend vptrack --target-backend vptrack \\
        --scenario-mode match_base --episodes 30 \\
        --target-bt-dll bt_peer/AIP_BASE_target.dll

Our side keeps reading Release/Rule_forTraining.xml, so do NOT pass --bt-rule-xml as well:
bt_rule_manager.activate_rule_xml() copies over that live file and would change our side too.

THIS RIG WORKS. It is the ONLY valid instrument for scoring a BT change (2026-08-13).

    An earlier revision of this docstring carried a large "KNOWN BROKEN BEYOND EPISODE 0" warning
    from COMPETITION_PLAN 4.1 F18. THAT WARNING WAS WRONG and is removed. F18 observed that three
    separate peer tree changes each moved only episode 0 and concluded the rig stopped delivering
    per-side rules after episode 1. F19 then blamed the harness, and F20 refuted both by direct
    measurement: every eval log shows exactly 60 "Behavior Tree Initialized" for 30 episodes x 2
    aircraft and zero "BT already exists", i.e. _recycle_native_bts() destroys and rebuilds both
    trees every episode and each re-reads its own XML. The rig was fine the whole time.

    The real reason those edits moved nothing was F25: a name= attribute on a control node made
    BehaviorTree.CPP build it with ZERO children, so 17 of 20 composites were empty shells and
    essentially the entire tactical layer was dead code. The edits were to branches that never
    executed. F25 was fixed 2026-08-13 and this rig was then used across full N=30 runs with the
    peer genuinely in effect throughout.

    PROVEN IN USE (2026-08-13), both N=30 on match_base, vptrack both sides:
      * ours (F25-fixed) vs peer on the pre-F25 tree  -> 16W/14D/0L, damage 6.99/0.06
        against a 9W/14D/7L symmetric control. That is the measurement F1-BLIND said was
        impossible and it is what established the F25 fix is worth shipping.
      * ours (F25 + a Gate 1 reorder) vs peer on F25-only -> 6W/11D/13L, i.e. the rig REJECTED a
        change that a symmetric same-tree-both-sides comparison had made look like a large win
        (21W/8D/1L). The change was reverted on this evidence.

    THE STANDING RULE THAT FOLLOWS: never adopt or reject a BT change on a symmetric measurement.
    Both aircraft read one global rule XML, so any same-tree-both-sides comparison gives BOTH
    sides the change and systematically inflates it. Score BT changes through this rig only.

    --verify runs --episodes 1. That is a resolution check, not a licence for an N>1 run; re-run
    it whenever the peer directory may have gone stale, and sanity-check that your result is not
    silently symmetric (see the two traps below).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
RULE_NAME = "Rule_forTraining.xml"
DLL_NAME = "AIP_BASE_target.dll"


def build(peer_dir: Path, xml_bytes: bytes, source_label: str) -> None:
    peer_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / DLL_NAME, peer_dir / DLL_NAME)
    (peer_dir / RULE_NAME).write_bytes(xml_bytes)

    ours = (ROOT / RULE_NAME).read_text(encoding="utf-8", errors="replace")
    theirs = (peer_dir / RULE_NAME).read_text(encoding="utf-8", errors="replace")
    print(f"peer directory : {peer_dir}")
    print(f"peer rule XML  : {source_label} ({len(xml_bytes)} bytes)")
    print(f"our rule XML   : {ROOT / RULE_NAME} ({len(ours.encode('utf-8'))} bytes)")
    if ours == theirs:
        print("\n  !! WARNING: the two rule files are IDENTICAL. This run would be symmetric,")
        print("     i.e. exactly the F1-BLIND situation you are trying to escape.")
    else:
        import difflib
        diff = list(difflib.unified_diff(theirs.splitlines(), ours.splitlines(),
                                         "peer", "ours", lineterm="", n=0))
        adds = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
        dels = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
        print(f"\n  differ: ours has {adds} line(s) the peer lacks, peer has {dels} ours lacks")

    rel = peer_dir.relative_to(ROOT).as_posix()
    print(f"\nUse it with:  --target-bt-dll {rel}/{DLL_NAME}")
    print("Do NOT also pass --bt-rule-xml (that would overwrite OUR live rule file).")


def verify(peer_dir: Path) -> int:
    """Prove the peer reads its OWN xml: with it removed exactly one tree must fail."""
    xml = peer_dir / RULE_NAME
    if not xml.exists():
        print(f"nothing to verify -- {xml} missing")
        return 1
    held = xml.read_bytes()
    xml.unlink()
    try:
        rel = peer_dir.relative_to(ROOT).as_posix()
        out = subprocess.run(
            [sys.executable, "scripts/eval_v5_vs_bt.py",
             "--ownship-backend", "vptrack", "--target-backend", "vptrack",
             "--scenario-mode", "match_base", "--episodes", "1",
             "--target-bt-dll", f"{rel}/{DLL_NAME}",
             "--out-csv", "artifacts/eval/peerbt_validate.csv"],
            cwd=ROOT, capture_output=True, text=True, errors="replace", timeout=900,
        )
        blob = (out.stdout or "") + (out.stderr or "")
        ok_n = blob.count("Behavior Tree Initialized")
        bad_n = blob.count("Initialization Failed")
    finally:
        xml.write_bytes(held)

    print(f"with the peer XML removed: {ok_n} tree(s) initialised, {bad_n} failed")
    if ok_n >= 1 and bad_n >= 1:
        print("Episode 0 reads the peer's own directory.")
        print()
        print("  !! THIS DOES NOT LICENSE A MULTI-EPISODE A/B. The peer's rules stop applying")
        print("     from episode 1 onward (COMPETITION_PLAN.md 4.1 F18) -- this check runs")
        print("     --episodes 1, which is the one episode that works. An N>1 run through this")
        print("     rig is UNMEASURED, not null, and it fails silently.")
        return 0
    print("NOT VERIFIED: the peer is not reading its own XML. Any A/B through this rig would be")
    print("symmetric and meaningless. Do not trust results until this passes.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--from-git", metavar="REV",
                     help=f"take {RULE_NAME} as of this git revision (e.g. dc3c46c^)")
    src.add_argument("--xml", metavar="PATH", help=f"use this file as the peer's {RULE_NAME}")
    ap.add_argument("--peer-dir", default="bt_peer",
                    help="directory under Release/ to build (default: bt_peer)")
    ap.add_argument("--verify", action="store_true",
                    help="prove the peer reads its own XML, then exit")
    args = ap.parse_args()

    peer_dir = ROOT / args.peer_dir
    if args.verify:
        return verify(peer_dir)

    if args.from_git:
        rel = "DogFightEnv/Release/" + RULE_NAME
        r = subprocess.run(["git", "show", f"{args.from_git}:{rel}"],
                           cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            print(f"git show failed for {args.from_git}:{rel}\n"
                  f"{(r.stderr or b'').decode('utf-8', 'replace')}")
            return 1
        build(peer_dir, r.stdout, f"git {args.from_git}")
    elif args.xml:
        p = Path(args.xml)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            print(f"no such file: {p}")
            return 1
        build(peer_dir, p.read_bytes(), str(p))
    else:
        ap.error("one of --from-git / --xml / --verify is required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
