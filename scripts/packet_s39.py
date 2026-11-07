"""Verify S39 native CI streams and retain a small, source-pinned packet.

Download both s39-exit-underfoot-* artifacts into named subdirectories of
one fixed scratch root. Raw ANSI and style snapshots stay in CI artifacts.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from scripts.presentation_p6_packet import require, source_hash, verify_capture


def build_packet(root: Path, run: dict[str, Any], artifacts: dict[str, Any],
                 destination: Path) -> dict[str, Any]:
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'native run did not pass')
    head, run_id = run['head_sha'], run['id']
    import subprocess
    tree = subprocess.check_output(['git', 'rev-parse', head+':src/blacksite'], cwd=ROOT, text=True).strip()
    expected_source = source_hash(head, tree)
    records: list[dict[str, Any]] = []
    files: dict[str, bytes] = {}
    summaries = []
    for width, height in ((80, 24), (132, 50)):
        name = f's39-exit-underfoot-{width}x{height}'
        matches = [row for row in artifacts['artifacts'] if row['name'] == name and not row['expired']]
        require(len(matches) == 1, f'missing or duplicate artifact: {name}')
        artifact = matches[0]
        require(artifact['workflow_run']['id'] == run_id, 'artifact belongs to a different run')
        directory = root/name
        result = json.loads((directory/'s39-results.json').read_text(encoding='utf-8'))
        client = json.loads((directory/'native-client.json').read_text(encoding='utf-8'))
        require(result['passed'] and result['head'] == head and result['wait_for_focus'] is False,
                f'{name}: result head/readiness mismatch')
        require(client['python_tree_sha256'] == expected_source, f'{name}: client source mismatch')
        require(result['transport'] == 'NetBBS Telnet -> registered native stdio', 'wrong transport')
        expected = {f's39-{scenario}-{width}x{height}-{tier}'
                    for scenario in ('exit-beside-regular', 'mission-beside-giver')
                    for tier in ('16', '256', 'truecolor')}
        actual = [row['capture'] for row in result['captures']]
        require(len(actual) == len(expected) and set(actual) == expected, f'{name}: incomplete capture matrix')
        routes = result['network_routes']
        require(len(routes) == 1 and routes[0]['size'] == [width, height]
                and routes[0]['route'] == 'network' and routes[0]['fixtures'] == []
                and routes[0]['chits'] == 200 and routes[0]['xp'] == 100 and routes[0]['loan_trace'] == 0,
                f'{name}: missing unmodified S19 network route')
        for capture in result['captures']:
            stem = capture['capture']  # Already checked against the exact expected basenames.
            require(capture['size'] == [width, height], f'{stem}: size mismatch')
            expected_verb = 'survey' if capture['scenario'] == 'mission-beside-giver' else 'go to'
            require(capture['focus']['verb'] == expected_verb, f'{stem}: wrong focus')
            require(set(capture['sha256']) == {'.ans', '.txt', '.json'}, f'{stem}: missing hashes')
            for suffix, expected_hash in capture['sha256'].items():
                require(sha256((directory/(stem+suffix)).read_bytes()).hexdigest() == expected_hash,
                        f'{stem}{suffix}: hash mismatch')
            start = verify_capture(directory, stem, width, height)
            files[stem+'.txt'] = (directory/(stem+'.txt')).read_bytes()
            records.append({**capture, 'file': stem+'.txt', 'source_head': head,
                'source_tree': tree, 'python_tree_sha256': expected_source,
                'run': run_id, 'run_url': run['html_url'], 'artifact': name,
                'artifact_id': artifact['id'], 'artifact_url':
                    f'https://github.com/Thiesi/Blacksite/actions/runs/{run_id}/artifacts/{artifact["id"]}',
                'raw_ansi_member': stem+'.ans', 'style_member': stem+'.json',
                'native_boundary_offset': start,
                'method': 'Direct byte copy of live native text; ANSI replay verified glyphs and styles'})
        summaries.append({'artifact': name, 'source_head': head, 'network_routes': routes,
                          'fixtures': result['fixtures'], 'captures_verified': len(actual)})
    manifest = {'transport': 'NetBBS Telnet -> registered native stdio', 'run': run_id,
        'source_head': head, 'source_tree': tree, 'python_tree_sha256': expected_source,
        'wait_for_focus': False, 'human_layout_approval': False, 'captures': records}
    files['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    files['results.json'] = (json.dumps({'passed': True, 'runs': summaries}, indent=2)+'\n').encode()
    require(sum(map(len, files.values())) <= 200_000, 'packet exceeds review evidence budget')
    require(not destination.exists(), 'preserve existing evidence; destination already exists')
    destination.mkdir(parents=True)
    for name, data in files.items():
        (destination/name).write_bytes(data)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/ops/captures/s39/native')
    args = parser.parse_args()
    manifest = build_packet(args.root, json.loads(args.run.read_text(encoding='utf-8-sig')),
                            json.loads(args.artifacts.read_text(encoding='utf-8-sig')), args.output)
    print(json.dumps({'source_head': manifest['source_head'], 'run': manifest['run'],
                      'captures_verified': len(manifest['captures'])}))
