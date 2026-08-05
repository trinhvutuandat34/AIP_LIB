# -*- coding: utf-8 -*-
"""DQ-avoidance hardening for the competition connector (2026-08-05).

COMPETITION_RULES.md Sec8: showing network instability 2+ times, or failing to connect, is
processed as DISQUALIFICATION. The in-platform UnrealAIPilotUDPClient
(src/dogfight/unreal/client.py -- a HARD no-edit boundary per
References and Manuals/CLAUDE.md) is fragile in two ways that risk exactly that DQ:

  1. _receive_loop() BREAKS on a single OSError (client.py:244-245) -- e.g. an ICMP
     port-unreachable surfacing as ECONNREFUSED on the connected UDP socket, or any transient
     network blip -> run() returns -> the client stops ENTIRELY and the server stops hearing
     from us (a disconnect on our side).
  2. Neither packet parsing nor command_policy.compute_command() is wrapped in try/except, so
     one garbled UDP packet or one provider hiccup/NaN throws straight out of run() and
     crashes the whole client.

The client cannot be edited (no-edit boundary), so both defenses are re-homed here in student
space and wired in from run_unreal_inference.py and student/my_submission.py:
  * supervise_client() -- a reconnect SUPERVISOR around run(): any exit/exception -> rebuild a
    fresh client and reconnect with capped backoff, so a transient network error self-heals.
  * ResilientActionProvider -- a provider WRAPPER that never raises and never emits a
    non-finite/mis-shaped action, so a provider error cannot propagate out of run().

This adds no new competition behavior; it only keeps the existing client connected. Pure
student-space (new file under student/, no platform edit).
"""
from __future__ import annotations

import time
import traceback

import numpy as np

from dogfight.ai.action_provider import ActionContext, ActionProvider, ActionResult, clip_action


class ResilientActionProvider(ActionProvider):
    """Delegates to an inner ActionProvider but NEVER raises and NEVER returns a non-finite or
    wrong-shaped action. On any inner error (or a NaN/Inf / bad-shape result) it returns the
    last good action, or a neutral action if none has succeeded yet, and clips into range.

    Rationale: a single provider hiccup must not propagate out of the no-edit client's run()
    and kill the UDP connection (-> DQ). This is defence-in-depth on top of my_submission.py's
    bundle-health gate: that catches NaN weights at load; this catches anything at runtime.
    """

    def __init__(self, inner: ActionProvider, neutral: "np.ndarray | None" = None):
        self._inner = inner
        self._last: "np.ndarray | None" = None
        self._neutral = (
            np.zeros(4, dtype=np.float32) if neutral is None
            else np.asarray(neutral, dtype=np.float32).reshape(-1)
        )
        self._error_count = 0

    def reset(self, context: "ActionContext | None" = None) -> None:
        try:
            self._inner.reset(context)
        except Exception as exc:  # a reset error must never escape into the client
            print(f"[resilience] inner.reset error ignored: {type(exc).__name__}: {exc}", flush=True)

    def compute_action(self, context: ActionContext) -> ActionResult:
        try:
            result = self._inner.compute_action(context)
            action = np.asarray(result.action, dtype=np.float32).reshape(-1)
            if action.shape != (4,) or not np.all(np.isfinite(action)):
                raise ValueError(f"bad action from inner provider: {action!r}")
            action = np.asarray(clip_action(action), dtype=np.float32).reshape(-1)
            self._last = action
            return ActionResult(
                action=action,
                source=result.source,
                confidence=getattr(result, "confidence", 1.0),
                info=(getattr(result, "info", {}) or {}),
            )
        except Exception as exc:
            self._error_count += 1
            if self._error_count <= 5 or self._error_count % 200 == 0:
                print(
                    f"[resilience] provider error #{self._error_count} "
                    f"({type(exc).__name__}: {exc}) -> fallback action",
                    flush=True,
                )
            fallback = self._last if self._last is not None else self._neutral
            return ActionResult(
                action=np.asarray(fallback, dtype=np.float32).reshape(-1),
                source="resilient-fallback",
                confidence=0.0,
                info={"fallback": True, "error": str(exc)},
            )

    def close(self) -> None:
        try:
            self._inner.close()
        except Exception:
            pass


def supervise_client(make_client, *, max_backoff_sec: float = 5.0, log=print) -> None:
    """Run client.run() in a reconnect loop so a transient network error does not kill us.

    The no-edit client's run() returns only when its receive loop exits (an OSError break) or
    throws, so ANY return already means 'connection lost' -> reconnect. Backoff is capped and
    small (default 5 s) so we keep trying often enough to re-establish before the server's
    disconnect window matters. Ctrl-C stops cleanly.

    make_client must build a FRESH client each call (the old socket is closed by stop()) and
    should REUSE the already-built, expensive action provider / command policy so a reconnect
    does NOT reload the model.
    """
    backoff = 1.0
    attempt = 0
    while True:
        attempt += 1
        client = None
        try:
            client = make_client()
            log(
                f"[resilience] connect attempt {attempt} -> "
                f"{getattr(client, 'server_ip', '?')}:{getattr(client, 'server_port', '?')}"
            )
            client.run()  # blocks until the receive loop exits
            log("[resilience] client.run() returned (receive loop exited) -> reconnecting")
        except KeyboardInterrupt:
            log("[resilience] KeyboardInterrupt -> stopping supervisor")
            _safe_stop(client)
            return
        except Exception as exc:
            log(f"[resilience] client crashed ({type(exc).__name__}: {exc}) -> reconnect in {backoff:.1f}s")
            traceback.print_exc()
        finally:
            _safe_stop(client)
        time.sleep(backoff)
        backoff = min(backoff * 2.0, max_backoff_sec)


def _safe_stop(client) -> None:
    if client is None:
        return
    try:
        client.stop()
    except Exception:
        pass
