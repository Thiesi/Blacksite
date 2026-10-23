"""UI 11: truthful cards, stale actions and compact journal rendering."""

from dataclasses import asdict

import pytest

from blacksite.content.schema import EvidenceRecord, ObjectSpec, StageTarget
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.contracts.panels import Panel
from blacksite.server.protocol import Frame
from blacksite.server.world.zone import ObjectState
from tests.contracts.test_adapter import live, shipped
from tests.fake_terminal import FakeTerminal


def board(live):
    game, owner, callers, players = live
    session = callers[0].session
    actor = game.core.combat.actor(players[0])
    spec = ObjectSpec('fixture-board', actor.position, 'terminal', params={'contract_handler': 'wardens'})
    owner.world.zones[actor.zone].objects[spec.id] = ObjectState(spec)
    panel = Panel(game.clock.now_tick(), spec.id, 'wardens')
    owner.panels.menus[session.id] = panel
    return session, panel


def test_ui_11_board_cancel_and_stale_selection_cannot_accept_a_different_job(live) -> None:
    game, owner, callers, players = live
    session, panel = board(live)
    body = owner.panels.body(session, panel)
    selected = body['rows'][0]['id']
    stale = Frame('intent', {'name': 'menu_select', 'args': {'row': selected, 'key': 'a'},
        'request_id': 'stale', 'expected_revision': session.view_revision-1})
    assert owner.input(session, stale, game.clock.now_tick())
    assert not owner.proposals and not owner.state.engine.instances
    owner.panels.act(session, panel, 'a', selected)
    assert panel.confirmation and len(owner.proposals) == 1
    assert owner.input(session, Frame('key', {'k': 'escape', 't': 0}), game.clock.now_tick())
    assert not panel.confirmation and not owner.proposals
    assert not owner.state.engine.instances and not owner.commerce.pending


def test_ui_11_confirmed_card_stays_bound_to_selected_proposal_when_rows_change(live) -> None:
    game, owner, callers, players = live
    session, panel = board(live)
    offer = owner.state.engine.board('wardens', owner.now())[0]
    older = owner.propose(players[0].id, offer, (players[0].id,))
    owner.panels.act(session, panel, 'a', offer.id)
    target = panel.confirmation[1]
    assert target != older.id
    assert owner.panels.body(session, panel)['detail'].startswith('Commit start?')
    owner.panels.act(session, panel, 'y', older.id)
    game.commit_commerce()
    assert target not in owner.proposals and older.id in owner.proposals


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_11_journal_acquisition_fields_are_readable_with_wide_names(live, tmp_path, size) -> None:
    game, owner, callers, players = live
    session = callers[0].session
    session.caps.update(width=size[0], height=size[1])
    record = EvidenceRecord('journal', 'optional', 'You compare the two crate IDs.',
        'A signed manifest', 'The goods go to reserve.', question='Who changed the route?',
        next_action='Bring the manifest to the handler.')
    owner.state.acquire(players[0].id, record, StageTarget('zone_object', zone=players[0].zone, object='crate'), owner.now())
    panel = Panel(game.clock.now_tick(), tab='journal')
    body = owner.panels.body(session, panel)
    info = DoorInfo(tmp_path/'door_info.json', tmp_path,
                    {'user_id': 1, 'handle': 'Wide\u754c', 'node_name': 'fixture'}, *size, '16', 3600)
    display = Display(info)
    display.receive(Frame('welcome', {'keymap': asdict(owner.content.keymaps), 'palette': asdict(owner.content.palette)}), 0)
    display.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': body}), 1)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(1)[0])
    text = terminal.screen_text()
    for label in ('Observed:', 'Source says:', 'Open question:', 'Next action:'):
        assert label in text
    assert 'Esc/B back' in text


def test_ui_11_empty_journal_has_selectable_row_so_client_can_return_to_jobs(live) -> None:
    game, owner, callers, players = live
    session = callers[0].session
    panel = Panel(0, tab='journal')
    body = owner.panels.body(session, panel)
    assert body['rows'] and 'j' in {a['key'] for a in body['actions']}
    owner.panels.act(session, panel, 'j', '')
    assert panel.tab == 'jobs'


def test_ui_11_contract_social_overlay_preserves_crew_and_chat_panels(live) -> None:
    game, owner, callers, players = live
    session = callers[0].session
    assert not owner.lat.social_overlay(session)
    owner.panels.menus[session.id] = Panel(0)
    assert owner.lat.social_overlay(session)
    owner.panels.close(session)
    from blacksite.server.crew_engine import CrewMenu
    game.core.crews.menus[session.id] = CrewMenu(0, 0)
    assert owner.lat.social_overlay(session)
