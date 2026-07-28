# -*- coding: utf-8 -*-
"""real_eagle observation v2 = my_observation.py's live-parity 14 features
+ target speed (15 total).

A SEPARATE module (not an edit to my_observation.py) because real_eagle v3
was still training when this landed: Ray env-runner workers re-import the
observation module from disk at every stage transition, and changing
OBSERVATION_SIZE under a live run's feet would crash it with an obs-shape
mismatch at the next stage. v4+ runs point observation_module at this file;
v3 keeps loading the untouched 14-feature module. Everything else about the
design (and the live-match parity constraints) is documented in
my_observation.py and applies here unchanged.

New feature vs v1, and why only this one:

  14  target speed (vector norm of target velocity, 0-600 m/s -> [-1, 1])

* Live-parity SAFE: the wire protocol carries target velocity (indices 6-8,
  see my_observation.py's docstring); a vector NORM is rotation-invariant, so
  the body-frame(u,v,w)-in-training vs world-frame-in-live difference cancels
  exactly like it does for ownship speed (feature 3). Together with feature 3
  the policy can now estimate the energy/speed advantage that BFM decisions
  (press vs extend) hinge on.
* Closure rate was considered and deliberately NOT added: it needs the
  velocity VECTOR projected onto the line of sight, and the velocity frame
  differs between training (body-frame u/v/w from FighterSim) and live play
  (world/NED frame from the UDP packet). A dot product is NOT rotation-
  invariant across that mismatch, so the same code cannot be correct in both
  contexts -- exactly the train/live divergence trap this observation module
  family exists to avoid. Revisit only if a frame flag or NED-velocity source
  is ever plumbed through both paths.

Keep OBSERVATION_SIZE synchronized with the vector returned by
build_observation().
"""
from __future__ import annotations

import numpy as np

from dogfight.envs.observation import normalize
from dogfight.sim.state_schema import StateIndex, velocity_xyz


OBSERVATION_MODE = "real_eagle15"
OBSERVATION_SIZE = 15
OBSERVATION_LOW = -1.0
OBSERVATION_HIGH = 1.0


def build_observation(ownship_state, target_state, geo_info, wez_config=None):
    """Return the 15-D observation vector as float32.

    Index map:
      0-2   ownship: roll, pitch, yaw
      3     ownship speed (velocity magnitude)
      4     ownship altitude (-D position)
      5-7   relative position: delta_n, delta_e, delta_d
      8-11  geometry: ATA, AA, LOS_az, LOS_el
      12    in_wez flag (-1 / +1)
      13    pursuit score, smooth ATA x range gradient
      14    target speed (velocity magnitude)          <- new in v2
    """
    obs = np.zeros(OBSERVATION_SIZE, dtype=np.float32)

    delta = target_state[:3] - ownship_state[:3]
    distance = geo_info._get_distance(ownship_state, target_state)
    ata = geo_info._get_antenna_train_angle(ownship_state, target_state, False)
    # proj=True (2D), not False: GeoMathUtil's 3D aspect-angle mode has a
    # matrix singularity exactly at 180 deg (head-on) that silently returns 0
    # instead of 180 - verified empirically.
    aa = geo_info._get_aspect_angle(ownship_state, target_state, True)
    az, el = geo_info._get_los_angle(ownship_state, target_state)

    ownship_speed_mps = float(np.linalg.norm(velocity_xyz(ownship_state)))
    target_speed_mps = float(np.linalg.norm(velocity_xyz(target_state)))
    ownship_alt_m = -float(ownship_state[StateIndex.D])

    # Ownship state
    obs[0] = normalize(float(ownship_state[StateIndex.ROLL]),  -180.0, 180.0)
    obs[1] = normalize(float(ownship_state[StateIndex.PITCH]),  -90.0,  90.0)
    obs[2] = normalize(float(ownship_state[StateIndex.YAW]),      0.0, 360.0)
    obs[3] = normalize(ownship_speed_mps,                         0.0, 600.0)
    obs[4] = normalize(ownship_alt_m,                             0.0, 15000.0)

    # Relative position
    obs[5] = normalize(float(delta[0]), -15000.0, 15000.0)
    obs[6] = normalize(float(delta[1]), -15000.0, 15000.0)
    obs[7] = normalize(float(delta[2]),  -8000.0,  8000.0)

    # Geometry
    obs[8]  = normalize(float(ata), -180.0, 180.0)
    obs[9]  = normalize(float(aa),  -180.0, 180.0)
    obs[10] = normalize(float(az),  -180.0, 180.0)
    obs[11] = normalize(float(el),   -90.0,  90.0)

    # WEZ flag: +1 if ownship is inside weapon engagement zone, -1 otherwise.
    # Uses the flat (Phase 1) wez keys deliberately, same as tactical16 - a
    # strict subset of phases 2/3 (COMPETITION_RULES.md #6.3), fine for an
    # observation feature even though update_damage() is phase-aware for the
    # actual damage calculation.
    if wez_config is not None:
        ata_abs = abs(float(ata))
        in_wez = (
            wez_config["min_range_m"] <= distance <= wez_config["max_range_m"]
            and ata_abs <= wez_config["angle_deg"] / 2.0
        )
        obs[12] = 1.0 if in_wez else -1.0
    else:
        obs[12] = -1.0

    # Pursuit score: smooth ATA x range gradient in [-1, 1]
    ata_factor   = max(0.0, 1.0 - abs(float(ata)) / 30.0)
    range_factor = max(0.0, 1.0 - distance / 3000.0)
    pursuit_raw  = ata_factor * range_factor
    obs[13] = 2.0 * pursuit_raw - 1.0

    # Target speed: opponent energy state (see module docstring for why the
    # norm is live-parity safe while closure rate is not).
    obs[14] = normalize(target_speed_mps, 0.0, 600.0)

    return obs


def describe_observation():
    return {
        "mode": OBSERVATION_MODE,
        "size": OBSERVATION_SIZE,
        "features": [
            "ownship_roll_norm",
            "ownship_pitch_norm",
            "ownship_yaw_norm",
            "ownship_speed_norm",
            "ownship_altitude_norm",
            "delta_n_norm",
            "delta_e_norm",
            "delta_d_norm",
            "ata_norm",
            "aa_norm",
            "los_az_norm",
            "los_el_norm",
            "in_wez_flag",
            "pursuit_score",
            "target_speed_norm",
        ],
        "description": (
            "my_observation.py's live-parity 14 features plus target speed "
            "(rotation-invariant velocity norm, live-recoverable). See module "
            "docstring for why closure rate is deliberately absent."
        ),
    }
