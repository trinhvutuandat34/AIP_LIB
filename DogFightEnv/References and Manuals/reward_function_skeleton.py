"""
JSBSim Dogfight Reward Function Skeleton
=========================================

Implements the 5-term reward decomposition from Part 7 of
BFM_ACM_Reward_Engineering_Reference.md, with per-curriculum-stage
weight presets matching Part 8 of that same doc. Intended as a
starting point for `my_reward.py` in the Top Gun Challenge starter kit.

ADAPT BEFORE USE — three things almost certainly need changing:
  1. State key names below (`_get` access pattern) to match whatever
     `my_obs.py` / your env wrapper actually outputs.
  2. Angle sign conventions — verify ATA/aspect sign against your
     own obs pipeline before trusting `positional_advantage()`.
  3. Scale constants (ps_scale, radius_scale, rate_scale, envelope
     ranges) — the defaults below are order-of-magnitude placeholders,
     not tuned to the F-16/FA-50 JSBSim models specifically.

Units: angles in degrees, distance in feet, speed in ft/sec,
altitude in ft, time in seconds — matches typical JSBSim property units.

Expected `state` structure (a plain dict; adjust to taste):
    state = {
        "own":   {"alt_ft", "vtrue_fps", "load_factor_g", "heading_deg"},
        "enemy": {"alt_ft", "vtrue_fps", "load_factor_g", "heading_deg"},
        "ata_deg":     Antenna Train Angle (own nose -> LOS-to-enemy),
        "aspect_deg":  Aspect Angle (enemy nose -> LOS-to-own aircraft).
                       NOTE: in this project's actual GeoMathUtil convention,
                       0 deg = you're at their six (best), 180 deg = nose-on
                       (worst) -- see positional_advantage()'s docstring.
        "hca_deg":     Heading Crossing Angle (optional, unused below
                        but exposed since your project already tracks it),
        "range_ft":    straight-line distance,
        "closure_fps": range rate, negative = closing,
        "own_turn_dir" / "enemy_turn_dir": +1 right / -1 left, sampled
                        at merge (only needed once w_geometry > 0),
        "done", "win", "loss": episode-end flags,
    }
`prev_state` is the same structure one timestep earlier (only "own"
is required in prev_state, for the finite-difference Ps estimate).
"""

from dataclasses import dataclass
import math

G = 32.2  # ft/sec^2


# ---------------------------------------------------------------------------
# 1. Config — one weight block per curriculum stage (Part 8 of the reference doc)
# ---------------------------------------------------------------------------

@dataclass
class RewardConfig:
    # Part 7 term weights
    w_position: float = 1.0
    w_range: float = 0.5
    w_energy: float = 0.3
    w_geometry: float = 0.0        # off until curriculum stage 3+
    w_terminal: float = 1.0

    # positional sub-weights (ATA vs Aspect Angle)
    w_ata: float = 0.5
    w_aspect: float = 0.5

    # engagement envelope, feet — adjust to your weapon/sensor model
    min_range_ft: float = 500.0
    max_range_ft: float = 9000.0

    # "attacker" rewards Ps > 0; "defender" rewards controlled Ps < 0
    # (Defensive Spiral, Part 6/8 — see Stage 5 note)
    energy_role: str = "attacker"

    # terminal reward magnitudes
    win_reward: float = 100.0
    loss_reward: float = -100.0
    timeout_reward: float = 0.0


# Curriculum presets mirroring Part 8. train.yaml can select one of
# these by stage number; weight magnitudes are starting points, not
# tuned values — the relative emphasis pattern is what matters.
STAGE_CONFIGS = {
    0: RewardConfig(  # Control primitives — no dogfight terms active
        w_position=0.0, w_range=0.0, w_energy=0.0, w_geometry=0.0, w_terminal=0.0),
    1: RewardConfig(  # Pursuit-curve control
        w_position=1.0, w_range=1.0, w_energy=0.2, w_geometry=0.0),
    2: RewardConfig(  # Yo-Yo energy trading
        w_position=1.0, w_range=0.6, w_energy=0.6, w_geometry=0.1),
    3: RewardConfig(  # Merge & lead-turn
        w_position=1.0, w_range=0.5, w_energy=0.4, w_geometry=0.6),
    4: RewardConfig(  # Scissors (energy contest)
        w_position=0.8, w_range=0.4, w_energy=0.9, w_geometry=0.3),
    5: RewardConfig(  # Defensive survival — energy role flips
        w_position=0.6, w_range=0.3, w_energy=0.2, w_geometry=0.1,
        w_terminal=1.5, energy_role="defender"),
    6: RewardConfig(  # Free-play league — shaping terms annealed down
        w_position=0.3, w_range=0.2, w_energy=0.2, w_geometry=0.2, w_terminal=2.0),
}


# ---------------------------------------------------------------------------
# 2. Geometry / energy primitives (Parts 1, 3, 4 of the reference doc)
# ---------------------------------------------------------------------------

def deg2rad(d: float) -> float:
    return d * math.pi / 180.0


def specific_energy(alt_ft: float, vtrue_fps: float) -> float:
    """Es = h + V^2 / (2g)   (Part 4)"""
    return alt_ft + (vtrue_fps ** 2) / (2.0 * G)


def specific_excess_power_fd(es_now: float, es_prev: float, dt: float) -> float:
    """
    Finite-difference Ps estimate: Ps ~ dEs/dt.
    Use this if thrust/drag aren't directly exposed in your obs.
    If they are, prefer the physics form Ps = (T - D) * V / W (Part 4) —
    it won't be corrupted by simulation-step noise the way a raw
    finite difference can be at very small dt.
    """
    if dt <= 0:
        return 0.0
    return (es_now - es_prev) / dt


def turn_rate_radius(vtrue_fps: float, load_factor_g: float):
    """
    Precise level-turn formulas (Part 3):
        R     = V^2 / (g * sqrt(n^2 - 1))
        omega = g * sqrt(n^2 - 1) / V        [rad/sec]
    Returns (radius_ft, rate_deg_per_sec).
    """
    n = max(load_factor_g, 1.0001)  # guard against sqrt of <=0 at n<=1
    root = math.sqrt(max(n * n - 1.0, 0.0))
    if root == 0.0 or vtrue_fps <= 0.0:
        return float("inf"), 0.0
    radius_ft = (vtrue_fps ** 2) / (G * root)
    rate_rad_s = (G * root) / vtrue_fps
    return radius_ft, math.degrees(rate_rad_s)


def classify_pursuit_mode(ata_deg: float, tol_deg: float = 10.0) -> str:
    """
    Rough pursuit-mode classifier (Part 2): nose ahead of LOS = "lead",
    on it = "pure", behind it = "lag". Sign convention here assumes
    positive ATA = nose ahead of LOS — verify against your obs pipeline
    and flip if needed.
    """
    if abs(ata_deg) <= tol_deg:
        return "pure"
    return "lead" if ata_deg > 0 else "lag"


def classify_engagement_geometry(own_turn_dir: int, enemy_turn_dir: int) -> str:
    """
    Heuristic one-circle / two-circle classifier (Part 5).
    +1 = turning right, -1 = turning left, sampled at/just after merge.
    Opposite signs -> turning toward each other -> two-circle (nose-to-nose).
    Same sign -> sharing one circle -> one-circle (nose-to-tail).
    This needs real merge-direction tracking in your env to be
    meaningful — validate against logged merges before trusting it
    as a reward-conditioning signal, it's the least battle-tested
    piece of this skeleton.
    """
    if own_turn_dir == 0 or enemy_turn_dir == 0:
        return "one_circle"  # no data yet; harmless default
    return "two_circle" if own_turn_dir != enemy_turn_dir else "one_circle"


# ---------------------------------------------------------------------------
# 3. Individual reward terms (Part 7, items 1-4)
# ---------------------------------------------------------------------------

def positional_advantage(ata_deg: float, aspect_deg: float, cfg: RewardConfig) -> float:
    """
    Term #1. Rewards low ATA (you're tracking them) and low Aspect Angle
    (you're near their 6 o'clock). Cosine-based -> smooth, bounded to
    [-1, 1], no singularities at 0deg/180deg.

    SIGN CONVENTION (verified, not assumed): this project's actual geometry
    code (GeoMathUtil._get_aspect_angle(proj=True) in DogFightEnv/Release,
    the exact call student/my_reward.py's "position" term and
    single_agent_env.py's final_aa_deg both use) returns aspect_deg=0 when
    YOU are at the TARGET'S six o'clock (best) and aspect_deg=180 when the
    target is nose-on to you (worst) -- verified 2026-07-10 by hand-tracing
    a concrete example (target flying straight at ownship -> the function
    returns 180, not 0). This is the OPPOSITE of the generic BFM-doctrine
    convention described in Part 1 of the reference doc (0=nose-on,
    180=six-o'clock) and of this function's original formula. Do not flip
    this back without re-verifying against GeoMathUtil directly -- the
    native C++ BT's MyAspectAngle_Degree uses the doctrine convention
    instead, so the two halves of this codebase disagree with each other;
    this function must match the Python side it actually reads from.
    """
    r_ata = math.cos(deg2rad(ata_deg))          # +1 when ATA = 0 deg
    r_aspect = math.cos(deg2rad(aspect_deg))     # +1 when Aspect = 0 deg (this project's convention)
    return cfg.w_ata * r_ata + cfg.w_aspect * r_aspect


def range_closure_shaping(range_ft: float, closure_fps: float, cfg: RewardConfig,
                           closure_scale: float = 200.0) -> float:
    """
    Term #2. Outside the engagement envelope: reward closing.
    Inside min range: reward opening back up (overshoot avoidance,
    mirrors the lead-pursuit caution in Part 2). Inside the envelope:
    small flat bonus. tanh keeps it smooth and bounded.
    """
    if range_ft > cfg.max_range_ft:
        return math.tanh(-closure_fps / closure_scale)   # want closure_fps < 0
    if range_ft < cfg.min_range_ft:
        return math.tanh(closure_fps / closure_scale)     # want closure_fps > 0
    return 0.1


def energy_term(ps_estimate: float, cfg: RewardConfig, ps_scale: float = 200.0) -> float:
    """
    Term #3. Normalizes Ps by a rough scale constant (200 ft/sec is the
    order-of-magnitude climb-rate example used in Part 4 — retune to
    your actual aircraft's typical Ps range) and squashes with tanh.
    Sign flips for the defender role per the Stage 5 note in Part 8.
    """
    sign = 1.0 if cfg.energy_role == "attacker" else -1.0
    return sign * math.tanh(ps_estimate / ps_scale)


def geometry_term(radius_ft: float, rate_deg_s: float, geometry: str,
                   radius_scale: float = 3000.0, rate_scale: float = 20.0) -> float:
    """
    Term #4 (optional/advanced, curriculum stage 3+). Rewards turn
    *rate* in a one-circle fight and (inverse) turn *radius* in a
    two-circle fight, per Part 5.
    """
    if geometry == "one_circle":
        return math.tanh(rate_deg_s / rate_scale)
    return math.tanh((radius_scale - radius_ft) / radius_scale)


def terminal_reward(done: bool, win: bool, loss: bool, cfg: RewardConfig) -> float:
    """Term #5."""
    if not done:
        return 0.0
    if win:
        return cfg.win_reward
    if loss:
        return cfg.loss_reward
    return cfg.timeout_reward


# ---------------------------------------------------------------------------
# 4. Top-level entry point — this is what my_reward.py should call
# ---------------------------------------------------------------------------

def compute_reward(state: dict, prev_state: dict, cfg: RewardConfig,
                    dt: float = 1.0 / 30.0):
    """
    Returns (total_reward, components_dict).

    Always log components_dict during training — a 5-term shaped
    reward is very easy to misweight silently (e.g. energy term
    dominating position term without you noticing), and per-term
    logging is the fastest way to catch that early.
    """
    own, enemy = state["own"], state["enemy"]
    prev_own = prev_state["own"]

    es_now = specific_energy(own["alt_ft"], own["vtrue_fps"])
    es_prev = specific_energy(prev_own["alt_ft"], prev_own["vtrue_fps"])
    ps = specific_excess_power_fd(es_now, es_prev, dt)

    radius_ft, rate_deg_s = turn_rate_radius(own["vtrue_fps"], own["load_factor_g"])

    geometry = "one_circle"
    if cfg.w_geometry > 0:
        geometry = classify_engagement_geometry(
            state.get("own_turn_dir", 0), state.get("enemy_turn_dir", 0))

    r_position = positional_advantage(state["ata_deg"], state["aspect_deg"], cfg)
    r_range = range_closure_shaping(state["range_ft"], state["closure_fps"], cfg)
    r_energy = energy_term(ps, cfg)
    r_geometry = geometry_term(radius_ft, rate_deg_s, geometry)
    r_terminal = terminal_reward(state.get("done", False), state.get("win", False),
                                  state.get("loss", False), cfg)

    total = (cfg.w_position * r_position
             + cfg.w_range * r_range
             + cfg.w_energy * r_energy
             + cfg.w_geometry * r_geometry
             + cfg.w_terminal * r_terminal)

    components = {
        "position": r_position, "range": r_range, "energy": r_energy,
        "geometry": r_geometry, "terminal": r_terminal,
        "ps_estimate": ps, "turn_radius_ft": radius_ft, "turn_rate_deg_s": rate_deg_s,
        "geometry_mode": geometry, "total": total,
    }
    return total, components


# ---------------------------------------------------------------------------
# 5. Minimal smoke test — `python reward_function_skeleton.py` to sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = STAGE_CONFIGS[2]  # Yo-Yo energy-trading stage

    prev_state = {
        "own": {"alt_ft": 20000.0, "vtrue_fps": 800.0, "load_factor_g": 3.0, "heading_deg": 0.0},
    }
    state = {
        "own": {"alt_ft": 20001.0, "vtrue_fps": 800.5, "load_factor_g": 4.5, "heading_deg": 10.0},
        "enemy": {"alt_ft": 19500.0, "vtrue_fps": 780.0, "load_factor_g": 2.0, "heading_deg": 170.0},
        "ata_deg": 15.0, "aspect_deg": 150.0,
        "range_ft": 4000.0, "closure_fps": -120.0,
        "own_turn_dir": 1, "enemy_turn_dir": -1,
        "done": False, "win": False, "loss": False,
    }

    total, comps = compute_reward(state, prev_state, cfg, dt=1 / 30)
    print(f"Stage 2 total reward: {total:.4f}")
    for k, v in comps.items():
        print(f"  {k}: {v}")
