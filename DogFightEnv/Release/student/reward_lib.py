# -*- coding: utf-8 -*-
"""BFM/ACM reward-shaping primitives for student/my_reward.py.

Holds positional_advantage() plus WEZ_PHASES/wez_pursuit_multipliers() (added
2026-07-15). The broader set from the reference (energy/Ps, turn-rate/radius,
one-circle/two-circle geometry, range-closure) lives, un-ported, in
`D:\\AIP\\reward_function_skeleton.py` (theory: `D:\\AIP\\
BFM_ACM_Reward_Engineering_Reference.md`). Those weren't kept here as dead
code: each needs state this project doesn't expose yet (closure rate, load
factor, live turn-direction-at-merge), and re-porting a formula from the
skeleton in SI units is a few lines when the state to feed it actually exists.
See memory/project_reward_reference_analysis.md for the full cross-check.
"""
from __future__ import annotations

import math

FEET_TO_METER = 0.3048
G_ACCEL = 9.80665  # standard gravity, m/s^2 (specific-energy conversion)

# Phase-widening WEZ schedule, byte-exact recovery (via __pycache__/*.cpython-313.pyc
# decompilation, since the 2026-07-15 accidental full-tree revert -- see
# memory/project_bulk_revert_regression_2026_07_15.md -- wiped the platform's own
# src/dogfight/config.py copy of this) of what the deck's phased-cone rule (LOS<1/2/3
# deg widening at 100s/150s) resolved to in code as of 2026-07-12. angle_deg here is
# the FULL cone width (2x the rule text's half-angle LOS figure), consistent across
# all three phases -- not a bug, just this codebase's convention. Kept in student
# space rather than src/dogfight/config.py (hard no-edit boundary, team policy since
# 2026-07-14) -- this is pure reference data + a pure function, no platform coupling.
WEZ_PHASES = [
    {"min_time_s": 0.0, "angle_deg": 2.0, "min_range_m": 500 * FEET_TO_METER,
     "max_range_m": 3000 * FEET_TO_METER, "damage_coefficient": 1.0},
    {"min_time_s": 100.0, "angle_deg": 4.0, "min_range_m": 500 * FEET_TO_METER,
     "max_range_m": 3500 * FEET_TO_METER, "damage_coefficient": 0.3},
    {"min_time_s": 150.0, "angle_deg": 6.0, "min_range_m": 500 * FEET_TO_METER,
     "max_range_m": 4000 * FEET_TO_METER, "damage_coefficient": 0.1},
]


def wez_pursuit_multipliers(phases: list[dict] | None, elapsed_s: float) -> tuple[float, float]:
    """Return (range_mult, angle_mult) scaling the base (phase-0) pursuit reward
    envelope to whichever phase the match clock has reached, so the pursuit
    shaping gradient widens late-match the same way the real WEZ cone does.

    Byte-exact recovery of the pre-revert src/dogfight/config.py function of the
    same name (phases assumed ordered narrowest/earliest-first; the loop keeps
    the last phase whose min_time_s has been reached).
    """
    if not phases:
        return (1.0, 1.0)
    base = phases[0]
    widest = base
    for phase in phases:
        if elapsed_s >= phase.get("min_time_s", 0.0):
            widest = phase
    base_range = base.get("max_range_m", 0.0)
    base_angle = base.get("angle_deg", 0.0)
    range_mult = widest["max_range_m"] / base_range if base_range > 0 else 1.0
    angle_mult = widest["angle_deg"] / base_angle if base_angle > 0 else 1.0
    return (range_mult, angle_mult)


def match_wez_phase(
    phases: list[dict] | None, dis_m: float, ata_deg: float, elapsed_s: float
) -> dict | None:
    """Return the WEZ phase governing a shot at this geometry/time, or None if no
    phase's range+angle envelope currently contains it.

    Added 2026-07-16 (student/my_reward.py's damage term is now phase-aware, see
    that module's docstring for why: update_damage() mutates health inside the
    closed FighterSim object the instant it runs, so there is no way to correct
    win/loss timing from outside src/dogfight -- only the reward signal can be
    fixed from student space). Reconstructed FRESH from the documented rule
    (COMPETITION_RULES.md Sec6.2's "narrowest-qualifying-phase-wins: a Phase-1
    -quality shot pays Phase-1 damage even late"), NOT decompiled -- no bytecode
    cache of the platform's own equivalent survived the 2026-07-15 revert, unlike
    WEZ_PHASES/wez_pursuit_multipliers above. Only a phase whose min_time_s has
    been reached is eligible; among eligible phases whose band contains the
    geometry, the one with the highest damage_coefficient (narrowest) wins.
    """
    best = None
    for phase in phases or []:
        if elapsed_s < phase.get("min_time_s", 0.0):
            continue
        if not (phase["min_range_m"] <= dis_m <= phase["max_range_m"]):
            continue
        if abs(ata_deg) > phase["angle_deg"] / 2.0:
            continue
        if best is None or phase["damage_coefficient"] > best["damage_coefficient"]:
            best = phase
    return best


def wez_damage_estimate(
    phases: list[dict] | None, dis_m: float, ata_deg: float, elapsed_s: float, delta_t: float
) -> float:
    """Phase-aware damage for delta_t seconds of continuous tracking at this
    geometry -- matches update_damage()'s live formula
    ((max_range_m - dis_m) / (max_range_m - min_range_m)) * delta_t, with the
    phase's damage_coefficient restored (the platform's current flat WEZ has no
    coefficient term at all: single cone, implicit coefficient 1.0). Returns 0.0
    outside every phase's envelope. See match_wez_phase()'s docstring for scope
    and provenance -- this is a reward-shaping estimate, not the authoritative
    damage/health value; it does not affect episode termination.
    """
    phase = match_wez_phase(phases, dis_m, ata_deg, elapsed_s)
    if phase is None:
        return 0.0
    base_range_m = phase["max_range_m"] - phase["min_range_m"]
    if base_range_m <= 0:
        return 0.0
    return ((phase["max_range_m"] - dis_m) / base_range_m) * delta_t * phase["damage_coefficient"]


def specific_energy(altitude_m: float, speed_mps: float) -> float:
    """Energy height E_s = h + V^2 / (2g), in meters -- the altitude an aircraft
    could reach by trading all of its kinetic energy for potential. The standard
    BFM 'energy state' scalar that collapses altitude and airspeed into one
    comparable number. Uses true airspeed magnitude (velocity_xyz norm); the
    reward runs only in training, so the body-frame(u,v,w)-vs-NED velocity-frame
    caveat that constrains the OBSERVATION does NOT apply here -- a magnitude is
    frame-invariant anyway, and no live packet ever reaches this code.
    """
    return altitude_m + (speed_mps * speed_mps) / (2.0 * G_ACCEL)


def energy_advantage(
    own_alt_m: float,
    own_speed_mps: float,
    tgt_alt_m: float,
    tgt_speed_mps: float,
    energy_ref_m: float = 1000.0,
) -> float:
    """Bounded [-1, 1] energy-state advantage of ownship over the target.

    +1 when ownship holds >> energy_ref_m more energy height than the target (a
    decisive edge -- you dictate the vertical, can convert altitude to closure
    or extend at will), -1 for the reverse, ~0 when matched. tanh keeps it
    smooth and saturating so a large gap can't dominate the geometry/damage
    terms; energy_ref_m sets the 'meaningful edge' scale (~1000 m of energy
    height is a strong advantage -- e.g. a 1 km altitude lead, or ~50 m/s of
    speed at combat altitude).

    This is the ONE BFM axis the geometry terms (pursuit/position/advantage, all
    angle x range) never touch. It needs no time derivative, so unlike a P_s
    (dE_s/dt) rate term it holds NO cross-step state -- safe for Ray's
    vectorized / multi-worker env runners, where a module-level 'previous
    energy' would corrupt across interleaved episodes. Learnable from the current
    15-feature observation: the policy sees ownship alt+speed, target speed, and
    delta_d (relative altitude), which together reconstruct both E_s values.

    CAUTION (why my_reward.py defaults energy_scale to 0.0, opt-in per stage):
    rewarding energy advantage can, at too high a weight, teach zoom-and-run
    energy hoarding -- the same disengagement failure mode the 2026-07-12 audit
    found in the ATA guard. It is self-limiting here (differential, not
    absolute: climbing away from a disengaged opponent who isn't bleeding earns
    nothing, while forgoing the pursuit/damage/terminal rewards that dominate),
    but keep the scale modest and only enable it where terminal win/loss still
    dominates the return. Range-gating (activate only inside the fight) is a
    documented future option if hoarding ever shows up in engagement replays.
    """
    if energy_ref_m <= 0.0:
        return 0.0
    delta = (
        specific_energy(own_alt_m, own_speed_mps)
        - specific_energy(tgt_alt_m, tgt_speed_mps)
    )
    return math.tanh(delta / energy_ref_m)


def positional_advantage(
    ata_deg: float, aspect_deg: float, w_ata: float = 0.5, w_aspect: float = 0.5
) -> float:
    """Rewards low ATA (you're tracking them) and low Aspect Angle (you're near
    their 6 o'clock). Cosine-based -> smooth, bounded to [-1, 1], no
    singularities at 0deg/180deg.

    SIGN CONVENTION (verified, not assumed): this project's actual geometry
    code (GeoMathUtil._get_aspect_angle(proj=True), the exact call
    student/my_reward.py's "position" term and single_agent_env.py's
    final_aa_deg both use) returns aspect_deg=0 when YOU are at the TARGET'S
    six o'clock (best) and aspect_deg=180 when the target is nose-on to you
    (worst) -- verified 2026-07-10 by hand-tracing a concrete example (target
    flying straight at ownship -> the function returns 180, not 0). This is
    the OPPOSITE of the generic BFM-doctrine convention (0=nose-on,
    180=six-o'clock). The native C++ BT's MyAspectAngle_Degree uses the
    doctrine convention instead, so the two halves of this codebase disagree
    with each other; this function matches the Python side it actually reads
    from -- don't flip it without re-verifying against GeoMathUtil directly.

    Overlaps with my_reward.py's existing "pursuit" (ATA x range) and
    "position" (AA x range) terms -- this is a smoother, range-independent,
    combined version of the same idea. Its weight (advantage_scale) is 0.0 by
    default for exactly that reason; don't raise it without also dialing those
    two down, or the three stack.
    """
    r_ata = math.cos(math.radians(ata_deg))       # +1 when ATA = 0 deg
    r_aspect = math.cos(math.radians(aspect_deg))  # +1 when Aspect = 0 deg (this project's convention)
    return w_ata * r_ata + w_aspect * r_aspect


if __name__ == "__main__":
    # Sign-regression guard: six o'clock (aspect=0) must score above nose-on (aspect=180).
    nose_on = positional_advantage(ata_deg=15.0, aspect_deg=170.0)
    six_oclock = positional_advantage(ata_deg=15.0, aspect_deg=10.0)
    print(f"positional_advantage(nose-on target)  = {nose_on:.4f}  (expect < 0)")
    print(f"positional_advantage(at target's six) = {six_oclock:.4f}  (expect > 0)")
    assert six_oclock > nose_on, "sign convention regression: six o'clock should score higher than nose-on"

    # Energy-advantage guards: sign, symmetry, saturation, and the altitude<->speed
    # trade (E_s treats 1 km of altitude and the equivalent airspeed as the same edge).
    higher = energy_advantage(6000.0, 200.0, 5000.0, 200.0)   # +1 km altitude lead
    lower = energy_advantage(5000.0, 200.0, 6000.0, 200.0)    # mirror -> negative
    matched = energy_advantage(5000.0, 200.0, 5000.0, 200.0)  # identical -> 0
    faster = energy_advantage(5000.0, 250.0, 5000.0, 200.0)   # speed edge, same alt
    print(f"energy_advantage(+1km alt)  = {higher:.4f}  (expect > 0)")
    print(f"energy_advantage(-1km alt)  = {lower:.4f}  (expect < 0)")
    print(f"energy_advantage(matched)   = {matched:.4f}  (expect ~0)")
    print(f"energy_advantage(+50 m/s)   = {faster:.4f}  (expect > 0)")
    assert higher > 0.0 > lower, "energy sign: more energy must score positive"
    assert abs(higher + lower) < 1e-9, "energy symmetry: mirror geometry must negate"
    assert abs(matched) < 1e-9, "matched energy must be ~0"
    assert faster > 0.0, "speed edge at equal altitude must score positive"
    assert -1.0 <= higher <= 1.0 and -1.0 <= lower <= 1.0, "energy_advantage must stay bounded"
    # energy_ref_m<=0 must be inert, never divide-by-zero.
    assert energy_advantage(9000.0, 300.0, 1000.0, 100.0, energy_ref_m=0.0) == 0.0
    print("reward_lib.py smoke test OK")
