"""Correct TWO Unreal<->native-BT frame mismatches on the LIVE inference path.

Found 2026-08-20 from a real-match report: our aircraft climbs away, never generates a firing
solution, gets gunned -- "no WEZ, just fly away". Two independent bugs reproduce this; both are
fixed here because either alone leaves the other live.

--------------------------------------------------------------------------------------------
BUG 1 -- VERTICAL SIGN (affects `VPTrackingProvider`'s own state-based tracking law)
--------------------------------------------------------------------------------------------

    local env   `state[2]` = `pm.geodetic2ned(...)[2]` = NED **Down**, negative above ground
    live Unreal `state[2]` = `PlaneInfo.position.z` copied straight through by
                `plane_info_to_state()` = **altitude, up-positive**

Verified against the captured server session `logs/unreal_packets/
rx_packets_20260514_155232_15208.jsonl`: z is positive in all 2984 samples (595-1067 m) and rises
when pitch is positive. `VPTrackingProvider._tracking_stick` negates state[2] to build an
up-positive relative vector (`controller_providers.py:377`) -- correct for NED, an inversion for
an already-up-positive altitude. Proof by equivalence, same attitudes, target 300 m above:

    LOCAL, target ABOVE : [-0.159429 -1.0       0.48018   1.0]
    LOCAL, target BELOW : [-0.982872 -0.0       0.053783  1.0]
    LIVE , target ABOVE : [-0.982872 -0.0       0.053783  1.0]   <- identical to LOCAL/BELOW

Fix: negate `state[2]` for both aircraft, live path only.

--------------------------------------------------------------------------------------------
BUG 2 -- HORIZONTAL FRAME (affects the native BT's OWN geometry, i.e. everything outside
VPTrackingProvider's tracking envelope, where `_tracking_stick` returns None and the fight is
flown entirely by `StepWithPlaneData`)
--------------------------------------------------------------------------------------------

The native BT does not receive Cartesian metres. Traced through `AIP_DCS`:

  - LOCAL path: `AIPilot.Step()` calls the DLL's `ChangeData()` first
    (`LibMain.cpp:368`), which passes JSBSim's real `NaviData.Lat/Lon` straight through
    UNCONVERTED into `oPlaneData.LocationX/Y` (degrees). The exported `Step()` (`LibMain.cpp:217`)
    copies that into a `PlaneInfo` and hands it to the INTERNAL `UCPPBehaviorTree::Step()`
    (`CPPBehaviorTree.cpp:157`), which runs `LLAtoCartesian(MyInfo.Location,
    Vector3(OriLAT, OriLOn, 0))` -- `OriLAT`/`OriLOn` are hardcoded in `CPPBehaviorTree.h:18-19`
    as `37.9145.../128.1818...`, which IS this project's own JSBSim spawn region (confirmed: the
    eval log's `init ID:1 Lat37.9235... Lon128.1818...` matches to 4 decimal places on longitude).
    So on the local path the geometry is self-consistent: real lat/lon in, matching-origin
    conversion out.

  - LIVE path: `AIPilot.StepWithPlaneData()` (`native_bt.py:208`) skips `ChangeData()` entirely.
    `BuildPlaneData()` (`native_bt.py:157`) copies `[own_plane.position.x, .y, .z]` --
    Unreal's LOCAL CARTESIAN METRES (confirmed from the same captured session: values like
    x=497.66, y=-166.84 -- not valid lat/lon) -- straight into `LocationX/Y`, then calls the
    SAME exported `Step()`, which hands it to the SAME `LLAtoCartesian(..., OriLAT, OriLOn)`.
    The DLL now treats a metre-valued Unreal x-coordinate as a latitude in degrees.

Numeric proof, same two captured aircraft (true separation 523.3 m):

    LOCAL-style input  (real lat/lon)         -> distance =        188 m   (sane)
    LIVE-style input   (raw Unreal metres)    -> distance = 57,033,198 m   (57,000 km)

Every `DECO_DistanceCheck`/`DECO_LOSCheck`/`DECO_AngleOffCheck` in the tree sees the enemy as
being on the opposite side of the planet. The BT's Fallback lands on its "target far away"
branch and steers at a phantom bearing that has nothing to do with the real opponent -- this
is what "climbs away, no WEZ" looks like from outside.

WHY THE LOCAL HARNESS NEVER CAUGHT THIS. `_compute_remote_action` (`bt_action_provider.py`,
`StepWithPlaneData`) only runs when `context.sim is None`. Local eval always has a real `sim`
object, so it takes the OTHER branch (`ai_pilot.Step(...)`, which DOES call `ChangeData()`
correctly). Every N=30/N=100 number in this project's history was produced on the correct-geometry
branch; none of them exercised this code path at all.

WHY THIS MATTERS MOST FOR A WIDE TRACKING ENVELOPE AND A TAIL-TO-TAIL START. `VPTrackingProvider`
overrides the BT's stick only INSIDE its envelope (`rng <= engage_range_m and
los_deg <= engage_los_deg`); outside it, `_tracking_stick` returns None and this broken code
flies the aircraft. A tail-to-tail (LOS~180 deg) start begins OUTSIDE even a widened
`engage_los_deg=90` gate, so the opening seconds -- exactly the reversal phase -- are flown on the
57,000 km phantom-target geometry. This is a materially different risk profile than a beam start.

Fix: feed `BuildPlaneData` the INVERSE of `LLAtoCartesian` (same hardcoded origin, same ellipsoid
constants) instead of raw Unreal x/y. Because the forward transform is linear at a fixed base
point, the inverse is closed-form and exact -- verified by round-trip on real captured values to
4e-10 m (double precision noise floor). Z is passed through unchanged: `dD = LLA.Z - BaseLLA.Z`
with `BaseLLA.Z=0` means Z was never run through the lat/lon math on either path.

--------------------------------------------------------------------------------------------
BUG 3 -- INCOMPLETE LIVE STATE VECTOR (affects `student/g_limiter.py`, i.e. the 10 G limiter
that wraps EVERY backend on both the eval path and the submission path). Found 2026-08-22.
--------------------------------------------------------------------------------------------

`plane_info_to_state()` fills state indices **0..8 and nothing else**; the local sim
(`FighterSim.py:224`) also fills `StateIndex.SIM_TIME` (state[41]). `GLimiter.observe()` derives
load factor as specific force from a velocity difference and takes dt from SIM_TIME. Live, that
is 0.0 on every frame, so `dt = 0.0`, the `dt < MIN_DT` guard returns early on every call,
`last_n` never leaves its 1.0 initial value, and the limiter clamps nothing, ever.

Measured (`scripts/probe_live_g_limiter.py`), identical ~12 G pull driven through both state
shapes:

    LOCAL (SIM_TIME filled)      measured_n = 12.958   clamped 97.5%   pitch -1.00 -> -0.77
    LIVE  (SIM_TIME never filled) measured_n =  1.000   clamped  0.0%   pitch -1.00 -> -1.00

So every N=30/N=50/N=100 figure in COMPETITION_PLAN.md 4.1 was produced by a G-LIMITED aircraft
and the submission flies an UNLIMITED one -- exactly the train/deploy divergence
`student/g_limiter.py` was written to prevent, reintroduced one layer down.

Second, smaller defect on the same code: `GLimiter._vel_neu` reads VZ as NED-down and negates
it, but the live wire sends velocity.z UP-positive (`logs/unreal_packets/
rx_packets_20260514_155232_15208.jsonl`: corr(pitch, vz) = +0.84, corr(dz, vz) = +0.73), so the
vertical term would enter the acceleration estimate sign-flipped even with dt repaired.

Fix (OPT-IN, default off -- see COMPLETE_LIVE_STATE): on the live path only, also negate
state[8] (VZ) alongside state[2], and fill state[41] from a monotonic clock. Then wrap the
G limiter INSIDE this provider rather than outside it, so it reads the completed state.
`build_action_provider()` in both entry points does the wrapping; the ordering matters and is
commented there.

--------------------------------------------------------------------------------------------
BOUNDARY & SCOPE
--------------------------------------------------------------------------------------------

`plane_info_to_state()` lives in `src/dogfight/unreal/policies.py`, inside the hard no-edit
boundary (`src/dogfight/**`, team policy 2026-07-14). This wrapper is the sanctioned route:
student-space, installed at the provider construction site in the entry scripts.

Corrects `ownship_state`/`target_state` (bug 1), `info["my_plane_data"]`/
`info["target_plane_data"]` (bug 2), and -- since 2026-08-22 -- `context.observation` as well,
when an `observation_rebuild` callable is supplied.

THE OBSERVATION GAP, and why it was worth closing. `policies.py` builds the observation from the
UNCORRECTED state before the provider is ever called, so a bundle-backed mode received bug 1
straight through on its feature vector: `student/my_observation_v2` reads altitude as
`-state[D]`, which live yields **-4572 m** instead of +4572 m, and the vertical component of the
relative-position triple flips sign with it. Two of fifteen features wrong, one of them far
outside the range it was normalised against. That is not a rounding error -- it means **no local
measurement of any bundle-backed mode transfers to the live server**, which in turn means the
hybrid modes could not be evaluated as submission candidates at all.

It stayed open while `MODE="vptrack"` shipped, because that mode ignores `context.observation`
entirely. It became decision-relevant when F48 showed `hybrid_gated`, composed correctly, beats
the shipped floor head to head. Wiring is per-mode: the entry points pass `observation_rebuild`
only for bundle-backed modes, so the shipped `vptrack` path is byte-identical to before.
"""

from __future__ import annotations

import math
import os
import time

import numpy as np

from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult
from dogfight.ai.native_bt import OPlaneData

# Hardcoded in AIP_DCS/BehaviorTree/CPPBehaviorTree.h:18-19 -- must match exactly, it is the
# origin the native BT's own LLAtoCartesian() call uses, not a value we get to choose.
# Opt-in (2026-08-22, bug 3). OFF by default so the submission's flight behaviour is bit-identical
# to every historical measurement unless the team turns this on deliberately. Turning it ON makes
# the LIVE path match the EVAL path (a working 10 G limiter), which is the direction that removes
# a divergence rather than adding one. Set DOGFIGHT_LIVE_STATE_COMPLETE=1.
COMPLETE_LIVE_STATE = os.environ.get("DOGFIGHT_LIVE_STATE_COMPLETE", "0") not in ("0", "", "false", "False")

_ORI_LAT = 37.91455691666666
_ORI_LON = 128.18188127777776

_WGS84_A = 6378137.0
_WGS84_B = 6356752.3142
_ECC2 = 1.0 - (_WGS84_B ** 2) / (_WGS84_A ** 2)
_ORI_LAT_RAD = math.radians(_ORI_LAT)
_N_RADIUS = _WGS84_A / math.sqrt(1.0 - _ECC2 * math.sin(_ORI_LAT_RAD) ** 2)
_M_RADIUS = _WGS84_A * (1.0 - _ECC2) / (1.0 - _ECC2 * math.sin(_ORI_LAT_RAD) ** 2) ** 1.5
_COS_ORI_LAT = math.cos(_ORI_LAT_RAD)


def _unreal_xy_to_fake_lla(x: float, y: float) -> tuple[float, float]:
    """Inverse of AIP_DCS's LLAtoCartesian(., Vector3(OriLAT, OriLOn, 0)).

    Feeding this output back through that exact formula recovers (x, y) as (dN, dE) -- i.e. the
    native BT's own conversion undoes this one, and its geometry ends up in real Cartesian metres
    instead of the 57,000 km phantom distance raw Unreal coordinates currently produce.
    """
    fake_lat = _ORI_LAT + x * 180.0 / (math.pi * _M_RADIUS)
    fake_lon = _ORI_LON + y * 180.0 / (math.pi * _N_RADIUS * _COS_ORI_LAT)
    return fake_lat, fake_lon


def _corrected_plane_data(pd: OPlaneData) -> OPlaneData:
    fixed = OPlaneData()
    ct_type = OPlaneData
    for name, _ in ct_type._fields_:
        setattr(fixed, name, getattr(pd, name))
    fake_lat, fake_lon = _unreal_xy_to_fake_lla(float(pd.LocationX), float(pd.LocationY))
    fixed.LocationX = fake_lat
    fixed.LocationY = fake_lon
    # LocationZ unchanged -- dD = LLA.Z - BaseLLA.Z with BaseLLA.Z=0 passes Z straight through
    # on both the local and live paths, so there is nothing to invert here.
    return fixed


class LiveVerticalFrameProvider(ActionProvider):
    """Fix both live-path frame bugs: state[2]'s vertical sign (bug 1) and my/target_plane_data's
    horizontal LLA misinterpretation (bug 2). See module docstring for the full derivation of
    each.

    Live path only. `context.sim is None` is exactly the live/remote discriminator already used by
    `BTActionProvider.compute_action()` to choose `_compute_remote_action`, so this applies the
    correction on precisely the same episodes that take the remote path and is a transparent
    pass-through in the local sim and in eval.
    """

    # Escape hatch so the fix can be A/B'd end-to-end (scripts/loopback_live_dryrun.py runs the
    # unfixed control this way). A test that cannot be made to FAIL proves nothing -- without a
    # control, "the commands varied" is not evidence the correction was applied. Never set this
    # in a submission: it restores the 110,700x range error measured in
    # scripts/verify_live_frame_fix.py.
    _DISABLE_ENV = "DOGFIGHT_DISABLE_LIVE_FRAME_FIX"

    def __init__(self, inner: ActionProvider, enabled: bool | None = None,
                 complete_state: bool | None = None, observation_rebuild=None) -> None:
        self.inner = inner
        # observation_rebuild(corrected_own, corrected_tgt) -> np.ndarray, or None to leave
        # context.observation alone. Only bundle-backed modes need it; see the module docstring.
        self.observation_rebuild = observation_rebuild
        self.observation_rebuild_failures = 0
        self.complete_state = (COMPLETE_LIVE_STATE if complete_state is None
                               else bool(complete_state))
        self._t0 = None
        if enabled is None:
            enabled = os.environ.get(self._DISABLE_ENV, "0") in ("0", "", "false", "False")
        self.enabled = bool(enabled)
        self.corrected_steps = 0
        self.passthrough_steps = 0
        if not self.enabled:
            print(f"[live_frame_fix] DISABLED via {self._DISABLE_ENV} -- diagnostic only, "
                  "the native BT will see a ~110,700x wrong range. Never ship this.")

    # Keep the wrapper transparent: _iter_bt_providers(), GLimitedProvider and the resilience
    # wrappers all reach through to the real provider by attribute.
    def __getattr__(self, name):
        return getattr(self.__dict__["inner"], name)

    def reset(self, context: ActionContext | None = None) -> None:
        # Per-episode, same argument as GLimiter.reset(): a clock that carries across a reset
        # yields one bogus dt on the first step of the next episode.
        self._t0 = None
        return self.inner.reset(context)

    def close(self) -> None:
        return self.inner.close()

    def _flip_vertical(self, state):
        if state is None:
            return None
        flipped = np.array(state, dtype=np.float64, copy=True)
        flipped[2] = -flipped[2]
        if self.complete_state:
            # Bug 3. VZ carries the same up-positive convention as position z on the wire, and
            # every consumer reads it as NED-down -- same inversion, one index over.
            flipped[8] = -flipped[8]
            # SIM_TIME is never populated live. A monotonic clock is the honest substitute: the
            # only consumer differentiates with it, and the wire has no simulation clock to read.
            if self._t0 is None:
                self._t0 = time.monotonic()
            flipped[41] = time.monotonic() - self._t0
        return flipped

    def compute_action(self, context: ActionContext) -> ActionResult:
        live = context.sim is None and context.opponent_sim is None
        if not (self.enabled and live):
            self.passthrough_steps += 1
            return self.inner.compute_action(context)

        self.corrected_steps += 1
        info = dict(context.info)
        my_pd = info.get("my_plane_data")
        tgt_pd = info.get("target_plane_data")
        if isinstance(my_pd, OPlaneData):
            info["my_plane_data"] = _corrected_plane_data(my_pd)
        if isinstance(tgt_pd, OPlaneData):
            info["target_plane_data"] = _corrected_plane_data(tgt_pd)

        own = self._flip_vertical(context.ownship_state)
        tgt = self._flip_vertical(context.target_state)

        observation = context.observation
        if self.observation_rebuild is not None and own is not None and tgt is not None:
            try:
                observation = np.asarray(
                    self.observation_rebuild(own, tgt), dtype=np.float32
                )
            except Exception as exc:
                # A rebuild failure must never end a match: fall back to the platform's own
                # vector, which is wrong on two features but finite and correctly shaped.
                self.observation_rebuild_failures += 1
                if self.observation_rebuild_failures <= 3:
                    print(f"[live_frame_fix] observation rebuild failed "
                          f"({type(exc).__name__}: {exc}) -- using the uncorrected vector",
                          flush=True)

        corrected = ActionContext(
            sim=context.sim,
            opponent_sim=context.opponent_sim,
            ownship_state=own,
            target_state=tgt,
            observation=observation,
            info=info,
        )
        result = self.inner.compute_action(corrected)
        if isinstance(result.info, dict):
            result.info["live_frame_corrected"] = True
        return result
