"""Break a league campaign down by START SEPARATION -- the axis the competition cycles per game.

    python scripts/summarize_by_separation.py artifacts/eval/matrix_sepfix_0908

WHY THIS EXISTS. `COMPETITION_RULES.md` Sec 5.1 cycles the start separation with the GAME INDEX:
1경기 2,000 ft -> 2경기 2,500 ft -> 3경기 3,000 ft -> 4경기 2,000 ft. Every BO3 therefore plays all
three, and **세트득실차 -- the third standings key, and the one that decides group order when
points tie -- is counted per GAME.** So a config that is strong at 2,000 ft and weak at 3,000 ft
does not merely have an uneven profile; it bleeds set differential in precisely the place the
group is settled, while its pooled win rate looks fine.

Pooling hides exactly that. This splits it.

Until 2026-09-08 the question could not even be asked: the eval derived separation from the alpha
schedule as a smooth sweep, and because that schedule contains both 0 and 180 (which map to the
same fraction) it emitted nine values of which only 609.6 m was a real game distance -- weighted
twice -- while **2,500 ft and 3,000 ft never occurred at all**. Campaigns run before that fix have
nothing to say about games 2 and 3, and this script will tell you so rather than averaging noise.
"""
from __future__ import annotations

import collections
import csv
import glob
import sys
from pathlib import Path

FT = 0.3048
REAL = {609.6: "2000 ft", 762.0: "2500 ft", 914.4: "3000 ft"}
_TARGET_LOST = "target altitude below min"
_OWNSHIP_LOST = "ownship altitude below min"


def outcome(r: dict) -> str:
    """Competition adjudication: whoever goes below the floor loses, regardless of health."""
    end = (r.get("end_condition") or "").strip()
    if _TARGET_LOST in end:
        return "W"
    if _OWNSHIP_LOST in end:
        return "L"
    ph = (r.get("phased_outcome") or "").strip().lower()
    return {"win": "W", "loss": "L", "crash": "L"}.get(ph, "D")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/eval")
    files = sorted(glob.glob(str(root / "league_match_base__*.csv")))
    if not files:
        print(f"no match_base league CSVs under {root}")
        return 1

    per = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    seen_seps: collections.Counter = collections.Counter()
    for f in files:
        stem = Path(f).stem[len("league_match_base__"):]
        cand, arch = stem.split("__vs__", 1)
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            sep = round(float(r["initial_distance_m"]), 1)
            seen_seps[sep] += 1
            per[cand][sep][outcome(r)] += 1
            per[cand][("ALL", arch)][outcome(r)] += 1

    stale = [s for s in seen_seps if s not in REAL]
    if stale:
        print("!! This campaign predates the 2026-09-08 separation fix: it contains "
              f"{len(stale)} separations that are not real game distances "
              f"({min(stale):.1f}-{max(stale):.1f} m).")
        print("!! Games 2 and 3 of a BO3 are NOT represented. Re-run before trusting this.\n")
    missing = [m for m in REAL if m not in seen_seps]
    if missing:
        print(f"!! NEVER SAMPLED: {', '.join(REAL[m] for m in sorted(missing))} -- "
              "a real game separation is absent from this data.\n")

    hdr = f"{'candidate':<22}" + "".join(f"{REAL[s]:>22}" for s in sorted(REAL)) + f"{'pooled':>22}"
    print("WIN RATE BY START SEPARATION (competition adjudication)")
    print("Game 1 / 2 / 3 of every BO3. 세트득실차 is counted per game, so an uneven row")
    print("bleeds set differential exactly where group order is decided.")
    print(hdr)
    print("-" * len(hdr))
    for cand in sorted(per):
        line = f"{cand:<22}"
        tot: collections.Counter = collections.Counter()
        for s in sorted(REAL):
            c = per[cand].get(s)
            if not c:
                line += f"{'--':>22}"
                continue
            n = sum(c.values())
            tot += c
            line += f"{c['W']:>4}/{c['D']}/{c['L']:<3} {c['W']/n:>6.1%} "
        n = sum(tot.values()) or 1
        line += f"{tot['W']:>4}/{tot['D']}/{tot['L']:<3} {tot['W']/n:>6.1%} "
        print(line)
    print("-" * len(hdr))
    print("W/D/L then win rate. A large spread across the three columns is the finding;")
    print("a flat row means separation is not what is costing us.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
