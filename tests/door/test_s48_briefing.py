"""S48 / #216: every Wake briefing page shows text, and the prose uses the frame's width."""

from dataclasses import replace
from pathlib import Path

import pytest

from karst41.content.loader import load_content
from karst41.door.model import Display
from karst41.server.protocol import Frame
from karst41.server.wake import Wake, briefing, pages
from tests.fake_terminal import FakeTerminal
from tests.presentation.snapshots import assert_golden


@pytest.fixture(scope='module')
def content():
    return load_content(Path(__file__).parents[2]/'src/karst41/content')


def test_216_pages_never_start_with_or_are_only_blank():
    assert pages(['a', 'b', '', 'c', ''], 2) == [['a', 'b'], ['c']]
    assert pages(['a', '', ''], 1) == [['a']]
    assert pages(['', 'a'], 3) == [['a']]
    assert pages([], 4) == [[]]


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
@pytest.mark.parametrize('screen', [1, 2, 3])
def test_216_every_briefing_page_shows_text(content, width, height, screen):
    book = briefing(content, screen, width, height)
    assert book and all(any(line.strip() for line in page) for page in book)
    assert all(page[0].strip() for page in book)
    wake = Wake(stage='briefing', screen=screen)
    for number in range(len(book)):
        wake.page = number
        body = wake.body(content, 'Handle', width, height)['body']
        assert body['lines'] == book[number] and body['flow'] is True
        assert body['title'].endswith(f'({number + 1}/{len(book)})')


def render(info, content, width, height, screen, page, presentation):
    wake = Wake(stage='briefing', screen=screen, page=page)
    display = Display(replace(info, width=width, height=height, color_depth='16'), presentation=presentation)
    display.receive(Frame('view', {'rev': 1, 'kind': 'wake', 'body': wake.body(content, 'Handle', width, height)}), 0)
    terminal = FakeTerminal(width, height)
    terminal.write(display.render(0)[0])
    return terminal


@pytest.mark.parametrize('width,height', [(80, 24), (132, 50)])
@pytest.mark.parametrize('presentation', [False, True])
def test_216_briefing_pages_render_with_text(repo_root, info, content, request, width, height, presentation):
    for screen in (1, 2, 3):
        for page in range(len(briefing(content, screen, width, height))):
            terminal = render(info, content, width, height, screen, page, presentation)
            first = briefing(content, screen, width, height)[page][0].split()[0]
            assert first in terminal.screen_text()
            assert_golden(repo_root/'tests/presentation/golden/s48-briefing',
                          f"s48_briefing_{'present' if presentation else 'legacy'}_{width}x{height}_{screen}_{page + 1}",
                          terminal, '16', trim=True, update=request.config.getoption('--update-goldens'))


def test_216_presentation_wraps_the_prose_to_the_frame_width(info, content):
    """The reviewer saw ~51 columns inside a 78-column frame."""
    terminal = render(info, content, 80, 24, 2, 0, True)
    rows = [row for row in terminal.screen_text().splitlines() if "Here's the part" in row or 'Sablier property' in row]
    longest = max(len(row.strip('│ ').rstrip()) for row in terminal.screen_text().splitlines()[2:14])
    assert rows and longest > 60
