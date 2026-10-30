"""UI 2.5 / P5: notice lifetime, priority, history and override resilience."""

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import pytest

from blacksite.content.loader import load_content
from blacksite.door import chrome as shared_chrome
from blacksite.door.cells import display_width
from blacksite.door.model import Display
from blacksite.door.palette import Color
from blacksite.door.present import chrome, paint as paint_module
from blacksite.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.presentation.test_client_foundations import content, display, zone_body, SIZES, TIERS  # noqa: F401


def render(model: Display, now: float, terminal: FakeTerminal | None = None) -> FakeTerminal:
    terminal = terminal or FakeTerminal(model.layout.width, model.layout.height)
    terminal.write(model.render(now)[0])
    return terminal


def send_notice(model: Display, now: float = 1, seconds: float = 1, text: str = 'Maintenance soon.') -> None:
    model.receive(Frame('toast', {'text': text, 'role': 'ui_text', 'seconds': seconds}), now)


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('tier', TIERS)
def test_ui_2_5_notice_uses_p3_priority_and_keeps_escape_and_world_log(content: Any, size: tuple[int, int], tier: str) -> None:
    width, height = size
    model = display(content, width, height, tier)
    body = zone_body(content, width, height)
    body.update(target=None, hazards=[], event=None, hint='E use counter  ? help  Ctrl-X leave')
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    model.receive(Frame('log', {'lines': [{'kind': 'system', 'text': 'A world line.'}]}), 0)
    term = render(model, 0)
    previous_log = term.screen_text().splitlines()[model.layout.log.y:model.layout.log.bottom]
    text = 'Maintenance界 soon. ' * 12
    send_notice(model, text=text)
    term = render(model, 1, term)
    rows = term.screen_text().splitlines()
    escape = body['escape']['action']
    expected = shared_chrome.focus_hint(text, model.layout.hint.width, [],
                                       fit_all=True, primary=True, escape=escape)
    assert rows[model.layout.hint.y][1:-1].rstrip() == expected
    assert escape in rows[model.layout.hint.y] and 'E use counter' not in rows[model.layout.hint.y]
    assert display_width(rows[model.layout.hint.y]) == width
    assert rows[model.layout.log.y:model.layout.log.bottom] == previous_log
    assert set(rows[model.layout.separator.y]) <= set('─┴╟╢├┤')
    assert not chrome.digest([line for line in model.logs if line['kind'] == 'notice'])


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('reason', ['hazard', 'danger', 'combat', 'hostile', 'line_prompt',
                                   'key_prompt', 'exit_prompt', 'channel'])
def test_ui_2_5_notice_moves_to_header_for_declared_threat_or_input_then_returns(content: Any, size: tuple[int, int], reason: str) -> None:
    width, height = size
    model = display(content, width, height)
    body = zone_body(content, width, height)
    body.update(target=None, hazards=[], event=None, hint='? help  Ctrl-X leave')
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    send_notice(model, seconds=30)
    term = render(model, 1)
    assert 'Maintenance soon.' in term.screen_text().splitlines()[model.layout.hint.y]
    if reason == 'hazard':
        body['hazards'] = [{'tiles': [], 'warning': 3}]
    elif reason in ('danger', 'combat'):
        model.receive(Frame('log', {'lines': [{'kind': reason, 'text': 'Declared threat.'}]}), 2)
    elif reason == 'hostile':
        body['target'] = {'id': 'patrol', 'name': 'Patrol', 'relation': 'hostile', 'range': 2, 'hp_percent': 100}
    elif reason in ('line_prompt', 'key_prompt'):
        model.receive(Frame('prompt', {'kind': 'line' if reason == 'line_prompt' else 'key',
                                      'id': 'answer', 'label': 'Answer', 'max_len': 24}), 2)
    elif reason == 'exit_prompt':
        model.key('ctrl-x', 2)
    elif reason == 'channel':
        body['me']['channel'] = 'zone'
        body['hint'] = 'Say: draft text  Esc cancels'
    model.receive(Frame('view', {'rev': 2, 'kind': 'zone', 'body': body}), 2)
    term = render(model, 2, term)
    rows = term.screen_text().splitlines()
    assert 'Maintenance soon.' in rows[model.layout.header.y]
    assert 'Maintenance soon.' not in rows[model.layout.hint.y]
    assert rows[model.layout.header.y][:model.layout.header.right].endswith('Maintenance soon.')
    assert rows[model.layout.header.y].endswith('╗')
    if reason in ('line_prompt', 'key_prompt'):
        assert 'Answer' in rows[model.layout.hint.y]
    elif reason == 'exit_prompt':
        assert 'Leave Karst?' in rows[model.layout.hint.y]
    elif reason == 'channel':
        assert body['hint'] in rows[model.layout.hint.y]
    body.update(target=None, hazards=[])
    body['me'].pop('channel', None)
    body['hint'] = '? help  Ctrl-X leave'
    model.prompt = model.key_prompt = None
    model.confirm_exit = False
    model.receive(Frame('view', {'rev': 3, 'kind': 'zone', 'body': body}), 3)
    term = render(model, 3, term)
    if reason in ('danger', 'combat'):
        assert 'Maintenance soon.' in term.screen_text().splitlines()[model.layout.header.y]
        model.update(12.1, 12.1)  # Only the injected clock makes the line unprotected.
        term = render(model, 12.1, term)
    rows = term.screen_text().splitlines()
    assert 'Maintenance soon.' in rows[model.layout.hint.y]
    assert 'Maintenance soon.' not in rows[model.layout.header.y]


@pytest.mark.parametrize('key_at', [2, 10, None])
def test_ui_2_5_notice_requires_eight_seconds_and_a_key_after_arrival(content: Any, key_at: float | None) -> None:
    model = display(content)
    send_notice(model, now=1)
    if key_at == 2:
        model.key('ctrl-l', key_at)
    model.update(chrome.NOTICE_SECONDS - .01, 1 + chrome.NOTICE_SECONDS - .01)
    assert model.toast is not None
    model.update(1 + chrome.NOTICE_SECONDS, 1 + chrome.NOTICE_SECONDS)
    assert (model.toast is None) == (key_at == 2)
    if key_at == 10:
        model.key('ctrl-l', key_at)
        assert model.toast is None
    elif key_at is None:
        model.update(200, 200)
        assert model.toast is not None


def test_ui_2_5_new_notice_resets_the_key_and_appears_once_in_scrollback(content: Any) -> None:
    model = display(content)
    send_notice(model, now=0, text='First notice.')
    model.key('ctrl-l', 1)
    send_notice(model, now=2, text='Second notice.')
    model.update(11, 11)
    assert model.toast is not None
    notices = [line for line in model.logs if line.get('kind') == 'notice']
    assert [line['text'] for line in notices] == ['First notice.', 'Second notice.']
    model.key('ctrl-p', 11)
    assert model.toast is None
    term = render(model, 11)
    assert term.screen_text().count('First notice.') == 1
    assert term.screen_text().count('Second notice.') == 1
    assert 'SCROLLBACK' in term.screen_text()


@pytest.mark.parametrize('size', SIZES)
def test_ui_2_5_long_header_notice_keeps_safety_threats_and_frame(content: Any, size: tuple[int, int]) -> None:
    model = display(content, *size)
    body = zone_body(content, *size)
    body['me'].update(safety='contested', heat_until=10, marked_until=10)
    body['hazards'] = [{'tiles': []}]
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    send_notice(model, text='Maintenance界 ' * 30)
    term = render(model, 1)
    header = term.screen_text().splitlines()[model.layout.header.y]
    assert all(word in header for word in ('CONTESTED', 'PvP G5+', 'HEAT', 'MARKED', 'Maintenance'))
    assert display_width(header) == size[0] and header.startswith('┌') and header.endswith('┐')


def test_ui_2_5_legacy_notice_keeps_its_timeout_log_and_separator_surface(content: Any) -> None:
    model = display(content, enabled=False)
    send_notice(model, seconds=1)
    assert not model.logs
    term = render(model, 1)
    assert 'Maintenance soon.' in term.screen_text().splitlines()[model.layout.separator.y]
    model.update(2, 2)
    assert model.toast is None  # No key needed; the new floor is opt-in.


@pytest.mark.parametrize('tier', ['256', 'truecolor'])
@pytest.mark.parametrize('unreachable', ['people', 'jacked'])
def test_p5_tr_3_local_palette_with_unreachable_floors_renders_and_caches(
        content: Any, tier: str, unreachable: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = asdict(content.palette)
    for role, values in data['roles'].items():
        affected = role.startswith('thing_') if unreachable == 'people' else role == 'wall_face'
        if affected:
            for variant in ('default', 'deutan', 'protan'):
                values[tier][variant] = '#FFFFFF' if tier == 'truecolor' else 231
    (tmp_path / 'palette.json').write_text(json.dumps(data), encoding='utf-8')
    override = load_content(content.root, tmp_path)
    model = display(override, tier=tier)
    body = zone_body(content)
    if unreachable == 'jacked':
        body['actors'][0]['jacked'] = True
    fallbacks: list[Color] = []
    fallback = paint_module._unreachable
    def record(colour: Color) -> Color:
        fallbacks.append(colour)
        return fallback(colour)
    monkeypatch.setattr(paint_module, '_unreachable', record)
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    term = render(model, 1)
    assert fallbacks and 'HP' in term.screen_text()
    count = len(fallbacks)
    model.key('ctrl-l', 2)
    render(model, 2, term)
    assert len(fallbacks) == count


def test_ui_2_5_safety_and_ordinary_log_words_do_not_infer_a_threat(content: Any) -> None:
    model = display(content)
    body = zone_body(content)
    body['me']['safety'] = 'open'
    body.update(target=None, hazards=[])
    model.receive(Frame('view', {'rev': 1, 'kind': 'zone', 'body': body}), 0)
    model.receive(Frame('log', {'lines': [{'kind': 'system', 'text': 'Combat and danger are words.'}]}), 0)
    send_notice(model)
    term = render(model, 1)
    rows = term.screen_text().splitlines()
    assert 'Maintenance soon.' in rows[model.layout.hint.y]
    assert 'Maintenance soon.' not in rows[model.layout.header.y]


def test_ui_2_5_session_warning_uses_the_same_notice_surface_once(content: Any) -> None:
    model = display(content)
    model.update(3300, 5)
    term = render(model, 5)
    rows = term.screen_text().splitlines()
    assert '5 minute' in rows[model.layout.hint.y]
    assert not any('5 minute' in row for row in rows[model.layout.log.y:model.layout.log.bottom])
    model.update(3301, 14)
    assert model.toast is not None
    model.key('ctrl-l', 14)
    assert model.toast is None
    assert len([line for line in model.logs if line.get('kind') == 'notice']) == 1


@pytest.mark.parametrize('size', SIZES)
@pytest.mark.parametrize('kind', ['menu', 'text', 'local'])
def test_ui_2_5_notice_keeps_existing_back_action_on_every_local_or_server_view(
        content: Any, size: tuple[int, int], kind: str) -> None:
    model = display(content, *size)
    body = {'title': 'Report', 'lines': ['You read.'], 'rows': [], 'hint': 'Enter selects  Esc/B leaves'}
    model.receive(Frame('view', {'rev': 1, 'kind': 'menu' if kind == 'menu' else 'text', 'body': body}), 0)
    if kind == 'local':
        model.open_help(['You read a note.'])
    send_notice(model)
    term = render(model, 1)
    hint = term.screen_text().splitlines()[model.layout.hint.y]
    assert all(text in hint for text in ('Maintenance soon.', 'Esc/B leaves', 'Ctrl-X leave'))
