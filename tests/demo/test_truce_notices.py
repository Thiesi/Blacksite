"""Demo round 3 (#170): the first-target notice and the HUNTED header word."""

from typing import Any

import pytest

from karst41.door.cells import display_width
from karst41.server.protocol import Frame
from tests.fake_terminal import FakeTerminal
from tests.presentation.test_client_foundations import content, display, zone_body  # noqa: F401

PLAYER = 'Fire: Marked 15m. No Halo, no work.'
NPC = 'Fire here and Sable comes. No Halo.'
HOSTILE = {'id': 'x', 'name': 'Somebody', 'relation': 'hostile', 'hp_percent': 100, 'range': 3, 'cover': 0}


def view(model: Any, body: dict[str, Any], rev: int, now: float) -> None:
    model.receive(Frame('view', {'rev': rev, 'kind': 'zone', 'body': body}), now)


def row_body(content: Any, width: int = 80, height: int = 24, **me: Any) -> dict[str, Any]:
    body = zone_body(content, width, height)
    body.update(hazards=[], event=None, target=None, hint='? help  Ctrl-X leaves')
    body['escape'] = {'routes': [], 'action': 'Ctrl-X leaves'}
    body['me'].update(zone_name='Sodium Row', safety='contested', truce='sable', **me)
    return body


def screen(model: Any, now: float) -> list[str]:
    terminal = FakeTerminal(model.layout.width, model.layout.height)
    model.force_full = True
    terminal.write(model.render(now)[0])
    return terminal.screen_text().splitlines()


@pytest.mark.parametrize('warning, text', [('Firing marks you', PLAYER), ('Truce: Sable answers', NPC),
                                           ('Sable answers', NPC)])
def test_first_target_shows_the_price_once_a_session(content: Any, warning: str, text: str) -> None:
    model = display(content, 80, 24)
    body = row_body(content)
    view(model, body, 1, 0)
    assert model.toast is None
    body['target'] = {**HOSTILE, 'relation': 'neutral', 'warning': warning}
    view(model, body, 2, 1)
    assert model.toast is not None and model.toast[0] == text
    model.toast = None
    view(model, body, 3, 2)
    assert model.toast is None


@pytest.mark.parametrize('text, warning', [(PLAYER, 'Firing marks you'), (NPC, 'Truce: Sable answers')])
def test_both_lines_fit_the_header_whole_at_80x24(content: Any, text: str, warning: str) -> None:
    model = display(content, 80, 24)
    body = row_body(content)
    body['target'] = {**HOSTILE, 'warning': warning}
    view(model, body, 1, 0)
    rows = screen(model, 1)
    assert text in rows[model.layout.header.y]
    assert display_width(rows[model.layout.header.y]) == 80


@pytest.mark.parametrize('warning, text', [('Firing marks you', PLAYER), ('Truce: Sable answers', NPC)])
def test_a_neutral_target_puts_the_notice_on_the_hint_line(content: Any, warning: str, text: str) -> None:
    model = display(content, 80, 24)
    body = row_body(content)
    body['target'] = {**HOSTILE, 'relation': 'neutral', 'warning': warning}
    view(model, body, 1, 0)
    assert text in screen(model, 1)[model.layout.hint.y]


@pytest.mark.parametrize('target, truce', [
    ({**HOSTILE, 'warning': 'Firing marks you'}, False),  # A Mark outside a truce zone keeps today's panel only.
    ({**HOSTILE, 'warning': 'Protected'}, True),
    ({**HOSTILE, 'warning': ''}, True),
    (None, True),
])
def test_no_notice_without_a_truce_warning(content: Any, target: dict[str, Any] | None, truce: bool) -> None:
    model = display(content, 80, 24)
    body = row_body(content)
    body['target'] = target
    if not truce:
        del body['me']['truce']
    view(model, body, 1, 0)
    assert model.toast is None and not model.truce_notice_shown


def test_any_key_still_acts_while_the_notice_is_up(content: Any) -> None:
    model = display(content, 80, 24)
    body = row_body(content)
    body['target'] = {**HOSTILE, 'warning': 'Firing marks you'}
    view(model, body, 1, 0)
    assert [frame.data['k'] for frame in model.key('f', 1) if frame.type == 'key'] == ['f']


def test_hunted_shows_only_from_the_declared_field(content: Any) -> None:
    model = display(content, 80, 24)
    view(model, row_body(content), 1, 0)
    assert 'HUNTED' not in screen(model, 1)[model.layout.header.y]
    view(model, row_body(content, hunted=True, marked_until='2030-01-01T00:00:00+00:00'), 2, 2)
    header = screen(model, 3)[model.layout.header.y]
    assert 'HUNTED' in header and 'MARKED' in header and display_width(header) == 80
