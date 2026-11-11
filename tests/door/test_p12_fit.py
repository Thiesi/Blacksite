"""P12: talk lines and log entries are never cut (slice P12, #204)."""

from copy import deepcopy
from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest

from karst41.content.loader import ContentTree, load_content
from karst41.content.schema import DialogueLine, Offer
from karst41.content.validate import validate
from karst41.door.cells import display_width
from karst41.door.doorinfo import DoorInfo
from karst41.door.fit import (LOG_CUT, TALK_LINE_ROWS, default_log_rows, fit_text,
                              select_entries, talk_rows, wrap_text)
from karst41.door.layout import compute
from karst41.door.model import Display
from karst41.door.present import chrome
from karst41.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.test_dialogue_runtime import content  # noqa: F401  (fixture)

SIZES = [(80, 24), (132, 50)]
RENDERERS = [False, True]  # default door views, opt-in presentation
SHIPPED = Path(__file__).resolve().parents[2] / 'src/karst41/content'


@cache
def shipped() -> ContentTree:
    return load_content(SHIPPED)


def longest_line() -> str:
    return max((ln.text for node in shipped().dialogue.values() for ln in node.lines), key=len)


def render(info: DoorInfo, size: tuple[int, int], presentation: bool, body: dict,
           logs: list[dict] | None = None, tier: str = 'truecolor') -> list[str]:
    display = Display(replace(info, width=size[0], height=size[1], color_depth=tier),
                      presentation=presentation)
    display.receive(Frame('welcome', {}), 0)
    display.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': body}), 0)
    if logs:
        display.receive(Frame('log', {'lines': logs}), 0)
    display.toast = None
    terminal = FakeTerminal(*size)
    terminal.write(display.render(0)[0])
    return terminal.screen_text().split('\n')


def talk_area(screen: list[str], size: tuple[int, int]) -> list[str]:
    area = compute(*size).menu.talk
    return [screen[y][area.x:area.right] for y in range(area.y, area.bottom)]


def talker(detail: str, actions: list[dict]) -> dict:
    return {'kind': 'talker', 'walk_away': True, 'title': 'Dispatcher', 'columns': ['Choice'],
            'rows': [], 'cursor': 0, 'detail': detail, 'actions': actions,
            'hint': 'Choose an action; move or Esc/B leaves'}


ACTIONS = {0: [], 1: [{'key': 'c', 'label': 'Work'}],
           3: [{'key': 'c', 'label': 'Work'}, {'key': 'v', 'label': 'Trade'},
               {'key': 'a', 'label': 'Ask about the back room'}]}


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('presentation', RENDERERS)
@pytest.mark.parametrize('count', [0, 1, 3])
def test_p12_longest_shipped_line_is_whole_with_one_leave_row(info, size, presentation, count):
    line = longest_line()
    assert len(line) >= 164
    rows = talk_area(render(info, size, presentation, talker(line, ACTIONS[count])), size)
    text = [row.rstrip() for row in rows]
    shown = ' '.join(row for row in text if row and not row.startswith(('c ', 'v ', 'a ', 'Esc/B')))
    assert shown.split() == line.split()  # every word, in order, nothing cut
    assert '...' not in shown
    assert text.count('Esc/B  Leave') == 1
    assert not any('Back' in row or 'Esc/B back' in row or 'Choice' in row for row in text)
    labels = [row for row in text if row.startswith(('c ', 'v ', 'a ', 'Esc/B'))]
    assert len(labels) == count + 1
    # One key column: every label starts in the same cell.
    starts = {row.index(' ') + len(row[row.index(' '):]) - len(row[row.index(' '):].lstrip(' ')) for row in labels}
    assert starts == {len('Esc/B  ')}
    blank = text.index(labels[0]) - 1
    assert text[blank] == '' and text[blank - 1]  # one blank row under the line


def test_p12_talk_line_starts_on_listing_top_and_spans_the_wide_page(info):
    line = longest_line()
    for presentation in RENDERERS:
        screen = render(info, (132, 50), presentation, talker(line, ACTIONS[1]))
        area = compute(132, 50).menu.talk
        assert area.y == 3 and area.width == 106
        assert screen[3][area.x:area.right].strip()  # the line starts at y3
        assert display_width(screen[3][area.x:area.right].rstrip()) > 53  # not the old column


@pytest.mark.parametrize('presentation', RENDERERS)
def test_p12_overlong_line_ends_its_last_row_with_ascii_cut(info, presentation):
    line = ' '.join(['word'] * 300)  # far more than 20 rows of 66 cells
    assert len(wrap_text(line, 66)) >= 20
    text = [row.rstrip() for row in talk_area(render(info, (80, 24), presentation, talker(line, ACTIONS[1])), (80, 24))]
    leave = text.index('Esc/B  Leave')
    assert text[leave - 2] == '' and text[leave - 3].endswith('...')
    assert '…' not in ''.join(text)


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('presentation', RENDERERS)
def test_p12_menu_detail_wraps_inside_its_rect(info, size, presentation):
    shape = compute(*size).menu
    detail = ('A heavy coat cut from old conveyor belting, stitched twice at every seam '
              'and patched where the last owner met something sharp.')
    assert display_width(detail) > shape.detail.width
    body = {'kind': 'vendor', 'title': 'Stall', 'columns': ['Item'], 'cursor': 0,
            'rows': [{'id': 'coat', 'cells': ['Belt coat']}], 'detail': detail,
            'actions': [{'key': 'e', 'label': 'buy'}]}
    screen = render(info, size, presentation, body)
    rows = [screen[y][shape.detail.x:shape.detail.right].rstrip()
            for y in range(shape.detail.y, shape.detail.bottom)]
    assert ' '.join(row for row in rows if row).split() == detail.split()
    assert 'e buy  Esc/B back' in screen[shape.actions.y]  # other menus keep the one-row bar


def test_p12_detail_fallback_and_blank_lines():
    assert fit_text('One.\n\nTwo.', 20, 3) == ['One.', '', 'Two.']
    cut = fit_text(' '.join(['word'] * 40), 20, 2)
    assert len(cut) == 2 and cut[-1].endswith('...') and display_width(cut[-1]) <= 20


def test_p12_talk_rows_key_column_follows_the_widest_key():
    rows = talk_rows('', [], 66, 14)
    assert [(r.key, r.label) for r in rows] == [('Esc/B  ', 'Leave')]
    rows = talk_rows('Hello.', [{'key': 'v', 'label': 'Trade'}], 66, 14)
    assert [r.text for r in rows[:2]] == ['Hello.', '']
    assert [(r.key, r.label) for r in rows[2:]] == [('v      ', 'Trade'), ('Esc/B  ', 'Leave')]


# --- rule 4: validator --------------------------------------------------------

@pytest.mark.parametrize(('change', 'message'), [
    ({'lines': (DialogueLine('fallback', ' '.join(['word'] * 60)),)}, 'wraps to 5 rows'),
    ({'offers': (Offer('vendor', 'x' * 41, 'v', 'vesper'),)}, 'label is 41 cells'),
    ({'offers': (Offer('vendor', 'Trade', 'b', 'vesper'),)}, 'unique single key'),
    ({'offers': tuple(Offer('vendor', f'Trade {key}', key, 'vesper') for key in 'acdefghij')},
     '9 offers; the 80x24 talk page fits at most 8'),
    ({'offers': (Offer('vendor', 'Trade', 'v', 'vesper'), Offer('vendor', 'Shop', 'V', 'vesper'))},
     'unique single key'),
])
def test_p12_validator_rejects_unfit_talk_content(content, change, message):  # noqa: F811
    tree = deepcopy(content)
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'], **change)
    assert any(message in problem.message for problem in validate(tree))


def test_p12_validator_accepts_a_four_row_line_and_a_40_cell_label(content):  # noqa: F811
    line = ' '.join(['word'] * 52)
    assert len(wrap_text(line, 66)) == TALK_LINE_ROWS
    tree = deepcopy(content)
    tree.dialogue['vesper'] = replace(tree.dialogue['vesper'],
        lines=(DialogueLine('fallback', line),), offers=(Offer('vendor', 'x' * 40, 'v', 'vesper'),))
    assert not [p for p in validate(tree) if 'rows' in p.message or 'cells' in p.message]


def test_p12_eight_offers_and_a_four_row_line_fit_the_80x24_talk_page():
    line = ' '.join(['word'] * 52)
    offers = [{'key': key, 'label': 'x' * 40} for key in 'acdefghi']
    rows = talk_rows(line, offers, 66, compute(80, 24).menu.talk.height)
    assert [r.text for r in rows[:4]] == wrap_text(line, 66) and rows[4] == type(rows[4])()
    assert [r.label for r in rows[5:]] == ['x' * 40] * 8 + ['Leave']


def test_p12_every_shipped_dialogue_line_fits():
    assert not [p for p in validate(shipped()) if 'talk page' in p.message or 'label is' in p.message]
    assert max(len(wrap_text(ln.text, 66)) for node in shipped().dialogue.values()
               for ln in node.lines) <= TALK_LINE_ROWS


# --- rule 5: the log ------------------------------------------------------------

def test_p12_select_entries_rules():
    # Newest reserved, others whole only, newest takes back free rows.
    assert select_entries([2, 2], [False, False], 3) == [0, 2]
    assert select_entries([1, 1, 1, 1], [True, True, True, False], 3) == [0, 1, 1, 1]
    assert select_entries([1, 1, 1, 2], [True, True, True, False], 3) == [0, 1, 1, 1]
    assert select_entries([1, 3], [True, True], 3) == [0, 3]
    assert select_entries([5], [False], 3) == [3]
    assert select_entries([1, 2, 1], [True, False, False], 3) == [1, 0, 1]
    # Steps 2 and 4 fill whatever is left: an entry too tall to fit whole is
    # skipped and an older, shorter one still fills the free row.
    assert select_entries([1, 3, 1], [False, False, False], 3) == [1, 0, 1]
    assert select_entries([1, 3, 1, 1], [False, False, False, False], 3) == [1, 0, 1, 1]
    assert select_entries([1, 3, 1], [True, True, False], 3) == [1, 0, 1]


def speech(text: str, second: int, arrived: float = 0) -> dict:
    return {'kind': 'speech', 'channel': 'zone', 'speaker': 'Dolf', 'text': text,
            'at': f'2026-11-11T12:00:{second:02}+00:00', '_arrived': arrived}


def line(kind: str, text: str, second: int, arrived: float = 0) -> dict:
    return {'kind': kind, 'channel': 'system', 'text': text,
            'at': f'2026-11-11T12:00:{second:02}+00:00', '_arrived': arrived}


TWO_ROWS = ("Back room's on Vesper's system. Jack in from the board if you want out the "
            'quiet way, and nobody on the Row will ask you why.')


def present_log(lines: list[dict], now: float = 1) -> list[tuple[str, str]]:
    return [(entry.text, text) for entry, text, _ in chrome.visible_rows(lines, 78, 3, now)]


def default_log(lines: list[dict]) -> list[str]:
    return [row['text'] for row in default_log_rows(lines, 78, 3)]


def test_p12_log_older_two_row_entry_never_shows_headless():
    older, newer = speech(TWO_ROWS, 0), line('ambient', TWO_ROWS.replace('Back', 'Front'), 1)
    present = present_log([older, newer])
    assert {entry for entry, _ in present} == {newer['text']} and len(present) == 2
    shown = default_log([older, newer])
    assert len(shown) == 2 and shown[0].startswith('[sys] Front room')


def test_p12_log_protected_danger_plus_two_speech_entries_are_all_whole():
    lines = [line('danger', 'The floor is live.', 0), speech(TWO_ROWS, 1), speech('Go.', 2)]
    rows = present_log(lines)
    for text in {entry for entry, _ in rows}:
        assert sum(1 for entry, _ in rows if entry == text) == len(chrome._entries(
            [next(l for l in lines if l['text'] == text)], 78)[0][1])


def test_p12_log_newest_entry_taller_than_the_log_shows_head_and_ctrl_p():
    tall = ' '.join(['word'] * 80)
    for rows in ([text for _, text in present_log([speech(tall, 0)])], default_log([line('system', tall, 0)])):
        assert len(rows) == 3 and rows[-1].endswith(LOG_CUT) and '…' not in ''.join(rows)


def test_p12_log_three_combat_lines_then_speech_keeps_the_speech():
    combat = [line('combat', f'A drone fires {i}.', i) for i in range(3)]
    rows = present_log([*combat, speech('Run.', 3)])
    assert [entry for entry, _ in rows] == ['A drone fires 1.', 'A drone fires 2.', 'Run.']
    rows = present_log([*combat, speech(TWO_ROWS, 3)])
    assert [entry for entry, _ in rows][:2] == ['A drone fires 1.', 'A drone fires 2.']
    assert rows[2][0] == TWO_ROWS and rows[2][1].endswith(LOG_CUT)


def test_p12_log_newest_protected_danger_wins_over_older_combat():
    tall = 'Move now. ' + ' '.join(['The vat line is venting into this corridor'] * 4)
    lines = [line('combat', 'A drone fires.', 0), line('danger', tall, 1)]
    assert len(chrome._entries(lines[1:], 78)[0][1]) == 3
    assert {entry for entry, _ in present_log(lines)} == {tall}


@pytest.mark.parametrize('presentation', RENDERERS)
def test_p12_log_renders_whole_entries_at_80x24(info, presentation):
    older = {'kind': 'speech', 'channel': 'zone', 'speaker': 'Dolf', 'text': TWO_ROWS}
    newer = {'kind': 'ambient', 'channel': 'zone', 'text': TWO_ROWS.replace('Back', 'Front')}
    body = {'kind': 'vendor', 'title': 'Stall', 'columns': ['Item'], 'cursor': 0,
            'rows': [{'id': 'coat', 'cells': ['Belt coat']}], 'detail': 'A coat.', 'actions': []}
    screen = render(info, (80, 24), presentation, body, [older, newer])
    log = compute(80, 24).log
    text = '\n'.join(screen[log.y:log.bottom])
    assert 'Front room' in text and 'Back room' not in text and 'quiet way' in text.replace('\n', ' ')
