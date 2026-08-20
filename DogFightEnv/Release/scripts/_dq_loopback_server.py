"""Minimal, long-running loopback UDP server for scripts/live_dq_rehearsal.py.

Reuses the exact wire structs already proven correct in scripts/cutoff_provider.py and
scripts/loopback_live_dryrun.py. Loops real captured MT_PlaneInfo frames continuously for
--duration-sec so a fault-injection rehearsal has something to reconnect TO after each induced
outage, unlike loopback_live_dryrun.py's one-shot replay.

2026-08-21 (F40), two corrections after the 2026-08-20 18:34 rehearsal was found to have
passed vacuously:

  1. --silence-every-sec / --silence-for-sec induce a REAL outage by having this server simply
     stop transmitting. The rehearsal's original fault injector shells out to
     `netsh advfirewall` to block UDP to 127.0.0.1 -- and **Windows Firewall does not filter
     loopback traffic**, so those blocks were no-ops. The evidence they were no-ops is in the
     run's own artifact: 3 "FAULT BLOCK" cycles of 6 s each against a 0.2 s recv timeout
     produced fallback_calls=0 and disconnects=0, which is impossible if the client had
     actually lost the wire. Server-side silence needs no firewall and no privileges, and is
     what the client would really see if the server died or the match ended.
  2. recvfrom() now tolerates ConnectionResetError. On Windows a UDP socket raises WinError
     10054 when a previous sendto() drew an ICMP port-unreachable -- i.e. every time the client
     goes away. That killed this server outright mid-rehearsal (see
     artifacts/eval/dq_server.log), taking the server down with the client and destroying the
     very reconnect window the rehearsal exists to test.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

_PLANE_INFO = struct.Struct("<iQb3f3f3f")
_SET_PLANE_ID = struct.Struct("<ib")
_MSG_TYPE = struct.Struct("<i")
_MT_PLANE_INFO = 2
_MT_CMD = 6
_MT_SET_PLANE_ID = 9
OUR_ID, ENEMY_ID = 0, 1
DEFAULT_CAPTURE = "logs/unreal_packets/rx_packets_20260514_155232_15208.jsonl"


def load_frames(capture: Path, want: int):
    from dogfight.unreal.protocol import unpack_plane_info
    by_index, order = {}, []
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9999)
    ap.add_argument("--duration-sec", type=float, default=90.0)
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--silence-every-sec", type=float, default=0.0,
                    help="Go silent this often (0=never). A REAL outage: we simply stop sending.")
    ap.add_argument("--silence-for-sec", type=float, default=6.0,
                    help="How long each silence window lasts.")
    args = ap.parse_args()

    frames = load_frames(ROOT / args.capture, 400)
    print(f"[dq-server] {len(frames)} frames loaded, looping for {args.duration_sec:.0f}s", flush=True)

    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.bind, args.port))
    srv.settimeout(2.0)

    client_addr = None
    t_start = time.time()
    t_end = t_start + args.duration_sec
    i = 0
    sent = answered = 0
    silent_windows = 0
    was_silent = False
    while time.time() < t_end:
        # --- real outage window: stop transmitting entirely (no firewall involved) ----------
        silent = False
        if args.silence_every_sec > 0:
            phase = (time.time() - t_start) % args.silence_every_sec
            silent = phase < args.silence_for_sec
        if silent and not was_silent:
            silent_windows += 1
            print(f"[dq-server] SILENCE #{silent_windows} begins "
                  f"({args.silence_for_sec:.1f}s, server stops sending)", flush=True)
        elif was_silent and not silent:
            print(f"[dq-server] SILENCE #{silent_windows} ends, resuming", flush=True)
        was_silent = silent

        if client_addr is None:
            try:
                _, client_addr = srv.recvfrom(2048)
                srv.sendto(_SET_PLANE_ID.pack(_MT_SET_PLANE_ID, OUR_ID), client_addr)
                print(f"[dq-server] client (re)connected: {client_addr}", flush=True)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
        if not silent:
            a, b = frames[i % len(frames)]
            i += 1
            ours, foe = (a, b) if a.plane_id == OUR_ID else (b, a)
            try:
                for pid, p in ((OUR_ID, ours), (ENEMY_ID, foe)):
                    srv.sendto(_PLANE_INFO.pack(
                        _MT_PLANE_INFO, i, pid,
                        p.position.x, p.position.y, p.position.z,
                        p.rotation.roll, p.rotation.pitch, p.rotation.yaw,
                        p.velocity.x, p.velocity.y, p.velocity.z), client_addr)
                sent += 1
            except OSError as exc:
                print(f"[dq-server] send failed (expected during a block window): {exc}", flush=True)
        try:
            data, from_addr = srv.recvfrom(2048)
            if len(data) >= 4 and _MSG_TYPE.unpack_from(data)[0] == _MT_CMD:
                answered += 1
            if from_addr != client_addr:
                client_addr = from_addr  # port can change across a reconnect
        except socket.timeout:
            pass
        except ConnectionResetError:
            # WinError 10054: an earlier sendto drew ICMP port-unreachable because the client
            # went away. Expected during a reconnect window -- must NOT kill the server.
            #
            # Dropping the address matters as much as not dying. A reconnecting client comes
            # back on a NEW ephemeral source port; if we keep transmitting at the dead one,
            # every send draws another 10054, every recvfrom raises instead of returning the
            # new client's heartbeat, and the server never learns the new address -- a
            # permanent deadlock. Measured 2026-08-21: frames froze at 647 across 7 client
            # reconnects until this reset was added.
            client_addr = None
        time.sleep(1.0 / 60.0)

    print(f"[dq-server] done. sent={sent} answered={answered} "
          f"answer_rate={100.0*answered/max(1,sent):.1f}% silence_windows={silent_windows}", flush=True)
    srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
