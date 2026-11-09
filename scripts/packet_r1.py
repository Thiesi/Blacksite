"""Verify twelve live R1 title artifacts and retain their small text packet."""

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


def build_packet(root: Path, run: dict[str, Any], artifacts: dict[str, Any],
                 destination: Path) -> dict[str, Any]:
    require(run['status'] == 'completed' and run['conclusion'] == 'success',
            'native run did not pass')
    head, run_id = run['head_sha'], run['id']
    tree = subprocess.check_output(['git', 'rev-parse', head+':src/karst41'],
                                   cwd=ROOT, text=True).strip()
    expected_source = source_hash(head, tree)
    files: dict[str, bytes] = {}
    records = []
    for mode in ('default', 'p5'):
        for width, height in ((80, 24), (132, 50)):
            for tier in ('16', '256', 'truecolor'):
                name = f'r1-title-{mode}-{width}x{height}-{tier}'
                matches = [a for a in artifacts['artifacts'] if a['name'] == name and not a['expired']]
                require(len(matches) == 1, f'missing or duplicate artifact: {name}')
                artifact = matches[0]
                require(artifact['workflow_run']['id'] == run_id, 'wrong artifact run')
                directory = root/name
                result = json.loads((directory/'r1-results.json').read_text(encoding='utf-8'))
                client = json.loads((directory/'native-client.json').read_text(encoding='utf-8'))
                require(result['passed'] and result['head'] == head, f'{name}: wrong result head')
                require(client['python_tree_sha256'] == expected_source, f'{name}: wrong wheel source')
                require(result['size'] == [width, height] and result['tier'] == tier
                        and result['presentation'] == mode and result['capture'] == name,
                        f'{name}: wrong capture matrix case')
                require(result['transport'] == 'NetBBS Telnet -> registered native stdio', 'wrong transport')
                wheel = result['clean_wheel']
                require(wheel['old_import_available'] is False and wheel['module_door_help']
                        and wheel['native_module_door_started'], f'{name}: incomplete clean-wheel proof')
                audit = result['world_audit']
                require(not audit['migration_required'] and not audit['findings']
                        and audit['rows'] > 0 and audit['tables'] > 0, f'{name}: missing world audit')
                require(audit == json.loads((directory/'world-audit.json').read_text(encoding='utf-8')),
                        f'{name}: inconsistent world audit')
                require(not result['presentation_acceptance'] and not result['h1_layout_approval']
                        and not result['s25_layout_approval'], 'engineering proof cannot grant human gates')
                require(set(result['sha256']) == {'.ans', '.txt', '.json'}, 'incomplete capture hashes')
                for suffix, digest in result['sha256'].items():
                    require(sha256((directory/(name+suffix)).read_bytes()).hexdigest() == digest,
                            f'{name}{suffix}: hash mismatch')
                start = verify_capture(directory, name, width, height)
                text = (directory/(name+'.txt')).read_text(encoding='utf-8')
                require('KARST 41' in text.splitlines()[1] and 'Karst, Year 41' in text
                        and 'The city was built to keep something in.' in text, f'{name}: missing title')
                require('THE WAKE' not in text, f'{name}: captured after the title')
                files[name+'.txt'] = (directory/(name+'.txt')).read_bytes()
                records.append({**result, 'file': name+'.txt', 'source_tree': tree,
                    'python_tree_sha256': expected_source, 'run': run_id,
                    'run_url': run['html_url'], 'artifact': name, 'artifact_id': artifact['id'],
                    'artifact_url': f'https://github.com/Thiesi/Karst41/actions/runs/{run_id}/artifacts/{artifact["id"]}',
                    'native_boundary_offset': start,
                    'verification': 'Original ANSI replay matches retained text and full glyph/style snapshot'})
    manifest = dict(source_head=head, source_tree=tree, python_tree_sha256=expected_source,
                    run=run_id, captures=records, presentation_acceptance=False,
                    h1_layout_approval=False, s25_layout_approval=False)
    files['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    require(sum(map(len, files.values())) <= 200_000, 'packet exceeds evidence budget')
    require(not destination.exists(), 'preserve existing evidence; destination already exists')
    destination.mkdir(parents=True)
    for name, data in files.items():
        (destination/name).write_bytes(data)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'docs/ops/captures/r1/native')
    args = parser.parse_args()
    report = build_packet(args.root, json.loads(args.run.read_text(encoding='utf-8-sig')),
                          json.loads(args.artifacts.read_text(encoding='utf-8-sig')), args.output)
    print(json.dumps(dict(head=report['source_head'], captures_verified=len(report['captures']),
                          run=report['run'])))
