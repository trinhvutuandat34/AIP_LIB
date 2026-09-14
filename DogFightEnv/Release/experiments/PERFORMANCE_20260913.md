# Performance results — 2026-09-13

Installed the validated Release|x64 native build and rebuilt both submission packages. No commit was made.

## Runtime changes

- `GeoMathUtil.py`: reuse repeated body-frame geometry with a bounded 128-entry stdlib cache. Immutable dtype/byte keys preserve behavior when callers mutate arrays. No dependency added.
- `GateTrace.h`: do not attach a status-change callback when tracing is disabled. Previously, disabled tracing still accumulated pending text indefinitely.
- Built the native DLL with the project's existing Release configuration instead of the previously installed Debug binary.
- `run_unreal_inference.py`: forward the adopted standoff/adaptive settings through direct tracking and both hybrid tracking modes; retain explicit CLI overrides.

| Measurement | Before | After | Result |
|---|---:|---:|---|
| Repeated geometry workload, median of five | 0.1914 s | 0.0638 s | 3.00× throughput |
| Simulation, 2,400-step cap, median of three alternating-order trials | 12.1917 s | 7.3430 s | 39.8% less wall time |
| Complete combat episode, 5,090 steps | 24.3363 s | 14.2131 s | 41.6% less wall time |
| Native test, 12,000 calls, private-memory growth | 8,904,704 bytes | 0 bytes | Disabled-trace accumulation removed |

The native control-byte digest matched exactly across original Debug, fixed Debug, and fixed Release builds. Simulation CSV comparisons matched outcomes and fields (numeric tolerance below 1e-10). Complete episodes also matched for adopted Model 1 (5,094 steps) and Model 2 (1,617 steps). These are local workloads, not a claim about every match or network latency. The 12,000-step combat limit was a cap, not the actual episode length.

## Win-rate evidence

The shared workspace adopted `adaptive300_deckttc` while this work was running. This change preserves that adoption and fixes live CLI parity; it does not introduce another tactical variant.

Two completed, paired 100-episode cutoff controls used identical starts within the corrected 609.6–9,144 m altitude and 200–300 m/s speed bands:

- Previous profile: 91/200 wins, **45.5%**.
- Adopted profile: 107/200 wins, **53.5%**, an observed **+8 percentage points**.
- Paired changes: 39 gained wins, 23 lost wins; exact two-sided McNemar **p = 0.0559**. Promising, but not established at the 5% threshold.
- Additional same-seed screen: mirror 9/12 → 8/12 wins; sniper 11/12 → 11/12. The benefit is not universal. These are local opponent analogues.

## Verification and artifacts

Geometry checks cover 1,061 cases, both directions, projection modes, mutation, precision and invalid values. Native tracing checks pass enabled/disabled. Live tracking defaults/overrides, standoff geometry, phase boundaries, match clock and scenario seeding checks pass.

Both rebuilt EXEs passed 600-frame loopback flight checks, including clean-directory copies extracted from their ZIPs. Extracted native DLLs separately produced positive `Behavior Tree Initialized` output and the original non-zero control digest. Both bundled DLLs and XML match workspace bytes. DLL CRC32: **2335424739**; XML: **1134304942**, 61 named nodes. Each ZIP contains exactly its EXE and `config.json`; launch-time server overrides remain supported.

Evidence, hashes, benchmark scripts and clean-directory logs: [performance artifacts](../artifacts/performance_20260912/). [Package manifest](../artifacts/performance_20260912/release_manifest.json) records both ZIP SHA-256 values. Previous EXEs/ZIPs/config are preserved under `previous_submission/`; original runtime under `baseline/`. Test subprocesses were stopped after verification.

Reproduce from `DogFightEnv/Release` with the installed `aip` Python environment:

```powershell
python scripts/test_geometry_performance.py --baseline artifacts/performance_20260912/baseline/GeoMathUtil.py
python scripts/test_live_tracking_defaults.py
python scripts/assert_baseline.py
```
