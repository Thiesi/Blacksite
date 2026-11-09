"""Verify the 24 S42 native captures and retain a source-pinned packet.

Download the six named artifacts into one fixed scratch root. Large raw
ANSI streams and style snapshots remain in their linked CI artifacts.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT)]

from scripts.presentation_p6_packet import require, source_hash, verify_capture
from scripts.source_layout import at_revision


def build_packet(root: Path, run: dict[str, Any], artifacts: dict[str, Any], destination: Path) -> dict[str, Any]:
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'native run did not pass')
    head, run_id = run['head_sha'], run['id']
    tree = subprocess.check_output(['git', 'rev-parse', head+':'+at_revision(head, 'src/karst41')], cwd=ROOT, text=True).strip()
    expected_source = source_hash(head, tree)
    records, summaries = [], []
    files: dict[str, bytes] = {}
    for width, height in ((80, 24), (132, 50)):
        for tier in ('16', '256', 'truecolor'):
            name = f's42-talker-{width}x{height}-{tier}'
            matches = [row for row in artifacts['artifacts'] if row['name'] == name and not row['expired']]
            require(len(matches) == 1, f'missing or duplicate artifact: {name}')
            artifact = matches[0]
            require(artifact['workflow_run']['id'] == run_id, 'artifact belongs to a different run')
            directory = root/name
            result = json.loads((directory/'s42-results.json').read_text(encoding='utf-8'))
            client = json.loads((directory/'native-client.json').read_text(encoding='utf-8'))
            require(result['passed'] and result['head'] == head, f'{name}: result head/readiness mismatch')
            require(client['python_tree_sha256'] == expected_source, f'{name}: client source mismatch')
            require(result['transport'] == 'NetBBS Telnet -> registered native stdio', 'wrong transport')
            require(result['shot']['state'] == 'flee' and result['shot']['target'], 'missing real-shot flee result')
            covered = result['covered_shot']
            require(covered['template'] == 'npc-plainclothes-warden' and not covered['revealed_to_caller']
                    and covered['line'] in ('Hit: Sodium regular.', 'Miss: Sodium regular.'),
                    'missing masked real-shot feedback')
            require(not result['presentation_acceptance'] and not result['h1_layout_approval']
                    and not result['s25_layout_approval'], 'engineering proof cannot grant human gates')
            expected = {f's42-{scenario}-{width}x{height}-{tier}' for scenario in (
                'talk-hint', 'one-press-walk-away', 'shot-flee-walks-off', 'covered-shot-label')}
            actual = [row['capture'] for row in result['captures']]
            require(len(actual) == len(expected) and set(actual) == expected, f'{name}: incomplete capture matrix')
            for capture in result['captures']:
                stem = capture['capture']
                require(capture['size'] == [width, height] and capture['tier'] == tier, f'{stem}: size/tier mismatch')
                require(set(capture['sha256']) == {'.ans', '.txt', '.json'}, f'{stem}: missing hashes')
                for suffix, expected_hash in capture['sha256'].items():
                    require(sha256((directory/(stem+suffix)).read_bytes()).hexdigest() == expected_hash,
                            f'{stem}{suffix}: hash mismatch')
                start = verify_capture(directory, stem, width, height)
                text = (directory/(stem+'.txt')).read_text(encoding='utf-8')
                if capture['scenario'] == 'talk-hint':
                    require('Move or Esc/B leaves' in text, f'{stem}: missing walk-away hint')
                elif capture['scenario'] == 'shot-flee-walks-off':
                    require('Sodium regular walks off.' in text, f'{stem}: missing flee close line')
                elif capture['scenario'] == 'covered-shot-label':
                    require(covered['line'] in text and 'Plainclothes Warden' not in text,
                            f'{stem}: combat feedback exposed the cover')
                files[stem+'.txt'] = (directory/(stem+'.txt')).read_bytes()
                records.append({**capture, 'file': stem+'.txt', 'source_head': head,
                    'source_tree': tree, 'python_tree_sha256': expected_source,
                    'run': run_id, 'run_url': run['html_url'], 'artifact': name,
                    'artifact_id': artifact['id'], 'artifact_url':
                        f'https://github.com/Thiesi/Karst41/actions/runs/{run_id}/artifacts/{artifact["id"]}',
                    'raw_ansi_member': stem+'.ans', 'style_member': stem+'.json',
                    'native_boundary_offset': start,
                    'method': 'Direct byte copy of live native text; ANSI replay verified glyphs and styles'})
            summaries.append({'artifact': name, 'source_head': head, 'shot': result['shot'],
                              'covered_shot': covered,
                              'fixtures': result['fixtures'], 'captures_verified': len(actual)})
    manifest = {'transport': 'NetBBS Telnet -> registered native stdio', 'run': run_id,
        'source_head': head, 'source_tree': tree, 'python_tree_sha256': expected_source,
        'presentation_acceptance': False, 'human_layout_approval': False, 'captures': records}
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
    parser.add_argument('--output', type=Path, default=ROOT/'docs/ops/captures/s42/native')
    args = parser.parse_args()
    manifest = build_packet(args.root, json.loads(args.run.read_text(encoding='utf-8-sig')),
                            json.loads(args.artifacts.read_text(encoding='utf-8-sig')), args.output)
    print(json.dumps({'source_head': manifest['source_head'], 'run': manifest['run'],
                      'captures_verified': len(manifest['captures'])}))
