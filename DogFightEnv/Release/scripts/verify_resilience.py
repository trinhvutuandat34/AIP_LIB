"""Pre-submission DQ check for student/submission_resilience.py -- no server required.

WHY. Two network-instability incidents is elimination (COMPETITION_RULES.md Sec 8), and the two
guards that exist for it -- `supervise_client`'s reconnect loop and `ResilientActionProvider`'s
never-raise contract -- were written 2026-08-05 and have NEVER been executed. A guard that has
never run is not a guard; it is an untested assumption on the one path that cannot be retried.

This exercises both against injected faults, in-process, with `time.sleep` stubbed so the whole
check finishes in well under a second. It does NOT replace a real induced-packet-loss rehearsal
against a live server -- it removes the failure modes that can be found without one.

    python scripts/verify_resilience.py

Exit code 0 = all checks pass. Non-zero = do not submit until fixed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for _p in (ROOT, SRC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np

from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult
from student import submission_resilience as SR
from student.submission_resilience import ResilientActionProvider, supervise_client

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


# ── ResilientActionProvider ───────────────────────────────────────────────────
class _Boom(ActionProvider):
    def compute_action(self, context):
        raise RuntimeError("inner provider exploded")


class _NaN(ActionProvider):
    def compute_action(self, context):
        return ActionResult(action=np.array([np.nan, 0.0, 0.0, 0.5]), source="nan")


class _BadShape(ActionProvider):
    def compute_action(self, context):
        return ActionResult(action=np.array([0.1, 0.2]), source="short")


class _OutOfRange(ActionProvider):
    def compute_action(self, context):
        return ActionResult(action=np.array([9.0, -9.0, 9.0, 9.0]), source="wild")


class _Good(ActionProvider):
    def compute_action(self, context):
        return ActionResult(action=np.array([0.3, -0.2, 0.1, 0.7]), source="good")


def verify_provider() -> None:
    print("ResilientActionProvider -- must never raise, never emit non-finite:")
    ctx = ActionContext(sim=None, opponent_sim=None)

    for label, inner in (
        ("inner raises", _Boom()),
        ("inner returns NaN", _NaN()),
        ("inner returns wrong shape", _BadShape()),
        ("inner returns out-of-range", _OutOfRange()),
    ):
        p = ResilientActionProvider(inner)
        try:
            a = np.asarray(p.compute_action(ctx).action, dtype=np.float32)
            ok = a.shape == (4,) and np.all(np.isfinite(a)) and np.all(np.abs(a) <= 1.0 + 1e-6)
            check(label, ok, f"action={a}")
        except Exception as exc:
            check(label, False, f"RAISED {type(exc).__name__}: {exc}")

    # Last-good retention: a good action, then a failure, must reuse the good one.
    class _Flaky(ActionProvider):
        def __init__(self):
            self.n = 0

        def compute_action(self, context):
            self.n += 1
            if self.n == 1:
                return ActionResult(action=np.array([0.3, -0.2, 0.1, 0.7]), source="good")
            raise RuntimeError("now broken")

    p = ResilientActionProvider(_Flaky())
    first = np.asarray(p.compute_action(ctx).action, dtype=np.float32)
    second = np.asarray(p.compute_action(ctx).action, dtype=np.float32)
    check("falls back to LAST GOOD action, not neutral",
          np.allclose(first, second), f"{first} -> {second}")

    # reset() must swallow inner errors too -- it runs on the same no-escape path.
    class _ResetBoom(ActionProvider):
        def reset(self, context=None):
            raise RuntimeError("reset exploded")

        def compute_action(self, context):
            return ActionResult(action=np.zeros(4), source="x")

    try:
        ResilientActionProvider(_ResetBoom()).reset(None)
        check("reset() swallows inner errors", True)
    except Exception as exc:
        check("reset() swallows inner errors", False, f"RAISED {type(exc).__name__}")

    # A healthy provider must pass through untouched.
    p = ResilientActionProvider(_Good())
    r = p.compute_action(ctx)
    check("healthy provider passes through",
          r.source == "good" and np.allclose(np.asarray(r.action), [0.3, -0.2, 0.1, 0.7]))


# ── supervise_client ──────────────────────────────────────────────────────────
class _Client:
    def __init__(self, behaviour, log):
        self.server_ip, self.server_port = "127.0.0.1", 9999
        self._behaviour = behaviour
        self._log = log
        self.stopped = False

    def run(self):
        self._log.append("run")
        action = self._behaviour.pop(0) if self._behaviour else "return"
        if action == "raise":
            raise ConnectionResetError("connection reset by peer")
        if action == "stop":
            raise KeyboardInterrupt()
        return  # receive loop exited == connection lost

    def stop(self):
        self.stopped = True


def verify_supervisor() -> None:
    print("\nsupervise_client -- must reconnect on drop and crash, and stop cleanly:")
    sleeps: list[float] = []
    real_sleep = SR.time.sleep
    SR.time.sleep = lambda s: sleeps.append(s)   # keep the check instant
    try:
        # A dropped connection, a hard crash, another drop, then Ctrl-C.
        behaviour = ["return", "raise", "return", "stop"]
        log: list[str] = []
        built: list[_Client] = []

        def make_client():
            c = _Client(behaviour, log)
            built.append(c)
            return c

        try:
            supervise_client(make_client, max_backoff_sec=5.0, log=lambda *a, **k: None)
            returned_cleanly = True
        except Exception as exc:
            returned_cleanly = False
            check("supervisor propagated an exception", False, f"{type(exc).__name__}: {exc}")

        check("survives a dropped connection AND a crash", len(log) >= 4,
              f"{len(log)} run() calls")
        check("builds a FRESH client per attempt", len(built) >= 4, f"{len(built)} clients")
        check("stops cleanly on KeyboardInterrupt", returned_cleanly)
        check("stop() called on every client", all(c.stopped for c in built))
        check("backoff is capped at max_backoff_sec",
              bool(sleeps) and max(sleeps) <= 5.0, f"sleeps={sleeps}")
        check("backoff is bounded below (retries stay frequent)",
              all(s >= 1.0 for s in sleeps) if sleeps else False, f"sleeps={sleeps}")
    finally:
        SR.time.sleep = real_sleep


# ── added 2026-08-11 ──────────────────────────────────────────────────────────
# Three gaps found while re-verifying this file's subject. The cases above cover a provider that
# hiccups occasionally and a client whose run() drops or crashes; these cover a provider that is
# broken for the REST OF THE MATCH, a server we cannot reach AT ALL (make_client itself failing,
# which the run()-based cases never exercise), and close() throwing on the way out.
def verify_sustained_faults() -> None:
    print("\nSustained / connect-time faults -- the match-day shapes not covered above:")

    class _AlwaysBroken(ActionProvider):
        def __init__(self):
            self.calls = 0

        def compute_action(self, context):
            self.calls += 1
            if self.calls == 1:                      # one good action to seed the fallback
                return ActionResult(action=np.array([0.3, -0.2, 0.1, 0.7], np.float32), source="good")
            raise RuntimeError("provider broken for the rest of the match")

        def close(self):
            raise RuntimeError("close exploded")

    inner = _AlwaysBroken()
    provider = ResilientActionProvider(inner)
    ctx = ActionContext(sim=None, opponent_sim=None)
    provider.compute_action(ctx)
    bad = 0
    for _ in range(500):
        r = provider.compute_action(ctx)
        a = np.asarray(r.action).reshape(-1)
        if a.shape != (4,) or not np.all(np.isfinite(a)):
            bad += 1
    check("500 consecutive provider failures still yield usable actions", bad == 0,
          f"{bad} bad of 500")

    try:
        provider.close()
        closed_ok = True
    except Exception:
        closed_ok = False
    check("close() swallows an inner exception", closed_ok)

    # make_client() itself failing -- i.e. we cannot even open a socket. The _Client cases above
    # all assume construction succeeds, so this path was untested.
    sleeps: list[float] = []
    real_sleep = SR.time.sleep
    SR.time.sleep = lambda s: sleeps.append(s)
    try:
        attempts = {"n": 0}

        def flaky_make_client():
            attempts["n"] += 1
            if attempts["n"] <= 8:
                raise OSError("cannot reach server")
            raise KeyboardInterrupt()

        try:
            supervise_client(flaky_make_client, max_backoff_sec=5.0, log=lambda *a, **k: None)
            survived = True
        except Exception:
            survived = False
        check("survives 8 consecutive CONNECT failures and keeps retrying",
              survived and attempts["n"] == 9, f"{attempts['n']} attempts")
        check("backoff grows then caps during a connect outage",
              bool(sleeps) and max(sleeps) <= 5.0 and max(sleeps) > 1.0, f"sleeps={sleeps}")
    finally:
        SR.time.sleep = real_sleep


def main() -> int:
    print("=" * 72)
    print("Pre-submission resilience check (no server required)")
    print("=" * 72)
    verify_provider()
    verify_supervisor()
    verify_sustained_faults()
    print("\n" + "=" * 72)
    if FAILURES:
        print(f"FAILED {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        print("DO NOT SUBMIT until these pass -- each is a live disconnect/DQ path.")
        return 1
    print("All resilience checks passed.")
    print("NOTE: this covers only what is testable without a server. A real induced")
    print("packet-loss / latency rehearsal against a live or practice server is still owed")
    print("(COMPETITION_PLAN.md Sec 8) -- 2 instability incidents is elimination.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
