"""Prove a built .exe actually flies, by replaying real captured wire geometry at it.

    python scripts/smoke_exe.py ../submission_exe/JinjjaBoramae.exe

THIS IS THE GATE THAT PACKAGING MUST NOT SHIP WITHOUT, and the reason is F70. If the native BT
cannot load its Rule XML, `CPPBehaviorTree.cpp:143-148` catches the exception, prints one line to
C++ `std::cout`, and sets `bInitialized=false`. `LibMain.cpp` then never inserts the tree, and
`Step()` returns its **zero-initialised** `ControlValue` -- roll, pitch, rudder and throttle all
0.0. No exception crosses the ctypes boundary. `ResilientActionProvider` gets a finite,
correctly-shaped action and forwards it. The client handshakes, answers every frame at 60 Hz, and
logs nothing unusual, while flying the whole match with the stick centred and the engine at idle.
**A dead submission and a healthy one are indistinguishable from the outside.** So this checks the
commands themselves, per channel, and greps for that one std::cout line.

WHY IT IS NOT `loopback_live_dryrun.py`. That script launches `run_unreal_inference.py` through
`sys.executable` -- a different entry point from the shipped one, with a different provider-build
path and a different `--server-ip` default -- and post-freeze it would be testing a file that is
not in the submission. It also gates variance with `max(spans) > 1e-4`, which passes if ONE of the
four channels moves: roll/pitch/rudder pinned at exactly 0.0 with only throttle jittering is a
PASS there. Here every channel is checked on its own. The frame-loading and protocol packing are
imported from it rather than duplicated.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

# The exe under test prints Korean, and this script's whole job is to relay its output when
# something fails. On a cp949 console that print is itself a UnicodeEncodeError -- the F40 failure
# mode my_submission.py:64-69 already guards against -- and it would take down the diagnostic
# right when it matters. Same two lines, same reason.
import io as _io  # noqa: E402
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
# The exact line CPPBehaviorTree.cpp:145 prints when the tree fails to construct.
_BT_FAIL = "Behavior Tree Initialization Failed"
_BT_OK = "Behavior Tree Initialized"


def _drain(proc: subprocess.Popen, sink: deque) -> threading.Thread:
    """Consume the child's stdout continuously, keeping only the tail.

    NOT optional plumbing -- without it this script DEADLOCKS, and it did. The submission runs
    its client with `enable_terminal_monitor=True` (my_submission.py), which prints a packet
    counter every frame. At 60 Hz that fills the 64 KB pipe buffer in seconds; the exe then
    blocks forever inside its own `print`, stops answering the socket, and this script waits out
    its handshake timeout against a process that is alive, healthy, and gagged. Reading the pipe
    only after `proc.terminate()` -- which is what loopback_live_dryrun.py does -- cannot work
    for a child this chatty.

    `sink` is (head_list, tail_deque): a 600-frame run emits tens of thousands of lines, and the
    two that matter are at opposite ends -- the start-up banner carries the BT's own
    `Behavior Tree Initialized` verdict, and the tail carries whatever it died of.
    """
    head, tail = sink

    def pump():
        for line in proc.stdout:
            if len(head) < 400:
                head.append(line)
            else:
                tail.append(line)
    t = threading.Thread(target=pump, daemon=True)
    t.start()
    return t


def run(exe: Path, port: int, want_frames: int, handshake_timeout: float) -> int:
    frames = load_frames(_ROOT / DEFAULT_CAPTURE, want_frames)
    if len(frames) < 30:
        print(f"FAIL: only {len(frames)} usable frames from the capture")
        return 1

    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.settimeout(0.5)

    # Point the exe at this socket. DOGFIGHT_TEAM_NAME is deliberately NOT set -- the displayed
    # name is baked into the shim and getting it wrong is a DQ risk (COMPETITION_RULES Sec 7.1),
    # so the test reads back what the binary actually chose instead of dictating it.
    env = dict(os.environ, DOGFIGHT_SERVER_IP="127.0.0.1", DOGFIGHT_SERVER_PORT=str(port))

    print(f"exe      : {exe}  ({exe.stat().st_size / 1e6:.1f} MB)")
    print(f"server   : 127.0.0.1:{port} (loopback, real UDP)")
    print(f"frames   : {len(frames)} real captured PlaneInfo pairs @ {TICK_HZ:.0f} Hz\n")

    proc = subprocess.Popen([str(exe)], cwd=str(exe.parent), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", bufsize=1)
    sink = ([], deque(maxlen=400))
    _drain(proc, sink)

    def tail_text(n: int = 3000) -> str:
        return ("".join(sink[0]) + "".join(sink[1]))[-n:]

    client_addr = None
    cmds: list[tuple] = []
    latencies: list[float] = []
    answered = 0
    t0 = time.time()
    try:
        while client_addr is None and time.time() - t0 < handshake_timeout:
            try:
                _, client_addr = srv.recvfrom(2048)
            except socket.timeout:
                if proc.poll() is not None:
                    print("FAIL: exe exited before handshake -- it could not start at all.")
                    print(tail_text())
                    return 1
        if client_addr is None:
            print(f"FAIL: no packet from the exe within {handshake_timeout}s")
            proc.kill()
            return 1
        print(f"handshake: {client_addr[0]}:{client_addr[1]} after {time.time() - t0:.2f}s")
        srv.sendto(_SET_PLANE_ID.pack(_MT_SET_PLANE_ID, OUR_PLANE_ID), client_addr)

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
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        srv.close()

    # Everything the exe said, head + tail. The drain thread already consumed the pipe.
    out = "".join(sink[0]) + "".join(sink[1])

    if not cmds:
        print("FAIL: the exe never sent a CMD.")
        print(tail_text())
        return 1

    names = ("roll", "pitch", "rudder", "throttle")
    chan = list(zip(*cmds))
    spans = [max(c) - min(c) for c in chan]
    peaks = [max(abs(v) for v in c) for c in chan]
    resp_rate = answered / len(frames)
    lat = sorted(latencies)
    worst = lat[-1] * 1e3

    print(f"\nresponse  : {answered}/{len(frames)} answered ({resp_rate:.1%})")
    print(f"latency   : p50 {lat[len(lat)//2]*1e3:.2f} ms | worst {worst:.2f} ms "
          f"(budget {LATENCY_BUDGET_S*1e3:.1f} ms)")
    for nm, sp, pk in zip(names, spans, peaks):
        print(f"  {nm:<9} span {sp:>9.5f}   peak |v| {pk:>9.5f}")
    print(f"distinct  : {len(set(cmds))} of {len(cmds)}")
    print(f"BT init   : {'FAILED LINE PRESENT' if _BT_FAIL in out else ('ok' if _BT_OK in out else 'no line seen')}\n")

    all_zero = sum(1 for c in cmds if all(abs(v) <= 1e-9 for v in c))
    checks = [
        ("answers >=95% of frames", resp_rate >= 0.95, f"got {resp_rate:.1%}"),
        ("worst latency within budget", worst <= LATENCY_BUDGET_S * 1e3, f"worst {worst:.2f} ms"),
        ("commands finite", all(all(v == v and abs(v) < 1e6 for v in c) for c in cmds), ""),
        # THE F70 GATE. Every frame exactly (0,0,0,0) is what a failed tree load produces.
        ("no all-zero command frames", all_zero == 0, f"{all_zero}/{len(cmds)} frames were (0,0,0,0)"),
        # PER CHANNEL, not max() over channels. roll and pitch are the two that must move on
        # real geometry; a pinned stick with a jittering throttle passes the old dry-run gate.
        ("roll responds to geometry", spans[0] > 1e-4, f"span {spans[0]:.6f}"),
        ("pitch responds to geometry", spans[1] > 1e-4, f"span {spans[1]:.6f}"),
        # Throttle may legitimately sit constant, but never at zero for a whole run: every
        # Task_* node writes it, so a flat 0.0 means nothing wrote it.
        ("throttle is non-trivial", peaks[3] > 1e-3, f"peak {peaks[3]:.6f}"),
        # The DLL's own verdict, straight from std::cout. --console exists for this line.
        ("native BT loaded its Rule XML", _BT_FAIL not in out,
         "CPPBehaviorTree.cpp printed its init-failure line: the Rule XML is not beside the DLL "
         "inside the bundle, so Step() is returning a zero-initialised ControlValue"),
    ]
    for label, ok, why in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  -- {why}" if why and not ok else ""))

    if all(ok for _, ok, _ in checks):
        print(f"\nPASS -- {exe.name} completes a real socket round trip and flies responsively.")
        return 0
    print("\nFAIL -- do not package this build. Exe output tail:")
    print(tail_text())
    return 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("exe", type=Path)
    p.add_argument("--port", type=int, default=9999)
    p.add_argument("--frames", type=int, default=600)
    # A frozen onefile exe unpacks ~10 MB of DLLs to a temp dir and cold-imports numpy/gymnasium
    # before it says anything, so first-run start-up is much slower than the source path's.
    p.add_argument("--handshake-timeout", type=float, default=120.0)
    a = p.parse_args()
    if not a.exe.is_file():
        print(f"FAIL: no such exe: {a.exe}")
        return 1
    return run(a.exe.resolve(), a.port, a.frames, a.handshake_timeout)


if __name__ == "__main__":
    raise SystemExit(main())
