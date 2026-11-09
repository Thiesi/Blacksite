"""R1 title proof from an installed wheel and a real native-door stream.

The title is brief on a first visit. Retain its last complete repaint
before the Wake, directly from the live caller's original ANSI prefix.
No renderer, title text, view, pause or server message is substituted.
"""

import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import traceback

from accept_s10_netbbs import NativeProbe
from audit_r1_world import audit
from r1_title import title_prefix
from tests.presentation.snapshots import snapshot


async def accept(root: Path, python: Path, size: tuple[int, int], tier: str,
                 presentation: str, show: bool) -> None:
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    # A real wheel in a clean venv must not depend on the old editable package.
    check = subprocess.run([str(python), '-I', '-c',
        'import importlib.util,karst41; assert importlib.util.find_spec("blacksite") is None; '
        'print(karst41.__version__)'], capture_output=True, text=True, check=True)
    help_result = subprocess.run([str(python), '-I', '-m', 'karst41.door', '--help'],
                                 capture_output=True, text=True, check=True)
    assert 'Karst 41 native door' in help_result.stdout
    probe = NativeProbe(root, python, show, show_all_tiers=True,
        door_environment={'DOOR_KARST41_PRESENTATION': '1' if presentation == 'p5' else '0'})
    passed = False
    try:
        await probe.start()
        width, height = size
        caller = await probe.open(width, height, 'R1'+tier, sixteen=tier == '16', truecolor=tier == 'truecolor')
        assert caller.session.caps['tier'] == tier
        raw, terminal = title_prefix(bytes(caller.caller.output), width, height)
        label = f'r1-title-{presentation}-{width}x{height}-{tier}'
        (root/(label+'.ans')).write_bytes(raw)
        (root/(label+'.txt')).write_bytes(terminal.screen_text().encode('utf-8'))
        (root/(label+'.json')).write_text(json.dumps(snapshot(terminal), ensure_ascii=False,
                                        indent=2)+'\n', encoding='utf-8')
        hashes = {suffix: sha256((root/(label+suffix)).read_bytes()).hexdigest()
                  for suffix in ('.ans', '.txt', '.json')}
        await probe.leave(caller, f'r1-left-{width}x{height}-{tier}')
        assert not probe.errors and probe.service.failure is None
        passed = True
    except BaseException:
        root.mkdir(parents=True, exist_ok=True)
        (root/'failure-trace.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    finally:
        await probe.close()
    if passed:
        # Explicit R1 offline audit: the acceptance service has closed its DB.
        persisted = audit(root/'world'/'world.db')
        assert not persisted['migration_required'], persisted
        (root/'world-audit.json').write_text(json.dumps(persisted, indent=2)+'\n', encoding='utf-8')
        (root/'r1-results.json').write_text(json.dumps({'passed': True, 'head': head,
            'transport': 'NetBBS Telnet -> registered native stdio', 'size': list(size), 'tier': tier,
            'presentation': presentation,
            'capture': label, 'sha256': hashes, 'ansi_prefix_bytes': len(raw),
            'method': 'Last complete title repaint before Wake; unchanged live ANSI prefix',
            'clean_wheel': {'version': check.stdout.strip(), 'old_import_available': False,
                            'module_door_help': True, 'native_module_door_started': True},
            'world_audit': persisted, 'presentation_acceptance': False,
            'h1_layout_approval': False, 's25_layout_approval': False}, indent=2)+'\n', encoding='utf-8')
        probe.report(f'R1 PASS {presentation}/{width}x{height}/{tier}: live title, clean wheel, offline persisted-data audit')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--door-python', type=Path, required=True)
    parser.add_argument('--size', choices=('80x24', '132x50'), required=True)
    parser.add_argument('--tier', choices=('16', '256', 'truecolor'), required=True)
    parser.add_argument('--presentation', choices=('default', 'p5'), default='default')
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()
    asyncio.run(accept(args.root, args.door_python, tuple(map(int, args.size.split('x'))),
                       args.tier, args.presentation, args.show))
