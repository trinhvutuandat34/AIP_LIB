"""Rank ablation arms on NET COMBAT EFFECTIVENESS, not on win rate alone.

    python scripts/score_arms.py --control artifacts/eval/league_match_base__ship_6000_120_deck__vs__cutoff.csv \
                                 "artifacts/eval/ablate_*_vs_cutoff.csv"

WHY NOT A HAND-ROLLED WEIGHTED SCORE. The competition already defines the aggregate: 200 s
engagement, timeout decided on damage dealt / remaining health (COMPETITION_RULES Sec 5), and
group advancement on 승 3 / 무 1 / 패 0 over a BO3 (Sec 1). `league.py::_load` turns an episode
CSV into exactly that, including the two crash-bucketing fixes of 2026-09-08. So this imports
that function rather than restating it -- the same anti-drift move league.py itself made when it
imported `_TARGET_LOST`/`_OWNSHIP_LOST` from summarize_cutoff.py. Inventing a second scorer here
would give this project a third opinion about what a win is, and it has already been bitten twice
by having two.

WHAT THE COLUMNS MEAN, in the language of the optimization brief:

    dealt / taken / diff  net combat effectiveness. `diff` is the one that matters most: 43% of
                          episodes against the cutoff end in timeout, and a timeout is
                          adjudicated on exactly this.
    wez%                  "successful firing opportunities". There is NO trigger in the protocol
                          -- the command struct is (roll, pitch, yaw, throttle) and the server
                          adjudicates hits on geometry -- so "firing when an opportunity exists"
                          IS holding 152.4-914.4 m at ATA <= 1 deg. This is that number.
    nopoint%              missed opportunities: episodes that never reach the envelope at all.
                          Against the cutoff this is 35% of episodes and is the single largest
                          recoverable pocket in the problem.
    died / deck           survivability, split into shot down vs flown into our own floor,
                          because they have different fixes.
    bo3                   expected BO3 match points. The ranking key.

Rows with a missing field are skipped and counted rather than coerced to zero: a run cut off
mid-write leaves a torn final line, and zero-filling it biases every mean downward.
"""
from __future__ import annotations

import argparse
import csv
import glob
import math
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent), str(_HERE.parent / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from league import _load  # noqa: E402  -- one definition of "what is a win", shared with the matrix

_NEEDED = ("phased_outcome", "end_condition", "ep_wez_steps", "ep_min_distance",
           "ep_damage_dealt", "ep_damage_taken")


def clean(path: Path) -> tuple[list[dict], int, Path]:
    """Rows with every needed field, plus a temp CSV holding just those rows.

    `league._load` takes a PATH and fills missing fields with `.get(...) or 0`, which would turn
    a torn final line into a zero-damage zero-WEZ episode and drag every mean down. So the rows
    are filtered here and handed to it as a clean file -- reusing its scoring without inheriting
    that coercion.
    """
    rows, dropped, header = [], 0, None
    with path.open(encoding="utf-8", errors="replace") as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames
        for r in rd:
            if any(r.get(k) in (None, "") for k in _NEEDED):
                dropped += 1
                continue
            rows.append(r)
    if not header:
        # A run that has only just started has an empty file and no header row yet.
        return [], dropped, path
    tmp = Path(tempfile.gettempdir()) / f"score_arms_{path.stem}.csv"
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return rows, dropped, tmp


def extras(rows: list[dict]) -> dict:
    n = len(rows)
    nopoint = sum(1 for r in rows if float(r["ep_wez_steps"]) == 0)
    died = sum(1 for r in rows if r["end_condition"] == "ownship destroyed")
    deck = sum(1 for r in rows if r["end_condition"] == "ownship altitude below min")
    return dict(nopoint=nopoint / n, died=died / n, deck=deck / n)


def line(label: str, s: dict, x: dict) -> str:
    return (f"{label:22s} n={s['n']:3d} | bo3 {s['bo3_points']:5.2f} | "
            f"W{s['w']:3d} D{s['d']:3d} L{s['l']:3d} kills {s['kills']:3d} | "
            f"dealt {s['dealt']:.3f} taken {s['taken']:.3f} NET {s['diff']:+.3f} | "
            f"wez {s['wez_rate']:5.1%} nopoint {x['nopoint']:5.1%} | "
            f"died {x['died']:4.0%} deck {x['deck']:4.0%}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", required=True)
    ap.add_argument("arms", nargs="+")
    a = ap.parse_args()

    cpath = Path(a.control)
    crows, cdrop, ctmp = clean(cpath)
    if not crows:
        print(f"control {cpath} has no usable rows")
        return 1
    cs, cx = _load(ctmp), extras(crows)
    print(line("CONTROL", cs, cx) + (f"  [{cdrop} torn]" if cdrop else ""))
    print()

    paths: list[str] = []
    for pat in a.arms:
        paths.extend(sorted(glob.glob(pat)))

    scored = []
    for p in paths:
        path = Path(p)
        if path.resolve() == cpath.resolve():
            continue
        rows, drop, tmp = clean(path)
        if not rows:
            print(f"{path.stem:22s} -- no usable rows yet")
            continue
        s, x = _load(tmp), extras(rows)
        name = path.stem.replace("ablate_", "").replace("_vs_cutoff", "")
        scored.append((s["bo3_points"], name, s, x, drop))

    for _, name, s, x, drop in sorted(scored, reverse=True):
        print(line(name, s, x) + (f"  [{drop} torn]" if drop else ""))
        # Standard error on the win-rate difference, so a delta is never read as a result on its own.
        pw_a, pw_c = s["w"] / s["n"], cs["w"] / cs["n"]
        se = math.sqrt(pw_a * (1 - pw_a) / s["n"] + pw_c * (1 - pw_c) / cs["n"])
        d = pw_a - pw_c
        print(f"{'':22s}    bo3 {s['bo3_points'] - cs['bo3_points']:+5.2f} | "
              f"win {d:+5.1%} ({d / se:+.2f} SE) | NET {s['diff'] - cs['diff']:+.3f} | "
              f"nopoint {x['nopoint'] - cx['nopoint']:+5.1%} | "
              f"died {x['died'] - cx['died']:+4.0%}")
        # The corner_on trap: win rate rose while offence collapsed. Win rate alone would pass it.
        if d > 0 and s["dealt"] < cs["dealt"] * 0.85:
            print(f"{'':22s}    !! win rate up but damage dealt fell "
                  f"{cs['dealt']:.3f} -> {s['dealt']:.3f} -- check before believing it")
        print()

    if scored:
        print("Ranked by expected BO3 match points (the competition's own aggregate).")
        print("A delta inside ~1 SE is not a result. N=40 gives roughly +/-11 pp on win rate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
