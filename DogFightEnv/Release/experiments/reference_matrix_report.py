"""Validate and summarize trusted Phase-2 baseline campaign runs.

Example:
    python experiments/reference_matrix_report.py \
        artifacts/winrate_20260913/20260913_60/baseline \
        artifacts/winrate_20260913/20260914_60/baseline \
        --out artifacts/winrate_20260913/reference_baseline_20260913_20260914.json
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parent), str(ROOT / 'scripts')]

import league  # noqa: E402
from winrate_campaign import ARCHETYPES, PAIR_FIELDS, validate_result  # noqa: E402
from summarize_winrate_campaign import outcome  # noqa: E402


def metrics(rows):
    n = len(rows)
    if not n:
        return {'n': 0}
    outcomes = [outcome(row) for row in rows]
    w, d, l = (outcomes.count(name) for name in ('win', 'draw', 'loss'))
    mean = lambda key: sum(float(row[key]) for row in rows) / n
    count = lambda condition: sum(bool(condition(row)) for row in rows)
    win_rate = w / n
    match_win, match_draw, _ = league._match_outcome_probs(w / n, d / n, l / n, 3)
    z = 1.959963984540054
    denominator = 1 + z * z / n
    center = (win_rate + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(win_rate * (1 - win_rate) / n + z * z / (4 * n * n)) / denominator
    target_destroyed = count(lambda row: row['end_condition'] == 'target destroyed')
    ownship_destroyed = count(lambda row: row['end_condition'] == 'ownship destroyed')
    target_ground = count(lambda row: row['end_condition'] == 'target altitude below min')
    ownship_ground = count(lambda row: row['end_condition'] == 'ownship altitude below min')
    return {
        'n': n,
        'w': w,
        'd': d,
        'l': l,
        'win_rate': win_rate,
        'win_rate_ci95': [center - margin, center + margin],
        'bo3_points': 3 * match_win + match_draw,
        'target_destroyed': target_destroyed,
        'ownship_destroyed': ownship_destroyed,
        'target_ground': target_ground,
        'ownship_ground': ownship_ground,
        'target_loss_rate': (target_destroyed + target_ground) / n,
        'ownship_loss_rate': (ownship_destroyed + ownship_ground) / n,
        'timeouts': count(lambda row: row['end_condition'] in ('max time out', 'episode step limit')),
        'phase1_wez_rate': count(lambda row: float(row['ep_wez_steps']) > 0) / n,
        'phased_wez_rate': count(lambda row: float(row['ep_wez_steps_phased']) > 0) / n,
        'damage_dealt': mean('ep_damage_dealt'),
        'damage_taken': mean('ep_damage_taken'),
        'damage_diff': mean('ep_damage_dealt') - mean('ep_damage_taken'),
        'mean_bt_fraction': mean('ep_bt_frac'),
    }


def grouped(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[str(key(row))].append(row)
    return {name: metrics(group) for name, group in sorted(groups.items())}


def load_run(folder):
    cells = {}
    for archetype in ARCHETYPES:
        csv_path = folder / f'{archetype}.csv'
        diagnostic = folder / f'{archetype}.jsonl'
        manifest_path = folder / f'{archetype}.manifest.json'
        if not all(path.is_file() for path in (csv_path, diagnostic, manifest_path)):
            raise FileNotFoundError(f'{folder}: incomplete {archetype} cell')
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('manifest_version') != 2 or manifest.get('status') != 'complete':
            raise ValueError(f'{manifest_path}: requires a complete version-2 manifest')
        if manifest.get('variant') != 'baseline' or manifest.get('archetype') != archetype:
            raise ValueError(f'{manifest_path}: not the requested baseline/{archetype} cell')
        expected = int(manifest['requested_episodes'])
        rows = validate_result(csv_path, diagnostic, expected)
        if manifest.get('actual_episodes') != len(rows):
            raise ValueError(f'{manifest_path}: actual_episodes does not match CSV')
        ours, official = metrics(rows), league._load(csv_path)
        for field in ('n', 'w', 'd', 'l'):
            if ours[field] != official[field]:
                raise ValueError(f'{csv_path}: {field} disagrees with league scorer')
        if abs(ours['bo3_points'] - official['bo3_points']) > 1e-12:
            raise ValueError(f'{csv_path}: BO3 disagrees with league scorer')
        for field in ('win_rate', 'phase1_wez_rate', 'phased_wez_rate',
                      'target_loss_rate', 'ownship_loss_rate'):
            if not 0.0 <= ours[field] <= 1.0:
                raise ValueError(f'{csv_path}: invalid {field}={ours[field]}')
        for field in ('damage_dealt', 'damage_taken', 'damage_diff', 'mean_bt_fraction'):
            if not math.isfinite(ours[field]):
                raise ValueError(f'{csv_path}: non-finite {field}')
        cells[archetype] = {'rows': rows, 'manifest': manifest}

    # Each opponent at a seed must receive the exact same episode starts.
    reference = cells[ARCHETYPES[0]]['rows']
    for archetype in ARCHETYPES[1:]:
        candidate = cells[archetype]['rows']
        for before, after in zip(reference, candidate):
            for field in PAIR_FIELDS:
                if before[field] != after[field]:
                    raise ValueError(f'{folder}: {archetype} start mismatch for episode '
                                     f'{before["episode"]}, field {field}')
    return cells


def validate_provenance(runs):
    first_cells = runs[0][1]
    common = ('profile', 'profile_argv', 'environment', 'identity',
              'experiment_source_sha256', 'python_executable', 'python_version')
    for folder, cells in runs[1:]:
        for archetype in ARCHETYPES:
            before = first_cells[archetype]['manifest']
            after = cells[archetype]['manifest']
            for field in common + ('evaluator_identity', 'opponent_identity', 'opponent_argv'):
                if before.get(field) != after.get(field):
                    raise ValueError(f'{folder}: {archetype} provenance mismatch for {field}')


def validate_independent_runs(runs):
    effective = []
    for folder, cells in runs:
        manifest = cells[ARCHETYPES[0]]['manifest']
        argv = manifest['evaluator_argv']
        offset = int(argv[argv.index('--episode-offset') + 1]) if '--episode-offset' in argv else 0
        first = int(manifest['seed']) + offset
        seeds = set(range(first, first + int(manifest['requested_episodes'])))
        for prior_folder, prior in effective:
            overlap = seeds & prior
            if overlap:
                raise ValueError(f'{folder} and {prior_folder} reuse {len(overlap)} effective '
                                 f'episode seeds ({min(overlap)}..{max(overlap)})')
        effective.append((folder, seeds))
    return [[min(seeds), max(seeds)] for _, seeds in effective]


def build_report(folders):
    runs = [(folder, load_run(folder)) for folder in folders]
    seeds = [cells[ARCHETYPES[0]]['manifest']['seed'] for _, cells in runs]
    if len(seeds) != len(set(seeds)):
        raise ValueError(f'independent runs require unique seeds, got {seeds}')
    effective_seed_ranges = validate_independent_runs(runs)
    validate_provenance(runs)

    report = {
        'status': 'validated',
        'profile': runs[0][1][ARCHETYPES[0]]['manifest']['profile'],
        'seeds': seeds,
        'effective_seed_ranges': effective_seed_ranges,
        'runs': [str(folder.resolve()) for folder, _ in runs],
        'identity': runs[0][1][ARCHETYPES[0]]['manifest']['identity'],
        'environment': runs[0][1][ARCHETYPES[0]]['manifest']['environment'],
        'opponents': {},
    }
    for archetype in ARCHETYPES:
        rows = []
        by_seed = {}
        for _, cells in runs:
            cell = cells[archetype]
            seed = str(cell['manifest']['seed'])
            by_seed[seed] = metrics(cell['rows'])
            rows.extend(cell['rows'])
        report['opponents'][archetype] = {
            'overall': metrics(rows),
            'by_seed': by_seed,
            'by_separation_m': grouped(rows, lambda row: f'{float(row["initial_distance_m"]):.1f}'),
            'by_side': grouped(rows, lambda row: f'{float(row["initial_side"]):+.0f}'),
            'by_separation_and_side': grouped(
                rows, lambda row: f'{float(row["initial_distance_m"]):.1f}/{float(row["initial_side"]):+.0f}'),
        }
    return report


def print_report(report):
    print(f"VALIDATED profile={report['profile']} seeds={report['seeds']}")
    print(f"{'opponent':10s} {'n':>4} {'W-D-L':>10} {'BO3':>5} {'kill':>5} {'shot':>5} "
          f"{'ground':>6} {'dmg net':>8} {'WEZ':>5} {'BT':>5}")
    for archetype, data in report['opponents'].items():
        row = data['overall']
        print(f"{archetype:10s} {row['n']:4d} {row['w']:3d}-{row['d']:3d}-{row['l']:3d} "
              f"{row['bo3_points']:5.2f} {row['target_destroyed']:5d} "
              f"{row['ownship_destroyed']:5d} {row['ownship_ground']:6d} "
              f"{row['damage_diff']:+8.3f} {row['phased_wez_rate']:5.0%} "
              f"{row['mean_bt_fraction']:5.0%}")
        for key, group in data['by_separation_and_side'].items():
            print(f"  {key:10s} n={group['n']:2d} {group['w']}-{group['d']}-{group['l']} "
                  f"BO3={group['bo3_points']:.2f} net={group['damage_diff']:+.3f} "
                  f"shot={group['ownship_destroyed']} ground={group['ownship_ground']}")


def self_test():
    rows = [
        {'end_condition': 'target destroyed', 'phased_outcome': 'win', 'ep_wez_steps': '2',
         'ep_wez_steps_phased': '3', 'ep_damage_dealt': '1', 'ep_damage_taken': '0.2',
         'ep_bt_frac': '0.25', 'initial_distance_m': '609.6', 'initial_side': '1'},
        {'end_condition': 'ownship destroyed', 'phased_outcome': 'loss', 'ep_wez_steps': '0',
         'ep_wez_steps_phased': '1', 'ep_damage_dealt': '0.1', 'ep_damage_taken': '1',
         'ep_bt_frac': '0.75', 'initial_distance_m': '609.6', 'initial_side': '-1'},
    ]
    result = metrics(rows)
    assert result['n'] == 2 and result['w'] == 1 and result['l'] == 1
    assert result['bo3_points'] == 1.5 and abs(result['damage_diff'] + 0.05) < 1e-12
    assert grouped(rows, lambda row: row['initial_side'])['1']['w'] == 1
    cells = {name: {'manifest': {'seed': 100, 'requested_episodes': 3,
                                 'evaluator_argv': []}} for name in ARCHETYPES}
    disjoint = {name: {'manifest': {'seed': 103, 'requested_episodes': 3,
                                    'evaluator_argv': []}} for name in ARCHETYPES}
    assert validate_independent_runs([(Path('a'), cells), (Path('b'), disjoint)]) == [[100, 102], [103, 105]]
    overlapping = {name: {'manifest': {'seed': 101, 'requested_episodes': 3,
                                       'evaluator_argv': []}} for name in ARCHETYPES}
    try:
        validate_independent_runs([(Path('a'), cells), (Path('b'), overlapping)])
    except ValueError as exc:
        assert 'reuse 2 effective episode seeds' in str(exc)
    else:
        raise AssertionError('overlapping effective episode seeds were accepted')
    print('PASS: reference matrix aggregation')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folders', nargs='*', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if len(args.folders) < 2 or args.out is None:
        parser.error('provide at least two baseline folders and --out')
    report = build_report(args.folders)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print_report(report)
    print(f'JSON: {args.out}')


if __name__ == '__main__':
    main()
