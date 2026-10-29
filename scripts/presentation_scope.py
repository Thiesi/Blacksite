"""Conservative draft-only native subset selection. Ready PRs run all jobs."""

import argparse
import json
from pathlib import PurePosixPath
import subprocess

DISPLAY_FILES = {f'src/blacksite/door/{name}.py' for name in
    ('model', 'cells', 'screens', 'layout', 'palette', 'log')}


def full_native(paths: list[str], draft: bool) -> tuple[bool, str]:
    if not draft:
        return True, 'ready for review or merge: full native matrix'
    if not paths:
        return True, 'no changed-path evidence'
    presentation = False
    for path in paths:
        parts = PurePosixPath(path).parts
        if '..' in parts or path.startswith('/'):
            return True, 'unrecognized path'
        allowed = (path in DISPLAY_FILES or path.startswith('src/blacksite/door/views/')
            or (path.startswith('src/blacksite/content/text/') and PurePosixPath(path).suffix in ('.md', '.txt'))
            or path.startswith('src/blacksite/content/art/')
            or path in ('src/blacksite/content/palette.json', 'src/blacksite/content/glyphs.json'))
        if allowed:
            presentation = True
        elif not path.startswith('tests/'):
            return True, f'outside the presentation-only allowlist: {path}'
    return (False, 'draft presentation-only changes') if presentation else (True, 'no presentation source change')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--draft', choices=('true', 'false'), required=True)
    args = parser.parse_args()
    for value in (args.base, args.head):
        if len(value) != 40 or any(ch not in '0123456789abcdef' for ch in value):
            parser.error('base and head must be full SHA identifiers')
    raw = subprocess.check_output(['git', 'diff', '--no-renames', '--name-only', '-z', args.base+'...'+args.head])
    paths = [name.decode('utf-8') for name in raw.split(b'\0') if name]
    full, reason = full_native(paths, args.draft == 'true')
    print(json.dumps({'full': full, 'reason': reason}))
