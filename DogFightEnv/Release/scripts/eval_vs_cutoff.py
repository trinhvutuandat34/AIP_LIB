"""Score any ownship backend against the organizers' real cutoff model, headless, at N episodes.

Adds `--target-backend cutoff` to scripts/eval_v5_vs_bt.py by patching its backend factory at
import time, so the entire existing scoring path -- match_base spawn geometry, the flat and
phased WEZ damage models, outcome classification, the CSV columns -- is reused unchanged. No
existing file is edited; this only adds a backend, in the same spirit as scripts/setup_peer_bt.py.

    python scripts/eval_vs_cutoff.py --ownship-backend vptrack --target-backend cutoff \
        --scenario-mode match_base --episodes 30 --out-csv artifacts/eval/vptrack_vs_cutoff.csv

Extra options beyond eval_v5_vs_bt's:
    --cutoff-action-repeat N   frames the cutoff holds each command (default 6, its competition
                               default). Pass 1 to remove the decision-rate asymmetry described
                               in scripts/cutoff_provider.py.
    --cutoff-exe PATH          override binary location.
    --cutoff-no-g-limit        do not apply the 10 G limiter to the cutoff side. Off by default:
                               our side is G-limited at the build_provider boundary, and leaving
                               the opponent unlimited would let it pull G the airframe does not
                               have and our own side is denied.

WHY THE `--target-backend bt` SUBSTITUTION BELOW. eval_v5_vs_bt's parser pins target_backend to a
`choices` list. Rather than reach into argparse internals (an earlier attempt recursed), argv is
rewritten to a value the parser accepts and the parsed value is corrected afterwards. The parser
is left completely untouched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_ROOT), str(_ROOT / "src"), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import eval_v5_vs_bt
from cutoff_provider import CutoffProvider
from student.controller_providers import GLimitedProvider
from student.g_limiter import G_LIMIT

_CUTOFF_OPTS: dict = {"action_repeat": 6, "exe_path": None, "g_limit": G_LIMIT}

_original_build = eval_v5_vs_bt.build_provider_or_none


def _build_provider_or_none(backend: str, **kwargs):
    if backend != "cutoff":
        return _original_build(backend, **kwargs)
    provider = CutoffProvider(
        exe_path=_CUTOFF_OPTS["exe_path"],
        action_repeat=_CUTOFF_OPTS["action_repeat"],
        # The cutoff flies the target seat, so it is force side 2 and its enemy is side 1.
        # These are BT blackboard labels only -- ownship identity comes from SetPlaneID.
        own_force_side=2,
        target_force_side=1,
    )
    limit = _CUTOFF_OPTS["g_limit"]
    return provider if limit is None else GLimitedProvider(provider, limit_g=float(limit))


def main() -> None:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--cutoff-action-repeat", type=int, default=6)
    pre.add_argument("--cutoff-exe", default=None)
    pre.add_argument("--cutoff-no-g-limit", action="store_true")
    mine, rest = pre.parse_known_args(sys.argv[1:])

    _CUTOFF_OPTS["action_repeat"] = int(mine.cutoff_action_repeat)
    _CUTOFF_OPTS["exe_path"] = mine.cutoff_exe
    _CUTOFF_OPTS["g_limit"] = None if mine.cutoff_no_g_limit else G_LIMIT

    wanted_cutoff = False
    for i, tok in enumerate(rest):
        if tok == "--target-backend" and i + 1 < len(rest) and rest[i + 1] == "cutoff":
            rest[i + 1] = "bt"
            wanted_cutoff = True
        elif tok == "--target-backend=cutoff":
            rest[i] = "--target-backend=bt"
            wanted_cutoff = True
    sys.argv = [sys.argv[0]] + rest

    eval_v5_vs_bt.build_provider_or_none = _build_provider_or_none

    original_parse = eval_v5_vs_bt.parse_args

    def parse_args():
        args = original_parse()
        if wanted_cutoff:
            args.target_backend = "cutoff"
        return args

    eval_v5_vs_bt.parse_args = parse_args
    eval_v5_vs_bt.main()


if __name__ == "__main__":
    main()
