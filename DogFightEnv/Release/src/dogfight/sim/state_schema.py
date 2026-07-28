from __future__ import annotations

from enum import IntEnum


class StateIndex(IntEnum):
    N = 0
    E = 1
    D = 2
    ROLL = 3
    PITCH = 4
    YAW = 5
    VX = 6
    VY = 7
    VZ = 8
    KCAS = 12
    FUEL = 23
    SIM_TIME = 41
    LAT = 42
    LON = 43
    ALT = 44
    HEALTH = 45


def position_ned(state):
    return state[StateIndex.N : StateIndex.D + 1]


def attitude_rpy(state):
    return state[StateIndex.ROLL : StateIndex.YAW + 1]


def velocity_xyz(state):
    """Velocity triple - see StateIndex.VX for the training-vs-live frame caveat."""
    return state[StateIndex.VX : StateIndex.VZ + 1]
