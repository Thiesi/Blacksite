"""UI 4/game 12: real Display keys, chart receipts and bounded wide text."""

from dataclasses import asdict, replace
from copy import deepcopy
from typing import Any

import pytest

from blacksite.content.schema import EventTemplate
from blacksite.door.model import Display
from blacksite.server.commerce import CommerceMenu
from blacksite.server.items import make_item
from blacksite.server.market_views import Panel as ServicesPanel
from blacksite.server.protocol import Frame, encode
from blacksite.server.rules.events import SCHEDULES
from tests.character_helpers import act, place
from tests.fake_terminal import FakeTerminal
from tests.server.test_event_engine import base_content, events_game, force
from tests.server.test_event_retention import archived_game


def display_for(info: Any, game: Any, size: tuple[int, int]) -> Any:
    display = Display(replace(info, width=size[0], height=size[1], color_depth='16'))
    display.receive(Frame('welcome', {'keymap': asdict(game.core.loop.content.keymaps),
        'palette': asdict(game.core.loop.content.palette)}), 0)
    return display


def render(display: Any, body: dict[str, Any], kind: str, size: tuple[int, int], rev: int = 1) -> str:
    now = max(1, display.last_render + 1)
    frame = Frame('view', {'rev': rev, 'kind': kind, 'body': body})
    encode(frame)
    display.receive(frame, now)
    terminal = FakeTerminal(*size)
    terminal.write(display.render(now)[0])
    assert terminal.cell(size[0]-1, size[1]-1) == ' '
    return terminal.screen_text()


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_4_services_v_real_client_read_and_back(info: Any, events_game: tuple[Any, ...], size: tuple[int, int]) -> None:
    game, caller, player = events_game
    force(game, 'curfew')
    terminal = next(obj for obj in game.core.world.zones['vatside-wake-hall'].objects.values()
                    if obj.spec.kind == 'terminal')
    place(game, caller, 'vatside-wake-hall',
          game.core.world.free_tile('vatside-wake-hall', terminal.spec.tile))
    source = game.core.market.views
    source.menus[caller.session.id] = ServicesPanel('terminal', terminal.spec.id, game.clock.now_tick())
    display = display_for(info, game, size)
    render(display, source.body(caller.session, source.menus[caller.session.id]),
           'menu', size, caller.session.view_revision)
    frames = display.key('v', 1)
    assert len(frames) == 1 and frames[0].data['args']['key'] == 'v'
    act(game, caller, frames[0])
    owner = game.core.events.views
    panel = owner.menus[caller.session.id]
    assert caller.session.id not in source.menus
    before = player.chits_hand, player.chits_bank, list(player.inventory)
    text = render(display, owner.body(caller.session, panel), 'menu', size, caller.session.view_revision)
    assert 'Curfew' in text and 'FORECASTS' in text
    frames = display.key('r', 2)
    assert len(frames) == 1
    act(game, caller, frames[0])
    game.commit_commerce()
    assert panel.selected and panel.selected in player.progress['event_forecasts']
    for _ in range(2):
        render(display, owner.body(caller.session, panel), 'menu', size, caller.session.view_revision)
        act(game, caller, display.key('b', 3)[0])
    assert caller.session.id not in owner.menus
    assert (player.chits_hand, player.chits_bank, player.inventory) == before


def ring_plan(game: Any) -> Any:
    owner = game.core.events
    template = EventTemplate('ring-fall', 'Ring-fall', ('vatside-clinics',), *SCHEDULES['ring-fall'], selection='one')
    owner.content.events[template.id] = template
    draft = owner.scheduler.fork()
    plan = draft.reserve(template, owner.now(), 42, owner.eligible)
    owner.effects.allocate(draft, plan)
    owner.jobs.allocate(draft, plan)
    assert owner.write(draft, [])
    game.commit_commerce()
    return owner.scheduler.plans[plan.id]


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_game_12_carried_chart_use_saves_actual_forecast_without_consuming_item(info: Any, events_game: tuple[Any, ...], size: tuple[int, int]) -> None:
    game, caller, player = events_game
    plan = ring_plan(game)
    owner = game.core.events
    assert owner.place(plan.where[0]) not in owner.text(plan, detailed=False)
    iid = f'{game.core.sessions.origin}:item:{game.core.combat.next_serial()+1}'
    chart = make_item(iid, owner.content.items['key_ringfall_chart'], player.id, owner.clock.now_utc().isoformat())
    game.core.commerce.items[iid] = chart
    player.inventory.append(iid)
    inventory = CommerceMenu('inventory', opened=game.clock.now_tick())
    game.core.commerce.menus[caller.session.id] = inventory
    rows = game.core.commerce.body(caller.session, inventory)['rows']
    inventory.cursor = next(index for index, row in enumerate(rows) if row['id'] == iid)
    display = display_for(info, game, size)
    render(display, game.core.commerce.body(caller.session, inventory), 'menu', size, caller.session.view_revision)
    before = player.chits_hand, player.chits_bank, chart.record()
    frames = display.key('u', 1)
    assert len(frames) == 1
    act(game, caller, frames[0])
    game.commit_commerce()
    panel = owner.views.menus[caller.session.id]
    assert panel.chart and panel.selected == plan.id
    assert player.progress['event_forecasts'][plan.id]['revision'] == plan.revision
    assert (player.chits_hand, player.chits_bank, game.core.commerce.items[iid].record()) == before
    assert owner.place(plan.where[0]) in player.progress['event_forecasts'][plan.id]['text']
    owner.admin('event.cancel', {'plan': plan.id}, lambda result: None)
    game.step()
    game.commit_commerce()
    body = owner.views.body(caller.session, panel)
    assert 'Your forecast changes' in body['detail'] and 'cancelled' in body['detail']
    render(display, body, 'menu', size, caller.session.view_revision)


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_2_two_events_keep_target_and_ally_health_visible(info: Any, events_game: tuple[Any, ...], size: tuple[int, int]) -> None:
    game, caller, player = events_game
    game.step()
    body = game.core.characters.sim.views[caller.session.id].previous['body']
    body['event'] = {'plans': [{'summary': 'Curfew 20m'}, {'summary': 'Choir Surge 10m'}]}
    body['hazards'] = [{'warning': 5, 'escape': ['west']}]
    body['target'] = {'id': 'fixture-target', 'name': 'Target界', 'faction': 'Freelance',
        'hp_percent': 73, 'range': 2, 'cover': 0, 'relation': 'hostile'}
    body['crew'] = [{'id': player.id, 'name': player.name, 'hp_pct': 100, 'zone': 'here'},
        {'id': 'fixture-ally', 'name': 'Ally界', 'hp_pct': 64, 'zone': 'here'}]
    display = display_for(info, game, size)
    text = render(display, body, 'zone', size)
    assert all(value in text for value in ('Curfew', 'Choir Surge', 'Target', '73%', 'Ally', '64%', '5s'))


@pytest.mark.parametrize('size', [(80,24),(132,50)])
def test_game_12_held_cancellation_survives_hot_history_retirement_and_restart(info: Any, archived_game: tuple[Any, ...], size: tuple[int,int]) -> None:
    game,caller,player,pid = archived_game
    owner = game.core.events
    owner.views.open(caller.session)
    panel = owner.views.menus[caller.session.id]
    display = display_for(info,game,size)
    render(display,owner.views.body(caller.session,panel),'menu',size,caller.session.view_revision)
    act(game,caller,display.key('h',2)[0])
    body = owner.views.body(caller.session,panel)
    assert body['rows'][0]['id'] == pid
    assert 'cancelled' in body['detail'] and 'Your forecast changes' in body['detail']
    text = render(display,body,'menu',size,caller.session.view_revision)
    assert 'cancelled' in text and 'RECENT FORECASTS' in text
    before = deepcopy(player.progress['event_forecasts'][pid])
    act(game,caller,display.key('r',3)[0])
    game.commit_commerce(error=True)
    assert player.progress['event_forecasts'][pid] == before
    render(display,owner.views.body(caller.session,panel),'menu',size,caller.session.view_revision)
    act(game,caller,display.key('r',4)[0])
    game.commit_commerce()
    assert player.progress['event_forecasts'][pid]['revision'] == before['final']['revision']
    assert 'Your forecast changes' not in owner.views.body(caller.session,panel)['detail']
