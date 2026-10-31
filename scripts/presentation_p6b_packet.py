"""Verify the B1/B2/B3 artifacts and retain a compact, byte-preserved packet."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT), str(ROOT/'scripts')]

from scripts.presentation_p6_packet import digest, require, safe_filename, source_hash, verify_capture
from scripts.presentation_p6b_changes import ALLOWED, ZONES

CONFIGS = (('80x24','16'), ('80x24','256'), ('132x50','16'),
           ('132x50','256'), ('132x50','truecolor'))
STEPS = ('clinic-known-interior', 'pharmacy-frontage', 'plaza-second-terminal',
         'sodium-row-entry', 'tin-halo-frontage')


def build(root: Path, metadata: list[dict[str, Any]], run: int, head: str,
          source_tree: str, destination: Path) -> dict[str, Any]:
    require(not destination.exists(), 'preserve existing evidence; choose a new packet directory')
    expected_source = source_hash(head, source_tree)
    expected = {f'p6b-native-{size}-{tier}' for size,tier in CONFIGS}
    expected |= {f'p6b-budget-{zid}' for zid in ZONES}
    artifacts = {a['name']: a for a in metadata if a['name'].startswith('p6b-')}
    require(set(artifacts) == expected, 'expected five native and three budget artifacts')
    files: dict[str, bytes] = {}
    records, budgets, provenance, incomplete = [], [], {}, []
    for name, artifact in artifacts.items():
        require(artifact.get('workflow_run', {}).get('head_sha') == head, f'{name}: artifact head mismatch')
        provenance[name] = {'id': artifact['id'], 'archive_digest': artifact['digest'],
            'url': f'https://github.com/Thiesi/Blacksite/actions/runs/{run}/artifacts/{artifact["id"]}'}
    for size,tier in CONFIGS:
        name = f'p6b-native-{size}-{tier}'
        directory = root/name/'p6b-proof'
        result = json.loads((directory/'result.json').read_text(encoding='utf-8'))
        require(result['head'] == head and result['passed'] and result['show'], f'{name}: execution mismatch')
        require(result['console']['isatty'] and result['console']['size'] == list(map(int,size.split('x'))),
                f'{name}: attached terminal dimensions mismatch')
        require(not result['teleports'] and not result['local_handle_override'] and not result['human_approval'],
                f'{name}: native provenance or human gate mismatch')
        require(result['source_matched_wheel']['python_tree_sha256'] == expected_source, f'{name}: source mismatch')
        for filename, item in result['manifest'].items():
            path = directory/safe_filename(filename)
            require(path.stat().st_size == item['bytes'] and digest(path) == item['sha256'], f'{name}/{filename}: hash mismatch')
        provenance[name]['result_sha256'] = digest(directory/'result.json')
        require(len(result['cases']) == 1, f'{name}: expected one case')
        case = result['cases'][0]
        require(case['size'] == list(map(int,size.split('x'))) and case['tier'] == tier, f'{name}: case mismatch')
        require(case['handle'].isascii() and '界' in case['character_name'], f'{name}: identity provenance mismatch')
        require(case['ordinary_inputs'] and case['jack_in_out'] and case['remembered_clinic_terminal']
                and not case['tin_halo_entered'], f'{name}: route incomplete')
        require(all(key in ('1b5b41','1b5b42','1b5b43','1b5b44','62','65','6a','1879','20')
                    for key in case['key_hex_after_character_creation']), f'{name}: unexpected player input')
        require(case['captures'] == [f'{step}-{size}-{tier}' for step in STEPS], f'{name}: checkpoints mismatch')
        for stem in case['captures']:
            offset = verify_capture(directory, stem, *case['size'])
            keep = tier != 'truecolor' or stem.startswith(('plaza-second-terminal-', 'tin-halo-frontage-'))
            if keep:
                files[stem+'.txt'] = (directory/(stem+'.txt')).read_bytes()
            records.append({'name': stem, 'artifact': name, 'artifact_path': 'p6b-proof/'+stem,
                'sha256': {ext: digest(directory/(stem+ext)) for ext in ('.ans','.txt','.json')},
                'ansi_offset': offset, 'committed_text': keep})
    change_report = None
    for zid in ZONES:
        name = f'p6b-budget-{zid}'
        directory = root/name
        changes = json.loads((directory/'b3-changes.json').read_text(encoding='utf-8'))
        require(not changes['owner_fingerprint_approval'] and {g['path'] for g in changes['goldens']} == ALLOWED,
                f'{name}: B3 scope or owner gate mismatch')
        require(change_report is None or changes == change_report, 'B3 artifacts disagree')
        change_report = changes
        if not (directory/'b2-budget.json').exists():
            # The first B2 run asserted before its end-only report write.
            # Preserve the verified B1/B3 packet and label the missing B2
            # evidence; never turn the missing report into a budget pass.
            incomplete.append(zid)
            provenance[name]['report_unavailable'] = True
            continue
        data = json.loads((directory/'b2-budget.json').read_text(encoding='utf-8'))
        require(data['head'] == head and not data['dirty'] and data['cpu_budget_reference']
                and data['seconds'] == 12., f'{name}: clean Linux reference required')
        if len(data['cases']) != 9 or data.get('incomplete_error'):
            incomplete.append(zid)
        provenance[name]['report_sha256'] = digest(directory/'b2-budget.json')
        for case in data['cases']:
            require(case['zone'] == zid, f'{name}: zone mismatch')
            row = {key: case[key] for key in ('zone','start','size','tier','fully_known','verdict','wire')}
            row['frame_summary'] = {label: arm['frames']['summary'] for label,arm in case['arms'].items()}
            row['frame_budgets_pass'] = all(arm['frames']['delta_16kib_pass'] and arm['frames']['render_p95_100ms_pass']
                                           for arm in case['arms'].values())
            budgets.append(row)
    files['changes.json'] = (json.dumps(change_report,separators=(',',':'))+'\n').encode()
    budget_pass = not incomplete and len(budgets) == 27 and all(
        row['frame_budgets_pass'] and row['verdict']['cpu_120s_per_hour_pass'] for row in budgets)
    files['performance.json'] = (json.dumps({'cases': budgets, 'incomplete_zones': incomplete,
        'budget_acceptance': False, 'all_numeric_targets_pass': budget_pass, 'cpu_policy':
        '120 s/h verdict recorded; every historical P5 increase requires explanation/review; '
        'different shipped maps/content, not a causal comparison'},separators=(',',':'))+'\n').encode()
    manifest = {'schema': 1, 'execution_head': head, 'run': run, 'source_git_tree': source_tree,
        'source_python_tree_sha256': expected_source, 'artifacts': provenance, 'captures': records,
        'replayed_glyph_and_style_checks': len(records), 'required_text_captures': len(files)-2,
        'transport': 'NetBBS 7.45.0 Telnet -> registered native stdio; sized attached PTYs; matched wheel',
        'fixtures': 'native: private node/world/accounts only; normal creation, arrows/E/J/B. '
                    'Budget: disclosed pose/knowledge, shipped population and seeded world, unchanged P1 meter.',
        'human_approval': False, 'fingerprint_approval': False, 'presentation_signoff': False,
        's25_layout_approval': False}
    manifest['capture_stage'] = 'pre-A7 diagnostic; final Part B capture waits for owner A7 merge'
    manifest['b1_acceptance'] = False
    manifest['budget_evidence_complete'] = not incomplete and len(budgets) == 27
    manifest['budget_acceptance'] = False
    files['manifest.json'] = (json.dumps(manifest,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
    total = sum(map(len,files.values()))
    require(total <= 195*1024, f'{total} bytes exceeds packet budget; review text selection explicitly')
    destination.mkdir(parents=True)
    for name,data in files.items():
        (destination/name).write_bytes(data)
    return {'execution_head': head, 'captures_replayed': len(records), 'budget_cases': len(budgets),
            'incomplete_budget_zones': incomplete, 'budget_acceptance': False,
            'committed_text_captures': len(files)-3, 'repository_bytes': total}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts-root',type=Path,required=True)
    parser.add_argument('--metadata',type=Path,required=True)
    parser.add_argument('--run',type=int,required=True)
    parser.add_argument('--head',required=True)
    parser.add_argument('--source-tree',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    data = json.loads(args.metadata.read_text(encoding='utf-8-sig'))
    if isinstance(data,dict):
        data = data['artifacts']
    print(json.dumps(build(args.artifacts_root,data,args.run,args.head,args.source_tree,args.output)))
