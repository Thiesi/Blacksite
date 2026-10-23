"""UI 11: truthful cards, stale actions and compact journal rendering."""

from dataclasses import asdict, replace
from typing import Any

import pytest

from blacksite.content.schema import EvidenceRecord, ObjectSpec, StageTarget
from blacksite.door.doorinfo import DoorInfo
from blacksite.door.model import Display
from blacksite.server.contracts.panels import Panel
from blacksite.server.protocol import Frame
from blacksite.server.world.zone import ObjectState
from tests.contracts.test_adapter import live, shipped
from tests.fake_terminal import FakeTerminal
from tests.contracts.test_adapter import accept, complete
from tests.contracts.test_engine import template


def board(live):
    game, owner, callers, players = live
    session = callers[0].session
    actor = game.core.combat.actor(players[0])
    spec = ObjectSpec('fixture-board', actor.position, 'terminal', params={'contract_handler': 'wardens'})
    owner.world.zones[actor.zone].objects[spec.id] = ObjectState(spec)
    panel = Panel(game.clock.now_tick(), spec.id, 'wardens')
    owner.panels.menus[session.id] = panel
    return session, panel


def test_game_9_1_vesper_turns_in_generated_faction_commission_without_changing_standing_giver(live):
    game,owner,callers,players=live
    iid=accept(live)
    complete(live,iid)
    session,panel=board(live)
    obj=owner.world.zones[game.core.combat.actor(players[0]).zone].objects[panel.target]
    obj.spec.params['contract_handler']='vesper'
    panel.handler='vesper'
    assert any(a['key']=='t' for a in owner.panels.card(session,panel,iid)[1])
    owner.panels.act(session,panel,'t',iid)
    assert panel.confirmation == ('turn-in',iid,'')
    owner.panels.act(session,panel,'y',iid)
    game.commit_commerce()
    assert owner.state.engine.instances[iid].giver == 'wardens'
    assert owner.state.engine.instances[iid].state == 'turned_in'


def test_ui_11_fixed_branch_consent_hides_other_solo_offer_but_keeps_accepted_job(live):
    game,owner,callers,players=live
    for branch in ('clinic','shield'):
        job=replace(template('fixture-'+branch),story=True,branch_group='fixture-walked',branch=branch)
        owner.content.contracts[job.id]=owner.state.engine.templates[job.id]=job
    draft=owner.state.fork()
    accepted=draft.engine.accept(draft.engine.story_offer('fixture-clinic',players[0].id),
                                 (owner.participant(players[0].id),),owner.now())
    owner.write(draft)
    game.commit_commerce()
    session,panel=board(live)
    rows=owner.panels.rows(session,panel)
    assert accepted.id in {row['id'] for row in rows}
    assert 'fixture-shield' not in {row['id'] for row in rows}


def test_ui_11_abandoned_job_remains_visible_and_original_workers_resume_with_frozen_terms(live: tuple[Any, ...]) -> None:
    game, owner, callers, players = live
    iid = accept(live)
    draft = owner.state.fork()
    for player in players[:2]:
        owner.withdraw(draft, iid, player.id)
    owner.write(draft)
    game.commit_commerce()
    original = owner.state.engine.instances[iid]
    roster, reward = original.roster, original.reward
    panel = Panel(game.clock.now_tick())
    assert any(row['id'] == iid and row['cells'][0] == 'withdrawn'
               for row in owner.panels.rows(callers[0].session, panel))
    assert any(a['key'] == 'r' for a in owner.panels.card(callers[0].session, panel, iid)[1])
    owner.panels.act(callers[0].session, panel, 'r', iid)
    owner.panels.act(callers[0].session, panel, 'y', iid)
    game.commit_commerce(error=True)
    assert owner.state.engine.instances[iid].withdrawn == {p.id for p in players[:2]}
    owner.panels.act(callers[0].session, panel, 'r', iid)
    owner.panels.act(callers[0].session, panel, 'y', iid)
    game.commit_commerce()
    attempt = owner.state.engine.instances[iid].stages[0].attempt
    other = Panel(game.clock.now_tick())
    owner.panels.act(callers[1].session, other, 'r', iid)
    owner.panels.act(callers[1].session, other, 'y', iid)
    game.commit_commerce()
    resumed = owner.state.engine.instances[iid]
    assert not resumed.withdrawn and resumed.state == 'active'
    assert resumed.stages[0].attempt == attempt
    assert resumed.roster == roster and resumed.reward == reward


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
