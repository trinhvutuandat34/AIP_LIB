# -*- coding: utf-8 -*-
"""Shared CLI argument definitions for train_rllib.py and train_curriculum.py.

Lives at the Release root (an editable entry-script location), NOT under
src/dogfight/** -- that package is a hard no-edit boundary (see CLAUDE.md's
editing table). This keeps the two trainers' ~44 shared flags defined once
without touching the common platform.
"""
from __future__ import annotations

import argparse


def add_common_training_args(parser: argparse.ArgumentParser) -> None:
    """CLI flags shared by train_rllib.py and train_curriculum.py.

    Defaults follow train_rllib.py; train_curriculum.py overrides its
    per-script defaults (algorithm/output-name/output-tag) via
    parser.set_defaults(...) after calling this.
    """
    parser.add_argument("--algorithm", choices=["ppo", "sac"], default="ppo",
                        help="RLlib algorithm to use.")
    parser.add_argument("--framework", default="torch", choices=["torch"],
                        help="Deep learning framework.")
    parser.add_argument("--num-env-runners", type=int, default=1,
                        help="Number of RLlib env runners.")
    parser.add_argument("--observation-mode", default="tactical16",
                        choices=["classic12", "relative14", "tactical16", "custom"])
    parser.add_argument("--observation-module", default="",
                        help="Optional module with custom observation size and build_observation(...).")
    parser.add_argument("--target-behavior-dll", default="AIP_BASE_target.dll")
    parser.add_argument("--reward-module", default="",
                        help="Optional module with MY_REWARD_CONFIG and compute_reward(...).")
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--train-batch-size", type=int, default=4096)
    parser.add_argument("--minibatch-size", type=int, default=256)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-param", type=float, default=0.2)
    parser.add_argument("--tau", type=float, default=0.005)
    parser.add_argument("--target-entropy", default="auto")
    parser.add_argument("--replay-buffer-capacity", type=int, default=None,
                        help="SAC replay buffer capacity. Ignored by PPO.")
    parser.add_argument("--model-fcnet-hiddens", default=None,
                        help="Comma-separated RLlib model hidden sizes, e.g. 512,256,128.")
    parser.add_argument("--model-fcnet-activation", default=None,
                        help="RLlib model encoder activation, e.g. relu or tanh.")
    parser.add_argument("--model-head-fcnet-hiddens", default=None,
                        help="Comma-separated RLlib model head hidden sizes, or empty for none.")
    parser.add_argument("--model-head-fcnet-activation", default=None,
                        help="RLlib model head activation, e.g. relu or tanh.")
    parser.add_argument("--model-vf-share-layers", default=None,
                        help="Whether PPO value function shares layers: true or false.")
    parser.add_argument("--network-spec-json", default="",
                        help=("JSON object for DogFight sequence_v1 network layout. "
                              "Usually supplied by scripts/run_experiment.py from algo.network."))
    parser.add_argument("--use-lstm", action="store_true",
                        help="Enable RLlib DefaultModelConfig LSTM for non-SAC algorithms such as PPO.")
    parser.add_argument("--use-lstm-sac", action="store_true",
                        help="Enable the patched Ray 2.54 SAC actor-LSTM path.")
    parser.add_argument("--lstm-scope", choices=["actor_only", "actor_critic"],
                        default="actor_only",
                        help="SAC LSTM scope: actor_only or actor_critic recurrent Q.")
    parser.add_argument("--lstm-cell-size", type=int, default=64,
                        help="LSTM hidden state size for --use-lstm-sac.")
    parser.add_argument("--max-seq-len", type=int, default=8,
                        help="Replay/train sequence length for --use-lstm-sac.")
    parser.add_argument("--debug-io", dest="debug_io", action="store_true",
                        help="Print recurrent SAC/RLlib debug I/O shape checks.")
    parser.add_argument("--debug-lstm-io", dest="debug_io", action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument("--use-lstm-prioritized-replay", action="store_true",
                        help=("Use patched PrioritizedEpisodeReplayBuffer sequence sampling for "
                              "--use-lstm-sac. Requires the RLLibLstm replay patch."))
    parser.add_argument("--output-name", default="f16_single_agent")
    parser.add_argument("--output-tag", default="latest")
    parser.add_argument("--notes", default="",
                        help="Optional free-text notes for this training run.")
    parser.add_argument("--restore-checkpoint", default="",
                        help="Restore a full RLlib native checkpoint before training.")
    parser.add_argument("--init-bundle", "--restart-from-bundle", dest="init_bundle",
                        default="",
                        help="Load lightweight policy bundle weights before fresh training.")
    parser.add_argument("--policy-probe-interval", type=int, default=0,
                        help=("Log fixed policy probe actions every N iterations. "
                              "0 disables policy_probe.csv/jsonl."))
    parser.add_argument("--policy-probe-steps", type=int, default=4,
                        help="Number of recurrent inference steps per policy probe.")
    parser.add_argument("--no-policy-probe-print", action="store_true",
                        help="Write policy probe files without console summaries.")
    parser.add_argument("--engagement-log-interval", type=int, default=0,
                        help=("Run a short policy-vs-target replay every N iterations and save "
                              "Tacview CSV logs. 0 disables it."))
    parser.add_argument("--engagement-log-steps", type=int, default=600,
                        help="Maximum environment steps per engagement replay episode.")
    parser.add_argument("--engagement-log-episodes", type=int, default=1,
                        help="Number of replay episodes to save at each engagement-log interval.")
    parser.add_argument("--no-engagement-log-print", action="store_true",
                        help="Write engagement replay files without console summaries.")
    parser.add_argument("--experiment-yaml", default="",
                        help="Optional YAML experiment definition path.")
