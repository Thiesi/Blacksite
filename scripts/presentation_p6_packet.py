"""Verify real P6 native artifacts and commit a small text review packet.

Download the four p6-fixture-* artifacts into separate named directories.
Raw ANSI and full style snapshots stay in those CI artifacts (§4 review
policy); selected byte-preserved text plus hashes go in the repository.
"""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT)]

from tests.fake_terminal import FakeTerminal
from tests.presentation.snapshots import canonical,snapshot


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_filename(value: str) -> str:
    require(bool(value) and value not in ('.','..') and Path(value).name==value
            and not any(char in value for char in ('/','\\',':')),
            f'artifact filename must be a basename: {value!r}')
    return value


def source_hash(head: str, source_tree: str) -> str:
    """Tie native Python bytes to a separately pinned Git source tree."""
    require(bool(re.fullmatch('[0-9a-f]{40}',head)) and bool(re.fullmatch('[0-9a-f]{40}',source_tree)),
            'head and source-tree must be full Git object ids')
    actual = subprocess.check_output(['git','rev-parse',f'{head}:src/blacksite'],cwd=ROOT,text=True).strip()
    require(actual==source_tree, f'expected source tree {source_tree}, but {head} contains {actual}')
    archive = subprocess.check_output(['git','archive',source_tree],cwd=ROOT)
    digest = sha256()
    # Read in memory, never extract artifact or archive paths. Match the
    # source-matched wheel guard in NativeProbe, including LF normalisation.
    with tarfile.open(fileobj=BytesIO(archive)) as tree:
        for member in sorted(tree.getmembers(),key=lambda item:item.name):
            if member.isfile() and member.name.endswith('.py'):
                data = tree.extractfile(member).read()
                digest.update(member.name.encode()+b'\0'+data.replace(b'\r\n',b'\n')+b'\0')
    return digest.hexdigest()


def verify_capture(directory: Path, stem: str, width: int, height: int) -> int:
    """Replay the shared native-door boundary without editing capture bytes."""
    safe_filename(stem)
    ansi,text,style = (directory/(stem+suffix) for suffix in ('.ans','.txt','.json'))
    terminal = FakeTerminal(width,height)
    stream = ansi.read_bytes()
    start = stream.find(b'\x1b[?1049h')
    require(start>=0 and b'\x1b[?1049l' not in stream[start:],
            f'{stem}: expected an active native door alternate screen')
    # Feed the exact stream incrementally, as the live caller does.
    # A multi-megabyte cumulative walk otherwise makes FakeTerminal's
    # pending-string parser quadratic; no capture bytes are changed.
    for offset in range(start,len(stream),4096):
        terminal.write(stream[offset:offset+4096])
    # NativeProbe uses the host's text newlines. Compare logical rows on
    # Windows too; retain and hash the original bytes without rewriting.
    require(terminal.screen_text()==text.read_bytes().decode('utf-8').replace('\r\n','\n'),
            f'{stem}: ANSI replay differs from captured text')
    require(canonical(snapshot(terminal))==canonical(json.loads(style.read_text(encoding='utf-8'))),
            f'{stem}: ANSI replay differs from captured styles')
    return start


def build_packet(root: Path, metadata: list[dict[str,Any]], run: int, head: str,
                 destination: Path, *, source_tree: str) -> dict[str,Any]:
    if destination.exists():
        raise FileExistsError('preserve existing evidence; use a new packet directory')
    expected_source = source_hash(head,source_tree)
    files: dict[str,bytes] = {}
    records,artifacts,source_hashes = [],{},set()
    cases = 0
    expected_artifacts = {f'p6-fixture-{theme}-{size}' for theme in ('dark','light')
                          for size in ('80x24','132x50')}
    for artifact in metadata:
        name = artifact['name']
        if not name.startswith('p6-fixture-'):
            continue
        require(name in expected_artifacts and name not in artifacts,
                f'unexpected or duplicate native artifact: {name!r}')
        directory = root/name/'p6-proof'
        result = json.loads((directory/'result.json').read_text(encoding='utf-8'))
        require(result['head']==head and result['passed'] and result['show'],
                f'{name}: head, native pass or attached-terminal provenance mismatch')
        native_source = result['source_matched_wheel']['python_tree_sha256']
        require(native_source==expected_source,
                f'{name}: native Python source hash differs from pinned source tree {source_tree}')
        source_hashes.add(native_source)
        for filename,expected in result['manifest'].items():
            require(digest(directory/safe_filename(filename))==expected,
                    f'{name}/{filename}: SHA-256 mismatch')
        artifacts[name] = {'id':artifact['id'],
            'url':f'https://github.com/Thiesi/Blacksite/actions/runs/{run}/artifacts/{artifact["id"]}',
            'result_sha256':digest(directory/'result.json')}
        for case in result['cases']:
            cases += 1
            width,height = case['size']
            require(case['handle'].isascii() and '界' in case['name'],
                    f'{name}: genuine ASCII handle and wide character name are required')
            require(len(case['captures'])==4,
                    f'{name}/{case["tier"]}: expected four named native checkpoints')
            for stem in case['captures']:
                safe_filename(stem)
                ansi,text,style = (directory/(stem+suffix) for suffix in ('.ans','.txt','.json'))
                # NativeProbe's Caller.replay starts at the door's alternate
                # screen, after NetBBS/Telnet negotiation. Preserve and hash
                # the entire stream; replay that same displayed boundary.
                start = verify_capture(directory,stem,width,height)
                step = stem.removeprefix(case['theme']+'-').removesuffix(f'-{width}x{height}-{case["tier"]}')
                require(step in ('charted-and-here','authored-cover','light-region-and-here','notice'),
                        f'{stem}: unrecognised checkpoint; update the review selection explicitly')
                keep = step in ('charted-and-here','light-region-and-here') or (
                    step in ('authored-cover','notice') and (
                        (width==80 and case['theme']=='dark' and case['tier']=='256') or
                        (width==132 and case['theme']=='light' and case['tier']=='truecolor')))
                if keep:
                    files[stem+'.txt'] = text.read_bytes()
                records.append({'name':stem,'scenario':step,'size':case['size'],'tier':case['tier'],
                    'theme':case['theme'],'artifact':name,'artifact_path':'p6-proof/'+stem,
                    'text_sha256':digest(text),'ansi_sha256':digest(ansi),'style_sha256':digest(style),
                    'door_ansi_offset':start,
                    'committed_text':stem+'.txt' if keep else None,
                    'caller_name':case['name'],'bbs_handle':case['handle']})
    require(set(artifacts)==expected_artifacts and cases==12 and len(records)==48 and len(source_hashes)==1,
            f'expected four artifacts, twelve cases, 48 captures and one source tree; '
            f'got {len(artifacts)}, {cases}, {len(records)}, {len(source_hashes)}')
    manifest = {'schema':1,'execution_head':head,'run':run,'source_git_tree':source_tree,
        'source_python_tree_sha256':source_hashes.pop(),
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
    require(total<=195*1024, f'packet is {total} bytes; retain room for the review README under 200 KiB')
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
    parser.add_argument('--source-tree',required=True,help='pinned Git object id of execution head:src/blacksite')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text(encoding='utf-8-sig'))
    if isinstance(metadata,dict):
        metadata = metadata['artifacts']
    print(json.dumps(build_packet(args.artifacts_root,metadata,args.run,args.head,args.output,
                                  source_tree=args.source_tree),indent=2))


if __name__=='__main__':
    main()
