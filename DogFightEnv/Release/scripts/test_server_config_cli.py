"""Does the exe accept the match server address on the command line, like unreal_bt_client.exe?

    python scripts/test_server_config_cli.py

WHY. `student/my_submission.py` (the frozen entry point) never called `parse_args()` -- the
2026-09-08 organizer answer on record said the address is fixed (127.0.0.1:9999 via config.json).
2026-09-12: corrected to CLI args, `--server-ip <ip> --server-port <port>`, matching how the
organizers launch their own `unreal_bt_client.exe`. This pins the resolution order in
`runtime_paths.load_network_config()`: CLI beats env beats config.json beats the 127.0.0.1:9999
default.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE.parent), str(_HERE.parent / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from student import runtime_paths as rp


def main() -> int:
    tmp = _HERE.parent / "artifacts" / "_test_server_config_cli.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps({"ip": "10.0.0.9", "port": 7777}), encoding="utf-8")
    try:
        # 1. nothing supplied -> the organizers' last-resort default
        assert rp.load_network_config(path=tmp.parent / "_missing.json", argv=[]) == (
            rp.DEFAULT_SERVER_IP, rp.DEFAULT_SERVER_PORT, "default")

        # 2. config.json alone answers
        ip, port, source = rp.load_network_config(path=tmp, argv=[])
        assert (ip, port) == ("10.0.0.9", 7777), (ip, port)
        assert source == str(tmp)

        # 3. env beats config.json (monkeypatched via os.environ, restored after)
        import os
        os.environ["DOGFIGHT_SERVER_IP"] = "10.0.0.5"
        os.environ["DOGFIGHT_SERVER_PORT"] = "6666"
        try:
            assert rp.load_network_config(path=tmp, argv=[]) == ("10.0.0.5", 6666, "environment")
        finally:
            del os.environ["DOGFIGHT_SERVER_IP"]
            del os.environ["DOGFIGHT_SERVER_PORT"]

        # 4. CLI beats env and config.json -- the actual match-day path, "name value" form
        os.environ["DOGFIGHT_SERVER_IP"] = "10.0.0.5"
        os.environ["DOGFIGHT_SERVER_PORT"] = "6666"
        try:
            argv = ["--team-name", "JinjjaBoramae", "--server-ip", "203.0.113.4",
                    "--server-port", "9999"]
            assert rp.load_network_config(path=tmp, argv=argv) == ("203.0.113.4", 9999, "cli")
        finally:
            del os.environ["DOGFIGHT_SERVER_IP"]
            del os.environ["DOGFIGHT_SERVER_PORT"]

        # 5. "--server-ip=value" form, and unknown flags around it do not break the scan
        argv = ["--server-ip=203.0.113.9", "--server-port=1234", "--ai-type", "RuleBased"]
        assert rp.load_network_config(path=tmp, argv=argv) == ("203.0.113.9", 1234, "cli")

        # 6. a malformed port on the CLI must not crash or silently win with a bad value
        argv = ["--server-ip", "203.0.113.9", "--server-port", "not-a-port"]
        ip, port, source = rp.load_network_config(path=tmp, argv=argv)
        assert (ip, port, source) == ("10.0.0.9", 7777, str(tmp)), (
            "an unparseable --server-port must fall through, not ship a bad port silently")
    finally:
        tmp.unlink(missing_ok=True)

    print("OK  --server-ip/--server-port outrank env, config.json and the loopback default; "
          "both 'name value' and 'name=value' forms parse; a bad --server-port falls through")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
