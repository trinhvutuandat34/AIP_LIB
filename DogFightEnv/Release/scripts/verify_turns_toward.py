"""Does the shipped exe turn TOWARD the enemy, or away from it?

    python scripts/verify_turns_toward.py ../submission_exe/JinjjaBoramae.exe

WHY THIS EXISTS. `smoke_exe.py` proves the exe answers every frame with finite, varying,
non-zero commands. It does NOT prove those commands point anywhere sensible -- a client that
flies perfectly smoothly in the wrong direction passes it. And "climbs/flies away, never
generates a firing solution, no WEZ contact" is a REAL reported symptom of this project
(`LIVE_INFERENCE_FRAME_BUGS.md`, written 2026-08-20 in response to a live match), caused by two
coordinate-frame mismatches between the training sim and the Unreal wire. Both are fixed in
`student/live_frame_fix.py`, and per that file's own §0 the fixes have **never been exercised
end-to-end against a live server**. This is the closest test available without one.

THE MEASUREMENT. We replay real captured `MT_PlaneInfo` pairs -- the exact bytes a real server
sent -- and for each answered frame compute, from those same bytes, where the enemy actually is
in our body frame. Then we ask whether the commanded roll agrees.

  az > 0  -> enemy is off our RIGHT wing  -> a pursuing aircraft rolls RIGHT (roll > 0)
  az < 0  -> enemy is off our LEFT  wing  -> a pursuing aircraft rolls LEFT  (roll < 0)

`agreement` is the fraction of frames where sign(roll) == sign(az). A tracker sits well above
0.5. A frame-sign bug sits well BELOW 0.5 -- it is not noise, it is anti-correlation, which is
exactly what "flies away and never points" looks like from the outside.

WHAT IT CANNOT TELL YOU. The capture is one recorded session, not a live engagement, and the
replayed aircraft does not react to our commands -- so this measures POINTING INTENT, not whether
we would win. A pass here does not prove the live path is healthy; a fail proves it is not.
"""
from __future__ import annotations

import argparse
import math
import os
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

import io as _io
for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, _io.UnsupportedOperation):
        pass

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parent / "src"))

from loopback_live_dryrun import (  # noqa: E402
    _CMD, _MSG_TYPE, _MT_CMD, _MT_PLANE_INFO, _MT_SET_PLANE_ID,
    _PLANE_INFO, _SET_PLANE_ID, DEFAULT_CAPTURE, ENEMY_PLANE_ID,
    LATENCY_BUDGET_S, OUR_PLANE_ID, TICK_HZ, load_frames,
)

_ROOT = _HERE.parent


def body_azimuth_deg(ours, foe) -> float | None:
    """Signed bearing to the enemy about our own vertical axis, degrees. + = right of the nose.

    Uses THIS CODEBASE'S OWN `body_axes()` rather than a textbook atan2, and that distinction is
    load-bearing: `body_axes` replicates `EulerAngle::toQuaternion`, a deliberately non-standard
    construction that its docstring warns "a textbook quaternion here silently disagrees with the
    C++ at high bank angles". A naive `atan2(dy, dx) - yaw` produced a perfect 0/600
    anti-correlation on this capture -- which was the measurer being wrong, not the exe.

    Only the HORIZONTAL component is projected onto the body right-vector. Commanded roll is what
    answers left/right, and staying in-plane sidesteps the vertical-sign question that
    LIVE_INFERENCE_FRAME_BUGS.md's bug 1 is about, so this test cannot be confounded by it.
    """
    import numpy as np
    from student.controller_providers import body_axes
    from dogfight.unreal.policies import plane_info_to_state

    own = plane_info_to_state(ours)
    _fwd, _up, right = body_axes(own)

    rel = np.array([foe.position.x - ours.position.x,
                    foe.position.y - ours.position.y,
                    0.0])
    n = float(np.linalg.norm(rel))
    if n < 1e-9:
        return None
    rel /= n
    # Signed: + when the enemy lies along our right wing. asin of the right-component gives the
    # magnitude too, which the 5-175 deg usability filter needs.
    s = float(np.clip(np.dot(right, rel), -1.0, 1.0))
    fwd_comp = float(np.dot(_fwd, rel))
    ang = math.degrees(math.asin(abs(s)))
    if fwd_comp < 0:                      # behind the 3-9 line: reflect into the rear hemisphere
        ang = 180.0 - ang
    return ang if s >= 0 else -ang


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", type=Path)
    ap.add_argument("--port", type=int, default=9999)
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--handshake-timeout", type=float, default=120.0)
    a = ap.parse_args()
    if not a.exe.is_file():
        print(f"FAIL: no such exe: {a.exe}")
        return 1

    frames = load_frames(_ROOT / DEFAULT_CAPTURE, a.frames)
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", a.port))
    srv.settimeout(0.5)
    env = dict(os.environ, DOGFIGHT_SERVER_IP="127.0.0.1", DOGFIGHT_SERVER_PORT=str(a.port))

    proc = subprocess.Popen([str(a.exe)], cwd=str(a.exe.parent), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", bufsize=1)
    tail: deque = deque(maxlen=200)
    threading.Thread(target=lambda: [tail.append(l) for l in proc.stdout], daemon=True).start()

    samples: list[tuple[float, float, float]] = []   # (az_deg, roll, pitch)
    client = None
    t0 = time.time()
    try:
        while client is None and time.time() - t0 < a.handshake_timeout:
            try:
                _, client = srv.recvfrom(2048)
            except socket.timeout:
                if proc.poll() is not None:
                    print("FAIL: exe exited before handshake")
                    print("".join(tail)[-2000:])
                    return 1
        if client is None:
            print("FAIL: no handshake")
            proc.kill()
            return 1
        srv.sendto(_SET_PLANE_ID.pack(_MT_SET_PLANE_ID, OUR_PLANE_ID), client)
        srv.settimeout(LATENCY_BUDGET_S)

        for i, (p, q) in enumerate(frames):
            ours, foe = (p, q) if p.plane_id == OUR_PLANE_ID else (q, p)
            for pid, pl in ((OUR_PLANE_ID, ours), (ENEMY_PLANE_ID, foe)):
                srv.sendto(_PLANE_INFO.pack(
                    _MT_PLANE_INFO, i, pid,
                    pl.position.x, pl.position.y, pl.position.z,
                    pl.rotation.roll, pl.rotation.pitch, pl.rotation.yaw,
                    pl.velocity.x, pl.velocity.y, pl.velocity.z), client)
            sent = time.perf_counter()
            while time.perf_counter() < sent + LATENCY_BUDGET_S:
                try:
                    data, _ = srv.recvfrom(2048)
                except socket.timeout:
                    break
                if len(data) >= 4 and _MSG_TYPE.unpack_from(data)[0] == _MT_CMD:
                    roll, pitch = _CMD.unpack_from(data)[3:5]
                    az = body_azimuth_deg(ours, foe)
                    if az is not None:
                        samples.append((az, roll, pitch))
                    break
            time.sleep(max(0.0, (1.0 / TICK_HZ) - (time.perf_counter() - sent)))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        srv.close()

    if not samples:
        print("FAIL: no commands captured")
        print("".join(tail)[-2000:])
        return 1

    # Frames where the enemy is nearly dead ahead or dead astern carry no left/right information,
    # so they are excluded rather than counted as coin flips that dilute the signal.
    useful = [(az, r, p) for az, r, p in samples if 5.0 <= abs(az) <= 175.0]
    agree = sum(1 for az, r, _ in useful if (r > 0) == (az > 0))
    n = len(useful)
    frac = agree / n if n else float("nan")

    # DEGENERATE-GEOMETRY GUARD. If the enemy never changes side over the capture, this test has
    # NO discriminating power: any constant roll sign scores either 0% or 100% regardless of what
    # the exe is doing. The default capture is exactly that case -- the enemy sits at +90 to +169
    # deg (right-rear) for all 600 frames and never crosses to the left -- so an unguarded run
    # reports a confident 0% "ANTI-CORRELATED" that means nothing. Refuse to answer instead.
    pos = sum(1 for az, _, _ in samples if az > 0)
    minority = min(pos, len(samples) - pos) / len(samples) if samples else 0.0
    if minority < 0.10:
        side = "RIGHT" if pos > len(samples) / 2 else "LEFT"
        print(f"\nINCONCLUSIVE -- the enemy stays on our {side} for "
              f"{max(pos, len(samples)-pos)}/{len(samples)} frames "
              f"({minority:.0%} on the other side).")
        print("A constant-sign azimuth makes this measurement meaningless: any constant roll")
        print("sign scores 0% or 100% whatever the aircraft is doing. This capture is a")
        print("one-sided tail chase, not a manoeuvring engagement.")
        print("\nNEEDED: a capture where the enemy crosses from one side to the other. Until")
        print("then this script cannot say whether the live path points correctly.")
        return 2

    ahead = [s for s in samples if abs(s[0]) <= 90.0]
    print(f"\nframes answered      : {len(samples)}")
    print(f"usable (5-175 deg)   : {n}")
    print(f"enemy ahead of wing  : {len(ahead)}/{len(samples)} ({len(ahead)/len(samples):.0%})")
    print(f"mean |azimuth|       : {sum(abs(s[0]) for s in samples)/len(samples):6.1f} deg")
    print(f"roll agrees with side: {agree}/{n} = {frac:.1%}")
    print()
    if frac >= 0.65:
        print(f"PASS -- the exe rolls TOWARD the enemy {frac:.0%} of the time. Pointing intent is "
              "correct on real wire geometry.")
        return 0
    if frac <= 0.35:
        print(f"FAIL -- ANTI-CORRELATED ({frac:.0%}). The exe rolls AWAY from the enemy. That is "
              "the LIVE_INFERENCE_FRAME_BUGS.md signature: flies off, never points, no WEZ.")
        print("".join(tail)[-1500:])
        return 1
    print(f"INCONCLUSIVE ({frac:.0%}) -- neither tracking nor cleanly inverted. Look at the "
          "per-frame data before drawing a conclusion.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
