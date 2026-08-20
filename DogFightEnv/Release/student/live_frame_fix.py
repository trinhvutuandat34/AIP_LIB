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
BOUNDARY & SCOPE
--------------------------------------------------------------------------------------------

`plane_info_to_state()` lives in `src/dogfight/unreal/policies.py`, inside the hard no-edit
boundary (`src/dogfight/**`, team policy 2026-07-14). This wrapper is the sanctioned route:
student-space, installed at the provider construction site in the entry scripts.

Corrects `ownship_state`/`target_state` (bug 1) and `info["my_plane_data"]`/
`info["target_plane_data"]` (bug 2). Does NOT rebuild `context.observation`, which `policies.py`
computes from the uncorrected state before the provider is called -- so RL and hybrid modes
remain affected by bug 1 on the observation vector specifically. Acceptable only because the
shipped mode is `vptrack`; revisit before shipping any bundle-backed mode.
"""

from __future__ import annotations

import math
import os

import numpy as np

from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult
from dogfight.ai.native_bt import OPlaneData

# Hardcoded in AIP_DCS/BehaviorTree/CPPBehaviorTree.h:18-19 -- must match exactly, it is the
# origin the native BT's own LLAtoCartesian() call uses, not a value we get to choose.
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

    def __init__(self, inner: ActionProvider, enabled: bool | None = None) -> None:
        self.inner = inner
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
        return self.inner.reset(context)

    def close(self) -> None:
        return self.inner.close()

    @staticmethod
    def _flip_vertical(state):
        if state is None:
            return None
        flipped = np.array(state, dtype=np.float64, copy=True)
        flipped[2] = -flipped[2]
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

        corrected = ActionContext(
            sim=context.sim,
            opponent_sim=context.opponent_sim,
            ownship_state=self._flip_vertical(context.ownship_state),
            target_state=self._flip_vertical(context.target_state),
            observation=context.observation,
            info=info,
        )
        result = self.inner.compute_action(corrected)
        if isinstance(result.info, dict):
            result.info["live_frame_corrected"] = True
        return result
