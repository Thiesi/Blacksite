"""Demo only: play the Sodium Row demo locally in a Windows console.

Run the server first, in another console (PowerShell shown; in cmd use
`set BLACKSITE_DEMO=sodium-row-evening`):

    $env:BLACKSITE_DEMO = 'sodium-row-evening'
    python -m blacksite.server --install-dir <dir> --tcp

Then, in Windows Terminal (or any VT console):

    python scripts/demo_sodium/play.py --install-dir <dir> --handle Thiesi [--signs]

It sets the console to UTF-8 and VT output for this run and restores the
previous code pages afterwards. It writes a drop file at the current
terminal size and starts the door with --local and the new presentation.
--user-id gives a second caller its own identity (playtest 3).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def utf8_console():
    if os.name != 'nt':
        return lambda: None
    kernel = ctypes.windll.kernel32
    previous = kernel.GetConsoleCP(), kernel.GetConsoleOutputCP()
    kernel.SetConsoleCP(65001)
    kernel.SetConsoleOutputCP(65001)
    handle = kernel.GetStdHandle(-11)
    mode = ctypes.c_uint32()
    had_mode = bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)))
    if had_mode:
        kernel.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING

    def restore():
        kernel.SetConsoleCP(previous[0])
        kernel.SetConsoleOutputCP(previous[1])
        if had_mode:
            kernel.SetConsoleMode(handle, mode.value)
    return restore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Play the Sodium Row demo locally (demo only).')
    parser.add_argument('--install-dir', required=True, type=Path)
    parser.add_argument('--handle', default='Thiesi')
    parser.add_argument('--user-id', type=int, default=1)
    parser.add_argument('--color', default='truecolor', choices=('16', '256', 'truecolor'))
    parser.add_argument('--signs', action='store_true', help='far signs at night (also set BLACKSITE_DEMO_SIGNS=charted on the server)')
    args = parser.parse_args(argv)

    size = shutil.get_terminal_size((132, 50))
    info = {'handle': args.handle, 'user_id': args.user_id, 'node_name': 'local',
            'terminal_width': size.columns, 'terminal_height': size.lines,
            'color_depth': args.color, 'unicode_style': True}
    drop = Path(tempfile.gettempdir()) / f'blacksite-demo-door-{args.user_id}.json'
    drop.write_text(json.dumps(info), encoding='utf-8')
    env = {**os.environ, 'NETBBS_DOOR_INFO': str(drop), 'BLACKSITE_INSTALL_DIR': str(args.install_dir.resolve()),
           'DOOR_BLACKSITE_PRESENTATION': '1'}
    if args.signs:
        env['DOOR_BLACKSITE_DEMO_SIGNS'] = 'charted'
    restore = utf8_console()
    try:
        return subprocess.call([sys.executable, '-m', 'blacksite.door', '--local'], env=env)
    finally:
        restore()


if __name__ == '__main__':
    sys.exit(main())
