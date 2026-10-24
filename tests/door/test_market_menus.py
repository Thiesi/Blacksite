"""UI 4 and game 8.3: real server menus and cell-buffer display."""

import json
from dataclasses import asdict
from typing import Any

import pytest

from blacksite.server.commerce import CommerceMenu
from blacksite.door.model import Display
from blacksite.server.market_views import Panel
from blacksite.server.protocol import Frame, ProtocolError, encode
from tests.character_helpers import act, place
from tests.door.test_relay_menus import render
from tests.server.test_market_engine import content, listed, trade_game


def choose(game: Any, caller: Any, key: str, row: str | None = None) -> None:
    owner = game.core.market
    panel = owner.views.menus[caller.session.id]
    rows = owner.views.rows(caller.session, panel)
    if row is not None:
        wanted = next(i for i, value in enumerate(rows) if value['id'] == row)
        act(game, caller, Frame('intent', {'name': 'menu_cursor', 'args': {'delta': wanted-panel.cursor}}))
        rows = owner.views.rows(caller.session, panel)
    selected = rows[min(panel.cursor, len(rows)-1)]['id'] if rows else ''
    act(game, caller, Frame('intent', {'name': 'menu_select', 'args': {'row': selected, 'key': key}}))


def open_market(game: Any, caller: Any) -> None:
    act(game, caller, Frame('intent', {'name': 'market.open', 'args': {}}))


def test_ui_4_real_client_hotkeys_open_empty_market_list_and_confirm(info: Any, trade_game: tuple[Any, ...]) -> None:
    game, clients, _, iid, terminal = trade_game
    caller, owner = clients[0], game.core.market
    panel = Panel('terminal', terminal, 0)
    owner.views.menus[caller.session.id] = panel
    display = Display(info)
    display.receive(Frame('welcome', {'keymap': asdict(owner.commerce.content.keymaps),
                                     'palette': asdict(owner.commerce.content.palette)}), 0)
    def press(key: str) -> None:
        display.receive(Frame('view', {'rev': caller.session.view_revision, 'kind': 'menu',
            'body': owner.views.body(caller.session, panel)}), 1)
        frames = display.key(key, 1)
        assert len(frames) == 1, (panel.kind, key)
        act(game, caller, frames[0])
    press('m')
    assert panel.kind == 'market' and not owner.views.rows(caller.session, panel)
    press('l')
    assert panel.kind == 'items'
    wanted = next(i for i, row in enumerate(owner.views.rows(caller.session, panel)) if row['id'] == iid)
    while panel.cursor < wanted:
        press('down')
    press('enter')
    token, _ = owner.views.prompts[caller.session.id]
    act(game, caller, Frame('line', {'id': token, 'text': '50'}))
    token, _ = owner.views.prompts[caller.session.id]
    act(game, caller, Frame('line', {'id': token, 'text': '100'}))
    press('enter')
    assert panel.confirmation and not owner.market.listings
    press('y')
    game.commit_commerce()
    assert len(owner.market.listings) == 1


def test_ui_4_real_client_bank_c_and_empty_bounty_post_are_advertised(info: Any, trade_game: tuple[Any, ...]) -> None:
    game, clients, _, _, terminal = trade_game
    caller, owner = clients[0], game.core.market
    display = Display(info)
    display.receive(Frame('welcome', {'keymap': asdict(owner.commerce.content.keymaps),
                                     'palette': asdict(owner.commerce.content.palette)}), 0)
    body = owner.views.body(caller.session, Panel('bounties', terminal, 0))
    display.receive(Frame('view', {'rev': 1, 'kind': 'menu', 'body': body}), 1)
    assert display.key('p', 1)[0].data['args'] == {'row': '', 'key': 'p'}
    zone = game.core.world.zones['vatside-clinics']
    bank = next(o.spec for o in zone.objects.values() if o.spec.kind == 'bank')
    place(game, caller, zone.id, game.core.world.free_tile(zone.id, bank.tile))
    screen = CommerceMenu('bank', bank.id, opened=game.clock.now_tick())
    game.core.commerce.menus[caller.session.id] = screen
    display.receive(Frame('view', {'rev': caller.session.view_revision, 'kind': 'menu',
        'body': game.core.commerce.body(caller.session, screen)}), 1)
    frames = display.key('c', 1)
    assert len(frames) == 1
    act(game, caller, frames[0])
    assert owner.views.menus[caller.session.id].kind == 'collect'


def test_ui_4_long_lived_market_history_pages_without_oversized_frames(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, terminal = trade_game
    owner, caller = game.core.market, clients[0]
    for index in range(3000):
        listing = owner.market.list_item(players[0].id, iid, 50, 100, 86400, index*2)
        listing.item_snapshot = owner.commerce.items[iid].record()
        owner.market.cancel(listing.id, players[0].id, index*2+1)
    panel = Panel('market', terminal, 0, mine=True)
    owner.views.menus[caller.session.id] = panel
    rows = owner.views.rows(caller.session, panel)
    # This was a real caller disconnect after sufficient accumulated history.
    with pytest.raises(ProtocolError):
        encode(Frame('view', {'rev': 1, 'kind': 'menu', 'body': {'rows': rows}}))
    body = owner.views.body(caller.session, panel)
    assert len(body['rows']) == 12 and body['pages'] == 250
    assert len(encode(Frame('view', {'rev': 1, 'kind': 'menu', 'body': body}))) < 10000
    act(game, caller, Frame('intent', {'name': 'menu_cursor', 'args': {'delta': 12}}))
    body = owner.views.body(caller.session, panel)
    assert body['page'] == 2 and body['cursor'] == 0
    assert body['rows'][0]['id'] == rows[12]['id']
    choose(game, caller, 'u')
    assert panel.confirmation[1]['listing'] == rows[12]['id']
    replies = []
    owner.admin('market.list', {'page': 2}, replies.append)
    result = replies[0]
    assert result['page'] == 2 and result['pages'] == 30 and result['total'] == 3000
    assert len(result['listings']) == 100 and result['bids'] == []
    assert result['listings'][0]['id'] == list(owner.market.listings)[100]
    response = {'title': 'admin.market.list', 'lines': [json.dumps(result)]}
    assert len(encode(Frame('view', {'rev': 1, 'kind': 'text', 'body': response}))) < 256*1024


def test_ui_4_price_prompts_survive_views_and_commit_only_after_y(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, _ = trade_game
    caller, owner = clients[0], game.core.market
    open_market(game, caller)
    choose(game, caller, 'l')
    choose(game, caller, 'enter', iid)
    token, field = owner.views.prompts[caller.session.id]
    assert field == 'price'
    assert owner.views.body(caller.session, owner.views.menus[caller.session.id])['clear_prompt'] is False
    act(game, caller, Frame('line', {'id': token, 'text': '50'}))
    token, field = owner.views.prompts[caller.session.id]
    assert field == 'buyout'
    assert owner.views.body(caller.session, owner.views.menus[caller.session.id])['clear_prompt'] is False
    act(game, caller, Frame('line', {'id': token, 'text': '100'}))
    choose(game, caller, 'enter', '86400')
    assert not game.core.commerce.pending and not owner.market.listings
    choose(game, caller, 'y')
    assert game.core.commerce.pending and iid in players[0].inventory
    game.commit_commerce()
    assert iid not in players[0].inventory and len(owner.market.listings) == 1


def test_ui_4_escape_from_price_prompt_keeps_item(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, iid, _ = trade_game
    caller, owner = clients[0], game.core.market
    open_market(game, caller)
    choose(game, caller, 'l')
    choose(game, caller, 'enter', iid)
    act(game, caller, Frame('intent', {'name': 'prompt_cancel', 'args': {}}))
    assert caller.session.id not in owner.views.menus and caller.session.id not in owner.views.prompts
    assert iid in players[0].inventory and not game.core.commerce.pending


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_4_listing_confirmation_explains_tiny_sale_net(info: Any, trade_game: tuple[Any, ...], size: tuple[int, int]) -> None:
    game, clients, _, iid, _ = trade_game
    caller, owner = clients[0], game.core.market
    open_market(game, caller)
    choose(game, caller, 'l')
    choose(game, caller, 'enter', iid)
    token, _ = owner.views.prompts[caller.session.id]
    act(game, caller, Frame('line', {'id': token, 'text': '1'}))
    token, _ = owner.views.prompts[caller.session.id]
    act(game, caller, Frame('line', {'id': token, 'text': '20'}))
    choose(game, caller, 'enter', '86400')
    text = render(info, size, owner.commerce.content, owner.views.body(caller.session, owner.views.menus[caller.session.id]))
    assert 'Net at ask: 0.' in text and 'Buyout net: 19.' in text
    assert '5% fee' in text and not owner.market.listings


def test_ui_4_f9_services_reach_board_terminal_without_replacing_map(trade_game: tuple[Any, ...]) -> None:
    game, clients, _, _, _ = trade_game
    caller, owner = clients[0], game.core.market
    zone = game.core.world.zones['core-plaza']
    board = zone.objects['civic-notice-board'].spec
    place(game, caller, zone.id, game.core.world.free_tile(zone.id, board.tile))
    act(game, caller, Frame('key', {'k': 'f9', 't': 0}))
    assert owner.views.menus[caller.session.id].kind == 'terminal'
    choose(game, caller, 'm')
    assert owner.views.menus[caller.session.id].kind == 'market'
    act(game, caller, Frame('intent', {'name': 'menu_close', 'args': {}}))
    act(game, caller, Frame('key', {'k': 'm', 't': 0}))
    assert caller.session.id in owner.sim.maps and caller.session.id not in owner.views.menus


def test_ui_4_existing_terminal_e_still_jacks_in(trade_game: tuple[Any, ...]) -> None:
    game, clients, players, _, _ = trade_game
    caller, owner = clients[0], game.core.market
    terminal = game.core.world.zones['core-plaza'].objects['plaza-public-1'].spec
    place(game, caller, 'core-plaza', terminal.tile)
    act(game, caller, Frame('key', {'k': 'e', 't': 0}))
    assert players[0].id in game.core.lattice.presences
    assert caller.session.id not in owner.views.menus


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_4_effective_stats_seller_and_bid_are_width_safe(info: Any, trade_game: tuple[Any, ...], size: tuple[int, int]) -> None:
    game, clients, _, _, terminal = trade_game
    lid = listed(trade_game)
    owner = game.core.market
    owner.execute(clients[1].session, 'bid', {'listing': lid, 'chits': 60})
    game.commit_commerce()
    body = owner.views.body(clients[1].session, Panel('market', terminal, 0))
    assert 'Uses carried' in body['detail'] and 'Loaded' not in body['detail']
    text = render(info, size, owner.commerce.content, body)
    assert 'Trader界1' in text and 'Market界1' in text
    assert '112%' in text and 'Damage' in text and '60' in text
    assert 'D bid' in text and 'Esc/B' in text


@pytest.mark.parametrize('size', [(80, 24), (132, 50)])
def test_ui_4_bounty_totals_show_target_without_posters(info: Any, trade_game: tuple[Any, ...], size: tuple[int, int]) -> None:
    game, clients, players, _, terminal = trade_game
    owner = game.core.market
    for caller, amount in ((clients[0], 100), (clients[2], 200)):
        owner.execute(caller.session, 'post', {'target': players[1].id, 'chits': amount})
        game.commit_commerce()
    body = owner.views.body(clients[1].session, Panel('bounties', terminal, 0))
    text = render(info, size, owner.commerce.content, body)
    assert 'Trader界2' in text and '300' in text and '2 posters' in text
    assert 'Trader界1' not in text and 'Trader界3' not in text
    assert players[0].id not in str(body) and players[2].id not in str(body)


def test_ui_4_bank_c_opens_collection_and_street_c_keeps_chat(trade_game: tuple[Any, ...]) -> None:
    game, clients, _, _, _ = trade_game
    caller, owner = clients[0], game.core.market
    zone = game.core.world.zones['vatside-clinics']
    bank = next(o.spec for o in zone.objects.values() if o.spec.kind == 'bank')
    place(game, caller, zone.id, game.core.world.free_tile(zone.id, bank.tile))
    game.core.commerce.menus[caller.session.id] = CommerceMenu('bank', bank.id, opened=game.clock.now_tick())
    game.step()
    row = game.core.commerce.body(caller.session, game.core.commerce.menus[caller.session.id])['rows'][0]['id']
    act(game, caller, Frame('intent', {'name': 'menu_select', 'args': {'row': row, 'key': 'c'}}))
    assert owner.views.menus[caller.session.id].kind == 'collect'
    assert caller.session.id not in game.core.commerce.menus
    act(game, caller, Frame('intent', {'name': 'menu_close', 'args': {}}))
    act(game, caller, Frame('key', {'k': 'c', 't': 0}))
    assert 'chat' in caller.session.pending_prompts
