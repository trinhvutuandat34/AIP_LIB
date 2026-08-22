"""Drive the organizers' cutoff model (`unreal_bt_client.exe`) as a local opponent.

WHY THIS EXISTS. The cutoff baseline ships as a standalone UDP *client*, so the only way the
organizers intended it to be run is against a live `DogFightViewer.exe` -- one match at a time,
with a human watching. That cannot produce a win rate. Worse, the obvious shortcut does not work
either: the cutoff tree cannot be loaded into `AIP_BASE_target.dll`, because 28 of the 42 node
types it uses (`SelectEFSF`, `MergeTurn`, `DECO_SBFMCheck`, `Support_OBFM`, ...) do not exist in
this project's node library at all. The two trees are divergent forks of the same framework.

WHAT THIS DOES. Implements the *server* half of the Unreal wire protocol (`src/dogfight/unreal/
protocol.py`) against a loopback socket, so the real cutoff binary becomes an ordinary
`ActionProvider` and can be dropped into `run_local_dogfight.py` / `eval_v5_vs_bt.py` as a target
backend. That makes the cutoff scoreable headless, at N=30, on the existing metric.

FIDELITY -- what is exact, and what is not.

Exact. `plane_info_to_state()` maps PlaneInfo pos/rot/vel onto state[0:9], and the local sim's
state[0:9] is (N,E,D metres, roll/pitch/yaw deg, body u/v/w m/s). This provider is the inverse of
that mapping, so the bytes the binary receives here are the same bytes it receives from Unreal.
Handshake, frame indexing and CMD decoding were verified against a captured real-server session
(`logs/unreal_packets/rx_packets_20260514_155232_15208.jsonl`).

Approximate, and it matters when reading results:
  * Over the wire the BT only ever sees position, attitude, speed magnitude and force side --
    `StepWithPlaneData`, not the full 51-float FDM the local BT path gets. That is a property of
    the real interface, so the cutoff is not disadvantaged here; but our own side, run locally,
    IS getting richer input than it would in a real match. Local numbers are optimistic for us.
  * The binary defaults to `--action-repeat 6` (its own choice, not a rule), so it re-ticks its
    tree at 10 Hz. This env calls providers every 60 Hz frame, so our side decides 6x more often
    than the cutoff here. CORRECTED 2026-08-22: this bullet used to claim that asymmetry "would
    NOT" exist in a real match. It would. COMPETITION_RULES Sec 4 (re-read 2026-08-20) makes the
    60 Hz answer-rate and the 0.1667 s per-decision compute cap two separate rules, and neither
    mandates action-repeat 6; the shipped submission sets `ACTION_REPEAT = 1`. So the local rig
    reproduces the real decision-rate relationship rather than flattering us, and the cutoff
    results should not be discounted for it. Use `action_repeat=1` to measure the cutoff without
    its own self-imposed handicap.

The binary is restarted per episode, mirroring `_recycle_native_bts()`: its tree carries state
(CoolTimer, blackboard) and episodes must stay independent.
"""

from __future__ import annotations

import os
import socket
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult, clip_action

# Wire formats -- must stay byte-identical to src/dogfight/unreal/protocol.py.
_PLANE_INFO = struct.Struct("<iQb3f3f3f")
_CMD = struct.Struct("<ibQffff")
_SET_PLANE_ID = struct.Struct("<ib")
_MSG_TYPE = struct.Struct("<i")

_MT_CMD = 6
_MT_SET_PLANE_ID = 9

_CUTOFF_PLANE_ID = 0
_ENEMY_PLANE_ID = 1

_DEFAULT_EXE_CANDIDATES = (
    _ROOT / "unreal_bt_client.exe",
    Path(r"D:\AIP1\AIP\unreal_bt_client.exe"),
    Path(r"D:\AIP1\AIP\컷오프모델-20260819T132623Z-1-001\컷오프모델\unreal_bt_client.exe"),
)


def default_exe_path() -> Path:
    for candidate in _DEFAULT_EXE_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "unreal_bt_client.exe not found. Pass exe_path= explicitly. Looked in: "
        + ", ".join(str(c) for c in _DEFAULT_EXE_CANDIDATES)
    )


class CutoffProvider(ActionProvider):
    """ActionProvider backed by the real cutoff binary over a loopback UDP socket."""

    def __init__(
        self,
        exe_path: str | os.PathLike | None = None,
        action_repeat: int = 6,
        own_force_side: int = 1,
        target_force_side: int = 2,
        team_name: str = "EasyModeCutoff",
        recv_timeout_sec: float = 2.0,
        handshake_timeout_sec: float = 10.0,
        verbose: bool = False,
    ) -> None:
        self.exe_path = Path(exe_path) if exe_path is not None else default_exe_path()
        if not self.exe_path.exists():
            raise FileNotFoundError(f"cutoff binary not found: {self.exe_path}")
        self.action_repeat = int(action_repeat)
        self.own_force_side = int(own_force_side)
        self.target_force_side = int(target_force_side)
        self.team_name = team_name
        self.recv_timeout_sec = float(recv_timeout_sec)
        self.handshake_timeout_sec = float(handshake_timeout_sec)
        self.verbose = bool(verbose)

        self._sock: socket.socket | None = None
        self._proc: subprocess.Popen | None = None
        self._client_addr: tuple[str, int] | None = None
        self._frame = 0
        self._last_action = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)

        # Diagnostics -- a silent stall here would look like a tactical result, so count it.
        # A cutoff that never received a packet, or that timed out every step and held its
        # opening command, would fly straight and read as a clean draw. That is exactly the
        # result being measured, so it has to be distinguishable from a real one.
        self.stat_steps = 0
        self.stat_timeouts = 0
        self.stat_restarts = 0
        self._act_sum = np.zeros(4, dtype=np.float64)
        self._act_sqsum = np.zeros(4, dtype=np.float64)
        self._act_changes = 0
        self.debug = bool(os.environ.get("CUTOFF_DEBUG"))

    def stats(self) -> dict:
        n = max(self.stat_steps, 1)
        mean = self._act_sum / n
        var = np.maximum(self._act_sqsum / n - mean * mean, 0.0)
        return {
            "steps": self.stat_steps,
            "timeouts": self.stat_timeouts,
            "restarts": self.stat_restarts,
            "action_changes": self._act_changes,
            "action_mean": [round(float(v), 4) for v in mean],
            "action_std": [round(float(v), 4) for v in np.sqrt(var)],
        }

    # ---------------------------------------------------------------- lifecycle

    def _start(self) -> None:
        self._stop()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", 0))
        port = self._sock.getsockname()[1]
        self._sock.settimeout(self.handshake_timeout_sec)

        self._proc = subprocess.Popen(
            [
                str(self.exe_path),
                "--server-ip", "127.0.0.1",
                "--server-port", str(port),
                "--team-name", self.team_name,
                "--action-repeat", str(self.action_repeat),
                "--ownship-force-side", str(self.own_force_side),
                "--target-force-side", str(self.target_force_side),
                # Fast heartbeat purely so the handshake lands quickly; the binary's default
                # 1.0 s would add up to a second of dead time to every episode reset.
                "--heartbeat-sec", "0.05",
                "--server-timeout-sec", "0",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        # The binary opens with a SimState/ClientJoinInfo heartbeat; the server answers with
        # SetPlaneID, which is what tells it which PlaneInfo stream is its own aircraft.
        try:
            _, addr = self._sock.recvfrom(2048)
        except socket.timeout as exc:
            self._stop()
            raise RuntimeError(
                f"cutoff binary never sent a heartbeat within {self.handshake_timeout_sec}s"
            ) from exc
        self._client_addr = addr
        self._sock.sendto(_SET_PLANE_ID.pack(_MT_SET_PLANE_ID, _CUTOFF_PLANE_ID), addr)
        self._sock.settimeout(self.recv_timeout_sec)
        self._frame = 0
        self._last_action = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
        self.stat_restarts += 1
        if self.verbose:
            print(f"[cutoff] started pid={self._proc.pid} port={port}")

    def _stop(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._client_addr = None

    def reset(self, context: ActionContext | None = None) -> None:
        # Restart rather than reuse: the tree keeps state across ticks (CoolTimer, blackboard),
        # so a reused process would leak the previous episode into this one.
        if self.debug and self.stat_steps:
            print(f"[cutoff] {self.stats()}", flush=True)
        self._start()

    def close(self) -> None:
        if self.debug:
            print(f"[cutoff] {self.stats()}", flush=True)
        self._stop()

    # ---------------------------------------------------------------- stepping

    @staticmethod
    def _plane_fields(state) -> tuple[list[float], list[float], list[float]]:
        s = np.asarray(state, dtype=np.float64)
        s = np.nan_to_num(s, nan=0.0, posinf=0.0, neginf=0.0)
        return (
            [float(s[0]), float(s[1]), float(s[2])],   # NED position, metres
            [float(s[3]), float(s[4]), float(s[5])],   # roll/pitch/yaw, degrees
            [float(s[6]), float(s[7]), float(s[8])],   # body u/v/w, m/s
        )

    def compute_action(self, context: ActionContext) -> ActionResult:
        if self._sock is None or self._client_addr is None:
            self._start()

        own_state = context.ownship_state
        enemy_state = context.target_state
        if own_state is None or enemy_state is None:
            return ActionResult(action=self._last_action.copy(), source="cutoff",
                                info={"reason": "no state"})

        self._frame += 1
        own_pos, own_rot, own_vel = self._plane_fields(own_state)
        foe_pos, foe_rot, foe_vel = self._plane_fields(enemy_state)

        sock = self._sock
        addr = self._client_addr
        sock.sendto(_PLANE_INFO.pack(2, self._frame, _CUTOFF_PLANE_ID,
                                     *own_pos, *own_rot, *own_vel), addr)
        sock.sendto(_PLANE_INFO.pack(2, self._frame, _ENEMY_PLANE_ID,
                                     *foe_pos, *foe_rot, *foe_vel), addr)

        self.stat_steps += 1
        action = None
        while True:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                break
            if len(data) < 4:
                continue
            if _MSG_TYPE.unpack_from(data)[0] != _MT_CMD:
                continue  # heartbeat (SimState / ClientJoinInfo) -- not a command
            unpacked = _CMD.unpack_from(data)
            action = np.array(unpacked[3:7], dtype=np.float32)
            break

        if action is None:
            # Hold the last command, exactly as the real client does between policy updates.
            self.stat_timeouts += 1
            action = self._last_action.copy()
        else:
            if not np.array_equal(action, self._last_action):
                self._act_changes += 1
            self._last_action = action.copy()

        self._act_sum += action
        self._act_sqsum += action.astype(np.float64) ** 2

        return ActionResult(
            action=clip_action(action),
            source="cutoff",
            info={"frame": self._frame, "timeouts": self.stat_timeouts},
        )
