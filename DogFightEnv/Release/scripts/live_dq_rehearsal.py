"""Live DQ rehearsal (2026-08-13) -- the induced-fault test against a REAL server that
COMPETITION_PLAN.md 4.1 F9/P9 has flagged as owed since 2026-08-05 and never run.

scripts/verify_resilience.py proves ResilientActionProvider/supervise_client absorb faults
IN-PROCESS (time.sleep stubbed, no socket). This script is the missing half: the SAME
production wrapper stack from student/my_submission.py, pointed at a REAL listening server
(a teammate's DogFightViewer.exe instance, or eventually the competition server), with REAL
network faults induced from the outside via a Windows Firewall rule -- not a mocked exception.

USAGE
    python scripts\\live_dq_rehearsal.py --server-ip <IP> --server-port <PORT> --duration-sec 300
    python scripts\\live_dq_rehearsal.py --server-ip <IP> --server-port <PORT> \\
        --induce-faults --block-sec 8 --unblock-sec 20 --fault-cycles 5

Without --induce-faults this just proves clean connect/run/disconnect against a real server --
worth doing FIRST, once, before ever adding faults. With --induce-faults it adds a background
thread that blocks/unblocks outbound UDP to server-ip:server-port via `netsh advfirewall`
(temporary rule, always removed on exit -- including on Ctrl-C or a crash) so the client
experiences a genuine connection loss, not a stubbed one.

Uses MODE="vptrack" -- the actual shipping submission path (student/controller_providers.py,
no RL bundle) -- via student.my_submission.build_action_provider(), so this rehearses the exact
provider stack that ships, not a synthetic stand-in. BT_RULE_XML / BT_DLL are left at
my_submission.py's own current settings; this script does not change what the tree does.

Writes a timestamped .log (every connect/disconnect/reconnect/fault event) and a .csv summary
(one row per action-provider call: timestamp, whether the action was finite, whether it was a
resilient-fallback) so the rehearsal produces the same kind of citable artifact as every other
eval in this project. Both land under artifacts/eval/.

Ctrl-C stops cleanly: the firewall rule (if any) is removed, the client is stopped, and both
artifacts are flushed and closed before exit.
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import threading
import time
from pathlib import Path

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dogfight.ai.bt_rule_manager import activate_rule_xml
from dogfight.unreal import AIType, ProviderCommandPolicy, UnrealAIPilotUDPClient

from student import my_submission
from student.submission_resilience import ResilientActionProvider, supervise_client

FIREWALL_RULE_NAME = "AIP_DQ_REHEARSAL_BLOCK"


class RehearsalLogger:
    """Wraps print() so every line also lands in a timestamped .log file with a wall-clock
    prefix, and keeps a small in-memory count of event categories for the closing summary."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._fh = open(log_path, "a", encoding="utf-8")
        self.counts: dict[str, int] = {}
        self.t0 = time.monotonic()

    def __call__(self, msg: str) -> None:
        line = f"[t+{time.monotonic() - self.t0:8.2f}s] {msg}"
        print(line, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()
        for key in ("connect attempt", "returned", "crashed", "FAULT BLOCK", "FAULT UNBLOCK"):
            if key in msg:
                self.counts[key] = self.counts.get(key, 0) + 1

    def close(self) -> None:
        self._fh.close()


class CountingActionProvider:
    """Sits between ResilientActionProvider and the real provider stack purely to log one CSV
    row per call -- whether the action was a genuine result or a resilient-fallback -- without
    changing behaviour at all. Delegates everything."""

    def __init__(self, inner, csv_writer, csv_fh):
        self._inner = inner
        self._w = csv_writer
        self._fh = csv_fh
        self.n_calls = 0
        self.n_fallback = 0

    def reset(self, context=None):
        return self._inner.reset(context)

    def compute_action(self, context):
        result = self._inner.compute_action(context)
        self.n_calls += 1
        is_fallback = getattr(result, "source", "") == "resilient-fallback"
        if is_fallback:
            self.n_fallback += 1
        self._w.writerow([time.time(), self.n_calls, is_fallback, getattr(result, "source", "")])
        if self.n_calls % 500 == 0:
            self._fh.flush()
        return result

    def close(self):
        return self._inner.close()


def _firewall_block(server_ip: str, server_port: int) -> None:
    subprocess.run(
        [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={FIREWALL_RULE_NAME}", "dir=out", "action=block", "protocol=UDP",
            f"remoteip={server_ip}", f"remoteport={server_port}",
        ],
        check=True, capture_output=True, text=True,
    )


def _firewall_unblock() -> None:
    subprocess.run(
        ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={FIREWALL_RULE_NAME}"],
        capture_output=True, text=True,  # do NOT check=True: fine if the rule is already gone
    )


def _fault_injector_thread(server_ip: str, server_port: int, block_sec: float,
                            unblock_sec: float, cycles: int, log: RehearsalLogger,
                            stop_event: threading.Event) -> None:
    log(f"[fault-injector] starting: {cycles} cycles, block {block_sec}s / unblock {unblock_sec}s")
    time.sleep(unblock_sec)  # let the connection establish cleanly first
    for i in range(1, cycles + 1):
        if stop_event.is_set():
            break
        log(f"[fault-injector] FAULT BLOCK #{i}/{cycles} -- blocking UDP to {server_ip}:{server_port}")
        _firewall_block(server_ip, server_port)
        stop_event.wait(block_sec)
        log(f"[fault-injector] FAULT UNBLOCK #{i}/{cycles} -- restoring connectivity")
        _firewall_unblock()
        stop_event.wait(unblock_sec)
    log("[fault-injector] all cycles complete")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server-ip", required=True)
    ap.add_argument("--server-port", type=int, default=my_submission.SERVER_PORT)
    ap.add_argument("--team-name", default=my_submission.TEAM_NAME)
    ap.add_argument("--duration-sec", type=float, default=180.0,
                     help="Total rehearsal wall-clock time. Ctrl-C stops early and cleanly.")
    ap.add_argument("--induce-faults", action="store_true",
                     help="Toggle a Windows Firewall UDP block against server-ip:server-port. "
                          "Requires an elevated (Administrator) shell for netsh to succeed.")
    ap.add_argument("--block-sec", type=float, default=8.0)
    ap.add_argument("--unblock-sec", type=float, default=20.0)
    ap.add_argument("--fault-cycles", type=int, default=3)
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "artifacts" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"live_dq_rehearsal_{stamp}.log"
    csv_path = out_dir / f"live_dq_rehearsal_{stamp}.csv"

    log = RehearsalLogger(log_path)
    csv_fh = open(csv_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_fh)
    writer.writerow(["unix_time", "call_index", "is_fallback", "source"])

    log(f"=== live DQ rehearsal starting -- server {args.server_ip}:{args.server_port}, "
        f"team {args.team_name}, duration {args.duration_sec}s, "
        f"induce_faults={args.induce_faults} ===")
    log(f"log: {log_path}")
    log(f"csv: {csv_path}")

    with activate_rule_xml(my_submission.BT_RULE_XML, ROOT):
        raw_provider = my_submission.build_action_provider()
        counting_provider = CountingActionProvider(raw_provider, writer, csv_fh)
        action_provider = ResilientActionProvider(counting_provider)

        observation_hook = None
        if my_submission.OBSERVATION_MODULE:
            from dogfight.ai.student_hooks import load_observation_hook
            observation_hook = load_observation_hook(my_submission.OBSERVATION_MODULE)

        command_policy = ProviderCommandPolicy(
            action_provider=action_provider,
            observation_mode=observation_hook["mode"] if observation_hook else my_submission.OBSERVATION_MODE,
            observation_fn=observation_hook["build_observation"] if observation_hook else None,
            ownship_force_side=1,
            target_force_side=2,
            action_repeat=my_submission.ACTION_REPEAT,
            debug_action_repeat=False,
        )

        def make_client():
            return UnrealAIPilotUDPClient(
                command_policy=command_policy,
                server_ip=args.server_ip,
                server_port=args.server_port,
                team_name=args.team_name,
                ai_type=AIType.Fusion,
                heartbeat_interval_sec=my_submission.HEARTBEAT_SEC,
                command_delay_sec=my_submission.COMMAND_DELAY_SEC,
                recv_timeout_sec=my_submission.RECV_TIMEOUT_SEC,
                enable_terminal_monitor=False,
            )

        stop_event = threading.Event()
        fault_thread = None
        if args.induce_faults:
            _firewall_unblock()  # clear any stale rule from a prior crashed run, ignore errors
            fault_thread = threading.Thread(
                target=_fault_injector_thread,
                args=(args.server_ip, args.server_port, args.block_sec, args.unblock_sec,
                      args.fault_cycles, log, stop_event),
                daemon=True,
            )
            fault_thread.start()

        supervisor_thread = threading.Thread(
            target=supervise_client, args=(make_client,), kwargs={"log": log}, daemon=True,
        )
        supervisor_thread.start()

        try:
            deadline = time.monotonic() + args.duration_sec
            while time.monotonic() < deadline:
                time.sleep(0.5)
        except KeyboardInterrupt:
            log("=== Ctrl-C received, stopping rehearsal ===")
        finally:
            stop_event.set()
            if args.induce_faults:
                log("[fault-injector] removing firewall rule (cleanup)")
                _firewall_unblock()
            action_provider.close()

    csv_fh.close()
    log(f"=== rehearsal complete === total calls={counting_provider.n_calls} "
        f"fallback_calls={counting_provider.n_fallback} "
        f"connect_attempts={log.counts.get('connect attempt', 0)} "
        f"disconnects={log.counts.get('returned', 0) + log.counts.get('crashed', 0)} "
        f"fault_blocks={log.counts.get('FAULT BLOCK', 0)}")
    log.close()
    print(f"\nArtifacts:\n  {log_path}\n  {csv_path}")


if __name__ == "__main__":
    main()
