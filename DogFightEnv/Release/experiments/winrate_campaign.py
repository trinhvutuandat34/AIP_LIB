"""Isolated, sequential controller experiments. Never changes the shipping runtime.

Run with the aip Python environment from Release:
    python experiments/winrate_campaign.py --variant baseline --episodes 12
    python experiments/winrate_campaign.py --variant closure --episodes 12
Variants are independent deltas against the adopted profile, not a cumulative stack.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/winrate_20260913'
VARIANTS = ('baseline', 'closure', 'hysteresis', 'recovery', 'aim_hold')
ARCHETYPES = ('cutoff', 'aggressor', 'mirror', 'sniper')
PROFILE = 'adaptive300_deckttc'
PAIR_FIELDS = ('episode', 'initial_distance_m', 'initial_altitude_m',
               'initial_speed_mps', 'initial_side')
MANIFEST_VERSION = 2
CAMPAIGN_ENVIRONMENT = {
    'DOGFIGHT_MATCH_ALTITUDE_RANGE_M': '609.6,9144',
    'DOGFIGHT_MATCH_SPEED_RANGE_MPS': '200,300',
    'DOGFIGHT_CUTOFF_LEGACY_Z': '0',
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_result(result, diagnostic, expected_episodes):
    """Reject truncated, appended, or mislabeled campaign output before it is scored."""
    with result.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_episodes:
        raise ValueError(f'{result}: expected {expected_episodes} rows, found {len(rows)}')
    missing = [name for name in PAIR_FIELDS if name not in (rows[0] if rows else {})]
    if missing:
        raise ValueError(f'{result}: missing pairing columns {missing}')
    try:
        episodes = [int(row['episode']) for row in rows]
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{result}: invalid episode identifiers') from exc
    wanted = list(range(expected_episodes))
    if episodes != wanted:
        raise ValueError(f'{result}: episode identifiers {episodes!r}, expected {wanted!r}')

    diagnostics = [json.loads(line) for line in diagnostic.read_text().splitlines() if line.strip()]
    diagnostic_episodes = [int(row['episode']) for row in diagnostics]
    if diagnostic_episodes != wanted:
        raise ValueError(f'{diagnostic}: episode identifiers {diagnostic_episodes!r}, expected {wanted!r}')
    return rows


def altered_tracking(source, variant):
    """Small source deltas retain the exact current controller around each experiment."""
    def replace(old, new):
        nonlocal source
        assert source.count(old) == 1, old
        source = source.replace(old, new)
    if variant == 'closure':
        replace('        if (self.standoff_m > 0.0 and rng < self.standoff_m',
                '''        radius = self.standoff_m
        now = self._match_time_s(own)
        previous = getattr(self, '_experiment_range', None)
        self._experiment_range = (now, rng)
        if previous is not None and 1e-4 <= now - previous[0] <= 1.0:
            closing = max(0.0, (previous[1] - rng) / (now - previous[0]))
            radius += min(300.0, 0.75 * closing)
        self._experiment_effect = self.standoff_m <= rng < radius and not shot_in_hand and losing_angle
        if (self.standoff_m > 0.0 and rng < radius''')
        replace('lag_m = min(self.standoff_m - rng, rng)', 'lag_m = min(radius - rng, rng)')
    elif variant == 'hysteresis':
        replace('                losing_angle = _tgt_ata < own_ata_deg',
                '''                difference = own_ata_deg - _tgt_ata
                now = self._match_time_s(own)
                current = getattr(self, '_experiment_extend', difference > 0.0)
                wanted = True if difference > 2.0 else False if difference < -2.0 else current
                pending, since = getattr(self, '_experiment_pending', (current, now))
                if wanted != pending:
                    pending, since = wanted, now
                if wanted != current and now - since >= 0.2:
                    current = wanted
                self._experiment_pending = (pending, since)
                self._experiment_extend = current
                losing_angle = current
                self._experiment_effect = current != (_tgt_ata < own_ata_deg)''')
    elif variant == 'recovery':
        replace('        fwd, up, right = body_axes(own)',
                '''        now = self._match_time_s(own)
        altitude = -float(own[StateIndex.D])
        previous = getattr(self, '_experiment_altitude', None)
        self._experiment_altitude = (now, altitude)
        climb = None
        if previous is not None and 1e-4 <= now - previous[0] <= 1.0:
            climb = (altitude - previous[1]) / (now - previous[0])
        if getattr(self, '_experiment_recovering', False):
            self._experiment_effect = True
            safe = altitude >= self.hard_deck_m + 100.0 and climb is not None and climb >= 0.0
            since = getattr(self, '_experiment_safe_since', None)
            self._experiment_safe_since = now if safe and since is None else since if safe else None
            if not safe or now - self._experiment_safe_since < 0.3:
                return None
            self._experiment_recovering = False
        else:
            self._experiment_effect = False
        fwd, up, right = body_axes(own)''')
        replace('                if self.hard_deck_m > 0.0 and own_alt_m < self.hard_deck_m:\n',
                '                if self.hard_deck_m > 0.0 and own_alt_m < self.hard_deck_m:\n                    self._experiment_recovering = True\n                    self._experiment_safe_since = None\n')
        replace('                                if own_alt_m / sink_mps < self.deck_ttc_s:\n                                    return None',
                '                                if own_alt_m / sink_mps < self.deck_ttc_s:\n                                    self._experiment_recovering = True\n                                    self._experiment_safe_since = None\n                                    return None')
    elif variant == 'aim_hold':
        replace('        self._los_error_sum += los_deg',
                '''        # Bound the integral to its existing contribution cap; release stored
        # turning demand near the true gun line, while keeping the proportional term.
        self._los_error_sum = min(self._los_error_sum, INTEGRAL_DIV * INTEGRAL_CAP)
        if own_ata_deg < 2.0:
            self._experiment_effect = True
            self._los_error_sum *= 0.95
        else:
            self._experiment_effect = False
            self._los_error_sum += los_deg''')
    return source


def worker_main(variant, runtime, diagnostic):
    import atexit
    import inspect
    import textwrap
    import types
    import numpy as np
    sys.path[:0] = [str(runtime), str(runtime / 'scripts'), str(runtime / 'src')]
    import eval_v5_vs_bt as evaluation
    import student.controller_providers as controllers
    original_factory = evaluation.build_provider
    # Source replacement strings match method indentation before dedenting.
    changed = altered_tracking(inspect.getsource(controllers.VPTrackingProvider._tracking_stick), variant)
    namespace = dict(vars(controllers))
    exec(textwrap.dedent(changed), namespace)
    tracking = namespace['_tracking_stick']
    episode_counter = [0]

    def factory(*args, **kwargs):
        provider = original_factory(*args, **kwargs)
        if kwargs.get('side') != 'ownship':
            return provider
        inner = provider
        while hasattr(inner, '_inner'):
            inner = inner._inner
        assert isinstance(inner, controllers.VPTrackingProvider), type(inner)
        stats = {}
        prior = {}
        def flush():
            if stats.get('ticks', 0):
                with diagnostic.open('a') as handle:
                    handle.write(json.dumps(dict(episode=episode_counter[0], **stats)) + '\n')
                episode_counter[0] += 1
                stats.clear()
        old_reset, old_close = inner.reset, inner.close
        def reset(this, *a, **kw):
            flush()
            prior.clear()
            for key in list(vars(this)):
                if key.startswith('_experiment_'):
                    delattr(this, key)
            return old_reset(*a, **kw)
        def close(this):
            flush()
            return old_close()
        def measured(this, own, target, vp, bt_throttle=0.5):
            try:
                command = tracking(this, own, target, vp, bt_throttle)
            except Exception:
                stats['errors'] = stats.get('errors', 0) + 1
                raise
            def count(key, value=1):
                stats[key] = stats.get(key, 0) + value
            count('ticks')
            count('experiment_effect_ticks', int(getattr(this, '_experiment_effect', False)))
            rel = np.array([target[0]-own[0], target[1]-own[1], own[2]-target[2]])
            distance = float(np.linalg.norm(rel))
            if distance > 0:
                forward = controllers.body_axes(own)[0]
                enemy = controllers.body_axes(target)[0]
                angle = float(np.degrees(np.arccos(np.clip(np.dot(forward, rel/distance), -1, 1))))
                enemy_angle = float(np.degrees(np.arccos(np.clip(np.dot(enemy, -rel/distance), -1, 1))))
                shot = 152.4 <= distance <= 914.4 and angle < 1.0
                count('below_floor_ticks', int(distance < 152.4))
                count('shot_ticks', int(shot))
                count('shot_exits', int(prior.get('shot', False) and not shot))
                extend = angle > enemy_angle
                count('angle_switches', int('extend' in prior and prior['extend'] != extend))
                if command is not None and 152.4 <= distance <= 914.4 and angle < 2:
                    count('near_aim_ticks')
                    count('near_roll_abs', abs(command[0]))
                    count('near_pitch_abs', abs(command[1]))
                    count('near_roll_reversals', int(prior.get('roll', 0) * command[0] < 0))
                prior.update(shot=shot, extend=extend)
            bt = command is None
            count('bt_ticks', int(bt))
            count('low_bt_ticks', int(bt and -own[2] < 1200))
            count('low_handoffs', int('bt' in prior and prior['bt'] != bt and -own[2] < 1200))
            prior.update(bt=bt, roll=command[0] if command is not None else 0)
            return command
        inner._tracking_stick = types.MethodType(measured, inner)
        inner.reset = types.MethodType(reset, inner)
        inner.close = types.MethodType(close, inner)
        atexit.register(flush)
        return provider
    evaluation.build_provider = factory
    if '--target-backend' in sys.argv and sys.argv[sys.argv.index('--target-backend') + 1] == 'cutoff':
        import eval_vs_cutoff
        eval_vs_cutoff.main()
    else:
        evaluation.main()


def main():
    # Parse only wrapper-owned flags first. Evaluator flags such as --episodes and --seed must
    # remain untouched for worker_main; the old shared parser consumed them and every requested
    # 12-episode campaign silently ran eval_v5_vs_bt's 30-episode default instead.
    wrapper = argparse.ArgumentParser(add_help=False)
    wrapper.add_argument('--variant', choices=VARIANTS, required=True)
    wrapper.add_argument('--worker', type=Path)
    wrapper.add_argument('--diagnostic', type=Path)
    worker_args, evaluator_argv = wrapper.parse_known_args()
    if worker_args.worker:
        if worker_args.diagnostic is None:
            raise ValueError('--diagnostic is required with --worker')
        sys.argv = [sys.argv[0]] + evaluator_argv
        worker_main(worker_args.variant, worker_args.worker, worker_args.diagnostic)
        return

    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=VARIANTS, required=True)
    parser.add_argument('--episodes', type=int, default=12)
    parser.add_argument('--seed', type=int, default=20260913)
    args = parser.parse_args()
    if args.episodes <= 0:
        raise ValueError('--episodes must be positive')
    sys.path.insert(0, str(ROOT / 'scripts'))
    import league
    run = OUT / f'{args.seed}_{args.episodes}' / args.variant
    run.mkdir(parents=True, exist_ok=True)
    def evaluate(archetype):
        runtime = run / archetype
        result = run / f'{archetype}.csv'
        diagnostic = run / f'{archetype}.jsonl'
        manifest_path = run / f'{archetype}.manifest.json'
        log_path = run / f'{archetype}.log'
        outputs = (runtime, result, diagnostic, manifest_path, log_path)
        existing = [str(path) for path in outputs if path.exists()]
        if existing:
            raise FileExistsError(f'Refusing to mix campaign output: {existing}')
        runtime.mkdir()
        for path in ROOT.iterdir():
            if path.is_file() and path.suffix.lower() in ('.py', '.dll', '.xml', '.exe', '.json'):
                shutil.copy2(path, runtime / path.name)
        for name in ('src', 'student', 'scripts', 'aircraft', 'engine'):
            shutil.copytree(ROOT / name, runtime / name, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        identity = {name: sha256(runtime/name)
                    for name in ('AIP_BASE.dll', 'AIP_BASE_target.dll', 'Rule_forTraining.xml', 'student/controller_providers.py')}
        evaluator_files = ['scripts/eval_v5_vs_bt.py']
        opponent_files = ['AIP_BASE_target.dll', 'student/controller_providers.py']
        if archetype == 'cutoff':
            evaluator_files += ['scripts/eval_vs_cutoff.py', 'scripts/cutoff_provider.py']
            opponent_files = ['unreal_bt_client.exe']
        evaluator_identity = {name: sha256(runtime/name) for name in evaluator_files}
        opponent_identity = {name: sha256(runtime/name) for name in opponent_files}
        common = ['--ownship-backend', 'vptrack', '--scenario-mode', 'match_base',
                  '--episodes', str(args.episodes), '--seed', str(args.seed), '--out-csv', str(result)]
        if archetype == 'cutoff':
            common += ['--target-backend', 'cutoff']
        profile_argv = list(league.CANDIDATES[PROFILE])
        opponent_argv = list(league.ARCHETYPES[archetype])
        common += profile_argv + opponent_argv
        command = [sys.executable, str(Path(__file__).resolve()), '--variant', args.variant,
                   '--worker', str(runtime), '--diagnostic', str(diagnostic)] + common
        env = dict(os.environ)
        for key in list(env):
            if key.startswith('DOGFIGHT_') or key.startswith('AIP_BT_GATE_TRACE'):
                del env[key]
        env.update(CAMPAIGN_ENVIRONMENT)
        manifest = dict(
            manifest_version=MANIFEST_VERSION,
            status='planned',
            variant=args.variant,
            archetype=archetype,
            profile=PROFILE,
            requested_episodes=args.episodes,
            seed=args.seed,
            evaluator_argv=common,
            profile_argv=profile_argv,
            opponent_argv=opponent_argv,
            command=command,
            environment=CAMPAIGN_ENVIRONMENT,
            python_executable=sys.executable,
            python_version=sys.version,
            identity=identity,
            evaluator_identity=evaluator_identity,
            opponent_identity=opponent_identity,
            experiment_source_sha256=sha256(Path(__file__)),
        )
        manifest_path.write_text(json.dumps(manifest, indent=2))
        print(f'START {args.variant} vs {archetype}', flush=True)
        with log_path.open('w') as log:
            subprocess.run(command, cwd=runtime, env=env, stdout=log, stderr=subprocess.STDOUT,
                           check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        rows = validate_result(result, diagnostic, args.episodes)
        manifest.update(status='complete', actual_episodes=len(rows))
        manifest_path.write_text(json.dumps(manifest, indent=2))
        data = league._load(result)
        print(f'DONE {args.variant} vs {archetype}: {data}', flush=True)
        return archetype, data
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(evaluate, ARCHETYPES))
    (run/'summary.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
