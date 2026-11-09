"""Validate/aggregate issue-184 reports, preserving misses and marginal signs."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


def summarize(reports: list[dict[str, Any]]) -> dict[str, Any]:
    cells = []
    identities = set()
    heads = {r['head'] for r in reports}
    if len(heads) != 1 or len(reports) != 6:
        raise ValueError('need all six groups at one exact head')
    for report in reports:
        if not report['complete'] or not report['cpu_budget_reference'] or report['seconds'] != 12:
            raise ValueError('incomplete, dirty, non-Linux or noncanonical report')
        group = (report['callers'], report['tier'])
        if group in identities:
            raise ValueError('duplicate caller/tier group')
        identities.add(group)
        for row in report['cases']:
            cells.append({'callers': report['callers'], 'tier': report['tier'],
                **{key: row[key] for key in ('stationary', 'moving', 'fully_known',
                    'door_total_cpu_s_per_hour', 'door_mean_cpu_s_per_hour',
                    'door_max_cpu_s_per_hour', 'server_cpu_s_per_hour', 'within_108')}})
    expected_groups = {(n, t) for n in (1, 4) for t in ('16', '256', 'truecolor')}
    if identities != expected_groups:
        raise ValueError('wrong caller/tier groups')
    keys = [(r['callers'], r['tier'], r['fully_known'], r['stationary'], r['moving']) for r in cells]
    expected = {(n, t, False, s, m) for n, t in expected_groups
                for s in (0, 20, 40, 80) for m in (4, 8, 12)}
    corners = {(n, t, True, s, m) for n, t in expected_groups
               for s in (0, 80) for m in (4, 12)}
    if len(keys) != len(set(keys)) or set(keys) not in (expected, expected | corners):
        raise ValueError('missing or duplicate required grid cells')
    marginals = []
    lookup = dict(zip(keys, cells))
    for row in cells:
        for axis, values in (('stationary', (0, 20, 40, 80)), ('moving', (4, 8, 12))):
            index = values.index(row[axis])
            if index == len(values)-1:
                continue
            next_value = values[index+1]
            other_key = (row['callers'], row['tier'], row['fully_known'],
                next_value if axis == 'stationary' else row['stationary'],
                next_value if axis == 'moving' else row['moving'])
            if other_key not in lookup:
                continue
            other = lookup[other_key]
            delta = next_value-row[axis]
            marginals.append({'axis': axis, 'from': row[axis], 'to': next_value,
                'callers': row['callers'], 'tier': row['tier'],
                'fully_known': row['fully_known'],
                'fixed_other_axis': row['moving'] if axis == 'stationary' else row['stationary'],
                'door_cpu_s_per_hour_per_added_npc_per_caller':
                    (other['door_total_cpu_s_per_hour']-row['door_total_cpu_s_per_hour'])/delta/row['callers'],
                'server_cpu_s_per_hour_per_added_npc':
                    (other['server_cpu_s_per_hour']-row['server_cpu_s_per_hour'])/delta})
    profiles = []
    for report in reports:
        for sample in report.get('profiles', []):
            evaluate = [r for r in sample['functions']
                        if r['file'].endswith('/npcs/engine.py') and r['function'] == 'evaluate']
            profiles.append({key: sample[key] for key in ('stationary', 'moving', 'callers',
                'ticks', 'total_profile_cpu_s', 'timer')} | {'npc_evaluate': evaluate})
    return {'schema': 1, 'head': next(iter(heads)), 'cells': cells, 'marginals': marginals,
        'profiles': profiles,
        'required_cells': sum(not c['fully_known'] for c in cells),
        'known_corner_cells': sum(c['fully_known'] for c in cells),
        'target': 'all individual callers <=108 Display-method CPU s/h; shared server reported separately',
        'limits': ['P1 hourly mix is provisional, not observed player behaviour.',
            'Marginals are adjacent finite differences, not a fitted linear cost.',
            'Cross-group host variation is not an isolated causal comparison.',
            'Shared tick profiles exclude durable storage, codecs and native I/O.',
            'This grants no population decision, H1 or S25 approval.']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = summarize([json.loads(p.read_text(encoding='utf-8')) for p in args.reports])
    result['reports_sha256'] = {str(p): sha256(p.read_bytes()).hexdigest() for p in args.reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
