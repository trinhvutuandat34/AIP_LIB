# Live Inference Frame Bugs — Two Coordinate-Frame Mismatches on the Unreal Wire Path

**What this file is for:** the single place to answer "does live inference actually work, and
what did we do about it". Written 2026-08-20, same day as `CUTOFF_MODEL_REFERENCE.md`, in
response to a real-match report: **our aircraft climbs away, never generates a firing solution,
and gets shot down — no WEZ contact, just flies off.** Two independent, verified bugs reproduce
that exact symptom. Both are fixed in `student/live_frame_fix.py`. **Neither fix has been tested
against a live Unreal connection.** That is the single most important open item in this project
right now — see §5.

For context elsewhere:
- **`CUTOFF_MODEL_REFERENCE.md`** — every win-rate number in that file was measured on a code
  path that structurally cannot exercise either bug below (see §4 here for why). Those numbers
  are valid as local measurements; they are not yet validated predictions of live behaviour.
- **`PROJECT_STRUCTURE.md`** — records `src/dogfight/**` as a hard no-edit boundary (team policy,
  2026-07-14). Both fixes live in `student/`, the sanctioned route, per that policy.

---

## 0. Summary for anyone with five minutes

Two of `state[2]`'s and `OPlaneData.LocationX/Y`'s frame conventions differ between the local
training sim and the live Unreal wire. Both are silently wrong in a way that produces flyable but
nonsensical commands — not a crash, not an exception, just an aircraft that behaves as if the
enemy is somewhere it isn't. Both are now corrected by one wrapper,
`student.live_frame_fix.LiveVerticalFrameProvider`, installed at both places a live provider gets
built (`run_unreal_inference.py`, `student/my_submission.py`). Both fixes are proven correct by
direct computation and by running the real DLL — **neither has been exercised end-to-end against
a live server**, because doing that requires either the organizers' address or
`DogFightViewer.exe` running locally with a human watching. That test has not happened yet.

Measured separately (§6): even in the best-performing local configuration, the code path that
carries these bugs flies **17-51% of every real match** by wall-clock time, depending on starting
geometry. This is not an edge case.

---

## 1. Bug 1 — vertical sign inversion (affects `VPTrackingProvider`'s own tracking law)

| | `state[2]` holds |
|---|---|
| Local training env | `pm.geodetic2ned(...)[2]` = **NED Down**, negative above ground |
| Live Unreal | `PlaneInfo.position.z`, copied straight through by `plane_info_to_state()` = **altitude, up-positive** |

Verified against the captured server session
`logs/unreal_packets/rx_packets_20260514_155232_15208.jsonl`: z is positive in all 2,984 samples
(595-1,067 m) and rises when pitch is positive — confirms up-positive, not NED.

`VPTrackingProvider._tracking_stick` (`student/controller_providers.py:377`) negates `state[2]` to
build an up-positive relative vector — correct for NED input, an inversion for input that is
*already* up-positive.

**Proof by equivalence** (same attitudes both sides, target 300 m above):

```
LOCAL, target ABOVE : [-0.159429 -1.0       0.48018   1.0]
LOCAL, target BELOW : [-0.982872 -0.0       0.053783  1.0]
LIVE , target ABOVE : [-0.982872 -0.0       0.053783  1.0]   <- identical to LOCAL/BELOW
```

Live "target above" produces a bit-identical command to local "target below". Told the enemy is
below when it is above, the controller pitches away — this alone is sufficient to produce
"climbs away" behaviour whenever the tracking law is engaged (inside the envelope; see Bug 2 for
what happens outside it).

**Fix:** negate `state[2]` for both aircraft, live path only. Only the difference between the two
aircraft matters for relative geometry, so the sea-level-vs-origin datum offset cancels.

---

## 2. Bug 2 — horizontal frame corruption (affects the native BT's own geometry)

This is the bigger bug: it affects **everything outside `VPTrackingProvider`'s tracking
envelope**, where `_tracking_stick` returns `None` and the aircraft is flown entirely by the
native BT via `StepWithPlaneData`.

Traced through `AIP_DCS` source, both call paths:

**Local path** — `AIPilot.Step()` (`src/dogfight/ai/native_bt.py`) calls the DLL's `ChangeData()`
first (`AIP_DCS/LibMain.cpp:368`), which passes JSBSim's real `NaviData.Lat/Lon` straight through
**unconverted** into `oPlaneData.LocationX/Y` (degrees). The exported `Step()`
(`LibMain.cpp:217`) copies that into a `PlaneInfo` and hands it to the internal
`UCPPBehaviorTree::Step()` (`AIP_DCS/BehaviorTree/CPPBehaviorTree.cpp:157`), which runs
`LLAtoCartesian(MyInfo.Location, Vector3(OriLAT, OriLOn, 0))`. `OriLAT`/`OriLOn` are hardcoded in
`CPPBehaviorTree.h:18-19` as `37.9145.../128.1818...` — confirmed to be **this project's own
JSBSim spawn region** (the eval log's `init ID:1 Lat37.9235... Lon128.1818...` matches to 4
decimal places on longitude). Self-consistent: real lat/lon in, matching-origin conversion out.

**Live path** — `AIPilot.StepWithPlaneData()` (`native_bt.py:208`) **skips `ChangeData()`
entirely**. `BuildPlaneData()` (`native_bt.py:157`) copies `[own_plane.position.x, .y, .z]` —
Unreal's local Cartesian **metres** (confirmed from the same captured session: values like
x=497.66, y=-166.84 — not valid lat/lon) — straight into `LocationX/Y`, then calls the **same**
exported `Step()`, which hands it to the **same** `LLAtoCartesian(..., OriLAT, OriLOn)`. The DLL
treats a metre-valued Unreal x-coordinate as a latitude in degrees.

**Numeric proof**, real captured aircraft pair, true separation 523.3 m:

```
LOCAL-style input  (real lat/lon)         -> distance =        188 m   (sane)
LIVE-style input   (raw Unreal metres)    -> distance = 57,033,198 m   (57,000 km)
```

Every `DECO_DistanceCheck` / `DECO_LOSCheck` / `DECO_AngleOffCheck` in the tree sees the enemy as
being on the opposite side of the planet. The tree's Fallback lands on its "target very far"
branch and steers at a phantom bearing that has nothing to do with the real opponent.

**Confirmed against the real DLL**, not just arithmetic — feeding it broken vs. fixed plane data
on identical tail-to-tail geometry (700 m apart) produces measurably different output:

```
BROKEN (raw Unreal metres): roll=-0.0000 pitch=-0.0000 rudder=+0.0000 thr=+1.0000  (constant, all ticks)
FIXED  (inverse-LLA)      : roll=+0.0000 pitch=-0.0000 rudder=+0.0000 thr=+0.5000  (constant, all ticks)
```

Both aircraft were on-axis in this synthetic test so roll/pitch/rudder read near zero either way
(bearing distortion from this bug is real but modest — see §3 for why); the clean, reproducible
divergence is **throttle**, consistent with the tree selecting a different Fallback branch
("target far, cruise/search" vs "target close, prosecute") depending on which geometry it's fed.

**Fix:** feed `BuildPlaneData` the exact inverse of `LLAtoCartesian` — same hardcoded origin, same
WGS84 ellipsoid constants. The forward transform is linear at a fixed base point, so the inverse
is closed-form. **Round-trip verified to 4×10⁻¹⁰ m** on real captured values — double-precision
noise floor, not an approximation.

```python
fake_lat = OriLAT + x * 180.0 / (math.pi * M)
fake_lon = OriLOn + y * 180.0 / (math.pi * N * cos(OriLAT_rad))
```

`M`, `N` are the same meridional/prime-vertical radii of curvature `LLAtoCartesian` itself
computes from `OriLAT`. `Z` is passed through unchanged — `dD = LLA.Z - BaseLLA.Z` with
`BaseLLA.Z = 0` means Z was never run through the lat/lon math on either path.

---

## 3. Why the bearing distortion from Bug 2 is real but modest, while distance is catastrophic

`M ≈ 6.335×10⁶`, `N·cos(OriLAT) ≈ 6.386×10⁶·0.789 ≈ 87,900` — wait, precisely:
`dN_per_metre_misread_as_degree ≈ M·π/180 ≈ 110,600`, `dE_per_metre_misread_as_degree ≈
N·cos(OriLAT)·π/180 ≈ 87,900`. Both raw Unreal x/y get scaled by similar-order-of-magnitude
factors (ratio ≈ 0.79), so the **apparent bearing** (`atan2(dE, dN)`) is distorted by roughly that
ratio — noticeable, not randomised. The **distance**, however, is scaled by the same enormous
factors on an absolute basis, so it comes out ~100,000× too large regardless of direction. This is
why every threshold-gated Decorator in the tree (`Distance <= 2000`, `LOS <= 15`, etc.) fails
uniformly — the geometry looks "impossibly far" in every doctrine check — while the specific
heading commanded can still look locally plausible in a synthetic on-axis test. Don't read the
small roll/pitch numbers in §2's DLL test as evidence the bug is mild; the distance corruption
alone is enough to break every distance/LOS gate in the tree.

---

## 4. Why nothing in this project's history caught either bug until now

`_compute_remote_action` (`bt_action_provider.py`) — the code path carrying both bugs — only runs
when `context.sim is None`. Every local evaluation this project has ever run (`run_local_dogfight.py`,
`eval_v5_vs_bt.py`, `scripts/eval_vs_cutoff.py`, and by extension every N=30/N=100 number in
`CUTOFF_MODEL_REFERENCE.md`) constructs a real local `sim` object, which routes through
`ai_pilot.Step(...)` — the branch that calls `ChangeData()` correctly. **None of this project's
local measurements, ever, have exercised the code path either bug lives in.** This is not a
criticism of the eval harness; it is a structural blind spot inherent to testing "live inference"
without a live connection, and it applies to `CutoffProvider` (`scripts/cutoff_provider.py`) too —
it feeds `ownship_state`/`target_state` directly, bypassing `plane_info_to_state()` and both bugs
entirely.

---

## 5. STATUS: fixed, and now verified headlessly against real wire data — sockets still untested

**Updated 2026-08-20 (later same day).** The geometry half of this is now closed: item 3 below was
the blocking gap and `scripts/verify_live_frame_fix.py` closes it, reproducing the 110,700× range
error on the live path and confirming the fix restores true range on real captured frames. What
remains open is the *transport* half — no socket, handshake, or reconnect has ever been exercised
(item 1).

**What is done:**
- Both bugs fully diagnosed with source-level proof (this document).
- Fix written: `student/live_frame_fix.py`, class `LiveVerticalFrameProvider`.
- Installed at both provider-construction sites: `run_unreal_inference.py:build_action_provider`
  and `student/my_submission.py:build_action_provider`, inside the G-limiter
  (`GLimitedProvider(LiveVerticalFrameProvider(...))`), so the chain for a live `vptrack` run is
  `GLimitedProvider -> LiveVerticalFrameProvider -> VPTrackingProvider` — confirmed by walking the
  constructed object graph.
- Both fixes independently proven correct: Bug 1 by equivalence (§1), Bug 2 by closed-form
  inverse + round-trip to 4×10⁻¹⁰ m + a real DLL call showing divergent behaviour (§2).
- `python -m py_compile` clean on all three touched/added files.

**What is NOT done, and must happen before this is trusted in a real match:**
1. **No live connection has ever exercised the fixed code.** Every proof above is either pure
   arithmetic, a direct DLL call with synthetic inputs, or a local-sim measurement that never
   touched the bug. Run `run_unreal_inference.py --mode vptrack` against a real
   `DogFightViewer.exe` (or, better, the actual competition server) and confirm the aircraft
   tracks correctly — this is the single highest-priority open item in this project.
2. **`context.observation` is NOT corrected.** `policies.py` builds it from the raw (unfixed)
   state before the provider is called, so any RL or hybrid mode's observation vector still
   carries Bug 1. Irrelevant while the shipped mode is `vptrack` (which reads `ownship_state`/
   `target_state` directly, not `observation`); revisit before shipping any bundle-backed mode.
3. ~~**No local harness exists that can even test these bugs.**~~ **BUILT AND PASSING, 2026-08-20:
   `scripts/verify_live_frame_fix.py`.** Headless, needs no server and no `DogFightViewer.exe`
   (which crashes on a no-GPU box — confirmed the same day). It decodes real `MT_PlaneInfo`
   packets from `logs/unreal_packets/` with the project's own `unpack_plane_info`, feeds the
   native BT through `StepWithPlaneData` exactly as `policies.py:_compute_provider_action` does
   (including `REMOTE_BT_FIGHTER_ID = 0`, which is the id `BuildPlaneData`'s hardcoded
   `Resv0 = 0.0` makes the DLL look the tree up by), and reads back **what the tree itself
   believes the range is** out of the blackboard via `GateTrace.h`'s `distance_m` column
   (`AIP_BASE_gatetrace.dll`). That single value is the right thing to assert on: every
   `DECO_DistanceCheck`/`DECO_LOSCheck`/`DECO_AngleOffCheck` in the tree is gated on it.

   **Measured, 25 real captured frames, true separation ~497 m:**

   | | BT's own `Distance` | vs truth |
   |---|---|---|
   | live path, unfixed (what ships without `live_frame_fix`) | **55,101,100 m** | **110,700× too large** |
   | live path, through `live_frame_fix` | **496.5 m** | within 0.6 m, 25/25 inside max(5 m, 2%) |

   The residual ~0.5 m is expected and understood, not error in the transform:
   `OPlaneData.LocationX/Y` are `c_float` (`native_bt.py:80-82`) and `_pack_plane_data_buffer`
   packs the target with `"fffffffifff"`, so encoding a latitude (~37.9) in float32 quantises to
   ~2.4×10⁻⁶ deg ≈ 0.27 m, where encoding a raw metre value (~500) quantised to ~3×10⁻⁵ m. The
   fix trades ~0.3 m of position precision for correct geometry — irrelevant against gates at
   152 m and up, and ~0.03° at 500 m against a 1° gun gate.

   The script also checks the failure mode a pure-arithmetic test cannot see: that the **wrapper
   actually engages**. It asserts `LiveVerticalFrameProvider` flips `state[2]` and rewrites
   `LocationX` when `sim is None`, and is a byte-exact pass-through when a local sim is present.
   This project has already shipped a correct transform that was wired into nothing once — the
   10 G limiter, "present in the tree, wired into nothing"
   (`run_local_dogfight.py:164-168`) — so "installed" and "running" are separate claims and are
   now separately tested.

   **What this does and does not establish.** It proves the geometry the DLL receives is now
   correct, on real wire data, through the real DLL. It does **not** exercise sockets, the
   handshake, `action_repeat` pacing, or reconnect behaviour — item 1 below is still open and is
   still the top live risk.
4. **Every win-rate number in `CUTOFF_MODEL_REFERENCE.md` predates this fix and was measured on
   the unaffected code path.** They are not wrong as local measurements, but none of them confirm
   what the fixed code actually does live. Re-validate the shipping configuration live before
   trusting the 81-100% figures as a competition prediction.

---

## 6. How much this matters, quantified: override-fraction measurement

`VPTrackingProvider` only overrides the native BT's stick *inside* its tracking envelope
(`rng <= engage_range_m and los_deg <= engage_los_deg`); outside it, the native BT — carrying
both bugs on the live path — flies. Instrumented `_override_steps`/`_total_steps` directly and
ran the shipping-candidate config (`throttle + 6000/90`) against the real cutoff binary at both
tested starting geometries, 5 episodes each:

| geometry | override fraction (control law flying) | **native-BT fraction (bug-affected on live path)** |
|---|---|---|
| beam merge (`los_deg=90`) | 64.8% – 83.3% | **17% – 35%** |
| tail-to-tail (`los_deg=180`) | 48.6% – 64.8% | **35% – 51%** |

The native BT flies roughly a third of a beam-merge match and up to half of a tail-to-tail match
— not a rare corner case. It is worse at tail-to-tail specifically because the opening reversal
(LOS starting near 180°, outside even a widened 90° gate) is native-BT territory for its entire
duration, which is exactly the phase where "climbs away, no WEZ" would appear if Bug 2 is still
live. This is the strongest available argument that the fix in §2 is not academic.

---

## 7. A related, smaller correction: the 60 Hz response-time rule does not mandate `--action-repeat 6`

Found while investigating tick-rate fidelity. `COMPETITION_RULES.md` §4 states: *"the engagement
server sends battlefield state at 60 Hz; your client must answer with a control command at 60 Hz
too"* and *"your AI's computation time is penalised if it exceeds 0.1667 s."* That is a **latency
budget per decision**, not a mandate to decide at 10 Hz — `--action-repeat` does not change the
*answer* rate at all (`ProviderCommandPolicy.compute_command` returns a CMD on every pair
regardless); it only controls how often the action is *recomputed*.

Measured: `VPTrackingProvider.compute_action` on the live (`StepWithPlaneData`) path, 5,000
samples — mean 0.109 ms, p99 0.166 ms, **worst-of-5,000 0.611 ms**, against a 166.67 ms budget.
**~272× inside the limit.** `--action-repeat 6` exists to match the RL training `step_ratio`
(a train/inference consistency argument for a *trained policy*), not because the rule requires
it. `vptrack` was never trained, so there is nothing to stay consistent with — ship it at
`--action-repeat 1`. If any RL or hybrid mode is shipped later, that mode specifically should keep
`--action-repeat 6` to match its training dynamics; this is a per-mode decision, not a global one.
