"""Record and diagnose what the SHIPPED exe actually does against a live DogFightViewer.

    # 1. start DogFightViewer.exe (it listens on 9999)
    # 2. start this proxy in between
    python scripts/viewer_trace.py record --listen 9998 --server-port 9999
    # 3. point the shipped exe at the proxy instead of the viewer
    set DOGFIGHT_SERVER_IP=127.0.0.1
    set DOGFIGHT_SERVER_PORT=9998
    ..\submission_exe\JinjjaBoramae.exe
    # 4. fly a match, Ctrl-C the proxy, then:
    python scripts/viewer_trace.py analyse artifacts/viewer_trace/<file>.jsonl

WHY A PROXY AND NOT LOGGING INSIDE THE CLIENT. The thing we need to diagnose is the SHIPPED
artifact, and it is frozen -- adding logging to it means rebuilding, which changes the binary
under test. A UDP relay sits between the exe and the viewer, forwards every datagram untouched
in both directions, and writes down what it saw. The exe is bit-identical to the one in the ZIP;
only the port it dials differs, and `student/runtime_paths.py` already resolves the environment
ahead of `config.json` precisely so this is possible without editing the submission.

WHAT IT ANSWERS. There is a standing, unresolved report -- ours and the one that prompted
`LIVE_INFERENCE_FRAME_BUGS.md` on 2026-08-20 -- that live behaviour is "climbs/flies away, never
generates a firing solution, no WEZ contact", while the local sim shows the same config entering
the weapons envelope in 65% of episodes against the cutoff. That file's fixes have **never been
exercised against a live server**; its own §0 calls this the single most important open item in
the project. This is the instrument for closing it.

`analyse` reports the four things that distinguish "fleeing" from "fighting":

  1. RANGE TREND      -- is separation growing over the match, or being closed?
  2. POINTING         -- is the enemy ahead of the 3-9 line, and is ATA being driven down?
  3. WEZ CONTACT      -- any frame inside 152.4-914.4 m with ATA <= 1 deg (the real gun envelope)
  4. ROLL AGREEMENT   -- when the enemy is off one wing, do we roll toward it?

Item 4 carries a degeneracy guard, learned the hard way: on a capture where the enemy never
changes side, a constant roll sign scores 0% or 100% regardless of what the aircraft is doing.
That produced a confident, completely wrong "ANTI-CORRELATED" verdict once already. If the
engagement is one-sided the script says so instead of answering.
"""
from __future__ import annotations

import argparse
import csv
import io as _io
import json
import math
import socket
import struct
import sys
import time
from pathlib import Path

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, _io.UnsupportedOperation):
        pass

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT), str(_ROOT / "src"), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Same structs the rest of the project uses; not re-derived here.
_MSG_TYPE = struct.Struct("<i")
_PLANE_INFO = struct.Struct("<iQb3f3f3f")
_CMD = struct.Struct("<ibQffff")
_MT_PLANE_INFO, _MT_CMD = 2, 6

# COMPETITION_RULES Sec 6.2 phase 1: the narrowest, highest-paying envelope.
_WEZ_MIN_M, _WEZ_MAX_M, _WEZ_ATA_DEG = 152.4, 914.4, 1.0


def _decode(blob: bytes) -> dict | None:
    if len(blob) < 4:
        return None
    mt = _MSG_TYPE.unpack_from(blob)[0]
    if mt == _MT_PLANE_INFO and len(blob) >= _PLANE_INFO.size:
        _, idx, pid, px, py, pz, rr, rp, ry, vx, vy, vz = _PLANE_INFO.unpack_from(blob)
        return {"t": "plane", "index": idx, "id": pid, "pos": [px, py, pz],
                "rot": [rr, rp, ry], "vel": [vx, vy, vz]}
    if mt == _MT_CMD and len(blob) >= _CMD.size:
        _, pid, idx, roll, pitch, yaw, thr = _CMD.unpack_from(blob)
        return {"t": "cmd", "index": idx, "id": pid,
                "roll": roll, "pitch": pitch, "yaw": yaw, "throttle": thr}
    return {"t": "other", "mt": mt}


def record(args: argparse.Namespace) -> int:
    out_dir = _ROOT / "artifacts" / "viewer_trace"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"trace_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"

    up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)     # faces the exe
    up.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    up.bind((args.listen_ip, args.listen))
    up.settimeout(0.2)
    down = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)   # faces the viewer
    down.settimeout(0.2)
    server = (args.server_ip, args.server_port)

    print(f"proxy    : exe -> {args.listen_ip}:{args.listen} -> viewer {server[0]}:{server[1]}")
    print(f"trace    : {path}")
    print("Point the exe at the proxy:")
    print(f"  set DOGFIGHT_SERVER_IP={args.listen_ip}")
    print(f"  set DOGFIGHT_SERVER_PORT={args.listen}")
    print("Ctrl-C to stop.\n")

    client = None
    n_up = n_down = 0
    t0 = time.time()
    with path.open("w", encoding="utf-8") as fh:
        try:
            while True:
                try:
                    blob, addr = up.recvfrom(4096)
                    client = addr
                    down.sendto(blob, server)
                    n_up += 1
                    fh.write(json.dumps({"ts": time.time() - t0, "dir": "c2s",
                                         "hex": blob.hex(), "dec": _decode(blob)}) + "\n")
                except socket.timeout:
                    pass
                try:
                    blob, _ = down.recvfrom(4096)
                    if client:
                        up.sendto(blob, client)
                    n_down += 1
                    fh.write(json.dumps({"ts": time.time() - t0, "dir": "s2c",
                                         "hex": blob.hex(), "dec": _decode(blob)}) + "\n")
                except socket.timeout:
                    pass
                if (n_up + n_down) % 2000 == 0 and (n_up + n_down):
                    print(f"  c2s {n_up}  s2c {n_down}", flush=True)
                    fh.flush()
        except KeyboardInterrupt:
            print(f"\nstopped. c2s {n_up}, s2c {n_down} -> {path}")
    if n_up == 0:
        print("!! the exe never sent anything -- check DOGFIGHT_SERVER_PORT matches --listen")
        return 1
    if n_down == 0:
        print("!! the viewer never answered -- check --server-port and that the viewer is up")
        return 1
    print(f"\nnow run:  python scripts/viewer_trace.py analyse {path}")
    return 0


def analyse(args: argparse.Namespace) -> int:
    import numpy as np
    from student.controller_providers import body_axes
    from dogfight.unreal.policies import plane_info_to_state

    class _P:                                   # minimal stand-in for a PlaneInfo
        __slots__ = ("position", "rotation", "velocity", "plane_id")

    def mk(d):
        p = _P()
        p.position = type("v", (), dict(zip("xyz", d["pos"])))()
        p.rotation = type("r", (), dict(zip(("roll", "pitch", "yaw"), d["rot"])))()
        p.velocity = type("v", (), dict(zip("xyz", d["vel"])))()
        p.plane_id = d["id"]
        return p

    planes: dict[int, dict[int, dict]] = {}
    cmds: dict[int, dict] = {}
    own_id = None
    for line in Path(args.trace).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        d = rec.get("dec") or {}
        if d.get("t") == "plane":
            planes.setdefault(d["index"], {})[d["id"]] = d
        elif d.get("t") == "cmd":
            cmds[d["index"]] = d
            own_id = d["id"] if own_id is None else own_id

    rows = []
    for idx, slot in sorted(planes.items()):
        if len(slot) < 2 or idx not in cmds:
            continue
        ids = sorted(slot)
        oid = own_id if own_id in slot else ids[0]
        fid = next(i for i in ids if i != oid)
        ours, foe = mk(slot[oid]), mk(slot[fid])
        c = cmds[idx]

        rel = np.array([foe.position.x - ours.position.x,
                        foe.position.y - ours.position.y,
                        foe.position.z - ours.position.z], dtype=float)
        rng = float(np.linalg.norm(rel))
        if rng < 1e-6:
            continue
        fwd, _up, right = body_axes(plane_info_to_state(ours))
        u = rel / rng
        ata = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(fwd, u))))))
        horiz = np.array([rel[0], rel[1], 0.0])
        hn = float(np.linalg.norm(horiz))
        az = 0.0
        if hn > 1e-9:
            s = float(np.clip(np.dot(right, horiz / hn), -1.0, 1.0))
            a = math.degrees(math.asin(abs(s)))
            if float(np.dot(fwd, horiz / hn)) < 0:
                a = 180.0 - a
            az = a if s >= 0 else -a
        rows.append({"index": idx, "range_m": rng, "ata_deg": ata, "az_deg": az,
                     "own_alt": ours.position.z, "foe_alt": foe.position.z,
                     "roll": c["roll"], "pitch": c["pitch"], "throttle": c["throttle"],
                     "in_wez": int(_WEZ_MIN_M <= rng <= _WEZ_MAX_M and ata <= _WEZ_ATA_DEG)})

    if not rows:
        print("no paired PlaneInfo+CMD frames in that trace")
        return 1

    out_csv = Path(args.trace).with_suffix(".analysis.csv")
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    first, last = rows[:max(1, n // 10)], rows[-max(1, n // 10):]
    r0 = sum(r["range_m"] for r in first) / len(first)
    r1 = sum(r["range_m"] for r in last) / len(last)
    ata0 = sum(r["ata_deg"] for r in first) / len(first)
    ata1 = sum(r["ata_deg"] for r in last) / len(last)
    ahead = sum(1 for r in rows if abs(r["az_deg"]) <= 90.0)
    wez = sum(r["in_wez"] for r in rows)
    minr = min(r["range_m"] for r in rows)
    minata = min(r["ata_deg"] for r in rows)

    print(f"\nframes                : {n}   -> {out_csv.name}")
    print(f"range   first10% -> last10% : {r0:8.0f} m -> {r1:8.0f} m   (min seen {minr:.0f} m)")
    print(f"ATA     first10% -> last10% : {ata0:8.1f} d -> {ata1:8.1f} d   (min seen {minata:.2f} d)")
    print(f"enemy ahead of the 3-9 line : {ahead}/{n} ({ahead/n:.0%})")
    print(f"WEZ frames (152-914 m, <=1 d): {wez}")
    print(f"throttle mean               : {sum(r['throttle'] for r in rows)/n:.2f}")

    pos = sum(1 for r in rows if r["az_deg"] > 0)
    minority = min(pos, n - pos) / n
    print()
    if minority < 0.10:
        print(f"roll agreement            : NOT MEASURABLE -- the enemy stayed on one side for "
              f"{max(pos, n-pos)}/{n} frames.")
    else:
        useful = [r for r in rows if 5.0 <= abs(r["az_deg"]) <= 175.0]
        agr = sum(1 for r in useful if (r["roll"] > 0) == (r["az_deg"] > 0))
        print(f"roll agreement            : {agr}/{len(useful)} = {agr/len(useful):.0%} "
              f"(>=65% tracks, <=35% is inverted)")

    print("\nVERDICT")
    fleeing = r1 > r0 * 1.5 and wez == 0
    if fleeing:
        print("  FLEEING -- separation grew and the gun envelope was never entered.")
        print("  This is the LIVE_INFERENCE_FRAME_BUGS.md symptom. Keep the trace.")
    elif wez > 0:
        print(f"  FIGHTING -- entered the gun envelope on {wez} frames.")
    else:
        print("  ENGAGED BUT NOT CONVERTING -- closed the range but never held "
              "<=1 deg inside 914 m. That is the dwell failure the local matrix shows, "
              "not a frame bug.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="relay between the exe and the viewer, logging both ways")
    r.add_argument("--listen", type=int, default=9998, help="port the EXE should dial")
    r.add_argument("--listen-ip", default="127.0.0.1")
    r.add_argument("--server-port", type=int, default=9999, help="port the VIEWER listens on")
    r.add_argument("--server-ip", default="127.0.0.1")
    a = sub.add_parser("analyse", help="turn a recorded trace into geometry + a verdict")
    a.add_argument("trace")
    args = ap.parse_args()
    return record(args) if args.cmd == "record" else analyse(args)


if __name__ == "__main__":
    raise SystemExit(main())
