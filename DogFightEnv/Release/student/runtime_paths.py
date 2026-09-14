"""Where the runtime's files live, whether we are running from source or from the frozen .exe.

WHY THIS EXISTS (2026-09-08). The finals require a PyInstaller **onefile** executable
(COMPETITION_RULES.md Sec 7.1 / F75: exactly two files at the ZIP root), and three separate places
in the runtime locate their assets by walking up from `__file__`. Under onefile every module is
unpacked into a temporary `sys._MEIPASS` directory whose depth does not match the source tree, so
each of those walks lands somewhere else -- or outside the bundle entirely:

  * `src/dogfight/ai/native_bt.py:99` walks FOUR `os.path.dirname` levels at import time. From
    source that is `.../Release`; frozen it is `<_MEIPASS>/dogfight/ai/` minus four, i.e.
    `C:\\Users\\<user>\\AppData\\Local\\Temp` -- and `AIPilot.__init__` then raises
    `FileNotFoundError` before a single packet moves.
  * `JSBSimWrapper.py:73-77` loads `JSBSimAIPLib.dll` from its own directory at IMPORT time.
  * `JSBSimWrapper.py:118` reads `aircraft/<f>/<f>_init.xml` relative to the same directory.

`src/dogfight/**` is a hard no-edit boundary, so none of those can be fixed in place. They do not
have to be: `AIPilot.__init__` does `os.path.join(lib_path, filename)`, and `os.path.join`
DISCARDS its left operand when the right one is absolute. So handing it an absolute path from the
entry point fixes the DLL lookup without touching the platform at all. The other two are satisfied
by the bundle layout instead -- `build_exe.py` places the DLLs, the Rule XMLs, `aircraft/` and
`engine/` at the ROOT of `_MEIPASS`, mirroring `Release/` exactly, so every `__file__`-relative
lookup that resolves to the bundle root keeps working unchanged.

TWO DIRECTORIES, AND THEY ARE NOT THE SAME ONE:
  * `base_dir()`  -- the *assets* root. Frozen: `sys._MEIPASS`, the unpacked bundle, which is a
    fresh temp directory per launch and is deleted on exit.
  * `exe_dir()`   -- the directory holding the executable itself. This is where `config.json`
    lives, because the ZIP puts it beside the exe, not inside it.
Conflating them means `config.json` is looked for in a temp directory that never contains it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Fixed by the organizers (COMPETITION_RULES.md Sec 7.1): the engagement server is on loopback.
# These are the fallbacks when config.json is absent or unreadable -- never a reason to fail.
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_SERVER_PORT = 9999

CONFIG_FILENAME = "config.json"

# Key spellings accepted from config.json. The organizers specified the VALUES (127.0.0.1:9999)
# but never published the schema, so read tolerantly rather than guessing one spelling and
# failing closed on match day. First match wins, checked in this order.
_IP_KEYS = ("ip", "server_ip", "serverIp", "host", "address", "server_address")
_PORT_KEYS = ("port", "server_port", "serverPort")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def base_dir() -> Path:
    """Root of the runtime assets: DLLs, Rule XMLs, `aircraft/`, `engine/`.

    Frozen -> the unpacked onefile bundle. From source -> `DogFightEnv/Release`, which is this
    file's parent's parent and is what every existing `__file__` walk already resolves to.
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def exe_dir() -> Path:
    """Directory the user actually unzipped into -- where `config.json` sits.

    NOT `base_dir()` when frozen: the bundle is a per-launch temp directory and the ZIP puts
    `config.json` next to the executable.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def asset(*parts: str) -> str:
    """Absolute path to a bundled runtime asset, as a str.

    Absolute is the point: passing this as `AIPilot(filename=...)` makes
    `native_bt.py:104`'s `os.path.join(lib_path, filename)` ignore its own broken `lib_path`.
    """
    return str(base_dir().joinpath(*parts))


def _coerce_port(value) -> int | None:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def _argv_value(argv: list[str], name: str) -> str | None:
    """First `name value` or `name=value` in `argv`, else None.

    A manual scan, not argparse: `student/my_submission.py` (the frozen entry point) has never
    called `parse_args()` -- F69 found that the only place that did was `run_unreal_inference.py`,
    a dev tool that never ships. A real argparse instance would reject any flag it does not know,
    which is exactly the startup-crash class F42/F69 exist to rule out. This only looks for what
    it needs and silently ignores everything else the organizer's launcher passes alongside it.
    """
    prefix = name + "="
    for i, tok in enumerate(argv):
        if tok == name and i + 1 < len(argv):
            return argv[i + 1]
        if tok.startswith(prefix):
            return tok[len(prefix):]
    return None


def load_network_config(path: Path | None = None, argv: list[str] | None = None) -> tuple[str, int, str]:
    """Return `(ip, port, source)` for the engagement server.

    Resolution order, most specific first:
      1. `--server-ip` / `--server-port` on the command line -- CORRECTED 2026-09-12. The
         2026-09-08 organizer answer on record said connection info is fixed (127.0.0.1:9999 via
         config.json); the team's later understanding is that the real match address is handed to
         the exe the same way the organizers launch their own `unreal_bt_client.exe`, i.e.
         `--server-ip <ip> --server-port <port>` (see `LIVE_AND_CUTOFF_COMMANDS.md`'s flag dump
         for that binary). This is a submission that gets ONE shot (F39), so both delivery
         mechanisms are honoured rather than betting on which organizer answer holds -- CLI wins
         because it is the one that matches how the reference client is actually run.
      2. `DOGFIGHT_SERVER_IP` / `DOGFIGHT_SERVER_PORT` in the environment -- kept because every
         rehearsal script and the match-day runbook use them, and they are a channel that needs
         no relaunch flags if the exe is already wrapped by a launcher script.
      3. `config.json` beside the executable.
      4. The organizers' 2026-09-08 fixed values, 127.0.0.1:9999 -- now just the last-resort
         default for local testing, not an assumption about match day.

    NEVER RAISES. A malformed or unreadable config.json falls through to the defaults with a
    printed warning: the values are fixed and known, so a parse error must not cost the match.
    `source` says which rung answered, so the startup banner can show it and an operator can see
    at a glance whether their config.json (or launch flags) were actually read.
    """
    cli_argv = sys.argv[1:] if argv is None else argv
    cli_ip = _argv_value(cli_argv, "--server-ip")
    cli_port = _coerce_port(_argv_value(cli_argv, "--server-port"))
    if cli_ip and cli_port:
        return cli_ip, cli_port, "cli"
    if cli_ip or cli_port:
        # ALL-OR-NOTHING. These are typed at the machine moments before the match, unlike
        # config.json -- half-applying one good CLI value and falling through to a DIFFERENT
        # source for the other would silently connect to an ip:port neither source actually
        # named. Warn and ignore both rather than guess.
        print(f"[runtime_paths] incomplete --server-ip/--server-port on the command line "
              f"(ip={cli_ip!r} port={_argv_value(cli_argv, '--server-port')!r}); "
              "ignoring both, falling through to env/config.json/default", flush=True)

    env_ip = os.environ.get("DOGFIGHT_SERVER_IP")
    env_port = _coerce_port(os.environ.get("DOGFIGHT_SERVER_PORT"))
    if env_ip and env_port:
        return env_ip, env_port, "environment"

    cfg_path = path if path is not None else (exe_dir() / CONFIG_FILENAME)
    ip = port = None
    source = "default"
    try:
        if cfg_path.is_file():
            data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            # Tolerate both a flat object and one nesting the pair under a section.
            for scope in (data, data.get("server"), data.get("network")) if isinstance(data, dict) else ():
                if not isinstance(scope, dict):
                    continue
                if ip is None:
                    ip = next((str(scope[k]).strip() for k in _IP_KEYS
                               if scope.get(k) not in (None, "")), None)
                if port is None:
                    port = next((p for k in _PORT_KEYS
                                 if (p := _coerce_port(scope.get(k))) is not None), None)
            if ip or port:
                source = str(cfg_path)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"[runtime_paths] {cfg_path} unreadable ({exc}); "
              f"using {DEFAULT_SERVER_IP}:{DEFAULT_SERVER_PORT}", flush=True)

    # CLI never reaches here with only one of the two set -- either both were valid and returned
    # above, or the incomplete-CLI branch already warned and this falls through as if CLI said
    # nothing at all.
    return (env_ip or ip or DEFAULT_SERVER_IP,
            env_port or port or DEFAULT_SERVER_PORT,
            "environment" if (env_ip or env_port) else source)
