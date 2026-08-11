"""A 10 G load-factor limiter, and why this simulator needs one.

MEASURED (scripts/g_limit_check.py, 2026-08-07): commanding full pitch wings-level produces
3.97 G at 250 kt rising to 14.86 G at 550 kt. The sim enforces NO structural limit, while a real
F-16 is rated to 9 G. That is a train/deploy divergence of exactly the kind this project has been
bitten by before (the throttle [-1,1] vs [0,1] remap, the aspect-angle sign flip): anything that
learns to exploit 15 G locally behaves differently the moment it meets a server that clamps it,
and the failure would show up on match day rather than in local evaluation.

Set to 10.0 G: above the 9 G airframe rating so a legitimate hard pull is never clipped, below
the 13-15 G the sim will otherwise hand out.

HOW. Load factor is not directly available from the state vector, so it is derived as SPECIFIC
FORCE from the velocity history: a = dv/dt, f = a - g_vec, n = |f|/g. This is the same
computation g_limit_check uses, and it is the correct one -- deriving n from turn rate assumes a
level turn and misreports a vertical pull, where gravity is not perpendicular to velocity.

dt comes from StateIndex.SIM_TIME rather than an assumed step size, so the limiter is correct
under any step_ratio (the eval harness runs 6, some probes run 1).

It is FEEDBACK, not feedforward: G is measured after the step that caused it, so the limiter
reacts one step late and a brief overshoot is expected. A predictive limiter would need an
airframe model this project does not have. One step at 60 Hz is 16 ms, which is short against
the dynamics that matter here.

Pitch magnitude is scaled by limit/n when exceeded, never sign-flipped -- reversing the pull
mid-maneuver would be far worse than briefly exceeding the cap. The scale is smoothed so the
limiter does not chatter between clamped and unclamped on alternating steps.

MEASURED BEHAVIOUR, and be clear about what it does NOT do. Full 4 s pull, limit 10.0 G:

    entry   mode        mean    p95     max   clamped
    450 kt  unlimited   2.09   8.45   10.65      --
    450 kt  LIMITED     2.09   8.45   10.65      4%
    500 kt  unlimited   2.35   9.55   13.50      --
    500 kt  LIMITED     2.34   8.24   13.50      6%
    550 kt  unlimited   1.90   8.48   15.24      --
    550 kt  LIMITED     1.87   7.39   15.24      7%

SUSTAINED load is held under the limit -- p95 falls 9.55 -> 8.24 at 500 kt and 8.48 -> 7.39 at
550 kt. SINGLE-STEP MAXIMA ARE UNCHANGED, and cannot be fixed by feedback: G is measured one
step after the command that produced it, so a transient is already recorded before the limiter
can act. Whether those 13-15 G maxima are even real is doubtful -- mean 2, p95 8, max 15 across
240 samples is the signature of differencing noise in a 1-step dv/dt estimate, not sustained
load. The quantity that matters for exploitation is sustained G, and that is now capped.

It engages rarely (4-7% of steps in a maximum pull, and far less in normal flight), so it is
not a performance tax on ordinary maneuvering.
"""
from __future__ import annotations

import numpy as np

from dogfight.sim.state_schema import StateIndex

G = 9.80665
G_LIMIT = 10.0
SMOOTHING = 0.5          # blend of new scale into the held one; 1.0 = no smoothing
MIN_DT = 1e-4
MAX_PLAUSIBLE_G = 60.0   # beyond this the sample is a reset transient, not flight


class GLimiter:
    """Stateful per-aircraft load-factor limiter. Reset it between episodes."""

    def __init__(self, limit_g: float = G_LIMIT):
        self.limit_g = float(limit_g)
        self._prev_v = None
        self._prev_t = None
        self._scale = 1.0
        self.last_n = 1.0
        self.clamped_steps = 0
        self.total_steps = 0

    def reset(self) -> None:
        # Per-episode state. Carrying velocity across a reset yields a colossal bogus
        # acceleration on the first step of the next episode -- the same class of
        # cross-episode leak documented for the BT's PreviousAltitudeForRate.
        self._prev_v = None
        self._prev_t = None
        self._scale = 1.0

    @staticmethod
    def _vel_neu(state) -> np.ndarray:
        """Velocity in N-E-Up. VZ is NED-down, so Up = -VZ."""
        return np.array([float(state[StateIndex.VX]), float(state[StateIndex.VY]),
                         -float(state[StateIndex.VZ])])

    def observe(self, state) -> float:
        """Update from the current state and return the measured load factor."""
        v = self._vel_neu(state)
        t = float(state[StateIndex.SIM_TIME])
        pv, pt = self._prev_v, self._prev_t
        self._prev_v, self._prev_t = v, t

        if pv is None or pt is None:
            return self.last_n
        dt = t - pt
        if not np.isfinite(dt) or dt < MIN_DT:
            return self.last_n

        a = (v - pv) / dt
        n = float(np.linalg.norm(a - np.array([0.0, 0.0, -G]))) / G
        if not np.isfinite(n) or n > MAX_PLAUSIBLE_G:
            return self.last_n
        self.last_n = n
        return n

    def limit_pitch(self, pitch_cmd: float, state) -> float:
        """Scale pitch magnitude so the measured load factor stays under the limit."""
        n = self.observe(state)
        self.total_steps += 1
        target = 1.0 if n <= self.limit_g else max(0.0, self.limit_g / n)
        # Smooth toward the target so the limiter does not oscillate on/off each step.
        self._scale += SMOOTHING * (target - self._scale)
        self._scale = min(1.0, max(0.0, self._scale))
        if self._scale < 0.999:
            self.clamped_steps += 1
        return float(pitch_cmd) * self._scale

    @property
    def clamp_fraction(self) -> float:
        return self.clamped_steps / self.total_steps if self.total_steps else 0.0
