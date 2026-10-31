"""Packet verification rejects edited glyph/style captures.

These small synthetic streams exercise the verifier, never play evidence.
"""

import json
from pathlib import Path

import pytest

from scripts.presentation_p6_packet import verify_capture
from tests.fake_terminal import FakeTerminal
from tests.presentation.snapshots import canonical, snapshot


@pytest.mark.parametrize('corrupt', ('none', 'text', 'style'))
def test_native_packet_checks_replayed_glyphs_and_styles(tmp_path: Path, corrupt: str) -> None:
    stream = b'node bytes\x1b[?1049h\x1b[2J\x1b[H\x1b[31mTest'
    terminal = FakeTerminal(80, 24)
    terminal.write(stream[stream.index(b'\x1b[?1049h'):])
    (tmp_path/'unit.ans').write_bytes(stream)
    text = terminal.screen_text()
    (tmp_path/'unit.txt').write_text(text.replace('Test','Fail') if corrupt == 'text' else text,
                                   encoding='utf-8', newline='\n')
    styles = snapshot(terminal)
    if corrupt == 'style':
        styles['styles'][0]['fg'] = [5, 99]
    (tmp_path/'unit.json').write_text(canonical(styles),encoding='utf-8',newline='\n')
    if corrupt == 'none':
        assert verify_capture(tmp_path,'unit',80,24) == len(b'node bytes')
    else:
        with pytest.raises(ValueError,match='ANSI replay differs'):
            verify_capture(tmp_path,'unit',80,24)
