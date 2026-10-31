"""Verify real P6 native artifacts and commit a small text review packet.

Download the four p6-fixture-* artifacts into separate named directories.
Raw ANSI and full style snapshots stay in those CI artifacts (§4 review
policy); selected byte-preserved text plus hashes go in the repository.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT)]

from tests.fake_terminal import FakeTerminal
from tests.presentation.snapshots import canonical,snapshot


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_packet(root: Path, metadata: list[dict[str,Any]], run: int, head: str,
                 destination: Path) -> dict[str,Any]:
    if destination.exists():
        raise FileExistsError('preserve existing evidence; use a new packet directory')
    files: dict[str,bytes] = {}
    records,artifacts,source_hashes = [],{},set()
    cases = 0
    for artifact in metadata:
        name = artifact['name']
        if not name.startswith('p6-fixture-'):
            continue
        directory = root/name/'p6-proof'
        result = json.loads((directory/'result.json').read_text(encoding='utf-8'))
        assert result['head']==head and result['passed'] and result['show'], name
        source_hashes.add(result['source_matched_wheel']['python_tree_sha256'])
        for filename,expected in result['manifest'].items():
            assert digest(directory/filename)==expected,(name,filename)
        artifacts[name] = {'id':artifact['id'],
            'url':f'https://github.com/Thiesi/Blacksite/actions/runs/{run}/artifacts/{artifact["id"]}',
            'result_sha256':digest(directory/'result.json')}
        for case in result['cases']:
            cases += 1
            width,height = case['size']
            assert case['handle'].isascii() and '界' in case['name']
            assert len(case['captures'])==4
            for stem in case['captures']:
                ansi,text,style = (directory/(stem+suffix) for suffix in ('.ans','.txt','.json'))
                terminal = FakeTerminal(width,height)
                terminal.write(ansi.read_bytes())
                assert terminal.screen_text()==text.read_bytes().decode('utf-8'),stem
                assert canonical(snapshot(terminal))==canonical(json.loads(style.read_text(encoding='utf-8'))),stem
                step = stem.removeprefix(case['theme']+'-').removesuffix(f'-{width}x{height}-{case["tier"]}')
                keep = step in ('charted-and-here','light-region-and-here') or (
                    step in ('authored-cover','notice') and (
                        (width==80 and case['theme']=='dark' and case['tier']=='256') or
                        (width==132 and case['theme']=='light' and case['tier']=='truecolor')))
                if keep:
                    files[stem+'.txt'] = text.read_bytes()
                records.append({'name':stem,'scenario':step,'size':case['size'],'tier':case['tier'],
                    'theme':case['theme'],'artifact':name,'artifact_path':'p6-proof/'+stem,
                    'text_sha256':digest(text),'ansi_sha256':digest(ansi),'style_sha256':digest(style),
                    'committed_text':stem+'.txt' if keep else None,
                    'caller_name':case['name'],'bbs_handle':case['handle']})
    assert len(artifacts)==4 and cases==12 and len(records)==48 and len(source_hashes)==1
    manifest = {'schema':1,'execution_head':head,'run':run,'source_python_tree_sha256':source_hashes.pop(),
        'transport':'NetBBS v7.45.0 Telnet -> registered native stdio; sized attached PTY; source-matched wheel',
        'fixture':'tests/fixtures/p6 via content.local; ordinary character creation; explicit initial placement (4,5), then real walking keys',
        'caller_provenance':'Wide character name is entered through ordinary character creation; genuine BBS handles remain ASCII. No handle override.',
        'artifacts':artifacts,'captures':records,'replay_glyph_and_style_checks':len(records),
        'human_approval':False,'presentation_signoff':False,'shipped_place_acceptance':False}
    files['manifest.json'] = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    summary = {'execution_head':head,'native_cases':cases,'captures_replayed':len(records),
               'committed_text_captures':len(files)-1,'sha256_checks':'all result-manifest files matched',
               'human_approval':False,'presentation_signoff':False}
    files['summary.json'] = (json.dumps(summary,indent=2)+'\n').encode('utf-8')
    total = sum(map(len,files.values()))
    assert total<=195*1024, f'packet is {total} bytes; retain room for the review README under 200 KiB'
    destination.mkdir(parents=True)
    for name,data in files.items():
        (destination/name).write_bytes(data)
    return {**summary,'repository_bytes':total}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts-root',type=Path,required=True)
    parser.add_argument('--metadata',type=Path,required=True)
    parser.add_argument('--run',type=int,required=True)
    parser.add_argument('--head',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding='utf-8-sig'))
    if isinstance(metadata,dict):
        metadata = metadata['artifacts']
    print(json.dumps(build_packet(args.artifacts_root,metadata,args.run,args.head,args.output),indent=2))


if __name__=='__main__':
    main()
