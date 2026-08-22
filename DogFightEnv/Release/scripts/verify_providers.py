"""Every backend must build a real, non-None ActionProvider -- no server, no episode required.

WHY THIS EXISTS (2026-08-22). A refactor of `run_local_dogfight._build_provider_raw()` split the
function in two: a stray top-level `def resolve_vptrack_floor(...)` was inserted between the
`vptrack` branch's `return` and the `if backend in ("hybrid_vptrack", "hybrid_gated"):` block that
should have followed it. Python treated everything from that `if` onward as DEAD CODE inside
`resolve_vptrack_floor` (unreachable past its own `return`), so `_build_provider_raw` silently fell
off the end and returned `None` for every backend except `fixed`/`bt`/`vptrack`.

Nothing caught it. `ast.parse()` passed (the file is syntactically valid Python). Every existing
guard (`verify_resilience`, `verify_report_fixes`, `verify_live_frame_fix`, `verify_match_spawn`,
`probe_live_g_limiter`) stayed green, because none of them construct a hybrid/rl provider. A
banner-text spot-check ("does the log line show the right floor?") also passed, because the banner
in `eval_v5_vs_bt.py` calls `resolve_vptrack_floor()` directly -- which still worked correctly in
isolation -- rather than going through the broken `_build_provider_raw`.

The actual failure mode: `build_provider()` passes a `None` inner straight through (the same `None`
that legitimately means "env-flown, `fixed` backend"), so a `hybrid_gated`/`hybrid_vptrack`/
`hybrid`/`rl` run got NO real provider at all -- an undriven aircraft that flies a fixed/neutral
trajectory into the altitude floor at ~41.5s regardless of which bundle or weights were requested.
Four full N=50 evals were burned on this before the uniform crash timing (all four backends,
independent bundles, converging to a ~0.6s-wide crash window) was the tell that something was
structurally wrong rather than a genuine combat result.

    python scripts/verify_providers.py

Exit 0 = every backend builds a real provider. Non-zero = do not trust ANY eval run until fixed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for _p in (ROOT, SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


# A bundle is only needed for rl/hybrid* -- point at whichever completed campaign exists.
_BUNDLE = ROOT / "artifacts/curriculum/real_eagle/v10_residual/stage_15_full_dogfight/final_bundle"

# backend -> extra kwargs it needs beyond the common set.
_CASES = {
    "bt": {},
    "vptrack": {"vptrack_range_m": 4000.0, "vptrack_los_deg": 60.0, "vptrack_throttle": True},
    "hybrid": {"bundle_dir": str(_BUNDLE)},
    "hybrid_vptrack": {
        "bundle_dir": str(_BUNDLE),
        "vptrack_range_m": 4000.0, "vptrack_los_deg": 60.0, "vptrack_throttle": True,
    },
    "hybrid_gated": {
        "bundle_dir": str(_BUNDLE),
        "vptrack_range_m": 4000.0, "vptrack_los_deg": 60.0, "vptrack_throttle": True,
    },
    "rl": {"bundle_dir": str(_BUNDLE)},
    "cutoff": {},
}


def verify_every_backend_builds() -> None:
    print("Every backend builds a real (non-None) ActionProvider:")
    cases = dict(_CASES)
    if not _BUNDLE.exists():
        print(f"  [SKIP] bundle-backed cases -- {_BUNDLE} not found on this machine")
        for _b in ("hybrid", "hybrid_vptrack", "hybrid_gated", "rl"):
            cases.pop(_b, None)
    try:
        import cutoff_provider
        cutoff_provider.default_exe_path()
    except Exception as exc:
        print(f"  [SKIP] cutoff -- binary not found on this machine ({exc})")
        cases.pop("cutoff", None)

    import run_local_dogfight as rld

    for backend, extra in cases.items():
        kwargs = dict(
            side="ownship", backend=backend, bundle_dir=None, bt_dll="AIP_BASE.dll",
            policy_id="default_policy", hybrid_mode="residual", alpha=0.5, residual_scale=0.10,
            observation_mode="real_eagle15", observation_module="student.my_observation_v2",
        )
        kwargs.update(extra)
        try:
            provider = rld.build_provider(**kwargs)
        except Exception as exc:
            check(f"{backend} builds without raising", False, f"{type(exc).__name__}: {exc}")
            continue
        check(f"{backend} returns a non-None provider", provider is not None,
              f"got {provider!r}" if provider is None else type(provider).__name__)
        if provider is not None:
            check(f"{backend} provider has compute_action", hasattr(provider, "compute_action"))


def main() -> int:
    print("=" * 72)
    print("Provider construction check (no server, no episode required)")
    print("=" * 72)
    verify_every_backend_builds()
    print("\n" + "=" * 72)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        print("Do not trust any eval run using an affected backend until this is fixed.")
        return 1
    print("All provider construction checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
