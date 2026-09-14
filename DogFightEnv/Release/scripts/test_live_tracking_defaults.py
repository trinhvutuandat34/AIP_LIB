"""Check that every live tracking mode builds the adopted Model 1, including CLI overrides.

    python scripts/test_live_tracking_defaults.py
"""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_unreal_inference as live
from student.controller_providers import get_model_profile


def main():
    with TemporaryDirectory() as bundle:
        for mode in ("vptrack", "hybrid_vptrack", "hybrid_gated"):
            for override in (False, True):
                argv = ["run_unreal_inference.py", "--mode", mode, "--bundle-dir", bundle]
                expected = get_model_profile(1)
                if override:
                    argv += ["--vptrack-standoff-m", "125", "--vptrack-adaptive-range", "0",
                             "--vptrack-deck-ttc", "2"]
                    expected.update(standoff_m=125, adaptive_range=False, deck_ttc_s=2)
                # No trained weights are needed to check the real BT tracking provider.
                with patch.object(sys, "argv", argv), patch.object(live, "RemappedRLProvider"):
                    args = live.parse_args()
                    provider = live._build_action_provider_raw(args, args.observation_mode)
                    floor = provider if mode == "vptrack" else provider.secondary_provider
                    for key, value in expected.items():
                        assert getattr(floor, key) == value, (mode, override, key, value)
                    provider.close()
    print("PASS: adopted tracking defaults and overrides reach all three live tracking modes")


if __name__ == "__main__":
    main()
