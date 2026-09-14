"""Split the corrected-band arms at the hard deck and score each half separately.

    python scripts/band_subset_report.py

WHY THIS EXISTS. The organizer-confirmed spawn band starts at 609.6 m (2,000 ft), which is
BELOW SHIP_HARD_DECK_M = 1,000 m. Below the deck `_tracking_stick` returns None and hands the
aircraft to the BT (student/controller_providers.py:801), so those rounds are flown by a
different stack than the rest -- the tuned controller is off through the merge. The old proxy
band started at exactly 1,000 m, so no episode in any pre-2026-09-11 CSV can show this.

A pooled number hides it: only ~4.6% of the real altitude band lies below the deck, so a
100-episode arm holds roughly 5 such episodes and the effect is invisible in the total. This
splits them out and scores each half with the SAME scorer as everything else -- `league._load`
via `score_arms.clean` -- rather than inventing a third opinion about what a win is.

READ THE SUB-DECK HALF AS DIRECTIONAL. At ~5 episodes per arm it is an indication, not a
result. Pool the seeds before believing anything.
"""
from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from league import _load           # noqa: E402 -- one definition of "what is a win"
from score_arms import clean, extras, line   # noqa: E402

_ROOT = _HERE.parent
DECK_M = 1000.0

# FULL-BAND arms only. The phase-B arms are clamped to 609.6-1000 m and are 100% sub-deck by
# construction, so splitting them here would just restate their own totals.
ARMS = [
    ("shipped, seed1", "band_nonotch_s1"),
    ("shipped, seed2", "band_nonotch_s2"),
    ("63-node control", "band_ctl63_s1"),
    ("deck 600, full band", "band_deck600_full"),
]


def _score(rows: list[dict], header: list[str], stem: str):
    """Score a row subset by handing it to league._load as its own clean file."""
    if not rows:
        return None, None
    tmp = Path(tempfile.gettempdir()) / f"band_subset_{stem}.csv"
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(rows)
    return _load(tmp), extras(rows)


def main() -> int:
    print(f"Split at the hard deck: initial_altitude_m < {DECK_M:.0f} m means the controller "
          f"is handed to the BT at spawn.\n")
    any_rows = False
    for label, stem in ARMS:
        path = _ROOT / "artifacts" / "eval" / f"{stem}_vs_cutoff.csv"
        if not path.exists():
            print(f"{label:22s} -- no CSV yet ({path.name})")
            continue
        rows, dropped, _ = clean(path)
        if not rows:
            print(f"{label:22s} -- empty")
            continue
        with path.open(encoding="utf-8", errors="replace") as fh:
            header = csv.DictReader(fh).fieldnames
        below = [r for r in rows if float(r["initial_altitude_m"]) < DECK_M]
        above = [r for r in rows if float(r["initial_altitude_m"]) >= DECK_M]
        assert len(below) + len(above) == len(rows), "partition lost rows"
        any_rows = True

        print(f"--- {label}  ({len(rows)} scored, {dropped} torn rows dropped) ---")
        for tag, subset in (("SUB-DECK", below), ("above deck", above)):
            s, x = _score(subset, header, f"{stem}_{tag}")
            if s is None:
                print(f"  {tag:10s} n=  0 | no episodes spawned here")
                continue
            print("  " + line(tag, s, x))
        print()

    if any_rows:
        print("The sub-deck half is ~4.6% of the band by construction, so expect ~5 episodes "
              "per 100-episode arm.\nPool seeds before drawing a conclusion; a single arm's "
              "sub-deck row is directional only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
