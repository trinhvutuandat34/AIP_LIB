"""Do our phase gates agree with the rulebook exactly at the boundaries?

    python scripts/test_phase_boundaries.py

WHY. COMPETITION_RULES Sec 6.2 (and the 통합 픽셀 데미지 맵 slide) state the range test as
INCLUSIVE (500 <= r <= 3000) and the angle test as STRICT (|theta| < 1). Those are different
comparisons, and a scorer that gets either backwards disagrees with the competition at the exact
geometry a marginal shot lands on. Found on 2026-09-09: the angle test used >, crediting Phase 1
at exactly 1.000 deg where the rule pays Phase 2, and Phase 3 at exactly 3.000 deg where the rule
pays zero.

The practical error is measure-zero -- it needs exact float equality -- so this is not about
recovering damage. It is about being able to cite our own numbers against the rulebook.
"""
from __future__ import annotations
import sys
from pathlib import Path
_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE.parent / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from student.reward_lib import WEZ_PHASES, match_wez_phase

FT = 0.3048
LATE = 190.0   # every phase eligible, so the nesting rule is what decides


def phase_at(r_ft: float, theta: float) -> str:
    ph = match_wez_phase(WEZ_PHASES, r_ft * FT, theta, LATE)
    return "none" if ph is None else f"P{WEZ_PHASES.index(ph) + 1}"


CASES = [
    # range: inclusive at both ends
    (499.9, 0.0, "none"), (500.0, 0.0, "P1"), (3000.0, 0.0, "P1"), (3000.1, 0.0, "P2"),
    (3500.0, 0.0, "P2"), (3500.1, 0.0, "P3"), (4000.0, 0.0, "P3"), (4000.1, 0.0, "none"),
    # angle: STRICT
    (1000.0, 0.999, "P1"), (1000.0, 1.0, "P2"), (1000.0, 1.999, "P2"),
    (1000.0, 2.0, "P3"), (1000.0, 2.999, "P3"), (1000.0, 3.0, "none"),
    # nesting: a Phase-1-quality shot late still pays Phase 1
    (600.0, 0.5, "P1"),
    # sign symmetry: the gate is on |theta|
    (1000.0, -0.5, "P1"), (1000.0, -2.5, "P3"),
]


def main() -> int:
    bad = [(r, t, want, phase_at(r, t)) for r, t, want in CASES if phase_at(r, t) != want]
    for r, t, want, got in bad:
        print(f"  MISMATCH r={r} ft theta={t} -> {got}, rulebook says {want}")
    if bad:
        print(f"\nFAIL: {len(bad)}/{len(CASES)} boundary cases disagree with COMPETITION_RULES Sec 6.2")
        return 1
    print(f"OK  {len(CASES)}/{len(CASES)} boundary cases match the rulebook "
          f"(range inclusive, angle strict, nesting and sign symmetry included)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
