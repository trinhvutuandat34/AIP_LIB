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
  3. (added 2026-08-21, F40 -- found against a REAL server, not reasoned about) A SILENT server
     produces only socket.timeout, which client.py:242-243 swallows with `continue`. The
     receive loop therefore spins forever, run() never returns, and defense 1 above never
     fires. Measured live: connected, 0 frames for 45 s, 0 reconnect attempts, no warning.

The client cannot be edited (no-edit boundary), so all three defenses are re-homed here in
student space and wired in from run_unreal_inference.py and student/my_submission.py:
  * supervise_client() -- a reconnect SUPERVISOR around run(): any exit/exception -> rebuild a
    fresh client and reconnect with capped backoff, so a transient network error self-heals.
  * ResilientActionProvider -- a provider WRAPPER that never raises and never emits a
    non-finite/mis-shaped action, so a provider error cannot propagate out of run(). It also
    timestamps every server-driven call, which is what makes silence observable at all.
  * _silence_watchdog() -- warns (and optionally reconnects) when the server stops speaking.

This adds no new competition behavior; it only keeps the existing client connected. Pure
student-space (new file under student/, no platform edit).
"""
from __future__ import annotations

import threading
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
        # --- server-liveness bookkeeping (2026-08-21, F40) ---------------------------------
        # compute_action() is driven by the client's receive loop: it is called once per
        # PlaneInfo pair the SERVER sends us. So "time since the last call" is a direct proxy
        # for "time since the server last spoke to us", and it is the only such signal
        # available from student space -- the socket itself lives inside the no-edit client.
        # Marked at ENTRY, not on success: a frame arriving is what we are measuring, not
        # whether the provider then handled it.
        self._call_count = 0
        self._last_call_monotonic: "float | None" = None

    @property
    def call_count(self) -> int:
        """Number of frames the server has driven through us since construction."""
        return self._call_count

    @property
    def last_call_monotonic(self) -> "float | None":
        """time.monotonic() of the most recent server-driven call, or None if never called."""
        return self._last_call_monotonic

    def reset(self, context: "ActionContext | None" = None) -> None:
        try:
            self._inner.reset(context)
        except Exception as exc:  # a reset error must never escape into the client
            print(f"[resilience] inner.reset error ignored: {type(exc).__name__}: {exc}", flush=True)

    def compute_action(self, context: ActionContext) -> ActionResult:
        self._call_count += 1
        self._last_call_monotonic = time.monotonic()
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


def _silence_watchdog(client, activity, *, warn_sec: float, reconnect_sec: float,
                      stop_event: "threading.Event", log) -> None:
    """Watch for SERVER SILENCE -- the one disconnect mode the supervisor cannot see.

    Found live 2026-08-21 (F40) against a real DogFightViewer: the client connected, received
    ZERO frames for 45 s, and supervise_client never noticed. Mechanism, in the no-edit client
    (src/dogfight/unreal/client.py:242-243):

        except socket.timeout:
            continue

    A silent server produces only recv timeouts, never an OSError, so _receive_loop() spins
    forever, run() never returns, and the reconnect supervisor above is never triggered. We sit
    connected and mute indefinitely. Confirmed not to be our bug: the organizers' own reference
    client (unreal_bt_client.exe) reported rx_packets=0 against the same server in the same
    minute.

    Two distinct silence cases, deliberately treated differently:

      * NEVER received a frame (call_count == 0). Could be a wrong SERVER_IP, a server that has
        not started the match yet, or a pre-match lobby wait. Reconnecting cannot fix any of
        those -- the heartbeat thread is already re-announcing us every heartbeat_interval_sec
        -- so this only WARNS. Warning is the whole point: a silent failure here is invisible
        until the match is over, and SERVER_IP is a known-open question on this project.
      * Frames FLOWED, then stopped (call_count > 0). That is a genuine mid-stream dropout, and
        the current behaviour -- sit mute until the match ends -- is a guaranteed loss. Only
        this case may force a reconnect, and only after reconnect_sec.

    reconnect_sec defaults to OFF (0.0) to match the organizers' reference client, whose
    --server-timeout-sec is documented "Warn (log only)". That is evidence that server silence
    is expected often enough that the reference does not reconnect on it -- plausibly normal
    between episodes. Enabling a reconnect on a gap that is merely a long inter-match pause
    would manufacture exactly the "network instability" COMPETITION_RULES Sec 8 disqualifies
    for. Turn it on only with a measured inter-episode pause to size it against.
    """
    warned_at = 0.0
    while not stop_event.is_set():
        stop_event.wait(0.5)
        if stop_event.is_set():
            return
        now = time.monotonic()
        last = activity.last_call_monotonic
        if activity.call_count == 0:
            # Never heard from the server at all. Warn on a slow cadence, never reconnect.
            if warn_sec > 0 and now - warned_at >= max(warn_sec, 5.0):
                warned_at = now
                log(f"[resilience] WARNING: no frames from server yet "
                    f"({getattr(client, 'server_ip', '?')}:{getattr(client, 'server_port', '?')}) "
                    f"-- connected but never received a PlaneInfo. Check SERVER_IP/port and "
                    f"that the match has started.")
            continue
        silence = now - (last if last is not None else now)
        if warn_sec > 0 and silence >= warn_sec and now - warned_at >= warn_sec:
            warned_at = now
            log(f"[resilience] WARNING: server silent for {silence:.1f}s "
                f"after {activity.call_count} frames")
        if reconnect_sec > 0 and silence >= reconnect_sec:
            log(f"[resilience] server silent for {silence:.1f}s (>= {reconnect_sec:.1f}s) "
                f"-> forcing reconnect")
            _safe_stop(client)  # closes the socket -> receive loop breaks -> run() returns
            return


def supervise_client(make_client, *, max_backoff_sec: float = 5.0, log=print,
                     activity=None, silence_warn_sec: float = 5.0,
                     silence_reconnect_sec: float = 0.0) -> None:
    """Run client.run() in a reconnect loop so a transient network error does not kill us.

    The no-edit client's run() returns only when its receive loop exits (an OSError break) or
    throws, so ANY return already means 'connection lost' -> reconnect. Backoff is capped and
    small (default 5 s) so we keep trying often enough to re-establish before the server's
    disconnect window matters. Ctrl-C stops cleanly.

    make_client must build a FRESH client each call (the old socket is closed by stop()) and
    should REUSE the already-built, expensive action provider / command policy so a reconnect
    does NOT reload the model.

    activity (optional, 2026-08-21 F40): the ResilientActionProvider wrapping this run's
    provider. Supplying it arms _silence_watchdog() -- see there for why a silent server is
    invisible to this loop without it, and why the reconnect half defaults to off. Omitting it
    keeps the exact pre-F40 behaviour.
    """
    backoff = 1.0
    attempt = 0
    while True:
        attempt += 1
        client = None
        stop_event = threading.Event()
        watchdog = None
        try:
            client = make_client()
            log(
                f"[resilience] connect attempt {attempt} -> "
                f"{getattr(client, 'server_ip', '?')}:{getattr(client, 'server_port', '?')}"
            )
            if activity is not None and (silence_warn_sec > 0 or silence_reconnect_sec > 0):
                watchdog = threading.Thread(
                    target=_silence_watchdog, args=(client, activity),
                    kwargs={"warn_sec": silence_warn_sec,
                            "reconnect_sec": silence_reconnect_sec,
                            "stop_event": stop_event, "log": log},
                    daemon=True,
                )
                watchdog.start()
            client.run()  # blocks until the receive loop exits
            log("[resilience] client.run() returned (receive loop exited) -> reconnecting")
        except KeyboardInterrupt:
            log("[resilience] KeyboardInterrupt -> stopping supervisor")
            stop_event.set()
            _safe_stop(client)
            return
        except Exception as exc:
            log(f"[resilience] client crashed ({type(exc).__name__}: {exc}) -> reconnect in {backoff:.1f}s")
            traceback.print_exc()
        finally:
            stop_event.set()
            if watchdog is not None:
                watchdog.join(timeout=1.0)
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
