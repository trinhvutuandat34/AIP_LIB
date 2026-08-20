"""End-to-end LIVE-PATH dry run over real UDP sockets, on loopback, with no GPU and no server.

WHY THIS EXISTS. Two items have been open and blocking for weeks, both for the same stated
reason -- "we cannot test the live path without the organizers' address or DogFightViewer.exe":

  * LIVE_INFERENCE_FRAME_BUGS.md Sec5 item 1: "No live connection has ever exercised the fixed
    code... this is the single highest-priority open item in this project."
  * COMPETITION_PLAN.md Sec8 / F9 / F27: the DQ-and-network workstream, never live-tested;
    2+ instability incidents on competition day is elimination.

Neither blocker is real. The cutoff binary's own `--help` gives the game away: its default is
`--server-ip 127.0.0.1`, and `127.0.0.1` is the ONLY IPv4 string in the whole executable. The
engagement server is expected on LOOPBACK. And this project already contains a working
server-side implementation of the Unreal wire protocol -- `scripts/cutoff_provider.py` binds a
UDP socket, answers the handshake, streams PlaneInfo and reads CMD. That server half is all
that is needed to put OUR OWN client through a genuine socket round trip.

So this script is the missing half of that idea, pointed the other way: instead of hosting a
server so the cutoff binary can play, it hosts a server so OUR client can play -- the real
`run_unreal_inference.py`, launched as a subprocess, over a real socket, on the real port,
speaking the real protocol.

WHAT IT ACTUALLY EXERCISES that no local eval can. `eval_v5_vs_bt.py` and friends always build a
real local `sim`, which routes through `ai_pilot.Step()` -> `ChangeData()`. The live path is the
OTHER branch (`context.sim is None` -> `StepWithPlaneData`), reached only through
`unreal/policies.py`. That branch carries both frame bugs, the action-repeat pacing, the
handshake, the heartbeat and the reconnect logic -- none of which any local measurement has ever
touched. This runs all of it.

THE KEY DISCRIMINATOR. Per LIVE_INFERENCE_FRAME_BUGS.md Sec2, feeding the DLL raw Unreal metres
makes the tree believe the enemy is ~55,000 km away, so it parks on its "target far away"
Fallback branch and emits a CONSTANT command (measured there: throttle pinned 1.0 every tick).
With the frame fix the tree sees true range and commands respond to geometry. So over a socket,
with real captured geometry replayed, "does the command vary?" is an end-to-end, black-box
detector for whether the fix is live -- observable from the server side without introspecting
the client at all.

USAGE
    python scripts/loopback_live_dryrun.py
    python scripts/loopback_live_dryrun.py --frames 900 --action-repeat 1

Exit 0 = handshake, response rate, latency and command sanity all pass.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Byte-identical to src/dogfight/unreal/protocol.py (same constants cutoff_provider.py uses).
_PLANE_INFO = struct.Struct("<iQb3f3f3f")
_CMD = struct.Struct("<ibQffff")
_SET_PLANE_ID = struct.Struct("<ib")
_MSG_TYPE = struct.Struct("<i")
_MT_PLANE_INFO = 2
_MT_CMD = 6
_MT_SET_PLANE_ID = 9

OUR_PLANE_ID = 0     # what the captured session's MT_SetPlaneID assigned
ENEMY_PLANE_ID = 1
DEFAULT_CAPTURE = "logs/unreal_packets/rx_packets_20260514_155232_15208.jsonl"

# COMPETITION_RULES.md Sec4: 60 Hz state, answer at 60 Hz, 0.1667 s per-decision budget.
TICK_HZ = 60.0
LATENCY_BUDGET_S = 1.0 / 6.0


def load_frames(capture: Path, want: int):
    """Real MT_PlaneInfo frames, paired by index -- the exact bytes a real server sent."""
    from dogfight.unreal.protocol import unpack_plane_info

    by_index: dict[int, dict[int, object]] = {}
    order: list[int] = []
    with capture.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("message_type") != "MT_PlaneInfo" or "hex" not in rec:
                continue
            try:
                pi = unpack_plane_info(bytes.fromhex(rec["hex"].replace(" ", "")))
            except Exception:
                continue
            slot = by_index.setdefault(pi.index, {})
            if pi.index not in order:
                order.append(pi.index)
            slot[pi.plane_id] = pi
    out = []
    for idx in order:
        slot = by_index[idx]
        if len(slot) >= 2:
            ids = sorted(slot)[:2]
            out.append((slot[ids[0]], slot[ids[1]]))
        if len(out) >= want:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--frames", type=int, default=600, help="PlaneInfo pairs to replay (60/s)")
    ap.add_argument("--port", type=int, default=9999)
    ap.add_argument("--mode", default="vptrack")
    ap.add_argument("--action-repeat", type=int, default=None,
                    help="override; default leaves run_unreal_inference.py's own default")
    ap.add_argument("--handshake-timeout", type=float, default=45.0)
    args = ap.parse_args()

    capture = ROOT / args.capture if not os.path.isabs(args.capture) else Path(args.capture)
    frames = load_frames(capture, args.frames)
    if len(frames) < 30:
        print(f"FAIL: only {len(frames)} usable frames from {capture}")
        return 1

    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.settimeout(0.5)

    cmd = [sys.executable, str(ROOT / "run_unreal_inference.py"),
           "--mode", args.mode, "--server-ip", "127.0.0.1",
           "--server-port", str(args.port), "--team-name", "dryrun"]
    if args.action_repeat is not None:
        cmd += ["--action-repeat", str(args.action_repeat)]

    print(f"server   : 127.0.0.1:{args.port}  (loopback, real UDP)")
    print(f"client   : run_unreal_inference.py --mode {args.mode}"
          + (f" --action-repeat {args.action_repeat}" if args.action_repeat else ""))
    print(f"frames   : {len(frames)} real captured PlaneInfo pairs @ {TICK_HZ:.0f} Hz")
    print()

    proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace")
    client_addr = None
    t0 = time.time()
    try:
        # 1) HANDSHAKE. The client speaks first (heartbeat/join); that is how the server learns
        #    its ephemeral port, exactly as cutoff_provider.py does it.
        while client_addr is None and time.time() - t0 < args.handshake_timeout:
            try:
                _, client_addr = srv.recvfrom(2048)
            except socket.timeout:
                if proc.poll() is not None:
                    print("FAIL: client exited before handshake")
                    print((proc.stdout.read() or "")[-2000:])
                    return 1
        if client_addr is None:
            print(f"FAIL: no packet from client within {args.handshake_timeout}s")
            proc.kill()
            return 1
        handshake_s = time.time() - t0
        srv.sendto(_SET_PLANE_ID.pack(_MT_SET_PLANE_ID, OUR_PLANE_ID), client_addr)
        print(f"handshake: client at {client_addr[0]}:{client_addr[1]} after {handshake_s:.2f}s -> SetPlaneID({OUR_PLANE_ID})")

        # 2) REPLAY + COLLECT.
        cmds, latencies, answered = [], [], 0
        srv.settimeout(LATENCY_BUDGET_S)
        for i, (a, b) in enumerate(frames):
            ours, foe = (a, b) if a.plane_id == OUR_PLANE_ID else (b, a)
            for pid, p in ((OUR_PLANE_ID, ours), (ENEMY_PLANE_ID, foe)):
                srv.sendto(_PLANE_INFO.pack(
                    _MT_PLANE_INFO, i, pid,
                    p.position.x, p.position.y, p.position.z,
                    p.rotation.roll, p.rotation.pitch, p.rotation.yaw,
                    p.velocity.x, p.velocity.y, p.velocity.z), client_addr)
            sent = time.perf_counter()
            deadline = sent + LATENCY_BUDGET_S
            while time.perf_counter() < deadline:
                try:
                    data, _ = srv.recvfrom(2048)
                except socket.timeout:
                    break
                if len(data) >= 4 and _MSG_TYPE.unpack_from(data)[0] == _MT_CMD:
                    latencies.append(time.perf_counter() - sent)
                    cmds.append(_CMD.unpack_from(data)[3:7])
                    answered += 1
                    break
            time.sleep(max(0.0, (1.0 / TICK_HZ) - (time.perf_counter() - sent)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        srv.close()

    out = proc.stdout.read() or ""

    if not cmds:
        print("FAIL: client never sent a CMD.")
        print(out[-2000:])
        return 1

    n = len(frames)
    resp_rate = answered / n
    lat_ms = sorted(latencies)
    p50 = lat_ms[len(lat_ms) // 2] * 1e3
    p99 = lat_ms[min(len(lat_ms) - 1, int(len(lat_ms) * 0.99))] * 1e3
    worst = lat_ms[-1] * 1e3
    finite = all(all(v == v and abs(v) < 1e6 for v in c) for c in cmds)
    uniq = len(set(cmds))
    chan = list(zip(*cmds))
    spans = [max(c) - min(c) for c in chan]
    varying = uniq > 1 and max(spans) > 1e-4

    print()
    print(f"response  : {answered}/{n} frames answered ({resp_rate:.1%})")
    print(f"latency   : p50 {p50:.2f} ms | p99 {p99:.2f} ms | worst {worst:.2f} ms"
          f"  (budget {LATENCY_BUDGET_S*1e3:.1f} ms)")
    print(f"commands  : {uniq} distinct of {len(cmds)}; per-channel span "
          f"roll {spans[0]:.4f} pitch {spans[1]:.4f} rud {spans[2]:.4f} thr {spans[3]:.4f}")
    print(f"finite    : {finite}")
    print()

    ok_hs = True
    ok_rate = resp_rate >= 0.95
    ok_lat = worst <= LATENCY_BUDGET_S * 1e3
    ok_var = varying
    for label, ok, why in (
        ("handshake completed", ok_hs, ""),
        ("answers >=95% of frames", ok_rate, f"got {resp_rate:.1%}"),
        ("worst latency within budget", ok_lat, f"worst {worst:.2f} ms"),
        ("commands finite", finite, ""),
        ("commands respond to geometry", ok_var,
         "constant command = the tree is parked on its 'target far away' branch, which is the "
         "live-frame-bug signature (LIVE_INFERENCE_FRAME_BUGS.md Sec2)"),
    ):
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  -- {why}" if why and not ok else ""))

    if all((ok_hs, ok_rate, ok_lat, finite, ok_var)):
        print("\nPASS -- the shipped live path completes a real socket round trip and flies "
              "responsively on real wire geometry.")
        return 0
    print("\nFAIL -- see above. Client tail:")
    print(out[-1500:])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
