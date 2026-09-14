"""Check candidate mechanisms without loading DLLs or changing the shipped controller."""
import csv
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import types

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts')]
from test_standoff_aimpoint import _provider, _state, StateIndex
import student.controller_providers as controllers
from winrate_campaign import altered_tracking, validate_result, VARIANTS, PAIR_FIELDS
from summarize_winrate_campaign import validate_pair


def make(variant):
    source = inspect.getsource(controllers.VPTrackingProvider._tracking_stick)
    ns = dict(vars(controllers))
    exec(textwrap.dedent(altered_tracking(source, variant)), ns)
    provider = _provider(300.0, adaptive=True)
    provider._tracking_stick = types.MethodType(ns['_tracking_stick'], provider)
    return provider


def main():
    for variant in VARIANTS:
        provider = make(variant)
        own = _state(0, 0, 4000)
        target = _state(400, 100, 4050, yaw_deg=210)
        for tick in range(30):
            own[StateIndex.SIM_TIME] = 1 + tick / 60
            target[StateIndex.N] -= 2
            command = provider._tracking_stick(own, target, None)
            assert command is not None and all(-1 <= c <= 1 for c in command[:3])
    # Predictive lag must act outside 300 m when closing, but must preserve an existing shot.
    baseline, closure = make('baseline'), make('closure')
    own, target = _state(0, 0, 4000, yaw_deg=60), _state(450, 100, 4050, yaw_deg=210)
    for p in (baseline, closure):
        p._tracking_stick(own, target, None)
    target[StateIndex.N] = 400
    own[StateIndex.SIM_TIME] += 0.1
    assert baseline._tracking_stick(own, target, None) != closure._tracking_stick(own, target, None)
    own, target = _state(0, 0, 4000), _state(200, 0, 4000, yaw_deg=90)
    assert make('baseline')._tracking_stick(own, target, None) == make('closure')._tracking_stick(own, target, None)
    # Recovery must persist after crossing the entry altitude, then release after stable climb.
    p = make('recovery')
    p.hard_deck_m = 1000
    own, target = _state(0, 0, 990), _state(400, 100, 1300)
    assert p._tracking_stick(own, target, None) is None
    for t, altitude in ((1.1, 1020), (1.2, 1105), (1.4, 1120)):
        own[StateIndex.SIM_TIME], own[StateIndex.D] = t, -altitude
        assert p._tracking_stick(own, target, None) is None
    own[StateIndex.SIM_TIME], own[StateIndex.D] = 1.6, -1140
    assert p._tracking_stick(own, target, None) is not None
    # Near-aim integral state must decrease from saturation rather than grow without bound.
    p = make('aim_hold')
    p._los_error_sum = 1e9
    p._tracking_stick(_state(0, 0, 4000), _state(300, 1, 4000), None)
    assert p._los_error_sum < controllers.INTEGRAL_DIV * controllers.INTEGRAL_CAP

    # Exercise the real wrapper subprocess. The regression consumed these two flags before the
    # evaluator saw them, silently turning every requested 12-episode run into 30 episodes.
    with tempfile.TemporaryDirectory() as folder:
        diagnostic = Path(folder) / 'dry-run.jsonl'
        command = [sys.executable, str(Path(__file__).with_name('winrate_campaign.py')),
                   '--variant', 'baseline', '--worker', str(Path(__file__).resolve().parents[1]),
                   '--diagnostic', str(diagnostic), '--episodes', '3', '--seed', '17',
                   '--ownship-backend', 'vptrack', '--target-backend', 'vptrack',
                   '--scenario-mode', 'match_base', '--dry-run']
        completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                   text=True, capture_output=True)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert '[eval] episodes=3' in completed.stdout, completed.stdout

        fields = list(PAIR_FIELDS) + ['end_condition', 'phased_outcome']
        control_file = Path(folder) / 'control.csv'
        candidate_file = Path(folder) / 'candidate.csv'
        rows = [dict(episode=str(i), initial_distance_m='762.0', initial_altitude_m='4000.0',
                     initial_speed_mps='250.0', initial_side='1', end_condition='max time out',
                     phased_outcome='draw') for i in range(3)]
        for path in (control_file, candidate_file):
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            path.with_suffix('.jsonl').write_text('\n'.join(
                json.dumps({'episode': i, 'ticks': 1}) for i in range(3)) + '\n')
        validate_result(control_file, control_file.with_suffix('.jsonl'), 3)

        manifest = dict(manifest_version=2, status='complete', archetype='mirror',
                        profile='adaptive300_deckttc', requested_episodes=3, actual_episodes=3,
                        seed=17, environment={'band': 'test'}, identity={'runtime': 'same'},
                        evaluator_identity={'eval': 'same'}, opponent_identity={'target': 'same'})
        control_file.with_suffix('.manifest.json').write_text(json.dumps(manifest))
        candidate_file.with_suffix('.manifest.json').write_text(json.dumps(manifest))
        validate_pair(control_file, candidate_file, rows, rows)

        duplicated = [dict(row) for row in rows]
        duplicated[2]['episode'] = duplicated[1]['episode']
        try:
            validate_pair(control_file, candidate_file, rows, duplicated)
        except ValueError as exc:
            assert 'duplicate candidate episode' in str(exc)
        else:
            raise AssertionError('duplicate episode identifiers were accepted')

        mismatched_manifest = dict(manifest, seed=18)
        candidate_file.with_suffix('.manifest.json').write_text(json.dumps(mismatched_manifest))
        try:
            validate_pair(control_file, candidate_file, rows, rows)
        except ValueError as exc:
            assert 'manifest mismatch for seed' in str(exc)
        else:
            raise AssertionError('mismatched pairing manifests were accepted')
        candidate_file.with_suffix('.manifest.json').write_text(json.dumps(manifest))

        bad_rows = rows[:2]
        with candidate_file.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(bad_rows)
        try:
            validate_result(candidate_file, candidate_file.with_suffix('.jsonl'), 3)
        except ValueError:
            pass
        else:
            raise AssertionError('truncated result was accepted')
    print('PASS: variants, worker forwarding, row-count guard, and exact pairing')


if __name__ == '__main__':
    main()
