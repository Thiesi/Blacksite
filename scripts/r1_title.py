"""Select a complete title repaint from unchanged native caller bytes."""

import re

from tests.fake_terminal import FakeTerminal


def title_prefix(stream: bytes, width: int, height: int) -> tuple[bytes, FakeTerminal]:
    start = stream.index(b'\x1b[?1049h')
    frame_starts = [m.start() for m in re.finditer(re.escape(b'\x1b[1;1H'), stream[start:])]
    selected = None
    for index in range(1, len(frame_starts)):
        end = start+frame_starts[index]
        frame = stream[start+frame_starts[index-1]:end]
        if f'\x1b[{height};1H'.encode() not in frame:
            continue
        terminal = FakeTerminal(width, height)
        for offset in range(start, end, 4096):
            terminal.write(stream[offset:min(offset+4096, end)])
        lines = terminal.screen_text().splitlines()
        if ('KARST 41' in lines[1] and 'Karst, Year 41' in terminal.screen_text()
                and 'The city was built to keep something in.' in terminal.screen_text()):
            selected = stream[:end], terminal
    if selected is None:
        raise AssertionError('No complete live native title repaint found')
    return selected
