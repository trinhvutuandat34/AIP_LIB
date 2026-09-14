"""Validate paired campaign CSVs and reuse the league's complete-outcome scoring."""
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import league

PAIR_FIELDS = ('episode', 'initial_distance_m', 'initial_altitude_m',
               'initial_speed_mps', 'initial_side')


def validate_pair(control_file, candidate_file, control, candidate):
    """Require an exact episode pairing and compatible v2 provenance."""
    if len(control) != len(candidate):
        raise ValueError(f'{candidate_file}: {len(candidate)} rows vs control {len(control)}')
    for label, rows in (('control', control), ('candidate', candidate)):
        episodes = [row['episode'] for row in rows]
        if len(episodes) != len(set(episodes)):
            raise ValueError(f'{candidate_file}: duplicate {label} episode identifiers')
    for before, after in zip(control, candidate):
        for key in PAIR_FIELDS:
            if before[key] != after[key]:
                raise ValueError(f'{candidate_file}: pairing mismatch for {key}: '
                                 f'{before[key]!r} != {after[key]!r}')

    before_manifest = json.loads(control_file.with_suffix('.manifest.json').read_text())
    after_manifest = json.loads(candidate_file.with_suffix('.manifest.json').read_text())
    comparable = ('manifest_version', 'archetype', 'profile', 'profile_argv', 'opponent_argv',
                  'requested_episodes', 'seed', 'environment', 'identity',
                  'evaluator_identity', 'opponent_identity', 'experiment_source_sha256',
                  'python_executable', 'python_version')
    for key in comparable:
        if key in before_manifest or key in after_manifest:
            if before_manifest.get(key) != after_manifest.get(key):
                raise ValueError(f'{candidate_file}: manifest mismatch for {key}')
    for manifest, rows, label in ((before_manifest, control, 'control'),
                                  (after_manifest, candidate, 'candidate')):
        if manifest.get('status') not in (None, 'complete'):
            raise ValueError(f'{candidate_file}: {label} manifest is not complete')
        if 'actual_episodes' in manifest and manifest['actual_episodes'] != len(rows):
            raise ValueError(f'{candidate_file}: {label} manifest row count mismatch')


def outcome(row):
    if row['end_condition'] in league._TARGET_LOST:
        return 'win'
    if row['end_condition'] in league._OWNSHIP_LOST:
        return 'loss'
    return row['phased_outcome'] if row['phased_outcome'] in ('win', 'loss') else 'draw'


def summarize(folder):
    results = {}
    for arm in sorted(folder.iterdir()):
        if not arm.is_dir():
            continue
        columns = {}
        for file in sorted(arm.glob('*.csv')):
            rows = list(csv.DictReader(file.open()))
            if not rows:
                continue
            diagnostics = [json.loads(line) for line in file.with_suffix('.jsonl').read_text().splitlines()]
            assert not any(row.get('errors', 0) for row in diagnostics), file
            score = league._load(file)
            summary = dict(score)
            summary['diagnostic_episodes'] = len(diagnostics)
            summary['diagnostics'] = {key: sum(row.get(key, 0) for row in diagnostics)
                                      for key in set().union(*(row.keys() for row in diagnostics)) if key != 'episode'}
            baseline = folder / 'baseline' / file.name
            if arm.name != 'baseline':
                if not baseline.exists():
                    raise FileNotFoundError(f'{file}: paired baseline does not exist: {baseline}')
                control = list(csv.DictReader(baseline.open()))
                validate_pair(baseline, file, control, rows)
                pair = [(outcome(a), outcome(b)) for a, b in zip(control, rows)]
                summary['gained_wins'] = sum(a != 'win' and b == 'win' for a, b in pair)
                summary['lost_wins'] = sum(a == 'win' and b != 'win' for a, b in pair)
            columns[file.stem] = summary
        results[arm.name] = columns
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    data = summarize(args.folder)
    (args.folder / 'paired_results.json').write_text(json.dumps(data, indent=2))
    for arm, columns in data.items():
        print(arm)
        for opponent, row in columns.items():
            print(opponent, {k: v for k, v in row.items() if k != 'diagnostics'})
            print(' diagnostic:', row['diagnostics'])
